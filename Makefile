SHELL := /bin/bash

.PHONY: check install-inbox-triage-raycast

check:
	@bash -n install-inbox-triage-raycast.sh raycast/inbox-triage/*.sh
	@source "$(HOME)/venvs/py3/bin/activate" && python3 -m unittest discover -s tests -p 'test_*.py'

install-inbox-triage-raycast:
	@./install-inbox-triage-raycast.sh
