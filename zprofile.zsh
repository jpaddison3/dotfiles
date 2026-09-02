# ~/.zprofile — sourced by login shells, including non-interactive `zsh -lc`,
# which is how Codex runs its shell commands. Before this file runs,
# /etc/zprofile's path_helper rebuilds PATH with /usr/local/bin at the front,
# which would put the real /usr/local/bin/orca ahead of the orca-open-guard shim.
# Re-prepend the shim dir so `orca` and `codex` keep resolving to the shims.
# (zshrc.zsh re-slots the same dir just before nvm's bin for interactive shells.)
# See codex-shim/README.md.
typeset -U path
path=($HOME/.local/codex-shim $path)

# Created by `pipx` on 2025-09-23 (carried over from the original ~/.zprofile).
export PATH="$PATH:$HOME/.local/bin"
