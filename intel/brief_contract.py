from __future__ import annotations

import re
from datetime import datetime


class BriefContractError(ValueError):
    pass


def validate_daily_pulse(
    brief: str,
    *,
    expected_interval: tuple[datetime, datetime] | None = None,
    expected_material_count: int | None = None,
) -> None:
    errors: list[str] = []
    if not re.search(r"(?m)^# ASA Industry News Pulse — \d{4}-\d{2}-\d{2}$", brief):
        errors.append("daily pulse header is missing or malformed")
    interval = re.search(
        r"(?m)^\*\*Reporting interval:\*\* "
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}) to "
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})$",
        brief,
    )
    if not interval:
        errors.append("reporting interval is missing or malformed")
    elif expected_interval and interval.groups() != tuple(value.isoformat() for value in expected_interval):
        errors.append("reporting interval does not match the deterministic Pacific boundary")
    required_sections = (
        "## Top summary",
        "## Material signals",
        "## Candidate disposition",
        "## References",
    )
    for section in required_sections:
        if section not in brief:
            errors.append(f"missing section: {section}")
    total = re.search(r"(?m)^\*\*Candidates classified:\*\* (\d+)$", brief)
    material = re.search(r"(?m)^\*\*Material signals:\*\* (\d+)$", brief)
    counts = re.search(
        r"(?m)^\*\*Classification counts:\*\* "
        r"material=(\d+); monitor=(\d+); noise=(\d+); duplicate=(\d+); needs_validation=(\d+)$",
        brief,
    )
    if not total or not material or not counts:
        errors.append("classification counts are missing or malformed")
    elif int(material.group(1)) != int(counts.group(1)) or int(total.group(1)) != sum(
        int(value) for value in counts.groups()
    ):
        errors.append("classification counts do not reconcile")
    if material and int(material.group(1)) == 0 and "No evidence-backed material signals" not in brief:
        errors.append("zero-material pulse is not explicit")
    material_section = re.search(r"(?ms)^## Material signals\s*(.*?)(?=^## |\Z)", brief)
    material_entries = re.findall(r"(?m)^###\s+", material_section.group(1) if material_section else "")
    if material and int(material.group(1)) != len(material_entries):
        errors.append("material entry count does not match declared Material signals")
    if expected_material_count is not None and material and int(material.group(1)) != expected_material_count:
        errors.append("material entry count does not match selected evidence-backed candidates")
    if errors:
        raise BriefContractError("; ".join(errors))


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
    surfaced = re.search(r"(?m)^\*\*Items surfaced:\*\*\s*(\d+)\s*$", brief)
    if not surfaced:
        errors.append("Items surfaced count is missing or malformed")
    else:
        surfaced_count = int(surfaced.group(1))
        if row_count == 0 and surfaced_count != 0:
            errors.append("watchlist has no valid rows")
        elif row_count > surfaced_count:
            errors.append("watchlist row count exceeds declared Items surfaced")

    if errors:
        raise BriefContractError("; ".join(errors))
