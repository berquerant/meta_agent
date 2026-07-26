import json
import sys
from datetime import datetime
from typing import Any


def read_file_or_stdin_or_str(s: str) -> str:
    """Read a file if s is @xxx. Read stdin if s is @-. Otherwise return s."""
    if s.startswith("@"):
        t = s.removeprefix("@")
        match t:
            case "-":
                return sys.stdin.read()
            case _:
                with open(t) as f:
                    return f.read()
    return s


def json_dumps(x: Any) -> str:
    """Serialize an object as a JSON string."""
    return json.dumps(x, separators=(",", ":"), ensure_ascii=False)


def now_str() -> str:
    """Get the current time string."""
    return datetime.now().strftime("%Y%m%d%H%M%S")


def __format_obj_attr_into_text(k: str, v: Any) -> str:
    s = str(v)
    if any((x in s) for x in ["```", "#"]):
        s = "`````\n" + s + "`````\n"
    return f"## {k}\n{s}"


def format_obj_into_text(title_key: str, x: dict[str, Any]) -> str:
    """Format an object as a markdown."""
    name = x[title_key]
    attrs = [__format_obj_attr_into_text(k, x[k]) for k in sorted(x.keys())]
    return f"# {name}" + "\n" + "\n\n".join(attrs)


def format_obj_list_into_text(title_key: str, xs: list[dict[str, Any]]) -> str:
    """Format objects as a markdown."""
    return "\n\n".join(format_obj_into_text(title_key, x) for x in xs)
