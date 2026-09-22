from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    """An immutable intelligence-routing handoff is incomplete or inconsistent."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_body(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid contract document: {path}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"contract document must be an object: {path}")
    return value


def validate_industry_pulse_delivery(package: dict[str, Any], canonical_text: str) -> None:
    required = {
        "version", "brief_id", "brief_date", "cadence", "interval", "producer",
        "canonical_body", "content_sha256", "transaction_id", "classification_counts",
        "material_signal_count", "signals", "destinations", "status",
    }
    if not required.issubset(package):
        raise ContractError("industry pulse receipt is missing required fields")
    body = _canonical_body(canonical_text)
    if body != package["canonical_body"] or hashlib.sha256(body.encode()).hexdigest() != package["content_sha256"]:
        raise ContractError("canonical content hash mismatch")
    if package["cadence"] != "weekday_daily" or package["producer"] != "industry_news":
        raise ContractError("industry pulse owner or cadence is invalid")
    if package["brief_id"] != f"industry-pulse-{package['brief_date']}":
        raise ContractError("industry pulse identity is invalid")
    interval = package["interval"]
    if not isinstance(interval, dict) or set(interval) != {"start", "end"}:
        raise ContractError("reporting interval is missing or malformed")
    counts = package["classification_counts"]
    expected_classes = {"material", "monitor", "noise", "duplicate", "needs_validation"}
    if not isinstance(counts, dict) or set(counts) != expected_classes or any(not isinstance(value, int) or value < 0 for value in counts.values()):
        raise ContractError("classification counts are incomplete")
    if counts["material"] != package["material_signal_count"]:
        raise ContractError("material signal count does not reconcile")
    signals = package["signals"]
    if not isinstance(signals, list) or len(signals) != package["material_signal_count"]:
        raise ContractError("material signal identities are incomplete")
    if any(
        not isinstance(signal, dict)
        or signal.get("classification") != "material"
        or not signal.get("signal_id")
        or not signal.get("title")
        for signal in signals
    ):
        raise ContractError("material signal identities are incomplete")
    destinations = package["destinations"]
    if not isinstance(destinations, dict) or set(destinations) != {"repository", "slack", "vault"}:
        raise ContractError("destination identities are incomplete")


def extract_daily_pulse_metadata(body: str, pulse_id: str) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts_match = re.search(
        r"(?m)^\*\*Classification counts:\*\* material=(\d+); monitor=(\d+); noise=(\d+); duplicate=(\d+); needs_validation=(\d+)$",
        body,
    )
    if not counts_match:
        raise ContractError("classification counts are missing from daily pulse")
    classes = ("material", "monitor", "noise", "duplicate", "needs_validation")
    counts = {name: int(value) for name, value in zip(classes, counts_match.groups())}
    section = re.search(r"(?ms)^## Material signals\s*(.*?)(?=^## |\Z)", body)
    reference_urls = {
        number: url
        for number, url in re.findall(r"(?m)^\s*(\d+)\.\s+.*?(https?://\S+)", body)
    }
    blocks = re.findall(
        r"(?ms)^###\s+(?:\d+\.\s*)?(.+?)\s*$\n(.*?)(?=^###\s+|\Z)",
        section.group(1) if section else "",
    )
    signals = []
    for title, block in blocks:
        direct_links = set(re.findall(r"https?://[^\s)>]+", block))
        cited_links = {reference_urls[number] for number in re.findall(r"\[REF\s+(\d+)\]", block, re.I) if number in reference_urls}
        signal: dict[str, Any] = {
            "signal_id": "signal-" + hashlib.sha256(f"{pulse_id}|{title}".encode()).hexdigest()[:24],
            "title": title,
            "classification": "material",
            "evidence_links": sorted(direct_links | cited_links),
        }
        proposals = {
            key: re.search(rf"(?m)^\*\*{label}:\*\*\s*(.+?)\s*$", block)
            for key, label in (
                ("proposed_decision", "Proposed decision"),
                ("proposed_next_action", "Proposed next action"),
                ("proposed_owner", "Proposed owner"),
            )
        }
        if all(match for match in proposals.values()):
            signal.update({key: match.group(1).strip() for key, match in proposals.items() if match})
        signals.append(signal)
    if len(signals) != counts["material"]:
        raise ContractError("material signal entries do not match classification counts")
    return counts, signals


def load_industry_pulse_package(brief_path: Path, receipt_path: Path) -> dict[str, Any]:
    package = _load_object(receipt_path)
    validate_industry_pulse_delivery(package, brief_path.read_text(encoding="utf-8"))
    return package


def load_competitive_radar_package(report_path: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = _load_object(manifest_path)
    evidence_key = "raw_evidence" if "raw_evidence" in manifest else "evidence"
    required = {"report_date", "report_path", "report_sha256", "atlas_backlink", "transaction_id", evidence_key}
    if not required.issubset(manifest):
        raise ContractError("competitive radar manifest is missing required fields")
    if _sha256(report_path) != manifest["report_sha256"]:
        raise ContractError("competitive radar report hash mismatch")
    evidence = manifest[evidence_key]
    if not isinstance(evidence, list) or not evidence:
        raise ContractError("evidence manifest is missing")
    root = manifest_path.parent.resolve()
    for entry in evidence:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise ContractError("evidence manifest is incomplete")
        candidate = (root / entry["path"]).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ContractError("evidence path escapes package root") from exc
        if not candidate.is_file() or _sha256(candidate) != entry["sha256"]:
            raise ContractError("evidence manifest hash mismatch")
    return manifest
