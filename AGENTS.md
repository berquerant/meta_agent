# AGENTS.md

## Keeping This File Up to Date

When you make structural changes to the project (adding/removing modules, commands, tools, or conventions), **update this file** so it accurately reflects the current state of the codebase. Treat AGENTS.md as living documentation: if the code contradicts what is written here, fix AGENTS.md.

---

## Project Overview

**meta_agent** is a Python CLI tool that acts as a *meta-agent* — an AI-powered assistant that generates, manages, and executes AI assistant recipes using the [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) framework.

It exposes six sub-commands:

| Command   | Description                                              |
|-----------|----------------------------------------------------------|
| `get`     | List or inspect recipes, agents, and tools               |
| `gen`     | Generate a new AI assistant recipe via an LLM            |
| `chat`    | Start an interactive multi-turn chat session             |
| `ask`     | Ask a single question using a recipe-configured agent    |
| `jarvis`  | Pass raw arguments directly to the underlying jarvis CLI |
| `tui`     | Launch an interactive terminal UI (Textual-based)        |

## Repository Layout

```
meta_agent/
├── meta_agent/        # Main package
│   ├── __init__.py
│   ├── api.py         # OpenJarvis wrappers (agents, tools, recipes)
│   ├── asking.py      # Chat/ask request building and execvp dispatch
│   ├── cli.py         # argparse entry point
│   ├── cmd.py         # High-level Cmd class wiring CLI args to api/gen
│   ├── gen.py         # Recipe generation logic and meta-agent prompt
│   ├── tools.py       # Custom OpenJarvis tool registrations
│   ├── tui.py         # Textual-based interactive TUI
│   └── utils.py       # Shared utilities (formatting, file reading, etc.)
├── scripts/           # Helper scripts (e.g. release.py)
├── tests/             # pytest test suite
├── pyproject.toml     # Project metadata and tool configuration
├── tox.ini            # Test/lint environment definitions
└── Makefile           # Developer convenience targets
```

## Development Setup

Requires **Python ≥ 3.14** and [uv](https://github.com/astral-sh/uv).
Check `pyproject.toml` for the authoritative `requires-python` constraint and dependency versions.

```shell
# Install all dependencies (including dev group)
make init        # → uv sync

# Install in editable mode
make dev         # → uv run pip install --editable .
```

## Running the CLI

```shell
uv run python -m meta_agent.cli -h
# or, after `make dev`:
meta_agent -h
```

## Testing

```shell
make test        # Run pytest
make check       # Run black + ruff + mypy in parallel
make ci          # Run all checks + tests
```

Individual environments can be run via tox (see `tox.ini` for the full list):

```shell
uv run tox -e py314   # unit tests with doctest
uv run tox -e mypy    # strict type checking
uv run tox -e ruff    # linting
uv run tox -e black   # formatting check
```

## Linting & Formatting

Tool settings live in `pyproject.toml` under `[tool.black]`, `[tool.ruff]`, and `[tool.mypy]`.
Refer to those sections for the current line-length, rule selections, and per-file ignores.

Always run `make check` before committing.

## Releasing

To release a new version (updates `pyproject.toml` and `uv.lock`, commits, tags, and pushes):

```shell
make release VERSION=X.Y.Z
# or with optional flags:
make release VERSION=X.Y.Z ARGS="--dry-run"
# or directly via uv:
uv run python scripts/release.py X.Y.Z
```

## Architecture Notes

### Recipe-Driven Design

`meta_agent` wraps the OpenJarvis `Jarvis` client. At runtime, a *recipe* (a TOML file in `~/.openjarvis/recipes/`) specifies:
- `engine` / `model` — the LLM backend
- `agent.type` — the ReAct/orchestrator agent strategy
- `agent.tools` — the tools available to that agent
- `system_prompt` — the agent's persona and instructions

CLI flags for `--engine`, `--model`, `--agent`, `--tools`, and `--system` always override recipe defaults.

### Meta-Agent (`gen`)

`gen.py` runs a special orchestrator agent whose system prompt instructs it to:
1. Call `list_tools` and `list_agents` to discover available capabilities.
2. Design the optimal `agent`, `tools`, and `system_prompt` combination.
3. Output a valid TOML recipe — no code blocks, no commentary.

The generated TOML is validated with `tomllib` and written to `~/.openjarvis/recipes/meta_agent__<name>_<timestamp>.toml`.

### Custom Tools (`tools.py`)

The following tools are registered into the OpenJarvis `ToolRegistry`:

| Tool name            | Description                                        |
|----------------------|----------------------------------------------------|
| `generate_assistant` | Generate a new assistant recipe from a query       |
| `inspect_recipe`     | Show detailed info about a specific recipe         |
| `inspect_agent`      | Show detailed info about a specific agent type     |
| `inspect_tool`       | Show detailed info about a specific tool           |
| `list_tools`         | List all registered tools with descriptions        |
| `list_agents`        | List all registered agents with descriptions       |
| `list_recipes`       | List all registered recipes with descriptions      |

When adding a new tool, register it with `@ToolRegistry.register("<name>")` and keep this table in sync.

### `ask` / `chat` Dispatch

Both commands resolve a recipe name → `AskingOpts`, then call `os.execvp` to replace the current process with the underlying `jarvis ask` or `jarvis chat` CLI.

## Key Conventions

- **Python version** — see `requires-python` in `pyproject.toml`. Use modern syntax freely (`match`/`case`, etc.).
- **Docstrings** — public functions/methods should have one-line docstrings. Check `[tool.ruff.lint]` for which D rules are enforced or ignored.
- **Line length** — defined in `pyproject.toml` under `[tool.black]` and `[tool.ruff]`.
- **Tests** — place new tests in `tests/`. Doctests inside `meta_agent/` are also collected automatically.
- **No fabricated tools/agents** — when contributing to the meta-agent prompt or any agent configuration, use only names that actually exist in the OpenJarvis registries (`list_tools`, `list_agents`).
