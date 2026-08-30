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

tag:
	@test -f VERSION || (echo "Error: VERSION file not found." && exit 1)
	@VER=$$(cat VERSION | tr -d '[:space:]'); \
	test -n "$$VER" || (echo "Error: VERSION file is empty." && exit 1); \
	echo "Tagging and pushing version $$VER..."; \
	git tag -a "$$VER" -m "Release $$VER" && \
	git push origin "$$VER"

.PHONY: init check test ci dev install update-golden release tag
