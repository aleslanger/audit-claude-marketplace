import json
import subprocess
from pathlib import Path

HOOK = "scripts/hooks/fix-plan-suggest-quality-loop.sh"


def run_hook(input_text: str) -> str:
    p = subprocess.run(["bash", HOOK], input=input_text.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # If the script exits non-zero, include stderr in the assertion to aid debugging
    if p.returncode != 0:
        raise RuntimeError(f"Hook script failed: returncode={p.returncode} stderr={p.stderr.decode('utf-8')}")
    return p.stdout.decode('utf-8')


def test_hook_output_contains_suggested_actions_and_ask():
    sample = '{"tool_name":"audit-to-plan","output":"docs/FIX_PLAN.md","content":"Created docs/FIX_PLAN.md with issues"}'
    out = run_hook(sample)
    data = json.loads(out)
    assert "hookSpecificOutput" in data
    h = data["hookSpecificOutput"]
    assert isinstance(h.get("suggestedActions"), list)
    assert isinstance(h.get("ask"), dict)
    commands = [a.get("command", "") for a in h.get("suggestedActions", [])]
    assert any("docs/FIX_PLAN.md" in c for c in commands)
    assert "docs/FIX_PLAN.md" in h["ask"].get("confirmCommand", "")
