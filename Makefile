.PHONY: install test lint help

install:
	python -m pip install -e .

test:
	python -m pytest

lint:
	python -m compileall -q src tests

help:
	@echo "make install  Install the CLI in editable mode"
	@echo "make test     Run unit tests"
	@echo "make lint     Compile-check Python files"
