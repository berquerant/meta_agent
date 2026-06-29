from dataclasses import asdict as dc_asdict
from os.path import expanduser

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

from .api import list_tools, list_agents, list_recipes, inspect_tool, inspect_agent, inspect_recipe
from .gen import generate_assistant, GenRequest
from .utils import format_obj_list_into_text, format_obj_into_text


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
        name = params.get("name", "")
        recipe = inspect_recipe(name)
        if recipe is None:
            return ToolResult(tool_name="inspect_recipe", success=False, content="Not found.")
        return ToolResult(
            tool_name="inspect_recipe",
            content=format_obj_into_text("name", dc_asdict(recipe)),
            success=True,
        )


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
        name = params.get("name", "")
        agent = inspect_agent(name)
        if agent is None:
            return ToolResult(tool_name="inspect_agent", success=False, content="Not found.")
        return ToolResult(
            tool_name="inspect_agent",
            content=format_obj_into_text("name", dc_asdict(agent)),
            success=True,
        )


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
        name = params.get("name", "")
        tool = inspect_tool(name)
        if tool is None:
            return ToolResult(tool_name="inspect_tool", success=False, content="Not found.")
        return ToolResult(
            tool_name="inspect_tool",
            content=format_obj_into_text("name", dc_asdict(tool)),
            success=True,
        )


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
        return ToolResult(
            tool_name="list_tools",
            content=format_obj_list_into_text("name", [dc_asdict(x) for x in list_tools()]),
            success=True,
        )


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
        return ToolResult(
            tool_name="list_agents",
            content=format_obj_list_into_text("name", [dc_asdict(x) for x in list_agents()]),
            success=True,
        )


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
        return ToolResult(
            tool_name="list_recipes",
            content=format_obj_list_into_text("name", [dc_asdict(x) for x in list_recipes()]),
            success=True,
        )
