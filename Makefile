init:
	@uv sync

check:
	uv run tox -e black,ruff,mypy

test:
	uv run tox -e py314

ci:
	uv run tox -e black,ruff,mypy,py314

dev:
	uv run pip install --editable .

install:
	pip install .

update-golden:
	uv run python scripts/update_golden.py

release:
	@test -n "$(VERSION)" || (echo "Error: VERSION is required. Usage: make release VERSION=x.y.z [ARGS=...]" && exit 1)
	uv run python scripts/release.py $(VERSION) $(ARGS)

.PHONY: init check test ci dev install update-golden release

