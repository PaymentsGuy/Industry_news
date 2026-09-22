from __future__ import annotations

import hashlib
import hmac
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
WORKTREES = ROOT.parent
sys.path[:0] = [
    str(WORKTREES / "cos" / "backend"),
    str(WORKTREES / "action-os" / "scripts"),
    str(WORKTREES / "mios" / "scripts"),
    str(WORKTREES / "mios" / "src"),
]

import action_os_industry_news_intake as action_os_intake
from chief_of_staff.industry_news import IndustryNewsSourceAdapter, build_industry_news_projection
from competitive_radar_mios_bridge import bridge_package
from competitive_radar_package import emit_package
from mios.db import Database

KEY = b"integration-vault-key"


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _industry_package(root: Path) -> Path:
    package_path = root / "packages" / "2026-09-21" / "delivery.json"
    package_path.parent.mkdir(parents=True)
    body = "# ASA Industry News Pulse — 2026-09-21\n\nSix material signals.\n"
    content_sha256 = hashlib.sha256(body.encode()).hexdigest()
    vault_relative = "Atlas/competitive-intel/intelligence-briefs/2026-09-21 - ASA Intelligence Brief.md"
    vault_file = root / "vault" / vault_relative
    vault_file.parent.mkdir(parents=True)
    vault_file.write_text(body)
    receipt = {
        "destination": "vault",
        "transaction_id": "pulse-tx-1",
        "brief_id": "industry-pulse-2026-09-21",
        "content_sha256": content_sha256,
        "vault_path": vault_relative,
        "vault_file_sha256": hashlib.sha256(vault_file.read_bytes()).hexdigest(),
        "readback": True,
        "receipt_id": "vault-receipt-1",
    }
    receipt["signature"] = hmac.new(KEY, _canonical(receipt), hashlib.sha256).hexdigest()
    signals = [
        {
            "signal_id": f"signal-{number}",
            "title": f"Material signal {number}",
            "classification": "material",
            "evidence_links": [f"https://evidence.example/{number}"],
            "proposed_decision": "Review the signal",
            "proposed_next_action": "Assign follow-up",
            "proposed_owner": "Troy",
        }
        for number in range(6)
    ]
    package = {
        "brief_id": "industry-pulse-2026-09-21",
        "brief_date": "2026-09-21",
        "cadence": "weekday_daily",
        "producer": "industry_news",
        "interval": {"start": "2026-09-18T06:30:00-07:00", "end": "2026-09-21T06:30:00-07:00"},
        "canonical_body": body,
        "content_sha256": content_sha256,
        "transaction_id": "pulse-tx-1",
        "classification_counts": {"material": 6, "monitor": 0, "noise": 0, "duplicate": 0, "needs_validation": 0},
        "material_signal_count": 6,
        "signals": signals,
        "destinations": {
            "repository": {"status": "verified", "commit_sha": "a" * 40},
            "slack": {"status": "verified", "workspace_id": "T1", "channel_id": "C1", "client_msg_id": "msg-1", "permalink": "https://slack.example/1", "readback_sha256": content_sha256},
            "vault": {"status": "verified", **receipt},
        },
        "status": "fully_delivered",
    }
    package_path.write_text(json.dumps(package))
    return package_path


def test_isolated_industry_and_radar_chain_has_read_only_consumers_and_no_downstream_work(tmp_path: Path) -> None:
    package_path = _industry_package(tmp_path)
    adapter = IndustryNewsSourceAdapter(
        package_root=package_path.parent.parent,
        vault_root=tmp_path / "vault",
        boundary=SimpleNamespace(status="read_only"),
        signing_key=KEY,
    )
    refreshed = adapter.refresh(scope={}, attempt_id="chain-1", now=datetime(2026, 9, 21, 7, tzinfo=ZoneInfo("America/Los_Angeles")))
    projection = build_industry_news_projection(refreshed.records, now=datetime(2026, 9, 21, 7, tzinfo=ZoneInfo("America/Los_Angeles")))
    assert refreshed.search_state == "succeeded"
    assert projection["daily"]["material_count"] == 6
    assert projection["external_writes_performed"] is False

    action_payload = {
        "pulse_id": "industry-pulse-2026-09-21",
        "pulse_sha256": json.loads(package_path.read_text())["content_sha256"],
        "pulse_link": package_path.as_uri(),
        "signal_id": "signal-0",
        "evidence_link": "https://evidence.example/0",
        "classification": "material",
        "proposed_decision": "Review the signal",
        "proposed_next_action": "Assign follow-up",
        "proposed_owner": "Troy",
    }
    action_payload["idempotency_key"] = "industry-news:" + hashlib.sha256(
        json.dumps({"pulse_id": action_payload["pulse_id"], "signal_id": action_payload["signal_id"]}, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:24]
    candidate = action_os_intake.submit_candidate(action_payload, root=tmp_path / "action-os", occurred_at="2026-09-21T07:00:00-07:00")
    assert candidate["external_writes_performed"] is False

    vault = tmp_path / "radar-vault"
    report = vault / "Atlas/competitive-intel/ASA Competitive Radar Weekly — 2026-09-21.md"
    evidence = vault / "Atlas/raw/competitive-intel/2026-09-21/evidence.md"
    report.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    report.write_text("# Competitive Radar\n")
    evidence.write_text("source evidence\n")
    emit_package("2026-09-21", vault_root=vault, producer_run_id="chain-1", completed_at="2026-09-21T12:00:00Z")
    db_path = tmp_path / "mios.db"
    imported = bridge_package("2026-09-21", vault_root=vault, db_path=db_path, test_mode=True)
    replay = bridge_package("2026-09-21", vault_root=vault, db_path=db_path, test_mode=True)
    assert imported["status"] == "complete"
    assert replay["intake_id"] == imported["intake_id"]
    db = Database(db_path, test_mode=True)
    try:
        row = db.conn.execute("SELECT state FROM competitive_radar_intakes WHERE intake_id=?", (imported["intake_id"],)).fetchone()
        assert row["state"] == "review_ready"
    finally:
        db.close()
