from dataclasses import asdict, dataclass
from enum import Enum
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
    RefactorResult,
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


class SaveAction(Enum):
    """Action to perform for saving refactored recipe."""

    IN_PLACE = "in_place"
    AS_NEW = "as_new"
    SKIP = "skip"
    ABORT = "abort"


def _print_refactor_assessment(result: RefactorResult) -> None:
    """Print evaluation report and validation findings."""
    print(f"=== Refactor Assessment for '{result.recipe_name}' ({result.old_version} -> {result.new_version}) ===")
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


def _print_refactor_output(result: RefactorResult, out_format: str) -> None:
    """Print refactored recipe content or diff according to out format."""
    match out_format:
        case "json":
            out_dict = {
                "recipe": result.recipe_name,
                "old_version": result.old_version,
                "new_version": result.new_version,
                "review": result.review_comments,
                "diff": result.diff,
                "refactored_content": result.refactored_content,
            }
            print("\n" + json_dumps(out_dict))
        case "toml":
            print("\n[Refactored TOML Content]:")
            print(result.refactored_content)
        case _:
            print("\n[Diff Preview]:")
            print(result.diff if result.diff else "(No changes detected)")


def _resolve_save_action(args: RefactorOpts, recipe_name: str, new_version: str) -> SaveAction:
    """Determine save mode via CLI flags or interactive prompt."""
    if args.dry_run:
        return SaveAction.SKIP

    # If --yes is given, save immediately without interactive confirmation
    if args.yes:
        if args.as_new:
            return SaveAction.AS_NEW
        return SaveAction.IN_PLACE

    # Specific mode specified without --yes: ask yes/no confirmation
    if args.in_place:
        prompt_msg = f"\nSave changes for '{recipe_name}' in-place ({new_version})? [y/N]: "
        try:
            choice = input(prompt_msg).strip().lower()
        except EOFError, KeyboardInterrupt:
            return SaveAction.ABORT
        return SaveAction.IN_PLACE if choice in ("y", "yes") else SaveAction.SKIP

    if args.as_new:
        prompt_msg = f"\nSave changes for '{recipe_name}' as a new file ({new_version})? [y/N]: "
        try:
            choice = input(prompt_msg).strip().lower()
        except EOFError, KeyboardInterrupt:
            return SaveAction.ABORT
        return SaveAction.AS_NEW if choice in ("y", "yes") else SaveAction.SKIP

    # Default interactive mode when neither --in-place, --as-new, nor --yes is provided
    prompt_msg = f"\nSave changes for '{recipe_name}'? [i]n-place ({new_version}) / [n]ew file / [s]kip: "
    try:
        choice = input(prompt_msg).strip().lower()
    except EOFError, KeyboardInterrupt:
        return SaveAction.ABORT

    match choice:
        case "i" | "in-place" | "inplace":
            return SaveAction.IN_PLACE
        case "n" | "new":
            return SaveAction.AS_NEW
        case _:
            return SaveAction.SKIP


def _process_single_refactor(recipe_name_or_path: str, args: RefactorOpts) -> bool:
    """Execute refactor on a single recipe. Returns False if aborted, True otherwise."""
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
        return True

    _print_refactor_assessment(result)
    _print_refactor_output(result, args.out)

    if args.dry_run:
        print("\n(Dry-run mode: no changes saved)")
        return True

    action = _resolve_save_action(args, result.recipe_name, result.new_version)
    match action:
        case SaveAction.ABORT:
            print("\nAborted.")
            return False
        case SaveAction.SKIP:
            print(f"Skipped saving changes for '{result.recipe_name}'.")
            return True
        case SaveAction.IN_PLACE | SaveAction.AS_NEW:
            in_place = action == SaveAction.IN_PLACE
            ok, _, msg = save_refactored_recipe(
                result,
                in_place=in_place,
                recipes_dir=args.recipes_dir or None,
            )
            print(f"✅ {msg}" if ok else f"❌ Failed to save recipe: {msg}")
            return True


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
        """Run recipe refactor command across specified recipes."""
        for recipe_name_or_path in args.recipes:
            cont = _process_single_refactor(recipe_name_or_path, args)
            if not cont:
                break
