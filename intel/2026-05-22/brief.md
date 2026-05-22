# ASA Daily Intelligence Brief — 2026-05-22

**Items reviewed:** 420
**Items surfaced:** 6
**Items deduped against ledger:** 18
**Today's headline:** CFPB's defunding notice and the shift to formal 1033 rulemaking after credit-union pressure escalate open-banking regulatory drift from "paused" to "actively being rewritten" — Vault's compliance narrative needs a refresh.

---

## TL;DR

1. Bud Financial disclosed sub-5ms transaction processing on IBM watsonx.data infrastructure, the first specific performance claim from the vendor now embedded in Banno [REF 1].
2. CFPB formally notified the court it cannot lawfully draw Federal Reserve funds, and separately shifted Section 1033 to full rulemaking after credit-union lobbying — two distinct facts not in the ledger's prior Sixth Circuit pause coverage [REF 2][REF 3].
3. Plaid shipped Guaranteed Payments (fraud-backed ACH guarantee) and a Cash Advance Index risk score, extending its move from data rail into underwriting and payment assurance [REF 4][REF 5].

---

## By roadmap area

**Vault.** Bud Financial's IBM watsonx.data disclosure (sub-5ms banking data processing) is the first concrete infrastructure claim from the vendor Jack Henry chose for Banno enrichment [REF 1]. Combined with the JPMorgan aggregator fee deals already in the ledger, the data-layer competition is now about latency and unit economics, not just coverage. Recommendation: Investigate whether ASA Vault can publish comparable p99 latency numbers within 30 days.

**Compass.** No material signal today.

**Auth.** No material signal today.

**Verify.** No material signal today.

**Pay.** Plaid Guaranteed Payments converts Plaid's fraud graph into a managed ACH guarantee product — a step beyond data provision into balance-sheet-adjacent risk assumption [REF 4]. This pressures ASA Pay's positioning because FI buyers will now ask whether ASA underwrites approvals or only enables them. Recommendation: Decision needed by 2026-06-15 on whether ASA Pay's roadmap includes a guarantee/indemnity tier or remains a pure orchestration layer.

**One View.** Bud's latency claim lands directly under One View's enrichment value proposition inside Banno, ASA's primary channel [REF 1]. The question is no longer whether Bud is embedded — it is whether Bud's performance envelope makes ASA One View's enrichment a hard replacement sell at Banno FIs. Recommendation: Monitor for any Banno FI defections or dual-vendor RFPs over the next 60 days.

**Forecast.** Plaid's Cash Advance Index scores repayment risk from network and cash flow data — overlapping Forecast's predictive cashflow territory but aimed at lenders, not FI engagement [REF 5]. The adjacency is real but the buyer is different (lender risk team vs. FI product team), so positioning impact is limited near-term. Recommendation: Monitor for Plaid extending the index into FI-facing decisioning.

**Horizontal.** Two distinct CFPB developments today: the bureau filed notice it cannot legally draw Fed funds [REF 2], and it shifted to full Section 1033 rulemaking after credit-union pressure [REF 3]. The ledger covered the Sixth Circuit pause; these are different facts — one operational (funding), one procedural (rulemaking path). Together they extend the compliance-timeline ambiguity into 2027 and weaken any "1033 deadline" narrative in ASA's sales motion. Recommendation: Decision needed by 2026-05-29 on whether to rewrite open-banking talk-track for Q3 BD cycle.

---

## Watchlist movement

| Entity | Signal type | One-line detail | Status | Ref |
|---|---|---|---|---|
| Jack Henry/Banno (Bud) | partnership | Bud discloses sub-5ms processing on IBM watsonx.data inside Banno enrichment | Delta | 1 |
| CFPB | regulatory | Bureau notifies court OLC ruled it cannot draw Fed funds under Dodd-Frank | New | 2 |
| CFPB | regulatory | Shifted to full Section 1033 rulemaking after credit-union lobbying | Delta | 3 |
| Plaid | launch | Guaranteed Payments — fraud-backed managed ACH approval product | New | 4 |
| Plaid | launch | Cash Advance Index — repayment risk score from network + cash flow data | New | 5 |
| Plaid | launch | Effects 2026 — broad AI, fraud, lending, payments, dev tooling launches | New | 6 |

