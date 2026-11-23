# Industry Pulse subscription-backed local worker — implementation report

## Delivery state

**Implemented and locally tested; not deployed, pushed, activated or real-generated.** The parent owns independent review, exact-runtime/OAuth/model acceptance, source release, stable installation and the real Pulse/delivery/COS readbacks.

- Isolated branch: `feat/pulse-local-codex`.
- Base: `8221cb7dbc770dd20d7d7c2ad481d18914289a2c` (clean live source observed before worktree creation).
- Worktree: `pulse-codex-migration` under the active research_analyst scratch directory. Do not install from scratch; it is subject to pruning.
- Local commit identity: obtain with `git rev-parse HEAD` after the local-only implementation commit; returned separately in the handoff. No source push/main promotion is part of this report.

## authorized_scope

Move daily Industry Pulse classification/synthesis off paid API calls onto the always-on Mac's subscription-backed Hermes Codex runtime. Keep GitHub collection, canonical report/date/interval, generation reservation, topic ledger/event registry, receipt-bound delivery/publication and existing local scheduler/watchdog/Vault bridge. Restrict the worker to one repository/main workflow/job and fixed data-only requests. Preserve failure-status consumer compatibility. Exact models are `gpt-6-luna` and `gpt-6.1-sol`; no paid fallback.

## explicit_non_goals

No deployment, GitHub writes/push, real model generation, production recovery, COS source changes, Hermes/default-profile changes, scheduler/watchdog/Vault replacement, public listener, generic job engine, self-hosted arbitrary-code runner, command execution from artifacts, remote prompt execution, new credential distribution or weekly Radar migration.

## material_assumptions

- Local `gh` authorization can read repository Actions and dispatch only the fixed result workflow operationally. The application is hard-coded to the approved endpoints; the underlying GitHub credential may have broader existing rights and is not a new security principal.
- Both workflows are released on main before activation. GitHub workflow_dispatch cannot invoke a workflow absent from the default branch.
- The repository is public (parent discovery); request/result content is public-news evidence plus already-public ledgers, not personal notes/configuration/authentication material.
- A dedicated Hermes OAuth home has no manual API-key fallback or custom endpoint. No `.env` or external profile configuration is copied by this implementation.
- Mac availability and subscription entitlement are operational dependencies, not reasons to spend against a paid API. Offline/unavailable conditions fail boundedly.
- The installed Hermes native adapter signature remains compatible. Changes in bootstrap shape, endpoint, model identity, incomplete responses or tool calls fail closed. Parent must verify the actual installed runtime/OAuth path.

## architecture_gate

- `code_architect_loaded`: true, because the accepted integrity/at-most-once invariant spans the GitHub producer, local executor and retrieving workflow.
- `change_class`: workflow gate plus data contract.
- `invariant`: only fixed classification/synthesis of the exact approved run-bound input may cause inference; inference is durably claimed before it starts and never automatically repeated after ambiguity. Only validated native report artifacts reach existing publication.
- `owner_boundary`: `intel/local_model_worker.py` owns the run protocol, validation, local claim/submission records and fixed Actions transport. `intel/codex_inference.py` owns the tool-free native model call. Existing `pipeline.synthesize_brief` retains synthesis/disposition/reference/publication validation.
- `consumer_files`: daily and result workflows; existing failure-status imports remain source-compatible.
- `duplicated_policy_found`: no new independent report generator or consumer health classifier. The retrieving side deliberately reuses native materialization/disposition helpers to verify source-bound metadata rather than trusting remote writes. Legacy per-item Perplexity code remains untouched for existing callers and Radar.
- `verification_tier`: protocol/fault unit tests, fake-GitHub/native-pipeline round trip, repository regression, shell/plist syntax; live path reserved to parent.

## Implemented behavior

