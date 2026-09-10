"""Recipe refactoring coordinator and helper utilities for MetaAgentTUI."""

from typing import TYPE_CHECKING

from textual.widgets import Button, Markdown, RichLog, Static


from ..refactor import (
    RefactorRequest,
    RefactorResult,
    refactor_recipe,
    save_refactored_recipe,
)
from .helpers import now_datetime_str

if TYPE_CHECKING:
    from .app import MetaAgentTUI


class RecipeRefactorer:
    """Coordinates background recipe refactoring and UI updates."""

    def __init__(self, app: "MetaAgentTUI") -> None:
        """Initialize with app reference."""
        self._app = app
        self._last_results: list[RefactorResult] = []

    def execute_refactor(
        self,
        recipes: list[str],
        query: str = "",
        target: str = "all",
    ) -> None:
        """Run recipe refactoring in background worker thread and update UI."""
        app = self._app
        log = app.query_one("#refactor-rich-log", RichLog)

        if not recipes:
            app.call_from_thread(
                lambda: app.notify("Please select at least one recipe to refactor", severity="warning")
            )
            return

        self._last_results = []
        total = len(recipes)

        def _format_all_results_markdown(results: list[RefactorResult]) -> str:
            if not results:
                return "# No Refactoring Results"

            parts = []
            for res in results:
                parts.append(f"# Refactor Report: `{res.recipe_name}`")
                parts.append(f"- **Original File**: `{res.original_path}`")
                parts.append(f"- **Version**: `{res.old_version}` ➔ `{res.new_version}`")

                if res.review_comments:
                    parts.append("\n### 📝 Review & Evaluation:")
                    parts.append(res.review_comments)

                if res.validation_before.has_issues:
                    parts.append("\n### ⚠️ Issues Before Refactoring:")
                    for w in res.validation_before.warnings:
                        parts.append(f"- {w}")

                if res.validation_after.has_issues:
                    parts.append("\n### ⚠️ Issues After Refactoring:")
                    for w in res.validation_after.warnings:
                        parts.append(f"- {w}")

                if res.diff:
                    parts.append("\n### 🔍 Diff Preview:")
                    parts.append("```diff\n" + res.diff + "\n```")
                elif res.refactored_content:
                    parts.append("\n### 📄 Refactored TOML:")
                    parts.append("```toml\n" + res.refactored_content + "\n```")
                parts.append("\n---\n")
            return "\n".join(parts)

        for i, recipe_name in enumerate(recipes, start=1):
            req = RefactorRequest(
                recipe_name_or_path=recipe_name,
                query=query,
                engine=app._engine,
                model=app._model,
                recipes_dir=app._recipes_dir,
                target=target,
            )

            ts_start = now_datetime_str()
            log.write(
                f"[dim]{ts_start}[/dim] [cyan]>[/cyan] [{i}/{total}] Evaluating & refactoring '{recipe_name}' "
                f"(target={target})..."
            )

            try:
                res = refactor_recipe(req)
            except Exception as e:
                err_msg = str(e)
                res = RefactorResult(
                    recipe_name=recipe_name,
                    original_path="",
                    original_content="",
                    refactored_content="",
                    diff="",
                    review_comments="",
                    old_version="0.1.0",
                    new_version="0.1.0",
                    success=False,
                    error_message=err_msg,
                )

            self._last_results.append(res)
            ts_end = now_datetime_str()

            if res.success:
                log.write(
                    f"[dim]{ts_end}[/dim] [bold green]✓[/bold green] [{i}/{total}] "
                    f"Refactored '{recipe_name}' ({res.old_version} -> {res.new_version})"
                )
            else:
                log.write(
                    f"[dim]{ts_end}[/dim] [bold red]✗[/bold red] [{i}/{total}] "
                    f"Failed '{recipe_name}': {res.error_message}"
                )

            # Progressive UI update
            current_results = list(self._last_results)

            def _update_progress(step: int = i, res_list: list[RefactorResult] = current_results) -> None:
                try:
                    md_text = _format_all_results_markdown(res_list)
                    app.query_one("#refactor-markdown", Markdown).update(md_text)
                    status_text = f"Refactored {step}/{total} recipes."
                    app.query_one("#refactor-status-bar", Static).update(status_text)
                except Exception:
                    pass

            app.call_from_thread(_update_progress)

        def _on_finish() -> None:
            try:
                app.query_one("#refactor-submit-btn", Button).disabled = False
                app.query_one("#refactor-save-inplace-btn", Button).display = True
                app.query_one("#refactor-save-new-btn", Button).display = True
                app.query_one("#refactor-discard-btn", Button).display = True
                app.query_one("#refactor-status-bar", Static).update("✅ Refactoring completed.")
            except Exception:
                pass
            app.notify(f"Refactoring complete for {len(self._last_results)} recipe(s)", severity="information")

        app.call_from_thread(_on_finish)

    def save_results(self, in_place: bool) -> None:
        """Save the last refactored results in-place or as new files."""
        app = self._app
        log = app.query_one("#refactor-rich-log", RichLog)

        if not self._last_results:
            app.notify("No refactored results available to save", severity="warning")
            return

        success_count = 0
        for res in self._last_results:
            if not res.success:
                continue
            ok, target_path, msg = save_refactored_recipe(
                res,
                in_place=in_place,
                recipes_dir=app._recipes_dir or None,
            )
            ts = now_datetime_str()
            if ok:
                success_count += 1
                log.write(f"[dim]{ts}[/dim] [bold green]✓ Saved:[/bold green] {msg}")
            else:
                log.write(f"[dim]{ts}[/dim] [bold red]✗ Save failed:[/bold red] {msg}")

        app._load_recipes()
        if success_count > 0:
            mode_str = "in-place" if in_place else "as new files"
            app.notify(f"Successfully saved {success_count} recipe(s) {mode_str}", severity="information")
        else:
            app.notify("Failed to save recipes or no valid changes", severity="error")

    def discard_results(self) -> None:
        """Discard refactoring results and reset preview/status."""
        app = self._app
        log = app.query_one("#refactor-rich-log", RichLog)
        self._last_results = []
        try:
            app.query_one("#refactor-save-inplace-btn", Button).display = False
            app.query_one("#refactor-save-new-btn", Button).display = False
            app.query_one("#refactor-discard-btn", Button).display = False
            app.query_one("#refactor-status-bar", Static).update("Refactoring changes discarded.")
            app.query_one("#refactor-markdown", Markdown).update(
                "# Recipe Refactoring & Optimization\n"
                "Refactoring changes were discarded. Select recipes and click Refactor to start again."
            )
        except Exception:
            pass
        ts = now_datetime_str()
        log.write(f"[dim]{ts}[/dim] [bold yellow]Refactoring results discarded.[/bold yellow]")
        app.notify("Refactoring results discarded", severity="information")
