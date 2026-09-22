from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

try:
    from intel import delivery
except ModuleNotFoundError:  # pragma: no cover
    import delivery


class VaultConflict(RuntimeError):
    """A same-date Vault artifact exists with a different canonical identity."""


def _atomic_write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
        staged = Path(handle.name)
    staged.replace(path)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _vault_document(package: dict[str, Any]) -> str:
    frontmatter = (
        "---\n"
        f"brief_id: {package['brief_id']}\n"
        f"brief_date: {package['brief_date']}\n"
        f"cadence: {package['cadence']}\n"
        f"producer: {package['producer']}\n"
        f"content_sha256: {package['content_sha256']}\n"
        f"producer_receipt_id: {package.get('producer_receipt', {}).get('receipt_id') or package['transaction_id']}\n"
        f"delivery_transaction_id: {package['transaction_id']}\n"
        "---\n\n"
    )
    return frontmatter + package["canonical_body"]


def _verify_commit_pinned_producer(package_file: Path, package: dict[str, Any]) -> None:
    receipt = package.get("producer_receipt")
    required = {"repository_commit", "brief_path", "package_path", "transaction_id", "content_sha256", "receipt_id"}
    if not isinstance(receipt, dict) or any(not receipt.get(field) for field in required):
        raise ValueError("commit-pinned producer receipt is required")
    commit = str(receipt["repository_commit"])
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit.lower()):
        raise ValueError("producer receipt repository commit is invalid")
    root = subprocess.run(
        ["git", "-C", str(package_file.parent), "rev-parse", "--show-toplevel"],
        check=False, capture_output=True, text=True,
    )
    if root.returncode:
        raise ValueError("producer package must be inside a Git repository")
    repo = Path(root.stdout.strip())
    for path in (receipt["brief_path"], receipt["package_path"]):
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise ValueError("producer receipt path is invalid")
    if (repo / receipt["package_path"]).resolve() != package_file.resolve():
        raise ValueError("producer receipt package path does not match the package")
    def show(path: str) -> bytes:
        result = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"], check=False, capture_output=True)
        if result.returncode:
            raise ValueError("producer receipt commit does not contain the declared source")
        return result.stdout
    brief = delivery.canonical_body(show(str(receipt["brief_path"])).decode("utf-8"))
    committed_package = json.loads(show(str(receipt["package_path"])).decode("utf-8"))
    if (
        receipt["transaction_id"] != package["transaction_id"]
        or receipt["content_sha256"] != package["content_sha256"]
        or delivery.sha256_text(brief) != package["content_sha256"]
        or committed_package.get("transaction_id") != package["transaction_id"]
        or committed_package.get("content_sha256") != package["content_sha256"]
    ):
        raise ValueError("producer receipt does not match committed package bytes")


def archive_package(
    package_file: Path,
    *,
    vault_root: Path,
    signing_key: bytes,
) -> dict[str, Any]:
    if not signing_key:
        raise ValueError("MIOS_VAULT_RECEIPT_KEY is required")
    package = json.loads(package_file.read_text(encoding="utf-8"))
    try:
        parsed_date = date.fromisoformat(str(package.get("brief_date") or ""))
    except ValueError as exc:
        raise ValueError("brief date must be strict ISO YYYY-MM-DD") from exc
    if parsed_date.isoformat() != package.get("brief_date"):
        raise ValueError("brief date must be strict ISO YYYY-MM-DD")
    for field in ("brief_id", "cadence", "producer", "content_sha256", "transaction_id"):
        value = package.get(field)
        if not isinstance(value, str) or not value or any(character in value for character in "\r\n"):
            raise ValueError(f"package {field} is missing or unsafe")
    if package.get("cadence") != "weekday_daily":
        raise ValueError("Vault bridge accepts weekday Industry News Pulse packages only")
    if delivery.sha256_text(delivery.canonical_body(package.get("canonical_body", ""))) != package.get("content_sha256"):
        raise ValueError("delivery package canonical body hash mismatch")
    _verify_commit_pinned_producer(package_file, package)

    relative = Path("Atlas/competitive-intel/intelligence-briefs") / f"{package['brief_date']} - ASA Intelligence Brief.md"
    destination = (vault_root / relative).resolve()
    root = vault_root.resolve()
    destination.relative_to(root)
    document = _vault_document(package)
    expected_bytes = document.encode("utf-8")
    if destination.exists():
        if destination.read_bytes() != expected_bytes:
            raise VaultConflict(f"Vault artifact conflict at {relative}")
    else:
        _atomic_write(destination, document)
    readback = destination.read_bytes()
    if readback != expected_bytes:
        raise RuntimeError("Vault readback mismatch")

    receipt: dict[str, Any] = {
        "destination": "vault",
        "transaction_id": package["transaction_id"],
        "brief_id": package["brief_id"],
        "content_sha256": package["content_sha256"],
        "vault_path": str(relative),
        "vault_file_sha256": _sha256_bytes(readback),
        "readback": True,
    }
    receipt["receipt_id"] = delivery._stable_id(
        receipt["transaction_id"], receipt["vault_path"], receipt["vault_file_sha256"], prefix="vault-receipt"
    )
    receipt["signature"] = delivery.sign_receipt(receipt, signing_key)
    receipt_file = package_file.with_name("vault-receipt.json")
    delivery._atomic_json(receipt_file, receipt)
    return delivery.import_receipt(package_file, receipt_file, verification_key=signing_key)


def archive_pending_packages(
    package_root: Path,
    *,
    vault_root: Path,
    signing_key: bytes,
) -> dict[str, int]:
    result = {"archived": 0, "failed": 0, "skipped": 0}
    for package_file in sorted(Path(package_root).glob("*/delivery.json")):
        try:
            package = json.loads(package_file.read_text(encoding="utf-8"))
            destinations = package.get("destinations") or {}
            if (destinations.get("vault") or {}).get("status") == "verified" or any(
                (destinations.get(name) or {}).get("status") != "verified" for name in ("repository", "slack")
            ):
                result["skipped"] += 1
                continue
            archive_package(
                package_file,
                vault_root=vault_root,
                signing_key=signing_key,
            )
            result["archived"] += 1
        except Exception:
            result["failed"] += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive one verified Industry News Pulse to the local Vault")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--package-file", type=Path)
    source.add_argument("--package-root", type=Path)
    parser.add_argument("--vault-root", required=True, type=Path)
    args = parser.parse_args()
    signing_key = os.environ.get("MIOS_VAULT_RECEIPT_KEY", "").encode("utf-8")
    result = (
        archive_package(args.package_file, vault_root=args.vault_root, signing_key=signing_key)
        if args.package_file
        else archive_pending_packages(args.package_root, vault_root=args.vault_root, signing_key=signing_key)
    )
    print(json.dumps(result, indent=2))
    return 1 if isinstance(result, dict) and result.get("failed", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
