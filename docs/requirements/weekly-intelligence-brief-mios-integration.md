# ASA Intelligence Brief → MIOS Integration Requirements

Status: requirements complete; implementation not authorized
Updated: 2026-08-20
Governing MIOS definition: `10-Projects/MIOS/MIOS Definition Interview.md`

## Objective

Preserve every historical ASA Intelligence Brief in the Obsidian Vault, ingest the briefs into MIOS in chronological order with Troy-controlled release and acceptance, and update future brief delivery so each new brief is sent to both Slack and the Vault. A verified Vault-create event queues the brief for MIOS ingestion.

This document defines requirements and acceptance behavior. It does not authorize code changes, workflow changes, source ingestion, migration, deployment, Slack writes, or MIOS writes.

## Current-state evidence

- Current Slack destination: `#troy-research`, channel ID `C0B1TPFSZKJ`.
- The Industry_news repository currently contains 40 dated `brief.md` artifacts:
  - 39 daily predecessor briefs dated 2026-05-01 through 2026-06-08.
  - One weekly brief dated 2026-06-15.
- The most recent 100 Slack messages expose four messages with Weekly Intelligence Brief headers:
  - Two distinct 2026-06-15 messages with different hashes and headlines.
  - 2026-08-10.
  - 2026-08-17.
- The recent-message API window does not prove the complete Slack history. Full historical inventory requires pagination, export, or another verified complete-history path.
- The GitHub-hosted workflow can commit repository artifacts and post to Slack, but it cannot directly write Troy's local Obsidian Vault without a separately designed and verified bridge or a runner with Vault access.

## Canonical Vault archive

### Location

`Atlas/competitive-intel/intelligence-briefs/`

### Filename

`YYYY-MM-DD - ASA Intelligence Brief.md`

The date is the brief's declared issue date:

1. Weekly header: `Week of YYYY-MM-DD`.
2. Daily predecessor header: `YYYY-MM-DD`.
3. If the header is missing or malformed, the record is blocked for manual date resolution; Slack timestamp is evidence, not an automatic replacement for the declared brief date.

### Required frontmatter

```yaml
brief_id: asa-intelligence-brief-YYYY-MM-DD # add -<sha8> only for accepted same-date variants
brief_date: YYYY-MM-DD
cadence: daily_predecessor | weekly
producer: industry_news | mios
source_repository_path: optional
source_slack_channel_id: C0B1TPFSZKJ
source_slack_message_ts: optional
source_slack_permalink: optional
content_sha256: <sha256>
producer_receipt_id: <trusted receipt identity>
archived_at: <timestamp>
mios_ingestion_receipt_id: optional
```

The Markdown body preserves the exact brief content. Provenance metadata may be added without rewriting the brief's claims. MIOS lifecycle state is owned only by the MIOS structured store; Vault frontmatter may carry an optional receipt link/projection but never authoritative ingestion status.

Date conflicts must never overwrite one another. Before Troy resolves a same-date conflict, variants are retained under `Atlas/competitive-intel/intelligence-briefs/_conflicts/YYYY-MM-DD/` using `<slack-ts-or-source-id>-<sha256-prefix>.md`. Troy selects one canonical brief for that date or explicitly accepts multiple same-date versions. If multiple variants are accepted, each `brief_id` and canonical filename adds the same stable short hash suffix. Same-date processing order is source timestamp ascending, then content hash ascending; no variant may overwrite another.

### Canonical payload and hashes

- Canonical brief payload means the brief body only, encoded UTF-8, normalized to LF line endings, with exactly one trailing newline and no Vault frontmatter.
- `content_sha256` hashes those canonical body bytes.
- `vault_file_sha256` hashes the complete Vault file including frontmatter and body, but is stored only in the external delivery receipt/sidecar—not inside the file it hashes—so the contract is non-circular.
- Repository, Slack, and Vault receipts all bind to the same `content_sha256` even though container bytes differ.
- Slack mrkdwn transformations, multipart messages, threads, or file attachments must be reconstructed in deterministic message-part order, converted back to canonical body bytes, and compared by `content_sha256` before delivery or historical reconciliation is accepted.

## Historical inventory and reconciliation

Before ingesting any brief:

