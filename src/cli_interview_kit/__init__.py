"""Build command-line apps whose prompts are declared once.

Declare each command as a ``Command``: its plain options, an ``Interview``
of questions and consents, and a run function. Hand the commands to an
``App``, which derives the flags, the terminal interview, the behaviour
when nobody can be asked, and the ``--questions`` document an AI assistant
interviews a user from.

Everything public is importable from this package; the modules whose names
start with an underscore are internal.
"""

from importlib.metadata import version as _version

from cli_interview_kit._prompts import parse_kv
from cli_interview_kit.app import App
from cli_interview_kit.command import Command, Invocation, Option
from cli_interview_kit.console import Console
from cli_interview_kit.errors import CliError, DeclarationError
from cli_interview_kit.interaction import Consent, Interaction
from cli_interview_kit.interview import (
    ChoiceSource,
    Condition,
    CustomKind,
    DefaultSource,
    Facts,
    Interview,
    Question,
    QuestionKind,
    when,
)
from cli_interview_kit.validators import Validator, byte_size, non_empty, whole_number

__version__ = _version("cli-interview-kit")

__all__ = [
    "App",
    "ChoiceSource",
    "CliError",
    "Command",
    "Condition",
    "Consent",
    "Console",
    "CustomKind",
    "DeclarationError",
    "DefaultSource",
    "Facts",
    "Interaction",
    "Interview",
    "Invocation",
    "Option",
    "Question",
    "QuestionKind",
    "Validator",
    "__version__",
    "byte_size",
    "non_empty",
    "parse_kv",
    "when",
    "whole_number",
]
