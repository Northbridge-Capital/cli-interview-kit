"""Commands declared as data: options, an interview, subcommands and a run.

A ``Command`` is everything needed to expose one command: its help, the
plain options that choose what it does (``--check``, ``--dry-run``,
positional arguments), the ``Interview`` it answers, any subcommands, and the
function that runs it. ``App`` builds the argument parser from these
declarations, so no command writes argparse code.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import Field, model_validator

from cli_interview_kit._model import FrozenModel
from cli_interview_kit.console import Console
from cli_interview_kit.interaction import Interaction
from cli_interview_kit.interview import Interview

RESERVED_NAMES = frozenset({"help", "debug", "yes", "questions"})
"""Names no option or question may take.

``--help``, ``--yes`` and ``--questions`` are a command's own flags, and
``debug`` is where the app's ``--debug`` lands in the parsed arguments every
command shares. ``--version`` exists only on the app and stores nothing, so
``version`` is free.
"""


class Option(FrozenModel):
    """A plain option or positional argument; not an interview question.

    Options choose what a command does (``--check``, ``--dry-run``) or name
    what it acts on. Anything the user could be asked belongs in the
    interview instead.

    Attributes
    ----------
    dest : str
        The name the value is read by, in snake_case; the flag is ``--``
        plus the name with dashes.
    help : str
        Help text.
    kind : Literal["switch", "value", "append", "positional"]
        ``switch`` is an on/off flag; ``value`` takes one value; ``append``
        is repeatable; ``positional`` is an argument.
    metavar : str | None
        Value placeholder in help.
    choices : tuple[str, ...]
        Allowed values.
    nargs : str | None
        A positional's arity, e.g. ``"*"``.
    convert : Callable[[str], Any] | None
        Converts and checks a value; raising ``ValueError`` is a usage error.
    exclusive : str | None
        Options sharing this name are mutually exclusive.
    """

    dest: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    help: str = Field(min_length=1)
    kind: Literal["switch", "value", "append", "positional"] = "value"
    metavar: str | None = None
    choices: tuple[str, ...] = ()
    nargs: Literal["?", "*", "+"] | None = None
    convert: Callable[[str], Any] | None = None
    exclusive: str | None = None

    @model_validator(mode="after")
    def _check_kind(self) -> Option:
        """Reject settings that do not fit the option's kind."""
        if self.nargs is not None and self.kind != "positional":
            raise ValueError(f"{self.flag}: only a positional takes nargs.")
        if self.kind == "switch" and (self.choices or self.convert or self.metavar):
            raise ValueError(f"{self.flag}: a switch takes no value settings.")
        if self.kind == "positional" and self.exclusive is not None:
            raise ValueError(f"{self.flag}: a positional cannot be mutually exclusive.")
        return self

    @property
    def flag(self) -> str:
        """The option's flag, or its name for a positional."""
        if self.kind == "positional":
            return self.dest
        return "--" + self.dest.replace("_", "-")

    def describe(self) -> dict[str, Any]:
        """Return the option as ``--questions`` lists it."""
        return {"flag": self.flag, "kind": self.kind, "help": self.help}


class Invocation(FrozenModel):
    """What a command's run function receives.

    Attributes
    ----------
    console : Console
        Output and prompts.
    interaction : Interaction
        Whether the run may prompt and has consent; pass it to
        ``Consent.ask``.
    answers : dict[str, Any]
        The answers of the questions that applied, by key.
    options : dict[str, Any]
        The options' values, by ``dest``.
    """

    console: Console
    interaction: Interaction
    answers: dict[str, Any]
    options: dict[str, Any]


class Command(FrozenModel):
    """One command.

    Attributes
    ----------
    name : str
        The command's name on the command line.
    help : str
        One-line help.
    options : tuple[Option, ...]
        Plain options and positionals.
    interview : Interview
        Questions and consents. A command with any gets ``--yes`` and
        ``--questions``.
    run : Callable[[Invocation], None] | None
        What the command does; ``None`` for a group of subcommands.
    subcommands : tuple[Command, ...]
        Nested commands.
    """

    name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    help: str = Field(min_length=1)
    options: tuple[Option, ...] = ()
    interview: Interview = Interview()
    run: Callable[[Invocation], None] | None = None
    subcommands: tuple[Command, ...] = ()

    @model_validator(mode="after")
    def _check_names(self) -> Command:
        """Reject a command that runs nothing, and clashing names."""
        if self.run is None and not self.subcommands:
            raise ValueError(f"Command '{self.name}' has neither a run nor subcommands.")
        names = [option.dest for option in self.options]
        names += [question.key for question in self.interview.questions]
        clashes = sorted({n for n in names if names.count(n) > 1} | (set(names) & RESERVED_NAMES))
        if clashes:
            raise ValueError(
                f"Command '{self.name}' uses {', '.join(clashes)} more than once or as a "
                f"reserved name ({', '.join(sorted(RESERVED_NAMES))})."
            )
        commands = [command.name for command in self.subcommands]
        if duplicated := sorted({n for n in commands if commands.count(n) > 1}):
            raise ValueError(f"Command '{self.name}' has duplicate subcommands: {duplicated}.")
        return self

    @property
    def interactive(self) -> bool:
        """Whether the command has questions or consents."""
        return bool(self.interview.questions or self.interview.consents)
