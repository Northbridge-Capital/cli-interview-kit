"""The app: parsing, dispatch, help, and the error policy."""

from __future__ import annotations

import json
from typing import Any

import pytest
from helpers import Recorder, app
from projects import APP

from cli_interview_kit import (
    App,
    CliError,
    Command,
    Consent,
    DeclarationError,
    Interview,
    Invocation,
    Option,
    __version__,
)


def raising(error: BaseException) -> Any:
    def run(_invocation: Invocation) -> None:
        raise error

    return run


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_:
        APP.main(["--version"])
    assert exit_.value.code == 0
    assert capsys.readouterr().out == "projects 1.0.0\n"
    assert __version__


def test_a_usage_error_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_:
        APP.main(["new", "--no-such-flag"])
    assert exit_.value.code == 2
    err = capsys.readouterr().err
    assert err.startswith("usage: projects ")
    assert "ERROR unrecognized arguments: --no-such-flag" in err


@pytest.mark.usefixtures("unattended")
def test_cli_errors_print_their_message(capsys: pytest.CaptureFixture[str]) -> None:
    assert app(run=raising(CliError("It broke."))).main(["go"]) == 1
    assert capsys.readouterr().err == "ERROR It broke.\n"


@pytest.mark.usefixtures("unattended")
def test_expected_errors_print_their_message(capsys: pytest.CaptureFixture[str]) -> None:
    command = Command(name="go", help="Go.", run=raising(LookupError("Missing.")))
    tool = App(
        name="tool",
        description="",
        version="1",
        commands=(command,),
        expected_errors=(LookupError,),
    )
    assert tool.main(["go"]) == 1
    assert capsys.readouterr().err == "ERROR Missing.\n"


@pytest.mark.usefixtures("unattended")
def test_unexpected_errors_print_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    assert app(run=raising(RuntimeError("Boom."))).main(["go"]) == 1
    assert capsys.readouterr().err == (
        "ERROR Unexpected RuntimeError: Boom.. Rerun with `tool --debug ...` for the traceback.\n"
    )


@pytest.mark.usefixtures("unattended")
def test_debug_shows_the_traceback() -> None:
    with pytest.raises(RuntimeError, match="Boom"):
        app(run=raising(RuntimeError("Boom."))).main(["--debug", "go"])


@pytest.mark.usefixtures("unattended")
def test_interrupts_exit_130(capsys: pytest.CaptureFixture[str]) -> None:
    assert app(run=raising(KeyboardInterrupt())).main(["go"]) == 130
    assert capsys.readouterr().err == "ERROR Aborted.\n"


@pytest.mark.usefixtures("unattended")
def test_messages_are_never_read_as_markup(capsys: pytest.CaptureFixture[str]) -> None:
    assert app(run=raising(CliError("Bad value '[/bold]' and [red]x[/red]."))).main(["go"]) == 1
    assert capsys.readouterr().err == "ERROR Bad value '[/bold]' and [red]x[/red].\n"


@pytest.mark.usefixtures("unattended")
def test_subcommands_and_groups(capsys: pytest.CaptureFixture[str]) -> None:
    recorder = Recorder()
    leaf = Command(
        name="add",
        help="Add.",
        options=(Option(dest="skill", kind="positional", nargs="+", help="Skills."),),
        run=recorder,
    )
    group = Command(name="skills", help="Skills.", subcommands=(leaf,))
    tool = App(name="tool", description="", version="1", commands=(group,))
    assert tool.main(["skills", "add", "a", "b"]) == 0
    assert recorder.invocation is not None
    assert recorder.invocation.options == {"skill": ["a", "b"]}
    with pytest.raises(SystemExit):
        tool.main(["skills"])


@pytest.mark.usefixtures("unattended")
def test_a_runnable_group_does_not_need_a_subcommand() -> None:
    recorder = Recorder()
    leaf = Command(name="add", help="Add.", run=print)
    group = Command(name="skills", help="Skills.", subcommands=(leaf,), run=recorder)
    tool = App(name="tool", description="", version="1", commands=(group,))
    assert tool.main(["skills"]) == 0
    assert recorder.invocation is not None


