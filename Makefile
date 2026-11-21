SHELL := /bin/bash

.PHONY: check install-bb-chrome install-inbox-triage-raycast install-pf-ssh

check:
	@for script in install-bb-chrome.sh install-inbox-triage-raycast.sh raycast/inbox-triage/*.sh keep-awake.sh keep-awakectl install-keep-awake.sh codex-shim/claude-account agent-tmp-cleanup.sh install-pf-ssh.sh; do /bin/bash -n "$$script" || exit; done
	@source "$(HOME)/venvs/py3/bin/activate" && python3 -m unittest discover -s tests -p 'test_*.py'

install-bb-chrome:
	@./install-bb-chrome.sh

install-inbox-triage-raycast:
	@./install-inbox-triage-raycast.sh

install-pf-ssh:
	@./install-pf-ssh.sh
