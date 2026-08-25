import hashlib
import json
import re
from pathlib import Path

import pytest

from intel.brief_contract import BriefContractError, validate_weekly_brief


ROOT = Path(__file__).parents[1]
FOLDER = ROOT / "intel/2026-08-17"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_aug17_original_is_preserved_and_corrected_revision_restores_only_raw_backed_urls():
    original_path = FOLDER / "brief.md"
    corrected_path = FOLDER / "brief.corrected-v1.md"
    raw_path = FOLDER / "raw.jsonl"
    receipt_path = FOLDER / "brief.corrected-v1.receipt.json"
    original = original_path.read_text(encoding="utf-8")
    corrected = corrected_path.read_text(encoding="utf-8")
    raw_items = {
        item["id"]: item
        for line in raw_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for item in [json.loads(line)]
    }
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    with pytest.raises(BriefContractError, match="reference 1 is missing a URL"):
        validate_weekly_brief(original)
    validate_weekly_brief(corrected)

    assert receipt["original_preserved"] is True
    assert receipt["analysis_text_changed"] is False
    assert len(receipt["restored_references"]) == 7
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    assert receipt["receipt_sha256"] == _sha(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    )
    assert receipt["original_file_sha256"] == _sha(original_path.read_bytes())
    assert receipt["corrected_file_sha256"] == _sha(corrected_path.read_bytes())
    assert receipt["raw_sha256"] == _sha(raw_path.read_bytes())

    references = corrected.split("## References", 1)[1]
    for mapping in receipt["restored_references"]:
        assert raw_items[mapping["raw_item_id"]]["source_url"] == mapping["source_url"]
        line = next(
            value for value in references.splitlines()
            if value.startswith(f"{mapping['reference']}. ")
        )
        assert mapping["source_url"] in line

    strip_urls = lambda value: re.sub(r"\s+https?://\S+(?=\s+—)", "", value)
    assert strip_urls(corrected) == original
