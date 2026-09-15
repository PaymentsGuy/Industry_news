from intel.brief_contract import validate_weekly_brief


def test_quiet_week_with_zero_surfaced_items_does_not_require_watchlist_rows():
    brief = (
        "# ASA Weekly Intelligence Brief — Week of 2026-06-15\n\n"
        "**Items reviewed:** 1\n"
        "**Items surfaced:** 0\n"
        "**Items deduped against ledger:** 1\n"
        "**This week's headline:** Quiet week; no material signals surfaced.\n\n"
        "## TL;DR\n\n"
        "1. No material signal in this category this week.\n"
        "2. No material signal in this category this week.\n"
        "3. No material signal in this category this week.\n\n"
        "## By roadmap area\n\n"
        "**Vault.** No material signal this week.\n\n"
        "## Watchlist movement\n\n"
        "| Entity | Signal type | One-line detail | Status | Ref |\n"
        "|---|---|---|---|---|\n\n"
        "## Open questions for the team\n\n"
        "No open questions this week.\n\n"
        "## References\n"
    )

    validate_weekly_brief(brief)
