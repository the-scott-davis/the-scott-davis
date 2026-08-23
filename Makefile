# Everything you need day to day. `make help` lists it.
.DEFAULT_GOAL := help
PY ?= python3

.PHONY: help install portrait preview analyze build fetch check test clean

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	$(PY) -m pip install -r requirements.txt

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
