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

## 🐳 Docker Usage

### Build Image

BuildKit cache mount is supported for faster builds:

```shell
docker build -t meta_agent .
```

### Running with Host Ollama

To communicate with an Ollama instance running on the host machine:

1. **Host Setup**:
   Ensure Ollama is listening on all interfaces (or accessible to containers).
   - On macOS: Default Ollama app binds to localhost; if needed, launch with `OLLAMA_HOST=0.0.0.0 ollama serve`.
   - On Linux: Make sure Ollama service is accessible from the Docker bridge/gateway.

2. **Run Container**:
   - **macOS**:
     ```shell
     docker run -it --rm \
       -v ~/.openjarvis/recipes:/root/.openjarvis/recipes \
       -v ~/Documents/meta_agent:/var/log/meta_agent \
       -e OLLAMA_HOST=http://host.docker.internal:11434 \
       meta_agent meta_agent tui -d /var/log/meta_agent
     ```
   - **Linux**:
     ```shell
     docker run -it --rm \
       --add-host=host.docker.internal:host-gateway \
       -v ~/.openjarvis/recipes:/root/.openjarvis/recipes \
       -e OLLAMA_HOST=http://host.docker.internal:11434 \
       meta_agent meta_agent tui -d /var/log/meta_agent
     ```
     *(Or run with `--network host` and `-e OLLAMA_HOST=http://127.0.0.1:11434` on Linux)*

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

