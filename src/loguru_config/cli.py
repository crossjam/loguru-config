"""Command line interface for the loguru-config package."""

from __future__ import annotations

import json
import pathlib
import random
from copy import deepcopy
from typing import Dict, Iterable, Iterator, Optional, Sequence, Tuple

import click
from click_default_group import DefaultGroup
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from loguru_config.loguru_config import LoguruConfig
from loguru_config.parsable_config import ParsableConfiguration
from loguru_config.example_stubs import ensure_example_stubs

console = Console()


def _snapshot_default_levels() -> Dict[str, object]:
    from loguru import logger

    # ``logger._core.levels`` holds ``Level`` namedtuples which are immutable, so a
    # shallow copy is sufficient. We still use ``deepcopy`` to guard against any
    # future changes in Loguru's implementation while keeping mutations isolated.
    return {name: deepcopy(level) for name, level in logger._core.levels.items()}


_DEFAULT_LEVEL_STATE = _snapshot_default_levels()


class CliError(click.ClickException):
    """Custom Click exception for CLI specific errors."""


def _read_text_source(source: Optional[str]) -> tuple[str, Optional[pathlib.Path]]:
    """Return the text contents and source path for the provided argument."""

    if source in (None, "-"):
        stream = click.get_text_stream("stdin")
        text = stream.read()
        if not text.strip():
            raise CliError("No configuration data received from standard input.")
        return text, None

    path = pathlib.Path(source)
    try:
        text = path.read_text()
    except OSError as exc:  # pragma: no cover - exercised during runtime errors.
        raise CliError(str(exc)) from exc
    return text, path


def _load_config_text(config_text: str) -> tuple[Dict, str]:
    """Load raw configuration text into a dictionary and return the loader name."""

    errors: Dict[str, Exception] = {}
    for loader in ParsableConfiguration.supported_loaders:
        try:
            loaded = loader(config_text)
            if isinstance(loaded, dict):
                return loaded, loader.__name__
            errors[loader.__name__] = TypeError(
                "Loader did not return a mapping configuration."
            )
        except ImportError:
            # Loader dependency is not installed, skip silently so another loader can succeed.
            continue
        except Exception as exc:  # pragma: no cover - exercised when parsing fails.
            errors[loader.__name__] = exc

    formatted = "\n".join(
        f"  - {name}: {exc}" for name, exc in errors.items()
    )
    raise CliError(
        "Unable to parse configuration text with any supported loader." +
        (f"\n{formatted}" if formatted else "")
    )


def _load_loguru_config(source: Optional[str]) -> tuple[LoguruConfig, Dict, Optional[pathlib.Path], str]:
    text, path = _read_text_source(source)
    data, loader_name = _load_config_text(text)
    config = LoguruConfig.load(data, inplace=True, configure=False)
    if config is None:  # pragma: no cover - defensive, load returns config when configure=False.
        raise CliError("Failed to load configuration")
    return config.parse(), data, path, loader_name


def _iter_sources(configs: Sequence[Optional[str]]) -> Iterator[Optional[str]]:
    if not configs:
        yield None
        return

    for config in configs:
        yield config


def _load_multiple_configs(configs: Sequence[Optional[str]]) -> list[tuple[LoguruConfig, Dict, Optional[pathlib.Path], str]]:
    return [_load_loguru_config(source) for source in _iter_sources(configs)]


def _render_heading(paths: Sequence[Optional[pathlib.Path]], index: int) -> None:
    if len(paths) > 1:
        path = paths[index]
        console.rule(str(path) if path else "stdin")


