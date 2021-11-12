### Contains the environment configuration that every shell or other environment
### will want. See bash_profile.bash for the bash-specific commands

# Log my commands for use later
export PROMPT_COMMAND='if [ "$(id -u)" -ne 0 ]; then echo "$(date "+%Y-%m-%d.%H:%M:%S") $(pwd) $(history 1)" >> ~/.logs/bash-history-$(date "+%Y-%m-%d").log; fi'

# And allow searching
alias loggrep="$HOME/Documents/dotfiles/loggrep.bash"

# basic aliases
alias flushdnscache='sudo killall -HUP mDNSResponder && echo "DNS caches flushed"'

# Homebrew
export PATH="/usr/local/bin:/usr/local/sbin:$PATH"
export HOMEBREW_NO_AUTO_UPDATE="1"

# Go Language
export GOPATH=$HOME/.go
export GOROOT=/usr/local/Cellar/go/1.9/libexec
export PATH=$PATH:$GOPATH/bin:$GOROOT/bin

# Python
alias py39='. ~/.venv/py39/bin/activate'

# Javascript
source "$HOME/.nvm/nvm.sh"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# Mongodb
export PATH="/usr/local/opt/mongodb-community@4.2/bin:$PATH"

# PSQL
export PATH="/usr/local/opt/postgresql@14/bin:$PATH"

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

## git
alias gitstashstaged="$HOME/Documents/dotfiles/git_stash_staged.bash"

# Rust
export PATH="$HOME/.cargo/bin:$PATH"

# Set editor
export EDITOR='vim'

# Tmux
alias mux="tmuxinator"
