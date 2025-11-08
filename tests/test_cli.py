import json
import sys
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from loguru_config.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def minimal_config_json() -> str:
    return json.dumps({
        "handlers": [
            {
                "sink": "ext://sys.stdout",
                "format": "{level} - {message}",
            }
        ]
    })


def test_about_command_displays_description(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["about"])
    assert result.exit_code == 0
    assert "loguru-config" in result.output
    assert "Utilities for validating" in result.output


def test_validate_reads_from_stdin_when_no_paths(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["validate"], input=minimal_config_json())
    assert result.exit_code == 0
    assert "Configuration is valid." in result.output
    assert "stdin" in result.output


def test_validate_handles_multiple_files(runner: CliRunner, tmp_path: Path) -> None:
    config_text = minimal_config_json()
    first = tmp_path / "config1.json"
    second = tmp_path / "config2.json"
    first.write_text(config_text)
    second.write_text(config_text)

    result = runner.invoke(cli, ["validate", str(first), str(second)])
    assert result.exit_code == 0
    assert result.output.count("Configuration is valid.") == 2


@pytest.mark.parametrize("command", [["validate"], ["test"], ["convert", "--output-format", "json"]])
def test_commands_handle_missing_input_data(runner: CliRunner, command: list[str]) -> None:
    result = runner.invoke(cli, command)
    assert result.exit_code != 0
    assert "No configuration data" in result.output or "Unable to parse" in result.output


def test_test_command_reads_from_stdin(monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    monkeypatch.setattr("loguru_config.cli.random.choice", lambda seq: seq[0])
    result = runner.invoke(cli, ["test"], input=minimal_config_json())
    assert result.exit_code == 0
    assert "Configured logger" in result.output
    assert "Fortune Log Messages" in result.output
    assert "You will find a new debugging insight today." in result.output


def test_test_command_installs_example_stubs(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    monkeypatch.setattr("loguru_config.cli.random.choice", lambda seq: seq[0])
    monkeypatch.delitem(sys.modules, "my_module", raising=False)
    monkeypatch.delitem(sys.modules, "my_module.secret", raising=False)
    result = runner.invoke(cli, ["test"], input=minimal_config_json())
    assert result.exit_code == 0
    assert "my_module.secret" in sys.modules


def test_test_command_handles_multiple_files(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_path: Path
) -> None:
    monkeypatch.setattr("loguru_config.cli.random.choice", lambda seq: seq[0])
    base = {
        "handlers": [
            {
                "sink": "ext://sys.stdout",
                "format": "{level} - {message}",
            }
        ],
        "levels": [
            {"name": "NOTICE", "no": 15, "icon": "!", "color": ""}
        ],
    }
    second = {
        "handlers": [
            {
                "sink": "ext://sys.stdout",
                "format": "{level} - {message}",
            }
        ],
        "levels": [
            {"name": "NOTICE", "no": 15, "icon": "!", "color": ""}
        ],
    }
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text(json.dumps(base))
    second_path.write_text(json.dumps(second))

    result = runner.invoke(cli, ["test", str(first_path), str(second_path)])
    assert result.exit_code == 0
    assert result.output.count("Configured logger") == 2


def test_convert_defaults_to_stdio(runner: CliRunner) -> None:
    yaml_config = textwrap.dedent(
        """
        handlers:
          - sink: ext://sys.stdout
            format: "{level} - {message}"
        """
    )
    result = runner.invoke(
        cli,
        ["convert", "--output-format", "json"],
        input=yaml_config,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["handlers"][0]["sink"] == "ext://sys.stdout"

