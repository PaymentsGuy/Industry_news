import pytest

from intel.brief_contract import BriefContractError, validate_weekly_brief


def weekly_brief(reference: str) -> str:
    return (
        "# ASA Weekly Intelligence Brief — Week of 2026-06-15\n\n"
        "**Items reviewed:** 1\n"
        "**Items surfaced:** 1\n"
        "**Items deduped against ledger:** 0\n"
        "**This week's headline:** Acme changed.\n\n"
        "## TL;DR\n\n1. Acme changed [REF 1].\n\n"
        "## By roadmap area\n\n**Vault.** Acme changed [REF 1].\n\n"
        "## Watchlist movement\n\n"
        "| Entity | Signal type | One-line detail | Status | Ref |\n"
        "|---|---|---|---|---|\n"
        "| Acme | Launch | Acme changed | New | [REF 1] |\n\n"
        "## Open questions for the team\n\n1. What next?\n\n"
        "## References\n\n"
        f"{reference}\n"
    )


def test_weekly_contract_accepts_complete_reference():
    validate_weekly_brief(
        weekly_brief('1. Source, "Acme changed," 2026-06-15. https://example.test/1 — *Evidence.*')
    )


def test_weekly_contract_rejects_more_watchlist_rows_than_items_surfaced():
    brief = weekly_brief(
        '1. Source, "Acme changed," 2026-06-15. https://example.test/1 — *Evidence.*'
    )
    extra_row = "| Beta | launch | Beta changed. | New | [REF 1] |\n"
    brief = brief.replace("## Open questions", extra_row + "\n## Open questions")

    with pytest.raises(BriefContractError, match="watchlist row count exceeds declared Items surfaced"):
        validate_weekly_brief(brief)


def test_weekly_contract_rejects_reference_without_url():
    with pytest.raises(BriefContractError, match="reference 1 is missing a URL"):
        validate_weekly_brief(
            weekly_brief('1. Source, “Acme changed,” 2026-06-15. — *Evidence.*')
        )


def test_weekly_contract_rejects_undefined_watchlist_reference():
    brief = weekly_brief('1. Source, "Acme changed," 2026-06-15. https://example.test/1 — *Evidence.*')
    brief = brief.replace("[REF 1] |", "[REF 2] |")
    with pytest.raises(BriefContractError, match="undefined references: 2"):
        validate_weekly_brief(brief)
