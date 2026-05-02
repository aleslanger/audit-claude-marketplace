from scripts.quality_loop import simulate_run


def test_simulate_runs_all_resolved():
    summary = simulate_run('tests/fixtures/sample_FIX_PLAN.md', threshold=95, dry_run=True, apply=False)
    assert summary['total'] == 2
    assert summary['resolved'] >= 1
    assert summary['cleanliness_percent'] >= 50.0