@click.group(
    cls=DefaultGroup,
    default="about",
    default_if_no_args=True,
    invoke_without_command=True,
)
@click.version_option()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Utilities for validating and experimenting with loguru-config files."""

    if ctx.invoked_subcommand is None:
        ctx.invoke(about)


@cli.command()
def about() -> None:
    """Show details about the loguru-config command line interface."""

    panel = Panel.fit(
        "[bold]loguru-config[/bold]\n"
        "Utilities for validating, converting, and exercising Loguru configuration files."\
        "\n\n"
        "Use [cyan]validate[/cyan] to ensure a configuration can be parsed,\n"
        "[cyan]test[/cyan] to exercise logging with random fortunes, and\n"
        "[cyan]convert[/cyan] to transform between supported serialization formats.",
        title="About",
        border_style="blue",
    )
    console.print(panel)


@cli.command()
@click.argument("configs", nargs=-1)
def validate(configs: Tuple[str, ...]) -> None:
    """Validate configuration files, or stdin when no paths are provided."""

    loaded = _load_multiple_configs(configs)
    paths = [path for _, __, path, ___ in loaded]

    for index, (loguru_config, _, path, _) in enumerate(loaded):
        _render_heading(paths, index)
        summary = Table(title="Configuration Summary", show_header=False)
        summary.add_row("Source", str(path) if path else "stdin")
        summary.add_row("Handlers", str(len(loguru_config.handlers or [])))
        summary.add_row("Levels", str(len(loguru_config.levels or [])))
        summary.add_row("Extra keys", str(len((loguru_config.extra or {}).keys())))
        summary.add_row("Activation entries", str(len(loguru_config.activation or [])))
        console.print("[green]Configuration is valid.[/green]")
        console.print(summary)


FORTUNES = (
    "You will find a new debugging insight today.",
    "A well-configured logger saves hours of tracing.",
    "Breakpoints cannot rival pristine log output.",
    "Logging clarity brings production serenity.",
    "Refactor fearlessly; the logs have your back.",
    "Verbose logs reveal the quietest bugs.",
    "Tracebacks tremble before tidy trace logs.",
    "A patient logger tells the story your tests forgot.",
    "Stack traces shine when log levels align.",
    "Tomorrow's outage is foiled by today's log review.",
    "May your log files roll gently and your metrics sing.",
)


def _iter_level_names(config: LoguruConfig) -> Iterable[str]:
    if config.levels:
        for entry in config.levels:
            if isinstance(entry, dict):
                name = entry.get("name")
            else:
                name = getattr(entry, "name", None)
            if name:
                yield str(name)
    else:
        yield from ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")


def _ensure_handler_directories(config: LoguruConfig) -> None:
    handlers = config.handlers or []
    for handler in handlers:
        sink = None
        if isinstance(handler, dict):
            sink = handler.get("sink")
        else:
            sink = getattr(handler, "sink", None)
        if isinstance(sink, str) and not sink.startswith("ext://"):
            path = pathlib.Path(sink)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)


def _remove_levels_for_config(config: LoguruConfig) -> None:
    from loguru import logger

    if not config.levels:
        return

    for entry in config.levels:
        if isinstance(entry, dict):
            name = entry.get("name")
        else:
            name = getattr(entry, "name", None)
        if name and name in logger._core.levels:  # type: ignore[attr-defined]
            del logger._core.levels[str(name)]  # type: ignore[attr-defined]


def _reset_custom_levels() -> None:
    from loguru import logger

    logger._core.levels.clear()  # type: ignore[attr-defined]
    logger._core.levels.update(  # type: ignore[attr-defined]
        {name: deepcopy(level) for name, level in _DEFAULT_LEVEL_STATE.items()}
    )


@cli.command()
@click.argument("configs", nargs=-1)
def test(configs: Tuple[str, ...]) -> None:
    """Validate configurations (or stdin) and emit fortunes for each log level."""

    ensure_example_stubs()
    loaded = _load_multiple_configs(configs)
    paths = [path for _, __, path, ___ in loaded]

    from loguru import logger

    for index, (loguru_config, _, path, _) in enumerate(loaded):
        _render_heading(paths, index)
        _ensure_handler_directories(loguru_config)
        _remove_levels_for_config(loguru_config)
        handler_ids = loguru_config.configure()
        console.print(
            f"[green]Configured logger with {len(handler_ids)} handlers from {path or 'stdin'}.[/green]"
        )

        table = Table(title="Fortune Log Messages")
        table.add_column("Level", style="magenta")
        table.add_column("Message", style="green")

        for level_name in _iter_level_names(loguru_config):
            message = random.choice(FORTUNES)
            table.add_row(level_name, message)
            logger.log(level_name, message)

        console.print(table)

        for handler_id in handler_ids:
            logger.remove(handler_id)
        _reset_custom_levels()


_SUPPORTED_FORMATS = {
    "json": "json",
    "json5": "json5",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
}


def _detect_format(
    path: Optional[pathlib.Path], explicit: Optional[str], fallback: Optional[str] = None
) -> str:
    if explicit:
        fmt = explicit.lower()
        if fmt not in _SUPPORTED_FORMATS:
            raise CliError(f"Unsupported format '{explicit}'.")
        return _SUPPORTED_FORMATS[fmt]
    if path and path.suffix:
        suffix = path.suffix.lstrip(".").lower()
        if suffix in _SUPPORTED_FORMATS:
            return _SUPPORTED_FORMATS[suffix]
    if fallback:
        fmt = fallback.lower()
        if fmt in _SUPPORTED_FORMATS:
            return _SUPPORTED_FORMATS[fmt]
        raise CliError(f"Unsupported fallback format '{fallback}'.")
    raise CliError("Unable to determine configuration format. Specify --input-format/--output-format explicitly.")


def _dump_config(data: Dict, fmt: str, indent: int = 2) -> str:
    fmt = fmt.lower()
    if fmt == "json":
        return json.dumps(data, indent=indent) + "\n"
    if fmt == "json5":
        try:
            import pyjson5
        except ImportError:  # pragma: no cover - depends on optional package.
            return json.dumps(data, indent=indent) + "\n"
        if hasattr(pyjson5, "dumps"):
            return pyjson5.dumps(data, indent=indent) + "\n"
        if hasattr(pyjson5, "encode"):
            return pyjson5.encode(data, indent=indent) + "\n"
        return json.dumps(data, indent=indent) + "\n"
    if fmt == "yaml":
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover
            raise CliError("PyYAML is required to output YAML format.") from exc
        return yaml.safe_dump(data, sort_keys=False)
    if fmt == "toml":
        try:
            import tomlkit
        except ImportError as exc:  # pragma: no cover
            raise CliError("tomlkit is required to output TOML format.") from exc
        return tomlkit.dumps(data)
    raise CliError(f"Unsupported output format '{fmt}'.")


@cli.command()
@click.argument("paths", nargs=-1)
@click.option("--input-format", "input_format", type=str, help="Input configuration format.")
@click.option("--output-format", "output_format", type=str, help="Output configuration format.")
@click.option("--indent", default=2, show_default=True, help="Indentation level for JSON/JSON5 output.")
def convert(
    paths: Tuple[str, ...],
    input_format: Optional[str],
    output_format: Optional[str],
    indent: int,
) -> None:
    """Convert configs, defaulting to stdin/stdout when no paths are supplied."""

    if not paths:
        conversions: list[Tuple[Optional[str], Optional[str]]] = [(None, None)]
    elif len(paths) == 1:
        conversions = [(paths[0], None)]
    elif len(paths) % 2 == 0:
        conversions = list(zip(paths[0::2], paths[1::2]))
    else:
        raise CliError("Provide input/output pairs when specifying multiple paths.")

    for index, (input_path_str, output_path_str) in enumerate(conversions):
        loguru_config, data, input_path, loader_name = _load_loguru_config(input_path_str)
        _ = loguru_config  # Only used for validation; conversion relies on raw data.

        inferred_input_format = {
            "load_json_config": "json",
            "load_yaml_config": "yaml",
            "load_json5_config": "json5",
            "load_toml_config": "toml",
        }.get(loader_name)

        input_fmt = _detect_format(input_path, input_format, inferred_input_format)
        output_path = pathlib.Path(output_path_str) if output_path_str and output_path_str != "-" else None
        output_fmt = _detect_format(output_path, output_format, input_fmt)

        rendered = _dump_config(data, output_fmt, indent=indent)

        if len(conversions) > 1:
            console.rule(f"Conversion {index + 1}")

        if output_path is None:
            click.echo(rendered, nl=False)
        else:
            output_path.write_text(rendered)
            console.print(
                f"[green]Converted {input_fmt.upper()} configuration to {output_fmt.upper()} at {output_path}.[/green]"
            )


def main() -> None:
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
