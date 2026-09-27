from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")


def is_eligible_pacific_run(moment: datetime, *, scheduled_cron: str = "") -> bool:
    if moment.tzinfo is None:
        raise ValueError("schedule guard requires a timezone-aware datetime")
    local = moment.astimezone(PACIFIC)
    if local.weekday() >= 5 or (local.hour, local.minute) < (6, 30):
        return False
    if scheduled_cron:
        scheduled_hour = {"30 13 * * 1-5": 13, "30 14 * * 1-5": 14}.get(scheduled_cron)
        nominal = local.replace(hour=6, minute=30, second=0, microsecond=0)
        return scheduled_hour is not None and nominal.astimezone(ZoneInfo("UTC")).hour == scheduled_hour
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit DST-safe weekday 06:30 PT eligibility")
    parser.add_argument("--at", help="ISO-8601 instant; defaults to now")
    parser.add_argument("--scheduled-cron", default="", help="GitHub schedule expression; empty for manual recovery")
    args = parser.parse_args()
    moment = datetime.fromisoformat(args.at.replace("Z", "+00:00")) if args.at else datetime.now(tz=ZoneInfo("UTC"))
    eligible = is_eligible_pacific_run(moment, scheduled_cron=args.scheduled_cron)
    local = moment.astimezone(PACIFIC)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"eligible={'true' if eligible else 'false'}\n")
            if eligible:
                from intel.pipeline import pacific_report_interval

                start, end = pacific_report_interval(local.date())
                handle.write(f"report_date={local.date().isoformat()}\n")
                handle.write(f"interval_start={start.isoformat()}\n")
                handle.write(f"interval_end={end.isoformat()}\n")
    else:
        print("true" if eligible else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
