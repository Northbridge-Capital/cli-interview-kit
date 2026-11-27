"""Interviews declared as data: questions, consents, and the engine answering them.

A command declares an ``Interview``: its questions in order, the consents it
may ask for, and where dynamic choices, defaults and facts come from. Every
way of answering is derived from that one declaration:

- one flag per question, so the command runs from flags alone;
- a terminal interview that asks each applicable question its flag did not
  answer, validating every answer at its prompt;
- defaults, or an error naming the flag for an answer with no safe default,
  when nobody can be asked (see ``cli_interview_kit.interaction``);
- the ``--questions`` JSON document, from which an AI assistant interviews
  the user in its own session and then runs the command with ``--yes`` and
  the flags.

A question's flag is derived from its key (``max_workers`` is
``--max-workers``). Declarations are checked when they are built: a
question whose settings do not fit its kind, or an interview referring to a
source, kind or group it does not declare, raises pydantic's
``ValidationError`` at import time rather than failing a user's run.
"""

from __future__ import annotations

import argparse
import string
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

from pydantic import Field, field_serializer, model_validator

from cli_interview_kit._model import FrozenModel
from cli_interview_kit._prompts import parse_kv, prompt_list, prompt_pairs
from cli_interview_kit.console import Console
from cli_interview_kit.errors import CliError
from cli_interview_kit.interaction import Consent, Interaction
from cli_interview_kit.validators import Validator, all_of, non_empty, whole_number

QuestionKind = Literal[
    "text", "select", "multiselect", "confirm", "int", "list", "pairs", "per_item", "custom"
]
"""How a question is answered; ``HOW_TO_ANSWER`` gives each kind's flag form."""

HOW_TO_ANSWER: dict[str, str] = {
    "text": "--flag VALUE",
    "select": "--flag CHOICE",
    "multiselect": "repeat --flag CHOICE; omitted means every choice",
    "confirm": "--flag or --no-flag",
    "int": "--flag NUMBER",
    "list": "repeat --flag VALUE",
    "pairs": "repeat --flag KEY=VALUE",
    "per_item": "repeat --flag ITEM=VALUE, one per item of items_from",
    "custom": "see the question's custom kind under custom_kinds",
}
"""Each kind's flag form, printed with ``--questions``."""

PROCEDURE: tuple[str, ...] = (
    "You are running this command for a user. Ask them the questions below, "
    "then run the command with their answers; do not answer for them.",
    "Go through the questions in order, a few at a time, grouped by section, "
    "using whatever way of asking the user you have.",
    "Skip a question whose when_all/when_any does not hold for the answers, "
    "options and facts so far.",
    "Offer a select or multiselect question's choices (choices, choices_now, "
    "with their labels) as options and a confirm question as yes/no. For a "
    "free-text question, offer its suggestions_now as options and accept any "
    "other value the user gives.",
    "Ask each applicable group once, as whether to keep its questions' "
    "defaults; ask the group's questions one by one only if the user wants a "
    "change. Do not bundle any other questions.",
    "A required question must be answered. Do not ask a prompted: false "
    "question unless the user brings it up.",
    "Before running, describe each consent that can apply and pass --yes only "
    "once the user has agreed to all of them. Consent does not carry over to "
    "another run.",
    "Run `command` with one flag per answer, as how_to_answer shows; leave "
    "out the flag of an answer that kept its default.",
    "If the run rejects a value, ask that question again with the error, then rerun.",
)
"""How an assistant runs a command for a user, printed with ``--questions``.

The procedure travels with the document, so any assistant that can run a
shell command can follow it, whichever tool it is.
"""

RULES: tuple[str, ...] = (
    "Passing a flag for a question that does not apply fails the run.",
    "Without its flag a question takes its default under --yes; a required "
    "question has no safe default.",
    "A default may reference earlier answers ({name}) and, for per_item, {item}.",
    "choices_from/items_from/suggestions_from name a dynamic source; "
    "choices_now, items_now and suggestions_now list its current values when "
    "it is local, otherwise the CLI checks the answer when it runs.",
    "prompted false: a setting the terminal interview never asks.",
    "consents: confirmations the run may need, given by --yes.",
)
"""What the fields of the ``--questions`` document mean."""

