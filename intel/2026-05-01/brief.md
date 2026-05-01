# ASA Daily Intelligence Brief — 2026-05-01

**Items reviewed:** 411
**Items surfaced:** 14
**Today's headline:** Bud Financial is now embedded inside Banno, ASA's primary distribution channel, while CFPB paralysis and a Plaid foundation-model push reshape the ground beneath Vault and One View.

---

## TL;DR

1. Bud Financial's transaction enrichment is now native to Jack Henry/Banno, putting a direct One View/Forecast competitor inside ASA's #1 FI distribution channel at ~1,000 institutions [REF 1][REF 2].
2. The CFPB has told a court it cannot lawfully draw funds and is signaling interim final rules and a fee-focused 1033 rewrite — open banking compliance posture is genuinely unsettled [REF 3][REF 4][REF 5].
3. Plaid shipped a transaction foundation model, a rebuilt income engine, and Protect fraud-network results — categorization, income verify, and fraud signals are all moving up-stack [REF 6][REF 7][REF 8].

---

## By roadmap area

**Vault.** JPMorgan reportedly cut fee deals with aggregators and is renegotiating with Yodlee, while Wells Fargo and PNC push fintechs toward Akoya — bank-imposed pricing on data access is now real, not theoretical [REF 9][REF 10]. Vault's permissioned-access narrative gets stronger, but unit economics for any aggregator-dependent path get worse. **Investigate** which of ASA's upstream data routes carry JPMC/WF/PNC fee exposure and model two pricing scenarios by next sprint review.

**Compass.** Plaid+Perplexity expanded into spending tracking and net-worth/AI planning, hitting Compass's consumer-insight value prop directly [REF 11]. Personetics also added an MCP server letting banks build agentic apps on customer financial data [REF 12]. **Decision needed by 2026-05-15:** does Compass ship an MCP surface this half, or do we cede the agentic-banking framing to Personetics and Bud?

**Auth.** No material signal today specific to Auth beyond Plaid Protect's network-fraud claims (59% more fraud caught), which is adjacent rather than core [REF 8]. **Monitor.**

**Verify.** Plaid rebuilt its income engine with finer taxonomy and configurable calculation [REF 7]; Socure passed $340M ARR at 62% YoY growth [REF 13]; Alloy launched perpetual KYB [REF 14]. The verify field is hardening on three sides at once. **Investigate** Verify's income-taxonomy parity vs. Plaid before Q3 planning locks.

**Pay.** Fiserv+Affirm bringing BNPL to debit cards raises FI feature expectations adjacent to Pay [REF 15]. FinCEN/OFAC's GENIUS Act AML/sanctions proposals could touch any stablecoin-adjacent flow we entertain [REF 16]. **Monitor**; no Pay-specific decision needed this week.

**One View.** This is the day's hot zone. Bud is now native in Banno [REF 1][REF 2], and Bud separately shipped an MCP server pitched as bank-grade financial intelligence for AI agents [REF 17]. Plaid's transaction foundation model targets the same categorization layer One View sells on [REF 6]. **Decision needed by 2026-05-08:** ASA's response posture to Bud-in-Banno — competitive displacement playbook, co-existence pitch, or accelerated alternative-channel push (Alkami, Q2, Lumin, Corelation).

**Forecast.** Bud-in-Banno also threatens Forecast's enrichment-dependent predictions at the same ~1,000 FIs [REF 1][REF 2]. Personetics+Atomic announced a deposit-growth collaboration squarely on Forecast's turf [REF 18]. **Investigate** which Banno FIs in our active pipeline have already been quoted Bud and whether Forecast's deposit-growth proof points are tight enough to defend.

**Horizontal.** Regulatory weather is the story. CFPB filed notice it cannot lawfully draw Federal Reserve funds [REF 3], is signaling interim final rules on 1033/1071 despite funding constraints [REF 4], and Bloomberg Law expects a quicker route on the rewrite with a fee focus [REF 5][REF 19]. The Sixth Circuit paused litigation pending rulemaking [REF 20]. Net effect: timeline ambiguity but a likely fee-centric rewrite that reshapes aggregator economics. **Decision needed by 2026-05-22:** refresh the investor and BD narrative on 1033 to reflect "rewrite, not repeal, fee-centric" — current talk track is stale.

---

## Watchlist movement

| Entity | Signal type | One-line detail | Ref |
|---|---|---|---|
| Jack Henry/Banno + Bud Financial | partnership | Bud transaction enrichment native in Banno Digital Platform | 1, 2 |
| CFPB | regulatory | Notice to court: cannot lawfully draw Fed funds | 3 |
| CFPB | regulatory | Signals interim final rules on 1033 and 1071 | 4 |
| CFPB | regulatory | 1033 rewrite expected on quicker path, fee-focused | 5, 19 |
| Sixth Circuit | regulatory | Paused 1033 litigation pending rulemaking | 20 |
| Plaid | launch | Transaction foundation model for categorization/insights | 6 |
| Plaid | launch | Rebuilt income engine with new taxonomy | 7 |
| Plaid | launch | Protect: claims 59% more fraud caught | 8 |
| Plaid + Perplexity | partnership | Expanded integration: spending, net worth, AI planning | 11 |
| Bud Financial | launch | MCP server for bank-grade financial intelligence | 17 |
| Personetics | launch | MCP server for agentic banking apps | 12 |
| Personetics + Atomic | partnership | Deposit-growth collaboration | 18 |
| Socure | other | Q1 2026 ARR $340M+, 62% YoY growth | 13 |
| Alloy | launch | Perpetual KYB and ongoing risk assessment | 14 |
| Akoya / JPMC / Yodlee | positioning | Bank fee deals and Akoya routing pressure | 9, 10 |
| Fiserv + Affirm | partnership | BNPL embedded into debit cards | 15 |
| FinCEN/OFAC | regulatory | GENIUS Act AML/sanctions proposed rules | 16 |

