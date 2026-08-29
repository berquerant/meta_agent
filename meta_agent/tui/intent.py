"""LLM semantic search and intent parsing / routing for MetaAgentTUI."""

from dataclasses import dataclass
import json
import re
from typing import Any, TYPE_CHECKING

from ..api import Recipe

if TYPE_CHECKING:
    from .app import MetaAgentTUI


@dataclass
class RecipeActionIntent:
    """Action intent parsed from user LLM query in the recipes tab."""

    action: str  # "search" | "edit" | "delete" | "resume" | "generate"
    target: str | None = None
    instruction: str | None = None
    ranked_names: list[str] | None = None
    chat_file: str | None = None
    generate_query: str | None = None


def build_recipe_action_prompt(query: str, catalogue: str, chat_catalogue: str) -> str:
    """Construct LLM prompt for recipe action intent classification and ranking."""
    return (
        "You are an assistant managing AI recipes and chat history.\n"
        f"User request: {query}\n\n"
        f"Available recipes:\n{catalogue}\n\n"
        f"Exported past chat sessions:\n{chat_catalogue}\n\n"
        "Determine the user's intent:\n"
        "- If the user wants to CREATE, GENERATE, or BUILD a new assistant recipe, return JSON: "
        '{"action": "generate", "generate_query": "<extracted_assistant_requirements>"}\n'
        "- If the user wants to RESUME, RESTORE, or CONTINUE a previous chat session/topic, return JSON: "
        '{"action": "resume", "chat_file": "<matched_file_name_or_keyword>", "recipe": "<recipe_name>"}\n'
        "- If the user wants to DELETE or REMOVE a recipe, return JSON: "
        '{"action": "delete", "target": "<recipe_name>"}\n'
        "- If the user wants to EDIT, UPDATE, or MODIFY a recipe, return JSON: "
        '{"action": "edit", "target": "<recipe_name>", "instruction": "<edit details>"}\n'
        "- If the user wants to SEARCH or FIND recipes, return JSON: "
        '{"action": "search", "ranked_names": ["<matching_recipe_name_1>", "<matching_recipe_name_2>"]}\n\n'
        "Output ONLY a valid JSON object matching one of the schemas above. No markdown fences, no explanation."
    )


def build_semantic_search_prompt(query: str, catalogue: str) -> str:
    """Construct LLM prompt for standard item semantic search ranking."""
    return (
        "You are a search assistant. The user is looking for items matching their query.\n"
        f"Query: {query}\n\n"
        f"Available items:\n{catalogue}\n\n"
        "Reply with ONLY a newline-separated list of matching item names, "
        "ordered by relevance (most relevant first). "
        "Include only names that appear in the list above. No explanations."
    )


def parse_recipe_action_intent(raw_response: str) -> RecipeActionIntent:
    """Parse JSON or structured text response from LLM recipe action prompt."""
    json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            action = str(data.get("action", "search")).lower()
            if action in ("delete", "remove", "del"):
                action = "delete"
            elif action in ("edit", "update", "modify"):
                action = "edit"
            elif action in ("resume", "restore", "continue", "history", "session"):
                action = "resume"
            elif action in ("generate", "gen", "create", "new", "build", "make"):
                action = "generate"
            else:
                action = "search"

            target = data.get("target") or data.get("recipe") or data.get("name")
            target_str = str(target).strip() if target else None
            chat_file = data.get("chat_file") or data.get("file")
            chat_file_str = str(chat_file).strip() if chat_file else None
            instruction = data.get("instruction") or data.get("changes") or data.get("detail")
            instruction_str = str(instruction).strip() if instruction else None
            gen_query = (
                data.get("generate_query") or data.get("query") or data.get("prompt") or data.get("requirements")
            )
            gen_query_str = str(gen_query).strip() if gen_query else None
            ranked = data.get("ranked_names") or data.get("matches") or []
            ranked_list = [str(x).strip() for x in ranked if str(x).strip()] if isinstance(ranked, list) else []

            return RecipeActionIntent(
                action=action,
                target=target_str,
                instruction=instruction_str,
                ranked_names=ranked_list,
                chat_file=chat_file_str,
                generate_query=gen_query_str,
            )
        except Exception:
            pass

    lines = [line.lstrip("- *").strip() for line in raw_response.splitlines() if line.strip()]
    return RecipeActionIntent(action="search", ranked_names=lines)


