from unittest.mock import MagicMock, patch

import pytest

from meta_agent.api import (
    inspect_engine,
    inspect_model,
    list_engines,
    list_models,
)
from meta_agent.cmd import Cmd, InspectOpts, ListOpts


def test_api_list_and_inspect_engines() -> None:
    engines = list_engines()
    assert len(engines) > 0
    names = [e.name for e in engines]
    assert "ollama" in names

    eng = inspect_engine("ollama")
    assert eng is not None
    assert eng.name == "ollama"
    assert "Ollama" in eng.description

    none_eng = inspect_engine("non_existent_engine_key")
    assert none_eng is None


def test_api_list_and_inspect_models() -> None:
    mock_client = MagicMock()
    mock_client.list_models.return_value = ["llama3", "gemma2"]

    with patch("meta_agent.api.get_llm_client", return_value=mock_client):
        models = list_models(engine="ollama")
        assert len(models) == 2
        assert models[0].name == "llama3"
        assert models[0].engine == "ollama"
        assert models[1].name == "gemma2"

        mod = inspect_model("llama3", engine="ollama")
        assert mod is not None
        assert mod.name == "llama3"
        assert mod.engine == "ollama"

        none_mod = inspect_model("non_existent", engine="ollama")
        assert none_mod is None


def test_cmd_list_and_inspect_engines_output(capsys: pytest.CaptureFixture[str]) -> None:
    mock_client = MagicMock()
    mock_client.list_engines.return_value = ["ollama"]

    with patch("meta_agent.api.get_llm_client", return_value=mock_client):
        Cmd.list_engines_cmd(ListOpts(out="name", engine="ollama"))
        captured = capsys.readouterr()
        assert "ollama" in captured.out

        Cmd.inspect_engine_cmd(InspectOpts(out="name", name="ollama", engine="ollama"))
        captured = capsys.readouterr()
        assert "ollama" in captured.out


def test_cmd_list_and_inspect_models_output(capsys: pytest.CaptureFixture[str]) -> None:
    mock_client = MagicMock()
    mock_client.list_models.return_value = ["llama3"]

    with patch("meta_agent.api.get_llm_client", return_value=mock_client):
        Cmd.list_models_cmd(ListOpts(out="name", engine="ollama"))
        captured = capsys.readouterr()
        assert "llama3" in captured.out

        Cmd.inspect_model_cmd(InspectOpts(out="name", name="llama3", engine="ollama"))
        captured = capsys.readouterr()
        assert "llama3" in captured.out
