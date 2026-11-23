"""No network or inference: production protocol exercised with fake GH transport."""
import copy
import json
import subprocess
from pathlib import Path

import pytest
from intel import failure_status


def module():
    from intel import local_model_worker
    return local_model_worker


def run():
    return dict(id=123, run_attempt=1, head_sha='a' * 40, head_branch='main',
                event='workflow_dispatch', status='in_progress',
                path='.github/workflows/daily-intel.yml', repository={'full_name': 'PaymentsGuy/Industry_news'})


def item():
    return dict(id='a' * 16, title='Public news', source='Publisher',
                source_url='https://example.org/news', published_date='2026-11-23T10:00:00Z', text='Public article', fetch_method='rss')


def request():
    m = module()
    return m.make_request(run(), '2026-11-23', [item()], [], [])


def classified():
    return dict(id='a' * 16, watchlist_bucket='none', watchlist_entity=None,
                signal_type='other', roadmap_areas=[], relevance_score=0,
                headline_paraphrase='Public news.', why_it_matters_for_asa='No material signal.',
                uncertainty_flags=[], duplicate_of_id=None, classification='noise')


def test_protocol_module_exists():
    assert module().REPO == 'PaymentsGuy/Industry_news'


@pytest.mark.parametrize('field,value', [('id', 124), ('run_attempt', 2), ('head_sha', 'b'*40),
    ('head_branch', 'other'), ('path', '.github/workflows/weekly-intel.yml'), ('event', 'pull_request'),
    ('repository', {'full_name': 'evil/Industry_news'})])
def test_wrong_run_rejected_before_inference(tmp_path, field, value):
    m = module(); req = request(); observed = run(); observed[field] = value
    calls = []
    with pytest.raises(ValueError):
        m.process(req, observed, tmp_path, lambda r, p: calls.append(r))
    assert calls == []


def test_tampered_hash_rejected(tmp_path):
    m = module(); req = request(); req['raw'][0]['text'] = 'changed'
    with pytest.raises(ValueError):
        m.process(req, run(), tmp_path, lambda *_: pytest.fail('inference'))


def test_claim_durable_before_inference_and_duplicate_never_repeats(tmp_path):
    m = module(); req = request(); calls = []
    def execute(r, work):
        claims = list((tmp_path / 'claims').glob('*.json'))
        assert len(claims) == 1
        assert json.loads(claims[0].read_text())['status'] == 'unknown'
        calls.append(1)
        raise TimeoutError('sensitive token must not escape')
    result = m.process(req, run(), tmp_path, execute)
    assert result['status'] == 'failed'
    assert 'sensitive' not in json.dumps(result)
    assert failure_status.valid_receipt(result['failure'], '2026-11-23', '123')
    assert m.process(req, run(), tmp_path, execute) == result
    assert calls == [1]


def test_crash_unknown_claim_blocks_automatic_repeat(tmp_path):
    m = module(); req = request()
    def crash(*_):
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        m.process(req, run(), tmp_path, crash)
    result = m.process(req, run(), tmp_path, lambda *_: pytest.fail('repeat'))
    assert result['status'] == 'failed'
    assert result['reason'] == 'execution_unknown'


def test_changed_request_same_run_blocks_repeat(tmp_path):
    m = module(); req = request()
    m.process(req, run(), tmp_path, lambda *_: (_ for _ in ()).throw(TimeoutError()))
    changed = m.make_request(run(), '2026-11-23', [{**item(), 'text': 'changed'}], [], [])
    with pytest.raises(ValueError, match='claim'):
        m.process(changed, run(), tmp_path, lambda *_: pytest.fail('repeat'))


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'wrong_id', 'score', 'extra', 'bucket'])
def test_batch_requires_exact_schema_and_coverage(mutation):
    m = module(); rows = [classified()]
    if mutation == 'missing': rows = []
    if mutation == 'duplicate': rows *= 2
    if mutation == 'wrong_id': rows[0]['id'] = 'b'*16
    if mutation == 'score': rows[0]['relevance_score'] = True
    if mutation == 'extra': rows[0]['command'] = 'execute'
    if mutation == 'bucket': rows[0]['watchlist_bucket'] = 'unknown'
    with pytest.raises(ValueError): m.validate_classifications(rows, [item()])


def test_batch_classification_uses_one_fixed_model_call():
    m = module(); calls = []
    def complete(**kwargs):
        calls.append(kwargs); return json.dumps([classified()])
    result = m.classify([item()], complete)
    assert len(calls) == 1
    assert calls[0]['model'] == 'gpt-6-luna'
    assert result[0]['_source_item'] == item()
    assert result[0]['classification'] == 'noise'


