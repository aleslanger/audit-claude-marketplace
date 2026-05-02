#!/usr/bin/env python3
"""FIX_PLAN.md parser and JSON writer used by the quality-loop reference runner and tests.

Simple, defensive parsing suitable for the SKILL.md-generated FIX_PLAN.md format used here.
"""

import re
import json
from pathlib import Path
from typing import List,Dict

HEADING_RE = re.compile(r"^\s*###\s*\[(?P<severity>[A-Z]+)\]\s*(?P<id>ISSUE-\d+)(?:\s*[—-]\s*(?P<title>.*))?", re.M)
FIELD_RE = re.compile(r"^-\s*\*\*(?P<field>[^*]+?)\*\*\s*(?::)?\s*(?P<value>.+)$")


def parse_fix_plan_md(path: str) -> List[Dict]:
    """Parse a FIX_PLAN.md file and return a list of issue dicts.

    Each issue dict contains: id, severity, title, file, problem, fix, status
    """
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    lines = text.splitlines()
    issues = []
    i = 0
    while i < len(lines):
        m = HEADING_RE.match(lines[i])
        if m:
            severity = m.group('severity')
            id_ = m.group('id')
            title = (m.group('title') or '').strip()
            i += 1
            block_lines = []
            while i < len(lines) and not HEADING_RE.match(lines[i]):
                block_lines.append(lines[i])
                i += 1
            fields = {}
            for bl in block_lines:
                bls = bl.strip()
                fm = FIELD_RE.match(bls)
                if fm:
                    field = fm.group('field').strip().rstrip(':')
                    value = fm.group('value').strip().strip('`').strip()
                    fields[field] = value
            issues.append({
                'id': fields.get('ID', id_),
                'severity': severity,
                'title': title,
                'file': fields.get('File'),
                'problem': fields.get('Problem'),
                'fix': fields.get('Fix'),
                'status': fields.get('Status', 'open'),
            })
        else:
            i += 1
    return issues


def parse_fix_plan_json(path: str) -> List[Dict]:
    p = Path(path)
    data = json.loads(p.read_text(encoding='utf-8'))
    return data


def write_fix_plan_json(md_path: str, json_path: str) -> None:
    issues = parse_fix_plan_md(md_path)
    Path(json_path).write_text(json.dumps(issues, indent=2), encoding='utf-8')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Write FIX_PLAN.json from FIX_PLAN.md')
    parser.add_argument('--md', help='input FIX_PLAN.md path', required=True)
    parser.add_argument('--json', help='output FIX_PLAN.json path', required=True)
    args = parser.parse_args()
    write_fix_plan_json(args.md, args.json)
    print(f'Wrote {args.json}')
