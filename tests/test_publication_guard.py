from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def reserve(root, day="2026-10-30", run_id="123", request_id=""):
    assert importlib.util.find_spec("intel.publication_guard"), "pre-generation publication guard is missing"
    from intel.publication_guard import reserve_generation
    return reserve_generation(root, day, run_id, request_id=request_id)


def test_first_attempt_is_reserved_before_generation(tmp_path):
    result = reserve(tmp_path, request_id="request-abc")
    assert result["generate"] is True
    marker = json.loads((tmp_path / "intel/2026-10-30/generation-attempt.json").read_text())
    assert marker["workflow_run_id"] == "123"
    assert marker["brief_date"] == "2026-10-30"
    assert marker["request_id"] == "request-abc"


def test_second_workflow_and_same_run_rerun_cannot_regenerate(tmp_path):
    reserve(tmp_path)
    original = (tmp_path / "intel/2026-10-30/generation-attempt.json").read_bytes()
    assert reserve(tmp_path)["generate"] is False
    assert reserve(tmp_path, run_id="456")["generate"] is False
    assert (tmp_path / "intel/2026-10-30/generation-attempt.json").read_bytes() == original


def test_existing_delivery_package_never_regenerates(tmp_path):
    folder = tmp_path / "intel/2026-10-30"
    folder.mkdir(parents=True)
    (folder / "delivery.json").write_text(json.dumps({"brief_id": "industry-pulse-2026-10-30", "brief_date": "2026-10-30", "cadence": "weekday_daily"}))
    assert reserve(tmp_path)["reason"] == "existing_package"
    assert not (folder / "generation-attempt.json").exists()


def test_partial_legacy_generation_requires_review_not_fresh_paid_run(tmp_path):
    folder = tmp_path / "intel/2026-10-30"
    folder.mkdir(parents=True)
    (folder / "triaged.jsonl").write_text("{}\n")
    assert reserve(tmp_path)["generate"] is False
    assert reserve(tmp_path)["reason"] == "existing_generation_artifacts"


@pytest.mark.parametrize("day,run_id,request_id", [("2026-10-3", "123", ""), ("../x", "123", ""), ("2026-10-30", "bad/id", ""), ("2026-10-30", "123", "bad\nrequest")])
def test_rejects_unsafe_or_noncanonical_identifiers(tmp_path, day, run_id, request_id):
    with pytest.raises(ValueError):
        reserve(tmp_path, day, run_id, request_id)
    assert not list(tmp_path.iterdir())


def test_concurrent_reservations_only_one_can_generate(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda n: reserve(tmp_path, run_id=str(100 + n)), range(8)))
    assert sum(row["generate"] for row in results) == 1


def test_workflow_is_dispatch_only_and_commits_guard_before_collection():
    workflow = (Path(__file__).parents[1] / ".github/workflows/daily-intel.yml").read_text()
    assert "  schedule:" not in workflow, "GitHub must not own the timer"
    assert "request_id:" in workflow
    assert "python -m intel.publication_guard" in workflow
    assert workflow.index("generation-attempt.json") < workflow.index("python -m intel.pipeline collect")
    assert "steps.generation.outputs.generate == 'true'" in workflow
