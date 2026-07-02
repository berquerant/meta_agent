import logging
import os
import sys
from dataclasses import dataclass, field

from .api import inspect_recipe
from .utils import json_dumps


@dataclass
class AskingRawRequest:
    jarvis: str | None = None
    args: list[str] = field(default_factory=list)

    @property
    def __jarvis(self) -> list[str]:
        if self.jarvis:
            return [self.jarvis]
        return ["uv", "run", "jarvis"]

    def run(self) -> None:
        cmd = self.__jarvis + self.args
        logging.info("exec: %s", json_dumps(cmd))
        sys.stdout.flush()
        sys.stderr.flush()
        os.execvp(cmd[0], cmd)


@dataclass
class AskingRequest:
    recipe: str
    engine: str
    model: str
    agent: str
    tools: str
    system: str
    jarvis: str | None = None


@dataclass
class AskingOpts:
    engine: str
    model: str
    agent: str
    system: str
    tools: str
    jarvis: str | None = None

    @staticmethod
    def new(req: AskingRequest) -> AskingOpts:
        r = inspect_recipe(req.recipe)
        if r is None:
            raise Exception(f"Recipe {req.recipe} is not found!")

        engine = req.engine or r.engine_key or "ollama"
        model = req.model or r.model or "gemma4:12b"
        agent = req.agent or r.agent_type or "orchestrator"
        tools = ""
        if req.tools is not None:
            tools = req.tools
        elif r.tools is not None:
            tools = ",".join(r.tools)
        system = req.system or r.system_prompt or ""
        return AskingOpts(engine=engine, model=model, agent=agent, tools=tools, system=system, jarvis=req.jarvis)

    @property
    def __jarvis(self) -> list[str]:
        if self.jarvis:
            return [self.jarvis]
        return ["uv", "run", "jarvis"]

    def as_cli_ask_opts(self, query: str) -> list[str]:
        cmd = [
            "--engine",
            self.engine,
            "--model",
            self.model,
            "--agent",
            self.agent,
        ]
        if len(self.tools) > 0:
            cmd += ["--tools", self.tools]
        cmd += [self.system + "\n# クエリ\n" + query]
        return cmd

    def as_cli_chat_opts(self) -> list[str]:
        cmd = [
            "--engine",
            self.engine,
            "--model",
            self.model,
            "--agent",
            self.agent,
            "--system",
            self.system,
        ]
        if len(self.tools) > 0:
            cmd += ["--tools", self.tools]
        return cmd

    def __execvp(self, cmd: list[str]) -> None:
        logging.info("exec: %s", json_dumps(cmd))
        sys.stdout.flush()
        sys.stderr.flush()
        os.execvp(cmd[0], cmd)

    def ask(self, query: str) -> None:
        self.__execvp(self.__jarvis + ["ask"] + self.as_cli_ask_opts(query))

    def chat(self) -> None:
        self.__execvp(self.__jarvis + ["chat"] + self.as_cli_chat_opts())
