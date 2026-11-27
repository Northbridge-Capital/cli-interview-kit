"""The app: one parser from the command declarations, one error policy.

``App.main`` builds the argument parser from the declared commands, then for
the selected command either prints ``--questions`` or resolves the
``Interaction``, answers the interview and runs the command. Every failure
leaves through one policy:

- ``CliError`` and the app's ``expected_errors``: the message, exit 1;
- Ctrl-C: ``Aborted.``, exit 130;
- anything else: one line naming the exception, exit 1, or the traceback
  with ``--debug``;
- a usage error (an unknown flag, a bad choice): argparse's message, exit 2.

Every app gets ``--version`` and ``--debug``; every command with questions
or consents gets ``--yes`` and ``--questions``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any, NoReturn

from pydantic import Field, model_validator

from cli_interview_kit._help import print_help, print_usage
from cli_interview_kit._model import FrozenModel
from cli_interview_kit.command import Command, Invocation, Option
from cli_interview_kit.console import Console
from cli_interview_kit.errors import CliError
from cli_interview_kit.interaction import Interaction

_COMMAND = "_cik_command"
_PATH = "_cik_path"


class _ArgumentParser(argparse.ArgumentParser):
    """An ``ArgumentParser`` whose help and usage render through rich."""

    # ``add_subparsers()`` gives every subparser its parent's class, so this one subclass covers
    # every command.

    def print_help(self, file: object = None) -> None:
        """Print the help through rich, ignoring ``file``."""
        _ = file
        print_help(self)

    def print_usage(self, file: object = None) -> None:
        """Print the usage line through rich, ignoring ``file``."""
        _ = file
        print_usage(self)

    def error(self, message: str) -> NoReturn:
        """Print the usage and the message, then exit with status 2."""
        print_usage(self)
        Console().error(message)
        self.exit(2)


class App(FrozenModel):
    """A command-line app built from command declarations.

    Attributes
    ----------
    name
        Program name.
    description
        Top-level help.
    version
        What ``--version`` prints after the name.
    commands
        The top-level commands.
    expected_errors
        Further exception types whose message is reported like a
        ``CliError``, for failures the app's own libraries raise.

    Methods
    -------
    main
        Run the command ``argv`` selects and return the exit code.
    build_parser
        Return the argument parser for every declared command.
    """

    name: str = Field(min_length=1)
    description: str
    version: str = Field(min_length=1)
    commands: tuple[Command, ...] = Field(min_length=1)
    expected_errors: tuple[type[Exception], ...] = ()

    @model_validator(mode="after")
    def _check_commands(self) -> App:
        """Reject duplicate top-level command names."""
        names = [command.name for command in self.commands]
        if duplicated := sorted({n for n in names if names.count(n) > 1}):
            raise ValueError(f"App '{self.name}' has duplicate commands: {duplicated}.")
        return self

    def main(self, argv: Sequence[str] | None = None) -> int:
        """Run the command ``argv`` selects and return the exit code.

        Parameters
        ----------
        argv
            The arguments after the program name; ``sys.argv[1:]`` if omitted.

        Returns
        -------
        The exit code: 0 on success, 1 on a failure, 130 when interrupted.

        Raises
        ------
        SystemExit
            A usage error (an unknown flag, a bad choice) exits with status 2, as argparse does.
        """
        console = Console()
        args = self.build_parser().parse_args(argv)
        try:
            self._dispatch(console, vars(args))
        except CliError as error:
            console.error(str(error))
            return 1
        except KeyboardInterrupt:
            console.error("Aborted.")
            return 130
        except Exception as error:
            if args.debug:
                raise
            if isinstance(error, self.expected_errors):
                console.error(str(error))
                return 1
            console.error(
                f"Unexpected {type(error).__name__}: {error}. Rerun with "
                f"`{self.name} --debug ...` for the traceback."
            )
            return 1
        return 0

    def build_parser(self) -> argparse.ArgumentParser:
        """Return the argument parser for every declared command.

        Returns
        -------
        The parser, with ``--version``, ``--debug`` and one subparser per command.
        """
        parser = _ArgumentParser(prog=self.name, description=self.description)
        _ = parser.add_argument(
            "--version", action="version", version=f"{self.name} {self.version}"
        )
        _ = parser.add_argument(
            "--debug",
            action="store_true",
            help="Show the full traceback when a command fails unexpectedly.",
        )
        _add_commands(parser, self.commands, (self.name,), required=True)
        return parser

    def _dispatch(self, console: Console, values: dict[str, Any]) -> None:
        """Print the selected command's ``--questions``, or answer its interview and run it."""
        command: Command = values[_COMMAND]
        command_line = " ".join(values[_PATH])
        options = {option.dest: values.get(option.dest) for option in command.options}
        if values.get("questions"):
            document = command.interview.document(
                command_line, [option.describe() for option in command.options]
            )
            _ = sys.stdout.write(json.dumps(document, indent=2) + "\n")
            return
        interaction = Interaction.resolve(
            bool(values.get("yes")), declared=command.interview.consent_keys
        )
        answers = command.interview.run(console, interaction, values, options)
        # A command without a run has subcommands, and argparse requires one.
        assert command.run is not None  # noqa: S101 -- see the comment above
        command.run(
            Invocation(console=console, interaction=interaction, answers=answers, options=options)
        )


