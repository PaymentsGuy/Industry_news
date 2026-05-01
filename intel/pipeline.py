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

TRIAGE_CONCURRENCY = 3     # parallel triage calls
TRIAGE_RELEVANCE_DROP = 2  # drop anything below this score
RSS_ITEMS_PER_FEED = 10    # cap per feed; older items are stale

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
    """Single-item triage call with prompt caching on the static rubric.

    The triage prompt is split into:
      - A cacheable preamble (rubric, watchlist, output schema) that is identical
        for every item in the run. Marked with cache_control=ephemeral so the
        Anthropic API caches it for 5 minutes.
      - A per-item suffix containing only the title/url/text being classified.

    On a typical run of ~80 items, this means 1 cache write + ~79 cache hits,
    which cuts triage input cost by roughly 90%.

    On failure returns a relevance_score=0 record so the item is dropped.
    """
    template = load_prompt("triage")

    # Render the full prompt with all variables substituted.
    full_prompt = render_prompt(
        template,
        title=item["title"],
        source=item["source"],
        source_url=item["source_url"],
        published_date=item.get("published_date", ""),
        full_text=item.get("text", ""),
        watchlist_version=watchlist_version,
        deterministic_id=item["id"],
    )

    # Split the prompt at the INPUT ITEM marker so we can cache everything
    # before it (rubric, watchlist, schema) and send only the item data fresh.
    # The triage.md prompt has "INPUT ITEM:" as a stable section header.
    split_marker = "INPUT ITEM:"
    if split_marker in full_prompt:
        before, after = full_prompt.split(split_marker, 1)
        cacheable_part = before.rstrip()
        per_item_part = split_marker + after
    else:
        # Fallback: prompt structure changed, send uncached
        cacheable_part = ""
        per_item_part = full_prompt

    # Build the message content. The cacheable block gets cache_control;
    # the per-item block does not.
    if cacheable_part:
        content = [
            {
                "type": "text",
                "text": cacheable_part,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": per_item_part,
            },
        ]
    else:
        content = [{"type": "text", "text": per_item_part}]

    try:
        response = client.messages.create(
            model=TRIAGE_MODEL,
            max_tokens=400,
            temperature=TRIAGE_TEMP,
            messages=[{"role": "user", "content": content}],
        )
        text = strip_code_fences(response.content[0].text)
        parsed = json.loads(text)
        parsed["_source_item"] = item
        # Surface cache stats in the audit trail so we can verify caching is
        # actually working in production.
        usage = getattr(response, "usage", None)
        if usage is not None:
            parsed["_cache_stats"] = {
                "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
                "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
                "input_tokens": getattr(usage, "input_tokens", 0) or 0,
                "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            }
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
@click.option("--prior-ledger", type=click.Path(path_type=Path), default=None,
              help="Path to yesterday's ledger.json. If missing or empty, "
                   "synthesis runs without the dedup filter (every item is fresh).")
def synthesize(in_file: Path, out_file: Path, prior_ledger: Path | None) -> None:
    """Run Stage 2 synthesis to produce a markdown brief.

    If --prior-ledger is supplied and exists, its contents are passed to the
    synthesis prompt so the model can dedupe today's items against topics
    already covered in the last 14 days.
    """
    triaged = read_jsonl(in_file)
    surviving = [t for t in triaged if (t.get("relevance_score") or 0) >= TRIAGE_RELEVANCE_DROP]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(2)
    client = Anthropic()

    # Load the prior topic ledger if it exists. On the first run after this
    # feature ships, no ledger will exist — that's fine, the prompt handles
    # the empty-array case explicitly.
    ledger: list[dict] = []
    if prior_ledger and Path(prior_ledger).exists():
        try:
            ledger = json.loads(Path(prior_ledger).read_text(encoding="utf-8"))
            log.info("Loaded prior ledger with %d entries from %s", len(ledger), prior_ledger)
        except Exception as e:
            log.warning("Could not parse prior ledger %s: %s — proceeding without dedup", prior_ledger, e)
    else:
        log.info("No prior ledger provided; synthesis will treat all items as fresh")

    template = load_prompt("synthesis")
    today_iso = date.today().isoformat()
    prompt = render_prompt(
        template,
        today_iso=today_iso,
        items_reviewed_count=len(triaged),
        triaged_items_json=json.dumps(surviving, ensure_ascii=False, indent=2),
        topic_ledger_json=json.dumps(ledger, ensure_ascii=False, indent=2),
        rubric_version="0.2",
        synthesis_version="0.3",
    )

    log.info("Synthesizing brief from %d surviving items (ledger has %d topics)",
             len(surviving), len(ledger))
    response = client.messages.create(
        model=SYNTHESIS_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    brief = strip_code_fences(response.content[0].text)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(brief, encoding="utf-8")
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