@pytest.mark.usefixtures("unattended")
def test_options_of_every_kind() -> None:
    recorder = Recorder()
    command = Command(
        name="go",
        help="Go.",
        options=(
            Option(dest="check", kind="switch", help="h", exclusive="mode"),
            Option(dest="diff", kind="switch", help="h", exclusive="mode"),
            Option(dest="size", help="h", convert=int, metavar="N"),
            Option(dest="color", help="h", choices=("red", "blue")),
            Option(dest="tag", kind="append", help="h"),
        ),
        run=recorder,
    )
    tool = App(name="tool", description="", version="1", commands=(command,))
    assert (
        tool.main(["go", "--diff", "--size", "3", "--color", "red", "--tag", "a", "--tag", "b"])
        == 0
    )
    assert recorder.invocation is not None
    assert recorder.invocation.options == {
        "check": False,
        "diff": True,
        "size": 3,
        "color": "red",
        "tag": ["a", "b"],
    }
    with pytest.raises(SystemExit):
        tool.main(["go", "--check", "--diff"])


@pytest.mark.usefixtures("unattended")
def test_yes_grants_consent(capsys: pytest.CaptureFixture[str]) -> None:
    assert APP.main(["remove", "--name", "billing", "--yes"]) == 0
    assert "OK Deleted billing." in capsys.readouterr().err


@pytest.mark.usefixtures("unattended")
def test_without_yes_a_consent_nobody_can_give_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert APP.main(["remove", "--name", "billing"]) == 1
    assert (
        "ERROR Delete project 'billing'? This needs consent: rerun with --yes."
        in capsys.readouterr().err
    )


@pytest.mark.usefixtures("unattended")
def test_a_safe_default_answers_a_consent_nobody_can_give(
    capsys: pytest.CaptureFixture[str],
) -> None:
    overwrite = Consent(key="overwrite", when="when files exist", safe_default=False)

    def run(invocation: Invocation) -> None:
        if not overwrite.ask(invocation.console, invocation.interaction, "Overwrite?"):
            invocation.console.warning("Kept the files.")

    command = Command(name="go", help="Go.", interview=Interview(consents=(overwrite,)), run=run)
    assert App(name="tool", description="", version="1", commands=(command,)).main(["go"]) == 0
    assert "WARN Kept the files." in capsys.readouterr().err


def test_a_consent_is_asked_at_a_terminal(
    terminal: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    terminal("n")
    assert APP.main(["remove", "--name", "billing"]) == 0
    assert "WARN Nothing was deleted." in capsys.readouterr().err


@pytest.mark.usefixtures("unattended")
def test_an_undeclared_consent_is_a_declaration_error() -> None:
    undeclared = Consent(key="sneaky", when="never listed")

    def run(invocation: Invocation) -> None:
        undeclared.ask(invocation.console, invocation.interaction, "Sure?")

    with pytest.raises(DeclarationError, match="Consent 'sneaky' is not declared"):
        app(run=run).main(["--debug", "go"])


@pytest.mark.usefixtures("unattended")
def test_the_example_reports_cli_errors(capsys: pytest.CaptureFixture[str]) -> None:
    assert APP.main(["new", "--name", "billing", "--dry-run"]) == 1
    assert "ERROR Project 'billing' already exists." in capsys.readouterr().err
    assert APP.main(["new", "--name", "fresh", "--dry-run"]) == 0
    captured = capsys.readouterr()
    assert "INFO Dry run: nothing is created." in captured.err
    assert "'name': 'fresh'" in captured.out


def test_questions_print_json_only(capsys: pytest.CaptureFixture[str]) -> None:
    assert APP.main(["remove", "--questions"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    document = json.loads(captured.out)
    assert document["command"] == "projects remove --yes"
    assert document["consents"] == [
        {
            "key": "delete",
            "when": "always: removing a project deletes it and its history",
            "safe_default": None,
        }
    ]
