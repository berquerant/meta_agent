from dataclasses import asdict, dataclass
from typing import Any, Callable

from .api import (
    list_tools,
    list_agents,
    list_recipes,
    inspect_recipe,
    inspect_agent,
    inspect_tool,
    list_engines,
    inspect_engine,
    list_models,
    inspect_model,
)
from .asking import AskingRequest, AskingOpts, AskingRawRequest
from .gen import generate_assistant, GenRequest
from .refactor import (
    RefactorRequest,
    refactor_recipe,
    save_refactored_recipe,
)
from .utils import json_dumps, format_obj_list_into_text, format_obj_into_text


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
    engine: str = "ollama"


@dataclass
class InspectOpts:
    out: str
    name: str
    engine: str = "ollama"


@dataclass
class RefactorOpts:
    recipes: list[str]
    query: str = ""
    engine: str = "ollama"
    model: str = "gemma4:12b"
    recipes_dir: str = ""
    target: str = "all"
    in_place: bool = False
    as_new: bool = False
    yes: bool = False
    dry_run: bool = False
    out: str = "diff"


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
    def list_engines_cmd(args: ListOpts) -> None:
        Cmd.__list_cmd(args, lambda: list_engines(default_engine=args.engine))

    @staticmethod
    def list_models_cmd(args: ListOpts) -> None:
        Cmd.__list_cmd(args, lambda: list_models(engine=args.engine))

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
    def inspect_engine_cmd(args: InspectOpts) -> None:
        Cmd.__inspect_cmd(args, lambda: inspect_engine(args.name, default_engine=args.engine))

    @staticmethod
    def inspect_model_cmd(args: InspectOpts) -> None:
        Cmd.__inspect_cmd(args, lambda: inspect_model(args.name, engine=args.engine))

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

    @staticmethod
    def raw_cmd(args: AskingRawRequest) -> None:
        args.run()

    @staticmethod
    def refactor_cmd(args: RefactorOpts) -> None:
        """Run recipe refactor command."""
        for recipe_name_or_path in args.recipes:
            req = RefactorRequest(
                recipe_name_or_path=recipe_name_or_path,
                query=args.query,
                engine=args.engine,
                model=args.model,
                recipes_dir=args.recipes_dir,
                target=args.target,
            )
            result = refactor_recipe(req)
            if not result.success:
                print(f"❌ Failed to refactor {recipe_name_or_path}: {result.error_message}")
                continue

            print(
                f"=== Refactor Assessment for '{result.recipe_name}' ({result.old_version} -> {result.new_version}) ==="
            )
            if result.review_comments:
                print("\n[Evaluation & Changes Summary]:")
                print(result.review_comments)

            if result.validation_before.has_issues:
                print("\n[Issues Detected Before Refactor]:")
                for w in result.validation_before.warnings:
                    print(f"  - {w}")

            if result.validation_after.has_issues:
                print("\n[Remaining Issues After Refactor]:")
                for w in result.validation_after.warnings:
                    print(f"  - {w}")

            if args.out == "json":
                out_dict = {
                    "recipe": result.recipe_name,
                    "old_version": result.old_version,
                    "new_version": result.new_version,
                    "review": result.review_comments,
                    "diff": result.diff,
                    "refactored_content": result.refactored_content,
                }
                print("\n" + json_dumps(out_dict))
            elif args.out == "toml":
                print("\n[Refactored TOML Content]:")
                print(result.refactored_content)
            else:
                print("\n[Diff Preview]:")
                if result.diff:
                    print(result.diff)
                else:
                    print("(No changes detected)")

            if args.dry_run:
                print("\n(Dry-run mode: no changes saved)")
                continue

            save_mode_inplace = args.in_place
            if not args.in_place and not args.as_new and not args.yes:
                # Ask user confirmation interactively
                prompt_msg = (
                    f"\nSave changes for '{result.recipe_name}'? "
                    f"[i]n-place ({result.new_version}) / [n]ew file / [s]kip: "
                )
                try:
                    choice = input(prompt_msg).strip().lower()
                except EOFError, KeyboardInterrupt:
                    print("\nAborted.")
                    break

                if choice in ("i", "in-place", "inplace", "y", "yes"):
                    save_mode_inplace = True
                elif choice in ("n", "new"):
                    save_mode_inplace = False
                else:
                    print(f"Skipped saving changes for '{result.recipe_name}'.")
                    continue
            elif args.as_new:
                save_mode_inplace = False
            elif args.in_place:
                save_mode_inplace = True
            elif args.yes:
                # Default for --yes without --in-place or --as-new is in-place
                save_mode_inplace = True

            ok, path, msg = save_refactored_recipe(
                result,
                in_place=save_mode_inplace,
                recipes_dir=args.recipes_dir or None,
            )
            if ok:
                print(f"✅ {msg}")
            else:
                print(f"❌ Failed to save recipe: {msg}")
