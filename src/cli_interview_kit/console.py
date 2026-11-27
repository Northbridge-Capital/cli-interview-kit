"""The one channel a command writes to and asks through.

Output follows the Unix convention: ``print`` writes the command's result to
stdout, and the status messages (``info``, ``success``, ``warning``,
``error``) and progress bars go to stderr, so a command's output can be piped
or parsed without the commentary. Status messages are plain text: anything in
them, including values the user typed, is printed literally and never read
as rich markup.

The prompts are questionary's, plus a free-text prompt that lists
suggestions under the input. Every prompt raises ``KeyboardInterrupt`` when
the user cancels it with Ctrl-C, which the app reports as ``Aborted.``.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from typing import TypeVar

import questionary
from questionary import Choice, Style
from rich.console import Console as RichConsole
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn
from rich.text import Text

from cli_interview_kit._suggest import suggest_text
from cli_interview_kit.errors import CliError
from cli_interview_kit.validators import Validator

T = TypeVar("T")

PROMPT_STYLE = Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "bold"),
        ("answer", "fg:green bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("suggestion", "fg:ansibrightblack"),
        # prompt_toolkit draws a validation message as a maroon bar by default.
        ("validation-toolbar", "noinherit fg:ansired bold"),
    ]
)
"""The prompts' colours; every prompt uses it."""


class Console:
    """Styled output and interactive prompts for a command.

    Methods
    -------
    print(renderable)
        Print a result to stdout: text, rich markup or any rich renderable.
    info(message), success(message), warning(message), error(message)
        Print a labelled status line to stderr, as plain text.
    progress(description)
        Show a progress bar on stderr for a series of named steps.
    select(prompt, choices, label)
        Ask for one of ``choices``.
    checkbox(prompt, choices, label, checked)
        Ask for any number of ``choices``.
    confirm(prompt, default)
        Ask a yes/no question.
    text(prompt, default, validate, suggestions)
        Ask for free text, validated, optionally with suggestions.
    """

    def __init__(self) -> None:
        self._out = RichConsole()
        self._err = RichConsole(stderr=True)

    def print(self, renderable: object) -> None:
        """Print a result to stdout: text, rich markup or a rich renderable."""
        self._out.print(renderable)

    def info(self, message: str) -> None:
        """Print an informational status line."""
        self._status("INFO", "bold cyan", message)

    def success(self, message: str) -> None:
        """Print a success status line."""
        self._status("OK", "bold green", message)

    def warning(self, message: str) -> None:
        """Print a warning status line."""
        self._status("WARN", "bold yellow", message)

    def error(self, message: str) -> None:
        """Print an error status line."""
        self._status("ERROR", "bold red", message)

    def _status(self, label: str, style: str, message: str) -> None:
        # Soft wrap: a long message stays one line when piped, for whatever reads it.
        self._err.print(
            Text.assemble((label, style), " ", message), highlight=False, soft_wrap=True
        )

    @contextmanager
    def progress(self, description: str) -> Generator[Callable[[int, int, str], None]]:
        """Show a progress bar on stderr for a series of named steps.

        Parameters
        ----------
        description : str
            What the steps do together, e.g. ``"Checking files"``.

        Yields
        ------
        Callable[[int, int, str], None]
            ``update(index, total, detail)``: call it before each step, with
            the step's 1-based index and what it is doing.
        """
        with Progress(
            TextColumn("[bold cyan]INFO[/bold cyan]"),
            TextColumn("{task.description}", markup=False),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("{task.fields[detail]}", markup=False),
            console=self._err,
        ) as progress:
            task = progress.add_task(description, total=None, detail="")

            def update(index: int, total: int, detail: str) -> None:
                progress.update(task, completed=index, total=total, detail=detail)

            yield update

    def select(self, prompt: str, choices: Sequence[T], label: Callable[[T], str]) -> T:
        """Ask for one of ``choices``.

        Parameters
        ----------
        prompt : str
            The question.
        choices : Sequence[T]
            What can be chosen.
        label : Callable[[T], str]
            How each choice is shown.

        Returns
        -------
        T
            The chosen item.

        Raises
        ------
        CliError
            If there is nothing to choose from.
        KeyboardInterrupt
            If the user cancels.
        """
        if not choices:
            raise CliError(f"{prompt}: nothing to choose from.")
        index: object = questionary.select(
            prompt,
            choices=[Choice(title=label(choice), value=i) for i, choice in enumerate(choices)],
            style=PROMPT_STYLE,
        ).ask()
        if not isinstance(index, int):
            raise KeyboardInterrupt
        return choices[index]

    def checkbox(
        self,
        prompt: str,
        choices: Sequence[T],
        label: Callable[[T], str],
        checked: Sequence[T] | None = None,
    ) -> list[T]:
        """Ask for any number of ``choices``.

        Parameters
        ----------
        prompt : str
            The question.
        choices : Sequence[T]
            What can be chosen.
        label : Callable[[T], str]
            How each choice is shown.
        checked : Sequence[T] | None, optional
            The choices ticked when the prompt opens; every choice when
            omitted, so the common answer "all of them" is one keypress.

        Returns
        -------
        list[T]
            The chosen items, in ``choices`` order.

        Raises
        ------
        CliError
            If there is nothing to choose from.
        KeyboardInterrupt
            If the user cancels.
        """
        if not choices:
            raise CliError(f"{prompt}: nothing to choose from.")
        ticked = choices if checked is None else checked
        indexes: object = questionary.checkbox(
            prompt,
            choices=[
                Choice(title=label(choice), value=i, checked=choice in ticked)
                for i, choice in enumerate(choices)
            ],
            style=PROMPT_STYLE,
        ).ask()
        if not isinstance(indexes, list):
            raise KeyboardInterrupt
        chosen = sorted(i for i in indexes if isinstance(i, int))  # pyright: ignore[reportUnknownVariableType]
        return [choices[i] for i in chosen]

    def confirm(self, prompt: str, default: bool) -> bool:
        """Ask a yes/no question.

        Raises
        ------
        KeyboardInterrupt
            If the user cancels.
        """
        answer: object = questionary.confirm(prompt, default=default, style=PROMPT_STYLE).ask()
        if not isinstance(answer, bool):
            raise KeyboardInterrupt
        return answer

    def text(
        self,
        prompt: str,
        default: str = "",
        validate: Validator | None = None,
        suggestions: Sequence[str] = (),
    ) -> str:
        """Ask for free text, asking again until it is valid.

        Parameters
        ----------
        prompt : str
            The question.
        default : str, optional
            Text the input starts with.
        validate : Validator | None, optional
            Raises ``ValueError`` for an invalid answer; its message is shown
            under the input until the answer changes.
        suggestions : Sequence[str], optional
            Values listed under the input while they match what is typed.
            Any other value can still be entered.

        Returns
        -------
        str
            The answer.

        Raises
        ------
        KeyboardInterrupt
            If the user cancels.
        """

        def _verdict(value: str) -> bool | str:
            if validate is None:
                return True
            try:
                _ = validate(value)
            except ValueError as error:
                return str(error)
            return True

        answer: object
        if suggestions:
            answer = suggest_text(
                prompt, suggestions, default=default, validate=_verdict, style=PROMPT_STYLE
            )
        else:
            answer = questionary.text(
                prompt, default=default, validate=_verdict, style=PROMPT_STYLE
            ).ask()
        if not isinstance(answer, str):
            raise KeyboardInterrupt
        return answer
