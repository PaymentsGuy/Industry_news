# ASA Daily Intelligence Brief — 2026-05-17

**Items reviewed:** 422
**Items surfaced:** 6
**Items deduped against ledger:** 38
**Today's headline:** Quiet weekend; the only fresh signals are a JPMorgan/Yodlee fee-deal escalation and a CFPB enforcement-pullback on BNPL — both narrow but each shifts a single ASA cost or compliance assumption.

---

## TL;DR

1. Plaid extended Bank Intelligence with Fraud Insights and a Primacy Score loyalty metric for FIs, moving deeper into FI-facing decisioning territory adjacent to Compass and One View [REF 1].
2. CFPB will not prioritize enforcement of its 2024 BNPL/Reg Z digital-accounts rule, removing a near-term compliance overhang for ASA Pay-adjacent flows [REF 2].
3. JPMorgan reached fee agreements with fintech aggregators (per CNBC via Reuters), confirming paid data access is moving from rumor to executed contracts [REF 3] — building on the JPMorgan/Yodlee renegotiation already in the ledger.

---

## By roadmap area

**Vault.** Delta on `jpmorgan_yodlee_data_pact`: Reuters/CNBC reports JPMorgan has now signed fee deals with multiple aggregators, not just Yodlee [REF 3]. This converts "fees loom" into "fees executed" and resets ASA Vault's unit-economics planning for JPMC-sourced data. Recommendation: **Decision needed by 2026-05-31** — finance and BD must price a JPMC pass-through model before contract renewal cycles.

**Compass.** Plaid Bank Intelligence now ships a Primacy Score for customer loyalty plus Fraud Insights aimed at FIs [REF 1]. This is Plaid pushing past consumer-app distribution into the FI-facing analytics seat ASA Compass targets. Recommendation: Investigate Plaid's Primacy Score methodology and FI pricing within two weeks; brief BD on differentiation talking points.

**Auth.** No material signal today.

**Verify.** No material signal today. (Plaid Income engine improvements [REF 4] are from April and already absorbed; flagging only because Plaid keeps compounding in this lane.)

**Pay.** CFPB formally deprioritized enforcement of the 2024 BNPL Reg Z digital-accounts rule [REF 2]. For ASA Pay, this lowers near-term compliance cost for BNPL-adjacent transaction handling but does not eliminate state-level exposure (see OCC/Illinois preemption in ledger). Recommendation: Monitor — no roadmap change, but compliance can deprioritize the BNPL/Reg Z workstream.

**One View.** Plaid's Fraud Insights and Primacy Score sit on top of categorized transaction data — the same substrate as One View [REF 1]. Plaid is now selling enrichment outputs (loyalty, fraud) rather than just raw connectivity, narrowing One View's "we turn transactions into decisions" pitch. Recommendation: Investigate by 2026-05-24 whether One View should publish a comparable primacy/loyalty signal as a packaged output.

**Forecast.** No material signal today.

**Horizontal.** Two fresh regulatory data points pull in opposite directions: CFPB pulling back on BNPL enforcement [REF 2], and JPMC monetizing data access [REF 3]. Net effect for ASA: federal compliance burden easing, private-sector data costs rising. Recommendation: Monitor — update the investor narrative slide to reflect "compliance tailwind, data-cost headwind."

---

## Watchlist movement

| Entity | Signal type | One-line detail | Status | Ref |
|---|---|---|---|---|
| Plaid | launch | Bank Intelligence adds Fraud Insights + Primacy Score loyalty metric for FIs | New | 1 |
| CFPB | regulatory | Will not prioritize enforcement of 2024 BNPL Reg Z digital-accounts rule | New | 2 |
| Akoya / JPMorgan | partnership | CNBC/Reuters: JPMC signed data-access fee deals with fintech aggregators | Delta | 3 |
| Plaid | launch | New Plaid Income engine: finer taxonomy, configurable calculation controls | New | 4 |
| Plaid | partnership | Expanded Perplexity integration: net worth, spend tracking, AI planning | New | 5 |
| Plaid | launch | Transaction foundation model for categorization and insights | New | 6 |

(Note: items 4–6 are dated April 2026 Plaid blog posts not previously surfaced; including under bias-toward-inclusion since each contains a specific new product fact and none appears in the ledger.)

---

## Open questions for the team

1. What is ASA's pass-through pricing model if JPMC, and likely Wells/PNC next, charge per-call fees to aggregators — and do we surface that as a line item or absorb it?
2. Does ASA need to ship a "primacy" or "primary-bank" score as a Compass/One View output before Plaid wins the FI category narrative on it?

---

## References

1. Plaid (blog), "Bank Intelligence is expanding for financial institutions," 2026-05-02. https://plaid.com/blog/expanding-bank-intelligence-fraud-and-loyalty/ — *Plaid productizes FI-facing fraud and customer-loyalty scoring, overlapping Compass and One View output layers.*
2. CFPB (newsroom), "CFPB Announcement Regarding Enforcement Actions Related to Buy Now, Pay Later Loans," 2025-05-06. https://www.consumerfinance.gov/about-us/newsroom/cfpb-announcement-regarding-enforcement-actions-related-to-buy-now-pay-later-loans/ — *Removes near-term Reg Z BNPL compliance overhang for ASA Pay-adjacent flows.*
3. Reuters (via Akoya blog), "JPMorgan secures deals with fintech aggregators over fees to access data, CNBC reports," 2025-11-14. https://news.google.com/rss/articles/CBMi5AFB...?oc=5 — *Confirms paid bank-data access moving from speculation to signed contracts; resets aggregation unit economics.*
4. Plaid (blog), "Meet the new engine behind Plaid Income," 2026-04-04. https://plaid.com/blog/meet-the-new-engine-behind-plaid-income/ — *Plaid raises the feature bar in income verification adjacent to ASA Verify.*
5. Plaid (blog), "Plaid and Perplexity expand integration to power personalized financial insights," 2026-04-04. https://plaid.com/blog/plaid-perplexity-ai-financial-insights-integration/ — *Plaid embeds in a second frontier AI surface beyond ChatGPT, deepening the AI-data-rail thesis.*
6. Plaid (blog), "Building a transaction foundation model to power intelligent finance," 2026-04-04. https://plaid.com/blog/building-transaction-foundation-model-intelligent-finance/ — *Plaid building proprietary transaction-categorization model directly contests One View's enrichment differentiation.*

---
*Brief generated by ASA daily intel pipeline. Triage rubric v0.2 / synthesis prompt v0.3. Items deduped against 14-day topic ledger.*