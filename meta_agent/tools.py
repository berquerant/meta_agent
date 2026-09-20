from typing import Any

from dataclasses import asdict as dc_asdict
from os.path import expanduser

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

from .api import (
    list_tools,
    list_agents,
    list_recipes,
    inspect_tool,
    inspect_agent,
    inspect_recipe,
    list_engines,
    list_models,
    inspect_engine,
    inspect_model,
)
from .gen import generate_assistant, GenRequest
from .refactor import RefactorRequest, refactor_recipe
from .llm import get_llm_client
from .utils import format_obj_list_into_text, format_obj_into_text


def _execute_inspect(tool_name: str, obj: Any) -> ToolResult:
    """Format an inspected dataclass object into a ToolResult or return not found."""
    if obj is None:
        return ToolResult(tool_name=tool_name, success=False, content="Not found.")
    return ToolResult(
        tool_name=tool_name,
        content=format_obj_into_text("name", dc_asdict(obj)),
        success=True,
    )


def _execute_list(tool_name: str, items: list[Any]) -> ToolResult:
    """Format a list of dataclass objects into a ToolResult."""
    return ToolResult(
        tool_name=tool_name,
        content=format_obj_list_into_text("name", [dc_asdict(x) for x in items]),
        success=True,
    )


@ToolRegistry.register("generate_assistant")
class GenerateAssistant(BaseTool):  # type: ignore[misc]
    tool_id = "generate_assistant"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="generate_assistant",
            description="Generate a new assistant.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The requirements of a new assistant.",
                    },
                    "engine": {
                        "type": "string",
                        "description": "Engine backend",
                    },
                    "model": {
                        "type": "string",
                        "description": "Model to use",
                    },
                },
                "required": ["query"],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        query = params.get("query", "")
        if not query:
            return ToolResult(tool_name="generate_assistant", success=False, content="No query.")
        engine = params.get("engine", "ollama")
        model = params.get("model", "gemma4:12b")
        # https://github.com/open-jarvis/OpenJarvis/blob/main/src/openjarvis/recipes/loader.py#L282
        req = GenRequest(query=query, recipes_dir=expanduser("~/.openjarvis/recipes"), engine=engine, model=model)
        res = generate_assistant(req)
        if not res.success:
            return ToolResult(
                tool_name="generate_assistant",
                success=False,
                content=res.message,
            )
        return ToolResult(
            tool_name="generate_assistant",
            content=format_obj_into_text("name", dc_asdict(res)),
            success=True,
        )


@ToolRegistry.register("inspect_recipe")
class InspectRecipe(BaseTool):  # type: ignore[misc]
    tool_id = "inspect_recipe"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="inspect_recipe",
            description="Show detailed information about a specific recipe.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the recipe.",
                    },
                },
                "required": ["name"],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        return _execute_inspect("inspect_recipe", inspect_recipe(params.get("name", "")))


@ToolRegistry.register("inspect_agent")
class InspectAgent(BaseTool):  # type: ignore[misc]
    tool_id = "inspect_agent"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="inspect_agent",
            description="Show detailed information about a specific agent.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the agent.",
                    },
                },
                "required": ["name"],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        return _execute_inspect("inspect_agent", inspect_agent(params.get("name", "")))


@ToolRegistry.register("inspect_tool")
class InspectTool(BaseTool):  # type: ignore[misc]
    tool_id = "inspect_tool"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="inspect_tool",
            description="Show detailed information about a specific tool.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the tool.",
                    },
                },
                "required": ["name"],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        return _execute_inspect("inspect_tool", inspect_tool(params.get("name", "")))


@ToolRegistry.register("list_tools")
class ListTools(BaseTool):  # type: ignore[misc]
    tool_id = "list_tools"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_tools",
            description="List all registered tools with their descriptions.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        return _execute_list("list_tools", list_tools())


@ToolRegistry.register("list_agents")
class ListAgents(BaseTool):  # type: ignore[misc]
    tool_id = "list_agents"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_agents",
            description="List all registered agents with their descriptions.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        return _execute_list("list_agents", list_agents())


@ToolRegistry.register("list_recipes")
class ListRecipes(BaseTool):  # type: ignore[misc]
    tool_id = "list_recipes"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_recipes",
            description="List all registered recipes with their descriptions.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        return _execute_list("list_recipes", list_recipes())


@ToolRegistry.register("inspect_engine")
class InspectEngine(BaseTool):  # type: ignore[misc]
    tool_id = "inspect_engine"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="inspect_engine",
            description="Show detailed information about a specific LLM engine.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the engine.",
                    },
                },
                "required": ["name"],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        return _execute_inspect("inspect_engine", inspect_engine(params.get("name", "")))


@ToolRegistry.register("list_engines")
class ListEngines(BaseTool):  # type: ignore[misc]
    tool_id = "list_engines"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_engines",
            description="List all available LLM inference engines.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        return _execute_list("list_engines", list_engines())


