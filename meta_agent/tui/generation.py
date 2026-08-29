"""Recipe generation coordinator and helper utilities for MetaAgentTUI."""

from pathlib import Path
from typing import TYPE_CHECKING
import tomllib

from textual.widgets import Button, Markdown, RichLog, Static

from ..api import find_recipe_files, Recipe
from ..gen import generate_assistant, GenRequest
from .helpers import now_datetime_str
from .screens.chat_options import ChatOptionsScreen

if TYPE_CHECKING:
    from .app import MetaAgentTUI


class RecipeGenerator:
    """Coordinates background recipe generation and UI updates."""

    def __init__(self, app: "MetaAgentTUI") -> None:
        """Initialize with app reference."""
        self._app = app

    def execute_generation(self, query: str) -> None:
        """Run recipe generation in background worker thread and update UI."""
        app = self._app
        log = app.query_one("#gen-rich-log", RichLog)
        req = GenRequest(engine=app._engine, model=app._model, query=query, recipes_dir=app._recipes_dir)

        try:
            r = generate_assistant(req)
        except Exception as e:
            err_msg = str(e)

            def _on_exc() -> None:
                ts_err = now_datetime_str()
                try:
                    app.query_one("#gen-status-bar", Static).update(f"❌ Error: {err_msg}")
                    app.query_one("#gen-submit-btn", Button).disabled = False
                    log.write(f"[dim]{ts_err}[/dim] [bold red]✗ Generation error: {err_msg}[/bold red]")
                except Exception:
                    pass
                app.notify(f"Generation error: {err_msg}", severity="error")

            app.call_from_thread(_on_exc)
            return

        if r.success:
            app._last_generated_recipe = r.name
            preview_md = (
                f"# ✅ Recipe Generated: `{r.name}`\n\n"
                f"- **Saved to**: `{r.path}`\n\n"
                "### Recipe TOML Content:\n"
                "```toml\n"
            )
            try:
                content = Path(r.path).read_text(encoding="utf-8")
                preview_md += content
            except Exception:
                preview_md += "# (Could not read generated file content)"
            preview_md += "\n```\n"

            def _on_success() -> None:
                ts_ok = now_datetime_str()
                try:
                    app.query_one("#gen-markdown", Markdown).update(preview_md)
                    app.query_one("#gen-status-bar", Static).update(f"✅ Generated `{r.name}` successfully!")
                    app.query_one("#gen-submit-btn", Button).disabled = False
                    app.query_one("#gen-chat-btn", Button).display = True
                    log.write(f"[dim]{ts_ok}[/dim] [bold green]✓ Successfully generated recipe: {r.name}[/bold green]")
                except Exception:
                    pass
                app.notify(f"Recipe generated: {r.name}", severity="information")
                app._load_recipes()

            app.call_from_thread(_on_success)
        else:

            def _on_failure() -> None:
                ts_fail = now_datetime_str()
                try:
                    app.query_one("#gen-status-bar", Static).update(f"❌ Failed: {r.message}")
                    app.query_one("#gen-submit-btn", Button).disabled = False
                    log.write(f"[dim]{ts_fail}[/dim] [bold red]✗ Generation failed: {r.message}[/bold red]")
                except Exception:
                    pass
                app.notify(f"Generation failed: {r.message}", severity="error")

            app.call_from_thread(_on_failure)

    def launch_chat_for_generated(self) -> None:
        """Launch chat options with the newly generated recipe."""
        app = self._app
        if not app._last_generated_recipe:
            return
        for r in app._recipes:
            if r.name == app._last_generated_recipe:
                app.push_screen(ChatOptionsScreen(r, app._engine, app._model, export_dir=app._export_dir))
                return

        # Fallback: discover from recipes_dir
        matched_files = find_recipe_files(app._last_generated_recipe, app._recipes_dir)
        if matched_files:
            try:
                with open(matched_files[0], "rb") as f:
                    data = tomllib.load(f)
                r_dict = data.get("recipe", {})
                rec = Recipe(
                    name=r_dict.get("name", app._last_generated_recipe),
                    description=r_dict.get("description", ""),
                    system_prompt=r_dict.get("system", ""),
                    engine_key=r_dict.get("engine", app._engine),
                    model=r_dict.get("model", app._model),
                    agent_type=r_dict.get("agent", "native_react"),
                    tools=r_dict.get("tools", []),
                )
                app.push_screen(ChatOptionsScreen(rec, app._engine, app._model, export_dir=app._export_dir))
            except Exception:
                pass
