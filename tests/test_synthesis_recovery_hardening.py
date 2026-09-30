import json
from datetime import date

import pytest

from intel.brief_contract import BriefContractError
from intel.pipeline import synthesize_brief


def _record(item_id: str, title: str, source_url: str, published_date: str) -> dict:
    return {
        "id": item_id,
        "watchlist_bucket": "channel_partners",
        "watchlist_entity": title,
        "signal_type": "partnership",
        "roadmap_areas": ["one_view"],
        "relevance_score": 2,
        "headline_paraphrase": f"{title} changed.",
        "why_it_matters_for_asa": "It affects ASA positioning.",
        "uncertainty_flags": [],
        "duplicate_of_id": None,
        "_source_item": {
            "id": item_id,
            "title": title,
            "source": "Example News",
            "source_url": source_url,
            "published_date": published_date,
        },
    }


def _candidate() -> str:
    return (
        "# ASA Weekly Intelligence Brief — Week of 2026-09-14\n\n"
        "**Items reviewed:** 2\n"
        "**Items surfaced:** 1\n"
        "**Items deduped against ledger:** 0\n"
        "**This week's headline:** Fresh source changed.\n\n"
        "## TL;DR\n\n1. Fresh source changed [REF 1].\n\n"
        "## By roadmap area\n\n**Vault.** Fresh source changed [REF 1].\n\n"
        "## Watchlist movement\n\n"
        "| Entity | Signal type | One-line detail | Status | Ref |\n"
        "|---|---|---|---|---|\n"
        "| Fresh source | Partnership | Changed | New | [REF 1] |\n\n"
        "## Open questions for the team\n\n1. What next?\n\n"
        "## References\n\n"
        '1. Model, "Wrong reference," 2026-01-01. https://model.invalid — *Wrong.*\n'
    )


def test_synthesis_uses_fresh_catalog_and_materializes_reference_metadata(tmp_path):
    in_file = tmp_path / "triaged.jsonl"
    out_file = tmp_path / "brief.md"
    ledger = tmp_path / "ledger.json"
    registry = tmp_path / "event_registry.json"
    fresh = _record(
        "fresh-item",
        "Fresh source",
        "https://example.com/fresh",
        "Sun, 14 Sep 2026 12:00:00 GMT",
    )
    stale = _record(
        "stale-item",
        "Stale source",
        "https://example.com/stale",
        "Mon, 01 Jan 2024 12:00:00 GMT",
    )
    in_file.write_text("\n".join(json.dumps(item) for item in (fresh, stale)) + "\n")
    ledger.write_text("[]")
    registry.write_text('{"schema_version": 1, "topics": []}')
    calls = []

    def completion(**kwargs):
        calls.append(kwargs)
        return _candidate()

    synthesize_brief(
        in_file,
        out_file,
        ledger,
        event_registry=registry,
        completion_func=completion,
        brief_date=date(2026, 9, 14),
    )

    prompt = calls[0]["messages"][0]["content"]
    brief = out_file.read_text()
    assert "Fresh source" in prompt
    assert "Stale source" not in prompt
    assert "https://example.com/fresh" in brief
    assert "https://model.invalid" not in brief


def test_daily_synthesis_uses_source_counts_and_interval_not_model_formatted_metadata(tmp_path):
    in_file = tmp_path / "triaged.jsonl"
    out_file = tmp_path / "brief.md"
    in_file.write_text(json.dumps(_record(
        "fresh", "Fresh source", "https://example.com/fresh",
        "Mon, 28 Sep 2026 20:00:00 GMT",
    )) + "\n")
    candidate = (
        "# ASA Industry News Pulse — 2026-09-29\n\n"
        "**Reporting interval:** Yesterday to today\n"
        "**Candidates classified:** one\n"
        "**Material signals:** one\n"
        "**Classification counts:** material: one\n\n"
        "## Top summary\n\nFresh source changed [REF 1].\n\n"
        "## Material signals\n\n### Fresh source\n\nFresh source changed [REF 1].\n\n"
        "## Candidate disposition\n\nOne item was classified.\n\n"
        "## References\n"
    )
    calls = []

    def completion(**kwargs):
        calls.append(kwargs)
        return candidate

    synthesize_brief(in_file, out_file, None, completion_func=completion, brief_date=date(2026, 9, 29))

    brief = out_file.read_text()
    assert len(calls) == 1
    assert "**Reporting interval:** 2026-09-28T06:30:00-07:00 to 2026-09-29T06:30:00-07:00" in brief
    assert "**Candidates classified:** 1\n**Material signals:** 1" in brief
    assert "**Classification counts:** material=1; monitor=0; noise=0; duplicate=0; needs_validation=0" in brief
    assert "Yesterday to today" not in brief
    assert "https://example.com/fresh" in brief


def test_daily_synthesis_does_not_repair_missing_evidence_body(tmp_path):
    in_file = tmp_path / "triaged.jsonl"
    out_file = tmp_path / "brief.md"
    in_file.write_text(json.dumps(_record(
        "fresh", "Fresh source", "https://example.com/fresh",
        "Mon, 28 Sep 2026 20:00:00 GMT",
    )) + "\n")

    with pytest.raises(BriefContractError, match="missing section: ## Material signals"):
        synthesize_brief(
            in_file, out_file, None, brief_date=date(2026, 9, 29),
            completion_func=lambda **kwargs: "# ASA Industry News Pulse — 2026-09-29\n\n## Top summary\n\nNo signals.\n",
        )
    assert not out_file.exists()
