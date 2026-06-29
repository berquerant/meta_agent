from dataclasses import asdict, dataclass

from .api import list_tools, list_agents, list_recipes, inspect_recipe, inspect_agent, inspect_tool
from .utils import json_dumps, format_obj_list_into_text, format_obj_into_text
from .gen import generate_assistant, GenRequest
from .asking import AskingRequest, AskingOpts
from typing import Any, Callable


def format_obj(x: dict[str, Any], out: str) -> str:
    """Format an object as a string."""
    match out:
        case "name":
            return str(x["name"])
        case "json":
            return json_dumps(x)
        case _:
            return format_obj_into_text("name", x)


def format_obj_list(x: list[dict[str, Any]], out: str) -> str:
    """Format objects as a string."""
    match out:
        case "name":
            return "\n".join(a["name"] for a in x)
        case "json":
            return json_dumps(x)
        case _:
            return format_obj_list_into_text("name", x)


@dataclass
class ListOpts:
    out: str


@dataclass
class InspectOpts:
    out: str
    name: str


class Cmd:
    @staticmethod
    def __list_cmd(args: ListOpts, f: Callable[[], Any]) -> None:
        print(format_obj_list([asdict(x) for x in f()], args.out))

    @staticmethod
    def list_recipes_cmd(args: ListOpts) -> None:
        Cmd.__list_cmd(args, list_recipes)

    @staticmethod
    def list_tools_cmd(args: ListOpts) -> None:
        Cmd.__list_cmd(args, list_tools)

    @staticmethod
    def list_agents_cmd(args: ListOpts) -> None:
        Cmd.__list_cmd(args, list_agents)

    @staticmethod
    def __inspect_cmd(args: InspectOpts, f: Callable[[], Any]) -> None:
        x = f()
        if x is None:
            raise Exception("Not found!")
        print(format_obj(asdict(x), args.out))

    @staticmethod
    def inspect_recipe_cmd(args: InspectOpts) -> None:
        Cmd.__inspect_cmd(args, lambda: inspect_recipe(args.name))

    @staticmethod
    def inspect_tool_cmd(args: InspectOpts) -> None:
        Cmd.__inspect_cmd(args, lambda: inspect_tool(args.name))

    @staticmethod
    def inspect_agent_cmd(args: InspectOpts) -> None:
        Cmd.__inspect_cmd(args, lambda: inspect_agent(args.name))

    @staticmethod
    def gen_cmd(args: GenRequest) -> None:
        r = generate_assistant(args)
        if not r.success:
            raise Exception(f"Failed to generate assistant! {r.message}")
        print(format_obj(asdict(r), "json"))

    @staticmethod
    def ask_cmd(args: AskingRequest, query: str) -> None:
        AskingOpts.new(args).ask(query)

    @staticmethod
    def chat_cmd(args: AskingRequest) -> None:
        AskingOpts.new(args).chat()
