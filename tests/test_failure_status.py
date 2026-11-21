import json
import pytest
import requests
import importlib

@pytest.fixture
def failure_status():
    return importlib.import_module('intel.failure_status')
from intel.pipeline import call_perplexity_triage
def sample_item():
    return {'id': 'test', 'title': 'Test', 'source': 'Test', 'source_url': 'https://example.com', 'published_date': '2026-11-20', 'text': 'Test'}

@pytest.mark.parametrize('codes,words,action', [([402], 'payment required', 'credits/billing'), ([429], 'rate limiting', 'limit resets'), ([402,429], 'payment required; rate limiting', 'credits/billing'), ([], 'failed', 'View the failed run')])
def test_safe_source_summary(codes, words, action, failure_status):
    receipt = failure_status.build_receipt('2026-11-20', '123', 'triage', codes, attempted_at='2026-11-20T15:00:00Z')
    assert words in receipt['summary']
    assert action in receipt['action']
    assert receipt['http_codes'] == sorted(set(codes))
    assert receipt['run_url'] == 'https://github.com/PaymentsGuy/Industry_news/actions/runs/123'
    assert 'balance' not in receipt['summary']
    assert failure_status.valid_receipt(receipt, '2026-11-20', '123')
    assert not failure_status.valid_receipt(receipt, '2026-11-19', '123')
    assert not failure_status.valid_receipt(receipt, '2026-11-20', '456')

@pytest.mark.parametrize('code', [402,429,500])
def test_triage_captures_only_safe_http_status(code):
    response = requests.Response()
    response.status_code = code
    def fail(**kwargs):
        raise requests.HTTPError('secret provider body', response=response)
    result = call_perplexity_triage(sample_item(), 'test', completion_func=fail)
    assert result.get('_provider_http_status') == code
    assert 'secret provider body' not in json.dumps(result)

def test_receipt_cli_without_delivery_package(tmp_path, monkeypatch, failure_status):
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    (tmp_path/'triaged.jsonl').write_text(json.dumps({'_provider_http_status':402})+'\n'+json.dumps({'_provider_http_status':429})+'\n')
    failure_status.write_failure(tmp_path, '2026-11-20', 'triage')
    receipt=json.loads((tmp_path/'failure-status.json').read_text())
    assert receipt['http_codes']==[402,429]
    assert not (tmp_path/'delivery.json').exists()

def test_unknown_exception_not_serialized(failure_status):
    receipt=failure_status.build_receipt('2026-11-20','123','triage',[999, 'secret'])
    assert receipt['http_codes']==[]
    assert 'secret' not in json.dumps(receipt)

def test_synthesis_keeps_all_transport_codes(tmp_path, monkeypatch, failure_status):
    from datetime import date
    from intel.pipeline import synthesize_brief
    from intel.brief_contract import BriefContractError
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    source = tmp_path / 'triaged.jsonl'
    source.write_text('')
    codes = iter([402, 429, 429])
    def fail(**kwargs):
        response = requests.Response()
        response.status_code = next(codes)
        raise requests.HTTPError('secret', response=response)
    with pytest.raises(BriefContractError):
        synthesize_brief(source, tmp_path / 'brief.md', None, completion_func=fail, brief_date=date(2026, 11, 20))
    receipt = failure_status.write_failure(tmp_path, '2026-11-20', 'synthesis')
    assert receipt['http_codes'] == [402, 429]
    assert 'secret' not in json.dumps(receipt)

def test_workflow_publishes_failure_without_delivery():
    from pathlib import Path
    import yaml
    workflow = yaml.safe_load(Path('.github/workflows/daily-intel.yml').read_text())
    steps = workflow['jobs']['brief']['steps']
    publication = next((s for s in steps if s.get('id') == 'failure_receipt'), {})
    assert 'failure()' in publication.get('if', '')
    assert 'intel.failure_status' in publication.get('run', '')
    assert 'git add "intel/${DATE}/failure-status.json"' in publication.get('run', '')
    assert 'delivery.json' not in publication.get('run', '')

