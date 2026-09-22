from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from intel import delivery
from intel.vault_bridge import VaultConflict, archive_package, archive_pending_packages


def _package(tmp_path: Path) -> Path:
    brief = tmp_path / "repo" / "intel" / "2026-09-21" / "brief.md"
    brief.parent.mkdir(parents=True)
    brief.write_text(
        "# ASA Industry News Pulse — 2026-09-21\n\n"
        "**Reporting interval:** 2026-09-18T06:30:00-07:00 to 2026-09-21T06:30:00-07:00\n"
        "**Candidates classified:** 0\n**Material signals:** 0\n"
        "**Classification counts:** material=0; monitor=0; noise=0; duplicate=0; needs_validation=0\n\n"
        "## Top summary\n\nNo evidence-backed material signals.\n\n"
        "## Material signals\n\nNo evidence-backed material signals.\n\n"
        "## Candidate disposition\n\nNo candidates.\n\n## References\n"
    )
    package = brief.with_name("delivery.json")
    delivery.create_package(
        brief,
        package,
        brief_date="2026-09-21",
        cadence="weekday_daily",
        workspace_id="T_TEST",
        interval={"start": "2026-09-18T06:30:00-07:00", "end": "2026-09-21T06:30:00-07:00"},
    )
    repo = tmp_path / "repo"
    for args in (
        ("init",), ("config", "user.email", "tests@example.test"),
        ("config", "user.name", "Tests"), ("add", "intel/2026-09-21/brief.md", "intel/2026-09-21/delivery.json"),
        ("commit", "-m", "fixture package"),
    ):
        subprocess.run(("git", "-C", str(repo), *args), check=True, capture_output=True)
    initial_commit = subprocess.run(("git", "-C", str(repo), "rev-parse", "HEAD"), check=True, capture_output=True, text=True).stdout.strip()
    delivery.mark_repository(package, initial_commit, repo_root=repo)
    subprocess.run(("git", "-C", str(repo), "add", "intel/2026-09-21/delivery.json"), check=True, capture_output=True)
    subprocess.run(("git", "-C", str(repo), "commit", "-m", "fixture receipt"), check=True, capture_output=True)
    return package


def test_vault_bridge_writes_reads_signs_and_imports_receipt(tmp_path: Path) -> None:
    package = _package(tmp_path)
    vault = tmp_path / "vault"

    result = archive_package(package, vault_root=vault, signing_key=b"fixture-key")

    archived = vault / "Atlas/competitive-intel/intelligence-briefs/2026-09-21 - ASA Intelligence Brief.md"
    assert archived.is_file()
    assert result["destinations"]["vault"]["status"] == "verified"
    assert result["destinations"]["vault"]["vault_file_sha256"]
    assert "signature" in result["destinations"]["vault"]
    assert not package.with_name("action-os-receipt.json").exists()


def test_vault_bridge_matching_replay_is_idempotent(tmp_path: Path) -> None:
    package = _package(tmp_path)
    vault = tmp_path / "vault"
    first = archive_package(package, vault_root=vault, signing_key=b"fixture-key")
    second = archive_package(package, vault_root=vault, signing_key=b"fixture-key")
    assert second["destinations"]["vault"]["receipt_id"] == first["destinations"]["vault"]["receipt_id"]


def test_vault_bridge_rejects_a_package_without_a_commit_pinned_producer_receipt(tmp_path: Path) -> None:
    package_file = _package(tmp_path)
    package = json.loads(package_file.read_text())
    del package["producer_receipt"]
    package_file.write_text(json.dumps(package))

    with pytest.raises(ValueError, match="producer receipt"):
        archive_package(package_file, vault_root=tmp_path / "vault", signing_key=b"fixture-key")

    assert not (tmp_path / "vault").exists()


def test_vault_bridge_fails_closed_on_same_date_hash_conflict(tmp_path: Path) -> None:
    package = _package(tmp_path)
    vault = tmp_path / "vault"
    destination = vault / "Atlas/competitive-intel/intelligence-briefs/2026-09-21 - ASA Intelligence Brief.md"
    destination.parent.mkdir(parents=True)
    destination.write_text("different existing artifact\n")

    with pytest.raises(VaultConflict):
        archive_package(package, vault_root=vault, signing_key=b"fixture-key")

    assert destination.read_text() == "different existing artifact\n"
    assert json.loads(package.read_text())["destinations"]["vault"]["status"] == "pending"


@pytest.mark.parametrize("brief_date", ["../escape", "2026-09-21\nforged: true", "not-a-date"])
def test_vault_bridge_rejects_unsafe_identity_fields_before_writing(tmp_path: Path, brief_date: str) -> None:
    package_file = _package(tmp_path)
    package = json.loads(package_file.read_text())
    package["brief_date"] = brief_date
    package_file.write_text(json.dumps(package))

    with pytest.raises(ValueError, match="brief date"):
        archive_package(package_file, vault_root=tmp_path / "vault", signing_key=b"fixture-key")

    assert not list((tmp_path / "vault").rglob("*.md"))


def test_local_bridge_discovers_only_remote_verified_pending_packages(tmp_path: Path) -> None:
    package_file = _package(tmp_path)
    package = json.loads(package_file.read_text())
    package["destinations"]["repository"] = {"status": "verified", "commit_sha": "a" * 40}
    package["destinations"]["slack"].update({"status": "verified", "message_ts": "1", "permalink": "https://slack.example/1", "readback_sha256": package["content_sha256"]})
    package["status"] = "partial_delivery"
    package_file.write_text(json.dumps(package))

    first = archive_pending_packages(tmp_path / "repo" / "intel", vault_root=tmp_path / "vault", signing_key=b"fixture-key")
    replay = archive_pending_packages(tmp_path / "repo" / "intel", vault_root=tmp_path / "vault", signing_key=b"fixture-key")

    assert first == {"archived": 1, "failed": 0, "skipped": 0}
    assert replay == {"archived": 0, "failed": 0, "skipped": 1}
