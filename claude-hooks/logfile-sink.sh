#!/bin/bash
set -uo pipefail
# Reader end of the process substitution stderr-to-logfile.py splices into a
# rewritten command's stderr redirect. $1 is the full original command, used
# to label every line so a grep hit is self-identifying.
label=${1:-unknown command}
mkdir -p "$HOME/.logs"
while IFS= read -r line || [ -n "$line" ]; do
  printf '%s [%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$label" "$line" >> "$HOME/.logs/$(date '+%Y-%m-%d').log"
done
