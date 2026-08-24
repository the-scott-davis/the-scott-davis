# Everything you need day to day. `make help` lists it.
.DEFAULT_GOAL := help
PY ?= python3

# The nightly job needs a 3.10+ interpreter that can actually do HTTPS. Pyenv
# builds are frequently linked against an OpenSSL that is no longer installed,
# which breaks TLS entirely and presents as a network error. So rather than
# trusting whatever `python3` resolves to, probe candidates and pick the first
# that imports ssl. Override with `make venv VENV_PY=/path/to/python`.
VENV_PY ?= $(shell for p in python3.13 python3.12 python3.11 python3.10 python3; do \
	command -v $$p >/dev/null 2>&1 || continue; \
	$$p -c 'import ssl,sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1 \
	  && { command -v $$p; break; }; \
	done)

.PHONY: help install venv nightly portrait preview analyze build fetch check test clean

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	$(PY) -m pip install -r requirements.txt

venv: ## Create the virtualenv the nightly job runs from
	@test -n "$(VENV_PY)" || { \
	  echo "No Python 3.10+ with working SSL found."; \
	  echo "Install one (macOS: brew install python@3.12, Debian: apt install python3.12-venv)"; \
	  echo "or point at it: make venv VENV_PY=/path/to/python3"; exit 1; }
	@echo "using $(VENV_PY) ($$($(VENV_PY) -V))"
	$(VENV_PY) -m venv .venv
	.venv/bin/pip install --quiet --upgrade pip
	.venv/bin/pip install --quiet -r requirements.txt
	@.venv/bin/python -c "import ssl" || { echo "this python cannot do HTTPS"; exit 1; }
	@echo "venv ready: $$(.venv/bin/python -V)"

nightly: ## Run the scheduled rebuild by hand
	./scripts/nightly.sh

portrait: ## Regenerate the portrait from the source photo
	$(PY) -m profilecard.portrait

preview: ## Render the portrait to a scratch file without writing committed files
	$(PY) -m profilecard.portrait --preview

analyze: ## Report whether the source image suits ascii or pixel mode
	$(PY) -m profilecard.portrait --analyze

build: ## Render the cards from cached stats (no GitHub token needed)
	$(PY) -m profilecard --offline

fetch: ## Fetch fresh stats from GitHub and render (needs GITHUB_TOKEN)
	$(PY) -m profilecard

check: ## Validate config.yml
	$(PY) -m profilecard --check

test: ## Run the test suite
	# Ignore globally-installed pytest plugins so the run depends only on
	# requirements.txt, not on whatever else is in site-packages.
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PY) -m pytest -q

clean: ## Remove generated SVGs and the stats cache
	rm -rf dist cache/loc.json
