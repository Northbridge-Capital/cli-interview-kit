"""The ``--questions`` document: a contract assistants read, pinned by a snapshot.

When a change to the document is intended, regenerate the snapshot with
``UPDATE_SNAPSHOTS=1 uv run pytest tests/test_questions_document.py`` and
review the diff; raise ``QUESTIONS_FORMAT_VERSION`` if a field changed
meaning or was removed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from helpers import question
from projects import APP

from cli_interview_kit import CustomKind, Interview

SNAPSHOT = Path(__file__).parent / "snapshots" / "projects_new_questions.json"


def test_the_document_matches_the_snapshot(capsys: pytest.CaptureFixture[str]) -> None:
    assert APP.main(["new", "--questions"]) == 0
    document = capsys.readouterr().out
    if os.environ.get("UPDATE_SNAPSHOTS"):
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(document, encoding="utf-8")
    assert document == SNAPSHOT.read_text(encoding="utf-8")


def test_offline_sources_are_listed_and_others_named() -> None:
    interview = Interview(
        questions=(
            question("env", "select", choices_from="envs"),
            question("pin", "per_item", items_from="schemas", suggestions_from="versions"),
            question("owner", suggestions_from="owners"),
            question("stage", "custom", custom="stage"),
        ),
        choices={
            "envs": lambda _a, _i: ["dev"],
            "schemas": lambda _a, _i: ["a", "b"],
            "versions": lambda _a, item: [f"{item}-1"],
            "owners": lambda _a, _i: ["me"],
        },
        offline=frozenset({"schemas", "versions"}),
        custom_kinds={"stage": CustomKind(flag_form="NAME:KIND", parse=list, prompt=print)},
    )
    document = interview.document("tool go", [])
    env, pin, owner, _ = document["questions"]
    assert "choices_now" not in env
    assert env["choices_from"] == "envs"
    assert pin["items_now"] == ["a", "b"]
    assert pin["suggestions_now"] == {"a": ["a-1"], "b": ["b-1"]}
    assert "suggestions_now" not in owner
    assert document["custom_kinds"] == {"stage": "NAME:KIND"}


def test_per_item_suggestions_without_local_items_are_one_list() -> None:
    interview = Interview(
        questions=(question("pin", "per_item", items_from="schemas", suggestions_from="versions"),),
        choices={"schemas": lambda _a, _i: ["a"], "versions": lambda _a, _i: ["1"]},
        offline=frozenset({"versions"}),
    )
    assert interview.document("tool go", [])["questions"][0]["suggestions_now"] == ["1"]


def test_validators_are_named() -> None:
    def identifier(value: str) -> str:
        return value

    document = Interview(questions=(question("name", validator=identifier),)).document("t", [])
    assert document["questions"][0]["validator"] == "identifier"
