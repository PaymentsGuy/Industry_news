# Intelligence Routing Contract v1

This contract freezes the owner and immutable identity at every handoff. Consumers may persist only the fields named here; they do not become editable owners of either report body.

## Industry News Pulse

`Industry_news` owns the canonical Markdown body and producer transaction. The version-2 runtime `delivery.json`, validated by `intel.routing_contract` when it is created, contains:

- `brief_id`, `cadence=weekday_daily`, and an inclusive-start/exclusive-end Pacific reporting interval;
- canonical body, `content_sha256`, source path, transaction ID, and repository producer receipt after commit readback;
- exact counts for `material`, `monitor`, `noise`, `duplicate`, and `needs_validation` candidates;
- stable material signal identities and evidence links; explicit proposal fields exist only for Action OS-eligible signals;
- repository, Slack, and Vault delivery receipts in the package, plus separate receipt files from COS and Action OS (`not_applicable` is explicit).

All evidence-backed material signals are retained. Internal batching must not create a publication cap. Action OS may be `not_applicable` when no signal has a concrete action or decision, proposed owner, and evidence.

Slack and Vault receive/read back the canonical body identity. The cloud workflow cannot impersonate the local Vault bridge; a managed local scanner consumes only repository-and-Slack-verified pending packages. COS verifies the signed Vault receipt and stores a read-only projection with pulse identity, interval, producer-derived count, freshness, status, and link. Action OS accepts only capability-authenticated, HMAC-bound requests whose signal, evidence link, classification, and pulse hash read back from the local verified package. No consumer stores an editable duplicate report body.

## Competitive Radar

Atlas owns the dated report and raw evidence. A package manifest contains:

- report date, relative report path/hash, and Atlas backlink;
- deterministic sorted raw-evidence paths and hashes;
- one package transaction ID and a separate producer receipt.

MIOS may persist the package identity, report hash/date, Atlas path/backlink, immutable evidence references, intake state, and human review history. It must not persist a competing editable report or create findings/downstream work during import.

## Failure and replay rules

Missing fields, path traversal, absent evidence, hash mismatch, same-period hash conflict, or missing receipt fails closed. Matching replay returns the existing identity. A provider acknowledgement without readback is ambiguous and blocks blind retry.

## Cutover rule

Historical Industry News MIOS records remain legacy provenance. Future Industry News ingestion retires only after repository, Slack, Vault, COS, and applicable Action OS receipts reconcile for one pulse identity. Retirement is visible and cannot be represented as ordinary success.
