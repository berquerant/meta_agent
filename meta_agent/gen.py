import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .api import Script
from .utils import now_str


@dataclass
class GenRequest:
    engine: str
    model: str
    query: str
    recipes_dir: str


@dataclass
class GenResponse:
    success: bool
    message: str
    name: str
    path: str


def generate_assistant(req: GenRequest) -> GenResponse:
    """Generate a new assistant."""
    from .logging import request_context

    with request_context():
        logging.debug("generate assistant: start, %s", req.query)
        s = Script(
            tools=["think", "list_tools", "list_agents"],
            agent="orchestrator",
            prompt=prompt + req.query,
        )
        r = s.run(engine=req.engine, model=req.model)
        print(r)
        try:
            t = tomllib.loads(r)
        except Exception:
            return GenResponse(
                success=False, message=f"Generated recipe is invalid toml! query={req.query}", name="", path=""
            )
        name = t["recipe"]["name"]
        p = Path(req.recipes_dir) / f"meta_agent__{name}_{now_str()}.toml"

        logging.info("Write the recipe %s into %s", name, p)
        try:
            with p.open("w") as f:
                print(r, file=f)
        except Exception as e:
            return GenResponse(success=False, message=f"Failed to persist the new recipe! {e}", name=name, path=str(p))
        logging.debug("generate_assistant: end, %s", name)
        return GenResponse(success=True, message="New recipe is generated.", name=name, path=str(p))


prompt = '''# Your Role
You are a meta-agent responsible for designing optimal AI assistant recipe specifications to accomplish the user's objective.
Analyze the given objective in depth, devise the most efficient and accurate combination of `agent`, `tools`, and `system_prompt`, and output the specification strictly in the designated TOML format.

# Thought Process & Steps
1. **Deconstruct Objective**: Break down the necessary thought process and actions required to achieve the user's goal (e.g. "code review", "log analysis").
2. **Component Selection**:
   - Select the required tools from the available tool registry.
   - Choose the most appropriate agent strategy (e.g. ReAct, Plan-and-Execute) from the agent registry.
3. **Prompt Engineering**:
   - Explicitly include "Role", "Constraints", and "Output Format" in the generated assistant's `system_prompt`.

# Constraints & Rules
- `agent.type` and `agent.tools` MUST only use names discovered via `list_agents` and `list_tools`. Do NOT fabricate non-existent tools or agents.
- Output strictly valid TOML format only. Do NOT include greetings, commentary, markdown explanation blocks, or notes.
- The output must be raw TOML content directly (no markdown code fence blocks like ```toml).
- The generated `system_prompt` must be clear, highly specific, and actionable.
- The assistant's `recipe.name` must contain only lowercase alphanumeric characters and hyphens.

# Output Format
You MUST output strictly in the following TOML structure:

[recipe]
name = "[assistant_name]"
description = "[concise description of the assistant]"
version = "0.1.0"

[engine]
key = "ollama"

[intelligence]
model = "gemma4:12b"

[agent]
type = "[agent_type chosen from list_agents]"
tools = [
    "[tool_1 chosen from list_tools]",
    "[tool_2 chosen from list_tools]",
]
system_prompt = """\\
# Your Role
[Describe the specific role and goal of this assistant]

# Constraints & Guidelines
- [List specific behavioral constraints, tone, and prohibited actions]
- [Guidelines on tool usage, e.g. 'Use tool X to perform Y']

# Output Format
[Define the clear output structure, e.g. Markdown format]
"""

# Query
'''  # noqa: E501