1. Original weekday workflow reserves and collects as before, then creates a data-only request artifact binding repository, run ID/attempt, source commit, date, 30-minute absolute deadline and SHA-256 of all request inputs.
2. Local poller checks the exact repository, main, daily-intel.yml workflow_dispatch in-progress run and exact active `brief` job. No remote source code is executed; only a request.json archive entry is read, never extracted as arbitrary paths.
3. An exclusive run-ID claim is fsynced, including the parent directory, before inference. Different hashes/attempts under the same run ID are blocked. Existing completed results are cached. Crash/unknown claims never re-infer automatically.
4. A single classification batch uses native calibration/schema and exact Luna model. Complete, duplicate-free coverage and field types/enums/text bounds are required. The original article object is attached deterministically, never accepted from model output.
5. Existing native synthesis uses exact Sol through a completion seam. Native contract-only regeneration remains bounded; transport/timeout exceptions from the native helper do not enter the legacy RequestException retry path. Native helper disables SDK retries, has no agent dispatcher, sends empty tools, rejects tool calls/incomplete output and verifies the subscription endpoint and response identity.
6. The successful envelope contains only typed classification rows, native brief text and source dispositions. The receiving workflow and original workflow each validate the request/result binding, full source coverage, references, dispositions, counts, date and interval. They materialize only the fixed native filenames.
7. Result return uses one fixed main workflow_dispatch; inputs are environment data, not shell code. A durable submission reservation precedes the POST. A lost acknowledgement is unknown and never auto-reposted. The original run retrieves the exact named result artifact from a successful result workflow; dispatch acknowledgement alone does not equal end-to-end delivery.
8. Safe failure uses the existing producer failure-status schema, with Codex provider labeling and legacy Perplexity compatibility. Existing valid same-run/stage failure evidence is preserved by the workflow failure handler.
9. Daily workflow no longer receives a Perplexity model credential. All existing collection/reservation/ledger/delivery/Slack/Vault owners remain. Weekly workflows and `pipeline.py` are unchanged.

## Bounds and intentional limitations

- Request maximum 2 MB; returned JSON maximum 60,000 UTF-8 bytes to stay beneath GitHub workflow_dispatch limits. There is no candidate or material-signal count cap. Oversize output fails instead of truncating coverage or changing providers. JSON escaping in the outer dispatch can add bytes; actual GitHub acceptance is a parent live gate and a rejected POST remains terminal/unknown rather than triggering model repetition.
- Request expires after 30 minutes; original wait is bounded to 30 minutes. Each native subprocess is at most 300 seconds and respects remaining request time; native HTTP timeout is 270 seconds.
- Original job remains GitHub-hosted while waiting. This is intentionally not a self-hosted runner or inbound server. Local gh polling is every 30 seconds via a separate launchd label.
- Run/result listing windows are bounded. Unavailable, expired, malformed or ambiguous artifacts fail/timeout rather than fabricate success.
- Concurrent manual pollers are unsupported operationally; launchd does not overlap its own instance. The exclusive inference claim still prevents a second inference, but a competing poller can conservatively surface an unknown failure while the first is active.
- No automatic claim reset/resend/recovery UI is added. Existing publication guard and owner-led provider/artifact reconciliation remain the retry authority.

## changed_files and scope_traceability

| Files | Authorized requirement |
|---|---|
| `.github/workflows/daily-intel.yml` | Replace only paid daily inference with prepare/upload/await; keep original downstream owners; add read-only Actions access |
| `.github/workflows/pulse-model-result.yml` | Fixed bounded result upload, no model credentials or executable input |
| `intel/local_model_worker.py` | Narrow run-bound protocol, validations, durable claim/submission, fixed polling/return/retrieval and native pipeline reuse |
| `intel/codex_inference.py` | Existing Hermes native OAuth transport, exact models, subscription endpoint, zero tools, zero SDK retry/fallback |
| `intel/failure_status.py` | Codex provider facts without changing legacy receipt shape or breaking old Perplexity validation |
| `scripts/run_local_model_worker` | Separate launchd-invoked local poll launcher, explicit durable state and dedicated home |
| `deploy/local-model-worker.plist.in`, `deploy/pulse-hermes-config.yaml` | Installable templates, not installed/activated here |
| `tests/test_local_model_worker.py`, `tests/test_local_model_workflow.py` | Protocol, faults, native model-call shape, fake transport and native-pipeline acceptance |
| `tests/test_daily_schedule_contract.py` | Update the superseded inference-command expectation; retain schedule/delivery assertions |
| `docs/local-model-worker-scope.md`, `docs/local-model-worker.md`, this report | Scope, operations, exact parent-owned release/activation and remaining gates |
| `docs/verification/local-model-worker/*` | Persisted RED/GREEN/full-collection evidence, no auth/model-provider response data |

## acceptance_checks and tests_or_readbacks_run

All model/network behavior in automated tests is explicitly synthetic; no real inference or GitHub mutation occurred. Committed pytest logs have trailing whitespace normalized only; original command output remains in the scratch evidence files.

