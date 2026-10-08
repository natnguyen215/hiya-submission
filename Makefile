# Thin aliases for tasks.py, which does the work on every OS. Pass eval flags with ARGS, e.g.
#   make eval ARGS=--cache
PYTHON ?= python3

install dev build run test eval:
	$(PYTHON) tasks.py $@ $(ARGS)

.PHONY: install dev build run test eval
