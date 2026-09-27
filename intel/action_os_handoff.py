from __future__ import annotations

import argparse
import hashlib
import hmac
import http.client
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _http_json(method: str, path: str, payload: dict[str, Any] | None, capability: str, *, base_url: str) -> dict[str, Any]:
    target = urlparse(base_url)
    if target.scheme != "http" or target.hostname != "127.0.0.1" or target.path not in {"", "/"}:
        raise ValueError("Action OS handoff must target the local Action OS service")
    connection = http.client.HTTPConnection("127.0.0.1", target.port or 8890, timeout=8)
    try:
        body = _canonical(payload) if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if body is not None:
            headers["X-Action-OS-Industry-News-Capability"] = capability
            headers["X-Action-OS-Industry-News-Signature"] = hmac.new(capability.encode(), body, hashlib.sha256).hexdigest()
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        result = json.loads(response.read())
        if response.status not in (200, 201):
            raise RuntimeError(f"Action OS handoff {method} returned HTTP {response.status}")
        if not isinstance(result, dict):
            raise ValueError("Action OS handoff returned an invalid response")
        return result
    finally:
        connection.close()


def publish_review_packets(
    package_path: Path, *, base_url: str, capability: str,
    request_json: Callable[[str, str, dict[str, Any] | None, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    package_path = Path(package_path).resolve()
    package = json.loads(package_path.read_text(encoding="utf-8"))
    destinations = package.get("destinations") or {}
    if (package.get("cadence") != "weekday_daily" or package.get("status") != "fully_delivered"
            or any((destinations.get(name) or {}).get("status") != "verified" for name in ("repository", "slack", "vault"))):
        raise ValueError("Industry News pulse must be fully delivered before Action OS handoff")
    content_hash = hashlib.sha256(str(package.get("canonical_body") or "").encode()).hexdigest()
    if content_hash != package.get("content_sha256") or package.get("brief_id") != f"industry-pulse-{package.get('brief_date')}":
        raise ValueError("Industry News handoff source identity mismatch")
    sender = request_json or (lambda method, path, payload, token: _http_json(method, path, payload, token, base_url=base_url))
    candidates = []
    for signal in package.get("signals") or []:
        if signal.get("classification") != "material":
            continue
        fields = ("proposed_decision", "proposed_next_action", "proposed_owner")
        present = [bool(str(signal.get(field) or "").strip()) for field in fields]
        if any(present) and not all(present):
            raise ValueError("Industry News proposed action is incomplete")
        if not all(present):
            continue
        evidence = signal.get("evidence_links") or []
        if not evidence:
            raise ValueError("Industry News proposed action requires source evidence")
        if not capability:
            raise ValueError("Action OS producer capability is required")
        identity = {"pulse_id": package["brief_id"], "signal_id": signal["signal_id"]}
        payload = {
            "pulse_id": package["brief_id"], "pulse_sha256": content_hash,
            "pulse_link": package_path.as_uri(), "signal_id": signal["signal_id"],
            "classification": "material", "evidence_link": evidence[0],
            **{field: signal[field] for field in fields},
            "idempotency_key": "industry-news:" + hashlib.sha256(_canonical(identity)).hexdigest()[:24],
        }
        created = sender("POST", "/api/intake-review/industry-news", payload, capability)
        candidate_id = str((created.get("candidate") or {}).get("candidate_id") or "")
        if not candidate_id.startswith("ir-industry-news-"):
            raise ValueError("Action OS handoff returned an invalid candidate identity")
        readback = sender("GET", f"/api/intake-review/industry-news/{candidate_id}", None, capability)
        received = (readback.get("candidate") or {}).get("industry_news_intake") or {}
        if readback.get("candidate", {}).get("candidate_id") != candidate_id or any(received.get(key) != value for key, value in payload.items()):
            raise ValueError("Action OS exact candidate readback mismatch")
        candidates.append(candidate_id)
    receipt = {
        "pulse_id": package["brief_id"], "pulse_sha256": content_hash,
        "status": "verified" if candidates else "no_actionable_signals",
        "candidate_ids": candidates,
    }
    with tempfile.NamedTemporaryFile(mode="wb", dir=package_path.parent, delete=False) as staged:
        staged.write(_canonical(receipt) + b"\n")
        staged.flush()
        os.fsync(staged.fileno())
    Path(staged.name).replace(package_path.with_name("action-os-receipt.json"))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Hand off source-backed Industry News decisions to Action OS Intake Review")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--action-os-url", default="http://127.0.0.1:8890")
    args = parser.parse_args()
    capability = os.environ.get("ACTION_OS_INDUSTRY_NEWS_CAPABILITY", "")
    failed = 0
    for path in sorted(args.package_root.glob("*/delivery.json")):
        package = json.loads(path.read_text(encoding="utf-8"))
        if package.get("cadence") != "weekday_daily" or package.get("status") != "fully_delivered":
            continue
        try:
            receipt = publish_review_packets(path, base_url=args.action_os_url, capability=capability)
            print(json.dumps({"pulse_id": receipt["pulse_id"], "status": receipt["status"], "candidate_ids": receipt["candidate_ids"]}))
        except (OSError, ValueError, RuntimeError) as exc:
            failed += 1
            print(json.dumps({"pulse_id": package.get("brief_id"), "status": "failed", "error": str(exc)}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
