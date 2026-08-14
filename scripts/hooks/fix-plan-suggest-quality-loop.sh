#!/usr/bin/env bash
set -euo pipefail
# Cross-CLI hook: detect creation of FIX_PLAN.md from various CLIs (Claude, Copilot CLI, Codex, etc.)
input=$(cat)

# Quick textual search across entire input (works for JSON & plain text)
if echo "$input" | grep -iqE 'FIX[_-]?PLAN(\.md)?'; then
  # Try to extract tool name if present in JSON-like inputs
  tool_name=$(echo "$input" | jq -r '.tool_name? // .tool?.name? // .source? // ""' 2>/dev/null || true)

  # Try to extract explicit plan path from common JSON fields
  plan_path=$(echo "$input" | jq -r '.output? // .plan? // .path? // .file? // .generated? // .file_path? // .plan_path? // ""' 2>/dev/null || true)

  # Fallback: prefer docs/FIX_PLAN.md if present, otherwise any token that looks like *FIX_PLAN.md*
  if [[ -z "$plan_path" || "$plan_path" == "null" ]]; then
    plan_path=$(echo "$input" | grep -oE '[^[:space:]\"]*docs/[^[:space:]\"]*FIX[_-]?PLAN(\.md)?' | head -n1 || true)
  fi
  if [[ -z "$plan_path" || "$plan_path" == "null" ]]; then
    plan_path=$(echo "$input" | grep -oE '[^[:space:]\"]*FIX[_-]?PLAN(\.md)?' | head -n1 || true)
  fi
  if [[ -z "$plan_path" || "$plan_path" == "null" ]]; then
    plan_path="docs/FIX_PLAN.md"
  fi

  if [[ -n "$tool_name" && "$tool_name" != "null" ]]; then
    msg="FIX_PLAN.md byl právě vytvořen. Doporučeno: nabídnout spuštění /quality-loop pro automatické opravení nalezených problémů. (trigger: $tool_name)"
  else
    msg="FIX_PLAN.md byl právě vytvořen. Doporučeno: nabídnout spuštění /quality-loop pro automatické opravení nalezených problémů."
  fi

  # Build rich hook output containing suggested actions and a confirmation ask.
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg m "$msg" --arg p "$plan_path" \
      '{
        hookSpecificOutput: {
          hookEventName: "PostToolUse",
          additionalContext: $m,
          suggestedActions: [
            {type: "command", label: "Run quality-loop (dry-run)", command: ("/skills quality-loop --plan " + $p + " --dry-run")},
            {type: "command", label: "Run quality-loop (apply, no-push)", command: ("/skills quality-loop --plan " + $p + " --apply --no-push")}
          ],
          ask: {
            type: "confirm",
            title: "Spustit quality-loop?",
            description: ("Spustit quality-loop na " + $p + " (doporučeno: nejprve --dry-run)."),
            confirmCommand: ("/skills quality-loop --plan " + $p + " --dry-run")
          }
        }
      }'
  else
    # Fallback to manual JSON building (escape quotes)
    esc_msg=$(printf '%s' "$msg" | sed 's/"/\\\"/g')
    esc_p=$(printf '%s' "$plan_path" | sed 's/"/\\\"/g')
    printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"$esc_msg\",\"suggestedActions\":[{\"type\":\"command\",\"label\":\"Run quality-loop (dry-run)\",\"command\":\"/skills quality-loop --plan $esc_p --dry-run\"},{\"type\":\"command\",\"label\":\"Run quality-loop (apply, no-push)\",\"command\":\"/skills quality-loop --plan $esc_p --apply --no-push\"}],\"ask\":{\"type\":\"confirm\",\"title\":\"Spustit quality-loop?\",\"description\":\"Spustit quality-loop na $esc_p (doporučeno: nejprve --dry-run).\",\"confirmCommand\":\"/skills quality-loop --plan $esc_p --dry-run\"}}}"
  fi

  exit 0
fi

# No match — echo original input unchanged
printf '%s' "$input"
