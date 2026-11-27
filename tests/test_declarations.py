"""Invalid declarations are rejected when they are built, naming the problem."""

from __future__ import annotations

from typing import Any

import pytest
from helpers import question
from pydantic import ValidationError

from cli_interview_kit import App, Command, Consent, CustomKind, Interview, Option, when


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (
            {"kind": "text", "choices": ("a",)},
            "only select, multiselect and per_item questions take choices",
        ),
        ({"kind": "select"}, "a select question needs choices or choices_from"),
        (
            {"kind": "text", "flag_choices_from": "x"},
            "only select and multiselect questions take flag_choices_from",
        ),
        ({"kind": "per_item"}, "items_from is required on a per_item question"),
        ({"kind": "text", "items_from": "x"}, "items_from is required on a per_item question"),
        ({"kind": "custom"}, "custom is required on a custom question"),
        (
            {"kind": "confirm", "suggestions_from": "x"},
            "only text, list and per_item questions take suggestions_from",
        ),
        (
            {"kind": "int", "validator": str.strip},
            "only text, list, pairs and per_item questions take a validator",
        ),
        (
            {"kind": "list", "default_from": "x"},
            "only text, select and per_item questions take default_from",
        ),
        (
            {"kind": "text", "default": "a", "default_from": "x"},
            "set default or default_from, not both",
        ),
        ({"kind": "confirm", "default": "yes"}, "a confirm question cannot default to 'yes'"),
        ({"kind": "int", "default": True}, "a int question cannot default to True"),
        ({"kind": "text", "default": 3}, "a text question cannot default to 3"),
        ({"kind": "list", "default": "a"}, "a list question cannot default to 'a'"),
        (
            {"kind": "text", "required": True, "default": "a"},
            "a required question has no safe default",
        ),
        ({"kind": "confirm", "required": True}, "a confirm question cannot be required"),
        ({"kind": "text", "required": True, "group": "g"}, "a required question cannot be grouped"),
        (
            {"kind": "text", "required": True, "prompted": False},
            "a required question must be prompted",
        ),
        (
            {"kind": "per_item", "items_from": "x", "prompt": "Value of {item} in {env}"},
            r"a per_item prompt may only use the \{item\} placeholder",
        ),
    ],
)
def test_questions_reject_settings_that_do_not_fit_their_kind(
    fields: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        question("name", **fields)


@pytest.mark.parametrize("key", ["Name", "my-key", "1st", ""])
def test_question_keys_are_snake_case(key: str) -> None:
    with pytest.raises(ValidationError):
        question(key)


@pytest.mark.parametrize(
    ("interview", "message"),
    [
        (
            {"questions": (question("a", "select", choices_from="x"),)},
            "--a names undeclared choices source 'x'",
        ),
        (
            {"questions": (question("a", default_from="x"),)},
            "--a names undeclared defaults source 'x'",
        ),
        (
            {"questions": (question("a", "custom", custom="x"),)},
            "--a names undeclared custom kind 'x'",
        ),
        ({"questions": (question("a", group="x"),)}, "--a names undeclared group 'x'"),
        ({"offline": frozenset({"x"})}, "offline names undeclared choices source 'x'"),
        ({"questions": (question("a"), question("a"))}, "question key 'a' is declared twice"),
        (
            {"consents": (Consent(key="c", when="w"), Consent(key="c", when="w"))},
            "consent key 'c' is declared twice",
        ),
        ({"groups": {"g": "nothing"}}, "group 'g' has no questions"),
        ({"questions": (question("a", default="{b}"),)}, r"--a's default references \{b\}"),
        (
            {"questions": (question("b", "int"), question("a", default="{b}"))},
            r"--a's default references \{b\}, which is not an earlier text or select question",
        ),
        ({"questions": (question("a", default="{item}"),)}, r"references \{item\}"),
        (
            {"questions": (question("a", when_all=(when("b", True),)), question("b", "confirm"))},
            "--a depends on 'b', which is not answered before it",
        ),
        (
            {"questions": (question("a", when_any=(when("a", "x"),)),)},
            "--a depends on 'a'",
        ),
    ],
)
def test_interviews_reject_references_to_anything_undeclared(
    interview: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        Interview(**interview)


def test_per_item_defaults_may_use_item() -> None:
    Interview(
        questions=(question("a", "per_item", items_from="s", default="{item}"),),
        choices={"s": lambda _a, _i: []},
    )


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"kind": "value", "nargs": "*"}, "only a positional takes nargs"),
        ({"kind": "switch", "choices": ("a",)}, "a switch takes no value settings"),
        ({"kind": "positional", "exclusive": "x"}, "a positional cannot be mutually exclusive"),
    ],
)
def test_options_reject_settings_that_do_not_fit_their_kind(
    fields: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        Option(dest="thing", help="A thing.", **fields)


def test_a_command_runs_something() -> None:
    with pytest.raises(ValidationError, match="has neither a run nor subcommands"):
        Command(name="go", help="Go.")


@pytest.mark.parametrize(
    ("options", "questions"),
    [
        ((Option(dest="name", help="h"),), (question("name"),)),
        ((Option(dest="yes", kind="switch", help="h"),), ()),
        ((), (question("questions"),)),
        ((Option(dest="debug", kind="switch", help="h"),), ()),
    ],
)
def test_command_names_do_not_clash(
    options: tuple[Option, ...], questions: tuple[Any, ...]
) -> None:
    with pytest.raises(ValidationError, match="more than once or as a reserved name"):
        Command(
            name="go",
            help="Go.",
            options=options,
            interview=Interview(questions=questions),
            run=print,
        )


def test_command_names_are_unique() -> None:
    go = Command(name="go", help="Go.", run=print)
    with pytest.raises(ValidationError, match="duplicate subcommands"):
        Command(name="group", help="Group.", subcommands=(go, go))
    with pytest.raises(ValidationError, match="duplicate commands"):
        App(name="tool", description="", version="1", commands=(go, go))


def test_custom_kinds_need_a_flag_form() -> None:
    with pytest.raises(ValidationError):
        CustomKind(flag_form="", parse=list, prompt=print)


def test_declarations_are_immutable() -> None:
    declared = question("name")
    with pytest.raises(ValidationError):
        declared.key = "other"  # pyright: ignore[reportAttributeAccessIssue]


def test_version_is_free_for_a_command() -> None:
    Command(name="go", help="Go.", options=(Option(dest="version", help="h"),), run=print)
