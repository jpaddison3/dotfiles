# Log my commands for use later
export PROMPT_COMMAND='if [ "$(id -u)" -ne 0 ]; then echo "$(date "+%Y-%m-%d.%H:%M:%S") $(pwd) $(history 1)" >> ~/.logs/bash-history-$(date "+%Y-%m-%d").log; fi'

# basic aliases
alias flushdnscache='sudo killall -HUP mDNSResponder && echo "DNS caches flushed"'

# pretty colors in bash
export PS1="\[\033[36m\]\u\[\033[m\]@\[\033[32m\]\h:\[\033[33;1m\]\W\[\033[m\]\$ "
export CLICOLOR=1
export LSCOLORS=ExFxBxDxCxegedabagacad
alias ls='ls -GFh'

# Hidden artifactory credentials
if [ -f ~/.config/artifactory_envar ]; then . ~/.config/artifactory_envar; fi

# Check /usr/local first - useful for homebrew and spacemacs
export PATH="/usr/local/bin:/usr/local/sbin:$PATH"

# Go Language
export GOPATH=$HOME/Documents/Kairos/golang
export GOROOT=/usr/local/Cellar/go/1.9/libexec
export PATH=$PATH:$GOPATH/bin:$GOROOT/bin
export LG=$HOME/Documents/Kairos/golang/src/github.com/KairosAerospace/leakyg
alias govtest='go list ./... | grep -v vendor | xargs go test'

# Python
alias py36='. ~/py36/bin/activate'

# GDAL
export PROJSO=/Library/Frameworks/PROJ.framework/PROJ
export GDAL_DATA=/Users/jpaddison/Documents/MrSID_DSDK-9.1.0.4045-darwin13.universal.clang51/Raster_DSDK/3rd-party/share/gdal

# GPSBabel
alias gpsbabel=/Applications/GPSBabelFE.app/Contents/MacOS/gpsbabel

# Javascript - needs work
export PATH="$HOME/.npm-packages/bin:/usr/local/Cellar/node/6.2.0/bin:$PATH"
# Meteor
export METEOR_PACKAGE_DIRS=../Vulcan/packages:../Vulcan-Starter/packages

# Latex
export PATH=$PATH:/Library/TeX/texbin

# CUDA GPU
export PATH=$PATH:/Developer/NVIDIA/CUDA-8.0/bin
EXTRA_LD=/Developer/NVIDIA/CUDA-8.0/lib:/Developer/NVIDIA/cudnn
export DYLD_LIBRARY_PATH=$DYLD_LIBRARY_PATH:$EXTRA_LD
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$EXTRA_LD

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# Homebrew Coreutils
alias timeout=gtimeout

PATH="/Users/jpaddison/perl5/bin${PATH:+:${PATH}}"; export PATH;
PERL5LIB="/Users/jpaddison/perl5/lib/perl5${PERL5LIB:+:${PERL5LIB}}"; export PERL5LIB;
PERL_LOCAL_LIB_ROOT="/Users/jpaddison/perl5${PERL_LOCAL_LIB_ROOT:+:${PERL_LOCAL_LIB_ROOT}}"; export PERL_LOCAL_LIB_ROOT;
PERL_MB_OPT="--install_base \"/Users/jpaddison/perl5\""; export PERL_MB_OPT;
PERL_MM_OPT="INSTALL_BASE=/Users/jpaddison/perl5"; export PERL_MM_OPT;