class IntentDispatcher:
    """Handles LLM semantic search execution and intent-based screen routing."""

    def __init__(self, app: "MetaAgentTUI") -> None:
        """Initialize with app reference."""
        self._app = app

    def handle_recipe_action_intent(
        self,
        intent: RecipeActionIntent,
        query: str,
        log_fn: Any,
    ) -> bool:
        """Handle matched recipe action intent (generate, resume, delete, edit). Returns True if handled."""
        match intent.action:
            case "generate":
                return self.handle_intent_generate(intent.generate_query or query, log_fn)
            case "resume":
                return self.handle_intent_resume(intent.chat_file or intent.target or query, log_fn)
            case "delete" | "edit" if intent.target:
                return self.handle_intent_recipe_mutation(intent.action, intent.target, log_fn)
            case _:
                return False

    def handle_intent_generate(self, gen_req: str, log_fn: Any) -> bool:
        """Switch to generate tab and start recipe generation worker."""
        log_fn(
            f"Intent matched recipe generation: '{gen_req}'. "
            "Switching to Generate tab and starting background generation.",
            "INFO",
            "green",
        )
        app = self._app

        def _start_gen() -> None:
            app.clear_notifications()
            from textual.widgets import Button, RichLog, Static, TabbedContent, TextArea

            try:
                app.query_one(TabbedContent).active = "tab-generate"
                app.query_one("#gen-input", TextArea).focus()
            except Exception:
                pass

            app._gen_input_history.append(gen_req)

            status_msg = "⏳ Generating assistant recipe (you can switch tabs anytime)..."
            app.query_one("#gen-status-bar", Static).update(status_msg)
            app.query_one("#gen-submit-btn", Button).disabled = True
            app.query_one("#gen-chat-btn", Button).display = False

            from .helpers import now_datetime_str

            ts_now = now_datetime_str()
            gen_log = app.query_one("#gen-rich-log", RichLog)
            gen_log.write(f"[dim]{ts_now}[/dim] [cyan]> Generation started from Ask LLM: '{gen_req}'[/cyan]")

            app.run_worker(
                lambda: app._execute_recipe_generation(gen_req),
                thread=True,
                name=f"recipe_gen_{gen_req[:20]}",
            )

        app.call_from_thread(_start_gen)
        return True

    def handle_intent_resume(self, search_term: str, log_fn: Any) -> bool:
        """Open chat resume modal with the requested search filter."""
        log_fn(
            f"Intent matched resume chat with term: '{search_term}'. Opening session picker.",
            "INFO",
            "green",
        )
        app = self._app

        def _open_resume() -> None:
            from .screens.resume_chat import ResumeChatScreen

            app.clear_notifications()
            app.push_screen(ResumeChatScreen(app._export_dir, initial_filter=search_term))

        app.call_from_thread(_open_resume)
        return True

    def handle_intent_recipe_mutation(self, action: str, target: str, log_fn: Any) -> bool:
        """Find target recipe and open delete or edit screen."""
        app = self._app
        from .helpers import find_matching_recipe

        matched_recipe = find_matching_recipe(app._recipes, target)
        if matched_recipe is not None:
            target_rec = matched_recipe
            log_fn(
                f"Intent matched {action} target: '{target_rec.name}'. Opening screen.",
                "INFO",
                "green",
            )

            def _open_action(rec: Recipe = target_rec, act: str = action) -> None:
                app.clear_notifications()
                app._selected_recipe = rec
                if act == "delete":
                    app.action_delete_recipe()
                else:
                    app.action_edit_recipe()

            app.call_from_thread(_open_action)
            return True

        log_fn(f"{action.capitalize()} target '{target}' not found.", "WARNING", "yellow")

        def _target_not_found(tgt: str = target, act: str = action) -> None:
            app.clear_notifications()
            app.notify(
                f"⚠️ Target recipe '{tgt}' to {act} was not found",
                severity="warning",
                timeout=6.0,
            )

        app.call_from_thread(_target_not_found)
        return False
