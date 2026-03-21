#!/bin/bash
# PreToolUse hook: auto-review staged changes before git commit

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only trigger on git commit commands
if [[ "$COMMAND" != git\ commit* ]]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROMPT_FILE="$SCRIPT_DIR/review-prompt.txt"

if [[ ! -f "$PROMPT_FILE" ]]; then
  exit 0
fi

STAGED_DIFF=$(git diff --staged --no-color 2>/dev/null)

# Skip if no staged changes
if [[ -z "$STAGED_DIFF" ]]; then
  exit 0
fi

REVIEW_PROMPT=$(cat "$PROMPT_FILE")

jq -n \
  --arg prompt "$REVIEW_PROMPT" \
  --arg diff "$STAGED_DIFF" \
  '{"additionalContext": ($prompt + "\n\n---\n## Staged diff:\n```\n" + $diff + "\n```")}'
