# ARR Great Reviewers Build System
#
# Available targets:
#   build                    - Full build: data + metrics + all pages (default)
#   build-mapped             - Full build that fails if any reviewers remain unmapped
#   build-fast              - Fast build: data + metrics + non-reviewer pages only
#   build-single-reviewer   - Single reviewer build: data + metrics + Marek Suppa page only
#   build-single-institution - Single institution build: data + metrics + Google page only
#   data                    - Download and process ARR data only
#   metrics                 - Calculate metrics only (requires data)
#   site                    - Generate complete site (requires data and metrics)
#   site-fast               - Generate site excluding reviewer pages
#   site-single-reviewer    - Generate site with only Marek Suppa reviewer page
#   site-single-institution - Generate site with only Google institution page
#   map-openreview          - Map all reviewers to OpenReview profiles
#   map-openreview-incremental - Map only new reviewers to OpenReview profiles
#   map-openreview-check    - Fail if any reviewers remain unmapped
#   map-openreview-check-top - Fail if any top-N reviewers per cycle remain unmapped
#   map-openreview-reprocess-top - Reprocess no-matches only for top-N reviewers per cycle
#
# Fast development workflow:
#   1. Use 'make build-fast' during development to avoid generating 2000+ reviewer pages
#   2. Use 'make build-single-reviewer' to test reviewer page functionality
#   3. Use 'make build-single-institution' to test institution page functionality
#   4. Use 'make build' for final complete build

.PHONY: build build-mapped data metrics site site-fast site-single-reviewer site-single-institution build-fast build-single-reviewer build-single-institution map-openreview map-openreview-incremental map-openreview-check map-openreview-check-top map-openreview-reprocess-top

VENV=.venv
PY=$(VENV)/bin/python

build: data metrics site

# Full build that requires all reviewers to be mapped
build-mapped: data
	$(PY) -m src.map_openreview_profiles incremental --reprocess-no-matches
	$(PY) -m src.map_openreview_profiles check --fail-on-missing
	$(PY) -m src.reviewer_utils
	$(PY) -m src.arr_analysis
	$(PY) -m src.institution_utils
	$(PY) -m src.build_site

map-openreview-check: install
	$(PY) -m src.map_openreview_profiles check --fail-on-missing

map-openreview-check-top: install
	$(PY) -m src.reviewer_utils
	$(PY) -m src.map_openreview_profiles check --top-n-per-cycle 100 --fail-on-missing

map-openreview-reprocess-top: install
	$(PY) -m src.map_openreview_profiles reprocess-top --top-n-per-cycle 100

# Fast build: rebuild all pages except individual reviewer pages
build-fast: data metrics site-fast

# Single reviewer build: rebuild everything + one specific reviewer (MarekSuppa1)
build-single-reviewer: data metrics site-single-reviewer

# Single institution build: rebuild everything + one specific institution (Google)
build-single-institution: data metrics site-single-institution

venv:
	uv venv $(VENV) --clear

install: venv
	uv pip install -r pyproject.toml

data: install
	$(PY) -m src.arr_dl

metrics:
	$(PY) -m src.reviewer_utils
	$(PY) -m src.arr_analysis
	$(PY) -m src.institution_utils

site:
	$(PY) -m src.build_site

# Fast site build: skip all reviewer and institution pages
site-fast:
	$(PY) -m src.build_site --skip-reviewers --skip-institutions

# Single reviewer site build: generate only Marek_Suppa1 reviewer page
site-single-reviewer:
	$(PY) -m src.build_site --single-reviewer "~Marek_Suppa1"

# Single institution site build: generate only Google institution page
site-single-institution:
	$(PY) -m src.build_site --single-institution "google"

map-openreview: install
	$(PY) -m src.map_openreview_profiles main

map-openreview-incremental: install
	$(PY) -m src.map_openreview_profiles incremental
