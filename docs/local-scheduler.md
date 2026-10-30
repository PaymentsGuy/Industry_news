# Local Industry News scheduler and watchdog

## Ownership and limits

Two launchd user jobs share one standard-library Python engine. Primary requests
weekday delivery at **06:30 America/Los_Angeles**; watchdog runs every 300 seconds
and on load, eligible weekdays from **06:40 PT** until the end of that same date.
Both use explicit `ZoneInfo` gating, including DST. No weekend or previous-date
backfill. Calendar triggers use the Mac's local timezone; keep it on Pacific for
the 06:30 primary trigger. The interval watchdog still gates on Pacific if the
Mac timezone changes.

These are two triggers on **one Mac**, not independent-host redundancy. Sleep,
logout, shutdown, offline service, or a stopped user launchd domain can delay
execution. The next eligible watchdog tick catches up only today's date.

The scheduler does not use an LLM or gateway to decide or dispatch. It uses
`/opt/homebrew/bin/python3` and `/opt/homebrew/bin/gh`. Telegram notifications use
`/Users/troymaas/.local/bin/hermes --profile default send --to telegram MESSAGE`;
that transport must already be configured. There is no hard dollar cap here:
legacy `MAX_DAILY_COST_USD` is not enforced. Duplicate paid generation is blocked,
not ordinary authorized one-run generation spend.

The existing five-minute repository/Vault bridge remains the sole checkout and
Vault-write owner. This engine never switches, pulls, commits, pushes, archives,
or invokes that bridge. No root or Full Disk Access is required.

## Producer and recovery contracts

Repository: `PaymentsGuy/Industry_news`, ref `main`.

- Producer dispatch: `daily-intel.yml`, optional input `request_id`; exact run
  display title `Industry News Pulse REQUEST_UUID`. The producer commits
  `intel/YYYY-MM-DD/generation-attempt.json` **before any paid generation** and
  skips generation when a package exists. Keep this guard and the producer's
  shared daily-intel concurrency. A failed/ambiguous paid attempt needs human
  investigation, never automatic paid regeneration.
- Delivery-only dispatch: `reconcile-daily-slack.yml`, inputs `brief_date` and
  `request_id`; exact title `Industry News Delivery REQUEST_UUID`. Allowed only
  for today's hash-valid package with repository status `verified` and Slack
  status `pending`, `failed`, `attempting`, or `ambiguous_outcome`. This workflow
  must use native `resume-slack`: uncertain existing writes are reconciled, not
  blindly reposted. It must contain no paid generation. The existing workflow
  owns receipt commits, including failure/ambiguous outcomes.
- Never automate `recover-intel.yml`: it creates a weekly package and calls paid
  synthesis. Missing Vault receipts are left to the existing bridge.

Remote reads use explicit `repos/PaymentsGuy/Industry_news/...` API paths (`gh api`
does not accept `--repo`). Workflow dispatch uses explicit `--repo` and `--ref`.
Contents reads use `?ref=main`, first prove repository access, and accept absence
only on the exact contents API `404 Not Found` response with matching HTTP 404.
Authentication failures, unreadable JSON, malformed packages, incomplete run
pagination and unavailable APIs are **errors**, never “no package.” Run reads
use `gh api --paginate --slurp`; de-duplicate IDs and verify every page's declared
`total_count` against the collected count. A changing count fails closed until
the next tick.

## Durable state and dispatch safety

State root defaults to `~/.local/share/asa-industry-news/scheduler-state`.
A shared nonblocking `flock` on `scheduler.lock` covers the whole callback.
Overlapping primary/watchdog callbacks return `locked` without external writes.
Daily `YYYY-MM-DD.json` records stage/timestamps, retained last error, reservations,
API-attempt counts, run IDs, alert/recovery acknowledgements and COS operations.
Writes use a same-directory atomic replacement plus file and directory fsync.
The JSON is the durable state; stdout is only an observation.

Before a producer dispatch, persist a UUID `request_id`, `dispatch_attempts` and
an ambiguous outcome. Delivery uses separate `delivery_request_id`,
`delivery_dispatch_attempts`, `delivery_dispatch_outcome` and `delivery_run_id`.
On every later tick, reconcile all workflow pages against the **exact** display
title before considering another request. A transport error, timeout, process
crash, or lost response cannot authorize a second dispatch. An accepted request
remains `dispatch_wait` until a run/package is actually read back; it is not a
verified publication. Active runs wait; completed same-date runs without the
expected receipt/package require human recovery, including successful no-ops.
A run still active from an earlier date also blocks a competing request.

Only explicit HTTP 400/401/403/404/405/422/429 rejections permit one retry, using
the same reserved UUID, for **at most two API attempts per lane/date**. HTTP 5xx,
network errors and nonzero transport outcomes are ambiguous. At most one
accepted/uncertain producer request and one accepted/uncertain delivery-only
recovery are issued per date. Remote generation markers independently prevent a
fresh local process/state from regenerating an already attempted paid package.
A date rollover during prerequisite reads is checked again before dispatch.

