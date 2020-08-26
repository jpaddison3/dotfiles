# macOS uses .bash_profile for normal user shells, but spacemacs uses .bashrc
if [ -f ~/.bashrc ]; then . ~/.bashrc; fi

export PATH="$HOME/.cargo/bin:$PATH"