@pytest.mark.parametrize('invalid', ['missing', 'date', 'run', 'unsafe'])
def test_failed_alert_fallback_and_dedup(tmp_path, failure_status, invalid):
    from test_local_scheduler import FakeGateway, DAY, now, package
    from intel.local_scheduler import Engine
    gateway = FakeGateway()
    receipt = failure_status.build_receipt(DAY, '123', 'triage', [402, 429])
    if invalid == 'date':
        receipt['brief_date'] = '2026-10-29'
    if invalid == 'run':
        receipt['workflow_run_id'] = '456'
    if invalid == 'unsafe':
        receipt['summary'] = 'secret'
    gateway.failure_status = lambda day: None if invalid == 'missing' else receipt
    gateway.run_list = [{'id':123, 'status':'completed', 'conclusion':'failure', 'created_at':'2026-10-30T13:30:00Z'}]
    engine = Engine(tmp_path, gateway, clock=now)
    engine.tick('watchdog')
    engine.tick('watchdog')
    assert len(gateway.notifications) == 1
    assert failure_status.RUN_ROOT + '123' in gateway.notifications[0]
    assert 'payment required' not in gateway.notifications[0]
    assert not gateway.dispatches
    gateway.pkg = package()
    assert engine.tick('watchdog')['stage'] == 'complete'
    assert len(gateway.notifications) == 2

def test_failed_alert_reuses_source_facts(tmp_path, failure_status):
    from test_local_scheduler import FakeGateway, DAY, now
    from intel.local_scheduler import Engine
    gateway = FakeGateway()
    receipt = failure_status.build_receipt(DAY, '123', 'triage', [402, 429])
    gateway.failure_status = lambda day: receipt
    gateway.run_list = [{'id':123, 'status':'completed', 'conclusion':'failure', 'created_at':'2026-10-30T13:30:00Z'}]
    Engine(tmp_path, gateway, clock=now).tick('watchdog')
    assert receipt['summary'] in gateway.notifications[0]
    assert receipt['action'] in gateway.notifications[0]

def test_incomplete_delivery_alert_preserves_the_source_failure(tmp_path, failure_status):
    from test_local_scheduler import FakeGateway, DAY, now, package
    from intel.local_scheduler import Engine
    gateway = FakeGateway()
    expected = failure_status.build_receipt(DAY, '123', 'slack', [])
    gateway.failure_status = lambda day: expected
    gateway.pkg = package()
    gateway.pkg['workflow_run_id'] = '123'
    gateway.pkg['status'] = 'partial_delivery'
    gateway.pkg['destinations']['repository']['status'] = 'pending'
    Engine(tmp_path, gateway, clock=now).tick('watchdog')
    assert expected['summary'] in gateway.notifications[0]
    assert expected['action'] in gateway.notifications[0]
    assert expected['run_url'] in gateway.notifications[0]
    assert not gateway.dispatches

def test_failure_publication_shell_uses_git_transport_without_delivery(tmp_path, monkeypatch):
    import os
    import subprocess
    from pathlib import Path
    import yaml
    repo = tmp_path / 'repo'
    remote = tmp_path / 'remote.git'
    repo.mkdir()
    def git(*args, cwd=repo):
        return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout
    git('init', '--bare', str(remote))
    git('init', '-b', 'main')
    git('config', 'user.name', 'test')
    git('config', 'user.email', 'test@example.com')
    (repo / 'initial').write_text('test')
    git('add', 'initial')
    git('commit', '-m', 'initial')
    git('remote', 'add', 'origin', str(remote))
    git('push', '-u', 'origin', 'main')
    folder = repo / 'intel/2026-11-20'
    folder.mkdir(parents=True)
    (folder / 'triaged.jsonl').write_text('{"_provider_http_status":402}\n{"_provider_http_status":429}\n')
    steps = yaml.safe_load(Path('.github/workflows/daily-intel.yml').read_text())['jobs']['brief']['steps']
    publication = next(s for s in steps if s.get('id') == 'failure_receipt')
    env = dict(os.environ, DATE='2026-11-20', GITHUB_RUN_ID='123', FAILED_STAGE='triage', PYTHONPATH=str(Path.cwd()))
    env['PATH'] = str(Path(__import__('sys').executable).parent) + os.pathsep + env['PATH']
    subprocess.run(['bash', '-e', '-c', publication['run']], cwd=repo, env=env, check=True, capture_output=True, text=True)
    actual = json.loads(git('show', 'main:intel/2026-11-20/failure-status.json', cwd=remote))
    assert actual['http_codes'] == [402, 429]
    assert not (folder / 'delivery.json').exists()
    assert not any(step.get('continue-on-error') for step in steps)
