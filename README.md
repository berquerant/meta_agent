# meta_agent

A CLI tool and interactive Terminal UI (TUI) acting as a *meta-agent* — generating, managing, and executing AI assistant recipes using the [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) framework.

```shell
❯ uv run python -m meta_agent.cli -h
usage: meta_agent [-h] {get,gen,chat,ask,jarvis,tui} ...

positional arguments:
  {get,gen,chat,ask,jarvis,tui}
    get                 Get resources
    gen                 Generate AI assistant recipe
    chat                Start an interactive multi-turn chat session
    ask                 Ask Jarvis a question
    jarvis              Raw jarvis command
    tui                 Launch the interactive TUI

options:
  -h, --help            show this help message and exit
```

---

## 🖥️ Terminal UI (`tui`)

Launch an interactive, feature-rich Textual terminal interface:

```shell
meta_agent tui
# or with custom settings:
meta_agent tui --engine ollama --model llama3 --export-dir ~/Documents/meta_agent
```

### ✨ Key Features
- **Resource Management**: Browse and search recipes, agent architectures, and tools with instant markdown previews.
- **Smart Ask LLM**: Natural language query bar supporting semantic search, auto-generating recipes, and launching chat sessions.
- **Interactive Chat**: Stream multi-turn conversations directly in the terminal with token-by-token rendering, copy-to-clipboard, and session export.
- **Session Resume & History**: Restore previous chat sessions from exported markdown files.
- **Recipe Editor & Deletion**: Edit recipe TOML with real-time syntax validation, or safely delete recipes with duplicate file preview.
- **Permanent Generate Tab**: Generate custom AI assistant recipes with streaming status updates and activity logs.

---

## 🚀 CLI Subcommands

| Command | Description |
|---|---|
| `tui` | Launch the full interactive terminal user interface |
| `get` | List or inspect recipes (`recipes`, `recipe`), agents (`agents`, `agent`), and tools (`tools`, `tool`) |
| `gen` | Generate a new AI assistant recipe via LLM orchestrator |
| `chat` | Start an interactive multi-turn chat session with an assistant recipe |
| `ask` | Ask a single question using a recipe-configured agent |
| `jarvis` | Forward raw arguments directly to the underlying `jarvis` CLI |

---

## 🛠️ Development

Requires **Python ≥ 3.14** and [uv](https://github.com/astral-sh/uv).

```shell
# Setup development environment
make init

# Install editable package
make dev

# Run linting, formatting, and unit tests
make check
make test
make ci
```
