SHELL := /bin/bash

.PHONY: check install-inbox-triage-raycast

check:
	@for script in install-inbox-triage-raycast.sh raycast/inbox-triage/*.sh keep-awake.sh keep-awakectl install-keep-awake.sh; do /bin/bash -n "$$script" || exit; done
	@source "$(HOME)/venvs/py3/bin/activate" && python3 -m unittest discover -s tests -p 'test_*.py'

install-inbox-triage-raycast:
	@./install-inbox-triage-raycast.sh
