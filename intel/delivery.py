#!/usr/bin/env python3
"""Receipt-bound ASA Intelligence Brief delivery coordinator.

This module is the single owner for future Slack delivery. It never claims full
multi-destination delivery until repository, Slack, and Vault receipts reconcile
against one transaction and canonical content hash.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import uuid
import subprocess
from pathlib import Path
from typing import Any, Protocol

import click
import requests

DEFAULT_CHANNEL = "C0B1TPFSZKJ"
SLACK_API = "https://slack.com/api"


class AmbiguousDelivery(RuntimeError):
    """A provider may have accepted the write, so an automatic retry is unsafe."""

class SlackApiError(RuntimeError):
    pass


class SlackClient(Protocol):
    def workspace_id(self) -> str: ...
    def post_message(self, *, channel: str, text: str, client_msg_id: str) -> dict[str, Any]: ...
    def find_by_client_msg_id(self, *, channel: str, client_msg_id: str) -> list[dict[str, Any]]: ...
    def get_message(self, *, channel: str, ts: str) -> dict[str, Any] | None: ...


def canonical_body(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_id(*parts: str, prefix: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        staged = Path(handle.name)
    staged.replace(path)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _receipt_bytes(receipt: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in receipt.items() if key != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_receipt(receipt: dict[str, Any], key: bytes) -> str:
    if not key:
        raise ValueError("Vault receipt signing key is required")
    return hmac.new(key, _receipt_bytes(receipt), hashlib.sha256).hexdigest()


def _refresh_status(package: dict[str, Any]) -> None:
    states = package["destinations"]
    if all(states[name]["status"] == "verified" for name in ("repository", "slack", "vault")):
        package["status"] = "fully_delivered"
    elif any(row["status"] == "verified" for row in states.values()):
        package["status"] = "partial_delivery"
    elif any(row["status"] == "ambiguous_outcome" for row in states.values()):
        package["status"] = "ambiguous_outcome"
    else:
        package["status"] = "pending"


def create_package(
    brief_file: Path,
    package_file: Path,
    *,
    brief_date: str,
    cadence: str,
    workspace_id: str,
    producer: str = "industry_news",
    workflow_run_id: str | None = None,
) -> dict[str, Any]:
    body = canonical_body(brief_file.read_text(encoding="utf-8"))
    content_hash = sha256_text(body)
    brief_id = f"asa-intelligence-brief-{brief_date}"
    transaction_id = _stable_id(brief_id, content_hash, producer, prefix="brief-delivery")
    client_msg_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"mios:{transaction_id}:{DEFAULT_CHANNEL}"))
    if not workspace_id:
        raise ValueError("Slack workspace identity is required")
    payload = {
        "version": 2,
        "brief_id": brief_id,
        "brief_date": brief_date,
        "cadence": cadence,
        "producer": producer,
        "canonical_body": body,
        "content_sha256": content_hash,
        "source_repository_path": str(brief_file),
        "transaction_id": transaction_id,
        "workflow_run_id": workflow_run_id or os.environ.get("GITHUB_RUN_ID") or None,
        "destinations": {
            "repository": {"status": "pending", "commit_sha": None},
            "slack": {
                "status": "pending",
                "workspace_id": workspace_id,
                "channel_id": DEFAULT_CHANNEL,
                "client_msg_id": client_msg_id,
                "attempt_count": 0,
            },
            "vault": {"status": "pending"},
        },
        "status": "pending",
    }
    if package_file.exists():
        existing = _read(package_file)
        expected = (brief_id, brief_date, cadence, producer, content_hash, transaction_id, workspace_id, workflow_run_id or os.environ.get("GITHUB_RUN_ID") or None)
        actual = (existing.get("brief_id"), existing.get("brief_date"), existing.get("cadence"), existing.get("producer"), existing.get("content_sha256"), existing.get("transaction_id"), existing.get("destinations", {}).get("slack", {}).get("workspace_id"), existing.get("workflow_run_id"))
        if actual != expected:
            raise ValueError("existing delivery package has a different immutable identity")
        return existing
    _atomic_json(package_file, payload)
    return payload


def mark_repository(package_file: Path, commit_sha: str, *, repo_root: Path) -> dict[str, Any]:
    package = _read(package_file)
    repo_root = Path(repo_root).resolve()
    if len(commit_sha) != 40 or any(char not in "0123456789abcdef" for char in commit_sha.lower()):
        raise ValueError("invalid repository commit SHA")

    def show(path_value: str) -> bytes:
        path = Path(path_value)
        rel = str(path.resolve().relative_to(repo_root)) if path.is_absolute() else str(path)
        result = subprocess.run(["git", "-C", str(repo_root), "show", f"{commit_sha}:{rel}"], capture_output=True)
        if result.returncode:
            raise ValueError(f"repository commit does not contain {rel}")
        return result.stdout

    brief_bytes = show(package["source_repository_path"])
    if sha256_text(canonical_body(brief_bytes.decode("utf-8"))) != package["content_sha256"]:
        raise ValueError("repository brief readback hash mismatch")
    package_rel = str(Path(package_file).resolve().relative_to(repo_root))
    committed_package = json.loads(show(package_rel).decode("utf-8"))
    if committed_package.get("transaction_id") != package["transaction_id"] or committed_package.get("content_sha256") != package["content_sha256"]:
        raise ValueError("repository package readback mismatch")
    brief_path = Path(package["source_repository_path"])
    brief_rel = str(brief_path.resolve().relative_to(repo_root)) if brief_path.is_absolute() else str(brief_path)
    package_rel = str(Path(package_file).resolve().relative_to(repo_root))
    producer_receipt = {
        "repository_commit": commit_sha,
        "brief_path": brief_rel,
        "package_path": package_rel,
        "workflow_run_id": package.get("workflow_run_id"),
        "transaction_id": package["transaction_id"],
        "content_sha256": package["content_sha256"],
    }
    producer_receipt["receipt_id"] = _stable_id(
        producer_receipt["repository_commit"],
        producer_receipt["brief_path"],
        producer_receipt["package_path"],
        str(producer_receipt["workflow_run_id"] or ""),
        producer_receipt["transaction_id"],
        producer_receipt["content_sha256"],
        prefix="producer-receipt",
    )
    existing_receipt = package.get("producer_receipt")
    if existing_receipt and existing_receipt != producer_receipt:
        raise ValueError("existing producer receipt has a different immutable identity")
    package["producer_receipt"] = producer_receipt
    package["destinations"]["repository"] = {"status": "verified", "commit_sha": commit_sha}
    _refresh_status(package)
    _atomic_json(package_file, package)
    return package


def _verify_slack_message(package: dict[str, Any], message: dict[str, Any], *, expected_ts: str | None = None) -> dict[str, Any]:
    row = package["destinations"]["slack"]
    if expected_ts and str(message.get("ts")) != expected_ts:
        raise AmbiguousDelivery("Slack native readback identity mismatch")
    if message.get("client_msg_id") != row.get("client_msg_id") or not message.get("permalink"):
        raise AmbiguousDelivery("Slack native readback identity mismatch")
    actual = sha256_text(canonical_body(str(message.get("text", ""))))
    if actual != package["content_sha256"]:
        raise ValueError("Slack native readback content hash mismatch")
    row.update(
        {
            "status": "verified",
            "message_ts": str(message["ts"]),
            "permalink": message.get("permalink"),
            "readback_sha256": actual,
        }
    )
    _refresh_status(package)
    return package


def resume_slack(package_file: Path, client: SlackClient, *, channel: str) -> dict[str, Any]:
    package = _read(package_file)
    row = package["destinations"]["slack"]
    if row.get("channel_id") != channel:
        raise ValueError("Slack channel does not match the delivery package")
    if row["status"] == "verified":
        return package
    if client.workspace_id() != row.get("workspace_id"):
        raise ValueError("Slack workspace does not match the delivery package")

    client_msg_id = row["client_msg_id"]
    matches = client.find_by_client_msg_id(channel=channel, client_msg_id=client_msg_id)
    if len(matches) == 1:
        package = _verify_slack_message(package, matches[0])
        _atomic_json(package_file, package)
        return package
    if len(matches) > 1:
        row["status"] = "ambiguous_outcome"
        _refresh_status(package)
        _atomic_json(package_file, package)
        raise AmbiguousDelivery("Multiple Slack messages share the deterministic client identity")
    if row["status"] == "ambiguous_outcome":
        raise AmbiguousDelivery("Slack outcome is ambiguous; unique native reconciliation is required before retry")

    row["attempt_count"] = int(row.get("attempt_count", 0)) + 1
    row["status"] = "attempting"
    _atomic_json(package_file, package)
    try:
        response = client.post_message(channel=channel, text=package["canonical_body"], client_msg_id=client_msg_id)
    except Exception as exc:
        package = _read(package_file)
        package["destinations"]["slack"]["status"] = "ambiguous_outcome"
        package["destinations"]["slack"]["last_error"] = type(exc).__name__
        _refresh_status(package)
        _atomic_json(package_file, package)
        raise AmbiguousDelivery("Slack response was lost; automatic repost is blocked") from exc

    ts = str(response.get("ts", ""))
    if not response.get("ok") or not ts:
        row["status"] = "failed"
        row["last_error"] = str(response.get("error", "missing native timestamp"))
        _refresh_status(package)
        _atomic_json(package_file, package)
        raise RuntimeError(f"Slack rejected delivery: {row['last_error']}")
    try:
        message = client.get_message(channel=channel, ts=ts)
    except Exception as exc:
        row["status"] = "ambiguous_outcome"
        row["last_error"] = type(exc).__name__
        _refresh_status(package)
        _atomic_json(package_file, package)
        raise AmbiguousDelivery("Slack acknowledged the write but native readback outcome is ambiguous") from exc
    if message is None:
        row["status"] = "ambiguous_outcome"
        _refresh_status(package)
        _atomic_json(package_file, package)
        raise AmbiguousDelivery("Slack acknowledged the write but native readback failed")
    package = _verify_slack_message(package, message, expected_ts=ts)
    _atomic_json(package_file, package)
    return package


def import_receipt(package_file: Path, receipt_file: Path, *, verification_key: bytes) -> dict[str, Any]:
    package = _read(package_file)
    receipt = _read(receipt_file)
    signature = str(receipt.get("signature", ""))
    if not hmac.compare_digest(signature, sign_receipt(receipt, verification_key)):
        raise ValueError("Vault receipt signature is invalid")
    if receipt.get("destination") != "vault":
        raise ValueError("Only Vault receipts may be imported by this command")
    if receipt.get("transaction_id") != package["transaction_id"]:
        raise ValueError("Vault receipt transaction does not match")
    if receipt.get("brief_id") != package["brief_id"]:
        raise ValueError("Vault receipt brief identity does not match")
    if receipt.get("content_sha256") != package["content_sha256"]:
        raise ValueError("Vault receipt content hash does not match")
    if receipt.get("readback") is not True or not receipt.get("vault_file_sha256"):
        raise ValueError("Vault receipt lacks destination-owned readback")
    package["destinations"]["vault"] = {"status": "verified", **receipt}
    _refresh_status(package)
    _atomic_json(package_file, package)
    return package


class SlackWebApiClient:
    def __init__(self, token: str, *, timeout: int = 30):
        if not token:
            raise ValueError("SLACK_BOT_TOKEN is required")
        self.token = token
        self.timeout = timeout

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{SLACK_API}/{method}",
            headers={"Authorization": f"Bearer {self.token}"},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise SlackApiError(str(data.get("error", "Slack API error")))
        return data

    def workspace_id(self) -> str:
        return str(self._call("auth.test", {}).get("team_id", ""))

    def post_message(self, *, channel: str, text: str, client_msg_id: str) -> dict[str, Any]:
        return self._call("chat.postMessage", {"channel": channel, "text": text, "mrkdwn": True, "client_msg_id": client_msg_id})

    def _history(self, channel: str) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        cursor = ""
        while True:
            payload: dict[str, Any] = {"channel": channel, "limit": 100}
            if cursor:
                payload["cursor"] = cursor
            data = self._call("conversations.history", payload)
            messages.extend(data.get("messages", []))
            cursor = str(data.get("response_metadata", {}).get("next_cursor", "")).strip()
            if not cursor:
                return messages

    def find_by_client_msg_id(self, *, channel: str, client_msg_id: str) -> list[dict[str, Any]]:
        return [row for row in self._history(channel) if row.get("client_msg_id") == client_msg_id]

    def get_message(self, *, channel: str, ts: str) -> dict[str, Any] | None:
        data = self._call("conversations.replies", {"channel": channel, "ts": ts, "limit": 1})
        rows = list(data.get("messages", []))
        if not rows:
            return None
        row = dict(rows[0])
        row["permalink"] = self._call("chat.getPermalink", {"channel": channel, "message_ts": ts}).get("permalink")
        return row


def publish_brief(brief_file: Path, package_file: Path | None = None) -> dict[str, Any]:
    package_file = package_file or brief_file.with_name("delivery.json")
    if not package_file.exists():
        create_package(brief_file, package_file, brief_date=brief_file.parent.name, cadence="weekly", workspace_id=os.environ.get("SLACK_TEAM_ID", ""))
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    channel = os.environ.get("SLACK_CHANNEL_ID", DEFAULT_CHANNEL)
    return resume_slack(package_file, SlackWebApiClient(token), channel=channel)


@click.group()
def cli() -> None:
    """Manage a receipt-bound brief delivery transaction."""


@cli.command("create")
@click.option("--brief-file", required=True, type=click.Path(path_type=Path))
@click.option("--package-file", required=True, type=click.Path(path_type=Path))
@click.option("--brief-date", required=True)
@click.option("--cadence", default="weekly")
@click.option("--workspace-id", required=True)
@click.option("--workflow-run-id", default=lambda: os.environ.get("GITHUB_RUN_ID", ""))
def create_cmd(brief_file: Path, package_file: Path, brief_date: str, cadence: str, workspace_id: str, workflow_run_id: str) -> None:
    click.echo(json.dumps(create_package(brief_file, package_file, brief_date=brief_date, cadence=cadence, workspace_id=workspace_id, workflow_run_id=workflow_run_id or None), indent=2))


@cli.command("mark-repository")
@click.option("--package-file", required=True, type=click.Path(path_type=Path))
@click.option("--commit-sha", required=True)
def mark_repository_cmd(package_file: Path, commit_sha: str) -> None:
    click.echo(json.dumps(mark_repository(package_file, commit_sha, repo_root=Path(".")), indent=2))


@cli.command("resume-slack")
@click.option("--package-file", required=True, type=click.Path(path_type=Path))
@click.option("--channel", default=DEFAULT_CHANNEL)
def resume_cmd(package_file: Path, channel: str) -> None:
    click.echo(json.dumps(resume_slack(package_file, SlackWebApiClient(os.environ.get("SLACK_BOT_TOKEN", "")), channel=channel), indent=2))


@cli.command("import-receipt")
@click.option("--package-file", required=True, type=click.Path(path_type=Path))
@click.option("--receipt-file", required=True, type=click.Path(path_type=Path))
def import_cmd(package_file: Path, receipt_file: Path) -> None:
    key = os.environ.get("MIOS_VAULT_RECEIPT_KEY", "").encode("utf-8")
    click.echo(json.dumps(import_receipt(package_file, receipt_file, verification_key=key), indent=2))


if __name__ == "__main__":
    cli()