def test_native_synthesis_exact_model_no_paid_fallback(monkeypatch, tmp_path):
    m = module(); calls = []
    def native(in_file, out_file, prior, registry, **kwargs):
        calls.append(kwargs)
        assert json.loads(prior.read_text()) == []
        assert json.loads(registry.read_text()) == []
        kwargs['completion_func'](model='sonar-pro', messages=[{'role':'user','content':'fixed native prompt'}])
        out_file.write_text('native validated output')
        (out_file.parent / 'synthesis-dispositions.json').write_text('{}')
    monkeypatch.setattr(m.pipeline, 'synthesize_brief', native)
    models = []
    def complete(**kw):
        models.append(kw['model'])
        return json.dumps([classified()]) if kw['model'] == 'gpt-6-luna' else 'output'
    result = m.execute_request(request(), tmp_path, complete)
    assert models == ['gpt-6-luna', 'gpt-6.1-sol']
    assert result['brief'] == 'native validated output'


def test_hermes_invocation_is_bounded_toolless_and_exact(monkeypatch, tmp_path):
    m = module(); calls = []
    (tmp_path / 'config.yaml').write_text('fallback_providers: []\n')
    def launch(argv, **kwargs):
        calls.append((argv, kwargs))
        if '--print-runtime-command' in argv:
            return subprocess.CompletedProcess(argv, 0, json.dumps(['/python','-I','-c',"import runpy; runpy.run_module('runpy', run_name='__main__', alter_sys=True)"]), '')
        return subprocess.CompletedProcess(argv, 0, json.dumps({'text':'[]','model':'gpt-6-luna','provider':'openai-codex'}), '')
    monkeypatch.setattr(m.subprocess, 'run', launch)
    assert m.hermes_completion(model='gpt-6-luna', messages=[{'role':'user','content':'public news'}], home=tmp_path) == '[]'
    argv, kw = calls[-1]
    assert argv[:3] == ['/python','-I','-c']
    assert 'codex_inference.py' in argv[3]
    assert kw['timeout'] <= 300
    assert json.loads(kw['input'])['model'] == 'gpt-6-luna'
    assert kw['env']['HERMES_HOME'] == str(tmp_path)
    assert 'OPENAI_API_KEY' not in kw['env']
    with pytest.raises(ValueError): m.hermes_completion(model='sonar', messages=[], home=tmp_path)


@pytest.mark.parametrize('tools,finish', [([{'name':'terminal'}], 'stop'), (None,'length')])
def test_native_codex_tools_and_incomplete_rejected(tools, finish):
    from intel.codex_inference import infer
    from types import SimpleNamespace as S
    class Raw:
        base_url = 'https://chatgpt.com/backend-api/codex'
        def with_options(self, **kw): assert kw == {'max_retries':0}; return self
        def close(self): pass
    class Adapter:
        def __init__(self, raw, model): self.chat = S(completions=self)
        def create(self, **kw):
            assert kw['tools'] == []
            return S(model=kw['model'], choices=[S(finish_reason=finish,message=S(tool_calls=tools,content='[]'))])
        def close(self): pass
    with pytest.raises(ValueError):
        infer('gpt-6-luna', [], resolver=lambda *a,**kw:(Raw(),'gpt-6-luna'), adapter=Adapter)


def test_fixed_result_payload_rejects_wrong_hash_or_arbitrary_writes(tmp_path):
    m = module(); req = request()
    result = m.failed_result(req, 'execution_failed')
    changed = copy.deepcopy(result); changed['request_hash'] = 'b'*64
    with pytest.raises(ValueError): m.accept_result(req, changed, tmp_path)
    changed = copy.deepcopy(result); changed['files'] = {'../../config': 'bad'}
    with pytest.raises(ValueError): m.accept_result(req, changed, tmp_path)
    with pytest.raises(RuntimeError): m.accept_result(req, result, tmp_path)
    assert (tmp_path/'failure-status.json').exists()


class FakeGH:
    def __init__(self, req): self.req = req; self.results = []; self.dispatches = 0
    def pending(self): return [run()]
    def request(self, observed): return self.req
    def return_result(self, result): self.dispatches += 1; self.results.append(copy.deepcopy(result))
    def result(self, req): return self.results[-1] if self.results else None