QUESTIONS_FORMAT_VERSION = 1
"""The ``version`` of the ``--questions`` document.

Raised when a field changes meaning or is removed, so an assistant reading
the document can tell; adding a field does not raise it.
"""

ChoiceSource = Callable[[Mapping[str, Any], str | None], Sequence[str]]
"""Dynamic choices: ``(answers so far, item or None) -> choices``."""

DefaultSource = Callable[[Mapping[str, Any], str | None], str | None]
"""A dynamic default: ``(answers so far, item or None) -> default``."""

Facts = Callable[[Mapping[str, Any]], Mapping[str, Any]]
"""Facts derived from the answers and options so far, for conditions."""

_COLLECTIONS = frozenset({"multiselect", "list", "pairs", "per_item", "custom"})
"""Kinds answered by a repeated flag."""

_TAKES_CHOICES = frozenset({"select", "multiselect", "per_item"})
_TAKES_SUGGESTIONS = frozenset({"text", "list", "per_item"})
_TAKES_VALIDATOR = frozenset({"text", "list", "pairs", "per_item"})
_TAKES_DEFAULT_FROM = frozenset({"text", "select", "per_item"})
_TEXT_ANSWERS = frozenset({"text", "select"})
"""Kinds whose answer is one string, so a default may reference it."""


class Condition(FrozenModel):
    """An answer, option or fact a question depends on.

    Attributes
    ----------
    key
        An earlier question's key, an option's ``dest``, or a fact.
    is_in
        The values that satisfy the condition.

    Methods
    -------
    holds
        Return whether the context's value is one of ``is_in``.
    describe
        Return the condition as text.
    """

    key: str
    is_in: tuple[str | bool, ...] = Field(min_length=1)

    def holds(self, context: Mapping[str, Any]) -> bool:
        """Return whether the context's value is one of ``is_in``.

        Parameters
        ----------
        context
            The values conditions see: options, answers and facts, by key.

        Returns
        -------
        Whether the condition holds.
        """
        return self.key in context and context[self.key] in self.is_in

    def describe(self) -> str:
        """Return the condition as text, e.g. ``source_type is files``.

        Returns
        -------
        The condition as text.
        """
        values = " or ".join(str(value).lower() for value in self.is_in)
        return f"{self.key} is {values}"


def when(key: str, *values: str | bool) -> Condition:
    """Return a condition: ``key`` is one of ``values``.

    Parameters
    ----------
    key
        An earlier question's key, an option's ``dest``, or a fact.
    values
        The values that satisfy the condition.

    Returns
    -------
    The condition.
    """
    return Condition(key=key, is_in=values)


