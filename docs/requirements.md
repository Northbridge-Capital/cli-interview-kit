# Requirements

What this project must do, the conditions it works under, and what it deliberately does not do.
Each requirement says where it is verified, so a change that breaks one fails a test, not a user.

## Purpose

Let a team build command-line tools whose every prompt is **declared once** and can be answered
by a person at a terminal, by flags in scripts and CI, or by an AI assistant interviewing the
user in its own chat, with the same validation and the same safety rules in all three.

## Functional requirements

| ID | Requirement | Verified by |
|---|---|---|
| F1 | Every question has a flag derived from its key, so every command runs from flags alone. | `tests/test_unattended.py` |
| F2 | At a terminal, each applicable question its flag did not answer is asked; an invalid answer shows its error and is asked again. | `tests/test_terminal.py`, `tests/test_suggest.py` |
| F3 | When nobody can be asked (`--yes`, a non-terminal stdin), each question takes its default, and one with no safe default fails naming its flag. | `test_a_required_answer_nobody_gives_fails_naming_its_flag` |
| F4 | A consent is given only by `--yes` or a person; with nobody to ask it takes its safe default or fails asking for `--yes`. A command cannot ask for a consent it did not declare. | `test_yes_grants_consent`, `test_without_yes_a_consent_nobody_can_give_fails`, `test_an_undeclared_consent_is_a_declaration_error` |
| F5 | Questions apply conditionally on earlier answers, options and facts; a flag for a question that does not apply fails the run. | `test_conditions_see_options_and_facts`, `test_a_flag_for_a_question_that_does_not_apply_fails` |
| F6 | `--questions` prints a versioned JSON document from which any AI assistant can interview the user and run the command: questions, local choices and suggestions, groups, consents, options and a procedure. | `tests/test_questions_document.py` (snapshot) |
| F7 | A declaration that cannot work is rejected when it is built, naming the question and the problem. | `tests/test_declarations.py` |
| F8 | One error policy with fixed exit codes: 0 success, 1 failure, 2 usage error, 130 interrupted; `--debug` shows the traceback. | `tests/test_app.py` |
| F9 | Results go to stdout and status lines to stderr; user input in a status line is never read as markup. | `tests/test_console.py`, `test_messages_are_never_read_as_markup` |

## Non-functional requirements

| ID | Requirement | Verified by |
|---|---|---|
| N1 | Works on macOS, Linux and Windows; Python 3.11 and newer. | CI matrix (3 OSes × Python 3.11, 3.14) |
| N2 | The declared dependency lower bounds work, not just the locked versions. | CI `test-lowest` |
| N3 | Four runtime dependencies only: pydantic, questionary, prompt-toolkit and rich. Another needs a strong case. | Review (`pyproject.toml`) |
| N4 | The package builds, renders on PyPI and imports from a clean environment; it is typed (`py.typed`). | CI `build` (`twine check --strict`) |
| N5 | 95% or more test coverage; warnings in tests are errors; the README and the example are executed by the tests. | CI `test`, `tests/test_readme.py` |
| N6 | Source passes strict type checking; workflows pass `actionlint` and `zizmor`; actions are pinned to commit SHAs. | CI `lint` |
| N7 | The API reference is generated from the docstrings, builds without warnings, and lists every public name. | CI `docs`, `tests/test_api_reference.py` |

## Environment and constraints

- **Terminals:** prompts need a terminal prompt_toolkit supports, which includes the usual ones on
  macOS, Linux and Windows. Without one, the command runs from flags and defaults.
- **Assistants:** any assistant that can run a shell command and read its output can follow
  `--questions`; nothing in the package is specific to one assistant.
- **Repository rules** (managed outside this repo): a code owner must approve every pull
  request, merges are squash-only, `ci-required` must pass, and tags matching `v*` are
  protected. Releases are tags on `main`, published to PyPI and as a GitHub Release (see
  CONTRIBUTING.md).

## Out of scope

A replacement for argparse's parsing itself; shell completion; configuration files or
environment-variable defaults; translations; asynchronous commands; typed answer objects (answers
are a `dict` keyed by question key). Each can be proposed in an issue.

## Verification status

Every requirement above is covered by the test suite and CI. The prompts are tested through
prompt_toolkit's pipe input, which checks answers and keys but not how a prompt looks; visual
changes are checked by hand in a real terminal.
