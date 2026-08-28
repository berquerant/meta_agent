"""Shared helpers for the TUI: sort, filter, and markdown formatting."""

from dataclasses import asdict
from typing import Any

from ..api import Agent, Recipe, Tool
from ..cmd import format_obj

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SORT_OPTIONS: list[tuple[str, str]] = [
    ("A → Z", "alpha_asc"),
    ("Z → A", "alpha_desc"),
]

SortKey = str  # "alpha_asc" | "alpha_desc"

CTRL_C_TIMEOUT: float = 2.0  # seconds


# ---------------------------------------------------------------------------
# Sort / filter
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
# Markdown formatting
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
