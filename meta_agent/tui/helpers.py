"""Shared helpers for the TUI: sorting, filtering, markdown formatting, command building, and prompt generation."""

from dataclasses import asdict, dataclass
import shlex
from typing import Any

from ..api import Agent, list_agents, list_tools, Recipe, Tool
from ..cmd import format_obj

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SORT_OPTIONS: list[tuple[str, str]] = [
    ("A → Z", "alpha_asc"),
    ("Z → A", "alpha_desc"),
]

SortKey = str  # "alpha_asc" | "alpha_desc"

CTRL_C_TIMEOUT: float = 2.0  # seconds timeout for double Ctrl+C app quit


# ---------------------------------------------------------------------------
# Sort & Filter Utilities
# ---------------------------------------------------------------------------


def sort_items(items: list[Any], sort_key: SortKey) -> list[Any]:
    """Sort a list of dataclass items by name."""
    reverse = sort_key == "alpha_desc"
    return sorted(items, key=lambda x: x.name.lower(), reverse=reverse)


def filter_items(items: list[Any], query: str) -> list[Any]:
    """Filter items whose name contains query (case-insensitive substring)."""
    q = query.strip().lower()
    if not q:
        return items
    return [x for x in items if q in x.name.lower()]


# ---------------------------------------------------------------------------
# Markdown Formatting Helpers
# ---------------------------------------------------------------------------


def _obj_to_markdown(obj: dict[str, Any]) -> str:
    """Convert a dataclass dict to a Markdown string for display."""
    return format_obj(obj, "text")


def recipe_markdown(r: Recipe) -> str:
    """Format recipe as markdown."""
    return _obj_to_markdown(asdict(r))


def agent_markdown(a: Agent) -> str:
    """Format agent as markdown."""
    return _obj_to_markdown(asdict(a))


def tool_markdown(t: Tool) -> str:
    """Format tool as markdown."""
    return _obj_to_markdown(asdict(t))


# ---------------------------------------------------------------------------
# Command Building Helpers
# ---------------------------------------------------------------------------


def build_chat_command_parts(
    recipe: Recipe,
    engine: str,
    model: str,
    agent: str,
    tools: str,
    system: str,
    default_engine: str,
    default_model: str,
    truncate_system: bool = False,
) -> list[str]:
    """
    Build the command parts list for running `meta_agent chat`.

    Only options that differ from recipe defaults or fallback defaults
    are explicitly included in the generated command flags.
    """
    parts: list[str] = ["meta_agent", "chat", "--recipe", shlex.quote(recipe.name)]

    rec_engine = recipe.engine_key or default_engine
    if engine and engine != rec_engine:
        parts.extend(["--engine", shlex.quote(engine)])

    rec_model = recipe.model or default_model
    if model and model != rec_model:
        parts.extend(["--model", shlex.quote(model)])

    rec_agent = recipe.agent_type or ""
    if agent and agent != rec_agent:
        parts.extend(["--agent", shlex.quote(agent)])

    rec_tools = ", ".join(recipe.tools) if recipe.tools else ""
    norm_tools = ",".join(t.strip() for t in tools.split(",") if t.strip())
    norm_rec_tools = ",".join(t.strip() for t in rec_tools.split(",") if t.strip())
    if tools and norm_tools != norm_rec_tools:
        parts.extend(["--tools", shlex.quote(norm_tools)])

    rec_system = (recipe.system_prompt or "").strip().replace("\r\n", "\n")
    norm_system = system.strip().replace("\r\n", "\n")
    if norm_system and norm_system != rec_system:
        if truncate_system and len(norm_system) > 60:
            display_system = norm_system[:60] + "..."
        else:
            display_system = norm_system
        parts.extend(["--system", shlex.quote(display_system)])

    return parts


def format_command_preview(parts: list[str]) -> str:
    """Format command parts with line-wrapping backslashes for preview display."""
    if not parts:
        return ""
    head = " ".join(parts[:4])
    tail_items: list[str] = []
    i = 4
    while i < len(parts):
        if i + 1 < len(parts):
            tail_items.append(f"{parts[i]} {parts[i+1]}")
            i += 2
        else:
            tail_items.append(parts[i])
            i += 1

    tail = " \\\n  ".join(tail_items)
    return f"{head} \\\n  {tail}" if tail else head


# ---------------------------------------------------------------------------
# Prompt Building Helpers
# ---------------------------------------------------------------------------


def now_datetime_str() -> str:
    """Return current date and time formatted as 'YYYY-MM-DD HH:MM:SS'."""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def build_chat_prompt(
    system_prompt: str | None,
    history: list[tuple[str, str, str]],
    current_query: str,
) -> str:
    """
    Construct prompt string including system prompt and prior conversation history.

    - 1st turn: system prompt + user query
    - Multi-turn: system prompt + prior turns tagged with <User>/<Assistant> + current query
    """
    prompt_parts: list[str] = []
    if system_prompt:
        prompt_parts.append(f"# System Prompt\n{system_prompt}\n")

    prior_turns = history[:-1] if history else []
    if prior_turns:
        prompt_parts.append("# Conversation History")
        for role, text, _time in prior_turns:
            prompt_parts.append(f"<{role}>\n{text}\n</{role}>")
        prompt_parts.append(f"\n# Current User Query\n{current_query}")
    else:
        if not system_prompt:
            prompt_parts.append(current_query)
        else:
            prompt_parts.append(f"# User Query\n{current_query}")

    return "\n\n".join(prompt_parts)


