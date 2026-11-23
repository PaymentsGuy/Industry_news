"""Incident regressions: captured Luna output and full-size lossless transport. No inference."""
import base64
import json
import lzma
import random
from pathlib import Path

import pytest

from test_local_model_worker import classified, item, module, request, run


def test_captured_luna_labels_are_derived_only_at_producer():
    m = module()
    rows = json.loads((Path(__file__).parent/'fixtures/local_model_worker/luna-captured-mismatch.json').read_text())
    raw = [{**item(), 'id':row['id']} for row in rows]
    with pytest.raises(ValueError, match='contradicts'):
        m.validate_classifications(rows, raw)
    output = m.classify(raw, lambda **_: json.dumps(rows))
    assert len(output) == 12
    assert output[0]['classification'] == output[2]['classification'] == 'needs_validation'
    assert output[9]['classification'] == 'duplicate'
    assert output[0]['relevance_score'] == 2
    assert output[0]['uncertainty_flags'] == ['proposal_details_unavailable']
    m.validate_classifications([{k:v for k,v in r.items() if k != '_source_item'} for r in output], raw)


@pytest.mark.parametrize('change', ['missing', 'extra', 'id', 'type', 'label'])
def test_producer_normalization_does_not_hide_invalid_schema(change):
    m = module(); row = classified()
    if change == 'missing': del row['classification']
    if change == 'extra': row['command'] = 'bad'
    if change == 'id': row['id'] = 'b'*16
    if change == 'type': row['relevance_score'] = True
    if change == 'label': row['classification'] = 123
    with pytest.raises(ValueError): m.classify([item()], lambda **_: json.dumps([row]))


def large_result(tmp_path):
    """433 complete rows, varied bounded text, native metadata/dispositions; not a count cap."""
    m = module(); rng = random.Random(20261119)
    words = 'bank payments regulatory platform market financial partner launch service data customers digital account credit funding research'.split()
    raw = [{**item(), 'id':f'{i:016x}'} for i in range(433)]
    rows = [{**classified(), 'id':r['id'],
             'headline_paraphrase':' '.join(rng.choices(words, k=21)),
             'why_it_matters_for_asa':' '.join(rng.choices(words, k=20))} for r in raw]
    req = m.make_request(run(), '2026-11-23', raw, [], [])
    quiet = ('# ASA Industry News Pulse — 2026-11-23\n\n## Top summary\n\nNo material change.\n\n'
             '## Material signals\n\nNo evidence-backed material signals.\n\n## Candidate disposition\n\n'
             'All candidates classified.\n\n## References\n')
    def complete(**kw):
        if kw['model'] != 'gpt-6-luna': return quiet
        batch = json.loads(kw['messages'][0]['content'].split('INPUT ITEMS JSON:\n')[-1])
        ids = {r['id'] for r in batch}
        return json.dumps([r for r in rows if r['id'] in ids])
    output = m.execute_request(req, tmp_path/'work', complete)
    return req, {**m.envelope(req), 'status':'succeeded','reason':None,'failure':None,'output':output}


def test_433_rows_dispatch_roundtrip_preserves_full_native_artifacts(tmp_path, monkeypatch):
    m = module(); req, result = large_result(tmp_path)
    assert len(m.encoded(result).encode()) > 250_000
    actual = m.process(req, run(), tmp_path/'state', lambda *_:result['output'])
    assert actual['status'] == 'succeeded'
    assert actual == result
    sent = []; gh = m.GitHub()
    gh.api = lambda path,payload:sent.append((path,payload))
    gh.return_result(actual)
    wire = sent[0][1]['inputs']['result']
    assert len(wire.encode()) <= 60_000
    outer = json.loads(wire)
    assert all(outer[k] == req[k] for k in ('run_id','run_attempt','request_hash'))
    decoded = m.decode_dispatch(wire)
    assert m.digest(decoded) == m.digest(result)
    assert decoded['request_hash'] == req['request_hash']
    m.validate_result(req, decoded)
    monkeypatch.setattr(m.GitHub, 'get_run', lambda _,rid:run())
    monkeypatch.setattr(m.GitHub, 'request', lambda _,observed:req)
    monkeypatch.setenv('PULSE_RESULT', wire)
    monkeypatch.setenv('GITHUB_OUTPUT', str(tmp_path/'gh-output'))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('sys.argv', ['worker','receive'])
    m.main()
    assert json.loads((tmp_path/'result.json').read_text()) == result
    assert (tmp_path/'gh-output').read_text().strip() == f"artifact_name=pulse-result-123-1-{req['request_hash']}"
    m.accept_result(req, decoded, tmp_path/'accepted')
    rows = m.pipeline.read_jsonl(tmp_path/'accepted/triaged.jsonl')
    assert len(rows) == 433
    assert [r['id'] for r in rows] == [r['id'] for r in req['raw']]
    assert (tmp_path/'accepted/brief.md').read_text() == result['output']['brief']


@pytest.mark.parametrize('damage', ['base64','corrupt','truncated','trailing','bomb','memory','wire','identity'])
def test_compressed_dispatch_rejects_corruption_bombs_and_identity(damage):
    m = module(); result = m.failed_result(request(), 'execution_failed')
    outer = json.loads(m.encode_dispatch(result))
    blob = base64.b64decode(outer['data'])
    if damage == 'base64': outer['data'] = '!bad!'
    if damage == 'corrupt': blob = blob[:30] + bytes([blob[30] ^ 1]) + blob[31:]
    if damage == 'truncated': blob = blob[:-5]
    if damage == 'trailing': blob += b'garbage'
    if damage == 'bomb': blob = lzma.compress(b'x' * (2_000_000 + 1))
    if damage == 'memory': blob = lzma.compress(b'{}', preset=9)
    if damage == 'wire': outer['data'] = 'a' * 60_001
    if damage == 'identity': outer['request_hash'] = 'b'*64
    if damage not in {'base64','wire'}: outer['data'] = base64.b64encode(blob).decode('ascii')
    with pytest.raises(ValueError): m.decode_dispatch(m.encoded(outer))


