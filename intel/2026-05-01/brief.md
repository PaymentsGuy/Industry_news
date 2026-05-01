# ASA Daily Intelligence Brief — 2026-05-01

**Items reviewed:** 931
**Items surfaced:** 14
**Today's headline:** Open banking economics are being rewritten in real time — bank-imposed data fees, a stayed 1033 rule, and Bud's capture of Banno are the three forces ASA must answer this quarter.

---

## TL;DR

1. Bud Financial is now embedded in Jack Henry/Banno for transaction enrichment and signed Nymbus and First Fidelity Bank — a direct competitor is colonizing two ASA channel partners simultaneously [REF 1] [REF 2] [REF 3].
2. CFPB's Section 1033 rule is stayed by court order with an interim final rule and ANPR in motion, while JPMorgan's data-access fees and renegotiated Yodlee pact are repricing the entire aggregation layer [REF 4] [REF 5] [REF 6] [REF 7].
3. Agentic AI via MCP is shipping in production: Personetics, Bud, Plaid, FactSet, and Narmi/Grasshopper all released MCP servers or transaction foundation models in the last six months [REF 8] [REF 9] [REF 10] [REF 11].

---

## By roadmap area

**Vault.** No direct signal on Vault itself today, but the JPMorgan aggregator-fee regime [REF 6] and renegotiated JPM/Yodlee pact [REF 7] reshape the cost structure underneath any permissioned-data product. **Monitor** — track whether ASA's pass-through economics hold if top-5 banks adopt JPM-style fees.

**Compass.** Personetics' MCP server [REF 8], Bud's MCP server [REF 9], and Plaid's transaction foundation model [REF 12] all directly target Compass's insights moat. Personetics now serves 150M+ monthly users at peer banks [REF 13]. **Decision needed by 2026-05-22:** ship an MCP-compatible interface for Compass or publicly commit to one.

**Auth.** The 1033 stay [REF 4] freezes the regulatory tailwind ASA's Auth narrative depends on. Wells Fargo and PNC are pressuring fintechs onto Akoya [REF 14], and Plaid Protect now claims 59% more fraud detection [REF 15]. **Investigate** how an Akoya-mandated FI shifts ASA Auth's connectivity story for shared accounts.

**Verify.** Plaid's AI document verification, Encompass mortgage integration, and new income-classification engine [REF 16] tighten the verify race. JPMorgan's fee regime threatens the unit economics of every income/asset verification call ASA brokers [REF 6]. **Investigate** Verify pricing exposure to top-5 bank fee schedules within two weeks.

**Pay.** Pinwheel-Plaid alliance for direct deposit switching [REF 17] and Q2's stablecoin and BNPL/Affirm integrations [REF 18] expand the competitive surface. The 1033 fee provisions [REF 5] could reshape Pay's permissioned-debit economics. **Monitor** — no immediate action.

**One View.** Bud Financial powers Jack Henry's Banno transaction enrichment [REF 1] and First Fidelity Bank's deployment [REF 3]. This is the most acute channel-partner threat in today's set: a direct competitor now sits inside ASA's largest distribution partner. **Decision needed by 2026-05-15:** BD and CPO align on Banno counter-positioning — defend, displace, or differentiate.

**Forecast.** Bud and Personetics are both wrapping forecast-adjacent capabilities in agentic AI [REF 8] [REF 9]. Plaid's transaction foundation model directly targets predictive cashflow [REF 12]. **Investigate** whether Forecast's roadmap clearly differentiates from foundation-model-based categorization within 30 days.

**Horizontal.** Section 1033 is in active rewrite under an ANPR with an interim final rule pending [REF 4] [REF 5]. CFPB has told a court it cannot lawfully draw Federal Reserve funds [REF 19], adding institutional uncertainty. JPMorgan's bilateral aggregator pacts [REF 7] suggest the future of US open banking may be commercially negotiated rather than regulator-defined. **Monitor** the interim rule text when published; **Decision needed by 2026-06-01** on whether ASA publicly takes a position in the comment period.

---

## Watchlist movement

| Entity | Signal type | One-line detail | Ref |
|---|---|---|---|
| Bud Financial / Jack Henry | partnership | Bud powers Banno transaction enrichment | 1 |
| Bud Financial / Nymbus | partnership | AI-powered PFM via Bud at Nymbus | 2 |
| Bud Financial / First Fidelity | partnership | Bank deployment in ASA target segment | 3 |
| CFPB | regulatory | 1033 stayed; new rulemaking initiated | 4 |
| CFPB | regulatory | Interim final rule on 1033 planned | 5 |
| JPMorgan (tech_macro) | regulatory | Aggregator data-access fees announced | 6 |
| Envestnet/Yodlee | partnership | JPM-Yodlee fee-based pact renegotiated | 7 |
| Personetics | launch | MCP server for agentic banking apps | 8 |
| Bud Financial | launch | MCP server for AI agents on bank data | 9 |
| Plaid | launch | March/April product updates incl. AI IDV | 10 |
| MCP for finance | launch | Narmi/Grasshopper first US bank MCP | 11 |
| Plaid | research | Transaction foundation model | 12 |
| Personetics | positioning | 150M+ monthly users milestone | 13 |
| Akoya | positioning | Wells Fargo, PNC pushing fintechs to Akoya | 14 |
| Plaid | launch | Protect detects 59% more fraud | 15 |
| Plaid | launch | Encompass mortgage + new Income engine | 16 |
| Pinwheel | partnership | Plaid preferred provider for DDS | 17 |
| Q2 | partnership | Stablecoin and Affirm BNPL integrations | 18 |
| CFPB | regulatory | Notified court it cannot draw Fed funds | 19 |

