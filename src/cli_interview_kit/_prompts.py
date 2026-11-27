"""Prompt loops for answers made of several items, and ``KEY=VALUE`` parsing."""

from __future__ import annotations

from collections.abc import Sequence

from cli_interview_kit.console import Console
from cli_interview_kit.errors import CliError
from cli_interview_kit.validators import Validator, all_of, non_empty


def parse_kv(items: Sequence[str] | None, flag: str) -> dict[str, str]:
    """Parse repeated ``KEY=VALUE`` flag values into a dict.

    Raises
    ------
    CliError
        If a value has no ``=`` or an empty key.
    """
    result: dict[str, str] = {}
    for item in items or ():
        key, separator, value = item.partition("=")
        if not separator or not key:
            raise CliError(f"{flag} expects KEY=VALUE; got '{item}'.")
        result[key] = value
    return result


def prompt_list(
    console: Console,
    label: str,
    *,
    required: bool,
    validate: Validator | None,
    suggestions: Sequence[str],
) -> list[str]:
    """Ask for items one at a time; each must be non-blank and valid."""
    result: list[str] = []
    while _keep_adding(console, label, required, len(result)):
        result.append(
            console.text(
                f"{label}: value",
                validate=all_of(non_empty, validate),
                suggestions=[s for s in suggestions if s not in result],
            )
        )
    return result


def prompt_pairs(
    console: Console,
    label: str,
    *,
    required: bool,
    validate: Validator | None,
) -> dict[str, str]:
    """Ask for name/value pairs one at a time; names are non-blank and new."""
    result: dict[str, str] = {}

    def _new_name(name: str) -> str:
        if name in result:
            raise ValueError(f"'{name}' is already set.")
        return name

    while _keep_adding(console, label, required, len(result)):
        name = console.text(f"{label}: name", validate=all_of(non_empty, _new_name))
        result[name] = console.text(f"{label}: value", validate=all_of(non_empty, validate))
    return result


def _keep_adding(console: Console, label: str, required: bool, collected: int) -> bool:
    """Return whether to ask for another item.

    A required collection asks for its first item straight away, so it can
    never end up empty.
    """
    if collected:
        return console.confirm("Add another?", default=False)
    return required or console.confirm(f"Add {_with_article(label)}?", default=False)


def _with_article(label: str) -> str:
    """Return ``label`` with its indefinite article, e.g. ``an upsert key``."""
    return f"{'an' if label[:1].lower() in 'aeiou' else 'a'} {label}"
