"""Disposable scheduler contract tests; never contact live services."""
import copy
import fcntl
import hashlib
import hmac
import json
import plistlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from typing import Any
from intel import local_scheduler as scheduler

DAY = "2026-10-30"


def now(value="2026-10-30T14:00:00+00:00"):
    return datetime.fromisoformat(value)


def package():
    return {
        "brief_date": DAY, "brief_id": "industry-pulse-" + DAY,
        "cadence": "weekday_daily", "producer": "industry_news",
        "canonical_body": "pulse\n", "content_sha256": hashlib.sha256(b"pulse\n").hexdigest(),
        "transaction_id": "transaction", "status": "fully_delivered",
        "destinations": {name: {"status": "verified"} for name in ("repository", "slack", "vault")},
    }


class FakeGateway:
    def __init__(self):
        self.pkg: Any = None
        self.attempt: Any = None
        self.run_list = []
        self.dispatches = []
        self.dispatch_result = "accepted"
        self.delivery_run_list = []
        self.delivery_dispatches = []
        self.delivery_dispatch_result = 'accepted'
        self.notifications = []
        self.alert_ok = True
        self.local_ok = True
        self.cos = {"industry_news": {"daily": {"pulse_id": "industry-pulse-" + DAY, "freshness": "current"}},
                    "sources": [{"id": "industry_news", "status": "current"}]}
        self.refreshes = []
        self.operation = {"status": "succeeded"}

    def package(self, day):
        return copy.deepcopy(self.pkg)

    def generation_attempt(self, day):
        return self.attempt

    def runs(self):
        return copy.deepcopy(self.run_list)

    def dispatch(self, request_id):
        self.dispatches.append(request_id)
        return self.dispatch_result

    def delivery_runs(self):
        return copy.deepcopy(self.delivery_run_list)

    def dispatch_delivery(self, day, request_id):
        self.delivery_dispatches.append((day, request_id))
        return self.delivery_dispatch_result

    def verify_local(self, pkg):
        if not self.local_ok:
            raise ValueError("Vault signature mismatch")

    def cos_brief(self):
        return self.cos

    def refresh(self, key):
        self.refreshes.append(key)
        return {"operation_id": "refresh-1", "status": "queued"}

    def refresh_status(self, operation_id):
        return self.operation

    def alert(self, text):
        self.notifications.append(text)
        return self.alert_ok


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(scheduler, "local scheduler implementation is missing")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.gateway = FakeGateway()
        self.clock = now()
        self.engine = scheduler.Engine(self.root, self.gateway, clock=lambda: self.clock)

    def tick(self, role="watchdog"):
        return self.engine.tick(role)

    def test_weekday_pt_and_dst_time_gates(self):
        for instant, role in [("2026-10-30T13:29:00+00:00", "primary"),
                              ("2026-10-30T13:39:00+00:00", "watchdog"),
                              ("2026-11-02T14:39:00+00:00", "watchdog"),
                              ("2026-10-31T20:00:00+00:00", "primary")]:
            self.clock = now(instant)
            self.assertEqual(self.tick(role)["stage"], "not_due")
        self.assertFalse(self.gateway.dispatches)
        self.assertFalse(list(self.root.glob("*.json")))
        self.clock = now("2026-11-02T14:40:00+00:00")
        self.assertEqual(self.tick()["stage"], "dispatch_wait")

    def test_primary_reserves_uuid_before_dispatch_and_duplicate_is_safe(self):
        def dispatch(request_id):
            saved = json.loads((self.root / (DAY + ".json")).read_text())
            self.assertEqual(saved["request_id"], request_id)
            self.assertEqual(saved["dispatch_attempts"], 1)
            self.gateway.dispatches.append(request_id)
            return "accepted"
        self.gateway.dispatch = dispatch
        self.clock = now("2026-10-30T13:30:00+00:00")
        self.assertEqual(self.tick("primary")["stage"], "dispatch_wait")
        self.tick()
        self.clock = now()
        self.tick()
        self.assertEqual(len(self.gateway.dispatches), 1)

    def test_missed_primary_watchdog_dispatches_same_day_only(self):
        self.clock = now("2026-10-30T13:40:00+00:00")
        self.assertEqual(self.tick()["stage"], "dispatch_wait")
        self.assertEqual(len(self.gateway.dispatches), 1)

    def test_active_run_blocks_dispatch(self):
        self.gateway.run_list = [{"id": 9, "status": "in_progress", "created_at": "2026-10-29T13:30:00Z"}]
        self.assertEqual(self.tick()["stage"], "run_active")
        self.assertFalse(self.gateway.dispatches)

    def test_failed_or_successful_no_package_run_never_redispatches(self):
        for conclusion in ("failure", "cancelled", "success"):
            self.gateway.run_list = [{"id": 9, "status": "completed", "conclusion": conclusion,
                                      "created_at": "2026-10-30T13:30:00Z"}]
            self.assertEqual(self.tick()["stage"], "human_recovery")
        self.assertFalse(self.gateway.dispatches)
        self.assertEqual(len(self.gateway.notifications), 1)

    def test_generation_marker_never_regenerates(self):
        self.gateway.attempt = {"request_id": "prior"}
        self.assertEqual(self.tick()["stage"], "human_recovery")
        self.assertFalse(self.gateway.dispatches)

    def test_lost_dispatch_response_reconciles_exact_title(self):
        self.gateway.dispatch_result = "ambiguous"
        state = self.tick()
        self.assertEqual(state["stage"], "dispatch_unknown")
        self.tick()
        self.gateway.run_list = [{"id": 12, "status": "queued", "created_at": "2026-10-30T13:50:00Z",
                                  "display_title": "Industry News Pulse " + state["request_id"]}]
        state = self.tick()
        self.assertEqual(state["run_id"], 12)
        self.assertEqual(len(self.gateway.dispatches), 1)

    def test_only_definitive_rejection_permits_second_dispatch(self):
        self.gateway.dispatch_result = "rejected"
        self.tick()
        self.tick()
        self.assertEqual(self.tick()["stage"], "human_recovery")
        self.assertEqual(len(self.gateway.dispatches), 2)
        self.assertEqual(len(set(self.gateway.dispatches)), 1)

    def test_read_failure_never_means_absent(self):
        def unavailable(day):
            raise RuntimeError("API unavailable")
        self.gateway.package = unavailable
        result = self.tick()
        self.assertEqual(result["stage"], "error")
        self.assertIn("API unavailable", result["error"])
        self.assertFalse(self.gateway.dispatches)
        self.assertTrue(result["updated_at"])

    def test_corrupt_state_fails_closed(self):
        (self.root / (DAY + ".json")).write_text("{broken")
        with self.assertRaises(ValueError):
            self.tick()
        self.assertFalse(self.gateway.dispatches)
        self.assertEqual((self.root / (DAY + ".json")).read_text(), "{broken")

    def test_corrupt_state_alerts_once_without_overwriting_reservation(self):
        path = self.root / (DAY + '.json')
        path.write_text('{broken')
        for _ in range(2):
            with self.assertRaises(ValueError):
                self.tick()
        self.assertEqual(len(self.gateway.notifications), 1, 'unreadable state needs a durable daily alert')
        self.assertEqual(path.read_text(), '{broken')
        health = json.loads((self.root / (DAY + '.state-error.json')).read_text())
        self.assertTrue(health['alert_sent_at'])
        path.write_text(json.dumps({'day': DAY}))  # Explicit human repair, not engine behavior.
        self.gateway.pkg = package()
        self.assertTrue(self.tick()['recovery_sent_at'])
        self.tick()
        self.assertEqual(len(self.gateway.notifications), 2)

    def test_concurrent_flock_is_noop(self):
        with (self.root / "scheduler.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.tick()["stage"], "locked")
        self.assertFalse(self.gateway.dispatches)

    def test_complete_package_skips_generation_and_validates_cos(self):
        self.gateway.pkg = package()
        self.assertEqual(self.tick()["stage"], "complete")
        self.tick()
        self.assertFalse(self.gateway.dispatches)
        self.assertFalse(self.gateway.refreshes)

    def test_wrong_date_id_hash_or_incomplete_receipts_never_complete(self):
        for field, value in [("brief_date", "2026-10-29"), ("brief_id", "industry-pulse-wrong"),
                             ("content_sha256", "0" * 64), ("status", "partial_delivery")]:
            self.gateway.pkg = package()
            self.gateway.pkg[field] = value
            self.assertNotEqual(self.tick()["stage"], "complete")
        self.gateway.pkg = package()
        self.gateway.pkg["destinations"]["vault"]["status"] = "pending"
        self.assertNotEqual(self.tick()["stage"], "complete")
        self.assertFalse(self.gateway.dispatches)

    def test_local_vault_verification_failure_blocks_cos_refresh(self):
        self.gateway.pkg = package()
        self.gateway.local_ok = False
        self.assertEqual(self.tick()["stage"], "error")
        self.assertFalse(self.gateway.refreshes)

    def test_cos_refresh_waits_then_verifies_identity_and_is_bounded(self):
        self.gateway.pkg = package()
        self.gateway.cos["industry_news"]["daily"]["pulse_id"] = "yesterday"
        self.assertEqual(self.tick()["stage"], "cos_refresh_wait")
        self.gateway.operation = {"status": "running"}
        self.tick()
        self.assertEqual(len(self.gateway.refreshes), 1)
        self.gateway.operation = {"status": "succeeded"}
        for _ in range(5):
            self.tick()
        self.assertEqual(len(self.gateway.refreshes), 3)
        self.assertEqual(self.tick()["stage"], "human_recovery")
        self.gateway.cos["industry_news"]["daily"]["pulse_id"] = "industry-pulse-" + DAY
        self.assertEqual(self.tick()["stage"], "complete")

    def test_cos_identity_without_current_source_is_not_complete(self):
        self.gateway.pkg = package()
        self.gateway.cos["sources"][0]["status"] = "stale"
        self.assertEqual(self.tick()["stage"], "cos_refresh_wait")

    def test_deadline_alert_delivery_retry_and_recovery_once(self):
        self.clock = now("2026-10-30T13:40:00+00:00")
        self.tick()
        self.assertFalse(self.gateway.notifications)
        self.clock = now()
        self.gateway.alert_ok = False
        state = self.tick()
        self.assertNotIn("alert_sent_at", state)
        self.gateway.alert_ok = True
        self.assertTrue(self.tick()["alert_sent_at"])
        self.tick()
        self.gateway.pkg = package()
        self.assertTrue(self.tick()["recovery_sent_at"])
        self.tick()
        self.assertEqual(len(self.gateway.notifications), 3)

    def test_delivery_recovery_waits_for_active_producer(self):
        self.gateway.pkg = package()
        self.gateway.pkg['status'] = 'partial_delivery'
        self.gateway.pkg['destinations']['slack']['status'] = 'pending'
        self.gateway.run_list = [{'id': 17, 'status': 'in_progress', 'created_at': '2026-10-30T13:30:00Z'}]
        self.assertEqual(self.tick()['stage'], 'run_active')
        self.assertFalse(self.gateway.delivery_dispatches)
        self.assertFalse(self.gateway.dispatches)

    def test_delivery_only_recovery_reserves_separate_identity_once(self):
        self.gateway.pkg = package()
        self.gateway.pkg['status'] = 'partial_delivery'
        self.gateway.pkg['destinations']['slack']['status'] = 'pending'
        def dispatch(day, request_id):
            saved = json.loads((self.root / (DAY + '.json')).read_text())
            self.assertEqual(saved['delivery_request_id'], request_id)
            self.assertEqual(saved['delivery_dispatch_attempts'], 1)
            self.gateway.delivery_dispatches.append((day, request_id))
            return 'accepted'
        self.gateway.dispatch_delivery = dispatch
        self.assertEqual(self.tick()['stage'], 'delivery_dispatch_wait')
        for status in ('failed', 'attempting', 'ambiguous_outcome'):
            self.gateway.pkg['destinations']['slack']['status'] = status
            self.tick()
        self.assertEqual(len(self.gateway.delivery_dispatches), 1)
        self.assertFalse(self.gateway.dispatches)

    def test_delivery_lost_response_exact_reconciliation_then_terminal_alert(self):
        self.gateway.pkg = package()
        self.gateway.pkg['status'] = 'partial_delivery'
        self.gateway.pkg['destinations']['slack']['status'] = 'ambiguous_outcome'
        self.gateway.delivery_dispatch_result = 'ambiguous'
        state = self.tick()
        self.assertEqual(state['stage'], 'delivery_dispatch_unknown')
        self.tick()
        run = {'id': 99, 'status': 'in_progress', 'created_at': '2026-10-30T13:45:00Z',
               'display_title': 'Industry News Delivery ' + state['delivery_request_id']}
        self.gateway.delivery_run_list = [run]
        self.assertEqual(self.tick()['stage'], 'delivery_run_active')
        self.assertEqual(self.tick()['delivery_run_id'], 99)
        run['status'] = 'completed'
        run['conclusion'] = 'failure'
        self.assertEqual(self.tick()['stage'], 'human_recovery')
        self.assertEqual(len(self.gateway.delivery_dispatches), 1)
        self.assertFalse(self.gateway.dispatches)

    def test_delivery_rejected_bounded_retry_and_unverified_repo_never_recovers(self):
        self.gateway.pkg = package()
        self.gateway.pkg['status'] = 'partial_delivery'
        self.gateway.pkg['destinations']['slack']['status'] = 'failed'
        self.gateway.pkg['destinations']['repository']['status'] = 'pending'
        self.assertEqual(self.tick()['stage'], 'receipts_wait')
        self.assertFalse(self.gateway.delivery_dispatches)
        self.gateway.pkg['destinations']['repository']['status'] = 'verified'
        self.gateway.delivery_dispatch_result = 'rejected'
        self.tick()
        self.tick()
        self.assertEqual(self.tick()['stage'], 'human_recovery')
        self.assertEqual(len(self.gateway.delivery_dispatches), 2)
        self.assertEqual(len(set(self.gateway.delivery_dispatches)), 1)

    def test_midnight_during_reads_does_not_dispatch_yesterday(self):
        self.clock = now('2026-10-31T06:59:59+00:00')
        def marker(day):
            self.clock = now('2026-10-31T07:00:01+00:00')
            return None
        self.gateway.generation_attempt = marker
        self.assertEqual(self.tick()['stage'], 'not_due')
        self.assertFalse(self.gateway.dispatches)

    def test_recovered_state_preserves_last_error_evidence(self):
        self.gateway.pkg = package()
        self.gateway.local_ok = False
        self.tick()
        self.gateway.local_ok = True
        result = self.tick()
        self.assertEqual(result['stage'], 'complete')
        self.assertEqual(result['last_error'], 'Vault signature mismatch')
        self.assertTrue(result['error_at'])

    def test_lost_cos_response_reuses_key_but_bounds_all_post_attempts(self):
        self.gateway.pkg = package()
        self.gateway.cos['industry_news']['daily']['pulse_id'] = 'yesterday'
        def lost(key):
            self.gateway.refreshes.append(key)
            raise RuntimeError('COS response lost')
        self.gateway.refresh = lost
        for _ in range(6):
            self.tick()
        self.assertEqual(len(self.gateway.refreshes), 3)
        self.assertEqual(len(set(self.gateway.refreshes)), 1)
        self.assertEqual(self.tick()['stage'], 'human_recovery')

    def test_corrupt_reservation_values_fail_closed(self):
        for bad in [{'dispatch_attempts': -1, 'request_id': 'broken', 'dispatch_outcome': 'rejected'},
                    {'dispatch_attempts': 0, 'dispatch_outcome': 'rejected'},
                    {'refresh_attempts': -1}]:
            (self.root / (DAY + '.json')).write_text(json.dumps(dict(day=DAY, **bad)))
            with self.assertRaises(ValueError):
                self.tick()
        self.assertFalse(self.gateway.dispatches)

    def test_reservation_crash_before_response_never_retries_dispatch(self):
        def crashed(request_id):
            raise RuntimeError('process died after reservation')
        self.gateway.dispatch = crashed
        self.assertEqual(self.tick()['stage'], 'error')
        self.gateway.dispatch = lambda request_id: self.fail('must not retry reserved dispatch')
        self.assertEqual(self.tick()['stage'], 'dispatch_unknown')

    def test_exact_title_reconciliation_ignores_similar_title(self):
        self.gateway.dispatch_result = 'ambiguous'
        state = self.tick()
        self.gateway.run_list = [{'id': 11, 'status': 'completed', 'created_at': '2026-10-29T13:30:00Z',
                                  'display_title': 'Industry News Pulse ' + state['request_id'] + '-other'}]
        self.assertEqual(self.tick()['stage'], 'dispatch_unknown')
        self.assertNotIn('run_id', self.tick())
        self.assertEqual(len(self.gateway.dispatches), 1)

    def test_inspect_complete_package_checks_local_and_cos_without_refresh(self):
        self.gateway.pkg = package()
        result = self.engine.inspect()
        self.assertTrue(result.get('local_vault_verified'), 'inspect must verify native local receipt')
        self.assertTrue(result.get('cos_current'), 'inspect must compare exact COS identity')
        self.gateway.cos['industry_news']['daily']['pulse_id'] = 'yesterday'
        self.assertFalse(self.engine.inspect()['cos_current'])
        self.assertFalse(self.gateway.refreshes)
        self.assertFalse(list(self.root.iterdir()))

    def test_inspect_does_not_create_state_or_write(self):
        before = set(self.root.iterdir())
        report = self.engine.inspect()
        self.assertEqual(report["day"], DAY)
        self.assertEqual(before, set(self.root.iterdir()))
        self.assertFalse(self.gateway.dispatches)
        self.assertFalse(self.gateway.notifications)


class NativeGatewayTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(scheduler, "NativeGateway"), "native gateway is missing")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls = []
        self.response = (0, '{}', '')

        def run(args, **kwargs):
            from subprocess import CompletedProcess
            self.calls.append(args)
            return CompletedProcess(args, *self.response)
        self.gateway = scheduler.NativeGateway(self.root / "repo", self.root / "vault", run=run)

    def test_contents_requires_repo_access_and_exact_404_only(self):
        responses = [(0, '{"full_name":"PaymentsGuy/Industry_news"}', ''),
                     (1, '{"message":"Not Found","status":"404"}', 'gh: Not Found (HTTP 404)')]
        def run(args, **kwargs):
            from subprocess import CompletedProcess
            self.calls.append(args)
            return CompletedProcess(args, *(responses.pop(0) if responses else self.response))
        self.gateway.run = run
        self.assertIsNone(self.gateway.package(DAY))
        self.assertIn('repos/PaymentsGuy/Industry_news', self.calls[0])
        self.assertIn('repos/PaymentsGuy/Industry_news/contents/intel/' + DAY + '/delivery.json?ref=main', self.calls[1])
        self.response = (1, '{"message":"Bad credentials","status":"401"}', 'HTTP 401')
        with self.assertRaises(RuntimeError):
            self.gateway.package(DAY)
        self.response = (1, '', 'network disconnected')
        with self.assertRaises(RuntimeError):
            self.gateway.package(DAY)

    def test_contents_decode_and_malformed_json_are_not_absence(self):
        import base64
        self.response = (0, json.dumps({"content": base64.b64encode(json.dumps(package()).encode()).decode(), "encoding": "base64"}), '')
        self.assertEqual(self.gateway.package(DAY), package())
        self.response = (0, '{}', '')
        with self.assertRaises(ValueError):
            self.gateway.package(DAY)

    def test_runs_paginated_slurped_and_counts_verified(self):
        self.response = (0, json.dumps([{"total_count": 2, "workflow_runs": [{"id": 1, "status": "queued", "created_at": "2026-10-30T13:30:00Z"}]},
                                       {"total_count": 2, "workflow_runs": [{"id": 2, "status": "completed", "created_at": "2026-10-30T13:30:00Z"}]}]), '')
        self.assertEqual(len(self.gateway.runs()), 2)
        self.assertIn('--paginate', self.calls[-1])
        self.assertIn('--slurp', self.calls[-1])
        self.response = (0, '[{"total_count":2,"workflow_runs":[]}]', '')
        with self.assertRaises(ValueError):
            self.gateway.runs()

    def test_dispatch_explicit_repo_main_and_transport_ambiguity(self):
        self.assertEqual(self.gateway.dispatch('fixture-id'), 'accepted')
        self.assertEqual(self.calls[-1], ['/opt/homebrew/bin/gh', 'workflow', 'run', 'daily-intel.yml', '--repo',
                                        'PaymentsGuy/Industry_news', '--ref', 'main', '-f', 'request_id=fixture-id'])
        self.response = (1, '', 'connection reset after write')
        self.assertEqual(self.gateway.dispatch('fixture-id'), 'ambiguous')
        self.response = (1, '', 'could not create workflow dispatch event: Unprocessable Entity (HTTP 422)')
        self.assertEqual(self.gateway.dispatch('fixture-id'), 'rejected')
        self.response = (1, '', 'HTTP 503')
        self.assertEqual(self.gateway.dispatch('fixture-id'), 'ambiguous')

    def test_native_delivery_dispatch_contract_and_paginated_reads(self):
        self.assertTrue(hasattr(self.gateway, 'dispatch_delivery'), 'delivery dispatch missing')
        self.assertEqual(self.gateway.dispatch_delivery(DAY, 'fixture-id'), 'accepted')
        self.assertEqual(self.calls[-1], ['/opt/homebrew/bin/gh', 'workflow', 'run', 'reconcile-daily-slack.yml',
                                        '--repo', 'PaymentsGuy/Industry_news', '--ref', 'main',
                                        '-f', 'brief_date=' + DAY, '-f', 'request_id=fixture-id'])
        self.response = (0, '[{"total_count":0,"workflow_runs":[]}]', '')
        self.assertEqual(self.gateway.delivery_runs(), [])
        self.assertIn('repos/PaymentsGuy/Industry_news/actions/workflows/reconcile-daily-slack.yml/runs?branch=main&per_page=100', self.calls[-1])
        self.assertIn('--paginate', self.calls[-1])
        self.assertIn('--slurp', self.calls[-1])

    def test_alert_success_only_on_zero_and_no_model_command(self):
        self.assertTrue(self.gateway.alert('fixture alert'))
        self.assertEqual(self.calls[-1], ['/Users/troymaas/.local/bin/hermes', '--profile', 'default', 'send', '--to', 'telegram', 'fixture alert'])
        self.response = (1, '', 'unavailable')
        self.assertFalse(self.gateway.alert('fixture alert'))

    def test_native_local_vault_receipt_signature_path_file_and_identity(self):
        pkg = package()
        receipt = {'destination': 'vault', 'brief_id': pkg['brief_id'], 'transaction_id': pkg['transaction_id'],
                   'content_sha256': pkg['content_sha256'], 'readback': True, 'receipt_id': 'fixture-receipt',
                   'vault_path': 'Atlas/competitive-intel/intelligence-briefs/' + DAY + ' - ASA Intelligence Brief.md'}
        document = b'---\nfixture: true\n---\n\npulse\n'
        receipt['vault_file_sha256'] = hashlib.sha256(document).hexdigest()
        receipt['signature'] = hmac.new(b'fixture-key', json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode(), hashlib.sha256).hexdigest()
        folder = self.root / 'repo' / 'intel' / DAY
        folder.mkdir(parents=True)
        receipt_file = folder / 'vault-receipt.json'
        receipt_file.write_text(json.dumps(receipt))
        pkg['destinations']['vault'].update(receipt)
        destination = self.root / 'vault' / receipt['vault_path']
        destination.parent.mkdir(parents=True)
        destination.write_bytes(document)
        self.response = (0, 'fixture-key\n', '')
        self.gateway.verify_local(pkg)
        self.assertEqual(self.calls[-1], ['/usr/bin/security', 'find-generic-password', '-w', '-s', 'ai.hermes.asa-industry-news.vault-receipt'])
        for field, value in [('signature', 'forged'), ('vault_path', '../escape'), ('brief_id', 'wrong')]:
            bad = dict(receipt, **{field: value})
            receipt_file.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                self.gateway.verify_local(pkg)
        receipt_file.write_text(json.dumps(receipt))
        destination.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.gateway.verify_local(pkg)

    def test_disposable_gh_executable_lost_dispatch_journey(self):
        import sys
        import subprocess
        fake = self.root / 'fake-gh'
        log = self.root / 'gh-calls.jsonl'
        fake.write_text('#!' + sys.executable + '\n' +
                        'import json, pathlib, sys\n' +
                        'log = pathlib.Path(' + repr(str(log)) + ')\n' +
                        'with log.open("a") as h: h.write(json.dumps(sys.argv[1:]) + "\\n")\n' +
                        'if sys.argv[1] == "workflow":\n'
                        '    print("connection reset after acceptance", file=sys.stderr)\n'
                        '    sys.exit(1)\n'
                        'if "/contents/" in sys.argv[2]:\n'
                        '    print(json.dumps({"message":"Not Found","status":"404"}))\n'
                        '    print("gh: Not Found (HTTP 404)", file=sys.stderr)\n'
                        '    sys.exit(1)\n'
                        'if "/runs?" in sys.argv[2]:\n'
                        '    print(json.dumps([{"total_count":0,"workflow_runs":[]}]))\n'
                        'else: print(json.dumps({"full_name":"PaymentsGuy/Industry_news"}))\n')
        fake.chmod(0o755)
        gateway = scheduler.NativeGateway(self.root / 'repo', self.root / 'vault', run=subprocess.run)
        gateway.GH = str(fake)
        engine = scheduler.Engine(self.root / 'state', gateway, clock=lambda: now('2026-10-30T13:40:00+00:00'))
        self.assertEqual(engine.tick('watchdog')['stage'], 'dispatch_unknown')
        self.assertEqual(engine.tick('watchdog')['stage'], 'dispatch_unknown')
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        dispatches = [call for call in calls if call[0] == 'workflow']
        self.assertEqual(len(dispatches), 1)
        self.assertIn('--repo', dispatches[0])
        self.assertEqual(dispatches[0][2], 'daily-intel.yml')

    def test_fake_cos_server_scoped_refresh_headers_and_poll(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import threading
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = ('<meta name="chief-of-staff-token" content="fixture-token" />' if self.path == '/' else
                        json.dumps({'status': 'running'} if self.path.startswith('/api/refresh/') else {'industry_news': {}})).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)
            def do_POST(self):
                received.append((self.path, dict(self.headers), json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(202)
                self.end_headers()
                self.wfile.write(b'{"operation_id":"refresh-1","status":"queued"}')
            def log_message(self, format, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.gateway.cos_url = 'http://127.0.0.1:' + str(server.server_port)
        self.assertEqual(self.gateway.cos_brief(), {'industry_news': {}})
        self.assertEqual(self.gateway.refresh('same-key')['operation_id'], 'refresh-1')
        self.assertEqual(self.gateway.refresh_status('refresh-1')['status'], 'running')
        path, headers, body = received[0]
        self.assertEqual(path, '/api/refresh')
        self.assertEqual(body, {'source_id': 'industry_news'})
        self.assertEqual(headers['Origin'], self.gateway.cos_url)
        self.assertEqual(headers['X-Chief-Of-Staff-Token'], 'fixture-token')
        self.assertEqual(headers['Idempotency-Key'], 'same-key')


class DeploymentTests(unittest.TestCase):
    def test_cli_inspect_injected_gateway_is_read_only(self):
        import contextlib
        import io
        self.assertTrue(hasattr(scheduler, 'main'), 'CLI entry point missing')
        with tempfile.TemporaryDirectory() as directory:
            gateway = FakeGateway()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = scheduler.main(['inspect', '--state-root', directory], gateway=gateway, clock=now)
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())['day'], DAY)
            self.assertFalse(list(Path(directory).iterdir()))
            self.assertFalse(gateway.dispatches)

    def test_launchd_artifacts_and_native_wrapper(self):
        root = Path(__file__).resolve().parents[1]
        prefix = '/Users/troymaas/.local/share/asa-industry-news/repo/'
        for label, role in [('scheduler', 'primary'), ('watchdog', 'watchdog')]:
            path = root / 'deploy' / ('ai.hermes.asa-industry-news-' + label + '.plist')
            self.assertTrue(path.exists(), 'launchd artifact is missing')
            data = plistlib.loads(path.read_bytes())
            self.assertEqual(data['ProgramArguments'], [prefix + 'scripts/run_local_scheduler', role])
            self.assertFalse(data.get('KeepAlive', False))
            if role == 'watchdog':
                self.assertEqual(data['StartInterval'], 300)
                self.assertTrue(data['RunAtLoad'])
            else:
                self.assertEqual(data['StartCalendarInterval'], [{'Weekday': d, 'Hour': 6, 'Minute': 30} for d in range(1, 6)])
        wrapper = root / 'scripts/run_local_scheduler'
        self.assertTrue(wrapper.exists(), 'native wrapper missing')
        text = wrapper.read_text()
        self.assertIn('/opt/homebrew/bin/python3', text)
        self.assertIn('PYTHONDONTWRITEBYTECODE', text)
        self.assertNotIn('uv run', text)
        self.assertNotIn('git ', text)


if __name__ == "__main__":
    unittest.main()
