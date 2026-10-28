import json
from datetime import date

import pytest

from intel import pipeline
from intel.brief_contract import BriefContractError


def record(number):
    return {
        'id': f'item-{number}', 'classification': 'material', 'relevance_score': 2,
        '_source_item': {'title': f'Source {number}', 'source': 'Example',
                         'source_url': f'https://example.com/{number}',
                         'published_date': 'Tue, 27 Oct 2026 20:00:00 GMT'},
    }


def candidate(dispositions, headings):
    return ('# ASA Industry News Pulse — 2026-10-28\n\n'
            '## Top summary\n\nSummary.\n\n## Material signals\n\n'
            + '\n\n'.join(f'### Signal {n}\n\nSource changed [REF {n}].' for n in headings)
            + '\n\n## Candidate disposition\n\nDisposition evidence.\n\n'
            + '<!-- candidate-dispositions: ' + json.dumps(dispositions) + ' -->\n\n'
            + '## References\n')


def run(tmp_path, text, ledger=None):
    src = tmp_path / 'triaged.jsonl'
    src.write_text('\n'.join(json.dumps(record(n)) for n in range(1, 5)) + '\n')
    prior = tmp_path / 'ledger.json'
    prior.write_text(json.dumps(ledger or []))
    out = tmp_path / 'brief.md'
    pipeline.synthesize_brief(src, out, prior, brief_date=date(2026, 10, 28),
                              completion_func=lambda **kwargs: text)
    return out.read_text()


def test_deduplication_updates_counts_from_complete_dispositions(tmp_path):
    brief = run(tmp_path, candidate({'1': 'material', '2': 'duplicate:1',
                                    '3': 'material', '4': 'duplicate:history:known_event'}, [1, 3]),
                [{'topic_key': 'known_event'}])
    assert '**Material signals:** 2\n' in brief
    assert 'material=2; monitor=0; noise=0; duplicate=2; needs_validation=0' in brief
    assert '**Candidates classified:** 4\n' in brief
    assert 'candidate-dispositions:' not in brief
    receipt = json.loads((tmp_path / 'synthesis-dispositions.json').read_text())
    assert receipt['dispositions']['2'] == 'duplicate:1'
    assert receipt['classification_counts']['material'] == 2


@pytest.mark.parametrize('dispositions,headings', [
    ({'1': 'material', '2': 'duplicate:1', '3': 'material'}, [1, 3]),
    ({'1': 'material', '2': 'duplicate:99', '3': 'material', '4': 'material'}, [1, 3, 4]),
    ({'1': 'material', '2': 'duplicate:history:invented', '3': 'material', '4': 'material'}, [1, 3, 4]),
    ({'1': 'material', '2': 'material', '3': 'material', '4': 'material'}, [1, 3]),
    ({'1': 'duplicate:2', '2': 'duplicate:1', '3': 'material', '4': 'material'}, [3, 4]),
])
def test_incomplete_or_invalid_accounting_fails_closed(tmp_path, dispositions, headings):
    with pytest.raises(BriefContractError):
        run(tmp_path, candidate(dispositions, headings))
    assert not (tmp_path / 'brief.md').exists()
    failures = sorted((tmp_path / 'synthesis-diagnostics').glob('attempt-*.json'))
    assert len(failures) == 3
    failure = json.loads(failures[-1].read_text())
    assert failure['raw_response'] == candidate(dispositions, headings)
    assert failure['error']
    assert failure['selected_source_count'] == 4
    assert failure['parsed_material_headings'] == len(headings)
    assert failure['selected_source_ids'] == [f'item-{n}' for n in range(1, 5)]


def test_dispositions_cannot_hide_a_material_entry_behind_another_reference(tmp_path):
    text = candidate({'1': 'material', '2': 'duplicate:1', '3': 'material', '4': 'duplicate:1'}, [1, 3])
    text = text.replace('Source changed [REF 3].', 'Source changed [REF 1].')
    with pytest.raises(BriefContractError, match='material source'):
        run(tmp_path, text)


def test_duplicate_disposition_keys_fail_closed_and_preserve_raw_response(tmp_path):
    text = candidate({'1': 'material', '2': 'duplicate:1', '3': 'material', '4': 'duplicate:1'}, [1, 3])
    text = text.replace('"2": "duplicate:1"', '"2": "material", "2": "duplicate:1"')
    with pytest.raises(BriefContractError, match='repeated'):
        run(tmp_path, text)
    failure = json.loads((tmp_path / 'synthesis-diagnostics/attempt-1.json').read_text())
    assert failure['raw_response'] == text
    assert not (tmp_path / 'brief.md').exists()


def test_missing_dispositions_cannot_publish_multiple_material_candidates(tmp_path):
    text = candidate({'1': 'material'}, [1, 2, 3, 4])
    text = text[:text.index('<!--')] + '\n## References\n'
    with pytest.raises(BriefContractError, match='dispositions'):
        run(tmp_path, text)
