### bash-only, not zsh etc.
if [ -f ~/.bashrc ]; then . ~/.bashrc; fi

# pretty colors
export PS1="\[\033[36m\]\u\[\033[m\]@\[\033[32m\]\h:\[\033[33;1m\]\W\[\033[m\]\$ "
export CLICOLOR=1
export LSCOLORS=ExFxBxDxCxegedabagacad

# git
# bash completions
source "$HOME/.config/.git-completion.bash"
[[ -r "/usr/local/etc/profile.d/bash_completion.sh" ]] && . "/usr/local/etc/profile.d/bash_completion.sh"

# Fuck off apple
export BASH_SILENCE_DEPRECATION_WARNING=1

## Google cloud
# opam configuration
test -r /Users/jpaddison/.opam/opam-init/init.sh && . /Users/jpaddison/.opam/opam-init/init.sh > /dev/null 2> /dev/null || true
# The next line updates PATH for the Google Cloud SDK.
if [ -f '/Users/jpaddison/Documents/open-source/google-cloud-sdk/path.bash.inc' ]; then . '/Users/jpaddison/Documents/open-source/google-cloud-sdk/path.bash.inc'; fi
# The next line enables shell command completion for gcloud.
if [ -f '/Users/jpaddison/Documents/open-source/google-cloud-sdk/completion.bash.inc' ]; then . '/Users/jpaddison/Documents/open-source/google-cloud-sdk/completion.bash.inc'; fi
