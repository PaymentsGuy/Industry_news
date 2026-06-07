# ASA Daily Intelligence Brief — 2026-06-07

**Items reviewed:** 425
**Items surfaced:** 5
**Items deduped against ledger:** 12
**Today's headline:** Plaid expanded its Bank Intelligence product with Fraud Insights and a Primacy Score for FIs — a direct shot at Compass and Verify positioning at the FI tier.

---

## TL;DR

1. Plaid is moving from aggregator into FI-facing intelligence with new Fraud Insights and a customer Primacy Score inside Bank Intelligence, plus a managed Guaranteed Payments ACH product [REF 1][REF 2].
2. CFPB filed a court notice that DOJ's OLC has ruled it cannot lawfully draw operating funds from the Federal Reserve under Dodd-Frank — a material escalation in the 1033 funding-constraint thread already in the ledger [REF 3].
3. Plaid's Effects 2026 recap confirms a multi-front product push across AI, fraud, lending, payments, and developer tooling on a single day — competitive surface area against ASA is widening simultaneously [REF 4].

---

## By roadmap area

**Vault.** Plaid's Effects 2026 announcements span aggregation-adjacent surfaces including new AI models and developer tooling [REF 4]. Implication for Vault is incremental, not structural — Plaid continues to bundle aggregation with higher-value layers, compressing standalone aggregator pricing power. Recommendation: Monitor; pull the Effects 2026 product list and map overlap to Vault SKUs by 2026-06-14.

**Compass.** Plaid's new Primacy Score directly targets the "who is your primary-relationship customer" question that Compass answers via behavioral signals [REF 2]. This is the first time Plaid has shipped a named FI-facing loyalty metric, which reframes Compass's pitch from "we have unique insight" to "we have *differentiated* insight." Recommendation: Decision needed by 2026-06-21 on whether Compass publishes a comparison primer for BD.

**Auth.** No material signal today.

**Verify.** Plaid Fraud Insights adds real-time fraud signals into the FI-facing Bank Intelligence product [REF 2]. This sits between Verify's identity layer and a downstream fraud decisioning stack — not a head-on collision, but it narrows the wedge. Recommendation: Investigate whether Fraud Insights is sold standalone or only bundled with Bank Intelligence.

**Pay.** Plaid Guaranteed Payments is a fully-managed ACH product where Plaid absorbs fraud risk on approved transactions [REF 1]. This is a meaningful shift: ASA Pay competes on rails and orchestration, not on underwriting the payment itself. If Plaid's loss rates hold, FIs and fintechs will ask why ASA Pay does not guarantee. Recommendation: Decision needed by 2026-06-28 on whether ASA Pay needs a guarantee-tier roadmap response.

**One View.** No material signal today.

**Forecast.** No material signal today.

**Horizontal.** Building on the CFPB funding-constraint thread last covered 2026-05-29, the CFPB filed a notice in NTEU v. Vought that DOJ's Office of Legal Counsel has determined the Bureau may not legally draw Federal Reserve funds under Dodd-Frank [REF 3]. This escalates from "signal" to "legal determination" and makes any near-term 1033 interim final rule mechanically harder to staff and defend. Recommendation: Monitor; brief BD on revised 1033 narrative for FI prospects by 2026-06-12.

---

## Watchlist movement

| Entity | Signal type | One-line detail | Status | Ref |
|---|---|---|---|---|
| CFPB | regulatory | DOJ OLC ruled CFPB cannot lawfully draw Federal Reserve funds; notice filed in NTEU v. Vought | Delta | 3 |
| Plaid | launch | Bank Intelligence expanded with Fraud Insights and Primacy Score for FIs | New | 2 |
| Plaid | launch | Guaranteed Payments — managed ACH with Plaid-backed fraud guarantee | New | 1 |
| Plaid | launch | Effects 2026 recap: new AI models, fraud, lending, payments, developer tools | New | 4 |
| Plaid | launch | Trust Index 3 fraud model upgrade for Plaid Protect | New | 5 |

---

## Open questions for the team

1. What is the loss rate and price point on Plaid Guaranteed Payments, and does ASA Pay need to offer a comparable underwritten tier or explicitly cede that lane?
2. Does the OLC ruling on CFPB funding change our 1033 talk track from "compliance window" to "indefinite stay," and does that help or hurt enterprise FI deal velocity?

---

## References

1. Plaid blog, "Plaid Guaranteed Payments: Approve more transactions without the risk," 2026-05-02. https://plaid.com/blog/introducing-plaid-guaranteed-payments/ — *Plaid enters underwritten ACH, a category ASA Pay does not currently address.*
2. Plaid blog, "Bank Intelligence is expanding for financial institutions," 2026-05-02. https://plaid.com/blog/expanding-bank-intelligence-fraud-and-loyalty/ — *Named FI-facing Fraud Insights and Primacy Score overlap Compass and Verify positioning.*
3. CFPB newsroom, "CFPB Notifies Court it Cannot Lawfully Draw Funds from the Federal Reserve," 2025-11-11. https://www.consumerfinance.gov/about-us/newsroom/cfpb-notifies-court-it-cannot-lawfully-draw-funds-from-the-federal-reserve/ — *DOJ OLC legal determination escalates the CFPB funding-constraint thread from political signal to litigated fact.*
4. Plaid blog, "Everything we announced at Plaid Effects 2026," 2026-05-04. https://plaid.com/blog/effects-2026-recap/ — *Single-day multi-product launch across AI, fraud, lending, payments, and dev tools signals broadening competitive surface.*
5. Plaid blog, "Ti3 is here: A bigger graph for a fast moving fraud landscape," 2026-05-01. https://plaid.com/blog/introducing-trust-index-3-fraud-detection/ — *Trust Index 3 deepens Plaid Protect's fraud graph, reinforcing the Verify-adjacent push.*

---
*Brief generated by ASA daily intel pipeline. Triage rubric v0.2 / synthesis prompt v0.3. Items deduped against 14-day topic ledger.*