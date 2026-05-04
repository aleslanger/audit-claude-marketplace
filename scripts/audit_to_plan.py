#!/usr/bin/env python3
"""Simulated audit-to-plan CLI that writes a FIX_PLAN.md.

Default output path is docs/FIX_PLAN.md. The script creates the docs/ directory
if it doesn't exist and writes a small, well-formed FIX_PLAN.md suitable for
consumption by the quality-loop runner and tests.
"""

import argparse
import datetime
from pathlib import Path
import json


SAMPLE_TEMPLATE = """# Fix Plan — {project}
Generated: {timestamp}
Scope: {scope} — {files}
Total issues: {total} (CRITICAL: {critical} · HIGH: {high} · MEDIUM: {medium} · LOW: {low})

---

## Critical

### [CRITICAL] ISSUE-001 — Unsafe SQL construction
- **ID:** `ISSUE-001`
- **File:** `app/query.py:42`
- **Problem:** Unsafe string interpolation into SQL query allows injection
- **Fix:** Use parameterized queries (db.execute(query, params))
- **Status:** `open`

---

## High

### [HIGH] ISSUE-002 — Use of eval on untrusted data
- **ID:** `ISSUE-002`
- **File:** `scripts/build.py:10`
- **Problem:** `eval` is used on input that may be attacker-controlled
- **Fix:** Replace eval with ast.literal_eval or a safer parser
- **Status:** `open`
"""


def main():
    parser = argparse.ArgumentParser(description='Simulated audit-to-plan generator')
    parser.add_argument('--output', '-o', default='docs/FIX_PLAN.md', help='Path to write FIX_PLAN.md (default: docs/FIX_PLAN.md)')
    parser.add_argument('--scope', choices=['diff', 'full'], default='diff', help='Audit scope')
    parser.add_argument('--project', default=None, help='Project name to include in header')
    parser.add_argument('--template', default=None, help='Path to use as template (copy contents)')
    parser.add_argument('--write-json', action='store_true', help='Also write FIX_PLAN.json next to the md')
    args = parser.parse_args()

    out_path = Path(args.output)
    out_dir = out_path.parent
    if not out_dir.exists():
        out_dir.mkdir(parents=True, exist_ok=True)

    if args.template:
        # Copy template verbatim
        src = Path(args.template)
        if not src.exists():
            raise SystemExit(f'Template not found: {src}')
        content = src.read_text(encoding='utf-8')
    else:
        timestamp = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        project = args.project or Path('.').resolve().name
        # Use small, deterministic issue counts for now
        total = 2
        critical = 1
        high = 1
        medium = 0
        low = 0
        files = 2
        content = SAMPLE_TEMPLATE.format(project=project, timestamp=timestamp, scope=args.scope, files=files, total=total, critical=critical, high=high, medium=medium, low=low)

    out_path.write_text(content, encoding='utf-8')
    print(f'Wrote {out_path}')

    if args.write_json:
        try:
            # import local parser to convert to JSON if available
            from scripts.fix_plan_parser import write_fix_plan_json
            json_path = out_path.with_suffix('.json')
            write_fix_plan_json(str(out_path), str(json_path))
            print(f'Wrote {json_path}')
        except Exception as e:
            print('Could not write JSON:', e)


if __name__ == '__main__':
    main()
