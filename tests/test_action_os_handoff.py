from __future__ import annotations

import hashlib
import json
from pathlib import Path


import pytest

from intel.action_os_handoff import publish_review_packets


def _package(tmp_path: Path, *, actionable: bool = True) -> Path:
    body = "# Daily pulse\n"
    path = tmp_path / "2026-09-21" / "delivery.json"
    path.parent.mkdir()
    signals = [{
        "signal_id": "signal-1", "classification": "material", "title": "Channel shift",
        "evidence_links": ["https://example.test/source"],
        **({"proposed_decision": "Review channel shift", "proposed_next_action": "Decide owner response", "proposed_owner": "Troy"} if actionable else {}),
    }]
    path.write_text(json.dumps({
        "brief_id": "industry-pulse-2026-09-21", "brief_date": "2026-09-21", "cadence": "weekday_daily", "canonical_body": body,
        "content_sha256": hashlib.sha256(body.encode()).hexdigest(), "status": "fully_delivered",
        "destinations": {"repository": {"status": "verified"}, "slack": {"status": "verified"}, "vault": {"status": "verified"}},
        "signals": signals,
    }))
    return path


def test_actionable_signal_is_signed_and_exact_readback_is_persisted(tmp_path: Path) -> None:
    package = _package(tmp_path)
    requests = []

    def request(method, path, payload, capability):
        requests.append((method, path, payload, capability))
        if method == "POST":
            return {"candidate": {"candidate_id": "ir-industry-news-test", "industry_news_intake": payload}}
        return {"candidate": {"candidate_id": "ir-industry-news-test", "industry_news_intake": requests[0][2]}}

    result = publish_review_packets(package, base_url="http://127.0.0.1:8890", capability="local-test", request_json=request)
    receipt = json.loads(package.with_name("action-os-receipt.json").read_text())
    assert result["status"] == "verified"
    assert receipt["pulse_sha256"] == json.loads(package.read_text())["content_sha256"]
    assert receipt["candidate_ids"] == ["ir-industry-news-test"]
    assert [row[0] for row in requests] == ["POST", "GET"]
    assert requests[0][2]["proposed_owner"] == "Troy"


def test_actionless_signal_does_not_create_action_os_work(tmp_path: Path) -> None:
    package = _package(tmp_path, actionable=False)
    def no_call(*args):
        pytest.fail("actionless material signal must not call Action OS")
    result = publish_review_packets(package, base_url="http://127.0.0.1:8890", capability="local-test", request_json=no_call)
    assert result["status"] == "no_actionable_signals"
    assert result["candidate_ids"] == []


def test_failed_readback_never_writes_success_receipt(tmp_path: Path) -> None:
    package = _package(tmp_path)
    def mismatch(method, path, payload, capability):
        return {"candidate": {"candidate_id": "ir-industry-news-test", "industry_news_intake": {}}}
    with pytest.raises(ValueError, match="readback"):
        publish_review_packets(package, base_url="http://127.0.0.1:8890", capability="local-test", request_json=mismatch)
    assert not package.with_name("action-os-receipt.json").exists()


def test_partial_delivery_cannot_publish(tmp_path: Path) -> None:
    package = _package(tmp_path)
    payload = json.loads(package.read_text())
    payload["status"] = "partial_delivery"
    package.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="fully delivered"):
        publish_review_packets(package, base_url="http://127.0.0.1:8890", capability="local-test")
