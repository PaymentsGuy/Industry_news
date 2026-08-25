#!/usr/bin/env python3
"""Update recent context and durable event memory after brief synthesis.

This is invoked as a separate step in the workflow:
    python intel/update_ledger.py --brief-file intel/<date>/brief.md \
                                  --ledger-out intel/<date>/ledger.json \
                                  --prior-ledger intel/<prev-date>/ledger.json \
                                  --event-registry intel/event_registry.json

The rolling ledger retains 90 days of narrative context. The durable event
registry retains covered event identity indefinitely so old stories cannot
become fresh merely because they aged out of recent context.

Topic extraction is done by an LLM call — we hand it the brief and ask for a
structured topic list. This is one extra Perplexity call per run.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import click

try:
    from intel.llm_provider import (
        MissingProviderCredential,
        perplexity_chat_completion,
        require_perplexity_api_key,
    )
except ModuleNotFoundError:  # pragma: no cover - supports `python intel/update_ledger.py`
    from llm_provider import (
        MissingProviderCredential,
        perplexity_chat_completion,
        require_perplexity_api_key,
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ledger")

LEDGER_WINDOW_DAYS = 90
EXTRACTION_MODEL = "sonar"

EXTRACTION_PROMPT = """You are extracting structured topic data from a daily
competitive intelligence brief, so the next day's brief can dedupe against it.

Your job: read the brief and produce a JSON array of topic entries. One entry
per distinct story/topic the brief covered. A "topic" is the underlying
matter, not the article — if the brief mentions Jack Henry's Bud integration
in three places, that is ONE topic.

Be conservative. If you're not sure whether two paragraphs describe one topic
or two, treat them as one topic and include both summaries in the summary
field separated by "; ". Over-merging is safer than over-splitting.

For each topic produce:
  - topic_key: a short, stable, snake_case identifier. Use entity + concept
    when possible (e.g. "banno_bud_enrichment", "cfpb_1033_stay",
    "personetics_mcp_server"). Avoid dates in the key — the same topic should
    keep the same key over multiple days.
  - summary: one sentence (max 30 words) capturing what the brief said. This
    is what will be shown to the LLM tomorrow when it decides whether new
    coverage of this topic is a meaningful delta.
  - entities: array of named entities involved (companies, regulators,
    standards bodies). Use canonical names ("Jack Henry", not "JKHY").
  - roadmap_areas: array from {vault, compass, auth, verify, pay, one_view,
    forecast, horizontal} — the ASA product areas the brief associated with
    this topic. Empty array if not stated.
  - source_urls: array of exact reference URLs supporting this topic.
  - source_dates: array of exact reference dates supporting this topic, in
    YYYY-MM-DD form when the brief provides that format.

Return ONLY a JSON array. No prose, no markdown fences. Example:

[
  {
    "topic_key": "banno_bud_enrichment",
    "summary": "Jack Henry shipped Bud Financial transaction enrichment as a native Banno feature.",
    "entities": ["Jack Henry", "Bud Financial"],
    "roadmap_areas": ["one_view", "forecast"]
  }
]

If the brief is a quiet-day brief with no stories, return an empty array: []

BRIEF:
"""


def extract_topics_from_brief(
    brief_text: str,
    completion_func=perplexity_chat_completion,
) -> list[dict]:
    """Call Perplexity to pull topic entries out of today's brief."""
    text = completion_func(
        messages=[{"role": "user", "content": EXTRACTION_PROMPT + brief_text}],
        model=EXTRACTION_MODEL,
        max_tokens=2000,
        temperature=0.0,
    ).strip()
    # Strip code fences if the model added them despite instructions
    if text.startswith("```"):
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1:]
        if text.endswith("```"):
            text = text[:-3]
    text = text.strip()
    try:
        topics = json.loads(text)
    except json.JSONDecodeError as e:
        log.warning("topic extraction returned invalid JSON: %s", e)
        return []
    if not isinstance(topics, list):
        log.warning("topic extraction did not return a list")
        return []
    return topics


def load_prior_ledger(path: Path | None) -> list[dict]:
    """Load yesterday's (or any prior) ledger. Returns empty list if missing."""
    if path is None or not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("could not parse prior ledger %s: %s", path, e)
        return []


