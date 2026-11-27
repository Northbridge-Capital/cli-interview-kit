"""An example app: ``projects new`` interviews for a project, ``projects remove`` deletes one.

Run it from the repository root:

    uv run python examples/projects.py new                # the terminal interview
    uv run python examples/projects.py new --questions    # what an AI assistant reads
    uv run python examples/projects.py new --yes --name demo --template service
    uv run python examples/projects.py remove --name demo

The test suite drives this app, so it stays a working example.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from cli_interview_kit import (
    App,
    CliError,
    Command,
    Consent,
    Interview,
    Invocation,
    Option,
    Question,
    byte_size,
    when,
)

PROJECTS = ("billing", "search", "website")
"""Stands in for whatever the app would look up: files, an API, a database."""

OWNERS = ("platform", "data", "web")


def identifier(value: str) -> str:
    """Accept a lower snake_case name, or a blank answer."""
    if value and not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ValueError("Use lower snake_case, e.g. order_book.")
    return value


def _owners(_answers: Mapping[str, Any], _item: str | None) -> list[str]:
    return list(OWNERS)


def _environments(answers: Mapping[str, Any], _item: str | None) -> list[str]:
    return ["dev", "prod"] if answers.get("template") == "service" else ["dev"]


def _projects(_answers: Mapping[str, Any], _item: str | None) -> list[str]:
    return list(PROJECTS)


def _create(invocation: Invocation) -> None:
    answers = invocation.answers
    if answers["name"] in PROJECTS:
        raise CliError(f"Project '{answers['name']}' already exists.")
    if invocation.options["dry_run"]:
        invocation.console.info("Dry run: nothing is created.")
    invocation.console.print(answers)


DELETE = Consent(key="delete", when="always: removing a project deletes it and its history")


def _remove(invocation: Invocation) -> None:
    name = invocation.answers["name"]
    if not DELETE.ask(invocation.console, invocation.interaction, f"Delete project '{name}'?"):
        invocation.console.warning("Nothing was deleted.")
        return
    invocation.console.success(f"Deleted {name}.")


NEW = Command(
    name="new",
    help="Create a project.",
    options=(Option(dest="dry_run", kind="switch", help="Show the project; create nothing."),),
    interview=Interview(
        questions=(
            Question(
                key="name",
                section="project",
                kind="text",
                prompt="Project name",
                help="The project's name, in snake_case.",
                required=True,
                validator=identifier,
            ),
            Question(
                key="template",
                section="project",
                kind="select",
                prompt="Template",
                help="What the project starts from.",
                choices=("library", "service"),
                labels={"library": "library (a package)", "service": "service (deployed)"},
                default="library",
            ),
            Question(
                key="owner",
                section="project",
                kind="text",
                prompt="Owning team",
                help="The team that owns the project.",
                suggestions_from="owners",
                default="platform",
            ),
            Question(
                key="environment",
                section="deployment",
                kind="multiselect",
                prompt="Environments",
                help="Where a service is deployed.",
                choices_from="environments",
                when_all=(when("template", "service"),),
            ),
            Question(
                key="memory",
                section="deployment",
                kind="text",
                prompt="Memory per instance",
                help="Memory per instance, e.g. 512m.",
                validator=byte_size,
                default="512m",
                group="sizing",
                when_all=(when("template", "service"),),
            ),
            Question(
                key="instances",
                section="deployment",
                kind="int",
                prompt="Instances",
                help="How many instances run.",
                default=2,
                group="sizing",
                when_all=(when("template", "service"),),
            ),
            Question(
                key="package",
                section="project",
                kind="text",
                prompt="Package name",
                help="The importable package name; defaults to the project name.",
                default="{name}",
                validator=identifier,
            ),
            Question(
                key="dependency",
                section="project",
                kind="list",
                prompt="dependency",
                help="A package the project depends on.",
            ),
            Question(
                key="label",
                section="project",
                kind="pairs",
                prompt="label",
                help="A KEY=VALUE label to tag the project with.",
            ),
            Question(
                key="ci",
                section="project",
                kind="confirm",
                prompt="Add CI?",
                help="Add a CI workflow.",
                default=True,
            ),
        ),
        choices={"owners": _owners, "environments": _environments},
        offline=frozenset({"owners", "environments"}),
        groups={"sizing": "memory and instance count of a service"},
    ),
    run=_create,
)


REMOVE = Command(
    name="remove",
    help="Delete a project.",
    interview=Interview(
        questions=(
            Question(
                key="name",
                section="project",
                kind="select",
                prompt="Project to delete",
                help="The project to delete.",
                choices_from="projects",
                required=True,
            ),
        ),
        consents=(DELETE,),
        choices={"projects": _projects},
        offline=frozenset({"projects"}),
    ),
    run=_remove,
)


APP = App(
    name="projects",
    description="Create and remove projects.",
    version="1.0.0",
    commands=(NEW, REMOVE),
)

if __name__ == "__main__":
    raise SystemExit(APP.main())
