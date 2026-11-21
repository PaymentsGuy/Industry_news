"""Safe, producer-owned terminal failure facts; no provider response text."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone, date
from pathlib import Path

RUN_ROOT = 'https://github.com/PaymentsGuy/Industry_news/actions/runs/'
STAGES = {'collect', 'triage', 'synthesis', 'ledger', 'delivery', 'repository', 'slack', 'workflow'}


def http_status(error):
    value = getattr(getattr(error, 'response', None), 'status_code', None)
    return value if type(value) is int and 400 <= value <= 599 else None


def build_receipt(report_date, run_id, stage, codes, *, attempted_at=None):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', report_date):
        raise ValueError('invalid report date')
    date.fromisoformat(report_date)
    run_id = str(run_id)
    if not re.fullmatch(r'[1-9]\d*', run_id) or stage not in STAGES:
        raise ValueError('invalid run identity or stage')
    codes = sorted({code for code in codes if type(code) is int and 400 <= code <= 599})
    provider = 'Perplexity' if stage in {'triage', 'synthesis'} else 'Industry Pulse'
    if 402 in codes:
        summary = f'{provider} rejected requests: payment required' + ('; rate limiting also occurred.' if 429 in codes else '.')
        action = f'Check {provider} credits/billing. Once resolved, explicitly retry the failed Pulse.'
    elif 429 in codes:
        summary = f'{provider} rejected requests: rate limiting.'
        action = 'Wait until the rate limit resets, then explicitly retry the failed Pulse.'
    else:
        summary = f'{provider} {stage} stage failed.'
        action = 'View the failed run, resolve the reported issue, then explicitly retry the failed Pulse.'
    attempted_at = attempted_at or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    if datetime.fromisoformat(attempted_at.replace('Z', '+00:00')).tzinfo is None:
        raise ValueError('attempt time must include timezone')
    return dict(schema_version=1, producer='industry_news', status='failed',
                brief_id=f'industry-pulse-{report_date}', brief_date=report_date,
                workflow_run_id=run_id, run_url=RUN_ROOT + run_id,
                attempted_at=attempted_at, stage=stage, provider=provider,
                http_codes=codes, summary=summary, action=action)


def valid_receipt(value, report_date, run_id):
    try:
        return isinstance(value, dict) and value == build_receipt(
            report_date, str(run_id), value['stage'], value['http_codes'], attempted_at=value['attempted_at'])
    except (KeyError, ValueError, TypeError):
        return False


def write_failure(out_dir, report_date, stage):
    out_dir = Path(out_dir)
    codes = []
    triaged = out_dir / 'triaged.jsonl'
    if stage in {'triage', 'synthesis'} and triaged.exists():
        for line in triaged.read_text().splitlines():
            try:
                codes.append(json.loads(line).get('_provider_http_status'))
            except (ValueError, AttributeError):
                continue
    evidence = out_dir / 'provider-errors.json'
    if stage == 'synthesis' and evidence.exists():
        value = json.loads(evidence.read_text())
        if value.get('workflow_run_id') == os.environ.get('GITHUB_RUN_ID'):
            codes.extend(value.get('http_codes', []))
    receipt = build_receipt(report_date, os.environ.get('GITHUB_RUN_ID', ''), stage, codes)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'failure-status.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--report-date', required=True)
    parser.add_argument('--stage', choices=sorted(STAGES), required=True)
    args = parser.parse_args()
    write_failure(args.out_dir, args.report_date, args.stage)


if __name__ == '__main__':
    main()
