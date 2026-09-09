"""Recipe refactoring and evaluation module."""

from dataclasses import dataclass, field
import difflib
import logging
from pathlib import Path
import re
import tomllib
from typing import Any

from .api import (
    find_recipe_files,
    list_agents,
    list_engines,
    list_models,
    list_tools,
    Script,
)
from .utils import now_str


@dataclass
class SemVer:
    """Semantic version representation (major.minor.patch)."""

    major: int = 0
    minor: int = 1
    patch: int = 0

    @classmethod
    def parse(cls, version_str: str) -> "SemVer":
        """Parse version string into SemVer."""
        m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", version_str.strip())
        if not m:
            return cls(0, 1, 0)
        major = int(m.group(1))
        minor = int(m.group(2))
        patch = int(m.group(3)) if m.group(3) is not None else 0
        return cls(major, minor, patch)

    def bump_patch(self) -> "SemVer":
        """Bump patch version."""
        return SemVer(self.major, self.minor, self.patch + 1)

    def bump_minor(self) -> "SemVer":
        """Bump minor version."""
        return SemVer(self.major, self.minor + 1, 0)

    def __str__(self) -> str:
        """Return formatted semver string."""
        return f"{self.major}.{self.minor}.{self.patch}"

    def to_suffix(self) -> str:
        """Return filename-safe suffix (e.g. v0-2-0)."""
        return f"v{self.major}-{self.minor}-{self.patch}"


@dataclass
class ValidationReport:
    """Validation report checking if recipe components exist."""

    invalid_tools: list[str] = field(default_factory=list)
    invalid_agent: str | None = None
    invalid_engine: str | None = None
    invalid_model: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        """Return True if any component issue is found."""
        return bool(
            self.invalid_tools or self.invalid_agent or self.invalid_engine or self.invalid_model or self.warnings
        )


def validate_recipe_components(
    recipe_toml_dict: dict[str, Any],
    default_engine: str = "ollama",
) -> ValidationReport:
    """Validate recipe tools, agent, engine, and model against registered components."""
    report = ValidationReport()

    # 1. Validate tools
    available_tools = {t.name for t in list_tools()}
    tools = recipe_toml_dict.get("agent", {}).get("tools", [])
    if isinstance(tools, list):
        for tool in tools:
            if tool and tool not in available_tools:
                report.invalid_tools.append(str(tool))
                report.warnings.append(f"Tool '{tool}' is not registered in ToolRegistry.")

    # 2. Validate agent
    available_agents = {a.name for a in list_agents()}
    agent = recipe_toml_dict.get("agent", {}).get("type")
    if agent and agent not in available_agents:
        report.invalid_agent = str(agent)
        report.warnings.append(f"Agent '{agent}' is not registered in AgentRegistry.")

    # 3. Validate engine & model
    engine_key = recipe_toml_dict.get("engine", {}).get("key") or default_engine
    available_engines = {e.name for e in list_engines(default_engine=engine_key)}
    if engine_key and available_engines and engine_key not in available_engines:
        report.invalid_engine = str(engine_key)
        report.warnings.append(f"Engine '{engine_key}' is not recognized.")

    model = recipe_toml_dict.get("intelligence", {}).get("model")
    if model:
        available_models = {m.name for m in list_models(engine=engine_key)}
        if available_models and model not in available_models:
            report.invalid_model = str(model)
            report.warnings.append(f"Model '{model}' was not found for engine '{engine_key}'.")

    return report


@dataclass
class RefactorRequest:
    """Request parameters for recipe refactoring."""

    recipe_name_or_path: str
    query: str = ""
    engine: str = "ollama"
    model: str = "gemma4:12b"
    recipes_dir: str = ""
    target: str = "all"  # "all" | "prompt" | "tools" | "agent" | "model"


@dataclass
class RefactorResult:
    """Result of refactoring a single recipe."""

    recipe_name: str
    original_path: str
    original_content: str
    refactored_content: str
    diff: str
    review_comments: str
    old_version: str
    new_version: str
    success: bool
    error_message: str = ""
    validation_before: ValidationReport = field(default_factory=ValidationReport)
    validation_after: ValidationReport = field(default_factory=ValidationReport)