def _add_commands(
    parser: argparse.ArgumentParser,
    commands: Sequence[Command],
    path: tuple[str, ...],
    *,
    required: bool,
) -> None:
    """Add a subparser for each command, recursively."""
    subparsers = parser.add_subparsers(dest=f"_cik_{len(path)}", required=required)
    for command in commands:
        sub = subparsers.add_parser(command.name, help=command.help, description=command.help)
        command_path = (*path, command.name)
        sub.set_defaults(**{_COMMAND: command, _PATH: command_path})
        _add_options(sub, command.options)
        if command.interactive:
            command.interview.add_arguments(sub)
            _add_interaction_flags(sub)
        if command.subcommands:
            _add_commands(sub, command.subcommands, command_path, required=command.run is None)


def _add_options(parser: argparse.ArgumentParser, options: Sequence[Option]) -> None:
    """Add a command's plain options and positionals."""
    exclusive: dict[str, argparse._MutuallyExclusiveGroup] = {}  # pyright: ignore[reportPrivateUsage]
    for option in options:
        target: argparse._ActionsContainer = parser  # pyright: ignore[reportPrivateUsage]
        if option.exclusive is not None:
            if option.exclusive not in exclusive:
                exclusive[option.exclusive] = parser.add_mutually_exclusive_group()
            target = exclusive[option.exclusive]
        kwargs: dict[str, Any] = {"help": option.help}
        if option.metavar:
            kwargs["metavar"] = option.metavar
        if option.choices:
            kwargs["choices"] = list(option.choices)
        if option.convert is not None:
            kwargs["type"] = option.convert
        if option.kind == "positional":
            if option.nargs:
                kwargs["nargs"] = option.nargs
            _ = target.add_argument(option.dest, **kwargs)
            continue
        if option.kind == "switch":
            kwargs["action"] = "store_true"
        elif option.kind == "append":
            kwargs["action"] = "append"
        _ = target.add_argument(option.flag, dest=option.dest, **kwargs)


def _add_interaction_flags(parser: argparse.ArgumentParser) -> None:
    """Add ``--yes`` and ``--questions``."""
    group = parser.add_argument_group("interaction")
    _ = group.add_argument(
        "--yes",
        action="store_true",
        help=(
            "Never prompt: every unanswered question takes its default (one "
            "with no safe default fails, naming its flag) and every consent "
            "the command asks for is given."
        ),
    )
    _ = group.add_argument(
        "--questions",
        action="store_true",
        help=(
            "Print the command's questions, consents and options as JSON and "
            "exit, so an AI assistant can ask them and run the command with "
            "--yes and the flags."
        ),
    )
