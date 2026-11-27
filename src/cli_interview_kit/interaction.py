"""How a run may interact with its user: answers and consents.

Each run resolves one ``Interaction`` from ``--yes`` and whether stdin is a
terminal, and every question and consent follows it:

- **Answers** (what to create, which environment): asked in a terminal.
  When nobody can be asked, each takes its default, and one with no safe
  default fails the run, naming its flag.
- **Consents** (delete something, deploy to production, overwrite files):
  ``--yes`` gives them. Without it they are asked in a terminal; when nobody
  can be asked, a consent with a safe default takes it and any other fails
  the run, asking for ``--yes``. A piped stdin never consents by itself.
"""

from __future__ import annotations

import sys

from pydantic import Field

from cli_interview_kit._model import FrozenModel
from cli_interview_kit.console import Console
from cli_interview_kit.errors import CliError, DeclarationError


class Interaction(FrozenModel):
    """Whether a run may prompt, and whether it has blanket consent.

    Attributes
    ----------
    can_prompt : bool
        Stdin is a terminal and ``--yes`` was not given.
    consent : bool
        ``--yes`` was given: every declared consent is granted.
    declared : frozenset[str]
        The keys of the consents the running command declares; only these
        can be asked for.
    """

    can_prompt: bool
    consent: bool
    declared: frozenset[str] = Field(default_factory=frozenset)

    @classmethod
    def resolve(cls, yes: bool, declared: frozenset[str] = frozenset()) -> Interaction:
        """Return the interaction for a run, from ``--yes`` and the terminal."""
        return cls(can_prompt=sys.stdin.isatty() and not yes, consent=yes, declared=declared)


class Consent(FrozenModel):
    """A confirmation a command may need before it acts.

    Declared on the command's ``Interview`` so ``--questions`` lists it: an
    assistant describes it to the user first and passes ``--yes`` only once
    they agree.

    Attributes
    ----------
    key : str
        Stable identifier.
    when : str
        When the command asks for it and what it allows, for ``--questions``.
    safe_default : bool | None
        The answer when nobody can be asked and ``--yes`` was not given, and
        the prompt's default. ``None`` means only ``--yes`` or a person can
        give it.
    """

    key: str = Field(min_length=1)
    when: str = Field(min_length=1)
    safe_default: bool | None = None

    def ask(self, console: Console, interaction: Interaction, message: str) -> bool:
        """Return whether the run has this consent.

        Parameters
        ----------
        console : Console
            Where to ask.
        interaction : Interaction
            The run's interaction.
        message : str
            The question to ask, saying exactly what will happen.

        Raises
        ------
        DeclarationError
            If the running command does not declare this consent.
        CliError
            If nobody can be asked, ``--yes`` was not given, and the consent
            has no safe default.
        """
        if self.key not in interaction.declared:
            raise DeclarationError(
                f"Consent '{self.key}' is not declared on the running command's "
                "Interview, so --questions cannot list it."
            )
        if interaction.consent:
            return True
        if interaction.can_prompt:
            return console.confirm(message, default=bool(self.safe_default))
        if self.safe_default is not None:
            return self.safe_default
        raise CliError(f"{message} This needs consent: rerun with --yes.")
