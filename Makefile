# Short names for the tasks in tasks.py. To give flags to the eval, use ARGS:
#   make eval ARGS=--cache
PYTHON ?= python3

install dev build run test eval:
	$(PYTHON) tasks.py $@ $(ARGS)

.PHONY: install dev build run test eval
