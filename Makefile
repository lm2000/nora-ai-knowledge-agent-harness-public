PYTHON ?= python3
NPM ?= npm
.PHONY: help validate lint test linkcheck diagrams shellcheck ui-check release-check release

help:
	@echo "make validate: lint, tests, UI production build, shell and documentation checks"
	@echo "make release: validate and build the explicit public source snapshot"

validate: lint test ui-check shellcheck linkcheck diagrams release-check

lint:
	$(PYTHON) -m ruff check src tests scripts deploy
	$(PYTHON) -m ruff format --check src tests scripts deploy

test:
	$(PYTHON) -m pytest -q

ui-check:
	$(NPM) --prefix ui test
	$(NPM) --prefix ui run typecheck
	NEXT_TELEMETRY_DISABLED=1 $(NPM) --prefix ui run build

linkcheck:
	$(PYTHON) scripts/check_links.py

diagrams:
	$(PYTHON) scripts/check_diagrams.py

shellcheck:
	$(PYTHON) -c 'import json,subprocess; [subprocess.run(["bash","-n",p],check=True) for p in json.load(open("release-manifest.json"))["files"] if p.endswith(".sh")]'

release-check:
	$(PYTHON) scripts/build_release.py --check

release: validate
	$(PYTHON) scripts/build_release.py
