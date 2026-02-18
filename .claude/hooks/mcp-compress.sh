#!/bin/bash
# Generic PostToolUse hook to compress oversized MCP tool output.
# Companion to rtk-rewrite.sh — RTK handles Bash, this handles MCP.
#
# Truncates MCP output exceeding a character threshold and appends
# a hint to use a detail tool (like get_event) for full data.
#
# Config via env vars:
#   MCP_COMPRESS_THRESHOLD  - char limit before truncating (default: 12000)

if ! command -v jq &>/dev/null; then
  exit 0
fi

set -euo pipefail

THRESHOLD="${MCP_COMPRESS_THRESHOLD:-12000}"

INPUT=$(cat)

TOOL_RESPONSE=$(echo "$INPUT" | jq -r '.tool_response // empty')

# Nothing to compress
if [ -z "$TOOL_RESPONSE" ]; then
  exit 0
fi

LENGTH=${#TOOL_RESPONSE}

# Under threshold — pass through unchanged
if [ "$LENGTH" -le "$THRESHOLD" ]; then
  exit 0
fi

# Truncate and append a hint
TRUNCATED="${TOOL_RESPONSE:0:$THRESHOLD}"

# Try to cut at the last complete event/entry boundary (double newline)
LAST_BREAK=$(echo "$TRUNCATED" | grep -b -o $'\n\n' | tail -1 | cut -d: -f1 || true)
if [ -n "$LAST_BREAK" ] && [ "$LAST_BREAK" -gt $(( THRESHOLD / 2 )) ]; then
  TRUNCATED="${TRUNCATED:0:$LAST_BREAK}"
fi

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
TRUNCATED="${TRUNCATED}

[Truncated: ${LENGTH} chars → ${#TRUNCATED} chars. Use a detail/get tool for full data on specific items.]"

# Return compressed output
jq -n \
  --arg output "$TRUNCATED" \
  '{
    "hookSpecificOutput": {
      "hookEventName": "PostToolUse",
      "updatedMCPToolOutput": $output
    }
  }'
