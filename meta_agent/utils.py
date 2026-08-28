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


def get_default_export_dir() -> str:
    """Get the default export directory (~/Documents/meta_agent or XDG equivalent)."""
    import os
    from pathlib import Path

    xdg_doc = os.environ.get("XDG_DOCUMENTS_DIR")
    if xdg_doc:
        base = Path(xdg_doc)
    else:
        base = Path.home() / "Documents"
    return str(base / "meta_agent")


def copy_to_system_clipboard(text: str) -> bool:
    """Copy text to system clipboard via OS native command if available."""
    import shutil
    import subprocess
    import sys

    timeout_sec = 2.0

    # macOS
    if sys.platform == "darwin" and shutil.which("pbcopy"):
        try:
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"), timeout=timeout_sec)
            return p.returncode == 0
        except Exception:
            pass

    # Wayland
    if shutil.which("wl-copy"):
        try:
            p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"), timeout=timeout_sec)
            return p.returncode == 0
        except Exception:
            pass

    # X11 (xclip)
    if shutil.which("xclip"):
        try:
            p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"), timeout=timeout_sec)
            return p.returncode == 0
        except Exception:
            pass

    # X11 (xsel)
    if shutil.which("xsel"):
        try:
            p = subprocess.Popen(["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"), timeout=timeout_sec)
            return p.returncode == 0
        except Exception:
            pass

    # Windows (clip.exe)
    if sys.platform == "win32" and shutil.which("clip"):
        try:
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-16le"), timeout=timeout_sec)
            return p.returncode == 0
        except Exception:
            pass

    return False


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
