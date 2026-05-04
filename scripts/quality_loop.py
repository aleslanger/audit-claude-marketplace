#!/usr/bin/env python3
"""Reference quality-loop runner (safe, default dry-run).

This script implements a conservative, reference implementation of the quality-loop
workflow described in the skill. By default it runs in dry-run mode and will not
modify the repository. Use --apply to enable commit simulation; real auto-fixes
are not implemented here — the runner demonstrates selection, ordering, and
plan updates and provides hooks where real fixes could be applied.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List
from scripts.fix_plan_parser import parse_fix_plan_md, parse_fix_plan_json, write_fix_plan_json

SEVERITY_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ORDER[::-1], 1)}  # LOW=1 .. CRITICAL=4


def load_plan(path: str) -> List[Dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    if p.suffix.lower() == '.json':
        return parse_fix_plan_json(str(p))
    else:
        return parse_fix_plan_md(str(p))


def select_next_issue(issues: List[Dict]) -> Dict:
    open_issues = [i for i in issues if i.get('status','open') == 'open']
    if not open_issues:
        return None
    # sort by severity (CRITICAL first), then by ID
    def keyfn(issue):
        sev_rank = SEVERITY_ORDER.index(issue.get('severity','LOW')) if issue.get('severity') in SEVERITY_ORDER else len(SEVERITY_ORDER)-1
        try:
            num = int(issue.get('id','ISSUE-0').split('-')[1])
        except Exception:
            num = 0
        return (sev_rank, num)
    open_issues.sort(key=keyfn)
    # highest severity first -> reverse
    return open_issues[0]


def simulate_run(plan_path: str, threshold: int = 95, dry_run: bool = True, apply: bool = False, branch_strategy: str = 'use-unique-suffix') -> Dict:
    issues = load_plan(plan_path)
    total = len([i for i in issues if i.get('status','open') == 'open'])
    if total == 0:
        return {'total': 0, 'resolved': 0, 'blocked': 0, 'skipped': 0}
    resolved = 0
    blocked = 0
    attempts = {i['id']: 0 for i in issues}

    def cleanliness(resolved, total, blocked):
        denom = max(1, total - blocked)
        return (resolved / denom) * 100.0

    # simple deterministic loop: mark each as resolved (simulation)
    for issue in [i for i in issues if i.get('status','open') == 'open']:
        issue_id = issue.get('id')
        # Simulation: pretend we apply the minimal fix and it succeeds
        attempts[issue_id] += 1
        if not dry_run and apply:
            # Placeholder: real apply logic would go here
            # For safety, we do not change files by default
            pass
        issue['status'] = 'resolved'
        resolved += 1
        current_clean = cleanliness(resolved, total, blocked)
        if current_clean >= threshold:
            break

    # After loop, build result
    summary = {
        'total': total,
        'resolved': resolved,
        'blocked': blocked,
        'skipped': max(0, total - resolved - blocked),
        'cleanliness_percent': round(cleanliness(resolved, total, blocked), 2),
        'issues': issues,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description='Reference quality-loop runner (dry-run by default)')
    parser.add_argument('--plan', default='docs/FIX_PLAN.md', help='Path to FIX_PLAN.md or FIX_PLAN.json')
    parser.add_argument('--threshold', type=int, default=95, help='Threshold percent to stop at')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Do not modify files or commit')
    parser.add_argument('--apply', action='store_true', default=False, help='Enable apply-mode (potentially make commits)')
    parser.add_argument('--no-push', action='store_true', default=True, help='Do not push branch to origin even if apply is used')
    parser.add_argument('--branch-strategy', choices=['use-unique-suffix','abort','force-delete'], default='use-unique-suffix')
    parser.add_argument('--write-json', action='store_true', default=False, help='Write FIX_PLAN.json from FIX_PLAN.md when plan is md')
    args = parser.parse_args()

    plan_path = args.plan
    if args.write_json and plan_path.lower().endswith('.md'):
        write_path = Path(plan_path).with_suffix('.json')
        write_fix_plan_json = write_path
        from scripts.fix_plan_parser import write_fix_plan_json as _write
        _write(plan_path, str(write_path))
        print(f'Wrote {write_path}')

    summary = simulate_run(plan_path, threshold=args.threshold, dry_run=args.dry_run, apply=args.apply, branch_strategy=args.branch_strategy)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
