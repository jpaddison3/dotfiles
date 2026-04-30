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
ln -sf $SCRIPTPATH/psqlrc ~/.psqlrc
ln -sf $SCRIPTPATH/dotgithelpers.bash ~/.githelpers
# You'll need to copy the git config yourself to edit your email in

# Claude configuration
mkdir -p ~/.claude
mkdir -p ~/.claude/skills
ln -f $SCRIPTPATH/root-claude-md.md ~/.claude/CLAUDE.md
ln -sf $SCRIPTPATH/claude-skills/review-codex ~/.claude/skills/review-codex
ln -sf $SCRIPTPATH/claude-skills/review-claude ~/.claude/skills/review-claude
ln -sf $SCRIPTPATH/claude-skills/review-multi ~/.claude/skills/review-multi

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

# launchd agents (plist itself can stay in ~/Documents — launchd only reads it)
mkdir -p ~/Library/LaunchAgents
ln -sf $SCRIPTPATH/com.jpaddison.pull-granola.plist ~/Library/LaunchAgents/com.jpaddison.pull-granola.plist
launchctl bootout gui/$(id -u)/com.jpaddison.pull-granola 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jpaddison.pull-granola.plist

# Software installation:
# Manual install: pure prompt (brew failed), ohmyzsh, cargo, nvm, yarn
brew install tmux tmuxinator reattach-to-user-namespace neovim

# TODO: Generate ssh keys for github
# TODO: VSCode extensions
