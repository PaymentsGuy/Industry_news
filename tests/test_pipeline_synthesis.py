import json

import pytest

from intel.brief_contract import BriefContractError
from intel.pipeline import SYNTHESIS_MODEL, synthesize_brief


def sample_triage_record(relevance_score=2):
    return {
        "id": "item-123",
        "watchlist_bucket": "channel_partners",
        "watchlist_entity": "Jack Henry",
        "signal_type": "partnership",
        "roadmap_areas": ["one_view"],
        "relevance_score": relevance_score,
        "headline_paraphrase": "Jack Henry added transaction enrichment to Banno.",
        "why_it_matters_for_asa": "Banno distribution can affect ASA positioning.",
        "uncertainty_flags": [],
        "duplicate_of_id": None,
        "_source_item": {
            "id": "item-123",
            "title": "Jack Henry adds transaction enrichment to Banno",
            "source_url": "https://example.com/item-123",
        },
    }


def valid_weekly_brief():
    return (
        "# ASA Weekly Intelligence Brief — Week of 2026-06-15\n\n"
        "**Items reviewed:** 1\n"
        "**Items surfaced:** 1\n"
        "**Items deduped against ledger:** 0\n"
        "**This week's headline:** Jack Henry changed Banno.\n\n"
        "## TL;DR\n\n1. Jack Henry changed Banno [REF 1].\n\n"
        "## By roadmap area\n\n**Vault.** Jack Henry changed Banno [REF 1].\n\n"
        "## Watchlist movement\n\n"
        "| Entity | Signal type | One-line detail | Status | Ref |\n"
        "|---|---|---|---|---|\n"
        "| Jack Henry | Partnership | Added transaction enrichment | New | [REF 1] |\n\n"
        "## Open questions for the team\n\n1. What next?\n\n"
        "## References\n\n"
        '1. Source, "Jack Henry adds transaction enrichment," 2026-06-15. https://example.com/item-123 — *Evidence.*\n'
    )


def prepare_files(tmp_path):
    in_file = tmp_path / "triaged.jsonl"
    out_file = tmp_path / "brief.md"
    prior_ledger = tmp_path / "ledger.json"
    event_registry = tmp_path / "event_registry.json"
    prior_ledger.write_text(json.dumps([{"topic": "already covered"}]), encoding="utf-8")
    event_registry.write_text(json.dumps({
        "schema_version": 1,
        "topics": [{
            "topic_key": "fiserv_cognition_devin",
            "first_covered": "2026-06-01",
            "last_covered": "2026-06-01",
            "summary": "Fiserv partnered with Cognition to use Devin AI.",
            "entities": ["Fiserv", "Cognition"],
            "events": [{
                "covered_on": "2026-06-01",
                "summary": "Fiserv partnered with Cognition to use Devin AI.",
                "source_urls": ["https://example.com/fiserv-june"],
                "source_dates": ["2026-06-01"],
            }],
        }],
    }), encoding="utf-8")
    in_file.write_text(json.dumps(sample_triage_record()) + "\n", encoding="utf-8")
    return in_file, out_file, prior_ledger, event_registry


def test_synthesize_brief_uses_perplexity_and_writes_validated_markdown(tmp_path):
    in_file, out_file, prior_ledger, event_registry = prepare_files(tmp_path)
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return f"```markdown\n{valid_weekly_brief()}```"

    synthesize_brief(
        in_file, out_file, prior_ledger,
        event_registry=event_registry, completion_func=fake_completion,
    )

    assert out_file.read_text(encoding="utf-8") == valid_weekly_brief().rstrip()
    assert len(calls) == 1
    assert calls[0]["model"] == SYNTHESIS_MODEL
    assert calls[0]["messages"] == [{"role": "user", "content": calls[0]["messages"][0]["content"]}]
    assert "already covered" in calls[0]["messages"][0]["content"]
    assert "fiserv_cognition_devin" in calls[0]["messages"][0]["content"]
    assert "durable_event_registry" in calls[0]["messages"][0]["content"]
    assert "same underlying event" in calls[0]["messages"][0]["content"]
    assert "weekly competitive intelligence" in calls[0]["messages"][0]["content"]
    assert "Jack Henry added transaction enrichment" in calls[0]["messages"][0]["content"]
    assert "```" not in out_file.read_text(encoding="utf-8")


def test_synthesize_retries_contract_failure_before_writing(tmp_path):
    in_file, out_file, prior_ledger, event_registry = prepare_files(tmp_path)
    invalid = valid_weekly_brief().replace(" https://example.com/item-123", "")
    responses = [invalid, valid_weekly_brief()]
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return responses.pop(0)

    synthesize_brief(
        in_file, out_file, prior_ledger,
        event_registry=event_registry, completion_func=fake_completion,
    )

    assert len(calls) == 2
    assert "reference 1 is missing a URL" in calls[1]["messages"][0]["content"]
    assert out_file.read_text(encoding="utf-8") == valid_weekly_brief().rstrip()


def test_synthesize_fails_closed_before_provider_when_durable_registry_is_invalid(tmp_path):
    in_file, out_file, prior_ledger, event_registry = prepare_files(tmp_path)
    event_registry.write_text("not-json", encoding="utf-8")
    calls = []

    with pytest.raises(BriefContractError, match="durable event registry"):
        synthesize_brief(
            in_file, out_file, prior_ledger,
            event_registry=event_registry,
            completion_func=lambda **kwargs: calls.append(kwargs),
        )

    assert calls == []
    assert not out_file.exists()
