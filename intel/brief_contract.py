from __future__ import annotations

import re


class BriefContractError(ValueError):
    pass


def validate_weekly_brief(brief: str) -> None:
    errors: list[str] = []
    required_sections = (
        "## TL;DR",
        "## By roadmap area",
        "## Watchlist movement",
        "## Open questions for the team",
        "## References",
    )
    if not re.search(r"(?m)^# ASA Weekly Intelligence Brief — Week of \d{4}-\d{2}-\d{2}$", brief):
        errors.append("weekly header is missing or malformed")
    for section in required_sections:
        if section not in brief:
            errors.append(f"missing section: {section}")

    match = re.search(r"(?ms)^## References\s*(.*?)(?=^## |\Z)", brief)
    references: dict[int, str] = {}
    if not match:
        errors.append("references section is missing")
    else:
        for line in match.group(1).splitlines():
            numbered = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
            if not numbered:
                continue
            number = int(numbered.group(1))
            definition = numbered.group(2)
            if number in references:
                errors.append(f"duplicate reference {number}")
                continue
            references[number] = definition
            if not re.search(r'https?://\S+', definition):
                errors.append(f"reference {number} is missing a URL")
            if not (
                re.search(r'"[^"\n]+"', definition)
                or re.search(r'“[^”\n]+”', definition)
            ):
                errors.append(f"reference {number} is missing a quoted title")
            if not (
                re.search(r"\b\d{4}-\d{2}-\d{2}\b", definition)
                or re.search(
                    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(?:[1-9]|[12]\d|3[01]),?\s+\d{4}\b",
                    definition,
                    re.I,
                )
            ):
                errors.append(f"reference {number} is missing a date")

    used = {int(number) for number in re.findall(r"\[REF\s+(\d+)\]", brief, re.I)}
    missing = used - set(references)
    if missing:
        errors.append("undefined reference anchors: " + ", ".join(str(number) for number in sorted(missing)))

    watchlist = re.search(r"(?ms)^## Watchlist movement\s*(.*?)(?=^## |\Z)", brief)
    row_count = 0
    if watchlist:
        for line in watchlist.group(1).splitlines():
            if not line.lstrip().startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) != 5 or cells[0].casefold() in {"entity", "---"} or set(cells[0]) == {"-"}:
                continue
            row_count += 1
            row_refs = {int(number) for number in re.findall(r"\d+", cells[4])}
            if not row_refs:
                errors.append(f"watchlist row {row_count} has no reference")
            undefined = row_refs - set(references)
            if undefined:
                errors.append(
                    f"watchlist row {row_count} uses undefined references: "
                    + ", ".join(str(number) for number in sorted(undefined))
                )
    if row_count == 0:
        errors.append("watchlist has no valid rows")
    surfaced = re.search(r"(?m)^\*\*Items surfaced:\*\*\s*(\d+)\s*$", brief)
    if not surfaced:
        errors.append("Items surfaced count is missing or malformed")
    elif row_count > int(surfaced.group(1)):
        errors.append("watchlist row count exceeds declared Items surfaced")

    if errors:
        raise BriefContractError("; ".join(errors))
