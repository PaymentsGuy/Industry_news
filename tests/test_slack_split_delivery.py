import json

import pytest

from intel import delivery
from tests.test_delivery import FakeSlack, make_package


def test_ambiguous_slack_reconciles_split_native_message_without_reposting(tmp_path):
    brief = tmp_path / "brief.md"
    brief.write_text("Signal from Login.gov and https://example.com/a?x=1&y=2\nSecond line.\n")
    package_path = tmp_path / "delivery.json"
    delivery.create_package(brief, package_path, brief_date="2026-09-29", cadence="weekly", workspace_id="T_TEST")
    package = json.loads(package_path.read_text())
    package["destinations"]["slack"]["status"] = "ambiguous_outcome"
    package_path.write_text(json.dumps(package))
    client_id = package["destinations"]["slack"]["client_msg_id"]
    slack = FakeSlack(history=[
        {"ts": "222.002", "client_msg_id": client_id, "text": "Second line.", "permalink": "https://slack.test/p222002"},
        {"ts": "222.001", "client_msg_id": client_id,
         "text": "Signal from <http://Login.gov|Login.gov> and <https://example.com/a?x=1&y=2>",
         "permalink": "https://slack.test/p222001"},
    ])

    result = delivery.resume_slack(package_path, slack, channel="C0B1TPFSZKJ")

    assert slack.post_calls == []
    assert result["destinations"]["slack"]["status"] == "verified"
    assert result["destinations"]["slack"]["message_ts"] == "222.001"
    assert result["destinations"]["slack"]["message_timestamps"] == ["222.001", "222.002"]
    assert result["destinations"]["slack"]["readback_sha256"] == package["content_sha256"]


def test_split_slack_readback_does_not_verify_missing_or_duplicate_content(tmp_path):
    _, package_path = make_package(tmp_path)
    package = json.loads(package_path.read_text())
    package["destinations"]["slack"]["status"] = "ambiguous_outcome"
    package_path.write_text(json.dumps(package))
    client_id = package["destinations"]["slack"]["client_msg_id"]
    slack = FakeSlack(history=[
        {"ts": "222.001", "client_msg_id": client_id, "text": package["canonical_body"], "permalink": "https://slack.test/p222001"},
        {"ts": "222.002", "client_msg_id": client_id, "text": "duplicated", "permalink": "https://slack.test/p222002"},
    ])

    with pytest.raises(delivery.AmbiguousDelivery):
        delivery.resume_slack(package_path, slack, channel="C0B1TPFSZKJ")
    assert slack.post_calls == []
    assert json.loads(package_path.read_text())["destinations"]["slack"]["status"] == "ambiguous_outcome"


def test_native_message_readback_uses_history_not_thread_replies(monkeypatch):
    client = delivery.SlackWebApiClient("test-token")
    calls = []

    def call(method, payload):
        calls.append(method)
        if method == "conversations.history":
            return {"messages": [{"ts": "222.001", "text": "body"}], "response_metadata": {"next_cursor": ""}}
        if method == "chat.getPermalink":
            return {"permalink": "https://slack.test/p222001"}
        raise AssertionError(method)

    monkeypatch.setattr(client, "_call", call)
    message = client.get_message(channel="C0B1TPFSZKJ", ts="222.001")
    assert message["permalink"] == "https://slack.test/p222001"
    assert calls == ["conversations.history", "chat.getPermalink"]
