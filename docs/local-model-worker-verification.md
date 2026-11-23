# Pulse worker corrective verification

## Scope and production boundary

Approved models: `gpt-6-luna` classification and `gpt-6.1-sol` synthesis through the local subscription-backed native Codex adapter. No paid fallback, no public ingress, no arbitrary remote execution. Production publication/delivery remains owned by the original GitHub pipeline.

Troy explicitly chose to preserve the failed November 23 attempt and start with the next scheduled Pulse. Do not delete or supersede that reservation, publish a diagnostic brief, or run catch-up.

## Executed corrective evidence

- Initial incident suite: **16 failed, 5 passed**. This established RED before product changes.
- `1cbc7eb`: producer-only native label normalization, batches of at most 24, complete bounded LZMA/base64 transport, strict decompression/identity checks, submission file and directory fsync before POST, existing OAuth-home instructions. Scoped repository campaign: **224 passed**.
- Native saved-input replay using 433 historical November 19 articles: first 24-item Luna call completed in **66.25 seconds** with **23 rows**, missing `e7fd81ad3737f15b`. Exact request/response and failed receipt retained locally; no publication or GitHub write occurred.
- `5819c22`: one bounded correction only for missing identities after a completed, nonempty, otherwise valid partial response. Completed rows retained; empty/malformed responses and ambiguous transport failures do not retry. Added tests first failed, then scoped campaign: **226 passed**.
- Independent read-only review found one further first-use durability issue: the new `claims` directory entry was not fsynced through its parent before inference. It found no additional blockers in classification correction, consumer strictness, compression, submission ordering or run binding.
- `5b876ca`: fsync claim file, claims directory, state directory and state parent before inference. Focused fresh-state test first failed on the original ordering; scoped repository campaign then passed **227 tests in 3.22 seconds**.

Command shape: the dedicated test venv runs `python -m pytest tests -q --tb=short --ignore=tests/integration/test_intelligence_routing_chain.py --basetemp=<unique profile scratch path>`. This is a **scoped** campaign: the excluded routing test requires sibling COS/Action OS/MIOS sources absent from this isolated checkout.

## Full saved-input acceptance

The complete replay **passed**: **433 input IDs, 433 unique validated output IDs**, no diagnostic errors, native Sol synthesis validated, and lossless compressed dispatch decoding plus native materialization passed. Elapsed **1,162.73 seconds**. Complete logical result: **219,170 bytes**; compressed dispatch string: **45,338 bytes**, with the aggregate POST budget separately enforced below 60,000 bytes.

The call trace records **22 Luna completions** (one exact-prompt captured native response reused, 21 fresh native calls) and **one fresh Sol call**. Responses and receipts remain in local diagnostic storage, not publication artifacts. Initial batch omissions were corrected only for missing IDs. The replay used commit `5819c22`; AST comparison confirms the later `5b876ca` changes only `process` claim-directory fsync, with inference, normalization, validation and transport functions unchanged. The additional ordering fix is covered by the passing 227-test campaign.

## Activation boundary

This record captures pre-activation acceptance. Source publication and the installed/loaded worker must be verified separately against the selected release commit. A passing local replay does not establish GitHub result-artifact retrieval, Slack delivery, Vault ingestion or COS freshness. Those unattended publication proofs remain pending the next scheduled Pulse; no catch-up or diagnostic publication is authorized.
