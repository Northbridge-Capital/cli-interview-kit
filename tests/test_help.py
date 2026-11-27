"""Help and usage output."""

from __future__ import annotations

import pytest
from helpers import app, question

from cli_interview_kit import App, Command, Option


def help_of(tool: App, *argv: str, capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(SystemExit):
        tool.main([*argv, "--help"])
    return capsys.readouterr().out


def test_top_level_help_lists_the_commands(capsys: pytest.CaptureFixture[str]) -> None:
    out = help_of(app(question("name")), capsys=capsys)
    assert out.startswith("usage: tool [-h] [--version] [--debug] {go} ...\n\nA tool.\n")
    assert "commands:\n  go\n    Go.\n" in out


def test_command_help_groups_flags_by_section(capsys: pytest.CaptureFixture[str]) -> None:
    out = help_of(
        app(
            question("name", help="Literal [brackets] stay."),
            question("fast", "confirm", section="speed"),
            question("color", "select", choices=("red", "blue"), section="speed"),
        ),
        "go",
        capsys=capsys,
    )
    assert "main:\n  --name NAME\n    Literal [brackets] stay.\n" in out
    assert "speed:\n  --fast, --no-fast\n    The fast.\n  --color {red,blue}\n" in out
    assert "interaction:\n  --yes\n" in out
    assert "  --questions\n" in out


def test_long_usage_lines_are_summarised(capsys: pytest.CaptureFixture[str]) -> None:
    options = tuple(Option(dest=f"flag_{i}", kind="switch", help="h") for i in range(9))
    positional = Option(dest="target", kind="positional", help="h")
    command = Command(name="go", help="Go.", options=(*options, positional), run=print)
    tool = App(name="tool", description="", version="1", commands=(command,))
    out = help_of(tool, "go", capsys=capsys)
    assert out.startswith("usage: tool go [-h] [OPTIONS] target\n")


def test_custom_kinds_show_their_flag_form(capsys: pytest.CaptureFixture[str]) -> None:
    from cli_interview_kit import CustomKind

    stage = CustomKind(flag_form="NAME:KIND", parse=list, prompt=print)
    out = help_of(
        app(question("stage", "custom", custom="stage"), custom_kinds={"stage": stage}),
        "go",
        capsys=capsys,
    )
    assert "  --stage NAME:KIND\n" in out


def test_metavars_override_the_value_name(capsys: pytest.CaptureFixture[str]) -> None:
    out = help_of(app(question("name", metavar="SNAKE_NAME")), "go", capsys=capsys)
    assert "  --name SNAKE_NAME\n" in out


def test_print_usage_renders_the_usage_line(capsys: pytest.CaptureFixture[str]) -> None:
    app(question("name")).build_parser().print_usage()
    assert capsys.readouterr().err == "usage: tool [-h] [--version] [--debug] {go} ...\n"
