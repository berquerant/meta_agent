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
    engine_key: str = ""
    model: str = ""
    agent_type: str = ""
    tools: list[str] = field(default_factory=list)
    version: str = ""


def list_recipes() -> list[Recipe]:
    """List all recipes."""
    logging.debug("list recipes")
    recipes = discover_recipes()
    return [
        Recipe(
            name=x.name,
            description=x.description or "",
            system_prompt=x.system_prompt or "",
            engine_key=x.engine_key or "",
            model=x.model or "",
            agent_type=x.agent_type or "",
            tools=list(x.tools) if x.tools else [],
            version=x.version or "",
        )
        for x in recipes
    ]


def find_recipe_files(recipe_name: str, recipes_dir: str | None = None) -> list[str]:
    """
    Search for TOML recipe files in the specified directory matching recipe_name.

    Matches either the recipe name declared in the TOML file or the filename stem.
    """
    from pathlib import Path
    import tomllib

    target_dir = Path(recipes_dir) if recipes_dir else Path.home() / ".openjarvis" / "recipes"
    if not target_dir.is_dir():
        return []

    matched: list[str] = []
    for toml_path in sorted(target_dir.glob("*.toml")):
        # Check stem match
        if toml_path.stem == recipe_name:
            matched.append(str(toml_path))
            continue

        # Check name in TOML content
        try:
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
            r_name = data.get("recipe", {}).get("name")
            if r_name == recipe_name:
                matched.append(str(toml_path))
        except Exception:
            continue

    return matched


def delete_recipe_file(path: str) -> bool:
    """Delete a recipe file at the given path."""
    from pathlib import Path

    p = Path(path)
    if p.is_file():
        try:
            p.unlink()
            return True
        except Exception as e:
            logging.error("Failed to delete recipe file %s: %s", path, e)
            return False
    return False