def test_logical_and_dispatch_oversize_are_terminal_without_truncation(tmp_path):
    m = module(); req, result = large_result(tmp_path)
    result['output']['brief'] += 'x' * 2_000_001
    with pytest.raises(ValueError): m.encode_dispatch(result)
    assert m.process(req,run(),tmp_path/'logical',lambda *_:result['output'])['status'] == 'failed'
    req, result = large_result(tmp_path/'second')
    # Valid native prose with intentionally incompressible text within the logical cap.
    rng = random.Random(1)
    result['output']['brief'] = result['output']['brief'].replace('No material change.', rng.randbytes(90_000).hex())
    m.validate_result(req, result)
    with pytest.raises(ValueError): m.encode_dispatch(result)
    failed = m.process(req,run(),tmp_path/'dispatch',lambda *_:result['output'])
    assert failed['status'] == 'failed'
    assert failed['reason'] == 'execution_failed'
    assert m.decode_dispatch(m.encode_dispatch(failed)) == failed


def batch_input(kwargs):
    return json.loads(kwargs['messages'][0]['content'].split('INPUT ITEMS JSON:')[-1])


def test_completed_partial_batch_repairs_only_missing_ids_once():
    m = module(); raw = [{**item(), 'id':f'{i:016x}'} for i in range(24)]; calls = []
    def complete(**kw):
        batch = batch_input(kw); calls.append([r['id'] for r in batch])
        chosen = batch[:-1] if len(calls) == 1 else batch
        return json.dumps([{**classified(), 'id':r['id']} for r in chosen])
    assert len(m.classify(raw, complete)) == 24
    assert calls == [[r['id'] for r in raw], [raw[-1]['id']]]


def test_partial_batch_repair_is_bounded_and_never_repeats_completed_ids():
    m = module(); raw = [{**item(), 'id':f'{i:016x}'} for i in range(24)]; calls = []
    def complete(**kw):
        batch = batch_input(kw); calls.append([r['id'] for r in batch])
        chosen = batch[:-2] if len(calls) == 1 else batch[:-1]
        return json.dumps([{**classified(), 'id':r['id']} for r in chosen])
    with pytest.raises(ValueError, match='coverage'):
        m.classify(raw, complete)
    assert len(calls) == 2
    assert calls[1] == [r['id'] for r in raw[-2:]]


@pytest.mark.parametrize('count,expected', [(25, 2), (49, 3)])
def test_bounded_batches_cover_each_candidate_exactly_once(count, expected):
    m = module(); raw = [{**item(), 'id':f'{i:016x}'} for i in range(count)]; calls = []
    def complete(**kw):
        batch = batch_input(kw); calls.append(batch)
        assert len(batch) <= 24
        return json.dumps([{**classified(), 'id':r['id']} for r in batch])
    output = m.classify(raw, complete)
    assert len(calls) == expected
    assert [r['id'] for batch in calls for r in batch] == [r['id'] for r in raw]
    assert [r['id'] for r in output] == [r['id'] for r in raw]


def test_failed_batch_is_not_repeated_and_later_batches_do_not_run(tmp_path):
    m = module(); raw = [{**item(), 'id':f'{i:016x}'} for i in range(49)]
    req = m.make_request(run(), '2026-11-23', raw, [], []); calls = []
    def complete(**kw):
        batch = batch_input(kw); calls.append(batch)
        if len(calls) == 2: raise TimeoutError('ambiguous outcome')
        return json.dumps([{**classified(), 'id':r['id']} for r in batch])
    execute = lambda r,w:m.execute_request(r,w,complete)
    failed = m.process(req, run(), tmp_path/'state', execute)
    assert failed['status'] == 'failed'
    assert len(calls) == 2
    assert m.process(req, run(), tmp_path/'state', execute) == failed
    assert len(calls) == 2


def test_submission_file_then_state_directory_are_fsynced_before_dispatch(tmp_path, monkeypatch):
    import os
    import stat
    from test_local_model_worker import FakeGH
    m = module(); gh = FakeGH(request()); events = []; real_fsync = os.fsync
    def fsync(fd):
        info = os.fstat(fd)
        if (tmp_path/'submitted-123.json').exists():
            if stat.S_ISREG(info.st_mode): events.append('file')
            elif info.st_ino == tmp_path.stat().st_ino: events.append('directory')
        return real_fsync(fd)
    def dispatch(result):
        assert events[-2:] == ['file','directory']
        events.append('dispatch')
    monkeypatch.setattr(m.os, 'fsync', fsync)
    gh.return_result = dispatch
    m.poll_once(gh, tmp_path, lambda *_: (_ for _ in ()).throw(TimeoutError()))
    assert events[:3] == ['file','directory','dispatch']


def test_consumer_still_rejects_inconsistent_classification(tmp_path):
    m = module(); req, result = large_result(tmp_path)
    result['output']['triaged'][0]['classification'] = 'material'
    with pytest.raises(ValueError, match='contradicts'): m.validate_result(req, result)
