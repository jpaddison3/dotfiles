#!/bin/bash
# Fix Claude Code's Chrome MCP connection by disabling the broken
# tengu_copper_bridge feature flag that forces the cloud WebSocket bridge.
#
# See: https://github.com/anthropics/claude-code/issues/24784
#
# What this does:
#   Patches ~/.claude.json to set tengu_copper_bridge = false
#
# The flag gets re-enabled whenever another Claude Code session starts
# (it re-fetches from GrowthBook). So this must be run right before
# starting the session that needs Chrome, and that session should avoid
# spawning new Claude Code processes that would overwrite the fix.
#
# After running, restart Claude Code for changes to take effect.

set -euo pipefail

CLAUDE_JSON="$HOME/.claude.json"

if [ ! -f "$CLAUDE_JSON" ]; then
  echo "ERROR: $CLAUDE_JSON not found"
  exit 1
fi

python3 -c "
import json
with open('$CLAUDE_JSON') as f:
    d = json.load(f)
gb = d.get('cachedGrowthBookFeatures', {})
before = gb.get('tengu_copper_bridge')
gb['tengu_copper_bridge'] = False
d['cachedGrowthBookFeatures'] = gb
with open('$CLAUDE_JSON', 'w') as f:
    json.dump(d, f, indent=2)
if before is not False:
    print('Fixed: tengu_copper_bridge set to false (was', before, ')')
else:
    print('Already fixed: tengu_copper_bridge is false')
print('Restart Claude Code for changes to take effect.')
"
