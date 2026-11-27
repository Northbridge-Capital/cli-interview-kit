"""Console output: results on stdout, status on stderr, nothing read as markup."""

from __future__ import annotations

import pytest
from conftest import CTRL_C, Keys

from cli_interview_kit import CliError, Console


def test_results_go_to_stdout_and_status_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    console = Console()
    console.print("result")
    console.info("i [b]x[/b]")
    console.success("s")
    console.warning("w")
    console.error("e")
    captured = capsys.readouterr()
    assert captured.out == "result\n"
    assert captured.err == "INFO i [b]x[/b]\nOK s\nWARN w\nERROR e\n"


def test_long_status_lines_are_not_wrapped(capsys: pytest.CaptureFixture[str]) -> None:
    Console().error("x" * 300)
    assert capsys.readouterr().err == "ERROR " + "x" * 300 + "\n"


def test_progress_reports_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    with Console().progress("Checking [files]") as update:
        update(1, 2, "a")
        update(2, 2, "b")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Checking [files]" in captured.err


@pytest.mark.parametrize("prompt", ["select", "checkbox"])
def test_nothing_to_choose_from_is_an_error(prompt: str) -> None:
    with pytest.raises(CliError, match="Pick: nothing to choose from"):
        getattr(Console(), prompt)("Pick", [], str)


def test_checkbox_ticks_the_given_choices(terminal: Keys) -> None:
    terminal("\r")
    assert Console().checkbox("Pick", ["a", "b", "c"], str, checked=["b"]) == ["b"]


def test_text_without_validation(terminal: Keys) -> None:
    terminal("x\r")
    assert Console().text("Name") == "x"


def test_cancelled_checkbox_raises(terminal: Keys) -> None:
    terminal(CTRL_C)
    with pytest.raises(KeyboardInterrupt):
        Console().checkbox("Pick", ["a"], str)
