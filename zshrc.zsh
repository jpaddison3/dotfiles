if [ -f ~/.bashrc ]; then . ~/.bashrc; fi

autoload -Uz promptinit; promptinit
prompt pure

# set up package manager
source ~/.zsh/antigen/antigen.zsh

# logging
HISTFILE=~/.zsh_history
HISTFILESIZE=1000000000
HISTSIZE=1000000000
SAVEHIST=$HISTSIZE
setopt INC_APPEND_HISTORY
setopt EXTENDED_HISTORY

alias loggrepz='history -E 1 | rg'

# git completion
zstyle ':completion:*:*:git:*' script ~/.zsh/git-completion.bash
fpath=(~/.zsh $fpath)
autoload -Uz compinit && compinit

# yarn completion
antigen bundle buonomo/yarn-completion

# The next line updates PATH for the Google Cloud SDK.
if [ -f '/Users/jpaddison/Downloads/google-cloud-sdk/path.zsh.inc' ]; then . '/Users/jpaddison/Downloads/google-cloud-sdk/path.zsh.inc'; fi

# The next line enables shell command completion for gcloud.
if [ -f '/Users/jpaddison/Downloads/google-cloud-sdk/completion.zsh.inc' ]; then . '/Users/jpaddison/Downloads/google-cloud-sdk/completion.zsh.inc'; fi
