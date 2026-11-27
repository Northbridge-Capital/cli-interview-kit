"""The terminal interview: real prompts, driven through a prompt_toolkit pipe."""

from __future__ import annotations

from typing import Any

import pytest
from conftest import BACKSPACE, CTRL_C, DOWN, ENTER, SPACE, TAB, UP, Keys
from helpers import Recorder, app, question
from projects import APP

from cli_interview_kit import Console, CustomKind


def answers_of(
    keys_typed: str, keys: Keys, *questions: Any, argv: tuple[str, ...] = (), **interview: Any
) -> dict[str, Any]:
    recorder = Recorder()
    keys(keys_typed)
    assert app(*questions, run=recorder, **interview).main(["go", *argv]) == 0
    return recorder.answers


def test_the_example_interview(terminal: Keys, capsys: pytest.CaptureFixture[str]) -> None:
    terminal(
        "demo",
        ENTER,  # name
        DOWN,
        ENTER,  # template: service
        ENTER,  # owner: keeps the default
        ENTER,  # environments: every one stays ticked
        ENTER,
        ENTER,  # memory, instances
        ENTER,  # package: defaults to the name
        "y",
        "requests",
        ENTER,
        "n",  # one dependency
        "n",  # no labels
        "n",  # no CI
    )
    assert APP.main(["new"]) == 0
    out = capsys.readouterr().out
    for expected in (
        "'name': 'demo'",
        "'template': 'service'",
        "'owner': 'platform'",
        "'environment': ['dev', 'prod']",
        "'instances': 2",
        "'package': 'demo'",
        "'dependency': ['requests']",
        "'ci': False",
    ):
        assert expected in out


def test_flags_are_not_asked_again(terminal: Keys) -> None:
    answers = answers_of(
        "",
        terminal,
        question("name"),
        question("fast", "confirm"),
        argv=("--name", "x", "--no-fast"),
    )
    assert answers == {"name": "x", "fast": False}


def test_an_invalid_answer_is_asked_again(terminal: Keys) -> None:
    def short(value: str) -> str:
        if len(value) > 2:
            raise ValueError("Too long.")
        return value

    answers = answers_of(
        "abc" + ENTER + BACKSPACE + ENTER, terminal, question("name", validator=short)
    )
    assert answers == {"name": "ab"}


def test_a_required_text_answer_cannot_be_blank(terminal: Keys) -> None:
    assert answers_of(ENTER + "x" + ENTER, terminal, question("name", required=True)) == {
        "name": "x"
    }


def test_select_and_multiselect(terminal: Keys) -> None:
    answers = answers_of(
        DOWN + ENTER + SPACE + DOWN + ENTER,
        terminal,
        question("color", "select", choices=("red", "blue"), labels={"red": "Red!"}),
        question("tag", "multiselect", choices=("a", "b", "c")),
    )
    assert answers == {"color": "blue", "tag": ["b", "c"]}


def test_a_required_multiselect_needs_a_choice(
    terminal: Keys, capsys: pytest.CaptureFixture[str]
) -> None:
    terminal(SPACE, DOWN, SPACE, ENTER)
    assert app(question("tag", "multiselect", choices=("a", "b"), required=True)).main(["go"]) == 1
    assert "--tag: choose at least one." in capsys.readouterr().err


def test_int_answers(terminal: Keys) -> None:
    answers = answers_of(
        "x" + ENTER + BACKSPACE + "7" + ENTER + ENTER,
        terminal,
        question("count", "int"),
        question("workers", "int", default=3),
    )
    assert answers == {"count": 7, "workers": 3}


def test_lists_and_pairs(terminal: Keys) -> None:
    answers = answers_of(
        "a"
        + ENTER
        + "y"
        + "b"
        + ENTER
        + "n"  # required list: no "Add?" first
        + "y"
        + "k"
        + ENTER
        + "v"
        + ENTER
        + "y"
        + "k"
        + ENTER
        + BACKSPACE
        + "j"
        + ENTER
        + "w"
        + ENTER
        + "n",
        terminal,
        question("item", "list", required=True),
        question("label", "pairs"),
    )
    assert answers == {"item": ["a", "b"], "label": {"k": "v", "j": "w"}}


def test_list_suggestions_leave_out_what_was_entered(terminal: Keys) -> None:
    answers = answers_of(
        "y" + DOWN + ENTER + "y" + DOWN + ENTER + "n",
        terminal,
        question("item", "list", suggestions_from="known"),
        choices={"known": lambda _a, _i: ["first", "second"]},
    )
    assert answers == {"item": ["first", "second"]}


def test_text_suggestions_complete_with_tab(terminal: Keys) -> None:
    answers = answers_of(
        "pla" + TAB + ENTER,
        terminal,
        question("owner", suggestions_from="owners"),
        choices={"owners": lambda _a, _i: ["platform", "data"]},
    )
    assert answers == {"owner": "platform"}


def test_per_item_asks_each_item(terminal: Keys) -> None:
    answers = answers_of(
        DOWN + ENTER + ENTER,
        terminal,
        question(
            "pin",
            "per_item",
            items_from="schemas",
            choices_from="versions",
            prompt="Version of {item}",
        ),
        question("path", "per_item", items_from="one", default="/{item}"),
        choices={
            "schemas": lambda _a, _i: ["orders"],
            "versions": lambda _a, _i: ["1", "2"],
            "one": lambda _a, _i: ["x"],
        },
    )
    assert answers == {"pin": {"orders": "2"}, "path": {"x": "/x"}}


def test_custom_kinds_prompt_themselves(terminal: Keys) -> None:
    def ask(console: Console) -> str:
        return console.text("Stage")

    stage = CustomKind(flag_form="X", parse=lambda values: values, prompt=ask)
    answers = answers_of(
        "s" + ENTER,
        terminal,
        question("stage", "custom", custom="stage"),
        custom_kinds={"stage": stage},
    )
    assert answers == {"stage": "s"}


def test_ctrl_c_aborts_with_130(terminal: Keys, capsys: pytest.CaptureFixture[str]) -> None:
    terminal(CTRL_C)
    assert app(question("name")).main(["go"]) == 130
    assert "Aborted." in capsys.readouterr().err


@pytest.mark.parametrize(
    "declared",
    [
        question("name", suggestions_from="s"),
        question("color", "select", choices=("a", "b")),
        question("tag", "multiselect", choices=("a", "b")),
        question("fast", "confirm"),
    ],
)
def test_ctrl_c_aborts_every_prompt(
    terminal: Keys, capsys: pytest.CaptureFixture[str], declared: Any
) -> None:
    terminal(CTRL_C)
    assert app(declared, choices={"s": lambda _a, _i: ["x"]}).main(["go"]) == 130


def test_up_wraps_to_the_last_suggestion(terminal: Keys) -> None:
    answers = answers_of(
        UP + ENTER,
        terminal,
        question("owner", suggestions_from="owners"),
        choices={"owners": lambda _a, _i: ["platform", "data", "web"]},
    )
    assert answers == {"owner": "web"}