def test_fake_github_roundtrip_timeout_and_replay(tmp_path):
    m = module(); req = request(); gh = FakeGH(req); calls=[]
    def infer(*_): calls.append(1); raise TimeoutError()
    m.poll_once(gh, tmp_path, infer)
    m.poll_once(gh, tmp_path, infer)
    assert calls == [1]
    assert gh.dispatches == 1
    with pytest.raises(RuntimeError): m.await_result(req, gh, tmp_path/'out', timeout=0.01, interval=0)
    assert failure_status.valid_receipt(json.loads((tmp_path/'out/failure-status.json').read_text()),'2026-11-23','123')
    empty = FakeGH(req)
    with pytest.raises(TimeoutError): m.await_result(req, empty, tmp_path/'empty', timeout=0, interval=0)


def test_codex_receipt_preserves_legacy_validation():
    receipt = failure_status.build_receipt('2026-11-23','123','synthesis',[],provider='OpenAI Codex')
    assert failure_status.valid_receipt(receipt,'2026-11-23','123')
    assert receipt['provider'] == 'OpenAI Codex'
    old = failure_status.build_receipt('2026-11-23','123','synthesis',[402])
    assert old['provider'] == 'Perplexity'
    assert failure_status.valid_receipt(old,'2026-11-23','123')


def test_codex_failure_is_not_overwritten_by_workflow_handler(monkeypatch, tmp_path):
    monkeypatch.setenv('GITHUB_RUN_ID','123')
    monkeypatch.setenv('PULSE_MODEL_BACKEND','codex')
    existing = failure_status.build_receipt('2026-11-23','123','synthesis',[],provider='OpenAI Codex')
    (tmp_path/'failure-status.json').write_text(json.dumps(existing))
    assert failure_status.write_failure(tmp_path,'2026-11-23','synthesis') == existing


def test_workflow_timeout_receipt_names_subscription_provider(monkeypatch, tmp_path):
    monkeypatch.setenv('GITHUB_RUN_ID','123')
    monkeypatch.setenv('PULSE_MODEL_BACKEND','codex')
    assert failure_status.write_failure(tmp_path,'2026-11-23','synthesis')['provider'] == 'OpenAI Codex'


def test_real_native_pipeline_and_fake_github_success(tmp_path):
    m = module(); req = request(); gh = FakeGH(req); calls = []
    quiet = ('# ASA Industry News Pulse — 2026-11-23\n\n'
             '## Top summary\n\nNo material change.\n\n'
             '## Material signals\n\nNo evidence-backed material signals in this interval.\n\n'
             '## Candidate disposition\n\nAll candidates were classified.\n\n## References\n')
    def complete(**kwargs):
        calls.append(kwargs['model'])
        return json.dumps([classified()]) if kwargs['model'] == 'gpt-6-luna' else quiet
    m.poll_once(gh, tmp_path/'state', lambda r,w: m.execute_request(r,w,complete))
    assert gh.results[-1]['status'] == 'succeeded'
    m.await_result(req, gh, tmp_path/'out', timeout=1, interval=0)
    assert calls == ['gpt-6-luna','gpt-6.1-sol']
    assert json.loads((tmp_path/'out/triaged.jsonl').read_text())['_source_item'] == item()
    assert '**Candidates classified:** 1' in (tmp_path/'out/brief.md').read_text()
    assert (tmp_path/'out/synthesis-dispositions.json').is_file()
    m.poll_once(gh, tmp_path/'state', lambda *_: pytest.fail('repeat inference'))
    assert gh.dispatches == 1


def test_native_transport_timeout_never_retries(tmp_path):
    m = module(); calls = []
    def complete(**kw):
        calls.append(kw['model'])
        if kw['model'] == 'gpt-6-luna': return json.dumps([classified()])
        raise TimeoutError('outcome unknown')
    result = m.process(request(), run(), tmp_path/'state', lambda r,w:m.execute_request(r,w,complete))
    assert result['status'] == 'failed'
    assert calls == ['gpt-6-luna','gpt-6.1-sol']


def test_archive_allowlist_and_ambiguous_artifacts():
    import io, zipfile
    m = module(); gh = m.GitHub()
    def blob(name):
        data = io.BytesIO()
        with zipfile.ZipFile(data,'w') as z: z.writestr(name, json.dumps(request()))
        return data.getvalue()
    listing = {'total_count':1,'artifacts':[{'id':42,'name':'expected','expired':False,'size_in_bytes':1000}]}
    seen = []
    def api(path, payload=None, binary=False):
        seen.append(path)
        return blob('../request.json') if binary else listing
    gh.api = api
    with pytest.raises(ValueError,match='archive'):
        gh.artifact(123,'expected','request.json')
    listing['artifacts'] *= 2
    with pytest.raises(ValueError,match='ambiguous'):
        gh.artifact(123,'expected','request.json')
    assert all(p.startswith('repos/PaymentsGuy/Industry_news/actions/') for p in seen)


