import json

from intel.update_ledger import EXTRACTION_MODEL, extract_topics_from_brief, merge_and_prune


def test_extract_topics_from_brief_uses_perplexity_completion_and_returns_topic_dicts():
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return """```json
[
  {
    "topic_key": "banno_bud_enrichment",
    "summary": "Jack Henry shipped Bud enrichment in Banno.",
    "entities": ["Jack Henry", "Bud Financial"],
    "roadmap_areas": ["one_view", "forecast"]
  }
]
```"""

    topics = extract_topics_from_brief("# Brief\nJack Henry shipped Bud enrichment.", completion_func=fake_completion)

    assert topics == [
        {
            "topic_key": "banno_bud_enrichment",
            "summary": "Jack Henry shipped Bud enrichment in Banno.",
            "entities": ["Jack Henry", "Bud Financial"],
            "roadmap_areas": ["one_view", "forecast"],
        }
    ]
    assert len(calls) == 1
    assert calls[0]["model"] == EXTRACTION_MODEL
    assert calls[0]["messages"] == [{"role": "user", "content": calls[0]["messages"][0]["content"]}]
    assert "Jack Henry shipped Bud enrichment" in calls[0]["messages"][0]["content"]
    assert calls[0]["max_tokens"] == 2000
    assert calls[0]["temperature"] == 0.0


def test_extract_topics_from_brief_returns_empty_list_for_malformed_provider_json(caplog):
    def fake_completion(**kwargs):
        return "not json"

    topics = extract_topics_from_brief("# Brief", completion_func=fake_completion)

    assert topics == []
    assert "topic extraction returned invalid JSON" in caplog.text


def test_merge_and_prune_preserves_existing_behavior():
    prior = [
        {
            "topic_key": "existing_topic",
            "first_covered": "2026-06-01",
            "last_covered": "2026-06-10",
            "summary": "Old summary.",
            "entities": ["OldCo"],
            "roadmap_areas": ["auth"],
        },
        {
            "topic_key": "stale_topic",
            "first_covered": "2026-05-01",
            "last_covered": "2026-05-20",
            "summary": "Too old.",
            "entities": [],
            "roadmap_areas": [],
        },
    ]
    new_topics = [
        {
            "topic_key": "existing_topic",
            "summary": "New summary.",
            "entities": ["NewCo", "OldCo"],
            "roadmap_areas": ["auth", "verify"],
        },
        {
            "topic_key": "new_topic",
            "summary": "Brand new.",
            "entities": ["FreshCo"],
            "roadmap_areas": ["one_view"],
        },
        {"summary": "missing key is ignored"},
    ]

    merged = merge_and_prune(prior, new_topics, "2026-06-15", window_days=14)

    assert json.loads(json.dumps(merged)) == [
        {
            "topic_key": "new_topic",
            "first_covered": "2026-06-15",
            "last_covered": "2026-06-15",
            "summary": "Brand new.",
            "entities": ["FreshCo"],
            "roadmap_areas": ["one_view"],
        },
        {
            "topic_key": "existing_topic",
            "first_covered": "2026-06-01",
            "last_covered": "2026-06-15",
            "summary": "New summary.",
            "entities": ["NewCo", "OldCo"],
            "roadmap_areas": ["auth", "verify"],
        },
    ]
