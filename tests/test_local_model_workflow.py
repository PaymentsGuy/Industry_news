from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_daily_routes_inference_to_request_and_await_without_paid_secrets():
    text = (ROOT/'.github/workflows/daily-intel.yml').read_text()
    assert 'PERPLEXITY_API_KEY' not in text
    assert 'intel.local_model_worker prepare' in text
    assert 'intel.local_model_worker await' in text
    assert 'pulse-request-${{ github.run_id }}-${{ github.run_attempt }}' in text
    assert 'actions: read' in text
    assert 'intel.pipeline triage' not in text
    assert 'intel.pipeline synthesize' not in text
    assert 'intel.pipeline collect' in text
    assert 'intel.update_ledger' in text
    assert 'intel.delivery create' in text
    assert 'intel.delivery resume-slack' in text


def test_result_workflow_cannot_execute_input_as_shell():
    text = (ROOT/'.github/workflows/pulse-model-result.yml').read_text()
    assert 'PULSE_RESULT: ${{ inputs.result }}' in text
    assert 'intel.local_model_worker receive' in text
    assert 'path: result.json' in text
    assert 'actions: read' in text
    assert 'contents: read' in text
    assert 'secrets.' not in text
    assert 'run: ${{' not in text


def test_worker_templates_do_not_replace_existing_owners():
    text = (ROOT/'scripts/run_local_model_worker').read_text()
    assert 'intel.local_model_worker poll' in text
    assert 'PULSE_WORKER_STATE' in text
    assert 'git pull' not in text
    assert (ROOT/'deploy/local-model-worker.plist.in').is_file()
    assert (ROOT/'deploy/pulse-hermes-config.yaml').is_file()
