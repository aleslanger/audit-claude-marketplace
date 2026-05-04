#!/usr/bin/env bash
set -euo pipefail
# Cross-CLI hook: detect creation of FIX_PLAN.md from various CLIs (Claude, Copilot CLI, Codex, etc.)
input=$(cat)

# Quick textual search across entire input (works for JSON & plain text)
if echo "$input" | grep -iqE 'FIX[_-]?PLAN(\\.md)?'; then
  # Try to extract tool name if present in JSON-like inputs
  tool_name=$(echo "$input" | jq -r '.tool_name? // .tool?.name? // .source? // ""' 2>/dev/null || true)
  if [[ -n "$tool_name" && "$tool_name" != "null" ]]; then
    msg="FIX_PLAN.md byl právě vytvořen. Doporučeno: nabídnout spuštění /quality-loop pro automatické opravení nalezených problémů. (trigger: $tool_name)"
  else
    msg="FIX_PLAN.md byl právě vytvořen. Doporučeno: nabídnout spuštění /quality-loop pro automatické opravení nalezených problémů."
  fi

  if command -v jq >/dev/null 2>&1; then
    jq -n --arg m "$msg" '{hookSpecificOutput:{hookEventName:"PostToolUse", additionalContext:$m}}'
  else
    esc_msg=$(printf '%s' "$msg" | sed 's/"/\\\"/g')
    printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"$esc_msg\"}}"
  fi

  exit 0
fi

# No match — echo original input unchanged
printf '%s' "$input"