| Check | Executed evidence |
|---|---|
| Initial protocol missing before implementation | `red.log`: 25 expected failures (new module absent) |
| Native no-agent transport and workflow migration missing | `native-red.log`: expected new-boundary/template failures |
| Codex failure preservation/provider initially wrong | `receipt-red.log`: 2 failures, 30 passing |
| Missing absolute request deadline | `deadline-red.log`: failure before deadline implementation |
| Wrong report title date / internally consistent but fabricated counts | `metadata-red.log`: 2 deterministic failures; both repaired by native metadata recomputation |
| Exact active workflow job | `job-red.log`: wrong job initially accepted; repaired in fixed GH polling boundary |
| Exact repo/workflow/branch/event/run/attempt/hash rejection before inference | New targeted tests |
| Durable claim before inference; cached duplicate; hard-crash unknown; changed same-run request blocked | New targeted tests |
| Strict classification coverage/schema; exact one batch model; native Sol synthesis; no paid endpoint | New targeted tests |
| Tool-call/incomplete native response rejection; retry count zero; subprocess environment isolation | New targeted tests |
| Successful quiet/material source-disposition round trips through real native pipeline with fake completions | New targeted tests; no replacement report generator |
| Wrong-result hash/arbitrary output fields/archive paths rejected; safe terminal receipt; timeout; lost POST ack blocks replay | New targeted tests |
| Targeted final campaign | `targeted.log` (final result below after final source verification) |
| Integrated single-repository campaign | `repository.log` (final result below after final source verification) |
| Full unfiltered suite | `integrated.log`: collection fails because external `action_os_industry_news_intake` is absent in this isolated single-repository layout. No full-suite pass claimed. |
| `git diff --check`, `plutil -lint deploy/local-model-worker.plist.in`, `sh -n scripts/run_local_model_worker` | Passed |

Final source-bound campaign: **42 targeted tests passed (0.16s)** and **203 single-repository tests passed (3.43s)**, including the active-job regression. The full unfiltered suite did not collect because the cross-repository module requires unavailable sibling sources. Live checkout readback remained clean at the original base commit. Shell/plist syntax and `git diff --check` passed.

### Interface discovery and execution issues

- Default Python and installed Hermes venv did not contain pytest. Created an isolated scratch test venv; installed repository dependencies and pytest there, not into live/default Hermes.
- A combined dependency/help command was refused/withdrawn by the tool approval layer. It was not retried or bypassed. Source inspection resolved the relevant interface instead.
- Web documentation extraction was unavailable through the configured search-only backend; used inspected installed launcher/adapter source and the loaded Hermes skill, not invented CLI/API flags.
- Important source finding: empty CLI toolset selection means defaults, not zero tools. Replaced the provisional CLI approach with the existing native adapter and empty tools; no Hermes code changed.
- An optional fake-provider/real-installed-adapter bootstrap probe was submitted but returned `pending_approval`, not execution output. No passing native-runtime probe is claimed. Its scratch script is available to the parent; exact-runtime acceptance remains unverified here.

## related_findings_deferred / remaining_gates

1. Independent parent review and real installed Hermes native adapter/OAuth acceptance for both exact models (including entitlement/token refresh and actual tool-free wire behavior). No paid fallback allowed if it fails.
2. Source release to main and actual GitHub result-dispatch/artifact-retrieval acceptance. Fake GH fixtures prove application contracts, not provider permissions, public workflow title semantics or payload-size acceptance.
3. Stable worker installation and launchd loaded-process readback. Templates passing syntax are not activation proof. Preserve durable claims across rollback.
4. One parent-authorized real Pulse using existing reservation policy; verify canonical report, full classification/dispositions, ledger, package, Slack, Vault and COS source status. Do not clear historic unknown reservations or recover a backlog automatically.
5. Existing COS/other installed consumers importing producer `valid_receipt` must run the reviewed producer revision before Codex receipt compatibility can be claimed operationally. No COS changes were made.
6. Cross-repository intelligence-routing test requires the external sibling COS/Action OS/MIOS sources. Reconstructing that broader environment is not part of this model-worker change.
7. Dispatch size bounds can fail large public reports rather than truncate material coverage. If observed in real acceptance, parent should approve a narrow compressed-result transport change, not add a general runner or paid API fallback.

## remediation_round

Initial authorized implementation with TDD iterations. No repeated architecture expansion, no Kanban, no production remediation or unrelated cleanup.

## stop_condition_met

Implementation, scoped regression, persisted evidence and activation handoff are complete once the final local campaign and local-only commit below are recorded. **Operational activation/real generation acceptance is intentionally not met** and remains the parent's separately owned gate. No deployment readiness or COS recovery is inferred from these tests.
