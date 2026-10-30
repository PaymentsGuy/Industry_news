"""Reserve one paid generation per date before the workflow calls a provider.

The workflow commits and pushes this reservation before collection/triage. A
failed attempt is recovered from retained artifacts, never by silently starting
another paid generation. Existing packages, including partial deliveries, retain
their original immutable identity.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import re


def reserve_generation(repo: Path, brief_date: str, workflow_run_id: str, *, request_id: str = "") -> dict:
    if date.fromisoformat(brief_date).isoformat() != brief_date:
        raise ValueError("brief date must be canonical YYYY-MM-DD")
    if not re.fullmatch(r"[0-9]{1,30}", workflow_run_id):
        raise ValueError("workflow run identity is invalid")
    if request_id and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", request_id):
        raise ValueError("request identity is invalid")
    folder = Path(repo) / "intel" / brief_date
    if (folder / "delivery.json").exists():
        return {"generate": False, "reason": "existing_package"}
    marker = folder / "generation-attempt.json"
    if marker.exists():
        return {"generate": False, "reason": "generation_already_reserved"}
    if any((folder / name).exists() for name in ("raw.jsonl", "triaged.jsonl", "brief.md")):
        return {"generate": False, "reason": "existing_generation_artifacts"}
    folder.mkdir(parents=True, exist_ok=True)
    payload = {"brief_date": brief_date, "workflow_run_id": workflow_run_id, "request_id": request_id}
    try:
        with marker.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        return {"generate": False, "reason": "generation_already_reserved"}
    return {"generate": True, "reason": "reserved"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief-date", required=True)
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--request-id", default="")
    args = parser.parse_args()
    result = reserve_generation(Path.cwd(), args.brief_date, args.workflow_run_id, request_id=args.request_id)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"generate={str(result['generate']).lower()}\n")
            handle.write(f"reason={result['reason']}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
