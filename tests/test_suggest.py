"""The suggestion prompt: listing, highlighting, completing and validating."""

from __future__ import annotations

import pytest
from conftest import CTRL_C, DOWN, ENTER, TAB, UP, Keys

from cli_interview_kit import Console
from cli_interview_kit._suggest import MAX_SHOWN, _State  # pyright: ignore[reportPrivateUsage]

OWNERS = ["platform", "data", "web", "data"]


def ask(keys: Keys, typed: str, **kwargs: object) -> str:
    keys(typed)
    return Console().text("Owner", suggestions=OWNERS, **kwargs)  # pyright: ignore[reportArgumentType]


def test_typing_without_choosing_keeps_the_text(terminal: Keys) -> None:
    assert ask(terminal, "anything" + ENTER) == "anything"


def test_down_then_enter_accepts_the_highlight(terminal: Keys) -> None:
    assert ask(terminal, DOWN + DOWN + ENTER) == "data"


def test_up_from_nothing_highlights_the_last(terminal: Keys) -> None:
    assert ask(terminal, UP + ENTER) == "web"


def test_highlights_wrap_around(terminal: Keys) -> None:
    assert ask(terminal, DOWN * 4 + ENTER) == "platform"


def test_tab_completes_the_first_match(terminal: Keys) -> None:
    assert ask(terminal, "ta" + TAB + ENTER) == "data"


def test_tab_without_matches_changes_nothing(terminal: Keys) -> None:
    assert ask(terminal, "zz" + TAB + ENTER) == "zz"


def test_arrows_without_matches_do_nothing(terminal: Keys) -> None:
    assert ask(terminal, "zz" + DOWN + ENTER) == "zz"


def test_typing_drops_the_highlight(terminal: Keys) -> None:
    assert ask(terminal, DOWN + "x" + ENTER) == "x"


def test_an_invalid_answer_stays_until_fixed(terminal: Keys) -> None:
    def no_web(value: str) -> str:
        if value == "web":
            raise ValueError("Not web.")
        return value

    assert ask(terminal, UP + ENTER + "x" + ENTER, validate=no_web) == "x"


def test_the_default_is_the_starting_text(terminal: Keys) -> None:
    assert ask(terminal, ENTER, default="mine") == "mine"


def test_ctrl_c_cancels(terminal: Keys) -> None:
    with pytest.raises(KeyboardInterrupt):
        ask(terminal, CTRL_C)


def test_matching_is_anywhere_and_case_insensitive() -> None:
    state = _State(suggestions=["Platform", "data", "web"])
    assert state.matches("AT") == ["Platform", "data"]
    assert state.matches("data") == []  # an exact match is not suggested again
    many = _State(suggestions=[f"s{i}" for i in range(20)])
    assert len(many.matches("")) == MAX_SHOWN
