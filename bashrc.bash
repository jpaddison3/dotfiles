# Log my commands for use later
export PROMPT_COMMAND='if [ "$(id -u)" -ne 0 ]; then echo "$(date "+%Y-%m-%d.%H:%M:%S") $(pwd) $(history 1)" >> ~/.logs/bash-history-$(date "+%Y-%m-%d").log; fi'

# And allow searching
alias loggrep="$HOME/Documents/dotfiles/loggrep.bash"

# basic aliases
alias flushdnscache='sudo killall -HUP mDNSResponder && echo "DNS caches flushed"'

# pretty colors in bash
export PS1="\[\033[36m\]\u\[\033[m\]@\[\033[32m\]\h:\[\033[33;1m\]\W\[\033[m\]\$ "
export CLICOLOR=1
export LSCOLORS=ExFxBxDxCxegedabagacad
alias ls='ls -GFh'

# Check /usr/local first - useful for homebrew and spacemacs
export PATH="/usr/local/bin:/usr/local/sbin:$PATH"

# Go Language
export GOPATH=$HOME/.go
export GOROOT=/usr/local/Cellar/go/1.9/libexec
export PATH=$PATH:$GOPATH/bin:$GOROOT/bin

# Python
alias py38='. ~/.venv/py38/bin/activate'

# GPSBabel
alias gpsbabel=/Applications/GPSBabelFE.app/Contents/MacOS/gpsbabel

# Javascript
source "$HOME/.nvm/nvm.sh"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# Meteor
export METEOR_PACKAGE_DIRS=../Vulcan/packages

# Mongodb
export PATH="/usr/local/opt/mongodb-community@4.0/bin:$PATH"

# PSQL
export PATH="/usr/local/opt/postgresql@9.6/bin:$PATH"

# Homebrew Coreutils
alias timeout=gtimeout

# Perl
PATH="/Users/jpaddison/perl5/bin${PATH:+:${PATH}}"; export PATH;
PERL5LIB="/Users/jpaddison/perl5/lib/perl5${PERL5LIB:+:${PERL5LIB}}"; export PERL5LIB;
PERL_LOCAL_LIB_ROOT="/Users/jpaddison/perl5${PERL_LOCAL_LIB_ROOT:+:${PERL_LOCAL_LIB_ROOT}}"; export PERL_LOCAL_LIB_ROOT;
PERL_MB_OPT="--install_base \"/Users/jpaddison/perl5\""; export PERL_MB_OPT;
PERL_MM_OPT="INSTALL_BASE=/Users/jpaddison/perl5"; export PERL_MM_OPT;

# heroku autocomplete setup
HEROKU_AC_BASH_SETUP_PATH=/Users/jpaddison/Library/Caches/heroku/autocomplete/bash_setup && test -f $HEROKU_AC_BASH_SETUP_PATH && source $HEROKU_AC_BASH_SETUP_PATH;

# git scripts
alias gitstashstaged="$HOME/Documents/dotfile/gitstashstaged.bash"

# bash completions
source "$HOME/.config/.git-completion.bash"
[[ -r "/usr/local/etc/profile.d/bash_completion.sh" ]] && . "/usr/local/etc/profile.d/bash_completion.sh"

# Hacky forum helper
alias coss="$HOME/Documents/dotfiles/checkout-save-settings.bash"

# Fuck off apple
export BASH_SILENCE_DEPRECATION_WARNING=1

# Google cloud
# opam configuration
test -r /Users/jpaddison/.opam/opam-init/init.sh && . /Users/jpaddison/.opam/opam-init/init.sh > /dev/null 2> /dev/null || true
# The next line updates PATH for the Google Cloud SDK.
if [ -f '/Users/jpaddison/Documents/open-source/google-cloud-sdk/path.bash.inc' ]; then . '/Users/jpaddison/Documents/open-source/google-cloud-sdk/path.bash.inc'; fi
# The next line enables shell command completion for gcloud.
if [ -f '/Users/jpaddison/Documents/open-source/google-cloud-sdk/completion.bash.inc' ]; then . '/Users/jpaddison/Documents/open-source/google-cloud-sdk/completion.bash.inc'; fi