---

## Open questions for the team

1. BD: how many of our active Banno-channel deals overlap with FIs Jack Henry can now upsell Bud enrichment to, and what's the Q3 retention exposure?
2. Engineering: what is the realistic 90-day path to an ASA MCP server for Vault/One View, given Bud, Personetics, Nymbus, and Fifth Third's Newline have shipped one?
3. Finance/BD: if JPMC-style data-access fees generalize to WF and PNC, what is Vault's gross-margin sensitivity and which upstream routes need a contingency?

---

## References

1. PR Newswire, "Jack Henry's transaction enrichment, powered by Bud Financial, brings greater clarity and accuracy to digital banking experiences," 2026-01-28. https://news.google.com/rss/articles/CBMijwJ... — *Bud now native in ASA's primary distribution channel.*
2. ATM Marketplace, "Jack Henry partners with Bud Financial to add transaction details to Banno Digital Platform," 2026-02-09. https://news.google.com/rss/articles/CBMixwF... — *Confirms Banno integration scope.*
3. CFPB Newsroom, "CFPB Notifies Court it Cannot Lawfully Draw Funds from the Federal Reserve," 2025-11-11. https://www.consumerfinance.gov/about-us/newsroom/cfpb-notifies-court-it-cannot-lawfully-draw-funds-from-the-federal-reserve/ — *Operational paralysis at the agency writing 1033.*
4. Consumer Financial Services Law Monitor, "CFPB Signals Issuance of Interim Final Rules on Section 1071 and Section 1033 Amid Funding Constraints," 2025-12-11. https://news.google.com/rss/articles/CBMi9wF... — *Interim final rule path changes timing assumptions.*
5. American Banker, "CFPB revamps 1033 open banking rule with new focus on fees," 2025-08-21. https://news.google.com/rss/articles/CBMimgF... — *Fee focus reshapes aggregator economics.*
6. Plaid blog, "Building a transaction foundation model to power intelligent finance," 2026-04-04. https://plaid.com/blog/building-transaction-foundation-model-intelligent-finance/ — *Direct attack on One View categorization moat.*
7. Plaid blog, "Meet the new engine behind Plaid Income," 2026-04-04. https://plaid.com/blog/meet-the-new-engine-behind-plaid-income/ — *Raises Verify's income parity bar.*
8. Plaid blog, "New era of fraud network intelligence: Early results from Plaid Protect," 2026-03-04. https://plaid.com/blog/plaid-protect-network-insights/ — *Network-scale fraud signal adjacent to Auth.*
9. Reuters, "JPMorgan secures deals with fintech aggregators over fees to access data," 2025-11-14. https://news.google.com/rss/articles/CBMi5AF... — *Bank fees on data access becoming real.*
10. Bloomberg Law, "Wells Fargo, PNC Push Fintechs to Use Bank-Backed Data Firm," 2025-11-04. https://news.google.com/rss/articles/CBMipgF... — *Akoya channel pressure on aggregator routes.*
11. Plaid blog, "Plaid and Perplexity expand integration to power personalized financial insights," 2026-04-04. https://plaid.com/blog/plaid-perplexity-ai-financial-insights-integration/ — *Consumer-side AI insights overlap with Compass.*
12. Fintech Finance, "Personetics Launches MCP Server—Enabling Banks to Develop Agentic AI Applications," 2025-09-11. https://news.google.com/rss/articles/CBMi9wF... — *Direct competitor with shipped MCP story.*
13. Business Wire, "Socure Q1 2026 Results: $340M+ Total ARR with 62% YoY Profitable Growth," 2026-04-28. https://news.google.com/rss/articles/CBMixwF... — *Verify channel partner scaling fast.*
14. Finovate, "Alloy Unveils Perpetual KYB and Customer Risk Assessment," 2026-01-21. https://news.google.com/rss/articles/CBMihAF... — *Encroaches on Verify identity/compliance.*
15. Finovate, "Fiserv Brings BNPL Capabilities to Debit Cards with Affirm," 2026-01-27. https://news.google.com/rss/articles/CBMihwF... — *Raises Pay feature expectations at FIs.*
16. JD Supra, "FinCEN and OFAC Propose Rule for Payment Stablecoin Issuers to Implement GENIUS Act," 2026-05-01. https://news.google.com/rss/articles/CBMigAF... — *Compliance overhang on any stablecoin-adjacent Pay flows.*
17. Financial IT, "Bud Financial Launches MCP Server to