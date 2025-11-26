### Contains the environment configuration that every shell or other environment
### will want. See bash_profile.bash for the bash-specific commands

# Deduplicate PATH entries
dedupe_path() {
    local path_array=()
    local IFS=':'
    local seen=""

    for dir in $PATH; do
        if [[ ":$seen:" != *":$dir:"* ]]; then
            path_array+=("$dir")
            seen="$seen:$dir"
        fi
    done

    PATH=$(IFS=':'; echo "${path_array[*]}")
    export PATH
}

# Log my commands for use later
export PROMPT_COMMAND='if [ "$(id -u)" -ne 0 ]; then echo "$(date "+%Y-%m-%d.%H:%M:%S") $(pwd) $(history 1)" >> ~/.logs/bash-history-$(date "+%Y-%m-%d").log; fi'

# And allow searching
alias loggrep="$HOME/Documents/dotfiles/loggrep.bash"

# basic aliases
alias flushdnscache='sudo killall -HUP mDNSResponder && echo "DNS caches flushed"'

# Homebrew
export PATH="/usr/local/bin:/usr/local/sbin:$PATH"
export HOMEBREW_NO_AUTO_UPDATE="1"
export HOMEBREW_PREFIX="/opt/homebrew";
export HOMEBREW_CELLAR="/opt/homebrew/Cellar";
export HOMEBREW_REPOSITORY="/opt/homebrew";
export HOMEBREW_SHELLENV_PREFIX="/opt/homebrew";
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin${PATH+:$PATH}";
export MANPATH="/opt/homebrew/share/man${MANPATH+:$MANPATH}:";
export INFOPATH="/opt/homebrew/share/info:${INFOPATH:-}";

# Go Language
export GOPATH=$HOME/.go
export PATH=$PATH:$GOPATH/bin

# Python
alias py313='. ~/venvs/py313/bin/activate'

# PSQL
export PATH="/opt/homebrew/opt/postgresql@14/bin:$PATH"

# Homebrew Coreutils
alias timeout=gtimeout

# Perl
PATH="/Users/jpaddison/perl5/bin${PATH:+:${PATH}}"; export PATH;
PERL5LIB="/Users/jpaddison/perl5/lib/perl5${PERL5LIB:+:${PERL5LIB}}"; export PERL5LIB;
PERL_LOCAL_LIB_ROOT="/Users/jpaddison/perl5${PERL_LOCAL_LIB_ROOT:+:${PERL_LOCAL_LIB_ROOT}}"; export PERL_LOCAL_LIB_ROOT;
PERL_MB_OPT="--install_base \"/Users/jpaddison/perl5\""; export PERL_MB_OPT;
PERL_MM_OPT="INSTALL_BASE=/Users/jpaddison/perl5"; export PERL_MM_OPT;

## git
alias gitstashstaged="$HOME/Documents/dotfiles/git_stash_staged.bash"

# Rust
export PATH="$HOME/.cargo/bin:$PATH"

# Set editor
export EDITOR='vim'

# Claude Code MCP mode switching
alias cmode="$HOME/Documents/dotfiles/claude-mcp-mode.bash"

# Tmux
alias mux="tmuxinator"
alias mux-dev='tmuxinator start multi'
# Minerva Claude instances
alias mux-dev-claude1='TMUX_SESSION=claude1 MINERVA_DIR=minerva-claude1 tmuxinator start multi'
alias mux-dev-claude2='TMUX_SESSION=claude2 MINERVA_DIR=minerva-claude2 tmuxinator start multi'

# JS
export PATH="$HOME/.yarn/bin:$PATH"

# Docker
export PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"

# Clean up PATH duplicates
dedupe_path
