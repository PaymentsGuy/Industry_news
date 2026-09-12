from __future__ import annotations

import json
import uuid
import subprocess
from pathlib import Path

import pytest

from intel import delivery


class FakeSlack:
    def __init__(self, *, posted=None, history=None, readback=None, post_error=None):
        self.posted = posted or {"ok": True, "ts": "123.456"}
        self.history = list(history or [])
        self.readback = readback
        self.post_error = post_error
        self.post_calls = []

    def workspace_id(self):
        return "T_TEST"

    def post_message(self, *, channel, text, client_msg_id):
        self.post_calls.append((channel, text, client_msg_id))
        if self.post_error:
            raise self.post_error
        return self.posted

    def find_by_client_msg_id(self, *, channel, client_msg_id):
        return [row for row in self.history if row.get("client_msg_id") == client_msg_id]

    def get_message(self, *, channel, ts):
        if self.readback is not None and self.readback.get("ts") == ts:
            return self.readback
        return next((row for row in self.history if row.get("ts") == ts), None)


def make_package(tmp_path: Path):
    brief = tmp_path / "brief.md"
    brief.write_text("# ASA Weekly Intelligence Brief\r\n\r\nSignal one.\r\n", encoding="utf-8")
    package = tmp_path / "delivery.json"
    delivery.create_package(brief, package, brief_date="2026-08-24", cadence="weekly", workspace_id="T_TEST")
    return brief, package


def test_create_package_uses_canonical_body_and_stable_identity(tmp_path):
    _, package_path = make_package(tmp_path)
    payload = json.loads(package_path.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert payload["brief_id"] == "asa-intelligence-brief-2026-08-24"
    assert payload["content_sha256"] == delivery.sha256_text("# ASA Weekly Intelligence Brief\n\nSignal one.\n")
    assert payload["transaction_id"].startswith("brief-delivery-")
    assert payload["workflow_run_id"] is None
    assert str(uuid.UUID(payload["destinations"]["slack"]["client_msg_id"])) == payload["destinations"]["slack"]["client_msg_id"]
    assert payload["destinations"]["slack"]["status"] == "pending"
    assert payload["destinations"]["vault"]["status"] == "pending"
    assert payload["status"] == "pending"


def test_slack_delivery_persists_attempt_and_verifies_native_readback(tmp_path):
    _, package_path = make_package(tmp_path)
    package = json.loads(package_path.read_text())
    client_id = package["destinations"]["slack"]["client_msg_id"]
    slack = FakeSlack(readback={
        "ts": "123.456",
        "client_msg_id": client_id,
        "text": package["canonical_body"],
        "permalink": "https://slack.test/archives/C0B1TPFSZKJ/p123456",
    })

    result = delivery.resume_slack(package_path, slack, channel="C0B1TPFSZKJ")

    assert len(slack.post_calls) == 1
    assert result["destinations"]["slack"]["status"] == "verified"
    assert result["destinations"]["slack"]["message_ts"] == "123.456"
    assert result["destinations"]["slack"]["readback_sha256"] == result["content_sha256"]
    assert result["status"] == "partial_delivery"


def test_lost_slack_response_is_ambiguous_and_never_blindly_reposts(tmp_path):
    _, package_path = make_package(tmp_path)
    slack = FakeSlack(post_error=TimeoutError("response lost"))

    with pytest.raises(delivery.AmbiguousDelivery):
        delivery.resume_slack(package_path, slack, channel="C0B1TPFSZKJ")

    assert len(slack.post_calls) == 1
    saved = json.loads(package_path.read_text())
    assert saved["destinations"]["slack"]["status"] == "ambiguous_outcome"

    with pytest.raises(delivery.AmbiguousDelivery):
        delivery.resume_slack(package_path, slack, channel="C0B1TPFSZKJ")
    assert len(slack.post_calls) == 1


def test_lost_native_readback_is_ambiguous_and_never_reposts(tmp_path):
    _, package_path = make_package(tmp_path)

    class ReadbackTimeout(FakeSlack):
        def get_message(self, *, channel, ts):
            raise TimeoutError("readback response lost")

    slack = ReadbackTimeout()
    with pytest.raises(delivery.AmbiguousDelivery):
        delivery.resume_slack(package_path, slack, channel="C0B1TPFSZKJ")
    assert len(slack.post_calls) == 1
    assert json.loads(package_path.read_text())["destinations"]["slack"]["status"] == "ambiguous_outcome"

    with pytest.raises(delivery.AmbiguousDelivery):
        delivery.resume_slack(package_path, slack, channel="C0B1TPFSZKJ")
    assert len(slack.post_calls) == 1


def test_ambiguous_slack_attempt_reconciles_unique_native_message_without_post(tmp_path):
    _, package_path = make_package(tmp_path)
    package = json.loads(package_path.read_text())
    package["destinations"]["slack"]["status"] = "ambiguous_outcome"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    client_id = package["destinations"]["slack"]["client_msg_id"]
    slack = FakeSlack(history=[{
        "ts": "222.333",
        "client_msg_id": client_id,
        "text": package["canonical_body"],
        "permalink": "https://slack.test/p222333",
    }])

    result = delivery.resume_slack(package_path, slack, channel="C0B1TPFSZKJ")

    assert slack.post_calls == []
    assert result["destinations"]["slack"]["status"] == "verified"


def test_import_vault_receipt_binds_same_transaction_and_hash(tmp_path):
    _, package_path = make_package(tmp_path)
    package = json.loads(package_path.read_text())
    receipt = tmp_path / "vault-receipt.json"
    key = b"test-vault-receipt-key"
    receipt_payload = {
        "destination": "vault",
        "transaction_id": package["transaction_id"],
        "brief_id": package["brief_id"],
        "content_sha256": package["content_sha256"],
        "vault_path": "Atlas/competitive-intel/intelligence-briefs/2026-08-24 - ASA Intelligence Brief.md",
        "vault_file_sha256": "a" * 64,
        "readback": True,
    }
    receipt_payload["signature"] = delivery.sign_receipt(receipt_payload, key)
    receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")

    result = delivery.import_receipt(package_path, receipt, verification_key=key)

    assert result["destinations"]["vault"]["status"] == "verified"
    assert result["status"] == "partial_delivery"

    bad = json.loads(receipt.read_text())
    bad["content_sha256"] = "b" * 64
    receipt.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="signature|content hash"):
        delivery.import_receipt(package_path, receipt, verification_key=key)