def _merge_topics(prior_topics: list[dict], new_topics: list[dict], today: str) -> list[dict]:
    indexed = {
        entry["topic_key"]: dict(entry)
        for entry in prior_topics
        if isinstance(entry, dict) and entry.get("topic_key")
    }
    for topic in new_topics:
        key = topic.get("topic_key") if isinstance(topic, dict) else None
        if not key:
            continue
        if key not in indexed:
            indexed[key] = {
                "topic_key": key,
                "first_covered": today,
                "last_covered": today,
                "summary": topic.get("summary", ""),
                "entities": [],
                "roadmap_areas": [],
            }
        entry = indexed[key]
        entry["last_covered"] = today
        entry["summary"] = topic.get("summary", entry.get("summary", ""))
        for field in ("entities", "roadmap_areas", "source_urls", "source_dates"):
            values = set(entry.get(field, []))
            values.update(value for value in topic.get(field, []) if value)
            if values or field in entry or field in topic:
                entry[field] = sorted(values)
    return sorted(
        indexed.values(),
        key=lambda entry: (entry.get("last_covered", ""), entry.get("topic_key", "")),
        reverse=True,
    )


def merge_and_prune(
    prior_ledger: list[dict], new_topics: list[dict], today: str,
    window_days: int = LEDGER_WINDOW_DAYS,
) -> list[dict]:
    """Merge today's topics and retain only the rolling context window.

    Merge rules:
      - If a topic_key in new_topics already exists in the prior ledger, update
        its last_covered to today and overwrite its summary with the new one
        (the new summary reflects the latest delta). Preserve first_covered.
      - If a topic_key in new_topics is not in the prior ledger, add it with
        first_covered = last_covered = today.
      - If a topic_key in the prior ledger is not in new_topics, leave it
        alone (its last_covered stays unchanged).

    Prune: drop any topic where last_covered is older than window_days.
    """
    today_dt = datetime.strptime(today, "%Y-%m-%d").date()
    cutoff = today_dt - timedelta(days=window_days)

    merged = _merge_topics(prior_ledger, new_topics, today)
    pruned = []
    dropped = 0
    for entry in merged:
        try:
            last = datetime.strptime(entry["last_covered"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            # Malformed entry; drop it
            dropped += 1
            continue
        if last >= cutoff:
            pruned.append(entry)
        else:
            dropped += 1


    log.info(
        "ledger merge: %d existing, %d new topics, %d dropped (older than %d days), %d total",
        len(prior_ledger), len(new_topics), dropped, window_days, len(pruned),
    )
    return pruned


def _registry_topics(value):
    if isinstance(value, dict) and value.get("schema_version") == 1 and isinstance(value.get("topics"), list):
        return [dict(topic) for topic in value["topics"]]
    if not isinstance(value, list):
        raise ValueError("durable event registry contract mismatch")
    topics = []
    for entry in value:
        if not isinstance(entry, dict) or not entry.get("topic_key"):
            continue
        event = {
            "covered_on": entry.get("last_covered") or entry.get("first_covered"),
            "summary": entry.get("summary", ""),
            "source_urls": sorted(set(entry.get("source_urls", []))),
            "source_dates": sorted(set(entry.get("source_dates", []))),
        }
        topics.append({
            "topic_key": entry["topic_key"],
            "first_covered": entry.get("first_covered", event["covered_on"]),
            "last_covered": entry.get("last_covered", event["covered_on"]),
            "entities": sorted(set(entry.get("entities", []))),
            "roadmap_areas": sorted(set(entry.get("roadmap_areas", []))),
            "events": [event],
        })
    return topics


def merge_durable_registry(prior_registry, new_topics: list[dict], today: str) -> dict:
    """Append covered event deltas without time-based pruning."""
    indexed = {topic["topic_key"]: topic for topic in _registry_topics(prior_registry)}
    source_owner = {}
    for key, topic in indexed.items():
        for event in topic.get("events", []):
            for url in event.get("source_urls", []):
                source_owner[url] = key
    for item in new_topics:
        if not isinstance(item, dict) or not item.get("topic_key"):
            continue
        urls = sorted(set(item.get("source_urls", [])))
        existing_keys = {source_owner[url] for url in urls if url in source_owner}
        key = sorted(existing_keys)[0] if len(existing_keys) == 1 else item["topic_key"]
        topic = indexed.setdefault(key, {
            "topic_key": key, "first_covered": today, "last_covered": today,
            "entities": [], "roadmap_areas": [], "events": [],
        })
        topic["first_covered"] = min(topic.get("first_covered") or today, today)
        topic["last_covered"] = max(topic.get("last_covered") or today, today)
        for field in ("entities", "roadmap_areas"):
            topic[field] = sorted(set(topic.get(field, [])) | set(item.get(field, [])))
        event = {
            "covered_on": today,
            "summary": item.get("summary", ""),
            "source_urls": urls,
            "source_dates": sorted(set(item.get("source_dates", []))),
        }
        identity = (
            event["covered_on"], " ".join(event["summary"].split()).casefold(),
            tuple(event["source_urls"]),
        )
        existing = {
            (
                prior.get("covered_on"), " ".join(prior.get("summary", "").split()).casefold(),
                tuple(sorted(prior.get("source_urls", []))),
            )
            for prior in topic.get("events", [])
        }
        if identity not in existing:
            topic.setdefault("events", []).append(event)
            topic["events"].sort(key=lambda value: (value.get("covered_on", ""), value.get("summary", "")))
        for url in urls:
            source_owner[url] = key
    topics = sorted(indexed.values(), key=lambda value: (value.get("last_covered", ""), value["topic_key"]), reverse=True)
    return {"schema_version": 1, "topics": topics}


def derive_recent_ledger(registry, today: str, window_days: int = LEDGER_WINDOW_DAYS) -> list[dict]:
    cutoff = datetime.strptime(today, "%Y-%m-%d").date() - timedelta(days=window_days)
    recent = []
    for topic in _registry_topics(registry):
        events = [
            event for event in topic.get("events", [])
            if event.get("covered_on") and datetime.strptime(event["covered_on"], "%Y-%m-%d").date() >= cutoff
        ]
        if not events:
            continue
        recent.append({
            "topic_key": topic["topic_key"],
            "first_covered": topic.get("first_covered"),
            "last_covered": max(event["covered_on"] for event in events),
            "summary": events[-1].get("summary", ""),
            "entities": topic.get("entities", []),
            "roadmap_areas": topic.get("roadmap_areas", []),
            "events": events,
        })
    return sorted(recent, key=lambda value: (value["last_covered"], value["topic_key"]), reverse=True)


def _write_json_atomic(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = path.with_name(path.name + ".tmp")
    candidate.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    candidate.replace(path)


@click.command()
@click.option("--brief-file", required=True, type=click.Path(path_type=Path))
@click.option("--prior-ledger", type=click.Path(path_type=Path), default=None,
              help="Path to yesterday's ledger.json. Optional; treated as empty if missing.")
@click.option("--ledger-out", required=True, type=click.Path(path_type=Path))
@click.option("--event-registry", type=click.Path(path_type=Path), default=None,
              help="Durable event registry path; retained indefinitely when supplied.")
@click.option("--today", default=None, help="ISO date for the merge. Defaults to UTC today.")
def main(
    brief_file: Path, prior_ledger: Path | None, ledger_out: Path,
    event_registry: Path | None, today: str | None,
) -> None:
    """Extract topics from today's brief, merge with prior ledger, prune old."""
    try:
        require_perplexity_api_key()
    except MissingProviderCredential as e:
        log.error(str(e))
        sys.exit(2)

    today_iso = today or date.today().isoformat()

    brief_text = brief_file.read_text(encoding="utf-8")
    log.info("Extracting topics from brief (%d chars)", len(brief_text))
    new_topics = extract_topics_from_brief(brief_text)
    log.info("Extracted %d topics from today's brief", len(new_topics))

    prior = load_prior_ledger(prior_ledger)
    log.info("Loaded %d prior ledger entries from %s", len(prior),
             prior_ledger if prior_ledger else "(no prior ledger)")

    if event_registry is not None and event_registry.exists():
        try:
            prior_events = json.loads(event_registry.read_text(encoding="utf-8"))
            _registry_topics(prior_events)
        except Exception as exc:
            raise click.ClickException(f"durable event registry is invalid: {exc}") from exc
    else:
        prior_events = prior
    durable = merge_durable_registry(prior_events, new_topics, today_iso)
    recent = derive_recent_ledger(durable, today_iso)
    _write_json_atomic(ledger_out, recent)
    log.info("Wrote ledger with %d entries to %s", len(recent), ledger_out)
    if event_registry is not None:
        _write_json_atomic(event_registry, durable)
        log.info("Wrote durable event registry with %d topics to %s", len(durable["topics"]), event_registry)


if __name__ == "__main__":
    main()
