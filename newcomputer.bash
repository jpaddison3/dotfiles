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
# Note on pure prompt: I had to manually install

# Text editor
mkdir -p ~/Library/Application\ Support/Code/User/
ln -sf $SCRIPTPATH/vscode-settings.json ~/Library/Application\ Support/Code/User/settings.json

# Other
ln -sf $SCRIPTPATH/psqlrc ~/.psqlrc
ln -sf $SCRIPTPATH/dotgithelpers.bash ~/.githelpers
# You'll need to copy the git config yourself to edit your email in

# Software installation:
# Manual install: pure prompt (brew failed), ohmyzsh, cargo, nvm, yarn
brew install tmux tmuxinator reattach-to-user-namespace

# TODO: Generate ssh keys for github
# TODO: VSCode extensions
