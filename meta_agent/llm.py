from __future__ import annotations

from collections.abc import Iterator
import logging
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM interactions to decouple meta_agent from OpenJarvis internals."""

    def ask(
        self,
        prompt: str,
        *,
        agent: str | None = None,
        tools: list[str] | None = None,
        engine: str = "ollama",
        model: str = "llama3",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Query LLM agent synchronously and return full text response."""
        ...

    def ask_stream(
        self,
        prompt: str,
        *,
        agent: str | None = None,
        tools: list[str] | None = None,
        engine: str = "ollama",
        model: str = "llama3",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        """Stream chunks from LLM agent progressively."""
        ...

    def list_engines(self, default_engine: str = "ollama") -> list[str]:
        """List available LLM engines."""
        ...

    def list_models(self, default_engine: str = "ollama") -> list[str]:
        """List available LLM models for the given engine."""
        ...


class OpenJarvisClient:
    """Default LLM client wrapping OpenJarvis."""

    def _resolve_defaults(self, max_tokens: int | None, temperature: float | None) -> tuple[int | None, float | None]:
        """Resolve max_tokens and temperature using config defaults if not provided."""
        if max_tokens is not None and temperature is not None:
            return max_tokens, temperature
        from .config import load_config

        cfg = load_config()
        resolved_max_tokens = max_tokens if max_tokens is not None else cfg.defaults.max_tokens
        resolved_temperature = temperature if temperature is not None else cfg.defaults.temperature
        return resolved_max_tokens, resolved_temperature

    def ask(
        self,
        prompt: str,
        *,
        agent: str | None = None,
        tools: list[str] | None = None,
        engine: str = "ollama",
        model: str = "llama3",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Query Jarvis and return full response."""
        from openjarvis import Jarvis

        eff_max_tokens, eff_temperature = self._resolve_defaults(max_tokens, temperature)
        j = Jarvis(model=model, engine_key=engine)
        try:
            res = j.ask_full(
                prompt,
                agent=agent,
                tools=tools,
                max_tokens=eff_max_tokens,
                temperature=eff_temperature,
            )
            if isinstance(res, dict):
                return str(res.get("content", ""))
            return str(res)
        except Exception as exc:
            logging.error("OpenJarvisClient.ask error: %s", exc)
            raise Exception("Error during asking") from exc
        finally:
            try:
                j.close()
            except Exception:
                pass

    def ask_stream(
        self,
        prompt: str,
        *,
        agent: str | None = None,
        tools: list[str] | None = None,
        engine: str = "ollama",
        model: str = "llama3",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        """Stream chunks from Jarvis."""
        import asyncio
        from openjarvis import Jarvis

        eff_max_tokens, eff_temperature = self._resolve_defaults(max_tokens, temperature)

        # If a complex agent is requested, stream is unsupported in OpenJarvis; fallback to ask
        if agent and agent not in ("simple", "none", "direct"):
            res = self.ask(
                prompt,
                agent=agent,
                tools=tools,
                engine=engine,
                model=model,
                max_tokens=eff_max_tokens,
                temperature=eff_temperature,
            )
            yield res
            return

        j = Jarvis(model=model, engine_key=engine)
        loop = asyncio.new_event_loop()
        try:
            gen = j.ask_stream(
                prompt,
                model=model,
                max_tokens=eff_max_tokens,
                temperature=eff_temperature,
            )
            while True:
                try:
                    chunk = loop.run_until_complete(gen.__anext__())
                    if chunk:
                        yield str(chunk)
                except StopAsyncIteration:
                    break
        except Exception as exc:
            logging.warning("Stream error, falling back to ask: %s", exc)
            res = self.ask(
                prompt,
                agent=agent,
                tools=tools,
                engine=engine,
                model=model,
                max_tokens=eff_max_tokens,
                temperature=eff_temperature,
            )
            yield res
        finally:
            try:
                loop.close()
            except Exception:
                pass
            try:
                j.close()
            except Exception:
                pass

    def list_engines(self, default_engine: str = "ollama") -> list[str]:
        """Discover available engines via OpenJarvis."""
        from openjarvis import Jarvis

        try:
            j = Jarvis(engine_key=default_engine)
            res = j.list_engines() or []
            return list(res)
        except Exception as exc:
            logging.warning("Failed to list engines via OpenJarvis: %s", exc)
            return []

    def list_models(self, default_engine: str = "ollama") -> list[str]:
        """Discover available models via OpenJarvis."""
        from openjarvis import Jarvis

        try:
            j = Jarvis(engine_key=default_engine)
            res = j.list_models() or []
            return list(res)
        except Exception as exc:
            logging.warning("Failed to list models via OpenJarvis: %s", exc)
            return []


_global_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get the active LLM client instance (or default OpenJarvisClient)."""
    global _global_llm_client
    if _global_llm_client is None:
        _global_llm_client = OpenJarvisClient()
    return _global_llm_client


def set_llm_client(client: LLMClient | None) -> None:
    """Override active LLM client (useful for mock injection during tests)."""
    global _global_llm_client
    _global_llm_client = client


def reset_llm_client() -> None:
    """Reset the LLM client to default OpenJarvisClient."""
    global _global_llm_client
    _global_llm_client = None
