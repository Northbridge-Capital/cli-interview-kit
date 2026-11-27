"""Answer validators: functions that return the value or raise ``ValueError``.

A validator receives the answer as typed and returns it, or raises
``ValueError`` with a message for the user. At a prompt the message is shown
under the input and the question is asked again; a flag value that fails
validation fails the run, naming the flag. Any function with this shape is a
validator; these are the built-in ones.
"""

from __future__ import annotations

import re
from collections.abc import Callable

Validator = Callable[[str], str]
"""``(value) -> value``, raising ``ValueError`` with a user-facing message."""

_BYTE_SIZE = re.compile(r"\d+[kmgt]?b?")


def non_empty(value: str) -> str:
    """Reject a blank answer.

    Parameters
    ----------
    value
        The answer as typed.

    Returns
    -------
    The answer, unchanged.

    Raises
    ------
    ValueError
        The answer is blank.
    """
    if not value.strip():
        raise ValueError("A value is required.")
    return value


def whole_number(value: str) -> str:
    """Accept a whole number, or a blank answer.

    Parameters
    ----------
    value
        The answer as typed.

    Returns
    -------
    The answer, unchanged.

    Raises
    ------
    ValueError
        The answer is neither blank nor a whole number.
    """
    stripped = value.strip()
    if stripped and not stripped.removeprefix("-").isdigit():
        raise ValueError("Enter a whole number, or leave it blank.")
    return value


def byte_size(value: str) -> str:
    """Accept a size such as ``512m`` or ``1g``, or a blank answer.

    Parameters
    ----------
    value
        The answer as typed.

    Returns
    -------
    The answer, unchanged.

    Raises
    ------
    ValueError
        The answer is neither blank nor a size.
    """
    stripped = value.strip()
    if stripped and not _BYTE_SIZE.fullmatch(stripped.lower()):
        raise ValueError("Enter a size such as 512m or 1g, or leave it blank.")
    return value


def all_of(*validators: Validator | None) -> Validator:
    """Return a validator applying each given one in order, skipping ``None``."""

    def _validate(value: str) -> str:
        for validator in validators:
            if validator is not None:
                _ = validator(value)
        return value

    return _validate
