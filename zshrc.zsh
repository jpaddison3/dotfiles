if [ -f ~/.bashrc ]; then . ~/.bashrc; fi

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

# # git completion
# zstyle ':completion:*:*:git:*' script ~/.zsh/git-completion.bash
# fpath=(~/.zsh $fpath)
# autoload -Uz compinit && compinit

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
