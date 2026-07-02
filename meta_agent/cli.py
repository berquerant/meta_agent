"""Entry point of CLI."""

import argparse
from os.path import expanduser

from .asking import AskingRequest, AskingRawRequest
from .cmd import Cmd, ListOpts, InspectOpts
from .gen import GenRequest


def get_resources(args):  # type: ignore[no-untyped-def]
    """Run get command."""
    name = ""
    if args.resource_name is not None:
        name = args.resource_name
    list_opts = ListOpts(out=args.out)
    inspect_opts = InspectOpts(out=args.out, name=name)
    match args.resource_type:
        case "recipe":
            if name:
                Cmd.inspect_recipe_cmd(inspect_opts)
            else:
                Cmd.list_recipes_cmd(list_opts)
        case "agent":
            if name:
                Cmd.inspect_agent_cmd(inspect_opts)
            else:
                Cmd.list_agents_cmd(list_opts)
        case "tool":
            if name:
                Cmd.inspect_tool_cmd(inspect_opts)
            else:
                Cmd.list_tools_cmd(list_opts)
        case _:
            raise Exception(f"Unknown resource type: {args.resource_type}")


def gen_cmd(args):  # type: ignore[no-untyped-def]
    """Run gen command."""
    r = GenRequest(engine=args.engine, model=args.model, query=args.query, recipes_dir=args.recipes)
    Cmd.gen_cmd(r)


def ask_cmd(args):  # type: ignore[no-untyped-def]
    """Run ask command."""
    r = AskingRequest(
        recipe=args.recipe,
        engine=args.engine,
        model=args.model,
        agent=args.agent,
        tools=args.tools,
        system=args.system,
        jarvis=args.jarvis,
    )
    Cmd.ask_cmd(r, args.query)


def chat_cmd(args):  # type: ignore[no-untyped-def]
    """Run chat command."""
    r = AskingRequest(
        recipe=args.recipe,
        engine=args.engine,
        model=args.model,
        agent=args.agent,
        tools=args.tools,
        system=args.system,
        jarvis=args.jarvis,
    )
    Cmd.chat_cmd(r)


def raw_cmd(args):  # type: ignore[no-untyped-def]
    """Run jarvis command."""
    Cmd.raw_cmd(AskingRawRequest(jarvis=args.jarvis, args=args.reminder))


def main() -> int:
    """Entry point of CLI."""
    p = argparse.ArgumentParser(
        prog="meta_agent",
    )
    sp = p.add_subparsers(required=True)

    get = sp.add_parser("get", help="Get resources")
    get.set_defaults(func=get_resources)
    get.add_argument("--out", "-o", choices=["json", "text", "name"], default="name", help="output format")
    get.add_argument("resource_type", choices=["recipe", "agent", "tool"])
    get.add_argument("resource_name", nargs="?")

    def add_chat_base_opts(x):  # type: ignore[no-untyped-def]
        x.add_argument("--engine", "-e", default="ollama", help="engine backend")
        x.add_argument("--model", "-m", default="gemma4:12b", help="model to use")

    gen = sp.add_parser("gen", help="Generate AI assistant recipe")
    gen.set_defaults(func=gen_cmd)
    add_chat_base_opts(gen)  # type: ignore[no-untyped-call]
    # https://github.com/open-jarvis/OpenJarvis/blob/main/src/openjarvis/recipes/loader.py#L282
    gen.add_argument("--recipes", "-r", default=expanduser("~/.openjarvis/recipes"), help="recipes directory")
    gen.add_argument("query", type=str)

    def add_chat_opts(x):  # type: ignore[no-untyped-def]
        x.add_argument("--recipe", "-r", required=True, type=str, help="recipe name")
        add_chat_base_opts(x)  # type: ignore[no-untyped-call]
        x.add_argument("--agent", "-a", type=str, help="agent type")
        x.add_argument("--tools", type=str, help="comma-separated tool names")
        x.add_argument("--system", type=str, help="custom system prompt")
        x.add_argument("--jarvis", type=str, default="jarvis", help="jarvis executable")

    chat = sp.add_parser("chat", help="Start an interactive multi-turn chat session")
    chat.set_defaults(func=chat_cmd)
    add_chat_opts(chat)  # type: ignore[no-untyped-call]

    ask = sp.add_parser("ask", help="Ask Jarvis a question")
    ask.set_defaults(func=ask_cmd)
    add_chat_opts(ask)  # type: ignore[no-untyped-call]
    ask.add_argument("query", type=str)

    raw = sp.add_parser("jarvis", help="Raw jarvis command")
    raw.set_defaults(func=raw_cmd)
    raw.add_argument("--jarvis", type=str, default="jarvis", help="jarvis executable")
    raw.add_argument("reminder", nargs=argparse.REMAINDER, help="jarvis args")

    args = p.parse_args()
    args.func(args)

    return 0


if __name__ == "__main__":
    import sys
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s")
    sys.exit(main())
