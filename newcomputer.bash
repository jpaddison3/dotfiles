#!/bin/bash
set -euox pipefail

###
# Install homebrew before running this script
###

# https://stackoverflow.com/questions/4774054/reliable-way-for-a-bash-script-to-get-the-full-path-to-itself
SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

# Terminal environment
ln -sf $SCRIPTPATH/bashrc.bash ~/.bashrc
ln -sf $SCRIPTPATH/bash_profile.bash ~/.bash_profile
ln -sf $SCRIPTPATH/zshrc.zsh ~/.zshrc
ln -sf $SCRIPTPATH/tmuxconfig.conf ~/.tmux.conf
mkdir -p ~/.tmuxinator
ln -sf $SCRIPTPATH/tmuxinator-multi.yml ~/.tmuxinator/multi.yml
ln -sf $SCRIPTPATH/tmuxinator-personal.yml ~/.tmuxinator/mux-personal.yml
# Note on pure prompt: I had to manually install

# Text editors
mkdir -p ~/Library/Application\ Support/Code/User/
ln -sf $SCRIPTPATH/vscode-settings.json ~/Library/Application\ Support/Code/User/settings.json
mkdir -p ~/.config
ln -sf $SCRIPTPATH/nvim ~/.config/nvim

# Other
ln -sf $SCRIPTPATH/dotgithelpers.bash ~/.githelpers
mkdir -p ~/.config/git
ln -sf $SCRIPTPATH/gitignore-global ~/.config/git/ignore
# You'll need to copy the git config yourself to edit your email in

# Passwordless sudo for my user. Drop-in (not /etc/sudoers directly) so a bad edit
# can't lock sudo out; visudo -cf validates before we trust it. Tradeoff: any process
# running as me can reach root with no friction — accepted on a personal machine.
# Caveat: a macOS major upgrade can wipe /etc/sudoers.d/ — re-run this block if sudo
# starts prompting again. Needs your password the first time (the one and only sudo
# prompt in this script).
echo "$(whoami) ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/$(whoami)-nopasswd
sudo chmod 440 /etc/sudoers.d/$(whoami)-nopasswd
sudo visudo -cf /etc/sudoers.d/$(whoami)-nopasswd

# Claude configuration
mkdir -p ~/.claude
mkdir -p ~/.claude/skills
ln -f $SCRIPTPATH/root-claude-md.md ~/.claude/CLAUDE.md
ln -sf $SCRIPTPATH/claude-skills/review-codex ~/.claude/skills/review-codex
ln -sf $SCRIPTPATH/claude-skills/review-claude ~/.claude/skills/review-claude
ln -sf $SCRIPTPATH/claude-skills/review-multi ~/.claude/skills/review-multi
ln -sf $SCRIPTPATH/claude-skills/rpr ~/.claude/skills/rpr
ln -sf $SCRIPTPATH/statusline-command.sh ~/.claude/statusline-command.sh
mkdir -p ~/.claude/hooks
ln -sf $SCRIPTPATH/claude-hooks/block-gdoc-cat-devnull.py ~/.claude/hooks/block-gdoc-cat-devnull.py
ln -sf $SCRIPTPATH/claude-hooks/stderr-to-logfile.py ~/.claude/hooks/stderr-to-logfile.py
ln -sf $SCRIPTPATH/claude-hooks/logfile-sink.py ~/.claude/hooks/logfile-sink.py
# Hook registration itself lives in ~/.claude/settings.json, which is untracked
# (not version-controlled) -- see claude-hooks/README.md.

# codex-shim: mirror Claude Code's /fast onto Codex's service_tier. The shim has to
# win the `codex` lookup, so zshrc.zsh slots ~/.local/codex-shim in just before
# nvm's node bin. See codex-shim/README.md.
mkdir -p ~/.local/codex-shim
ln -sf $SCRIPTPATH/codex-shim/codex-mirror ~/.local/codex-shim/codex

