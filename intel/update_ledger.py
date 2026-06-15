#!/usr/bin/env python3
"""Update the rolling 14-day topic ledger after a brief is synthesized.

This is invoked as a separate step in the workflow:
    python intel/update_ledger.py --brief-file intel/<date>/brief.md \
                                  --ledger-out intel/<date>/ledger.json \
                                  --prior-ledger intel/<prev-date>/ledger.json

The ledger is a small JSON file that tracks which topics have been covered in
the brief and when, so the synthesis step can dedupe-with-deltas on the next
day. Topics older than 14 days are pruned automatically.

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

LEDGER_WINDOW_DAYS = 14
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


def merge_and_prune(
    prior_ledger: list[dict],
    new_topics: list[dict],
    today: str,
    window_days: int = LEDGER_WINDOW_DAYS,
) -> list[dict]:
    """Merge today's topics into the prior ledger and prune anything older
    than the window.

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

    # Index prior ledger by topic_key for fast merge
    indexed = {entry["topic_key"]: entry for entry in prior_ledger if "topic_key" in entry}

    for topic in new_topics:
        key = topic.get("topic_key")
        if not key:
            continue
        if key in indexed:
            indexed[key]["last_covered"] = today
            indexed[key]["summary"] = topic.get("summary", indexed[key].get("summary", ""))
            # Merge entities and roadmap areas additively (a topic can grow
            # in scope over time)
            existing_ents = set(indexed[key].get("entities", []))
            for e in topic.get("entities", []):
                existing_ents.add(e)
            indexed[key]["entities"] = sorted(existing_ents)
            existing_areas = set(indexed[key].get("roadmap_areas", []))
            for a in topic.get("roadmap_areas", []):
                existing_areas.add(a)
            indexed[key]["roadmap_areas"] = sorted(existing_areas)
        else:
            indexed[key] = {
                "topic_key": key,
                "first_covered": today,
                "last_covered": today,
                "summary": topic.get("summary", ""),
                "entities": topic.get("entities", []),
                "roadmap_areas": topic.get("roadmap_areas", []),
            }

    # Prune old entries
    pruned = []
    dropped = 0
    for entry in indexed.values():
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

    pruned.sort(key=lambda e: (e.get("last_covered", ""), e.get("topic_key", "")), reverse=True)
    log.info(
        "ledger merge: %d existing, %d new topics, %d dropped (older than %d days), %d total",
        len(prior_ledger), len(new_topics), dropped, window_days, len(pruned),
    )
    return pruned


@click.command()
@click.option("--brief-file", required=True, type=click.Path(path_type=Path))
@click.option("--prior-ledger", type=click.Path(path_type=Path), default=None,
              help="Path to yesterday's ledger.json. Optional; treated as empty if missing.")
@click.option("--ledger-out", required=True, type=click.Path(path_type=Path))
@click.option("--today", default=None, help="ISO date for the merge. Defaults to UTC today.")
def main(brief_file: Path, prior_ledger: Path | None, ledger_out: Path, today: str | None) -> None:
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

    merged = merge_and_prune(prior, new_topics, today_iso)

    ledger_out.parent.mkdir(parents=True, exist_ok=True)
    ledger_out.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote ledger with %d entries to %s", len(merged), ledger_out)


if __name__ == "__main__":
    main()