def test_safe_result_submission_unknown_blocks_repost(tmp_path):
    m = module(); gh = FakeGH(request()); calls=[]
    def lost(result): calls.append(result); raise TimeoutError('POST may have succeeded')
    gh.return_result = lost
    with pytest.raises(TimeoutError):
        m.poll_once(gh,tmp_path,lambda *_: (_ for _ in ()).throw(TimeoutError()))
    m.poll_once(gh,tmp_path,lambda *_:pytest.fail('repeat inference'))
    assert len(calls) == 1


def test_native_endpoint_and_model_fail_closed():
    from intel.codex_inference import infer
    class Raw:
        base_url = 'https://api.openai.com/v1'
        def close(self): pass
    with pytest.raises(ValueError,match='endpoint'):
        infer('gpt-6-luna',[],resolver=lambda *a,**k:(Raw(),'gpt-6-luna'),adapter=lambda *_:pytest.fail('paid route'))


def test_worker_rechecks_run_before_claim(tmp_path):
    m = module(); gh = FakeGH(request())
    def request_after_cancel(observed):
        observed['status'] = 'completed'
        return gh.req
    gh.request = request_after_cancel
    with pytest.raises(ValueError): m.poll_once(gh,tmp_path,lambda *_:pytest.fail('cancelled inference'))


def test_expired_request_is_rejected_before_claim(monkeypatch, tmp_path):
    m = module(); req = request()
    monkeypatch.setattr(m.time,'time',lambda:req['deadline_unix'] + 1)
    with pytest.raises(ValueError,match='deadline'):
        m.process(req,run(),tmp_path,lambda *_:pytest.fail('expired inference'))
    assert not (tmp_path/'claims').exists()


def material_result(tmp_path):
    m = module(); raw = [item(),{**item(),'id':'b'*16,'title':'Second public news'}]
    req = m.make_request(run(),'2026-11-23',raw,[],[])
    rows = [{**classified(),'id':r['id'],'relevance_score':2,'classification':'material'} for r in raw]
    brief = ('# ASA Industry News Pulse — 2026-11-23\n\n## Top summary\n\nPublic signal.\n\n'
             '## Material signals\n\n### Signal 1\n\nPublic change [REF 1].\n\n'
             '## Candidate disposition\n\nBoth candidates classified; second duplicates first.\n\n'
             '<!-- candidate-dispositions: {"1":"material","2":"duplicate:1"} -->\n\n## References\n')
    def complete(**kw): return json.dumps(rows) if kw['model'] == 'gpt-6-luna' else brief
    result = m.process(req,run(),tmp_path/'state',lambda r,w:m.execute_request(r,w,complete))
    assert result['status'] == 'succeeded'
    return req,result


def test_native_material_dispositions_roundtrip(tmp_path):
    m = module(); req,result = material_result(tmp_path)
    m.accept_result(req,result,tmp_path/'out')
    assert result['output']['dispositions']['classification_counts']['duplicate'] == 1
    assert 'https://example.org/news' in (tmp_path/'out/brief.md').read_text()


@pytest.mark.parametrize('change',['date','counts'])
def test_result_metadata_is_source_bound(tmp_path,change):
    m = module(); req,result = material_result(tmp_path)
    if change == 'date':
        result['output']['brief'] = result['output']['brief'].replace('Pulse — 2026-11-23','Pulse — 2026-11-24')
    else:
        result['output']['brief'] = result['output']['brief'].replace('classified:** 2','classified:** 3').replace('monitor=0','monitor=1')
    with pytest.raises(ValueError): m.accept_result(req,result,tmp_path/'out')


def test_github_poll_requires_exact_active_brief_job():
    m = module(); gh = m.GitHub(); jobs = [{'name':'not-the-brief','status':'in_progress','run_id':123}]
    def api(suffix, **kw):
        return {'total_count':len(jobs),'jobs':jobs} if '/jobs?' in suffix else {'workflow_runs':[run()]}
    gh.api = api
    assert gh.pending() == []
    jobs[0]['name'] = 'brief'
    assert gh.pending() == [run()]