# Codex skills
mkdir -p ~/.codex/skills
ln -sf $SCRIPTPATH/claude-skills/asana ~/.codex/skills/asana
ln -sf $SCRIPTPATH/claude-skills/betterheap ~/.codex/skills/betterheap
ln -sf $SCRIPTPATH/claude-skills/ci ~/.codex/skills/ci
ln -sf $SCRIPTPATH/claude-skills/cpr ~/.codex/skills/cpr
ln -sf $SCRIPTPATH/claude-skills/linear ~/.codex/skills/linear
ln -sf $SCRIPTPATH/claude-skills/review-codex ~/.codex/skills/review-codex
ln -sf $SCRIPTPATH/claude-skills/review-claude ~/.codex/skills/review-claude
ln -sf $SCRIPTPATH/claude-skills/review-multi ~/.codex/skills/review-multi
ln -sf $SCRIPTPATH/claude-skills/rpr ~/.codex/skills/rpr
ln -sf $SCRIPTPATH/claude-skills/sentry ~/.codex/skills/sentry
ln -sf $SCRIPTPATH/claude-skills/writing-partner ~/.codex/skills/writing-partner

# launchd-invoked scripts can't live inside ~/Documents — macOS's App
# Management sandbox blocks bash from exec'ing files there, and symlinks
# resolve back to Documents and hit the same wall. Hard links work: TCC
# checks the access-time path, and both paths share an inode, so edits via
# in-place writes propagate automatically.
#
# Caveat: editors that save via "write temp + rename" (VSCode default, vim
# with `set backupcopy=no`, Write tool atomic replace) break the link —
# dotfiles gets a new inode and ~/.local/bin/ keeps the old one. Same for
# `git checkout` replacing the file. Re-run this block after such changes.
mkdir -p ~/.local/bin
ln -f $SCRIPTPATH/pull-granola.py ~/.local/bin/pull-granola.py
ln -f $SCRIPTPATH/pull-granola-launchd.sh ~/.local/bin/pull-granola-launchd.sh

# keep-awake is interactive-only (never launchd-invoked), so the App Management
# sandbox wall above doesn't apply — a plain symlink is fine and, unlike the
# hard links, survives atomic-save / `git checkout` without re-linking.
ln -sf $SCRIPTPATH/keep-awake.sh ~/.local/bin/keep-awake

# launchd agent. The plist must be a real file (or hard link) in
# ~/Library/LaunchAgents — macOS Background Tasks Management doesn't follow
# symlinks, so a symlinked plist is invisible to BTM, never appears in
# System Settings → Login Items, and gets silently lost on reboot.
mkdir -p ~/Library/LaunchAgents
ln -f $SCRIPTPATH/com.jpaddison.pull-granola.plist ~/Library/LaunchAgents/com.jpaddison.pull-granola.plist
launchctl bootout gui/$(id -u)/com.jpaddison.pull-granola 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jpaddison.pull-granola.plist

# Software installation:
# Manual install: pure prompt (brew failed), ohmyzsh, cargo, nvm, yarn
brew install tmux tmuxinator reattach-to-user-namespace neovim coreutils
# Nerd Font glyphs (git branch / diagnostic icons in nvim). Symbols-only so it can
# act as a non-ASCII fallback while a normal font (Monaco) renders text. In iTerm:
# Profiles > Text > "Use a different font for non-ASCII text" > Symbols Nerd Font.
brew install --cask font-symbols-only-nerd-font

# Python venv for ad-hoc scripting. Homebrew python is externally-managed (PEP 668),
# so a venv is the sane place for global-ish packages. ~/venvs/py3 is a version-proof
# symlink pointing at the real versioned dir; bump PYVER on the next upgrade and re-run.
# py-requirements.txt is the source of truth; shell alias/VSCode/CLAUDE.md all use py3.
brew install python@3.14
PYVER=3.14
mkdir -p ~/venvs
[ -d ~/venvs/py${PYVER//.} ] || python${PYVER} -m venv ~/venvs/py${PYVER//.}
~/venvs/py${PYVER//.}/bin/pip install --upgrade pip
~/venvs/py${PYVER//.}/bin/pip install -r "$SCRIPTPATH/py-requirements.txt"
ln -sfn ~/venvs/py${PYVER//.} ~/venvs/py3

# TODO: Generate ssh keys for github
# TODO: VSCode extensions
