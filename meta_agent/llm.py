from collections.abc import Iterator
import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


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

    def _log_request(
        self,
        prompt: str,
        agent: str | None,
        tools: list[str] | None,
        engine: str,
        model: str,
        max_tokens: int | None,
        temperature: float | None,
    ) -> None:
        """Log request details including character and estimated token counts."""
        prompt_chars = len(prompt)
        est_tokens = max(1, prompt_chars // 4)
        logger.info(
            "LLM Request: prompt_chars=%d, estimated_prompt_tokens=%d, engine='%s', model='%s', agent=%s, "
            "tools_count=%d, max_tokens=%s, temperature=%s",
            prompt_chars,
            est_tokens,
            engine,
            model,
            agent or "none",
            len(tools) if tools else 0,
            max_tokens,
            temperature,
        )

    def _log_response(
        self,
        response_text: str,
        telemetry: dict[str, Any] | None,
        max_tokens: int | None,
    ) -> None:
        """Log response details and emit a warning if the response was truncated."""
        resp_chars = len(response_text)
        usage = (telemetry.get("usage") if telemetry else {}) or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens", max(1, resp_chars // 4) if resp_chars > 0 else 0)
        total_tokens = usage.get("total_tokens")
        finish_reason = telemetry.get("finish_reason") if telemetry else None

        logger.info(
            "LLM Response: response_chars=%d, prompt_tokens=%s, completion_tokens=%s, "
            "total_tokens=%s, finish_reason=%s",
            resp_chars,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            finish_reason,
        )

        is_truncated = finish_reason == "length" or (
            max_tokens is not None and isinstance(completion_tokens, int) and completion_tokens >= max_tokens
        )
        if is_truncated:
            logger.warning(
                "LLM response was truncated due to reaching max_tokens limit (max_tokens=%s, "
                "completion_tokens=%s, finish_reason=%s)",
                max_tokens,
                completion_tokens,
                finish_reason,
            )

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
        from openjarvis.core.events import EventType
        from .logging import request_context

        eff_max_tokens, eff_temperature = self._resolve_defaults(max_tokens, temperature)
        with request_context():
            self._log_request(prompt, agent, tools, engine, model, eff_max_tokens, eff_temperature)
            j = Jarvis(model=model, engine_key=engine)
            last_inference_event: dict[str, Any] = {}
            if hasattr(j, "_bus") and j._bus is not None:
                j._bus.subscribe(EventType.INFERENCE_END, lambda ev: last_inference_event.update(ev.data))
            try:
                res = j.ask_full(
                    prompt,
                    agent=agent,
                    tools=tools,
                    max_tokens=eff_max_tokens,
                    temperature=eff_temperature,
                )
                content = str(res.get("content", "")) if isinstance(res, dict) else str(res)
                self._log_response(content, last_inference_event, eff_max_tokens)
                return content
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
        from openjarvis.core.events import EventType
        from .logging import request_context

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

        with request_context():
            self._log_request(prompt, agent, tools, engine, model, eff_max_tokens, eff_temperature)
            j = Jarvis(model=model, engine_key=engine)
            last_inference_event: dict[str, Any] = {}
            if hasattr(j, "_bus") and j._bus is not None:
                j._bus.subscribe(EventType.INFERENCE_END, lambda ev: last_inference_event.update(ev.data))
            loop = asyncio.new_event_loop()
            collected_chunks: list[str] = []
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
                            chunk_str = str(chunk)
                            collected_chunks.append(chunk_str)
                            yield chunk_str
                    except StopAsyncIteration:
                        break
                full_resp = "".join(collected_chunks)
                self._log_response(full_resp, last_inference_event, eff_max_tokens)
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