1. Freeze a manifest boundary with `manifest_cutoff_at`, exact repository commit SHA, Slack channel ID, and retrieval method/version.
2. Build a manifest from all repository `brief.md` files at that exact commit.
3. Retrieve complete Slack channel history through a verified paginated/export path until the channel-history boundary is reached.
4. Record retrieval cursors/pages, oldest and newest message timestamps, edited/deleted-message evidence available from the source, multipart/thread/file reconstruction, and a closure receipt proving the retrieval did not stop at an arbitrary recent-message window.
5. Identify every Daily and Weekly Intelligence Brief by declared date, Slack message timestamp, producer, and canonical content hash.
6. Reconcile repository and Slack copies:
   - Exact hash match: one brief identity with multiple source locations.
   - Same date, different hash: retain both as a conflict set requiring Troy's manual selection or explicit multi-version acceptance.
   - Slack-only: archive exact Slack content to the Vault.
   - Repository-only: archive the repository artifact and record Slack delivery as unavailable/unverified.
7. Do not silently deduplicate the two observed June 15 messages; their content and headlines differ.
8. Produce exact counts for discovered, matched, Slack-only, repository-only, conflicted, reconstructed multipart, edited/deleted, and blocked records.
9. Troy reviews and accepts the immutable manifest hash and closure receipt before the first MIOS ingestion release.

## Oldest-first controlled ingestion

1. Sort the accepted manifest by declared brief date ascending.
2. Only one brief may be active in the MIOS ingestion/acceptance process at a time.
3. Begin with the oldest accepted brief.
4. Before release, show:
   - Brief identity, date, cadence, hash, and exact Vault path.
   - Source locations and reconciliation status.
   - Expected MIOS operation and no-unrelated-writes statement.
5. Troy manually releases that one brief.
6. MIOS performs extraction and reconciliation in an isolated candidate transaction/workspace. It must not mutate the accepted authoritative signal state before Troy's acceptance.
7. The candidate transaction extracts atomic signals, reconciles stable identities, appends evidence, versions material changes, ranks decision candidates, and renders the acceptance cockpit.
8. MIOS stops at `awaiting_troy_acceptance`.
9. Troy reviews alongside automated QA:
   - Extracted signals and omitted/noise sections.
   - Evidence links and exact brief provenance.
   - Provisional versus verified status.
   - ASA implications and explainable ranking.
   - Reconciliation with previously accepted signals.
   - New versions, supersessions, and preserved history.
   - Cockpit usefulness and counts.
10. Automated QA records a pass/fail verdict bound to the immutable brief identity/hash and candidate-result hash.
11. Troy chooses accept, reject, or rework against that same immutable candidate.
12. The composite acceptance gate passes only when automated QA is `pass` and Troy is `accept` for the same hashes.
13. Only the composite gate may atomically promote the candidate transaction and record before/after counts, changed signal IDs, versions, and receipt hashes.
14. Reject, rework, or QA failure leaves the accepted authoritative signal state unchanged, preserves the candidate/QA evidence, and keeps the next brief blocked.
15. Rework retries reuse the same brief identity and increment a candidate-attempt number; they never create a second active brief.
16. A single-owner lock and unique active-candidate constraint prevent a second brief from entering `released`, `processing`, or `awaiting_troy_acceptance` while one is active.
17. Only a promoted composite acceptance unlocks manual release of the next newer brief.
18. Continue one brief at a time until the accepted manifest is current.

## Replay and update behavior

- Releasing the same brief identity/hash again is idempotent and creates no duplicate signals, evidence, decisions, or receipts.
- A different hash for an already accepted date is a proposed new brief version and requires manual approval.
- Repeated signals append evidence to one stable signal identity.
- A new signal version is created only when material facts, meaning, or ASA implication changes.
- Prior evidence, interpretations, decisions, monitoring triggers, and output receipts remain available.

## Future dual delivery

For every future ASA Intelligence Brief, whether produced by Industry_news during transition or by MIOS later:

