#!/bin/bash
set -euo pipefail
# -x to make it print commands for debugging

cp settings-dev.json settings-staging.json settings-prod.json ../tmp-settings/
git checkout "$1"
cp ../tmp-settings/* .
