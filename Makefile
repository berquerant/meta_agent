init:
	@uv sync

check:
	uv run tox -e black,ruff,mypy -p 3

test:
	uv run tox -e py314

ci:
	uv run tox -e black,ruff,mypy,py314 -p 4

dev:
	uv run pip install --editable .

install:
	pip install .

.PHONY: init check test ci dev install
