from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from intel.schedule import is_eligible_pacific_run

ROOT = Path(__file__).parents[1]


def test_delayed_scheduled_run_remains_eligible_on_pacific_weekday():
    assert is_eligible_pacific_run(datetime(2026, 7, 6, 13, 47, tzinfo=ZoneInfo("UTC")))
    assert is_eligible_pacific_run(datetime(2026, 12, 7, 15, 5, tzinfo=ZoneInfo("UTC")))
    assert not is_eligible_pacific_run(datetime(2026, 7, 6, 13, 29, tzinfo=ZoneInfo("UTC")))
    assert not is_eligible_pacific_run(datetime(2026, 7, 5, 15, 5, tzinfo=ZoneInfo("UTC")))


def test_managed_vault_bridge_tracks_main_and_publishes_receipts():
    script = (ROOT / "scripts/run_local_vault_bridge").read_text()
    assert 'feat/asa-intelligence-routing' not in script
    assert 'git -C "$REPO" switch main' in script
    assert 'git -C "$REPO" pull --ff-only origin main' in script
    assert 'for receipt in intel/*/delivery.json intel/*/vault-receipt.json' in script
    assert 'git push origin main' in script


def test_delayed_candidate_uses_correct_dst_cron_without_second_publication():
    summer = datetime(2026, 7, 6, 14, 47, tzinfo=ZoneInfo("UTC"))
    winter = datetime(2026, 12, 7, 15, 5, tzinfo=ZoneInfo("UTC"))
    assert is_eligible_pacific_run(summer, scheduled_cron="30 13 * * 1-5")
    assert not is_eligible_pacific_run(summer, scheduled_cron="30 14 * * 1-5")
    assert is_eligible_pacific_run(winter, scheduled_cron="30 14 * * 1-5")
    assert not is_eligible_pacific_run(winter, scheduled_cron="30 13 * * 1-5")
    workflow = (ROOT / ".github/workflows/daily-intel.yml").read_text()
    assert 'github.event.schedule' in workflow
