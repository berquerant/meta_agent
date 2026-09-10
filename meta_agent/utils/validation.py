"""Validation utilities for recipes and registered components."""

from dataclasses import dataclass, field
from typing import Any

from ..api import (
    list_agents,
    list_engines,
    list_models,
    list_tools,
)


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


def _validate_tools(tools: Any, report: ValidationReport) -> None:
    """Validate tool names against registered tools."""
    if not isinstance(tools, list):
        return
    available_tools = {t.name for t in list_tools()}
    for tool in tools:
        if tool and tool not in available_tools:
            report.invalid_tools.append(str(tool))
            report.warnings.append(f"Tool '{tool}' is not registered in ToolRegistry.")


def _validate_agent(agent: Any, report: ValidationReport) -> None:
    """Validate agent type against registered agents."""
    if not agent:
        return
    available_agents = {a.name for a in list_agents()}
    if agent not in available_agents:
        report.invalid_agent = str(agent)
        report.warnings.append(f"Agent '{agent}' is not registered in AgentRegistry.")


def _validate_engine_and_model(
    engine_key: str,
    model: Any,
    report: ValidationReport,
) -> None:
    """Validate engine key and model name against registered engines/models."""
    available_engines = {e.name for e in list_engines(default_engine=engine_key)}
    if engine_key and available_engines and engine_key not in available_engines:
        report.invalid_engine = str(engine_key)
        report.warnings.append(f"Engine '{engine_key}' is not recognized.")

    if model:
        available_models = {m.name for m in list_models(engine=engine_key)}
        if available_models and model not in available_models:
            report.invalid_model = str(model)
            report.warnings.append(f"Model '{model}' was not found for engine '{engine_key}'.")


def validate_recipe_components(
    recipe_toml_dict: dict[str, Any],
    default_engine: str = "ollama",
) -> ValidationReport:
    """Validate recipe tools, agent, engine, and model against registered components."""
    report = ValidationReport()

    tools = recipe_toml_dict.get("agent", {}).get("tools", [])
    _validate_tools(tools, report)

    agent = recipe_toml_dict.get("agent", {}).get("type")
    _validate_agent(agent, report)

    engine_key = recipe_toml_dict.get("engine", {}).get("key") or default_engine
    model = recipe_toml_dict.get("intelligence", {}).get("model")
    _validate_engine_and_model(engine_key, model, report)

    return report
