# Allow installation of 3rd party modules
use epm

# Allow aliases
epm:install &silent-if-installed github.com/zzamboni/elvish-modules
use github.com/zzamboni/elvish-modules/alias

# Prompt
epm:install &silent-if-installed github.com/zzamboni/elvish-themes
use github.com/zzamboni/elvish-themes/chain

# Keybindings
edit:insert:binding[Alt-Backspace] = $edit:kill-small-word-left~
# TODO: Yank

# Import regex module
use re

# Git completions
epm:install &silent-if-installed github.com/zzamboni/elvish-completions
use github.com/zzamboni/elvish-completions/git git-completions

# Python
# TODO: Fork and fix deprecation warning
epm:install &silent-if-installed=$true github.com/iwoloschin/elvish-packages
use github.com/iwoloschin/elvish-packages/python
python:virtualenv-directory = $E:HOME/.venv

# Personal scripts
alias:new coss $E:HOME/Documents/dotfiles/checkout-save-settings.bash
alias:new gitstashstaged $E:HOME/Documents/dotfiles/git_stash_staged.bash

# Export aliases
-exports- = (alias:export)