@ToolRegistry.register("inspect_model")
class InspectModel(BaseTool):  # type: ignore[misc]
    tool_id = "inspect_model"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="inspect_model",
            description="Show detailed information about a specific model.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the model.",
                    },
                    "engine": {
                        "type": "string",
                        "description": "The engine backend (default: ollama).",
                    },
                },
                "required": ["name"],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        return _execute_inspect(
            "inspect_model",
            inspect_model(params.get("name", ""), engine=params.get("engine", "ollama")),
        )


@ToolRegistry.register("list_models")
class ListModels(BaseTool):  # type: ignore[misc]
    tool_id = "list_models"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_models",
            description="List available models for a given engine.",
            parameters={
                "type": "object",
                "properties": {
                    "engine": {
                        "type": "string",
                        "description": "Engine backend (default: ollama).",
                    },
                },
                "required": [],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        return _execute_list("list_models", list_models(engine=params.get("engine", "ollama")))


@ToolRegistry.register("refactor_recipe")
class RefactorRecipeTool(BaseTool):  # type: ignore[misc]
    tool_id = "refactor_recipe"

    def __init__(self, recipes_dir: str | None = None) -> None:
        super().__init__()
        self.recipes_dir = recipes_dir or expanduser("~/.openjarvis/recipes")

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="refactor_recipe",
            description="Evaluate and refactor an existing recipe using LLM.",
            parameters={
                "type": "object",
                "properties": {
                    "recipe": {
                        "type": "string",
                        "description": "The recipe name or file path to refactor.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional instructions or optimization goals.",
                    },
                    "target": {
                        "type": "string",
                        "description": "Refactoring target component (all, prompt, tools, agent, model).",
                    },
                    "engine": {
                        "type": "string",
                        "description": "Engine backend to use for refactoring (default: ollama).",
                    },
                    "model": {
                        "type": "string",
                        "description": "Model to use for refactoring (default: gemma4:12b).",
                    },
                },
                "required": ["recipe"],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        recipe_name = params.get("recipe", "")
        if not recipe_name:
            return ToolResult(tool_name="refactor_recipe", success=False, content="No recipe specified.")
        query = params.get("query", "")
        target = params.get("target", "all")
        engine = params.get("engine", "ollama")
        model = params.get("model", "gemma4:12b")

        req = RefactorRequest(
            recipe_name_or_path=recipe_name,
            query=query,
            target=target,
            engine=engine,
            model=model,
            recipes_dir=self.recipes_dir,
        )
        res = refactor_recipe(req)
        if not res.success:
            return ToolResult(tool_name="refactor_recipe", success=False, content=res.error_message)

        report = (
            f"Refactored: {res.recipe_name} ({res.old_version} -> {res.new_version})\n\n"
            f"Review comments:\n{res.review_comments}\n\n"
            f"Diff:\n{res.diff}\n\n"
            f"Refactored TOML:\n{res.refactored_content}"
        )
        return ToolResult(tool_name="refactor_recipe", content=report, success=True)


@ToolRegistry.register("ask_recipe")
class AskRecipeTool(BaseTool):  # type: ignore[misc]
    tool_id = "ask_recipe"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="ask_recipe",
            description="Ask a single question to an agent configured with a specific recipe.",
            parameters={
                "type": "object",
                "properties": {
                    "recipe": {
                        "type": "string",
                        "description": "The name of the recipe to use.",
                    },
                    "query": {
                        "type": "string",
                        "description": "The question to ask the agent.",
                    },
                    "engine": {
                        "type": "string",
                        "description": "Override engine backend.",
                    },
                    "model": {
                        "type": "string",
                        "description": "Override model.",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Max tokens to generate.",
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Sampling temperature.",
                    },
                },
                "required": ["recipe", "query"],
            },
            category="custom",
        )

    def execute(self, **params) -> ToolResult:  # type: ignore[no-untyped-def]
        recipe_name = params.get("recipe", "")
        query = params.get("query", "")
        if not recipe_name or not query:
            return ToolResult(tool_name="ask_recipe", success=False, content="Both recipe and query are required.")

        r = inspect_recipe(recipe_name)
        if r is None:
            return ToolResult(tool_name="ask_recipe", success=False, content=f"Recipe '{recipe_name}' not found.")

        engine = params.get("engine") or r.engine_key or "ollama"
        model = params.get("model") or r.model or "gemma4:12b"
        agent = r.agent_type or "native_react"
        tools = r.tools or []
        system_prompt = r.system_prompt or ""
        max_tokens = params.get("max_tokens")
        temperature = params.get("temperature")

        client = get_llm_client()
        try:
            full_prompt = f"{system_prompt}\n\nUser Query: {query}" if system_prompt else query
            ans = client.ask(
                full_prompt,
                agent=agent,
                tools=tools,
                engine=engine,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return ToolResult(tool_name="ask_recipe", content=ans, success=True)
        except Exception as exc:
            return ToolResult(tool_name="ask_recipe", success=False, content=f"Error executing agent: {exc}")
