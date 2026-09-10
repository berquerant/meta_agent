"""Screen routing and recipe action coordinator for MetaAgentTUI."""

from typing import TYPE_CHECKING

from ...api import find_recipe_files, Recipe
from .chat_options import ChatOptionsScreen
from .delete_recipe import DeleteRecipeScreen
from .edit_recipe import EditRecipeScreen
from .help import HelpScreen
from .recipe_detail import RecipeDetailScreen
from .resume_chat import ResumeChatScreen

if TYPE_CHECKING:
    from ..app import MetaAgentTUI


class ScreenNavigator:
    """Coordinates screen transitions, modals, and recipe action dialogs."""

    def __init__(self, app: "MetaAgentTUI") -> None:
        """Initialize with app reference."""
        self._app = app

    def open_help(self) -> None:
        """Display the help and keyboard shortcuts modal."""
        self._app.push_screen(HelpScreen())

    def resume_chat(self) -> None:
        """Open session picker modal to resume previous chat session."""
        self._app.push_screen(ResumeChatScreen(self._app._export_dir))

    def open_chat_options(self, recipe: Recipe) -> None:
        """Push ChatOptionsScreen to review and start chat."""
        self._app.push_screen(
            ChatOptionsScreen(
                recipe,
                self._app._engine,
                self._app._model,
                export_dir=self._app._export_dir,
            )
        )

    def chat_recipe(self) -> None:
        """Open chat options for the currently selected recipe."""
        if self._app._selected_recipe is not None:
            self.open_chat_options(self._app._selected_recipe)
        else:
            self._app.notify("Please select a recipe first", severity="warning")

    def edit_recipe(self) -> None:
        """Open editor screen for currently selected recipe."""
        if self._app._selected_recipe is None:
            self._app.notify("Please select a recipe first", severity="warning")
            return

        recipe_name = self._app._selected_recipe.name
        matched_files = find_recipe_files(recipe_name, self._app._recipes_dir)

        def _on_edit_done(saved: bool | None) -> None:
            if saved:
                self._app.notify(f"Recipe '{recipe_name}' updated", severity="information")
                self._app._load_recipes()

        self._app.push_screen(
            EditRecipeScreen(recipe_name, matched_files),
            _on_edit_done,
        )

    def delete_recipe(self) -> None:
        """Prompt to delete selected recipe on recipes tab, or show recipe details modal on refactor tab."""
        from textual.widgets import SelectionList, TabbedContent

        try:
            active_tab = self._app.query_one(TabbedContent).active
        except Exception:
            active_tab = "tab-recipes"

        if active_tab == "tab-refactor":
            try:
                sl = self._app.query_one("#refactor-recipe-list", SelectionList)
                rec_name: str | None = None
                if sl.highlighted is not None and 0 <= sl.highlighted < sl.option_count:
                    opt = sl.get_option_at_index(sl.highlighted)
                    rec_name = str(opt.value)
                elif sl.selected:
                    rec_name = list(sl.selected)[0]
                elif self._app._selected_recipe:
                    rec_name = self._app._selected_recipe.name

                if not rec_name:
                    self._app.notify("No recipe selected to view details", severity="warning")
                    return

                matched = [r for r in self._app._recipes if r.name == rec_name]
                if matched:
                    self._app.push_screen(RecipeDetailScreen(matched[0]))
                else:
                    self._app.notify(f"Recipe '{rec_name}' not found", severity="warning")
            except Exception:
                pass
            return

        if self._app._selected_recipe is None:
            self._app.notify("Please select a recipe first", severity="warning")
            return

        recipe_name = self._app._selected_recipe.name
        matched_files = find_recipe_files(recipe_name, self._app._recipes_dir)

        def _on_delete_done(deleted: bool | None) -> None:
            if deleted:
                self._app.notify(f"Recipe '{recipe_name}' deleted", severity="information")
                self._app._load_recipes()

        self._app.push_screen(
            DeleteRecipeScreen(recipe_name, matched_files),
            _on_delete_done,
        )
