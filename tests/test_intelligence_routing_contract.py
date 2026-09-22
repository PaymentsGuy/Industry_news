from __future__ import annotations

import json
from pathlib import Path

import pytest

from intel.routing_contract import (
    ContractError,
    extract_daily_pulse_metadata,
    load_competitive_radar_package,
    load_industry_pulse_package,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_industry_pulse_fixture_freezes_cross_owner_identity() -> None:
    package = load_industry_pulse_package(
        FIXTURES / "industry_pulse" / "2026-09-21" / "brief.md",
        FIXTURES / "industry_pulse" / "2026-09-21" / "delivery.json",
    )

    assert package["cadence"] == "weekday_daily"
    assert package["interval"] == {
        "start": "2026-09-18T06:30:00-07:00",
        "end": "2026-09-21T06:30:00-07:00",
    }
    assert package["classification_counts"] == {
        "material": 6,
        "monitor": 1,
        "noise": 1,
        "duplicate": 1,
        "needs_validation": 1,
    }
    assert package["material_signal_count"] == 6
    assert set(package["destinations"]) == {"repository", "slack", "vault"}
    assert len(package["signals"]) == 6


def test_industry_pulse_rejects_mismatched_body_hash(tmp_path: Path) -> None:
    source = FIXTURES / "industry_pulse" / "2026-09-21"
    brief = tmp_path / "brief.md"
    receipt = tmp_path / "delivery.json"
    brief.write_text((source / "brief.md").read_text() + "tampered\n")
    receipt.write_text((source / "delivery.json").read_text())

    with pytest.raises(ContractError, match="canonical content hash"):
        load_industry_pulse_package(brief, receipt)


def test_industry_pulse_rejects_missing_destination_receipt(tmp_path: Path) -> None:
    source = FIXTURES / "industry_pulse" / "2026-09-21"
    brief = source / "brief.md"
    payload = json.loads((source / "delivery.json").read_text())
    del payload["destinations"]["vault"]
    receipt = tmp_path / "delivery.json"
    receipt.write_text(json.dumps(payload))

    with pytest.raises(ContractError, match="destination identities"):
        load_industry_pulse_package(brief, receipt)


def test_runtime_contract_preserves_actionable_signal_evidence_and_proposal() -> None:
    counts, signals = extract_daily_pulse_metadata(
        "**Classification counts:** material=1; monitor=0; noise=0; duplicate=0; needs_validation=0\n\n"
        "## Material signals\n\n### Signal A\n"
        "**Evidence:** https://evidence.example/a\n"
        "**Proposed decision:** Review channel change\n"
        "**Proposed next action:** Confirm owner response\n"
        "**Proposed owner:** Troy\n\n## Candidate disposition\n",
        "industry-pulse-2026-09-21",
    )

    assert counts["material"] == 1
    assert signals[0]["evidence_links"] == ["https://evidence.example/a"]
    assert signals[0]["proposed_decision"] == "Review channel change"


def test_competitive_radar_fixture_freezes_evidence_identity() -> None:
    package = load_competitive_radar_package(
        FIXTURES / "competitive_radar" / "2026-09-21" / "report.md",
        FIXTURES / "competitive_radar" / "2026-09-21" / "manifest.json",
    )

    assert package["report_date"] == "2026-09-21"
    assert package["atlas_backlink"].endswith("ASA Competitive Radar Weekly — 2026-09-21.md")
    assert package["transaction_id"] == "competitive-radar-2026-09-21-fixture-v1"
    assert len(package["evidence"]) == 2


def test_competitive_radar_rejects_missing_evidence_hash(tmp_path: Path) -> None:
    source = FIXTURES / "competitive_radar" / "2026-09-21"
    payload = json.loads((source / "manifest.json").read_text())
    del payload["evidence"][0]["sha256"]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload))

    with pytest.raises(ContractError, match="evidence manifest"):
        load_competitive_radar_package(source / "report.md", manifest)
