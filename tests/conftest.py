"""Fixtures that run commands at a fake terminal or with nobody to ask.

``terminal`` drives the real prompts: keystrokes go into a prompt_toolkit
pipe and stdin reports itself as a terminal. ``unattended`` makes stdin a
pipe, as in CI or under an assistant.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

ENTER = "\r"
DOWN = "\x1b[B"
UP = "\x1b[A"
TAB = "\t"
SPACE = " "
CTRL_C = "\x03"
BACKSPACE = "\x7f"


class _Stdin:
    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


Keys = Callable[..., None]


@pytest.fixture
def terminal(monkeypatch: pytest.MonkeyPatch) -> Iterator[Keys]:
    """Yield ``keys(*chunks)``, which types into the next prompts."""
    monkeypatch.setattr(sys, "stdin", _Stdin(tty=True))
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):

        def keys(*chunks: str) -> None:
            pipe.send_text("".join(chunks))

        yield keys


@pytest.fixture
def unattended(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make stdin a pipe: nobody can be asked."""
    monkeypatch.setattr(sys, "stdin", _Stdin(tty=False))
