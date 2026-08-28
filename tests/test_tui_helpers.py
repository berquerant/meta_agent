from dataclasses import dataclass
from unittest import TestCase

from meta_agent.api import Recipe
from meta_agent.tui.helpers import (
    build_chat_command_parts,
    build_chat_prompt,
    build_recipe_action_prompt,
    build_semantic_search_prompt,
    filter_items,
    format_command_preview,
    parse_exported_chat_file,
    parse_recipe_action_intent,
    sort_items,
)


@dataclass
class DummyItem:
    name: str


class TestTUIHelpers(TestCase):
    def test_sort_items(self) -> None:
        items = [DummyItem("banana"), DummyItem("Apple"), DummyItem("cherry")]
        asc = sort_items(items, "alpha_asc")
        self.assertEqual([x.name for x in asc], ["Apple", "banana", "cherry"])

        desc = sort_items(items, "alpha_desc")
        self.assertEqual([x.name for x in desc], ["cherry", "banana", "Apple"])

    def test_filter_items(self) -> None:
        items = [DummyItem("alpha_bot"), DummyItem("beta_bot"), DummyItem("alpha_tool")]
        filtered = filter_items(items, "alpha")
        self.assertEqual([x.name for x in filtered], ["alpha_bot", "alpha_tool"])

        empty_filtered = filter_items(items, "")
        self.assertEqual(len(empty_filtered), 3)

    def test_build_chat_command_parts(self) -> None:
        rec = Recipe(
            name="test_recipe",
            description="Test recipe description",
            engine_key="ollama",
            model="llama3",
            agent_type="native_react",
            tools=["file_read", "bash"],
            system_prompt="You are helpful.",
        )

        # Exact match with recipe defaults -> no override flags
        parts = build_chat_command_parts(
            recipe=rec,
            engine="ollama",
            model="llama3",
            agent="native_react",
            tools="file_read, bash",
            system="You are helpful.",
            default_engine="ollama",
            default_model="llama3",
        )
        self.assertEqual(parts, ["meta_agent", "chat", "--recipe", "test_recipe"])

        # Override engine, model, and system prompt
        parts_overridden = build_chat_command_parts(
            recipe=rec,
            engine="cloud",
            model="gemini-1.5-pro",
            agent="orchestrator",
            tools="file_read",
            system="Custom system prompt",
            default_engine="ollama",
            default_model="llama3",
        )
        self.assertIn("--engine", parts_overridden)
        self.assertIn("cloud", parts_overridden)
        self.assertIn("--model", parts_overridden)
        self.assertIn("gemini-1.5-pro", parts_overridden)
        self.assertIn("--agent", parts_overridden)
        self.assertIn("orchestrator", parts_overridden)
        self.assertIn("--tools", parts_overridden)
        self.assertIn("file_read", parts_overridden)
        self.assertIn("--system", parts_overridden)

    def test_format_command_preview(self) -> None:
        parts = ["meta_agent", "chat", "--recipe", "my_bot", "--engine", "cloud", "--model", "gpt-4o"]
        formatted = format_command_preview(parts)
        self.assertIn("meta_agent chat --recipe my_bot \\\n", formatted)
        self.assertIn("--engine cloud", formatted)
        self.assertIn("--model gpt-4o", formatted)

    def test_build_chat_prompt(self) -> None:
        # First turn with system prompt
        p1 = build_chat_prompt("You are a bot.", [], "Hello")
        self.assertIn("# System Prompt\nYou are a bot.", p1)
        self.assertIn("# User Query\nHello", p1)

        # Multi-turn prompt
        history = [
            ("User", "Hi", "2026-01-01 10:00:00"),
            ("Assistant", "Hello there!", "2026-01-01 10:00:05"),
            ("User", "What can you do?", "2026-01-01 10:01:00"),
        ]
        p2 = build_chat_prompt("You are a bot.", history, "What can you do?")
        self.assertIn("# Conversation History", p2)
        self.assertIn("<User>\nHi\n</User>", p2)
        self.assertIn("<Assistant>\nHello there!\n</Assistant>", p2)
        self.assertIn("# Current User Query\nWhat can you do?", p2)

    def test_prompt_builders(self) -> None:
        rec_prompt = build_recipe_action_prompt(
            query="find recipe",
            catalogue="- bot: A bot",
            chat_catalogue="- File 'chat_1.md': Test session",
        )
        self.assertIn("User request: find recipe", rec_prompt)
        self.assertIn("- bot: A bot", rec_prompt)
        self.assertIn("chat_1.md", rec_prompt)
        self.assertIn('"action": "generate"', rec_prompt)

        search_prompt = build_semantic_search_prompt(
            query="find tool",
            catalogue="- tool1: Description",
        )
        self.assertIn("Query: find tool", search_prompt)
        self.assertIn("- tool1: Description", search_prompt)

    def test_parse_recipe_action_intent(self) -> None:
        # Generate intent
        raw_gen = '{"action": "generate", "query": "Build a python pytest bot"}'
        intent_gen = parse_recipe_action_intent(raw_gen)
        self.assertEqual(intent_gen.action, "generate")
        self.assertEqual(intent_gen.generate_query, "Build a python pytest bot")

        # Resume intent
        raw_resume = '{"action": "resume", "chat_file": "chat_pytest_20260101.md", "recipe": "pytest_bot"}'
        intent_resume = parse_recipe_action_intent(raw_resume)
        self.assertEqual(intent_resume.action, "resume")
        self.assertEqual(intent_resume.chat_file, "chat_pytest_20260101.md")

        # Delete intent
        raw_del = '{"action": "delete", "target": "old_bot"}'
        intent_del = parse_recipe_action_intent(raw_del)
        self.assertEqual(intent_del.action, "delete")
        self.assertEqual(intent_del.target, "old_bot")

        # Edit intent
        raw_edit = '{"action": "edit", "target": "custom_bot", "instruction": "change tools"}'
        intent_edit = parse_recipe_action_intent(raw_edit)
        self.assertEqual(intent_edit.action, "edit")
        self.assertEqual(intent_edit.target, "custom_bot")

        # Search fallback intent
        raw_search = "bot_alpha\nbot_beta\nbot_gamma"
        intent_search = parse_recipe_action_intent(raw_search)
        self.assertEqual(intent_search.action, "search")
        self.assertEqual(intent_search.ranked_names, ["bot_alpha", "bot_beta", "bot_gamma"])

    def test_parse_exported_chat_file(self) -> None:
        content = (
            "# Chat Session: my_test_recipe\n"
            "- **Engine**: ollama\n"
            "- **Model**: gemma4:12b\n"
            "- **Agent**: orchestrator\n"
            "- **Tools**: file_read, bash\n"
            "- **System**: You are a helpful test assistant.\n"
            "---\n\n"
            "## 👤 User [2026-08-28 10:00:00]\n"
            "Can you run tests?\n\n"
            "## 🤖 Assistant [2026-08-28 10:00:05]\n"
            "Yes, I can execute pytest for you.\n"
        )
        parsed = parse_exported_chat_file(content)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.recipe_name, "my_test_recipe")
        self.assertEqual(parsed.engine, "ollama")
        self.assertEqual(parsed.model, "gemma4:12b")
        self.assertEqual(parsed.agent, "orchestrator")
        self.assertEqual(parsed.tools, "file_read, bash")
        self.assertEqual(parsed.system, "You are a helpful test assistant.")
        self.assertEqual(len(parsed.history), 2)
        self.assertEqual(parsed.history[0], ("User", "Can you run tests?", "2026-08-28 10:00:00"))
        self.assertEqual(parsed.history[1], ("Assistant", "Yes, I can execute pytest for you.", "2026-08-28 10:00:05"))
