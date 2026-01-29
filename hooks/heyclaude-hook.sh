#!/bin/bash
# HeyClaude hook for Claude Code
# Sends idle_prompt notifications to HeyClaude app

# Read JSON from stdin
INPUT=$(cat)

# POST to HeyClaude server (ignore errors if server is down)
curl -s -X POST "http://127.0.0.1:8765/notification" \
    -H "Content-Type: application/json" \
    -d "$INPUT" \
    --connect-timeout 2 \
    --max-time 5 \
    >/dev/null 2>&1 || true

exit 0
