from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from intel.schedule import is_eligible_pacific_run


def test_runner_guard_selects_weekday_0630_pacific_across_dst() -> None:
    assert is_eligible_pacific_run(datetime(2026, 7, 6, 13, 30, tzinfo=ZoneInfo("UTC")))
    assert is_eligible_pacific_run(datetime(2026, 12, 7, 14, 30, tzinfo=ZoneInfo("UTC")))


def test_runner_guard_rejects_weekend_and_wrong_local_time() -> None:
    assert not is_eligible_pacific_run(datetime(2026, 7, 5, 13, 30, tzinfo=ZoneInfo("UTC")))
    assert not is_eligible_pacific_run(datetime(2026, 7, 6, 14, 30, tzinfo=ZoneInfo("UTC")))


def test_workflow_uses_dst_safe_guard_and_weekday_daily_identity() -> None:
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "daily-intel.yml").read_text()
    assert "30 13 * * 1-5" in workflow
    assert "30 14 * * 1-5" in workflow
    assert "python intel/schedule.py" in workflow
    assert "cadence weekday_daily" in workflow
