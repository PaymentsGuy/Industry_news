#!/usr/bin/env python3
"""ASA daily intel pipeline.

Subcommands:
    collect     Pull RSS + EDGAR feeds into raw.jsonl
    triage      Run Stage 1 LLM triage on raw items
    synthesize  Run Stage 2 LLM synthesis into a daily brief
    publish     Post brief to Slack

Each step writes a deterministic artifact, so the full daily run is auditable
from `intel/<date>/raw.jsonl` -> `triaged.jsonl` -> `brief.md`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

import click
import feedparser
import requests
import yaml
from anthropic import Anthropic

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = REPO_ROOT / "intel" / "watchlist.yaml"
PROMPTS_DIR = REPO_ROOT / "intel" / "prompts"

# Model selection. Triage runs once per item (~50/day) so cost matters; Sonnet
# is the right balance of quality vs cost. Synthesis runs once per day and
# quality matters more than cost, so Opus.
TRIAGE_MODEL = "claude-sonnet-4-6"
SYNTHESIS_MODEL = "claude-opus-4-7"

TRIAGE_TEMP = 0.0          # deterministic classification
SYNTHESIS_TEMP = 0.3       # slight variation in prose, still controlled

TRIAGE_CONCURRENCY = 8     # parallel triage calls
TRIAGE_RELEVANCE_DROP = 2  # drop anything below this score
RSS_ITEMS_PER_FEED = 30    # cap per feed; older items are stale

DEFAULT_HTTP_TIMEOUT = 30
USER_AGENT = "asa-intel/0.1 (https://www.asavault.com)"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("asa-intel")


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """ASA daily intel pipeline."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def deterministic_id(source_url: str, title: str) -> str:
    """Stable 16-char ID for an item, used for dedupe and audit traces."""
    h = hashlib.sha256()
    h.update(source_url.encode("utf-8"))
    h.update(b"::")
    h.update(title.encode("utf-8"))
    return h.hexdigest()[:16]


def load_watchlist() -> dict:
    return yaml.safe_load(WATCHLIST_PATH.read_text())


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


def render_prompt(template: str, **vars: Any) -> str:
    """Simple {{var}} substitution. Avoids f-string conflicts with JSON braces."""
    out = template
    for key, val in vars.items():
        out = out.replace("{{" + key + "}}", str(val))
    return out


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def strip_code_fences(text: str) -> str:
    """LLMs sometimes wrap JSON/markdown in fences despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (and optional language hint)
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        # Remove closing fence
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


# ---------------------------------------------------------------------------
# COLLECT
# ---------------------------------------------------------------------------

def fetch_rss(url: str, source_name: str) -> tuple[list[dict], str | None]:
    """Fetch one RSS/Atom feed. Returns (items, error). Failures are logged
    but don't abort the run."""
    try:
        feed = feedparser.parse(
            url, request_headers={"User-Agent": USER_AGENT}
        )
        if feed.bozo and not feed.entries:
            return [], f"parse failure: {feed.bozo_exception}"
    except Exception as e:
        return [], f"exception: {e}"

    items: list[dict] = []
    for entry in feed.entries[:RSS_ITEMS_PER_FEED]:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        published = entry.get("published") or entry.get("updated") or ""
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        if not title or not link:
            continue
        items.append({
            "id": deterministic_id(link, title),
            "title": title,
            "source": source_name,
            "source_url": link,
            "published_date": published,
            "text": summary,
            "fetch_method": "rss",
        })
    return items, None


def fetch_edgar(cik: str, source_name: str) -> tuple[list[dict], str | None]:
    """SEC EDGAR Atom feed for a given CIK; surfaces 8-K filings."""
    cik_padded = str(cik).lstrip("0").zfill(10)
    url = (
        f"https://www.sec.gov/cgi-bin/browse-edgar?"
        f"action=getcompany&CIK={cik_padded}&type=8-K&dateb=&owner=include&count=10&output=atom"
    )
    return fetch_rss(url, f"{source_name} (SEC 8-K)")


@cli.command()
@click.option("--out-dir", required=True, type=click.Path(path_type=Path))
def collect(out_dir: Path) -> None:
    """Pull every feed in watchlist.yaml into raw.jsonl."""
    out_dir.mkdir(parents=True, exist_ok=True)
    watchlist = load_watchlist()

    raw: list[dict] = []
    errors: list[dict] = []
    seen_ids: set[str] = set()
    feeds: list[tuple[str, str, str]] = []  # (kind, source_name, url-or-cik)

    # Bucketed entities
    for entries in (watchlist.get("buckets") or {}).values():
        for e in entries or []:
            name = e["name"]
            for key in ("blog_rss", "pressroom_rss", "newsroom_rss"):
                if e.get(key):
                    feeds.append(("rss", f"{name} ({key.split('_')[0]})", e[key]))
            if e.get("sec_cik"):
                feeds.append(("edgar", name, e["sec_cik"]))

    # Trade press
    for entry in (watchlist.get("trade_press") or []):
        if entry.get("rss"):
            feeds.append(("rss", entry["name"], entry["rss"]))

    # Google Alerts (user-configured)
    for url in (watchlist.get("google_alerts") or []):
        feeds.append(("rss", "Google Alert", url))

    log.info("Pulling %d feeds", len(feeds))

    for kind, name, url_or_cik in feeds:
        if kind == "rss":
            items, err = fetch_rss(url_or_cik, name)
        elif kind == "edgar":
            items, err = fetch_edgar(url_or_cik, name)
        else:
            continue

        if err:
            errors.append({"source": name, "url": url_or_cik, "error": err})
            log.warning("feed error: %s -> %s", name, err)
            continue

        for it in items:
            if it["id"] in seen_ids:
                continue
            seen_ids.add(it["id"])
            raw.append(it)

        time.sleep(0.2)  # gentle backoff between feeds

    write_jsonl(out_dir / "raw.jsonl", raw)
    write_jsonl(out_dir / "collect_errors.jsonl", errors)
    log.info(
        "Collected %d items from %d feeds, %d errors -> %s",
        len(raw), len(feeds), len(errors), out_dir,
    )


