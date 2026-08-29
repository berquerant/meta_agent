from collections.abc import Iterator
from pathlib import Path
import tempfile

import pytest
from textual.widgets import Button, TabbedContent, TextArea

from meta_agent.asking import AskingOpts
from meta_agent.llm import LLMClient, reset_llm_client, set_llm_client
from meta_agent.tui.app import MetaAgentTUI
from meta_agent.tui.screens.chat import ChatScreen
from meta_agent.tui.screens.chat_options import ChatOptionsScreen
from meta_agent.tui.widgets import Markdown


class MockLLMClient(LLMClient):
    """Configurable mock LLM client for E2E testing."""

    def __init__(
        self,
        default_response: str = "Mocked LLM Response",
        stream_chunks: list[str] | None = None,
        custom_responses: dict[str, str] | None = None,
    ) -> None:
        self.default_response = default_response
        self.stream_chunks = stream_chunks or ["Chunk 1 ", "Chunk 2 ", "Done."]
        self.custom_responses = custom_responses or {}
        self.ask_calls: list[dict[str, object]] = []

    def ask(
        self,
        prompt: str,
        *,
        agent: str | None = None,
        tools: list[str] | None = None,
        engine: str = "ollama",
        model: str = "llama3",
    ) -> str:
        self.ask_calls.append(
            {
                "prompt": prompt,
                "agent": agent,
                "tools": tools,
                "engine": engine,
                "model": model,
            }
        )
        for key, resp in self.custom_responses.items():
            if key in prompt:
                return resp
        return self.default_response

    def ask_stream(
        self,
        prompt: str,
        *,
        agent: str | None = None,
        tools: list[str] | None = None,
        engine: str = "ollama",
        model: str = "llama3",
    ) -> Iterator[str]:
        self.ask_calls.append(
            {
                "prompt": prompt,
                "agent": agent,
                "tools": tools,
                "engine": engine,
                "model": model,
                "stream": True,
            }
        )
        for chunk in self.stream_chunks:
            yield chunk

    def list_engines(self, default_engine: str = "ollama") -> list[str]:
        return ["ollama", "cloud", "vllm"]

    def list_models(self, default_engine: str = "ollama") -> list[str]:
        return ["llama3", "gpt-4o", "gemini-1.5-pro"]


@pytest.fixture(autouse=True)
def _cleanup_llm_client() -> Iterator[None]:
    """Ensure mock LLM client is reset after each test."""
    yield
    reset_llm_client()


@pytest.mark.anyio
async def test_e2e_tui_generate_recipe_workflow() -> None:
    """E2E Test: Generating a new recipe via LLM in GenerateTab, inspecting preview, and launching chat."""
    generated_toml = (
        '[recipe]\nname = "pytest_generator"\ndescription = "A test generator bot."\n'
        'engine = "ollama"\nmodel = "llama3"\nagent = "native_react"\ntools = ["file_read"]\n'
        'system = "You are a test expert."\n'
    )
    mock_client = MockLLMClient(default_response=generated_toml)
    set_llm_client(mock_client)

    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            # Switch to GenerateTab
            app.action_open_generate()
            await pilot.pause()

            # Enter generation prompt in TextArea and submit
            gen_input = app.query_one("#gen-input", TextArea)
            gen_input.text = "Create a pytest assistant"
            await pilot.click("#gen-submit-btn")

            # Wait for background thread worker to finish and button to appear
            chat_btn = app.query_one("#gen-chat-btn", Button)
            for _ in range(50):
                await pilot.pause()
                if chat_btn.display:
                    break

            # Verify LLM was called
            assert len(mock_client.ask_calls) >= 1

            # Verify recipe file was saved on disk
            saved_files = list(Path(tmpdir).glob("meta_agent__pytest_generator_*.toml"))
            assert len(saved_files) == 1
            assert "pytest_generator" in saved_files[0].read_text(encoding="utf-8")

            # Verify preview in Markdown widget
            preview_md = app.query_one("#gen-markdown", Markdown)
            assert preview_md is not None

            # Verify 'Chat with Recipe' button is visible and click it
            for _ in range(50):
                await pilot.pause()
                if any(r.name == "pytest_generator" for r in app._recipes):
                    break
            assert chat_btn.display is True
            app.on_gen_chat_btn()
            await pilot.pause()

            # Should open ChatOptionsScreen for the generated recipe
            assert isinstance(app.screen, ChatOptionsScreen)
            assert app.screen._recipe.name == "pytest_generator"


