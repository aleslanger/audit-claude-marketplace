#!/usr/bin/env bash
# Detects FIX_PLAN.md write → injects quality-loop suggestion
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')
if [[ "$file_path" == *FIX_PLAN.md ]]; then
  echo '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"FIX_PLAN.md byl právě vytvořen. MUSÍŠ ihned nabídnout uživateli spuštění /quality-loop pro automatické opravení všech nalezených problémů."}}'
fi