class Question(FrozenModel):
    """One interview question.

    Attributes
    ----------
    key
        Answer key, in snake_case; the flag is ``--`` plus the key with dashes.
    section
        Interview section and help group.
    kind
        How the question is answered.
    prompt
        Terminal prompt. For ``list`` and ``pairs`` it names one item; for
        ``per_item`` it may use ``{item}``.
    help
        What the answer means; the flag's help.
    choices
        Fixed choices of a ``select``, ``multiselect`` or ``per_item`` question.
    choices_from
        Dynamic choices from the interview's ``choices`` source of that name,
        after any fixed ones (per item for ``per_item``).
    flag_choices_from
        Further values the flag accepts that the prompt does not offer.
    items_from
        The ``choices`` source listing a ``per_item`` question's items.
    labels
        How choices are shown.
    default
        The answer when nobody is asked, and the prompt's starting value. A
        string may reference earlier text or select answers (``{name}``) and,
        for ``per_item``, ``{item}``.
    default_from
        A dynamic default from the interview's ``defaults`` source instead.
    required
        The answer has no safe default: a run that cannot prompt fails
        without the flag.
    validator
        Checks every answer, at the prompt and from the flag.
    metavar
        The flag's value placeholder in help.
    prompted
        Whether the terminal interview asks it; ``False`` for settings only
        set by flag.
    custom
        The custom kind of a ``custom`` question.
    suggestions_from
        A ``choices`` source of suggested values for a free-text answer:
        listed under the input in a terminal and by ``--questions``, never
        enforced.
    group
        A group from ``Interview.groups`` an assistant may ask as one
        bundled question ("keep these defaults?").
    when_all
        Asked only when every condition holds.
    when_any
        Asked only when at least one condition holds, if any are declared.
    flag
        The flag answering this question.

    Methods
    -------
    applies
        Return whether the question is asked, given the context so far.
    describe_conditions
        Return when the question applies, as text.
    placeholders
        Return the ``{name}`` placeholders of a string default.
    """

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    section: str = Field(min_length=1)
    kind: QuestionKind
    prompt: str = Field(min_length=1)
    help: str = Field(min_length=1)
    choices: tuple[str, ...] = ()
    choices_from: str | None = None
    flag_choices_from: str | None = None
    items_from: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    default: str | bool | int | None = None
    default_from: str | None = None
    required: bool = False
    validator: Validator | None = None
    metavar: str | None = None
    prompted: bool = True
    custom: str | None = None
    suggestions_from: str | None = None
    group: str | None = None
    when_all: tuple[Condition, ...] = ()
    when_any: tuple[Condition, ...] = ()

    @property
    def flag(self) -> str:
        """The flag answering this question."""
        return "--" + self.key.replace("_", "-")

    @field_serializer("validator")
    def _validator_name(self, validator: Validator | None) -> str | None:
        """Serialize a validator as its function name."""
        return None if validator is None else getattr(validator, "__name__", "validator")

    @model_validator(mode="after")
    def _check_kind(self) -> Question:
        """Reject settings that do not fit the question's kind."""
        kind = self.kind
        rules: list[tuple[bool, str]] = [
            (
                bool(self.choices or self.choices_from) and kind not in _TAKES_CHOICES,
                "only select, multiselect and per_item questions take choices",
            ),
            (
                kind in ("select", "multiselect") and not (self.choices or self.choices_from),
                f"a {kind} question needs choices or choices_from",
            ),
            (
                self.flag_choices_from is not None and kind not in ("select", "multiselect"),
                "only select and multiselect questions take flag_choices_from",
            ),
            (
                (kind == "per_item") != (self.items_from is not None),
                "items_from is required on a per_item question and allowed only there",
            ),
            (
                (kind == "custom") != (self.custom is not None),
                "custom is required on a custom question and allowed only there",
            ),
            (
                self.suggestions_from is not None and kind not in _TAKES_SUGGESTIONS,
                "only text, list and per_item questions take suggestions_from",
            ),
            (
                self.validator is not None and kind not in _TAKES_VALIDATOR,
                "only text, list, pairs and per_item questions take a validator",
            ),
            (
                self.default_from is not None and kind not in _TAKES_DEFAULT_FROM,
                "only text, select and per_item questions take default_from",
            ),
            (
                self.default is not None and self.default_from is not None,
                "set default or default_from, not both",
            ),
            (
                not _default_fits(kind, self.default),
                f"a {kind} question cannot default to {self.default!r}",
            ),
            (
                self.required and (self.default is not None or self.default_from is not None),
                "a required question has no safe default; drop required or the default",
            ),
            (self.required and kind == "confirm", "a confirm question cannot be required"),
            (self.required and self.group is not None, "a required question cannot be grouped"),
            (self.required and not self.prompted, "a required question must be prompted"),
            (
                kind == "per_item" and any(name != "item" for name in _fields(self.prompt)),
                "a per_item prompt may only use the {item} placeholder",
            ),
        ]
        for broken, message in rules:
            if broken:
                raise ValueError(f"{self.flag}: {message}.")
        return self

    def applies(self, context: Mapping[str, Any]) -> bool:
        """Return whether the question is asked, given the context so far.

        Parameters
        ----------
        context
            The values conditions see: options, answers and facts, by key.

        Returns
        -------
        Whether the question is asked.
        """
        return all(c.holds(context) for c in self.when_all) and (
            not self.when_any or any(c.holds(context) for c in self.when_any)
        )

    def describe_conditions(self) -> str:
        """Return when the question applies, as text.

        Returns
        -------
        The conditions, joined with "and" and "or".
        """
        parts = [c.describe() for c in self.when_all]
        if self.when_any:
            parts.append(" or ".join(c.describe() for c in self.when_any))
        return " and ".join(parts)

    def placeholders(self) -> list[str]:
        """Return the ``{name}`` placeholders of a string default.

        Returns
        -------
        The placeholder names; empty if the default is not a string.
        """
        return _fields(self.default) if isinstance(self.default, str) else []


