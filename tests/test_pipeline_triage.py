import json

from intel.pipeline import call_perplexity_triage


REQUIRED_TRIAGE_FIELDS = {
    "id",
    "watchlist_bucket",
    "watchlist_entity",
    "signal_type",
    "roadmap_areas",
    "relevance_score",
    "headline_paraphrase",
    "why_it_matters_for_asa",
    "uncertainty_flags",
    "duplicate_of_id",
}


def sample_item():
    return {
        "id": "item-123",
        "title": "Jack Henry adds transaction enrichment to Banno",
        "source": "Example RSS",
        "source_url": "https://example.com/item-123",
        "published_date": "2026-06-15",
        "text": "Jack Henry announced a Banno transaction enrichment integration.",
    }


def test_perplexity_triage_preserves_required_schema_and_omits_anthropic_cache_blocks():
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return json.dumps(
            {
                "id": "item-123",
                "watchlist_bucket": "channel_partners",
                "watchlist_entity": "Jack Henry",
                "signal_type": "partnership",
                "roadmap_areas": ["one_view", "forecast"],
                "relevance_score": 2,
                "headline_paraphrase": "Jack Henry added enrichment capabilities to Banno.",
                "why_it_matters_for_asa": "Banno distribution can affect ASA One View positioning.",
                "uncertainty_flags": [],
                "duplicate_of_id": None,
            }
        )

    triaged = call_perplexity_triage(sample_item(), "0.2", completion_func=fake_completion)

    assert REQUIRED_TRIAGE_FIELDS <= triaged.keys()
    assert triaged["id"] == "item-123"
    assert triaged["relevance_score"] == 2
    assert triaged["_source_item"]["id"] == "item-123"
    assert "_cache_stats" not in triaged
    assert len(calls) == 1
    assert calls[0]["model"] == "sonar"
    assert "response_format" not in calls[0]
    assert calls[0]["messages"][0]["role"] == "user"
    assert isinstance(calls[0]["messages"][0]["content"], str)
    assert "cache_control" not in json.dumps(calls[0]["messages"])


def test_perplexity_triage_failure_degrades_to_zero_score_record():
    def failing_completion(**kwargs):
        raise RuntimeError("provider unavailable")

    triaged = call_perplexity_triage(sample_item(), "0.2", completion_func=failing_completion)

    assert REQUIRED_TRIAGE_FIELDS <= triaged.keys()
    assert triaged["id"] == "item-123"
    assert triaged["relevance_score"] == 0
    assert triaged["uncertainty_flags"] == ["triage_error"]
    assert triaged["_source_item"]["id"] == "item-123"