1. Generate the canonical repository artifact.
2. Deliver the exact brief to Slack `#troy-research`.
3. Deliver the exact brief to the Vault archive path using the naming/frontmatter contract above.
4. Verify both destinations independently.
5. Persist one delivery transaction identity plus durable per-destination receipts for repository/output artifact, Slack, and Vault. Each receipt binds brief ID, canonical content hash, destination identity, attempt number, and readback.
6. Record repository hash, Vault file hash, Slack channel/message timestamp/permalink, and delivery status.
7. A run is fully delivered only when the canonical repository/output artifact is durable and both Slack and Vault readback pass for the same transaction/hash.
8. One destination succeeding while the other fails is `partial_delivery`; the successful receipt remains durable and retry targets only missing/failed destinations using the same delivery identity.
9. A partial-delivery Vault-created queue record remains blocked and cannot become ingestion-ready until receipt reconciliation passes or Troy accepts a historical exception.
10. The current GitHub-hosted runner must not pretend it wrote the local Vault. Architecture must choose a verified bridge, synchronization consumer, or runner with approved Vault access.

## Vault-created trigger

After a new brief is atomically written and read back from the Vault, emit or expose a MIOS ingestion event with:

```json
{
  "event_type": "mios.brief.created",
  "brief_id": "asa-intelligence-brief-YYYY-MM-DD",
  "brief_date": "YYYY-MM-DD",
  "cadence": "weekly",
  "vault_path": "Atlas/competitive-intel/intelligence-briefs/YYYY-MM-DD - ASA Intelligence Brief.md",
  "content_sha256": "...",
  "producer": "industry_news",
  "producer_receipt_id": "...",
  "delivery_transaction_id": "...",
  "source_slack_channel_id": "C0B1TPFSZKJ",
  "source_slack_message_ts": "...",
  "event_id": "mios-brief-created-<sha256>",
  "idempotency_key": "<brief-id>|<content-sha256>|<producer-receipt-id>",
  "created_at": "..."
}
```

Trigger requirements:

- Emit only after atomic Vault write and hash readback.
- Compute `event_id` deterministically from brief ID, canonical content hash, Vault path, producer receipt, and delivery transaction. Stable event identity prevents duplicate queue entries.
- Producer authority comes from a trusted immutable producer/delivery receipt, not editable Vault frontmatter alone.
- Replayed identical events are idempotent; changed files, conflicting hashes, forged producer identity, missing receipts, or reused IDs with different payloads fail closed and require reconciliation.
- During historical catch-up and until Troy changes the policy, the trigger creates a pending ingestion record; it does not bypass manual release.
- A pending record is not eligible for release until the canonical artifact and both Slack/Vault delivery receipts reconcile successfully, unless Troy explicitly accepts a historical repository-only or Slack-only exception during manifest review.
- If `producer: mios`, the event is output lineage only and must not be re-ingested, preventing a feedback loop.
- Unknown producer identity, missing hash, malformed date, or missing Vault path fails closed.

## MIOS Release 1 acceptance extension

Release 1 must complete the historical catch-up with real briefs. The first two briefs prove the vertical-slice behavior, but that proof alone does not complete Release 1:

1. Manifest accepted by Troy.
2. Oldest brief archived to the canonical Vault path.
3. Manual release ingests only that brief.
4. Source-to-screen signal extraction and ranking pass automated QA and Troy acceptance.
5. Same-brief replay is idempotent.
6. Next brief changes the living signal picture without duplicates or lost history.
7. At least one signal shows appended evidence and, when warranted, material-change versioning.
8. Decision/monitoring capture persists across restart.
9. No downstream action is automatically created.
10. Catch-up state and next eligible brief are visible and exact.
11. Every brief in Troy's accepted frozen manifest passes the composite automated-QA + Troy-acceptance gate in oldest-first order.
12. Final accepted state is current through the manifest cutoff, with zero unreconciled eligible briefs, zero duplicate identities/evidence/decisions, and an exact completion receipt.
13. Release 1 is not accepted—and the predecessor MIOS is not eligible for retirement—until the entire accepted manifest is current.

## Deferred implementation choices

The architecture/implementation plan, when separately authorized, must decide:

- Complete Slack-history retrieval mechanism.
- GitHub-to-Vault delivery bridge or runner model.
- Filesystem event watcher versus explicit delivery webhook/event queue.
- MIOS structured-store engine.
- Backup, rollback, and recovery procedures.

No choice above is authorized by this requirements update.
