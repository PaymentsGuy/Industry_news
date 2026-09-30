from pathlib import Path


def test_daily_slack_reconciliation_only_reads_existing_delivery_and_commits_receipt():
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "reconcile-daily-slack.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "concurrency:" in workflow
    assert "group: daily-intel" in workflow
    assert "python -m intel.delivery resume-slack" in workflow
    assert "git add intel/${DATE}/delivery.json" in workflow
    assert "intel.pipeline" not in workflow
    assert "intel.delivery create" not in workflow
    assert "intel.delivery mark-repository" not in workflow