def build_refactor_prompt(
    recipe_content: str,
    query: str,
    target: str,
    validation_report: ValidationReport,
) -> str:
    """Construct LLM prompt for evaluating and refactoring a recipe in English."""
    avail_tools = [f"- {t.name}: {t.description}" for t in list_tools()]
    avail_agents = [f"- {a.name}: {a.description}" for a in list_agents()]

    validation_warning_text = ""
    if validation_report.has_issues:
        validation_warning_text = "\n# Issues Detected in Pre-Validation:\n" + "\n".join(
            f"- {w}" for w in validation_report.warnings
        )

    user_instruction = (
        f"Specific user modification request:\n{query}"
        if query.strip()
        else "No specific user request provided. Evaluate and refactor autonomously following best practices."
    )

    tools_joined = "\n".join(avail_tools)
    agents_joined = "\n".join(avail_agents)

    return f"""# Your Role
You are an expert meta-engineer specializing in evaluating, optimizing, and refactoring AI assistant recipe TOML specifications.
Analyze the given recipe TOML, evaluate its effectiveness, and output an improved, consistent, high-quality TOML recipe.

# Existing Recipe TOML:
```toml
{recipe_content}
```
{validation_warning_text}

# Refactoring Focus (Target):
{target} (Focus on "all" for general optimization, or specifically on "prompt", "tools", "agent", or "model" as specified)

# User Request:
{user_instruction}

# Available Components (Do NOT fabricate non-existent tools or agents):
## Available Tools:
{tools_joined}

## Available Agents:
{agents_joined}

# Evaluation & Refactoring Guidelines:
1. **Component Validity & Consistency**:
   - `agent.type` and `agent.tools` MUST only use names from the available list above. Replace or remove any invalid/hallucinated tools or agents.
2. **Tool Selection**:
   - Ensure necessary tools for the assistant's purpose are present, and remove unnecessary or redundant tools.
3. **Prompt Quality**:
   - Ensure `system_prompt` clearly specifies role, constraints, tool usage guidelines, and output format.
4. **Versioning (SemVer)**:
   - When modifying the recipe, bump `[recipe].version` appropriately (patch for minor fixes, minor for functional or component changes).

# Output Format:
Provide your response strictly in the following format:
First, write concise evaluation and change bullet points.
Then, add the separator line `---TOML---` on a new line, followed immediately by the complete refactored TOML content (do not wrap in markdown code blocks).

[Evaluation and Refactoring Summary in bullet points]

---TOML---
[recipe]
name = "..."
description = "..."
version = "..."

[engine]
key = "..."

[intelligence]
model = "..."

[agent]
type = "..."
tools = [
    "...",
]
system_prompt = \"\"\"...\"\"\"
"""  # noqa: E501


def generate_diff(original: str, new: str, fromfile: str = "original", tofile: str = "refactored") -> str:
    """Generate a unified diff between original and new TOML."""
    orig_lines = original.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, new_lines, fromfile=fromfile, tofile=tofile)
    return "".join(diff)


def extract_toml_and_review(raw_output: str) -> tuple[str, str]:
    """Separate review comments and TOML string from LLM output."""
    if "---TOML---" in raw_output:
        parts = raw_output.split("---TOML---", 1)
        review = parts[0].strip()
        toml_part = parts[1].strip()
    else:
        match = re.search(r"(\[recipe\].*)", raw_output, re.DOTALL)
        if match:
            idx = match.start(1)
            review = raw_output[:idx].strip()
            toml_part = raw_output[idx:].strip()
        else:
            review = ""
            toml_part = raw_output.strip()

    if toml_part.startswith("```"):
        toml_part = re.sub(r"^```(?:toml)?\n?", "", toml_part)
        toml_part = re.sub(r"\n?```$", "", toml_part)
    toml_part = toml_part.strip()
    return review, toml_part