def test_forged_vault_receipt_is_rejected(tmp_path):
    _, package_path = make_package(tmp_path)
    package = json.loads(package_path.read_text())
    receipt = tmp_path / "forged.json"
    receipt.write_text(json.dumps({
        "destination": "vault",
        "transaction_id": package["transaction_id"],
        "brief_id": package["brief_id"],
        "content_sha256": package["content_sha256"],
        "vault_path": "Atlas/competitive-intel/intelligence-briefs/x.md",
        "vault_file_sha256": "a" * 64,
        "readback": True,
        "signature": "forged",
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="signature"):
        delivery.import_receipt(package_path, receipt, verification_key=b"real-key")


def test_recreating_same_package_is_idempotent_and_never_erases_receipts(tmp_path):
    brief, package_path = make_package(tmp_path)
    saved = json.loads(package_path.read_text())
    saved["destinations"]["slack"]["status"] = "verified"
    package_path.write_text(json.dumps(saved), encoding="utf-8")
    replay = delivery.create_package(brief, package_path, brief_date="2026-08-24", cadence="weekly", workspace_id="T_TEST")
    assert replay["destinations"]["slack"]["status"] == "verified"

    brief.write_text("different content\n", encoding="utf-8")
    with pytest.raises(ValueError, match="existing delivery package"):
        delivery.create_package(brief, package_path, brief_date="2026-08-24", cadence="weekly", workspace_id="T_TEST")


def test_recreating_package_rejects_cadence_identity_drift(tmp_path):
    brief, package_path = make_package(tmp_path)
    with pytest.raises(ValueError, match="existing delivery package"):
        delivery.create_package(brief, package_path, brief_date="2026-08-24", cadence="daily_predecessor", workspace_id="T_TEST")


def test_repository_receipt_requires_commit_native_readback(tmp_path):
    repo=tmp_path/"repo"; repo.mkdir(); subprocess.run(["git","init","-q",str(repo)],check=True)
    brief_dir=repo/"intel/2026-08-24"; brief_dir.mkdir(parents=True)
    brief=brief_dir/"brief.md"; brief.write_text("# ASA Weekly Intelligence Brief\n\nSignal one.\n")
    package=brief_dir/"delivery.json"; delivery.create_package(brief,package,brief_date="2026-08-24",cadence="weekly",workspace_id="T_TEST")
    subprocess.run(["git","-C",str(repo),"add","."],check=True)
    subprocess.run(["git","-C",str(repo),"-c","user.name=test","-c","user.email=test@example.test","commit","-qm","package"],check=True)
    sha=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"],text=True).strip()
    assert delivery.mark_repository(package,sha,repo_root=repo)["destinations"]["repository"]["status"]=="verified"
    with pytest.raises(ValueError,match="commit"):
        delivery.mark_repository(package,"0"*40,repo_root=repo)


def test_repository_receipt_is_a_commit_pinned_mios_handoff(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    brief_dir = repo / "intel/2026-08-24"
    brief_dir.mkdir(parents=True)
    brief = brief_dir / "brief.md"
    brief.write_text("# ASA Weekly Intelligence Brief\n\nSignal one.\n", encoding="utf-8")
    package = brief_dir / "delivery.json"
    delivery.create_package(
        brief,
        package,
        brief_date="2026-08-24",
        cadence="weekly",
        workspace_id="T_TEST",
        workflow_run_id="123456",
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.test", "commit", "-qm", "package"],
        check=True,
    )
    source_commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()

    result = delivery.mark_repository(package, source_commit, repo_root=repo)

    receipt = result["producer_receipt"]
    assert receipt["repository_commit"] == source_commit
    assert receipt["brief_path"] == "intel/2026-08-24/brief.md"
    assert receipt["package_path"] == "intel/2026-08-24/delivery.json"
    assert receipt["workflow_run_id"] == "123456"
    assert receipt["receipt_id"].startswith("producer-receipt-")
    assert receipt["content_sha256"] == result["content_sha256"]
    assert result["destinations"]["repository"] == {"status": "verified", "commit_sha": source_commit}


def test_slack_workspace_and_native_identity_must_match(tmp_path):
    _, package_path = make_package(tmp_path)
    package = json.loads(package_path.read_text())

    class WrongWorkspace(FakeSlack):
        def workspace_id(self): return "T_WRONG"

    with pytest.raises(ValueError, match="workspace"):
        delivery.resume_slack(package_path, WrongWorkspace(), channel="C0B1TPFSZKJ")

    client_id = package["destinations"]["slack"]["client_msg_id"]
    class BadReadback(FakeSlack):
        def get_message(self, *, channel, ts):
            return {"ts": "999", "client_msg_id": client_id, "text": package["canonical_body"], "permalink": "https://slack.test/p999"}
    with pytest.raises(delivery.AmbiguousDelivery, match="identity"):
        delivery.resume_slack(package_path, BadReadback(), channel="C0B1TPFSZKJ")


def test_slack_web_api_history_paginates_to_closure(monkeypatch):
    client = delivery.SlackWebApiClient("token")
    calls = []
    pages = [
        {"ok": True, "messages": [{"ts": "2"}], "response_metadata": {"next_cursor": "next"}},
        {"ok": True, "messages": [{"ts": "1"}], "response_metadata": {"next_cursor": ""}},
    ]

    def fake_call(method, payload):
        calls.append((method, dict(payload)))
        return pages.pop(0)

    monkeypatch.setattr(client, "_call", fake_call)
    assert [row["ts"] for row in client._history("C0B1TPFSZKJ")] == ["2", "1"]
    assert calls[1][1]["cursor"] == "next"


def test_slack_json_error_fails_closed_before_post(monkeypatch, tmp_path):
    _, package_path = make_package(tmp_path)
    client = delivery.SlackWebApiClient("token")
    calls = []
    def fake_post(url, **kwargs):
        calls.append(url.rsplit('/', 1)[-1])
        class Response:
            def raise_for_status(self): pass
            def json(self): return {"ok": False, "error": "missing_scope"}
        return Response()
    monkeypatch.setattr(delivery.requests, "post", fake_post)
    with pytest.raises(delivery.SlackApiError, match="missing_scope"):
        delivery.resume_slack(package_path, client, channel="C0B1TPFSZKJ")
    assert calls == ["auth.test"]


def test_pipeline_publish_delegates_to_delivery_owner_and_has_no_webhook_posting():
    source = (Path(__file__).parents[1] / "intel" / "pipeline.py").read_text(encoding="utf-8")
    assert "delivery.publish_brief" in source
    assert "SLACK_WEBHOOK_URL" not in source
    assert "requests.post(webhook" not in source


def test_workflow_commits_package_before_slack_and_commits_receipt_afterward():
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "daily-intel.yml").read_text(encoding="utf-8")
    create_at = workflow.index("intel/delivery.py create")
    package_commit_at = workflow.index("Commit canonical artifact and delivery package")
    slack_at = workflow.index("intel/delivery.py resume-slack")
    receipt_commit_at = workflow.index("Commit Slack delivery receipt")
    assert create_at < package_commit_at < slack_at < receipt_commit_at
    assert "SLACK_BOT_TOKEN" in workflow
    assert "SLACK_CHANNEL_ID" in workflow
    assert "SLACK_TEAM_ID" in workflow
    assert "SLACK_WEBHOOK_URL" not in workflow
    assert "if: always()" in workflow
    assert "git diff --cached --quiet ||" in workflow
