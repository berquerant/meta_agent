"""Shared helpers for the TUI: filtering, markdown formatting, command building, and session parsing."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
import re
import shlex
from typing import Any

from ..api import Agent, Engine, list_agents, list_tools, Model, Recipe, Tool
from ..cmd import format_obj
from .intent import (
    build_recipe_action_prompt,
    build_semantic_search_prompt,
    parse_recipe_action_intent,
    RecipeActionIntent,
)

__all__ = [
    "CTRL_C_TIMEOUT",
    "filter_items",
    "find_matching_recipe",
    "recipe_markdown",
    "agent_markdown",
    "tool_markdown",
    "ChatCommandOptions",
    "build_chat_command_parts",
    "format_command_preview",
    "now_datetime_str",
    "build_chat_prompt",
    "RecipeActionIntent",
    "build_recipe_action_prompt",
    "build_semantic_search_prompt",
    "parse_recipe_action_intent",
    "RestoredChatSession",
    "parse_exported_chat_file",
    "RuntimeOptions",
    "fetch_runtime_options",
    "InputHistory",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CTRL_C_TIMEOUT: float = 2.0  # seconds timeout for double Ctrl+C app quit


# ---------------------------------------------------------------------------
# Filter Utilities
# ---------------------------------------------------------------------------


def filter_items(items: list[Any], query: str) -> list[Any]:
    """Filter items whose name contains query (case-insensitive substring)."""
    q = query.strip().lower()
    if not q:
        return items
    return [x for x in items if q in x.name.lower()]


def find_matching_recipe(recipes: Sequence[Recipe], target: str | None) -> Recipe | None:
    """Locate matching recipe object by exact or substring name match."""
    if not target or not recipes:
        return None
    tgt_clean = target.strip().lower()
    if not tgt_clean:
        return None
    # 1. Exact match
    for r in recipes:
        if r.name.lower() == tgt_clean:
            return r
    # 2. Substring match fallback
    for r in recipes:
        if tgt_clean in r.name.lower() or r.name.lower() in tgt_clean:
            return r
    return None


# ---------------------------------------------------------------------------
# Markdown Formatting Helpers
# ---------------------------------------------------------------------------


def _obj_to_markdown(obj: Any) -> str:
    """Format dataclass object into Markdown text with bold keys."""
    return format_obj(asdict(obj), "md")


def recipe_markdown(recipe: Recipe) -> str:
    """Convert Recipe to rendered Markdown string."""
    return _obj_to_markdown(recipe)


def agent_markdown(agent: Agent) -> str:
    """Convert Agent to rendered Markdown string."""
    return _obj_to_markdown(agent)


def tool_markdown(tool: Tool) -> str:
    """Convert Tool to rendered Markdown string."""
    return _obj_to_markdown(tool)


def engine_markdown(engine: Engine) -> str:
    """Convert Engine to rendered Markdown string."""
    return _obj_to_markdown(engine)


def model_markdown(model: Model) -> str:
    """Convert Model to rendered Markdown string."""
    return _obj_to_markdown(model)


# ---------------------------------------------------------------------------
# Chat Command Builders
# ---------------------------------------------------------------------------


@dataclass
class ChatCommandOptions:
    """Options used to build the CLI invocation command for `meta_agent chat`."""

    recipe: Recipe
    engine: str = ""
    model: str = ""
    agent: str = ""
    tools: str = ""
    system: str = ""
    default_engine: str = ""
    default_model: str = ""
    truncate_system: bool = False


def _append_override(parts: list[str], flag: str, val: str, default: str) -> None:
    """Append flag and value if overridden value differs from default."""
    if val and val != default:
        parts.extend([flag, shlex.quote(val)])


def _append_tools_override(parts: list[str], tls: str, rec_tools: list[str]) -> None:
    """Append --tools flag if provided tools list differs from recipe tools."""
    rec_tools_str = ", ".join(rec_tools) if rec_tools else ""
    norm_tools = ",".join(t.strip() for t in tls.split(",") if t.strip())
    norm_rec_tools = ",".join(t.strip() for t in rec_tools_str.split(",") if t.strip())
    if tls and norm_tools != norm_rec_tools:
        parts.extend(["--tools", shlex.quote(norm_tools)])


def _append_system_override(parts: list[str], sys: str, rec_system: str, truncate: bool) -> None:
    """Append --system flag if provided prompt differs from recipe system prompt."""
    norm_rec_sys = rec_system.strip().replace("\r\n", "\n")
    norm_sys = sys.strip().replace("\r\n", "\n")
    if norm_sys and norm_sys != norm_rec_sys:
        display_sys = (norm_sys[:60] + "...") if (truncate and len(norm_sys) > 60) else norm_sys
        parts.extend(["--system", shlex.quote(display_sys)])


def build_chat_command_parts(
    recipe: Recipe | None = None,
    engine: str = "",
    model: str = "",
    agent: str = "",
    tools: str = "",
    system: str = "",
    default_engine: str = "",
    default_model: str = "",
    truncate_system: bool = False,
    *,
    opts: ChatCommandOptions | None = None,
) -> list[str]:
    """
    Build the command parts list for running `meta_agent chat`.

    Only options that differ from recipe defaults or fallback defaults
    are explicitly included in the generated command flags.
    """
    if opts is not None:
        rec, eng, mod, agt = opts.recipe, opts.engine, opts.model, opts.agent
        tls, sys, def_eng, def_mod = opts.tools, opts.system, opts.default_engine, opts.default_model
        trunc_sys = opts.truncate_system
    else:
        if recipe is None:
            return []
        rec, eng, mod, agt = recipe, engine, model, agent
        tls, sys, def_eng, def_mod = tools, system, default_engine, default_model
        trunc_sys = truncate_system

    parts: list[str] = ["meta_agent", "chat", "--recipe", shlex.quote(rec.name)]
    _append_override(parts, "--engine", eng, rec.engine_key or def_eng)
    _append_override(parts, "--model", mod, rec.model or def_mod)
    _append_override(parts, "--agent", agt, rec.agent_type or "")
    _append_tools_override(parts, tls, rec.tools)
    _append_system_override(parts, sys, rec.system_prompt or "", trunc_sys)
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
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def build_chat_prompt(
    system_prompt: str | None,
    history: list[tuple[str, str, str]],
    new_user_message: str,
) -> str:
    """Construct full LLM prompt including system persona, turn history, and latest input."""
    prompt_lines: list[str] = []
    if system_prompt:
        prompt_lines.append(f"# System Prompt\n{system_prompt.strip()}\n")

    if history:
        prompt_lines.append("# Conversation History")
        for role, msg, _ in history:
            prompt_lines.append(f"<{role}>\n{msg.strip()}\n</{role}>")
        prompt_lines.append("")
        prompt_lines.append(f"# Current User Query\n{new_user_message.strip()}")
    else:
        prompt_lines.append(f"# User Query\n{new_user_message.strip()}")
    return "\n".join(prompt_lines)


# ---------------------------------------------------------------------------
# Chat History Session Parser
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
# Runtime Resource Inspection Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeOptions:
    """Available runtime presets for engines, models, agents, and tools."""

    engines: list[tuple[str, str]]
    models: list[tuple[str, str]]
    agents: list[tuple[str, str]]
    tools: list[str]


def fetch_runtime_options(default_engine: str, default_model: str) -> RuntimeOptions:
    """Query LLM client and registries to discover available options with fallback defaults."""
    from meta_agent.llm import get_llm_client

    client = get_llm_client()
    try:
        discovered_engines = client.list_engines(default_engine)
        engine_opts = [(e, e) for e in discovered_engines] if discovered_engines else []
        discovered_models = client.list_models(default_engine)
        model_opts = [(m, m) for m in discovered_models] if discovered_models else []
        if not engine_opts:
            raise ValueError("No engines discovered")
        if not model_opts:
            model_opts = [(default_model, default_model)]
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


# ---------------------------------------------------------------------------
# Input History Manager
# ---------------------------------------------------------------------------


class InputHistory:
    """Manages input prompt history navigation with draft persistence."""

    def __init__(self, max_size: int = 100) -> None:
        """Initialize empty history buffer."""
        self._entries: list[str] = []
        self._cursor: int = -1
        self._draft: str = ""
        self._max_size = max_size

    @property
    def entries(self) -> list[str]:
        """Return a copy of the history entries."""
        return list(self._entries)

    def append(self, text: str) -> None:
        """Append a new non-empty entry and reset the navigation cursor."""
        text = text.strip()
        if not text:
            return
        self._entries.append(text)
        if len(self._entries) > self._max_size:
            self._entries.pop(0)
        self._cursor = -1
        self._draft = ""

    def previous(self, current_draft: str) -> str | None:
        """Navigate backwards in history (older prompt)."""
        if not self._entries:
            return None

        if self._cursor == -1:
            self._draft = current_draft
            self._cursor = len(self._entries) - 1
        elif self._cursor > 0:
            self._cursor -= 1

        return self._entries[self._cursor]

    def next(self) -> str | None:
        """Navigate forwards in history (newer prompt or draft)."""
        if not self._entries or self._cursor == -1:
            return None

        if self._cursor < len(self._entries) - 1:
            self._cursor += 1
            return self._entries[self._cursor]

        self._cursor = -1
        return self._draft

    def clear(self) -> None:
        """Clear all entries and reset cursor."""
        self._entries.clear()
        self._cursor = -1
        self._draft = ""
