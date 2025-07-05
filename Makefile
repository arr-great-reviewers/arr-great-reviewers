.PHONY: build data metrics site

VENV=.venv
PY=$(VENV)/bin/python

build: data metrics site

venv:
	uv venv $(VENV)

install: venv
	uv pip install -r pyproject.toml

data: install
	$(PY) -m src.arr_dl

metrics:
	$(PY) -m src.reviewer_utils
	$(PY) -m src.arr_analysis

site:
	$(PY) -m src.build_site
