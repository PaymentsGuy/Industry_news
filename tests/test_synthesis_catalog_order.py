from datetime import date

from intel.pipeline import _synthesis_catalog


def _record(item_id: str, score: int, bucket: str, published_date: str) -> dict:
    return {
        "id": item_id,
        "watchlist_bucket": bucket,
        "relevance_score": score,
        "why_it_matters_for_asa": "Relevant evidence.",
        "_source_item": {
            "title": item_id,
            "source": "Example",
            "source_url": f"https://example.test/{item_id}",
            "published_date": published_date,
        },
    }


def test_synthesis_catalog_orders_higher_relevance_before_recency():
    selected, catalog = _synthesis_catalog(
        [
            _record("lower-but-newer", 2, "channel_partners", "Sun, 14 Sep 2026 12:00:00 GMT"),
            _record("higher-but-older", 3, "direct_adjacent", "Sat, 13 Sep 2026 12:00:00 GMT"),
        ],
        date(2026, 9, 14),
    )

    assert [item["id"] for item in selected] == ["higher-but-older", "lower-but-newer"]
    assert [entry["ref"] for entry in catalog] == [1, 2]