# ---------------------------------------------------------------------------
# Recipe Action Intent Helpers
# ---------------------------------------------------------------------------


@dataclass
class RecipeActionIntent:
    """Action intent parsed from user LLM query in the recipes tab."""

    action: str  # "search" | "edit" | "delete"
    target: str | None = None
    instruction: str | None = None
    ranked_names: list[str] | None = None


def parse_recipe_action_intent(raw_response: str) -> RecipeActionIntent:
    """Parse JSON or structured text response from LLM recipe action prompt."""
    import json
    import re

    # Try extracting JSON object {...}
    json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            action = str(data.get("action", "search")).lower()
            if action in ("delete", "remove", "del"):
                action = "delete"
            elif action in ("edit", "update", "modify"):
                action = "edit"
            else:
                action = "search"

            target = data.get("target") or data.get("recipe") or data.get("name")
            target_str = str(target).strip() if target else None
            instruction = data.get("instruction") or data.get("changes") or data.get("detail")
            instruction_str = str(instruction).strip() if instruction else None
            ranked = data.get("ranked_names") or data.get("matches") or []
            ranked_list = [str(x).strip() for x in ranked if str(x).strip()] if isinstance(ranked, list) else []

            return RecipeActionIntent(
                action=action,
                target=target_str,
                instruction=instruction_str,
                ranked_names=ranked_list,
            )
        except Exception:
            pass

    # Fallback to pure newline-separated list as search results
    lines = [line.lstrip("- *").strip() for line in raw_response.splitlines() if line.strip()]
    return RecipeActionIntent(action="search", ranked_names=lines)


# ---------------------------------------------------------------------------
# Exported Chat File Restoration
# ---------------------------------------------------------------------------


@dataclass
class RestoredChatSession:
    """Restored chat session configuration and message history from an exported Markdown file."""

    recipe_name: str
    engine: str
    model: str
    agent: str | None
    tools: str | None
    system: str | None
    history: list[tuple[str, str, str]]  # (role, text, timestamp)


def parse_exported_chat_file(content: str) -> RestoredChatSession | None:
    """Parse an exported chat session markdown file into RestoredChatSession."""
    import re

    header_m = re.search(r"# Chat Session:\s*(.+)", content)
    if not header_m:
        return None

    recipe_name = header_m.group(1).strip()

    def _extract_field(field_name: str) -> str | None:
        m = re.search(rf"- \*\*{field_name}\*\*:\s*(.+)", content)
        if m:
            val = m.group(1).strip()
            if val.lower() in ("none", "direct engine", ""):
                return None if field_name != "engine" and field_name != "model" else val
            return val
        return None

    engine = _extract_field("Engine") or "ollama"
    model = _extract_field("Model") or "gemma4:12b"
    agent = _extract_field("Agent")
    tools = _extract_field("Tools")
    system = _extract_field("System")

    # Extract conversation messages: ## 👤 User [timestamp] or ## 🤖 Assistant [timestamp]
    msg_pattern = re.compile(
        r"##\s*(?:👤|🤖)?\s*(User|Assistant)\s*(?:\[(.*?)\])?\n(.*?)(?=\n##\s*(?:👤|🤖)?\s*(?:User|Assistant)|\Z)",
        re.DOTALL,
    )
    history: list[tuple[str, str, str]] = []
    for m in msg_pattern.finditer(content):
        role = m.group(1).strip()
        ts = (m.group(2) or "").strip() or now_datetime_str()
        text = m.group(3).strip()
        if text:
            history.append((role, text, ts))

    return RestoredChatSession(
        recipe_name=recipe_name,
        engine=engine,
        model=model,
        agent=agent,
        tools=tools,
        system=system,
        history=history,
    )


# ---------------------------------------------------------------------------
# Runtime Options Discovery
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeOptions:
    """Available runtime presets for engines, models, agents, and tools."""

    engines: list[tuple[str, str]]
    models: list[tuple[str, str]]
    agents: list[tuple[str, str]]
    tools: list[str]


def fetch_runtime_options(default_engine: str, default_model: str) -> RuntimeOptions:
    """Query OpenJarvis and registries to discover available options with fallback defaults."""
    from openjarvis import Jarvis

    try:
        j = Jarvis(engine_key=default_engine)
        engine_opts = [(e, e) for e in j.list_engines()]
        model_opts = [(m, m) for m in j.list_models()]
        j.close()
    except Exception:
        engine_opts = [
            ("ollama", "ollama"),
            ("vllm", "vllm"),
            ("cloud", "cloud"),
            ("litellm", "litellm"),
            ("llamacpp", "llamacpp"),
        ]
        model_opts = [(default_model, default_model)]

    try:
        agent_opts = [(a.name, a.name) for a in list_agents()]
    except Exception:
        agent_opts = [
            ("orchestrator", "orchestrator"),
            ("native_react", "native_react"),
            ("simple", "simple"),
        ]

    try:
        tool_names = [t.name for t in list_tools()]
    except Exception:
        tool_names = ["file_read", "file_write", "bash", "calculator", "think", "web_search"]

    return RuntimeOptions(
        engines=engine_opts,
        models=model_opts,
        agents=agent_opts,
        tools=tool_names,
    )
