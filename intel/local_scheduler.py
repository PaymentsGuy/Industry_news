"""Same-Mac, fail-closed Industry News scheduling; Python standard library only."""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import hmac
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")


def canonical(text):
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"


def atomic_json(path, value):
    """Persist reservations before external effects, including directory metadata."""
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        staged = Path(handle.name)
        try:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(staged, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            staged.unlink(missing_ok=True)


def validate_package(package, day):
    expected = {"brief_date": day, "brief_id": "industry-pulse-" + day,
                "cadence": "weekday_daily", "producer": "industry_news"}
    if any(package.get(key) != value for key, value in expected.items()):
        raise ValueError("remote package identity mismatch")
    body = package["canonical_body"]
    if body != canonical(body) or hashlib.sha256(body.encode()).hexdigest() != package["content_sha256"]:
        raise ValueError("remote package canonical body hash mismatch")
    if not package.get("transaction_id"):
        raise ValueError("remote package transaction missing")
    return package.get("status") == "fully_delivered" and all(
        package.get("destinations", {}).get(name, {}).get("status") == "verified"
        for name in ("repository", "slack", "vault")
    )


class Engine:
    def __init__(self, state_root, gateway, *, clock=lambda: datetime.now(timezone.utc)):
        self.root = Path(state_root)
        self.gateway = gateway
        self.clock = clock

    def _load(self, day):
        path = self.root / (day + ".json")
        if not path.exists():
            return {"day": day}
        state = json.loads(path.read_text())
        if not isinstance(state, dict) or state.get("day") != day:
            raise ValueError("invalid daily scheduler state")
        # A damaged reservation must never silently become permission to dispatch.
        for field, maximum in (("dispatch_attempts", 2), ("delivery_dispatch_attempts", 2), ("refresh_attempts", 3)):
            count = state.get(field, 0)
            if type(count) is not int or not 0 <= count <= maximum:
                raise ValueError("invalid scheduler attempt counter")
        for prefix in ("", "delivery_"):
            if any(prefix + key in state for key in ("request_id", "dispatch_outcome", "dispatch_attempts")):
                try:
                    request_id = state[prefix + "request_id"]
                    valid = str(uuid.UUID(request_id)) == request_id
                except (KeyError, ValueError, TypeError, AttributeError):
                    valid = False
                if not valid or not state.get(prefix + "dispatch_attempts") or state.get(prefix + "dispatch_outcome") not in {"accepted", "rejected", "ambiguous"}:
                    raise ValueError("invalid dispatch reservation")
        return state

    def inspect(self):
        day = self.clock().astimezone(PACIFIC).date().isoformat()
        package = self.gateway.package(day)
        report = {"day": day, "state": self._load(day), "package_present": package is not None,
                  "package_complete": validate_package(package, day) if package is not None else False,
                  "generation_attempt_present": self.gateway.generation_attempt(day) is not None,
                  "runs": self.gateway.runs(), "delivery_runs": self.gateway.delivery_runs(),
                  "local_vault_verified": False, "cos_current": False}
        if package is not None and report["package_complete"]:
            self.gateway.verify_local(package)
            report["local_vault_verified"] = True
            report["cos_current"] = self._cos_current(self.gateway.cos_brief(), package["brief_id"])
        return report

    @staticmethod
    def _cos_current(brief, pulse_id):
        daily = brief.get("industry_news", {}).get("daily", {})
        current = any(row.get("id") == "industry_news" and row.get("status") == "current"
                      for row in brief.get("sources", []))
        return daily.get("pulse_id") == pulse_id and daily.get("freshness") == "current" and current

    def tick(self, role):
        if role not in {"primary", "watchdog"}:
            raise ValueError("unknown scheduler role")
        local = self.clock().astimezone(PACIFIC)
        day = local.date().isoformat()
        if local.weekday() >= 5 or (local.hour, local.minute) < (6, 30 if role == "primary" else 40):
            return {"day": day, "stage": "not_due"}
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.root / "scheduler.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"day": day, "stage": "locked"}
            stamp = local.isoformat()
            health_path = self.root / (day + ".state-error.json")
            try:
                state = self._load(day)
            except (OSError, ValueError):
                # Never overwrite an unreadable reservation to record its own failure.
                health = json.loads(health_path.read_text()) if health_path.exists() else {"day": day}
                health.update(stage="error", updated_at=stamp, error_at=stamp,
                              last_error="daily scheduler state unreadable or invalid; preserve reservations")
                atomic_json(health_path, health)
                if not health.get("alert_sent_at"):
                    try:
                        sent = self.gateway.alert(f"Industry News {day}: daily scheduler state unreadable; human repair required, do not delete reservations or rerun generation.")
                    except Exception:
                        sent = False
                    if sent:
                        health["alert_sent_at"] = stamp
                    else:
                        health["alert_error_at"] = stamp
                    atomic_json(health_path, health)
                raise
            if health_path.exists():
                health = json.loads(health_path.read_text())
                for key in ("alert_sent_at", "last_error", "error_at"):
                    if key in health:
                        state.setdefault(key, health[key])

            def save(stage, error=None):
                state.update(stage=stage, updated_at=stamp)
                state.setdefault("started_at", stamp)
                if error:
                    state["error"] = error
                    state["last_error"] = error
                    state["error_at"] = stamp
                else:
                    state.pop("error", None)
                state.setdefault("stage_timestamps", {})[stage] = stamp
                atomic_json(self.root / (day + ".json"), state)

            try:
                self._advance(state, day, save)
            except Exception as exc:
                # Gateways use bounded, secret-free exception messages.
                save("error", str(exc))
            needs_alert = state["stage"] in {"error", "human_recovery"} or (
                state["stage"] != "complete" and local.hour >= 7)
            if needs_alert and not state.get("alert_sent_at"):
                text = f"Industry News {day}: {state['stage']}; {state.get('error', '07:00 PT delivery deadline missed')}. Human review; do not rerun paid generation."
                try:
                    sent = self.gateway.alert(text)
                except Exception:
                    sent = False
                if sent:
                    state["alert_sent_at"] = stamp
                else:
                    state["alert_error_at"] = stamp
                atomic_json(self.root / (day + ".json"), state)
            if state["stage"] == "complete" and state.get("alert_sent_at") and not state.get("recovery_sent_at"):
                try:
                    sent = self.gateway.alert(f"Industry News {day}: recovered; repository, Slack, Vault and COS identity verified.")
                except Exception:
                    sent = False
                if sent:
                    state["recovery_sent_at"] = stamp
                else:
                    state["recovery_error_at"] = stamp
                atomic_json(self.root / (day + ".json"), state)
            return state

    def _advance(self, state, day, save):
        package = self.gateway.package(day)
        if package is not None:
            if not validate_package(package, day):
                destinations = package.get("destinations", {})
                if (destinations.get("repository", {}).get("status") == "verified"
                        and destinations.get("slack", {}).get("status") in {"pending", "failed", "attempting", "ambiguous_outcome"}):
                    self._delivery(state, day, save)
                else:
                    save("receipts_wait")
                return
            self.gateway.verify_local(package)
            brief = self.gateway.cos_brief()
            if self._cos_current(brief, package["brief_id"]):
                save("complete")
                return
            if state.get("refresh_operation"):
                operation = self.gateway.refresh_status(state["refresh_operation"])
                if operation["status"] in {"queued", "running", "in_progress"}:
                    save("cos_refresh_wait")
                    return
                state.pop("refresh_operation")
            if state.get("refresh_attempts", 0) >= 3:
                save("human_recovery", "COS identity still stale after three scoped refresh attempts")
                return
            # Persist before POST. A lost response is retried using the SAME idempotency key.
            if not state.get("refresh_pending_key"):
                state["refresh_pending_key"] = f"industry-news-{day}-{state.get('refresh_attempts', 0) + 1}"
            state["refresh_attempts"] = state.get("refresh_attempts", 0) + 1
            save("cos_refresh_reserved")
            operation = self.gateway.refresh(state["refresh_pending_key"])
            state["refresh_operation"] = operation["operation_id"]
            state.pop("refresh_pending_key")
            save("cos_refresh_wait")
            return

        runs = self.gateway.runs()  # Every page must be readable before dispatch.
        request_id = state.get("request_id")
        matches = [run for run in runs if request_id and run.get("display_title") == "Industry News Pulse " + request_id]
        if len(matches) > 1:
            save("human_recovery", "multiple workflow runs match reserved request identity")
            return
        if matches:
            state["run_id"] = matches[0]["id"]
        if any(run["status"] != "completed" for run in runs):
            save("run_active")
            return
        today_runs = [run for run in runs if datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")).astimezone(PACIFIC).date().isoformat() == day]
        if matches or today_runs:
            save("human_recovery", "completed daily workflow has no package; no automatic paid rerun")
            return
        if self.gateway.generation_attempt(day) is not None:
            save("human_recovery", "paid generation already reserved remotely")
            return
        outcome = state.get("dispatch_outcome")
        if request_id and outcome != "rejected":
            save("dispatch_unknown" if outcome != "accepted" else "dispatch_wait")
            return
        if state.get("dispatch_attempts", 0) >= 2:
            save("human_recovery", "two definitive dispatch rejections")
            return
        if self.clock().astimezone(PACIFIC).date().isoformat() != day:
            save("not_due")
            return
        state.setdefault("request_id", str(uuid.uuid4()))
        state["dispatch_attempts"] = state.get("dispatch_attempts", 0) + 1
        state["dispatch_outcome"] = "ambiguous"
        save("dispatch_reserved")
        outcome = self.gateway.dispatch(state["request_id"])
        if outcome not in {"accepted", "rejected", "ambiguous"}:
            raise ValueError("invalid dispatch result")
        state["dispatch_outcome"] = outcome
        save({"accepted": "dispatch_wait", "rejected": "dispatch_rejected", "ambiguous": "dispatch_unknown"}[outcome])


    def _delivery(self, state, day, save):
        """At most one accepted/unknown delivery-only workflow, never paid recovery."""
        runs = self.gateway.delivery_runs()
        producer_runs = self.gateway.runs()
        if any(run["status"] != "completed" for run in producer_runs):
            save("run_active")
            return
        request_id = state.get("delivery_request_id")
        matches = [run for run in runs if request_id and run.get("display_title") == "Industry News Delivery " + request_id]
        if len(matches) > 1:
            save("human_recovery", "multiple delivery runs match reserved identity")
            return
        if matches:
            state["delivery_run_id"] = matches[0]["id"]
        if any(run["status"] != "completed" for run in runs):
            save("delivery_run_active")
            return
        today_runs = [run for run in runs if datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")).astimezone(PACIFIC).date().isoformat() == day]
        if matches or today_runs:
            save("human_recovery", "delivery recovery completed but Slack receipt is not verified")
            return
        outcome = state.get("delivery_dispatch_outcome")
        if request_id and outcome != "rejected":
            save("delivery_dispatch_wait" if outcome == "accepted" else "delivery_dispatch_unknown")
            return
        if state.get("delivery_dispatch_attempts", 0) >= 2:
            save("human_recovery", "two definitive delivery dispatch rejections")
            return
        if self.clock().astimezone(PACIFIC).date().isoformat() != day:
            save("not_due")
            return
        state.setdefault("delivery_request_id", str(uuid.uuid4()))
        state["delivery_dispatch_attempts"] = state.get("delivery_dispatch_attempts", 0) + 1
        state["delivery_dispatch_outcome"] = "ambiguous"
        save("delivery_dispatch_reserved")
        outcome = self.gateway.dispatch_delivery(day, state["delivery_request_id"])
        if outcome not in {"accepted", "rejected", "ambiguous"}:
            raise ValueError("invalid delivery dispatch result")
        state["delivery_dispatch_outcome"] = outcome
        save({"accepted": "delivery_dispatch_wait", "rejected": "delivery_dispatch_rejected", "ambiguous": "delivery_dispatch_unknown"}[outcome])


class NativeGateway:
    """Read-only repository/Vault adapter; only dispatch, alerts and scoped COS POST write."""
    REPO = "PaymentsGuy/Industry_news"
    GH: str = "/opt/homebrew/bin/gh"

    def __init__(self, repo_root, vault_root, *, run=subprocess.run):
        self.repo_root = Path(repo_root)
        self.vault_root = Path(vault_root)
        self.run = run
        self.cos_url = "http://127.0.0.1:4173"

    def _command(self, args):
        try:
            return self.run(args, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("local command unavailable or timed out") from None

    def _api(self, endpoint, *, paginate=False, absent_ok=False):
        args = [self.GH, "api", endpoint]
        if paginate:
            args += ["--paginate", "--slurp"]
        result = self._command(args)
        try:
            payload = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise RuntimeError("GitHub API response is not readable JSON") from None
        if result.returncode:
            if (absent_ok and isinstance(payload, dict) and str(payload.get("status")) == "404"
                    and payload.get("message") == "Not Found" and "(HTTP 404)" in result.stderr):
                return None
            raise RuntimeError("GitHub API read failed; absence not established")
        return payload

    def _contents(self, day, filename):
        # A hidden/inaccessible repository may also yield 404: establish repo access first.
        self._api(f"repos/{self.REPO}")
        result = self._api(f"repos/{self.REPO}/contents/intel/{day}/{filename}?ref=main", absent_ok=True)
        if result is None:
            return None
        if not isinstance(result, dict) or result.get("encoding") != "base64" or not isinstance(result.get("content"), str):
            raise ValueError("GitHub contents response is malformed")
        try:
            body = base64.b64decode("".join(result["content"].split()), validate=True)
            value = json.loads(body)
        except (ValueError, UnicodeError):
            raise ValueError("GitHub contents JSON is malformed") from None
        if not isinstance(value, dict):
            raise ValueError("GitHub contents must contain a JSON object")
        return value

    def package(self, day):
        return self._contents(day, "delivery.json")

    def generation_attempt(self, day):
        return self._contents(day, "generation-attempt.json")

    def runs(self):
        return self._runs("daily-intel.yml")

    def delivery_runs(self):
        return self._runs("reconcile-daily-slack.yml")

    def _runs(self, workflow):
        pages = self._api(f"repos/{self.REPO}/actions/workflows/{workflow}/runs?branch=main&per_page=100", paginate=True)
        if not isinstance(pages, list) or not pages:
            raise ValueError("workflow pagination missing")
        runs = {}
        for page in pages:
            if not isinstance(page, dict) or not isinstance(page.get("workflow_runs"), list):
                raise ValueError("workflow page malformed")
            for run in page["workflow_runs"]:
                if not isinstance(run, dict) or not all(run.get(key) for key in ("id", "status", "created_at")):
                    raise ValueError("workflow run malformed")
                runs[run["id"]] = run
        if any(page.get("total_count") != len(runs) for page in pages):
            raise ValueError("workflow pagination incomplete or changed during read")
        return list(runs.values())

    def dispatch(self, request_id):
        return self._dispatch("daily-intel.yml", ["-f", "request_id=" + request_id])

    def dispatch_delivery(self, day, request_id):
        return self._dispatch("reconcile-daily-slack.yml", ["-f", "brief_date=" + day, "-f", "request_id=" + request_id])

    def _dispatch(self, workflow, fields):
        try:
            result = self._command([self.GH, "workflow", "run", workflow, "--repo", self.REPO,
                                    "--ref", "main", *fields])
        except RuntimeError:
            return "ambiguous"
        if result.returncode == 0:
            return "accepted"
        # Only an explicit HTTP client rejection is safe to retry. Network/5xx are UNKNOWN.
        if re.search(r"\(HTTP (400|401|403|404|405|422|429)\)", result.stderr):
            return "rejected"
        return "ambiguous"

    def verify_local(self, package):
        day = package["brief_date"]
        receipt_file = self.repo_root / "intel" / day / "vault-receipt.json"
        try:
            receipt = json.loads(receipt_file.read_text())
        except (OSError, ValueError):
            raise ValueError("local Vault receipt missing or malformed") from None
        remote = {key: value for key, value in package["destinations"]["vault"].items() if key != "status"}
        if receipt != remote:
            raise ValueError("local Vault receipt differs from remote verified receipt")
        if receipt.get("destination") != "vault" or receipt.get("readback") is not True or not receipt.get("receipt_id"):
            raise ValueError("Vault receipt lacks destination readback")
        if any(receipt.get(key) != package.get(key) for key in ("transaction_id", "brief_id", "content_sha256")):
            raise ValueError("Vault receipt identity mismatch")
        expected_path = f"Atlas/competitive-intel/intelligence-briefs/{day} - ASA Intelligence Brief.md"
        if receipt.get("vault_path") != expected_path:
            raise ValueError("Vault receipt path mismatch")
        root = self.vault_root.resolve()
        target = (root / expected_path).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Vault path escapes configured root")
        result = self._command(["/usr/bin/security", "find-generic-password", "-w", "-s",
                                "ai.hermes.asa-industry-news.vault-receipt"])
        key = result.stdout.rstrip("\n").encode()
        if result.returncode or not key:
            raise ValueError("Vault verification key unavailable")
        unsigned = {name: value for name, value in receipt.items() if name != "signature"}
        signed = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        signature = hmac.new(key, signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(receipt.get("signature", "")), signature):
            raise ValueError("Vault receipt signature mismatch")
        try:
            document = target.read_bytes()
        except OSError:
            raise ValueError("Vault destination unavailable") from None
        if hashlib.sha256(document).hexdigest() != receipt.get("vault_file_sha256"):
            raise ValueError("Vault file readback hash mismatch")
        # Bind file body to the same canonical pulse, not just a signed file digest.
        try:
            body = document.decode().split("---\n\n", 1)[1]
        except (UnicodeError, IndexError):
            raise ValueError("Vault file frontmatter/body malformed") from None
        if body != package["canonical_body"]:
            raise ValueError("Vault file body differs from canonical pulse")

    def _http(self, path, *, payload=None, headers=None):
        raw = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.cos_url + path, data=raw, headers=headers or {},
                                         method="POST" if raw is not None else "GET")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.read().decode()
        except (OSError, ValueError):
            raise RuntimeError("COS local API unavailable or rejected request") from None

    def cos_brief(self):
        try:
            return json.loads(self._http("/api/v3/command-brief"))
        except ValueError:
            raise ValueError("COS command brief malformed") from None

    def refresh_status(self, operation_id):
        if not re.fullmatch(r"refresh-[A-Za-z0-9-]+", operation_id):
            raise ValueError("COS refresh identity malformed")
        try:
            return json.loads(self._http("/api/refresh/" + operation_id))
        except ValueError:
            raise ValueError("COS refresh status malformed") from None

    def refresh(self, key):
        class TokenParser(HTMLParser):
            token = None

            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == "meta" and values.get("name") == "chief-of-staff-token":
                    self.token = values.get("content")

        parser = TokenParser()
        parser.feed(self._http("/"))
        if not parser.token or parser.token == "__CHIEF_OF_STAFF_TOKEN__":
            raise ValueError("COS launch token unavailable")
        headers = {"Content-Type": "application/json", "Origin": self.cos_url,
                   "X-Chief-Of-Staff-Token": parser.token, "Idempotency-Key": key}
        try:
            return json.loads(self._http("/api/refresh", payload={"source_id": "industry_news"}, headers=headers))
        except ValueError:
            raise ValueError("COS refresh response malformed") from None

    def alert(self, text):
        result = self._command(["/Users/troymaas/.local/bin/hermes", "--profile", "default", "send",
                                "--to", "telegram", text])
        return result.returncode == 0


def main(argv=None, *, gateway=None, clock=lambda: datetime.now(timezone.utc)):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("primary", "watchdog", "inspect"))
    app_root = Path.home() / ".local/share/asa-industry-news"
    parser.add_argument("--state-root", type=Path, default=app_root / "scheduler-state")
    parser.add_argument("--repo-root", type=Path, default=app_root / "repo")
    parser.add_argument("--vault-root", type=Path,
                        default=Path.home() / "Documents/Documents - Troy’s MacBook Air/Main local Vault")
    args = parser.parse_args(argv)
    engine = Engine(args.state_root, gateway or NativeGateway(args.repo_root, args.vault_root), clock=clock)
    try:
        report = engine.inspect() if args.mode == "inspect" else engine.tick(args.mode)
    except Exception:
        # Do not emit arbitrary subprocess output, receipt content, or key material.
        print(json.dumps({"stage": "error", "error": "scheduler preflight/state unavailable; inspect permissions and daily state without deleting reservations"}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 1 if report.get("stage") in {"error", "human_recovery"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
