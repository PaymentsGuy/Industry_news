import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
DAY = ROOT / "intel/2026-05-02"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def test_may2_corrected_revision_is_self_bound_and_preserves_original():
    original_path = DAY / "brief.md"
    corrected_path = DAY / "brief.corrected-v1.md"
    raw_path = DAY / "raw.jsonl"
    receipt_path = DAY / "brief.corrected-v1.receipt.json"

    receipt = json.loads(receipt_path.read_text())
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    assert receipt["receipt_sha256"] == sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    )
    assert receipt["original_preserved"] is True
    assert receipt["analysis_text_changed"] is False
    assert receipt["original_file_sha256"] == sha256(original_path.read_bytes())
    assert receipt["corrected_file_sha256"] == sha256(corrected_path.read_bytes())
    assert receipt["raw_sha256"] == sha256(raw_path.read_bytes())

    original = original_path.read_text()
    corrected = corrected_path.read_text()
    marker = "> **Historical corrected revision — 2026-08-21.**"
    assert marker not in original
    assert marker in corrected
    assert corrected.split("## References", 1)[0] == original.split("## References", 1)[0]
    for number in range(1, 7):
        pattern = rf"(?m)^{number}\. .*$"
        corrected_definition = re.search(pattern, corrected)
        original_definition = re.search(pattern, original)
        assert corrected_definition and original_definition
        assert corrected_definition.group(0) == original_definition.group(0)

    raw_items = {json.loads(line)["id"]: json.loads(line) for line in raw_path.read_text().splitlines()}
    for restored in receipt["restored_references"]:
        item = raw_items[restored["raw_item_id"]]
        assert item["source_url"] == restored["source_url"]
        definition = re.search(
            rf"(?m)^{restored['reference']}\. .*?(https?://\S+)", corrected
        )
        assert definition and definition.group(1) == restored["source_url"]