def refactor_recipe(req: RefactorRequest) -> RefactorResult:
    """Evaluate and refactor a recipe using LLM."""
    logging.debug("refactor_recipe start: %s", req.recipe_name_or_path)

    orig_path_obj: Path | None = None
    candidate_path = Path(req.recipe_name_or_path)
    if candidate_path.is_file():
        orig_path_obj = candidate_path
    else:
        files = find_recipe_files(req.recipe_name_or_path, req.recipes_dir)
        if files:
            orig_path_obj = Path(files[0])

    if not orig_path_obj or not orig_path_obj.exists():
        return RefactorResult(
            recipe_name=req.recipe_name_or_path,
            original_path="",
            original_content="",
            refactored_content="",
            diff="",
            review_comments="",
            old_version="0.1.0",
            new_version="0.1.0",
            success=False,
            error_message=f"Recipe file not found for '{req.recipe_name_or_path}'",
        )

    orig_content = orig_path_obj.read_text(encoding="utf-8")
    try:
        orig_dict = tomllib.loads(orig_content)
    except Exception as e:
        return RefactorResult(
            recipe_name=req.recipe_name_or_path,
            original_path=str(orig_path_obj),
            original_content=orig_content,
            refactored_content="",
            diff="",
            review_comments="",
            old_version="0.1.0",
            new_version="0.1.0",
            success=False,
            error_message=f"Original recipe contains invalid TOML: {e}",
        )

    recipe_name = str(orig_dict.get("recipe", {}).get("name", orig_path_obj.stem))
    old_version_str = str(orig_dict.get("recipe", {}).get("version", "0.1.0"))
    old_semver = SemVer.parse(old_version_str)

    val_before = validate_recipe_components(orig_dict, default_engine=req.engine)

    prompt = build_refactor_prompt(
        recipe_content=orig_content,
        query=req.query,
        target=req.target,
        validation_report=val_before,
    )

    s = Script(
        tools=["think", "list_tools", "list_agents"],
        agent="orchestrator",
        prompt=prompt,
    )

    try:
        raw_resp = s.run(engine=req.engine, model=req.model)
    except Exception as e:
        return RefactorResult(
            recipe_name=recipe_name,
            original_path=str(orig_path_obj),
            original_content=orig_content,
            refactored_content="",
            diff="",
            review_comments="",
            old_version=str(old_semver),
            new_version=str(old_semver),
            success=False,
            error_message=f"LLM execution failed: {e}",
            validation_before=val_before,
        )

    review_comments, new_toml = extract_toml_and_review(raw_resp)

    try:
        new_dict = tomllib.loads(new_toml)
    except Exception as e:
        return RefactorResult(
            recipe_name=recipe_name,
            original_path=str(orig_path_obj),
            original_content=orig_content,
            refactored_content=new_toml,
            diff="",
            review_comments=review_comments,
            old_version=str(old_semver),
            new_version=str(old_semver),
            success=False,
            error_message=f"Refactored TOML is invalid: {e}",
            validation_before=val_before,
        )

    new_version_str = str(new_dict.get("recipe", {}).get("version", ""))
    new_semver = SemVer.parse(new_version_str) if new_version_str else old_semver.bump_minor()
    if str(new_semver) == str(old_semver):
        new_semver = old_semver.bump_minor()

    if new_dict.get("recipe", {}).get("version") != str(new_semver):
        if 'version = "' in new_toml:
            new_toml = re.sub(r'version\s*=\s*"[^"]*"', f'version = "{new_semver}"', new_toml, count=1)
        else:
            new_toml = new_toml.replace("[recipe]", f'[recipe]\nversion = "{new_semver}"', 1)

    val_after = validate_recipe_components(new_dict, default_engine=req.engine)
    diff = generate_diff(orig_content, new_toml, fromfile=str(orig_path_obj.name), tofile="refactored")

    return RefactorResult(
        recipe_name=recipe_name,
        original_path=str(orig_path_obj),
        original_content=orig_content,
        refactored_content=new_toml,
        diff=diff,
        review_comments=review_comments,
        old_version=str(old_semver),
        new_version=str(new_semver),
        success=True,
        validation_before=val_before,
        validation_after=val_after,
    )


def save_refactored_recipe(
    result: RefactorResult,
    in_place: bool = False,
    recipes_dir: str | None = None,
) -> tuple[bool, str, str]:
    """
    Save refactored recipe either in-place or as a new file with SemVer.

    Returns (success, path, message).
    """
    if not result.success:
        return False, "", result.error_message

    if in_place:
        target_path = Path(result.original_path)
        try:
            target_path.write_text(result.refactored_content, encoding="utf-8")
            return True, str(target_path), f"Updated {target_path.name} in-place (version: {result.new_version})"
        except Exception as e:
            return False, str(target_path), f"Failed to overwrite {target_path}: {e}"

    target_dir = Path(recipes_dir) if recipes_dir else Path(result.original_path).parent
    target_dir.mkdir(parents=True, exist_ok=True)

    semver = SemVer.parse(result.new_version)
    new_recipe_name = f"{result.recipe_name}_{semver.to_suffix()}"

    content = result.refactored_content
    if f'name = "{result.recipe_name}"' in content:
        content = content.replace(f'name = "{result.recipe_name}"', f'name = "{new_recipe_name}"', 1)

    new_filename = f"meta_agent__{new_recipe_name}_{now_str()}.toml"
    new_path = target_dir / new_filename

    try:
        new_path.write_text(content, encoding="utf-8")
        return True, str(new_path), f"Saved as new recipe: {new_recipe_name} -> {new_path.name}"
    except Exception as e:
        return False, str(new_path), f"Failed to create new recipe file {new_path}: {e}"
