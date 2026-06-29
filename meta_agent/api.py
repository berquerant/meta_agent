import logging
from dataclasses import dataclass, field
from typing import cast

from openjarvis import Jarvis
from openjarvis.core.registry import ToolRegistry, AgentRegistry
from openjarvis.recipes.loader import discover_recipes, resolve_recipe, Recipe as JRecipe
from openjarvis.tools._stubs import ToolSpec


@dataclass
class Script:
    agent: str
    prompt: str
    tools: list[str] = field(default_factory=list)

    def run(self, engine: str, model: str, query: str = "") -> str:
        j = Jarvis(model=model, engine_key=engine)
        try:
            result = j.ask_full(
                self.prompt + query,
                agent=self.agent,
                tools=self.tools,
            )
            response = result["content"]
        except Exception as exc:
            raise Exception("Error during asking") from exc
        finally:
            j.close()
        return cast(str, response)


def inspect_tool(name: str) -> ToolSpec | None:
    """Get the tool."""
    logging.debug("inspect_tool: %s", name)
    import openjarvis.tools  # noqa: F401

    tool_cls = ToolRegistry.get(name)
    try:
        tool_instance = tool_cls() if callable(tool_cls) else tool_cls
        spec = tool_instance.spec
        return spec
    except Exception as e:
        logging.error("Failed to inspect tool: %s, %s", name, e)
        return None


@dataclass
class Tool:
    name: str
    description: str
    category: str


def list_tools() -> list[Tool]:
    """List all tools."""
    logging.debug("list tools")
    import openjarvis.tools  # noqa: F401

    result = []
    keys = sorted(ToolRegistry.keys())
    for key in keys:
        spec = inspect_tool(key)
        if spec is None:
            continue
        description = getattr(spec, "description", "")
        category = getattr(spec, "category", "")
        result.append(Tool(name=key, description=description, category=category))
    return result


@dataclass
class Agent:
    name: str
    description: str


def inspect_agent(name: str) -> Agent | None:
    """Get the agent."""
    logging.debug("inspect agent: %s", name)
    import openjarvis.agents  # noqa: F401
    from inspect import getdoc

    try:
        agent_cls = AgentRegistry.get(name)
    except Exception as e:
        logging.error("Failed to inspect agent: %s, %s", name, e)
        return None
    doc = ""
    rawdoc = getdoc(agent_cls)
    if rawdoc is not None:
        doc = rawdoc
    return Agent(name=name, description=doc)


def list_agents() -> list[Agent]:
    """List all agents."""
    logging.debug("list agents")
    import openjarvis.agents  # noqa: F401

    result = []
    keys = sorted(AgentRegistry.keys())
    for key in keys:
        x = inspect_agent(key)
        if x is None:
            continue
        result.append(x)

    return result


def inspect_recipe(name: str) -> JRecipe | None:
    """Get the recipe."""
    logging.debug("inspect recipe: %s", name)
    r = resolve_recipe(name)
    if r is None:
        logging.error("Failed to inspect recipe: %s", name)
    return r


@dataclass
class Recipe:
    name: str
    description: str
    system_prompt: str


def list_recipes() -> list[Recipe]:
    """List all recipes."""
    logging.debug("list recipes")
    recipes = discover_recipes()
    return [Recipe(name=x.name, description=x.description, system_prompt=x.system_prompt) for x in recipes]
