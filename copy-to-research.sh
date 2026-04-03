#!/bin/bash
# Copies a file into the product research pr-summaries folder.
# Usage: copy-to-research.sh <source-file>

set -euo pipefail

DEST_DIR="$HOME/80k/ai-products-research/automated-inputs/pr-summaries"

if [ $# -ne 1 ]; then
  echo "Usage: copy-to-research.sh <source-file>" >&2
  exit 1
fi

src="$1"

if [ ! -f "$src" ]; then
  echo "Error: source file not found: $src" >&2
  exit 1
fi

if [ ! -d "$DEST_DIR" ]; then
  echo "Error: destination directory not found: $DEST_DIR" >&2
  exit 1
fi

cp "$src" "$DEST_DIR/"
echo "Copied $(basename "$src") to $DEST_DIR/"
