#!/bin/bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
destination="$HOME/.local/share/lmstudio-policy"
mkdir -p "$destination" "$HOME/.local/bin"
install -m 755 "$source_dir/lms" "$destination/lms"
install -m 755 "$source_dir/configure.py" "$destination/configure.py"
ln -sfn "$destination/lms" "$HOME/.local/bin/lms"
python3 "$destination/configure.py"