Do not delete state to “retry.” Invalid state fails closed without overwriting
reservations. A separate `YYYY-MM-DD.state-error.json` stores state-load errors
and notification acknowledgements; after explicit human repair, its alert marker
is inherited for one recovery notification. If the state directory itself cannot
be read/written, durable notification deduplication cannot be guaranteed; repair
permissions/disk space and inspect the launchd logs.

## Completion and COS readback

`complete` requires all of:

1. Remote package has exact date, `industry-pulse-YYYY-MM-DD`, producer
   `industry_news`, cadence `weekday_daily`, a nonempty transaction identity,
   canonical LF/newline body and matching SHA-256.
2. Remote `status` is `fully_delivered` and repository, Slack and Vault statuses
   are all `verified`.
3. Local `intel/YYYY-MM-DD/vault-receipt.json` equals the remote Vault receipt
   (apart from the destination status wrapper). Validate destination/readback,
   transaction, pulse ID, canonical content hash, exact destination path, HMAC
   signature and actual Vault file SHA-256/body. The key is captured privately
   with `/usr/bin/security find-generic-password -w -s
   ai.hermes.asa-industry-news.vault-receipt`; it is never printed or persisted.
   Default Vault root matches `scripts/run_local_vault_bridge`:
   `~/Documents/Documents - Troy’s MacBook Air/Main local Vault`.
4. `GET http://127.0.0.1:4173/api/v3/command-brief` has the exact
   `industry_news.daily.pulse_id`, daily freshness `current`, and the
   `industry_news` source row has status `current`. The unique dated pulse plus
   verified native signed package is the identity contract; no COS hash or
   transaction-schema extension is required.

When this package is verified but COS is stale, request `POST /api/refresh` with
`{"source_id":"industry_news"}`, matching `Origin`, `X-Chief-Of-Staff-Token`
read privately from the local page's `chief-of-staff-token` meta tag, and a durable
`Idempotency-Key`. **The current COS server treats source_id as metadata and may
read all registered adapters; this is not source-isolated execution.** This uses
the existing endpoint without changing its contract; never request an unscoped
whole-refresh or restart services. Do not claim unrelated adapters were skipped.

Allow at most **three POST attempts per date**, reserving the counter before
sending. A lost response retains the same idempotency key for a bounded retry.
When an operation ID is known, poll `GET /api/refresh/ID`; queued/running work is
left alone. On the next tick, independently read the exact pulse/source identity;
POST acceptance or an operation's success alone is not completion. Continued
wrong identity, missing token or exhausted attempts becomes an error/human alert.

## Alerts

Waiting work that is still incomplete at **07:00 PT** triggers a daily failure
alert on the next eligible tick. Terminal failures, invalid evidence and API
errors alert immediately. Persist `alert_sent_at` only after the Hermes send
subprocess exits zero; failed sends remain retryable. Send one recovery message
only after full package/Vault/COS readback, recording `recovery_sent_at` only on
success. This is durable callback-level deduplication, not an exactly-once
Telegram guarantee across a crash after delivery but before acknowledgement.

## Read-only inspection and tests

```sh
scripts/run_local_scheduler inspect
scripts/run_local_scheduler --help
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3 -m unittest discover \
  -s tests -p test_local_scheduler.py -v
```

`inspect` reads today's remote package/marker and both workflow run lists; for a
complete remote package it also verifies the native local Vault receipt and COS
identity. It creates no lock/state, sends no alerts, dispatches nothing, and never
refreshes COS. It returns JSON. Normal waits/no-ops exit zero; errors and
`human_recovery` exit one. Inspection success means the read completed; use
`package_complete`, `local_vault_verified`, and `cos_current` to assess readiness.

Fixture seams: `Engine(state_root, gateway, clock=...)`,
`main(argv, gateway=..., clock=...)`, and `NativeGateway(..., run=...)`.
Tests use disposable paths under the process `TMPDIR`, fake subprocesses/a
real disposable fake-gh executable, and a loopback HTTP fixture. They never
invoke production gh, Keychain, Hermes, COS, the Vault bridge or paid generation.
No project virtualenv is required for the standard-library test suite.

## Deployment handoff (not performed by implementation tests)

Files under `deploy/` are templates, not installed jobs. Wrapper is executable;
primary plist has five weekday 06:30 calendar entries, watchdog has
`StartInterval=300` and `RunAtLoad=true`. Both call the same wrapper with distinct
roles, explicit Troy paths/HOME/PATH and separate log files under `~/Library/Logs`.
There is no KeepAlive loop.

Before separately authorized activation: verify the deployed producer guard and
delivery-only workflow contracts, authenticated gh read/dispatch authority,
Pacific Mac timezone, readable Vault/Keychain receipt, COS local token and API,
configured Telegram home destination and writable state/log directories. Resume
the existing bridge through its owner. Run read-only `inspect`, install/bootstrap
the two user launch agents through the approved deployment owner, then verify
loaded paths and later dispatch/run/package readbacks independently. Installing
templates does not prove loaded execution or end-to-end delivery. No commit,
push, installation, activation or live workflow dispatch is part of these tests.
