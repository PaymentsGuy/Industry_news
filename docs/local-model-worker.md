# Industry Pulse local model worker — activation runbook

## Ownership and security boundary

GitHub still reserves the report date, collects feeds, updates the topic ledger/event registry, creates the receipt-bound package, commits canonical outputs and delivers to Slack. The existing local scheduler/watchdog and Vault bridge remain unchanged. Weekly Radar remains on its existing Perplexity route.

The new Mac process only polls `PaymentsGuy/Industry_news`, main, `.github/workflows/daily-intel.yml`, `workflow_dispatch`, an in-progress run, and the single data-only request artifact. It never downloads or executes a script, workflow command or model prompt from GitHub. Local reviewed `intel/prompts/triage.md` calibration and `pipeline.synthesize_brief` build the prompts. Article content is untrusted evidence; there is no agent/tool dispatcher.

Model route: installed Hermes `resolve_provider_client('openai-codex', model=..., raw_codex=True)` plus its existing `CodexAuxiliaryClient`. Exact models are `gpt-6-luna` for one batch classification and `gpt-6.1-sol` for native synthesis. The endpoint must be `https://chatgpt.com/backend-api/codex`; SDK HTTP retries are disabled and no provider fallback is constructed. Tool schemas are explicitly empty, incomplete/tool-call responses are rejected, and the subprocess has a hard deadline. Do **not** substitute `hermes chat --toolsets ''`: the installed CLI interprets that as the default toolset.

The Hermes bootstrap discovery command is supported by the installed launcher. This integration intentionally depends on the observed native adapter interface; an incompatible Hermes update fails closed. Parent-owned tiny exact-model acceptance must exercise `hermes_completion`, not merely a CLI agent with a similar model flag.

## Before activation (parent/release owner only)

1. Independently review the local commit and run the tests below. Publish/merge only under the separately granted release authority. Both workflow changes must be present on **main** before the first real Pulse. The result-upload workflow cannot be dispatched until it exists there.
2. Provision a stable pinned worker release outside the bridge's live checkout and outside the scratch directory. Do not point launchd at this development worktree (scratch data can be pruned).
3. Verify `gh` is authenticated locally with Actions read and workflow-dispatch rights for the exact repository. No PAT, Codex token or OAuth secret is added to GitHub. Existing GitHub Slack credentials stay under the original owner. The repository is public: only public news and the existing public report ledgers may be included in requests/results.
4. Set `PULSE_HERMES_HOME` to the existing owner-authenticated `/Users/troymaas/.hermes/profiles/research_analyst` home. Parent native calls for both approved models succeeded there; an empty dedicated home had no OAuth credential. Reuse the owned native credential resolver without copying tokens or changing that profile's configuration. The helper constructs no agent, memory, MCP or tool dispatcher and rejects every endpoint except the ChatGPT subscription endpoint. No API-key fallback is constructed.
5. Exercise both exact models and a complete saved-input replay through the shipped helper, then verify installation and the loaded launchd job. Troy explicitly chose to preserve the November 23 failed attempt and begin with the next scheduled Pulse: do not clear its generation reservation or run catch-up. Actual unattended GitHub/result-artifact/delivery/Vault/COS acceptance remains pending that scheduled execution; diagnostic replay is not publication.

## Stable installation template

These are **activation instructions, not actions performed by the implementation worker**. Replace `REVIEWED_COMMIT` with the reviewed/promoted commit; never use an unreviewed moving branch.

```sh
BASE="$HOME/.local/share/asa-industry-news/model-worker"
mkdir -p "$BASE/state" "$BASE/state/tmp"
chmod 700 "$BASE/state" "$BASE/state/tmp"
git -C "$HOME/.local/share/asa-industry-news/repo" worktree add --detach "$BASE/release" REVIEWED_COMMIT
python3 -m venv "$BASE/venv"
"$BASE/venv/bin/python" -m pip install -r "$BASE/release/requirements.txt"
export PULSE_WORKER_STATE="$BASE/state"
export PULSE_HERMES_HOME="/Users/troymaas/.hermes/profiles/research_analyst"
export PULSE_PYTHON="$BASE/venv/bin/python"
# Existing OAuth is reused; no token is copied or placed in a command or GitHub.
```

Render `deploy/local-model-worker.plist.in` to `~/Library/LaunchAgents/com.asa.industry-news.model-worker.plist` with these exact substitutions, using XML escaping for paths:

| Placeholder | Value |
|---|---|
| `@RELEASE@` | `$BASE/release` |
| `@STATE@` | `$BASE/state` |
| `@HERMES_HOME@` | `/Users/troymaas/.hermes/profiles/research_analyst` |
| `@PYTHON@` | `$BASE/venv/bin/python` |

Then validate and activate only after the acceptance prerequisites above:

