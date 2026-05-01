# ASA Daily Competitive Intelligence Pipeline

Automated daily pull of competitor, channel-partner, regulatory, and technology signal for ASA Technologies. Runs at 5:00 AM Pacific, produces a one-page executive brief by 8:00 AM, posts to Slack, and commits the full audit trail to this repo.

## What it does

1. **Collect** — pulls RSS feeds for every entity in `intel/watchlist.yaml`, plus SEC EDGAR filings for public competitors.
2. **Triage** — calls Claude once per raw item with the Stage 1 rubric prompt; drops anything scoring below 2.
3. **Synthesize** — calls Claude once with the surviving items and produces a markdown brief in the canonical format.
4. **Publish** — posts the brief to Slack (`#daily-intel`) and commits raw items + triage scores + final brief to `intel/<date>/`.

## Repo structure

```
.
├── .github/
│   └── workflows/
│       └── daily-intel.yml          # GitHub Actions scheduler
├── intel/
│   ├── watchlist.yaml               # source of truth for what to track
│   ├── pipeline.py                  # CLI: collect | triage | synthesize | publish
│   ├── prompts/
│   │   ├── triage.md                # Stage 1 prompt (canonical)
│   │   └── synthesis.md             # Stage 2 prompt (canonical)
│   └── 2026-04-29/                  # one folder per run
│       ├── raw.jsonl                # everything pulled
│       ├── triaged.jsonl            # everything scored
│       └── brief.md                 # the published output
├── requirements.txt
└── README.md
```

## One-time setup

1. **Create the repo and copy these files in.** Push to GitHub.

2. **Set repository secrets** (Settings → Secrets and variables → Actions):
   - `ANTHROPIC_API_KEY` — your Claude API key
   - `SLACK_WEBHOOK_URL` — incoming webhook for `#daily-intel`

3. **Verify watchlist URLs.** The seed `watchlist.yaml` has reasonable RSS guesses but URLs change. Run locally once to confirm:
   ```bash
   pip install -r requirements.txt
   python intel/pipeline.py collect --out-dir intel/$(date +%F)
   ```
   Inspect `intel/<date>/raw.jsonl` and the `collect_errors` log. Fix any feeds that 404'd in `watchlist.yaml`.

4. **Set up Google Alerts.** In your personal Google Alerts UI, create alerts for: each direct competitor name, "Section 1033", "embedded finance bank", "agentic AI banking", plus your own watchlist additions. For each, set delivery to "RSS feed" and copy the feed URL into the `google_alerts:` section of `watchlist.yaml`.

5. **Test end-to-end locally:**
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   export SLACK_WEBHOOK_URL=https://hooks.slack.com/...   # optional for dry run
   DATE=$(date +%F)
   python intel/pipeline.py collect    --out-dir intel/$DATE
   python intel/pipeline.py triage     --in-file intel/$DATE/raw.jsonl --out-file intel/$DATE/triaged.jsonl
   python intel/pipeline.py synthesize --in-file intel/$DATE/triaged.jsonl --out-file intel/$DATE/brief.md
   python intel/pipeline.py publish    --brief-file intel/$DATE/brief.md  # add --dry-run to skip Slack
   ```

6. **Enable the workflow.** Once the dry run looks right, enable `.github/workflows/daily-intel.yml`. It runs daily at 12:00 UTC (5 AM PT) and on manual `workflow_dispatch`.

## Daily ops

- The brief lands in `#daily-intel` around 8 AM PT. Reading time: 90 seconds.
- Anything tagged "Decision needed by [date]" goes on your action list immediately. Everything else is reading.
- Once a week, glance at the `intel/<date>/triaged.jsonl` files — look for score-3 items the brief de-emphasized, or score-1 items that should have been higher. That's how you tune the rubric.
- Once a month, edit `watchlist.yaml`. Markets shift; entities die or get acquired. The watchlist is a living document.
- Once a quarter, review `intel/prompts/triage.md` and `synthesis.md`. Treat any change as a code change — PR, review, ship.

## Cost ceiling

At ~50 items/day with Claude Sonnet pricing, this runs roughly **$0.50–$1.00/day**. The workflow has a hard `MAX_DAILY_COST_USD=3` env var; if exceeded, it fails loudly. That usually means a runaway feed or a misconfigured retry loop, not legitimate volume.

## Failure modes & monitoring

- **Workflow failed** — GitHub emails the repo admins. Almost always either an API key issue or a rate limit.
- **Brief posted but feels wrong** — check `intel/<date>/triaged.jsonl` for inflated scores or missing watchlist matches. Fix the rubric, not the brief.
- **Watchlist feed silently 404'd** — `pipeline.py collect` writes a `collect_errors.jsonl` next to `raw.jsonl`. The Slack post includes a one-line summary of feed errors so you notice.

## v2 backlog (deliberately out of scope for v1)

- LinkedIn company page monitoring (no clean API; needs Phantombuster or paid tool)
- X/Twitter list monitoring (API access tier required)
- Podcast transcript ingestion (Whisper + episode filter)
- App store changelog scraping (AppFollow or Sensor Tower)
- Job posting deltas per careers page (per-site scrapers)
- Patent filings (USPTO PatentsView, weekly cadence)
- Per-area Slack threads instead of one channel post
- Human-in-the-loop approval before publish (sign-off button)

## Operating principles (don't compromise)

1. Every claim in the brief traces to a `[REF n]`. No exceptions.
2. The brief is one page. Length is a bug, not a feature.
3. Silence in a roadmap area is data. Don't pad.
4. The watchlist and prompts are versioned alongside this code.
