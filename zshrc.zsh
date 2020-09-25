if [ -f ~/.bashrc ]; then . ~/.bashrc; fi

autoload -Uz promptinit; promptinit
prompt pure

# TODO logging

# git completion
zstyle ':completion:*:*:git:*' script ~/.zsh/git-completion.bash
fpath=(~/.zsh $fpath)
autoload -Uz compinit && compinit
