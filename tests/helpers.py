"""Small builders for declarations under test."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cli_interview_kit import App, Command, Interview, Invocation, Option, Question


def question(key: str = "name", kind: Any = "text", **fields: Any) -> Question:
    """Return a question with every field the test does not care about filled in."""
    fields.setdefault("section", "main")
    fields.setdefault("prompt", key.capitalize())
    fields.setdefault("help", f"The {key}.")
    return Question(key=key, kind=kind, **fields)


class Recorder:
    """A run function that keeps what it received."""

    def __init__(self) -> None:
        self.invocation: Invocation | None = None

    def __call__(self, invocation: Invocation) -> None:
        self.invocation = invocation

    @property
    def answers(self) -> dict[str, Any]:
        assert self.invocation is not None, "the command did not run"
        return self.invocation.answers


def app(
    *questions: Question,
    run: Callable[[Invocation], None] | None = None,
    options: tuple[Option, ...] = (),
    **interview: Any,
) -> App:
    """Return an app whose one command, ``go``, has these questions."""
    command = Command(
        name="go",
        help="Go.",
        options=options,
        interview=Interview(questions=questions, **interview),
        run=run or Recorder(),
    )
    return App(name="tool", description="A tool.", version="1.2.3", commands=(command,))