# ---------------------------------------------------------------------------
# TRIAGE — Stage 1
# ---------------------------------------------------------------------------

def call_claude_triage(client: Anthropic, item: dict, watchlist_version: str) -> dict:
    """Single-item triage call. Always returns a dict; never raises.
    On failure returns a relevance_score=0 record so the item is dropped."""
    template = load_prompt("triage")
    prompt = render_prompt(
        template,
        title=item["title"],
        source=item["source"],
        source_url=item["source_url"],
        published_date=item.get("published_date", ""),
        full_text=item.get("text", ""),
        watchlist_version=watchlist_version,
        deterministic_id=item["id"],
    )

    try:
        response = client.messages.create(
            model=TRIAGE_MODEL,
            max_tokens=400,
            temperature=TRIAGE_TEMP,
            messages=[{"role": "user", "content": prompt}],
        )
        text = strip_code_fences(response.content[0].text)
        parsed = json.loads(text)
        # Carry the original item forward so synthesis has full context.
        parsed["_source_item"] = item
        return parsed
    except Exception as e:
        log.warning("triage failure for %s: %s", item.get("id"), e)
        return {
            "id": item["id"],
            "watchlist_bucket": "none",
            "watchlist_entity": None,
            "signal_type": "other",
            "roadmap_areas": [],
            "relevance_score": 0,
            "headline_paraphrase": item["title"][:140],
            "why_it_matters_for_asa": "[triage error - see logs]",
            "uncertainty_flags": ["triage_error"],
            "duplicate_of_id": None,
            "_source_item": item,
        }


@cli.command()
@click.option("--in-file",  required=True, type=click.Path(path_type=Path))
@click.option("--out-file", required=True, type=click.Path(path_type=Path))
def triage(in_file: Path, out_file: Path) -> None:
    """Run Stage 1 triage with concurrent LLM calls."""
    items = read_jsonl(in_file)
    watchlist = load_watchlist()
    version = watchlist.get("version", "0")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(2)
    client = Anthropic()

    log.info("Triaging %d items (concurrency=%d)", len(items), TRIAGE_CONCURRENCY)
    triaged: list[dict] = []
    with ThreadPoolExecutor(max_workers=TRIAGE_CONCURRENCY) as ex:
        futures = [ex.submit(call_claude_triage, client, it, version) for it in items]
        for fut in as_completed(futures):
            triaged.append(fut.result())

    # Sort: highest relevance first, then most recent.
    triaged.sort(
        key=lambda x: (
            int(x.get("relevance_score", 0) or 0),
            x.get("_source_item", {}).get("published_date", ""),
        ),
        reverse=True,
    )

    write_jsonl(out_file, triaged)
    surviving = [t for t in triaged if (t.get("relevance_score") or 0) >= TRIAGE_RELEVANCE_DROP]
    log.info(
        "Triage complete: %d items, %d survive (score >= %d)",
        len(triaged), len(surviving), TRIAGE_RELEVANCE_DROP,
    )


# ---------------------------------------------------------------------------
# SYNTHESIZE — Stage 2
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--in-file",  required=True, type=click.Path(path_type=Path))
@click.option("--out-file", required=True, type=click.Path(path_type=Path))
def synthesize(in_file: Path, out_file: Path) -> None:
    """Run Stage 2 synthesis to produce a markdown brief."""
    triaged = read_jsonl(in_file)
    surviving = [t for t in triaged if (t.get("relevance_score") or 0) >= TRIAGE_RELEVANCE_DROP]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(2)
    client = Anthropic()

    template = load_prompt("synthesis")
    today_iso = date.today().isoformat()
    prompt = render_prompt(
        template,
        today_iso=today_iso,
        items_reviewed_count=len(triaged),
        triaged_items_json=json.dumps(surviving, ensure_ascii=False, indent=2),
        yesterdays_summary_or_null="null",  # v2: load yesterday's brief
        rubric_version="0.1",
        synthesis_version="0.1",
    )

    log.info("Synthesizing brief from %d surviving items", len(surviving))
    response = client.messages.create(
        model=SYNTHESIS_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    brief = strip_code_fences(response.content[0].text)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(brief)
    log.info("Brief written to %s (%d chars)", out_file, len(brief))


# ---------------------------------------------------------------------------
# PUBLISH
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--brief-file", required=True, type=click.Path(path_type=Path))
@click.option("--dry-run", is_flag=True, default=False, help="Print to stdout instead of posting to Slack.")
def publish(brief_file: Path, dry_run: bool) -> None:
    """Post the brief to the Slack incoming webhook."""
    brief = brief_file.read_text()
    webhook = os.environ.get("SLACK_WEBHOOK_URL")

    if dry_run or not webhook:
        log.info("Dry run / no webhook; printing brief preview.")
        print(brief)
        return

    # Slack webhook accepts up to ~40k chars; our briefs are well under that.
    payload = {"text": brief, "mrkdwn": True}
    try:
        r = requests.post(webhook, json=payload, timeout=DEFAULT_HTTP_TIMEOUT)
        r.raise_for_status()
        log.info("Posted brief to Slack (%d chars)", len(brief))
    except Exception as e:
        log.error("Slack post failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    cli()