def _fields(template: str) -> list[str]:
    """Return the ``{name}`` placeholders of a format string."""
    return [name for _, name, _, _ in string.Formatter().parse(template) if name is not None]


def _default_fits(kind: QuestionKind, default: object) -> bool:
    """Return whether ``default`` has the type a ``kind`` answer has."""
    if default is None:
        return True
    if kind == "confirm":
        return isinstance(default, bool)
    if kind == "int":
        return isinstance(default, int) and not isinstance(default, bool)
    if kind in ("text", "select", "per_item"):
        return isinstance(default, str)
    return False


class CustomKind(FrozenModel):
    """A question kind an app defines, with its own flag form and prompt.

    Registered in ``Interview.custom_kinds`` under the name a question's
    ``custom`` refers to. Its flag is repeatable.

    Attributes
    ----------
    flag_form
        How one flag value is written, for help and ``--questions``.
    parse
        Turns the flag's values into the answer; raises ``CliError``.
    prompt
        Asks for the answer in a terminal, validating as it goes.
    """

    flag_form: str = Field(min_length=1)
    parse: Callable[[list[str]], Any]
    prompt: Callable[[Console], Any]


class Interview(FrozenModel):
    """A command's questions and consents, and where their dynamic parts come from.

    Attributes
    ----------
    questions
        The questions, in the order they are asked.
    consents
        The confirmations the command may ask for while it runs.
    choices
        Dynamic choice, item and suggestion sources, by name.
    defaults
        Dynamic default sources, by name.
    offline
        The choice sources that are local and cheap: ``--questions`` lists
        their values and only names the others.
    facts
        Facts derived from the answers and options, for conditions.
    custom_kinds
        The custom kinds the questions use, by name.
    groups
        Bundled question groups, by name, each with what it covers in one
        line.
    consent_keys
        The keys of the declared consents.

    Methods
    -------
    add_arguments
        Add one flag per question to a parser, grouped by section.
    run
        Answer every applicable question from its flag, a prompt, or its default.
    document
        Return the interview as the document ``--questions`` prints.
    """

    questions: tuple[Question, ...] = ()
    consents: tuple[Consent, ...] = ()
    choices: dict[str, ChoiceSource] = Field(default_factory=dict)
    defaults: dict[str, DefaultSource] = Field(default_factory=dict)
    offline: frozenset[str] = frozenset()
    facts: Facts | None = None
    custom_kinds: dict[str, CustomKind] = Field(default_factory=dict)
    groups: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_references(self) -> Interview:
        """Reject duplicate keys and references to anything not declared."""
        problems: list[str] = []
        for name in sorted(self.offline - self.choices.keys()):
            problems.append(f"offline names undeclared choices source '{name}'")
        for keys, what in (
            ([q.key for q in self.questions], "question"),
            ([c.key for c in self.consents], "consent"),
        ):
            for key in sorted({k for k in keys if keys.count(k) > 1}):
                problems.append(f"{what} key '{key}' is declared twice")
        grouped = {q.group for q in self.questions}
        for name in sorted(self.groups.keys() - grouped):
            problems.append(f"group '{name}' has no questions")
        earlier: dict[str, Question] = {}
        later = {q.key for q in self.questions}
        for question in self.questions:
            later.discard(question.key)
            problems.extend(self._question_problems(question, earlier, later))
            earlier[question.key] = question
        if problems:
            raise ValueError("; ".join(problems) + ".")
        return self

    def _question_problems(
        self, question: Question, earlier: Mapping[str, Question], later: set[str]
    ) -> list[str]:
        """Return what is wrong with one question's references."""
        flag = question.flag
        problems = [
            f"{flag} names undeclared {registry} '{name}'"
            for name, names, registry in (
                (question.choices_from, self.choices, "choices source"),
                (question.flag_choices_from, self.choices, "choices source"),
                (question.items_from, self.choices, "choices source"),
                (question.suggestions_from, self.choices, "choices source"),
                (question.default_from, self.defaults, "defaults source"),
                (question.custom, self.custom_kinds, "custom kind"),
                (question.group, self.groups, "group"),
            )
            if name is not None and name not in names
        ]
        for name in question.placeholders():
            if name == "item" and question.kind == "per_item":
                continue
            source = earlier.get(name)
            if source is None or source.kind not in _TEXT_ANSWERS:
                problems.append(
                    f"{flag}'s default references {{{name}}}, which is not an "
                    "earlier text or select question"
                )
        for condition in (*question.when_all, *question.when_any):
            if condition.key == question.key or condition.key in later:
                problems.append(
                    f"{flag} depends on '{condition.key}', which is not answered before it"
                )
        return problems

    @property
    def consent_keys(self) -> frozenset[str]:
        """The keys of the declared consents."""
        return frozenset(consent.key for consent in self.consents)

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add one flag per question to ``parser``, grouped by section.

        Parameters
        ----------
        parser
            The command's argument parser.
        """
        sections: dict[str, argparse._ArgumentGroup] = {}  # pyright: ignore[reportPrivateUsage]
        for question in self.questions:
            if question.section not in sections:
                sections[question.section] = parser.add_argument_group(question.section)
            kwargs: dict[str, Any] = {"dest": question.key, "help": question.help}
            if question.metavar:
                kwargs["metavar"] = question.metavar
            elif question.custom is not None:
                kwargs["metavar"] = self.custom_kinds[question.custom].flag_form
            if question.kind == "confirm":
                kwargs.update(action=argparse.BooleanOptionalAction, default=None)
            elif question.kind in _COLLECTIONS:
                kwargs["action"] = "append"
            elif question.kind == "int":
                kwargs["type"] = int
            if (
                question.kind in ("select", "multiselect")
                and question.choices_from is None
                and question.flag_choices_from is None
            ):
                kwargs["choices"] = list(question.choices)
            _ = sections[question.section].add_argument(question.flag, **kwargs)

    def run(
        self,
        console: Console,
        interaction: Interaction,
        flag_values: Mapping[str, Any],
        options: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Answer every applicable question from its flag, a prompt, or its default.

        Parameters
        ----------
        console
            Where to ask.
        interaction
            Whether the run may prompt.
        flag_values
            The parsed flags, by question key; ``None`` or ``[]`` if not given.
        options
            The command's option values, which conditions may test.

        Returns
        -------
        The answers of the questions that apply, by key.

        Raises
        ------
        CliError
            A flag answers a question that does not apply, a value fails
            validation, or a run that cannot prompt misses a required answer.
        """
        asker = _Asker(self, console, interaction.can_prompt)
        answers: dict[str, Any] = {}
        for question in self.questions:
            flag_value = flag_values.get(question.key)
            if not question.applies(self._context(answers, options)):
                if _supplied(flag_value):
                    raise CliError(
                        f"{question.flag} does not apply here: it is only used "
                        f"when {question.describe_conditions()}."
                    )
                continue
            if not question.prompted and not _supplied(flag_value):
                answers[question.key] = asker.unprompted(question, answers)
                continue
            answers[question.key] = asker.ask(question, flag_value, answers)
        return answers

    def _context(self, answers: Mapping[str, Any], options: Mapping[str, Any]) -> dict[str, Any]:
        """Return what conditions see: options, answers, then facts."""
        context = {**options, **answers}
        if self.facts is not None:
            context.update(self.facts(context))
        return context

    def document(self, command_line: str, options: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Return the interview as the document ``--questions`` prints.

        Parameters
        ----------
        command_line
            How the command is invoked, e.g. ``mytool deploy``.
        options
            The command's plain options, described.

        Returns
        -------
        The document: the questions, consents and options, with how an assistant asks them.
        """
        return {
            "version": QUESTIONS_FORMAT_VERSION,
            "command": f"{command_line} --yes",
            "how_to_answer": HOW_TO_ANSWER,
            "procedure": list(PROCEDURE),
            "rules": list(RULES),
            "questions": [self._describe(question) for question in self.questions],
            "custom_kinds": {name: kind.flag_form for name, kind in self.custom_kinds.items()},
            "groups": {
                name: {
                    "covers": covers,
                    "questions": [q.flag for q in self.questions if q.group == name],
                }
                for name, covers in self.groups.items()
            },
            "consents": [consent.model_dump(mode="json") for consent in self.consents],
            "options": list(options),
        }

    def _describe(self, question: Question) -> dict[str, Any]:
        """Return one question for the document, with its local values."""
        entry: dict[str, Any] = {"flag": question.flag, **question.model_dump(mode="json")}
        for field, source in (("choices", question.choices_from), ("items", question.items_from)):
            if source in self.offline:
                entry[f"{field}_now"] = list(self.choices[source]({}, None))
        suggestions = question.suggestions_from
        if suggestions in self.offline:
            source = self.choices[suggestions]
            items = question.items_from
            if question.kind == "per_item" and items in self.offline:
                entry["suggestions_now"] = {
                    item: list(source({}, item)) for item in self.choices[items]({}, None)
                }
            else:
                entry["suggestions_now"] = list(source({}, None))
        return entry


def _supplied(flag_value: object) -> bool:
    """Return whether a flag was given on the command line."""
    return flag_value is not None and flag_value != []


class _Defaults(dict[str, str]):
    """Placeholder values for a default; an unanswered one is empty."""

    def __missing__(self, key: str) -> str:
        return ""


class _Asker:
    """Answers one question at a time for one run of an interview."""

    def __init__(self, interview: Interview, console: Console, can_prompt: bool) -> None:
        self._interview = interview
        self._console = console
        self._can_prompt = can_prompt

    def ask(self, question: Question, flag_value: Any, answers: Mapping[str, Any]) -> Any:
        """Answer ``question`` by its kind."""
        match question.kind:
            case "text":
                return self._text(question, flag_value, answers)
            case "select":
                return self._select(question, flag_value, answers)
            case "multiselect":
                return self._multiselect(question, flag_value, answers)
            case "confirm":
                return self._confirm(question, flag_value)
            case "int":
                return self._int(question, flag_value)
            case "list":
                return self._list(question, flag_value, answers)
            case "pairs":
                return self._pairs(question, flag_value)
            case "per_item":
                return self._per_item(question, flag_value, answers)
            case "custom":
                return self._custom(question, flag_value)

    def unprompted(self, question: Question, answers: Mapping[str, Any]) -> Any:
        """Answer a question the interview never asks and no flag answered."""
        # It takes its default, resolved like any other; a collection is empty.
        if question.kind in ("list", "multiselect"):
            return []
        if question.kind in ("pairs", "per_item"):
            return {}
        if question.kind in _TAKES_DEFAULT_FROM:
            return self._default(question, answers)
        return question.default

    def _validator(self, question: Question) -> Validator:
        """Return the checks every answer to ``question`` must pass."""
        return all_of(non_empty if question.required else None, question.validator)

    def _checked(self, question: Question, value: str, label: str = "") -> str:
        """Validate a flag value, failing the run with the flag named."""
        try:
            return self._validator(question)(value)
        except ValueError as error:
            raise CliError(f"{label or question.flag} '{value}': {error}") from error

    def _missing(self, question: Question, label: str = "") -> CliError:
        """Return the error for a required answer nobody can give."""
        return CliError(
            f"{label or question.flag} is required: it has no safe default, so "
            "pass it when the run cannot prompt."
        )

    def _source(self, name: str | None, answers: Mapping[str, Any], item: str | None) -> list[str]:
        """Return the values of a choices source, or none if ``name`` is unset."""
        return [] if name is None else list(self._interview.choices[name](answers, item))

    def _default(
        self, question: Question, answers: Mapping[str, Any], item: str | None = None
    ) -> str | None:
        """Return the question's default, resolving its source or placeholders."""
        if question.default_from is not None:
            return self._interview.defaults[question.default_from](answers, item)
        if question.default is None:
            return None
        values = _Defaults({k: v for k, v in answers.items() if isinstance(v, str)})
        if item is not None:
            values["item"] = item
        return str(question.default).format_map(values)

    def _choices(
        self, question: Question, answers: Mapping[str, Any], item: str | None = None
    ) -> list[str]:
        """Return the question's choices: fixed ones, then its source's."""
        return [*question.choices, *self._source(question.choices_from, answers, item)]

    def _flag_choices(self, question: Question, answers: Mapping[str, Any]) -> list[str]:
        """Return every value the flag accepts."""
        return [
            *self._choices(question, answers),
            *self._source(question.flag_choices_from, answers, None),
        ]

    def _label(self, question: Question) -> Callable[[str], str]:
        """Return how a choice is shown: its label, or itself."""
        return lambda choice: question.labels.get(choice, choice)

    def _text(self, question: Question, flag_value: str | None, answers: Mapping[str, Any]) -> str:
        """Answer a ``text`` question from its flag, a prompt, or its default."""
        if flag_value is not None:
            return self._checked(question, flag_value)
        default = self._default(question, answers) or ""
        if self._can_prompt:
            return self._console.text(
                question.prompt,
                default=default,
                validate=self._validator(question),
                suggestions=self._source(question.suggestions_from, answers, None),
            )
        if question.required:
            raise self._missing(question)
        return self._checked(question, default) if default else default

    def _select(
        self, question: Question, flag_value: str | None, answers: Mapping[str, Any]
    ) -> str:
        """Answer a ``select`` question from its flag, a prompt, or its default."""
        if flag_value is not None:
            allowed = self._flag_choices(question, answers)
            if flag_value not in allowed:
                raise CliError(
                    f"{question.flag} '{flag_value}' must be one of: {', '.join(allowed)}."
                )
            return flag_value
        choices = self._choices(question, answers)
        if not choices:
            raise CliError(f"{question.flag}: there is nothing to choose from.")
        if len(choices) == 1:
            self._console.info(f"{question.prompt}: {self._label(question)(choices[0])}")
            return choices[0]
        if self._can_prompt:
            return self._console.select(question.prompt, choices, label=self._label(question))
        default = self._default(question, answers)
        if default is None:
            raise self._missing(question)
        if default not in self._flag_choices(question, answers):
            raise CliError(
                f"{question.flag}: its default '{default}' is not one of "
                f"{', '.join(choices)}; pass {question.flag}."
            )
        return default

    def _multiselect(
        self, question: Question, flag_value: list[str] | None, answers: Mapping[str, Any]
    ) -> list[str]:
        """Answer a ``multiselect`` question from its flag, a prompt, or every choice."""
        if flag_value:
            allowed = self._flag_choices(question, answers)
            if unknown := sorted(set(flag_value) - set(allowed)):
                raise CliError(
                    f"{question.flag} names {', '.join(unknown)}, which "
                    f"{'is' if len(unknown) == 1 else 'are'} not among: {', '.join(allowed)}."
                )
            return list(dict.fromkeys(flag_value))
        choices = self._choices(question, answers)
        if len(choices) > 1 and self._can_prompt:
            selected = self._console.checkbox(question.prompt, choices, label=self._label(question))
        else:
            selected = choices
        if question.required and not selected:
            raise CliError(f"{question.flag}: choose at least one.")
        return selected

    def _confirm(self, question: Question, flag_value: bool | None) -> bool:
        """Answer a ``confirm`` question from its flag, a prompt, or its default."""
        if flag_value is not None:
            return flag_value
        default = bool(question.default)
        if self._can_prompt:
            return self._console.confirm(question.prompt, default=default)
        return default

    def _int(self, question: Question, flag_value: int | None) -> int | None:
        """Answer an ``int`` question from its flag, a prompt, or its default."""
        if flag_value is not None:
            return flag_value
        default = question.default if isinstance(question.default, int) else None
        if not self._can_prompt:
            if question.required:
                raise self._missing(question)
            return default
        entered = self._console.text(
            question.prompt,
            default="" if default is None else str(default),
            validate=all_of(non_empty if question.required else None, whole_number),
        )
        return int(entered) if entered.strip() else default

    def _list(
        self, question: Question, flag_value: list[str] | None, answers: Mapping[str, Any]
    ) -> list[str]:
        """Answer a ``list`` question from its flag, a prompt, or an empty list."""
        if flag_value:
            return [self._checked(question, value) for value in flag_value]
        if self._can_prompt:
            return prompt_list(
                self._console,
                question.prompt,
                required=question.required,
                validate=question.validator,
                suggestions=self._source(question.suggestions_from, answers, None),
            )
        if question.required:
            raise self._missing(question)
        return []

    def _pairs(self, question: Question, flag_value: list[str] | None) -> dict[str, str]:
        """Answer a ``pairs`` question from its flag, a prompt, or an empty dict."""
        if flag_value:
            pairs = parse_kv(flag_value, question.flag)
            return {
                key: self._checked(question, value, f"{question.flag} {key}=...")
                for key, value in pairs.items()
            }
        if self._can_prompt:
            return prompt_pairs(
                self._console,
                question.prompt,
                required=question.required,
                validate=question.validator,
            )
        if question.required:
            raise self._missing(question)
        return {}

    def _per_item(
        self, question: Question, flag_value: list[str] | None, answers: Mapping[str, Any]
    ) -> dict[str, str]:
        """Answer a ``per_item`` question: one value for each item of its source."""
        items = self._source(question.items_from, answers, None)
        supplied = parse_kv(flag_value, question.flag)
        if unknown := sorted(set(supplied) - set(items)):
            raise CliError(
                f"{question.flag} names {', '.join(unknown)}, not among: {', '.join(items)}."
            )
        return {
            item: self._per_item_answer(question, item, supplied.get(item), answers)
            for item in items
        }

    def _per_item_answer(
        self, question: Question, item: str, flag_value: str | None, answers: Mapping[str, Any]
    ) -> str:
        """Answer a ``per_item`` question for one item."""
        label = f"{question.flag} {item}=..."
        if flag_value is not None:
            return self._checked(question, flag_value, label)
        default = self._default(question, answers, item)
        if self._can_prompt:
            prompt = question.prompt.format(item=item)
            choices = self._choices(question, answers, item)
            if len(choices) > 1:
                return self._console.select(prompt, choices, label=self._label(question))
            return self._console.text(
                prompt,
                default=default or "",
                validate=self._validator(question),
                suggestions=self._source(question.suggestions_from, answers, item),
            )
        if default is None:
            if question.required:
                raise self._missing(question, label)
            return ""
        return default

    def _custom(self, question: Question, flag_value: list[str] | None) -> Any:
        """Answer a ``custom`` question with its kind's parser or prompt."""
        kind = self._interview.custom_kinds[str(question.custom)]
        if flag_value:
            return kind.parse(flag_value)
        if self._can_prompt:
            return kind.prompt(self._console)
        if question.required:
            raise self._missing(question)
        return None
