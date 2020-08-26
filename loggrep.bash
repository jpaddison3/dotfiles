#!/bin/bash
set -euo pipefail
# -x to make it print commands for debugging

grep -r "$1" ~/.logs | sort | tail
