"""Unit tests for OpenJarvisClient and LLM defaults resolution in meta_agent.llm."""

from unittest.mock import MagicMock, patch

from meta_agent.config import DefaultsConfig, MetaAgentConfig
from meta_agent.llm import OpenJarvisClient, get_llm_client, set_llm_client, reset_llm_client


def test_get_and_set_llm_client() -> None:
    """Test get_llm_client singleton and override."""
    reset_llm_client()
    default_client = get_llm_client()
    assert isinstance(default_client, OpenJarvisClient)

    mock_client = MagicMock()
    set_llm_client(mock_client)
    assert get_llm_client() is mock_client

    reset_llm_client()
    assert isinstance(get_llm_client(), OpenJarvisClient)


def test_openjarvis_client_resolve_defaults_explicit() -> None:
    """Test explicit max_tokens and temperature take precedence."""
    client = OpenJarvisClient()
    max_tokens, temp = client._resolve_defaults(max_tokens=4096, temperature=0.3)
    assert max_tokens == 4096
    assert temp == 0.3


def test_openjarvis_client_resolve_defaults_from_config() -> None:
    """Test fallback to config.json defaults when None."""
    client = OpenJarvisClient()
    cfg = MetaAgentConfig(defaults=DefaultsConfig(max_tokens=8192, temperature=0.8))
    with patch("meta_agent.config.load_config", return_value=cfg):
        max_tokens, temp = client._resolve_defaults(max_tokens=None, temperature=None)
        assert max_tokens == 8192
        assert temp == 0.8


def test_openjarvis_client_ask_passes_tokens_and_temp() -> None:
    """Test OpenJarvisClient.ask propagates max_tokens and temperature to Jarvis."""
    client = OpenJarvisClient()
    mock_jarvis = MagicMock()
    mock_jarvis.ask_full.return_value = {"content": "ok"}

    with patch("openjarvis.Jarvis", return_value=mock_jarvis) as mock_cls:
        res = client.ask("test query", max_tokens=2048, temperature=0.1)
        assert res == "ok"
        mock_cls.assert_called_once_with(model="llama3", engine_key="ollama")
        mock_jarvis.ask_full.assert_called_once()
        _, kwargs = mock_jarvis.ask_full.call_args
        assert kwargs["max_tokens"] == 2048
        assert kwargs["temperature"] == 0.1
