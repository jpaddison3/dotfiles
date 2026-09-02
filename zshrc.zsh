if [ -f ~/.bashrc ]; then . ~/.bashrc; fi

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# oh-my-zsh
export ZSH="/Users/jpaddison/.oh-my-zsh"
ZSH_THEME=""
plugins=(git zsh-auto-nvm-use yarn-autocompletions)
source $ZSH/oh-my-zsh.sh

# logging
HISTFILE=~/.zsh_history
HISTFILESIZE=1000000000
HISTSIZE=1000000000
SAVEHIST=$HISTSIZE
setopt INC_APPEND_HISTORY
setopt EXTENDED_HISTORY

alias loggrepz='history -E 1 | rg'
alias fix-chrome-mcp='~/Documents/dotfiles/fix-chrome-mcp.sh'

# # git completion
# zstyle ':completion:*:*:git:*' script ~/.zsh/git-completion.bash
# fpath=(~/.zsh $fpath)
# autoload -Uz compinit && compinit

fpath+=$HOME/.zsh/pure
autoload -U promptinit; promptinit
prompt pure

# The next line updates PATH for the Google Cloud SDK.
if [ -f '/Users/jpaddison/Downloads/google-cloud-sdk/path.zsh.inc' ]; then . '/Users/jpaddison/Downloads/google-cloud-sdk/path.zsh.inc'; fi

# The next line enables shell command completion for gcloud.
if [ -f '/Users/jpaddison/Downloads/google-cloud-sdk/completion.zsh.inc' ]; then . '/Users/jpaddison/Downloads/google-cloud-sdk/completion.zsh.inc'; fi

password () {
  chars=${1:-32}
  inputlen="$((chars * 2))"
  openssl rand -base64 $inputlen | tr -dc A-Za-z0-9 | head -c$chars && echo ""
}
# openssl rand -base64 32 | tr -dc A-Za-z0-9

# TODO; might not be all I need
unsetopt share_history

# codex-shim: mirror Claude Code's /fast onto Codex's service_tier.
# The shim has to win the `codex` lookup, so it sits ahead of nvm's node bin —
# that's where npm installs the real binary, and nvm prepends itself to the very
# front of PATH. Outside a Claude session the shim is a transparent passthrough,
# so plain `codex` from the CLI is unchanged.
# Details: ~/Documents/dotfiles/codex-shim/README.md
#
# ~/.local/bin gets the same treatment so the native Claude Code install
# (~/.local/bin/claude) always beats a stray npm-global copy in nvm's bin —
# an npm claude resurrected there is inert instead of silently taking over.
# (zprofile's pipx line appends ~/.local/bin at the tail; we drop that and
# reinsert it here, ahead of nvm. It holds no node/npm, so nothing shadows.)
() {
  emulate -L zsh
  local seg; local -a out; local inserted=0
  for seg in $path; do
    [[ $seg == $HOME/.local/codex-shim || $seg == $HOME/.local/bin ]] && continue  # drop existing
    if (( ! inserted )) && [[ $seg == $HOME/.nvm/versions/node/*/bin ]]; then
      out+=($HOME/.local/codex-shim $HOME/.local/bin); inserted=1  # insert before nvm
    fi
    out+=$seg
  done
  (( inserted )) || out=($HOME/.local/codex-shim $HOME/.local/bin $out)  # no nvm dir? front
  path=($out)
}

# Per-repo Claude account. Account choice is CLAUDE_CONFIG_DIR at launch, so a
# wrapper is the only way to make it per-repo. Default (~/.claude) is the
# personal-Max login on the work email.
#   ~/.claude-team  — "80,000 Hours" Team org (work email)
#   ~/.claude-gmail — johnpaddison@gmail.com account
# An explicit CLAUDE_CONFIG_DIR wins over the repo mapping, e.g.:
#   CLAUDE_CONFIG_DIR=~/.claude-team claude
claude() {
  if [[ -n "$CLAUDE_CONFIG_DIR" ]]; then
    command claude "$@"
    return
  fi
  local -a gmail_repos=(
    "$HOME/Documents/dotfiles"
    "$HOME/personal-coding/personal-travel"
    "$HOME/personal-coding/todoist-quick-add"
    "$HOME/personal-coding/dharma"
    "$HOME/personal-coding/gdoc"
    "$HOME/personal-coding/betterheap"
  )
  local repo
  for repo in $gmail_repos; do
    if [[ "$PWD" == "$repo"* ]]; then
      CLAUDE_CONFIG_DIR="$HOME/.claude-gmail" command claude "$@"
      return
    fi
  done
  if [[ "$PWD" == "$HOME/personal-coding/claude-life"* ]]; then
    CLAUDE_CONFIG_DIR="$HOME/.claude-team" command claude "$@"
  else
    command claude "$@"
  fi
}