@pytest.mark.anyio
async def test_e2e_tui_chat_streaming_workflow() -> None:
    """E2E Test: Streaming response in ChatScreen direct engine mode."""
    tokens = ["Hello! ", "I am ", "your AI ", "assistant."]
    mock_client = MockLLMClient(stream_chunks=tokens)
    set_llm_client(mock_client)

    opts = AskingOpts(engine="ollama", model="llama3", agent=None, tools="", system="You are helpful.")
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            chat_screen = ChatScreen("stream_bot", opts, export_dir=tmpdir)
            app.push_screen(chat_screen)
            await pilot.pause()

            # Submit user query via send button or ctrl+j
            chat_input = chat_screen.query_one("#chat-input", TextArea)
            chat_input.text = "Introduce yourself"
            chat_screen.query_one("#chat-send-btn", Button).press()

            # Wait for streaming worker to complete
            for _ in range(50):
                await pilot.pause()
                if len(chat_screen._history) >= 2:
                    break

            # History should contain User message and Assistant assembled response
            assert len(chat_screen._history) == 2
            assert chat_screen._history[0][0] == "User"
            assert chat_screen._history[0][1] == "Introduce yourself"
            assert chat_screen._history[1][0] == "Assistant"
            assert chat_screen._history[1][1] == "Hello! I am your AI assistant."

            # Verify markdown widget updated
            chat_md = chat_screen.query_one("#chat-markdown", Markdown)
            assert chat_md is not None


@pytest.mark.anyio
async def test_e2e_tui_chat_agent_execution_workflow() -> None:
    """E2E Test: Agent mode full response in ChatScreen."""
    mock_client = MockLLMClient(default_response="All tests passed successfully.")
    set_llm_client(mock_client)

    opts = AskingOpts(
        engine="ollama", model="llama3", agent="orchestrator", tools="file_read,bash", system="You are a test runner."
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            chat_screen = ChatScreen("agent_bot", opts, export_dir=tmpdir)
            app.push_screen(chat_screen)
            await pilot.pause()

            # Submit user query
            chat_input = chat_screen.query_one("#chat-input", TextArea)
            chat_input.text = "Run test suite"
            chat_screen.query_one("#chat-send-btn", Button).press()

            # Wait for agent worker to complete
            for _ in range(50):
                await pilot.pause()
                if len(chat_screen._history) >= 2:
                    break

            assert len(chat_screen._history) == 2
            assert chat_screen._history[0][1] == "Run test suite"
            assert chat_screen._history[1][1] == "All tests passed successfully."


@pytest.mark.anyio
async def test_e2e_tui_ask_llm_action_workflow() -> None:
    """E2E Test: Ask LLM natural language intent parsing and automatic tab routing."""
    intent_json = '{"action": "generate", "generate_query": "Build a rust docker assistant"}'
    recipe_toml = (
        '[recipe]\nname = "docker_bot"\ndescription = "Docker bot"\nengine = "ollama"\n'
        'model = "llama3"\nagent = "native_react"\ntools = []\nsystem = "prompt"\n'
    )
    mock_client = MockLLMClient(
        default_response=intent_json,
        custom_responses={
            "あなたの役割": recipe_toml,
            "managing AI recipes": intent_json,
            "User request": intent_json,
        },
    )
    set_llm_client(mock_client)

    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Type natural language search in recipes tab
            search_ta = app.query_one("#recipes-search", TextArea)
            search_ta.text = "I need a rust docker helper"
            await pilot.pause()

            # Trigger LLM search
            app._trigger_llm_search("recipes")

            # Wait for LLM search worker to process and route tab
            tabs = app.query_one(TabbedContent)
            for _ in range(50):
                await pilot.pause()
                if tabs.active == "tab-generate":
                    break

            # The intent was 'generate' -> app should route to GenerateTab
            assert tabs.active == "tab-generate"
