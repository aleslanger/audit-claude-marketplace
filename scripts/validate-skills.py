#!/usr/bin/env python3
"""Validate that every SKILL.md has required frontmatter fields."""

import sys
import re
from pathlib import Path

REQUIRED_FIELDS = {"name", "description"}
SKILL_GLOB = "skills/*/SKILL.md"

def parse_frontmatter(text):
    """Return dict of frontmatter fields, or None if no frontmatter."""
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip().strip("'\"")
    return fields

def main():
    root = Path(__file__).parent.parent
    skills = sorted(root.glob(SKILL_GLOB))

    if not skills:
        print("ERROR: no SKILL.md files found under skills/")
        sys.exit(1)

    errors = []
    for path in skills:
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        rel = path.relative_to(root)
        if fm is None:
            errors.append(f"{rel}: missing YAML frontmatter (expected --- block at top)")
            continue
        for field in REQUIRED_FIELDS:
            if field not in fm or not fm[field]:
                errors.append(f"{rel}: missing required frontmatter field '{field}'")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)

    print(f"OK: {len(skills)} skill(s) validated")
    for p in skills:
        print(f"  - {p.relative_to(root)}")

if __name__ == "__main__":
    main()