---

## Open questions for the team

1. Can ASA Vault publish a defensible latency benchmark against Bud's sub-5ms claim, or do we concede infrastructure narrative and compete on consent/privacy?
2. Does ASA Pay's two-year roadmap commit to a guarantee/indemnity tier, or do we explicitly position as orchestration-only and cede the assurance layer to Plaid/Stripe-class players?
3. With CFPB operationally and procedurally weakened on 1033, what does ASA's BD team substitute for the "compliance deadline" hook in Q3 outreach?

---

## References

1. IBM, "Banking at 5 milliseconds: How Bud Financial built a data-intelligence platform on IBM watsonx.data," 2026-01-14. https://news.google.com/rss/articles/CBMirgFBVV95cUxPNUFOVkluUHViREJMWGFWWmR1NWNINFVKbkxoSzBEQlFUbThrSTZ6MUJ5SlNNTldLRmJSY1JEU2lsczdqX3NCNHVGNGZvYU5KVVVPclh1SVU3MG41Vi10UW00bG9pQkJFdDZNWVgyTkNwRHdaUDRBeEhKellNZ1NvS3NSYkVuVklXWVVBQVhCR1U4OVY3UHJncU9LREN0UGxPdE5vckU1cUJMTktkb3c?oc=5 — *First concrete performance disclosure from the vendor embedded in Banno, ASA's primary channel.*
2. CFPB, "CFPB Notifies Court it Cannot Lawfully Draw Funds from the Federal Reserve," 2025-11-11. https://www.consumerfinance.gov/about-us/newsroom/cfpb-notifies-court-it-cannot-lawfully-draw-funds-from-the-federal-reserve/ — *Operational defunding distinct from the Sixth Circuit procedural pause already tracked.*
3. Credit Union Times, "CFPB Shifts to Full Rulemaking for Section 1033 Rewrite After Credit Union Push," 2026-01-29. https://news.google.com/rss/articles/CBMitgFBVV95cUxNYkVEbkZhM3BIY2hOLWpEcENsTjRxeDdHTnFNZWxyTExZOHFFc3RJSUV6TlRSbVhSWUoxX3U2VGtXUi1oZGkzV2lnT0prdlBOUzVRVWd1cFpRcUQyZl9OclNFcGp0RlA0eU94Z3duVGRFeHUySEV1c09TRGtoU0pjZ3ZZN1h1TTlvT3BGVlZhMFZxaU1tajB2RjcwOWVfX1NBZHlidmpUOFdSRTQxaFl6bFdhUEZRUQ?oc=5 — *Procedural escalation beyond the prior interim-rule speculation, with named lobby pressure.*
4. Plaid, "Plaid Guaranteed Payments: Approve more transactions without the risk," 2026-05-02. https://plaid.com/blog/introducing-plaid-guaranteed-payments/ — *Plaid extending from data provision into balance-sheet-adjacent payment assurance.*
5. Plaid, "Introducing Plaid Cash Advance Index for smarter decisioning," 2026-05-03. https://plaid.com/blog/cash-advance-index-risk-decisioning/ — *Productized cashflow risk scoring overlapping Forecast positioning, lender-aimed.*
6. Plaid, "Everything we announced at Plaid Effects 2026," 2026-05-04. https://plaid.com/blog/effects-2026-recap/ — *Breadth-of-product signal across AI, fraud, lending, payments, and dev tooling in a single release cycle.*

---
*Brief generated by ASA daily intel pipeline. Triage rubric v0.2
/ synthesis prompt v0.3. Items deduped against 14-day topic
ledger.*