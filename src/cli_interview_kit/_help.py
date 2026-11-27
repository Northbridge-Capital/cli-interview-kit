"""Rich-rendered ``--help`` and usage output for every app.

The help is built from the parser's own model (its action groups, each
action's flags, metavar, choices and help, and a subparsers action's
commands) and rendered as a definition list: each flag on its own line with
its help indented beneath it. Flag names vary a lot in length, and a
two-column table would either wrap the long ones away from their metavar or
squeeze every other row's help.

The usage line itself comes from ``argparse.HelpFormatter``, which already
wraps brackets and mutually exclusive groups correctly; past
``_SUMMARIZE_THRESHOLD`` flags it is shortened to ``[OPTIONS]``.

argparse exposes this model only through underscored attributes. They have
been stable for many Python versions, and CI runs the help tests on the
oldest and newest supported Python. All text is printed literally, never
read as rich markup.
"""

from __future__ import annotations

import argparse

from rich.console import Console as RichConsole
from rich.padding import Padding
from rich.text import Text

_SUMMARIZE_THRESHOLD = 8
"""Above this many flags, the usage line shows ``[OPTIONS]`` instead."""


def usage_line(parser: argparse.ArgumentParser) -> str:
    """Return the parser's ``usage: ...`` line."""
    actions = parser._actions  # pyright: ignore[reportPrivateUsage]
    flags = [a for a in actions if a.option_strings and a.option_strings != ["-h", "--help"]]
    if len(flags) <= _SUMMARIZE_THRESHOLD:
        formatter = argparse.HelpFormatter(prog=parser.prog)
        formatter.add_usage(
            parser.usage,
            actions,
            parser._mutually_exclusive_groups,  # pyright: ignore[reportPrivateUsage]
        )
        return formatter.format_help().strip()
    positionals = [_metavar(a) for a in actions if not a.option_strings]
    return " ".join([f"usage: {parser.prog}", "[-h]", "[OPTIONS]", *positionals])


def print_usage(parser: argparse.ArgumentParser) -> None:
    """Print the usage line to stderr, as argparse does on a usage error."""
    RichConsole(stderr=True).print(Text(usage_line(parser)))


def print_help(parser: argparse.ArgumentParser) -> None:
    """Print the full help: usage, description, then every group of flags."""
    console = RichConsole()
    console.print(Text(usage_line(parser)))
    if parser.description:
        console.print()
        console.print(Text(parser.description))
    for group in parser._action_groups:  # pyright: ignore[reportPrivateUsage]
        _print_group(console, group)


def _print_group(console: RichConsole, group: argparse._ArgumentGroup) -> None:  # pyright: ignore[reportPrivateUsage]
    """Print one group's title, then each flag with its help beneath it."""
    title = group.title or ""
    rows: list[tuple[str, str]] = []
    for action in group._group_actions:  # pyright: ignore[reportPrivateUsage]
        if action.help == argparse.SUPPRESS:
            continue
        if isinstance(action, argparse._SubParsersAction):  # pyright: ignore[reportPrivateUsage]
            title = "commands"
            choices: list[argparse.Action] = action._choices_actions  # pyright: ignore[reportPrivateUsage, reportUnknownMemberType]
            rows.extend((choice.dest, choice.help or "") for choice in choices)
            continue
        rows.append((_invocation(action), action.help or ""))
    if not rows:
        return
    console.print()
    console.print(Text(f"{title}:", style="bold cyan"))
    for invocation, help_text in rows:
        console.print(Text(f"  {invocation}", style="cyan"))
        if help_text:
            console.print(Padding(Text(help_text), (0, 0, 0, 4), expand=False))


def _invocation(action: argparse.Action) -> str:
    """Return every flag of an action with its metavar, e.g. ``--yes, --no-yes``."""
    if not action.option_strings:
        return _metavar(action)
    if action.nargs == 0:
        return ", ".join(action.option_strings)
    return f"{', '.join(action.option_strings)} {_metavar(action)}"


def _metavar(action: argparse.Action) -> str:
    """Return how an action's value is shown: its metavar, choices or name."""
    if isinstance(action.metavar, str):
        return action.metavar
    if action.choices:
        return "{" + ",".join(str(c) for c in action.choices) + "}"
    return action.dest if not action.option_strings else action.dest.upper()
