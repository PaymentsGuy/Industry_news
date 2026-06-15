import json

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


def test_synthesize_brief_uses_perplexity_and_writes_stripped_markdown(tmp_path):
    in_file = tmp_path / "triaged.jsonl"
    out_file = tmp_path / "brief.md"
    prior_ledger = tmp_path / "ledger.json"
    prior_ledger.write_text(json.dumps([{"topic": "already covered"}]), encoding="utf-8")
    in_file.write_text(json.dumps(sample_triage_record()) + "\n", encoding="utf-8")
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return "```markdown\n# Weekly ASA Intel Brief\n\n## References\n- https://example.com/item-123\n```"

    synthesize_brief(in_file, out_file, prior_ledger, completion_func=fake_completion)

    assert out_file.read_text(encoding="utf-8") == (
        "# Weekly ASA Intel Brief\n\n## References\n- https://example.com/item-123"
    )
    assert len(calls) == 1
    assert calls[0]["model"] == SYNTHESIS_MODEL
    assert calls[0]["messages"] == [{"role": "user", "content": calls[0]["messages"][0]["content"]}]
    assert "already covered" in calls[0]["messages"][0]["content"]
    assert "weekly competitive intelligence" in calls[0]["messages"][0]["content"]
    assert "Jack Henry added transaction enrichment" in calls[0]["messages"][0]["content"]
    assert "```" not in out_file.read_text(encoding="utf-8")
