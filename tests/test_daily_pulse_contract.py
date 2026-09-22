from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from intel.brief_contract import BriefContractError, validate_daily_pulse
from intel.pipeline import _synthesis_catalog, pacific_report_interval


def _item(number: int, published: str, *, score: int = 3) -> dict:
    return {
        "id": f"item-{number:02d}",
        "classification": "material",
        "relevance_score": score,
        "watchlist_bucket": "competitors",
        "why_it_matters_for_asa": f"Material signal {number}",
        "_source_item": {
            "source": "Fixture",
            "title": f"Signal {number}",
            "source_url": f"https://example.test/{number}",
            "published_date": published,
        },
    }


def test_daily_catalog_retains_every_material_signal_without_fixed_cap() -> None:
    items = [_item(number, "2026-09-20T10:00:00Z") for number in range(1, 8)]

    selected, catalog = _synthesis_catalog(items, date(2026, 9, 21))

    assert [row["id"] for row in selected] == [f"item-{number:02d}" for number in range(1, 8)]
    assert len(catalog) == 7


def test_daily_catalog_uses_exact_pacific_interval_not_rolling_calendar_days() -> None:
    items = [
        _item(1, "2026-09-22T12:00:00Z"),  # 05:00 PT, before Tuesday boundary
        _item(2, "2026-09-22T14:00:00Z"),  # 07:00 PT, inside interval
    ]

    selected, _ = _synthesis_catalog(items, date(2026, 9, 23))

    assert [row["id"] for row in selected] == ["item-02"]


def test_monday_interval_starts_at_prior_friday_boundary() -> None:
    start, end = pacific_report_interval(date(2026, 9, 21))

    assert start == datetime(2026, 9, 18, 6, 30, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert end == datetime(2026, 9, 21, 6, 30, tzinfo=ZoneInfo("America/Los_Angeles"))


def test_non_weekday_report_date_is_rejected() -> None:
    with pytest.raises(ValueError, match="weekday"):
        pacific_report_interval(date(2026, 9, 20))


def test_daily_contract_accepts_explicit_no_material_change() -> None:
    validate_daily_pulse(
        "# ASA Industry News Pulse — 2026-09-22\n\n"
        "**Reporting interval:** 2026-09-21T06:30:00-07:00 to 2026-09-22T06:30:00-07:00\n"
        "**Candidates classified:** 2\n"
        "**Material signals:** 0\n"
        "**Classification counts:** material=0; monitor=1; noise=1; duplicate=0; needs_validation=0\n\n"
        "## Top summary\n\nNo material change.\n\n"
        "## Material signals\n\nNo evidence-backed material signals in this interval.\n\n"
        "## Candidate disposition\n\nAll candidates were classified.\n\n"
        "## References\n"
    )


def test_daily_contract_rejects_count_mismatch() -> None:
    with pytest.raises(BriefContractError, match="classification counts"):
        validate_daily_pulse(
            "# ASA Industry News Pulse — 2026-09-22\n\n"
            "**Reporting interval:** 2026-09-21T06:30:00-07:00 to 2026-09-22T06:30:00-07:00\n"
            "**Candidates classified:** 2\n"
            "**Material signals:** 1\n"
            "**Classification counts:** material=0; monitor=1; noise=1; duplicate=0; needs_validation=0\n\n"
            "## Top summary\n\nOne signal.\n\n"
            "## Material signals\n\nSignal.\n\n"
            "## Candidate disposition\n\nAll candidates were classified.\n\n"
            "## References\n"
        )


def test_daily_contract_rejects_wrong_interval_and_missing_material_entries() -> None:
    brief = (
        "# ASA Industry News Pulse — 2026-09-22\n\n"
        "**Reporting interval:** 2026-09-20T06:30:00-07:00 to 2026-09-22T06:30:00-07:00\n"
        "**Candidates classified:** 1\n"
        "**Material signals:** 1\n"
        "**Classification counts:** material=1; monitor=0; noise=0; duplicate=0; needs_validation=0\n\n"
        "## Top summary\n\nOne signal.\n\n"
        "## Material signals\n\nNo structured entries.\n\n"
        "## Candidate disposition\n\nAll candidates were classified.\n\n"
        "## References\n"
    )
    expected = pacific_report_interval(date(2026, 9, 22))

    with pytest.raises(BriefContractError, match="reporting interval|material entry count"):
        validate_daily_pulse(brief, expected_interval=expected, expected_material_count=1)
