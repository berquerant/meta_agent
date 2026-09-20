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
    max_tokens: int | None = None
    temperature: float | None = None


@dataclass
class AskingOpts:
    engine: str
    model: str
    agent: str
    system: str
    tools: str
    jarvis: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None

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
        return AskingOpts(
            engine=engine,
            model=model,
            agent=agent,
            tools=tools,
            system=system,
            jarvis=req.jarvis,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )

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
        if self.max_tokens is not None:
            cmd += ["--max-tokens", str(self.max_tokens)]
        if self.temperature is not None:
            cmd += ["--temperature", str(self.temperature)]
        if len(self.tools) > 0:
            cmd += ["--tools", self.tools]
        cmd += [self.system + "\n# Query\n" + query]
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
        if self.max_tokens is not None:
            cmd += ["--max-tokens", str(self.max_tokens)]
        if self.temperature is not None:
            cmd += ["--temperature", str(self.temperature)]
        if len(self.tools) > 0:
            cmd += ["--tools", self.tools]
        return cmd

    def ask(self, query: str) -> None:
        """Execute a single query using LLMClient and print the response."""
        from .llm import get_llm_client

        tools_list = [t.strip() for t in self.tools.split(",") if t.strip()]
        full_query = (self.system + "\n# Query\n" + query) if self.system else query
        client = get_llm_client()

        # Stream chunks or get full response
        for chunk in client.ask_stream(
            full_query,
            agent=self.agent or "orchestrator",
            tools=tools_list,
            engine=self.engine,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        ):
            print(chunk, end="", flush=True)
        print()

    def chat(self) -> None:
        """Run an interactive CLI chat session with request tracking."""
        from .llm import get_llm_client
        from .tui.helpers import build_chat_prompt

        tools_list = [t.strip() for t in self.tools.split(",") if t.strip()]
        client = get_llm_client()
        history: list[tuple[str, str, str]] = []

        print(f"Starting chat session with agent '{self.agent}' (model: {self.model}, engine: {self.engine})")
        print("Type 'exit', 'quit', or press Ctrl+D / Ctrl+C to stop.\n")

        while True:
            try:
                user_input = input("User > ").strip()
            except EOFError, KeyboardInterrupt:
                print("\nExiting chat session.")
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Exiting chat session.")
                break

            full_query = build_chat_prompt(self.system, history, user_input)
            print("Assistant > ", end="", flush=True)
            chunks: list[str] = []
            try:
                for chunk in client.ask_stream(
                    full_query,
                    agent=self.agent or "orchestrator",
                    tools=tools_list,
                    engine=self.engine,
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                ):
                    print(chunk, end="", flush=True)
                    chunks.append(chunk)
                print("\n")
                assistant_response = "".join(chunks)
                from datetime import datetime

                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                history.append(("User", user_input, ts))
                history.append(("Assistant", assistant_response, ts))
            except Exception as e:
                print(f"\n⚠️ Error: {e}\n")