---

## Open questions for the team

1. **BD/CPO:** What is our concrete counter-move for Banno now that Bud is the embedded enrichment provider — displace, co-exist, or shift channel weight to Alkami/Q2/Lumin?
2. **CTO:** Should ASA ship an MCP server in Q2, and if so, against which surface (One View read, Compass insights, or Vault actions)?
3. **CEO:** Do we file public comments on the 1033 rewrite under our name, and what is our stated position on bank-imposed aggregator fees?

---

## References

1. ATM Marketplace, "Jack Henry partners with Bud Financial to add transaction details to Banno Digital Platform," 2026-02-09. https://news.google.com/rss/articles/CBMixwFBVV95cUxNc05GZ1ZBZFcxdnhZVHdwTGpBN2R5VVVxeVhRcjdJRnBPUUw4WndYLTFxQmlkSTh1eWQ4dGYzejc5V0lfWmtLYjRQX08xZ2NSS2VXb0NmZThLWGVoa1ZLWm5qWjhJNGl6bkhSVWxjaUQ1UldQV3RuVVAzSVNpRXBvb3RYTkxobnJuZGdyRTVaTWR4OF9ON3pNQ0FQWHlKMGF2NGgxa2ZaYTU3SWxLUExhbXJiSmxUOUN3UlAxWnNvS25ZNWpySGZF — *Direct competitor inside top ASA channel partner.*
2. PR Newswire, "Nymbus Signs Agreement With Bud Financial," 2025-07-08. https://news.google.com/rss/articles/CBMikwJBVV95cUxNblZST0NuTmhUM2QtNmN3RTdiX3JCOGs2M29BMHZfMnZZWjNpUW9hRGhyS2VpSUVsWTJ1UmFGSW91NENkek1SME4tOXlmakpnMkJqZl9GbzBXb1VfR1EzN3ZqeVFnRnd4M3Mwb3pYOVF3c3RZX3JtRnJVaFlYd3QtTElhQXppM2N4Q3NiVThIY1VuZnNzYi1Kd3k1d3RhTXpGZWRnLXA0RkZDOV9XRFhpNmN1YXFJMWhMY2JWLWdHRExNa2ZVYWdCNVVUcWhZdk1rbHhFVWo2c3RDdERXX2x6ODlvWmh1R2JvY3M3TVZqOGk0MWl3VWVvTjhDMWZIcDBDdkF4VkhfZ1I1bEZUUkk1XzI3cw — *Second channel partner taken by Bud.*
3. FinTech Futures, "First Fidelity Bank partners Bud Financial," 2026-02-25. https://news.google.com/rss/articles/CBMikwFBVV95cUxOcGtIeTMzWW5ET25xTnhtTnRuQk5CZlB4LXV5WV9XU1FYNFhQUmtsMEpCUVQ5S3h2eFNFRlVPOFVfd3pYX2pvVldJcEdLR09EYmRFeGxIbDZsM3ktRjhHR1pzNFNTRmwwTVBKSkZid19VdEljWkxBSW40R2Z0VTZOZVRVUDdBUU41ZG1uWDE3VmxpWGc — *Bud expanding direct FI footprint.*
4. Consumer Financial Services Law Monitor, "CFPB Section 1033 Open Banking Rule Stayed," 2025-07-30. https://news.google.com/rss/articles/CBMi0gFBVV95cUxOQ0ZJeE5IRXViWHFNZUphRlVpX0dLSjhnNmRCVTlNdy1wUGhzUDhjanU4bnVJalZlRGJEb3dMQkd5Z0xQaFZuZVJFZTdrd1Q3QnRMeWppUHJmYmhIZ3lpZS1jMEJBSXVNczlMUjc2NUUwWVhDSXVMblR2aVB6NkEzNlE0a2NrbHRsQnROTkgzb0JNbDlvU285aDlMWENUcUx0M2UzNk1GbHdtWG1jTThkNWJzNkp0Qkx1dXFCYnU0V3FoYXZ3NmY5NUZSRlkwdjFveEE — *Stay reshapes 1033 timeline.*
5. American Banker, "CFPB to issue 'interim' final rule on 1033 open banking," 2025-12-10. https://news.google.com/rss/articles/CBMikwFBVV95cUxNMU5HQzVKYVlJSFFXU29hQmg4bUpISVNqMlhwUDFrcnlXbWxEYWxDX1JROUF2YkNqRHBKcnpZWnZEaHYxRGtlektzWHVhT2JFSlZoSVpiS0NJMXlWdUlRcFJ0WkdBNWxmY1JGdGxIdGEySWU3aW03Q0syc2ZwTG9GWDVUWFNLRWZaSGVDaThpNERaRk0 — *Interim rule could move quickly.*
6