"""Answering from flags and defaults when nobody can be asked."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from helpers import Recorder, app, question

from cli_interview_kit import CliError, CustomKind, Option, when

pytestmark = pytest.mark.usefixtures("unattended")


def run(*questions: Any, argv: tuple[str, ...] = (), **interview: Any) -> dict[str, Any]:
    recorder = Recorder()
    assert app(*questions, run=recorder, **interview).main(["go", *argv]) == 0
    return recorder.answers


def fails(
    capsys: pytest.CaptureFixture[str],
    *questions: Any,
    argv: tuple[str, ...] = (),
    **interview: Any,
) -> str:
    assert app(*questions, **interview).main(["go", *argv]) == 1
    return capsys.readouterr().err


def test_flags_answer_every_kind() -> None:
    answers = run(
        question("name"),
        question("color", "select", choices=("red", "blue")),
        question("tag", "multiselect", choices=("a", "b", "c")),
        question("fast", "confirm"),
        question("count", "int"),
        question("item", "list"),
        question("label", "pairs"),
        argv=(
            "--name",
            "x",
            "--color",
            "blue",
            "--tag",
            "c",
            "--tag",
            "a",
            "--tag",
            "c",
            "--fast",
            "--count",
            "3",
            "--item",
            "p",
            "--item",
            "q",
            "--label",
            "k=v=w",
        ),
    )
    assert answers == {
        "name": "x",
        "color": "blue",
        "tag": ["c", "a"],
        "fast": True,
        "count": 3,
        "item": ["p", "q"],
        "label": {"k": "v=w"},
    }


def test_defaults_answer_what_no_flag_did() -> None:
    answers = run(
        question("name", default="demo"),
        question("package", default="{name}_pkg"),
        question("color", "select", choices=("red", "blue"), default="blue"),
        question("tag", "multiselect", choices=("a", "b")),
        question("fast", "confirm", default=True),
        question("slow", "confirm"),
        question("count", "int", default=4),
        question("other", "int"),
        question("item", "list"),
        question("label", "pairs"),
    )
    assert answers == {
        "name": "demo",
        "package": "demo_pkg",
        "color": "blue",
        "tag": ["a", "b"],
        "fast": True,
        "slow": False,
        "count": 4,
        "other": None,
        "item": [],
        "label": {},
    }


def test_a_placeholder_for_an_unanswered_question_is_empty() -> None:
    answers = run(
        question("mode", "select", choices=("a", "b"), default="a"),
        question("name", when_all=(when("mode", "b"),)),
        question("package", default="pkg{name}"),
    )
    assert answers["package"] == "pkg"


@pytest.mark.parametrize(
    "declared",
    [
        question("name", required=True),
        question("color", "select", choices=("red", "blue"), required=True),
        question("count", "int", required=True),
        question("item", "list", required=True),
        question("label", "pairs", required=True),
    ],
)
def test_a_required_answer_nobody_gives_fails_naming_its_flag(
    capsys: pytest.CaptureFixture[str], declared: Any
) -> None:
    assert f"{declared.flag} is required" in fails(capsys, declared)


def test_a_required_multiselect_with_no_choices_fails(capsys: pytest.CaptureFixture[str]) -> None:
    err = fails(
        capsys,
        question("tag", "multiselect", choices_from="none", required=True),
        choices={"none": lambda _a, _i: []},
    )
    assert "--tag: choose at least one." in err


def test_a_flag_value_failing_validation_fails_the_run(capsys: pytest.CaptureFixture[str]) -> None:
    def short(value: str) -> str:
        if len(value) > 3:
            raise ValueError("Too long.")
        return value

    err = fails(capsys, question("name", validator=short), argv=("--name", "abcd"))
    assert "--name 'abcd': Too long." in err


def test_a_default_failing_validation_fails_the_run(capsys: pytest.CaptureFixture[str]) -> None:
    def never(_value: str) -> str:
        raise ValueError("Never valid.")

    assert "--name 'x': Never valid." in fails(
        capsys, question("name", default="x", validator=never)
    )


def test_pairs_values_are_validated(capsys: pytest.CaptureFixture[str]) -> None:
    def digits(value: str) -> str:
        if not value.isdigit():
            raise ValueError("Digits only.")
        return value

    err = fails(capsys, question("label", "pairs", validator=digits), argv=("--label", "k=v"))
    assert "--label k=... 'v': Digits only." in err


@pytest.mark.parametrize("bad", ["novalue", "=value"])
def test_pairs_need_a_key_and_an_equals_sign(capsys: pytest.CaptureFixture[str], bad: str) -> None:
    err = fails(capsys, question("label", "pairs"), argv=("--label", bad))
    assert f"--label expects KEY=VALUE; got '{bad}'." in err


def test_a_flag_for_a_question_that_does_not_apply_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    err = fails(
        capsys,
        question("mode", "select", choices=("a", "b"), default="a"),
        question(
            "extra", when_all=(when("mode", "b"),), when_any=(when("mode", "b"), when("x", True))
        ),
        argv=("--extra", "1"),
    )
    assert (
        "--extra does not apply here: it is only used when mode is b and mode is b or x is true."
        in err
    )


def test_conditions_see_options_and_facts() -> None:
    def facts(context: Mapping[str, Any]) -> dict[str, Any]:
        return {"big": context.get("size") == "l"}

    recorder = Recorder()
    tool = app(
        question("size", "select", choices=("s", "l"), default="s"),
        question("workers", "int", default=8, when_all=(when("big", True),)),
        question("dry", "confirm", when_all=(when("plan", True),)),
        run=recorder,
        options=(Option(dest="plan", kind="switch", help="Plan."),),
        facts=facts,
    )
    assert tool.main(["go", "--size", "l"]) == 0
    assert recorder.answers == {"size": "l", "workers": 8}
    assert recorder.invocation is not None
    assert recorder.invocation.options == {"plan": False}


def test_select_flags_are_checked_against_dynamic_choices(
    capsys: pytest.CaptureFixture[str],
) -> None:
    sources = {"colors": lambda _a, _i: ["red"], "hidden": lambda _a, _i: ["black"]}
    color = question("color", "select", choices_from="colors", flag_choices_from="hidden")
    assert run(color, argv=("--color", "black"), choices=sources) == {"color": "black"}
    err = fails(capsys, color, argv=("--color", "blue"), choices=sources)
    assert "--color 'blue' must be one of: red, black." in err


def test_a_select_with_one_choice_takes_it(capsys: pytest.CaptureFixture[str]) -> None:
    answers = run(
        question("env", "select", choices_from="envs"), choices={"envs": lambda _a, _i: ["dev"]}
    )
    assert answers == {"env": "dev"}
    assert "INFO Env: dev" in capsys.readouterr().err


def test_a_select_with_nothing_to_choose_fails(capsys: pytest.CaptureFixture[str]) -> None:
    err = fails(
        capsys, question("env", "select", choices_from="envs"), choices={"envs": lambda _a, _i: []}
    )
    assert "--env: there is nothing to choose from." in err


def test_a_select_default_must_be_a_choice(capsys: pytest.CaptureFixture[str]) -> None:
    err = fails(
        capsys,
        question("env", "select", choices_from="envs", default="prod"),
        choices={"envs": lambda _a, _i: ["dev", "test"]},
    )
    assert "--env: its default 'prod' is not one of dev, test; pass --env." in err


def test_a_select_default_can_come_from_a_source() -> None:
    answers = run(
        question("env", "select", choices=("dev", "test"), default_from="env"),
        defaults={"env": lambda _a, _i: "test"},
    )
    assert answers == {"env": "test"}


def test_multiselect_flags_must_be_choices(capsys: pytest.CaptureFixture[str]) -> None:
    sources = {"tags": lambda _a, _i: ["a"]}
    tag = question("tag", "multiselect", choices_from="tags")
    assert "--tag names x, which is not among: a." in fails(
        capsys, tag, argv=("--tag", "x"), choices=sources
    )
    assert "--tag names x, y, which are not among: a." in fails(
        capsys, tag, argv=("--tag", "x", "--tag", "y"), choices=sources
    )


def test_per_item_answers_one_value_per_item(capsys: pytest.CaptureFixture[str]) -> None:
    pin = question(
        "pin",
        "per_item",
        items_from="schemas",
        default_from="pinned",
        prompt="Version of {item}",
    )
    interview: dict[str, Any] = {
        "choices": {"schemas": lambda _a, _i: ["a", "b", "c"]},
        "defaults": {"pinned": lambda _a, item: None if item == "c" else f"{item}-1"},
    }
    assert run(pin, argv=("--pin", "b=2"), **interview) == {"pin": {"a": "a-1", "b": "2", "c": ""}}
    assert "--pin names z, not among: a, b, c." in fails(
        capsys, pin, argv=("--pin", "z=1"), **interview
    )


def test_per_item_defaults_may_use_the_item() -> None:
    answers = run(
        question("path", "per_item", items_from="envs", default="/data/{item}"),
        choices={"envs": lambda _a, _i: ["dev", "prod"]},
    )
    assert answers == {"path": {"dev": "/data/dev", "prod": "/data/prod"}}


def test_a_required_per_item_answer_fails_naming_the_item(
    capsys: pytest.CaptureFixture[str],
) -> None:
    err = fails(
        capsys,
        question("path", "per_item", items_from="envs", required=True),
        choices={"envs": lambda _a, _i: ["dev"]},
    )
    assert "--path dev=... is required" in err


def test_unprompted_questions_take_their_default() -> None:
    answers = run(
        question("item", "list", prompted=False),
        question("tag", "multiselect", choices=("a",), prompted=False),
        question("label", "pairs", prompted=False),
        question("path", "per_item", items_from="envs", prompted=False),
        question("fast", "confirm", default=True, prompted=False),
        question("name", default="demo"),
        question("package", default="{name}_pkg", prompted=False),
        question("color", "select", choices=("a", "b"), default_from="color", prompted=False),
        choices={"envs": lambda _a, _i: ["dev"]},
        defaults={"color": lambda _a, _i: "b"},
    )
    assert answers == {
        "item": [],
        "tag": [],
        "label": {},
        "path": {},
        "fast": True,
        "name": "demo",
        "package": "demo_pkg",
        "color": "b",
    }


def test_custom_kinds_parse_their_flags(capsys: pytest.CaptureFixture[str]) -> None:
    stage = CustomKind(
        flag_form="NAME:KIND",
        parse=lambda values: [tuple(v.split(":")) for v in values],
        prompt=lambda _console: [],
    )
    declared = question("stage", "custom", custom="stage")
    assert run(declared, argv=("--stage", "a:b"), custom_kinds={"stage": stage}) == {
        "stage": [("a", "b")]
    }
    assert run(declared, custom_kinds={"stage": stage}) == {"stage": None}
    required = question("stage", "custom", custom="stage", required=True)
    assert "--stage is required" in fails(capsys, required, custom_kinds={"stage": stage})


def test_parse_errors_from_custom_kinds_fail_the_run(capsys: pytest.CaptureFixture[str]) -> None:
    def parse(values: list[str]) -> object:
        raise CliError(f"--stage: bad {values[0]}.")

    stage = CustomKind(flag_form="X", parse=parse, prompt=lambda _console: None)
    err = fails(
        capsys,
        question("stage", "custom", custom="stage"),
        argv=("--stage", "q"),
        custom_kinds={"stage": stage},
    )
    assert "--stage: bad q." in err