```sh
PLIST="$HOME/Library/LaunchAgents/com.asa.industry-news.model-worker.plist"
plutil -lint "$PLIST"
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl print "gui/$(id -u)/com.asa.industry-news.model-worker"
```

`RunAtLoad` starts polling immediately. Launchd polls every 30 seconds and does not overlap executions of this job. Do not manually start a competing poller. No existing scheduler/bridge plist is changed. The launcher uses `/bin/sh` explicitly, so executable file mode is not required.

## Normal path and bounds

1. Existing workflow commits its generation reservation, collects data, creates a request containing repository, run/attempt, source commit, canonical report date, 30-minute absolute deadline and SHA-256 of the complete request data.
2. `actions/upload-artifact@v4` publishes `pulse-request-RUN-ATTEMPT/request.json`. Original workflow waits at most 30 minutes.
3. Worker validates identity/hash/deadline, creates/fsyncs an exclusive durable run claim **before inference**, then classifies in fixed batches of at most 24 articles and performs native synthesis. Every candidate is retained exactly once; producer labels are derived using native duplicate → uncertainty → score precedence, while consumer validation remains strict. A completed, nonempty, otherwise valid partial batch gets at most one correction for **only missing IDs**; already completed IDs are never repeated. Empty/malformed responses fail immediately. Native contract-only synthesis regeneration remains bounded by the existing maximum of three candidates; transport timeouts/errors never auto-repeat ambiguous inference or proceed to later batches.
4. Worker validates coverage, schema, dispositions, references, report date/interval and all classification counts. A failure sends only safe producer-owned failure facts, never model/provider response text or rejected candidate diagnostics.
5. A locally reserved POST dispatches only `pulse-model-result.yml` on main. The reservation file and its containing directory are fsynced **before** the POST. Complete logical output is capped at 2 MB and transported losslessly as LZMA/base64 with an aggregate POST body below 60,000 UTF-8 bytes. Decoding caps output and memory and rejects corruption, truncation, trailing data or outer/inner identity mismatch. Oversized outputs fail safely rather than truncate signals or switch providers. Requests are capped at 2 MB; there is no candidate/material-signal count cap. Each model subprocess is at most 300 seconds and respects the remaining request deadline. Native HTTP timeout is 270 seconds.
6. The result workflow validates the envelope against the original exact request before uploading `pulse-result-RUN-ATTEMPT-HASH/result.json`. It has read-only repository/Actions permissions, no secrets and never interpolates input JSON into a shell command.
7. Original workflow retrieves that exact artifact from a successful main result workflow and validates it again. Only `triaged.jsonl`, `brief.md`, `synthesis-dispositions.json` (or safe `failure-status.json`) can be materialized. Existing ledger/delivery continues without accepting an arbitrary remote write payload. Request data is removed before canonical report commits. Request/result Actions artifacts expire after two days.

## Failure and reconciliation

- Offline Mac, unavailable OAuth/models, expired request, schema failure or transport limit: Pulse fails boundedly, produces the existing `failure-status.json` shape, and does **not** use paid Perplexity/OpenAI fallback. A timeout has a truthful Codex provider label. Existing legacy Perplexity receipts still validate.
- Claims are keyed by run ID, including across GitHub reruns. Changed hash/attempt under that ID is blocked. Completed results are cached, not regenerated. A hard interruption leaves `status=unknown`; the next poll emits safe failure rather than inferring again.
- Result submission is reserved before the POST. Lost POST acknowledgement leaves submission unknown and does not dispatch again automatically. The original workflow times out if no result is found. A successful dispatch HTTP response alone is not delivery proof: parent acceptance must verify the result-workflow artifact and original workflow readback.
- Do not delete claim/submission files, automatically rerun the GitHub job, or clear the publication reservation to recover an unknown outcome. Inspect the exact original run, result workflow/artifact, claim/hash and public delivery/package first. A deliberate new attempt requires owner-approved reconciliation under the existing publication guard; this worker adds no automatic reset command.
- Status schema compatibility is implemented in the producer's `failure_status.valid_receipt`. A separately installed consumer pinned to old producer code must receive the same reviewed producer release through its existing deployment owner before Codex receipts can be claimed accepted. No COS source was edited here.

To stop only this worker:

```sh
launchctl bootout "gui/$(id -u)/com.asa.industry-news.model-worker"
```

Preserve its state/claims across rollback. Do not restore the paid workflow as an automatic fallback; a rollback policy decision belongs to the release owner. Existing scheduler and Vault bridge continue independently.

## Tests

```sh
python -m pytest tests/test_local_model_worker.py tests/test_local_model_workflow.py -q
python -m pytest tests -q --ignore=tests/integration/test_intelligence_routing_chain.py
```

The excluded cross-repository integration module requires sibling COS, Action OS and MIOS checkouts; it cannot collect in the isolated single-repository layout. This limitation is separate from the fake-GitHub/native-pipeline integration coverage in the new tests. Full collection failure and scoped passing evidence are retained in the implementation report.
