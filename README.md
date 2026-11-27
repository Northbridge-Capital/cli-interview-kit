# cli-interview-kit

[![CI](https://github.com/Northbridge-Capital/cli-interview-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/Northbridge-Capital/cli-interview-kit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cli-interview-kit)](https://pypi.org/project/cli-interview-kit/)
[![Python](https://img.shields.io/pypi/pyversions/cli-interview-kit)](https://pypi.org/project/cli-interview-kit/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/Northbridge-Capital/cli-interview-kit/blob/main/LICENSE)

Build Python command-line tools whose prompts are declared once and answered in three ways:

- **at the terminal**, as an interview that validates every answer and asks again until it is
  right;
- **by flags**, because every question has one, so the same command runs in CI and scripts;
- **by an AI assistant**: `--questions` prints the interview as JSON, the assistant asks the user
  in its own chat and runs the command with their answers.

```python
from cli_interview_kit import App, Command, Interview, Question

NEW = Command(
    name="new",
    help="Create a project.",
    interview=Interview(
        questions=(
            Question(
                key="name",
                section="project",
                kind="text",
                prompt="Project name",
                help="The project's name.",
                required=True,
            ),
            Question(
                key="template",
                section="project",
                kind="select",
                prompt="Template",
                help="What the project starts from.",
                choices=("library", "service"),
                default="library",
            ),
        ),
    ),
    run=lambda invocation: print(invocation.answers),
)

APP = App(name="projects", description="Create projects.", version="1.0.0", commands=(NEW,))

if __name__ == "__main__":
    raise SystemExit(APP.main())
```

```console
$ projects new                                  # a person at a terminal is interviewed
? Project name demo
? Template service
{'name': 'demo', 'template': 'service'}

$ projects new --yes --name demo                # nobody to ask: flags and defaults
{'name': 'demo', 'template': 'library'}

$ projects new --yes                            # an answer with no safe default fails
ERROR --name is required: it has no safe default, so pass it when the run cannot prompt.

$ projects new --questions                      # what an AI assistant reads
{ "version": 1, "command": "projects new --yes", "procedure": [...], "questions": [...] }
```

**Status: alpha (`0.x`).** The API may change between minor versions; see the
[changelog](https://github.com/Northbridge-Capital/cli-interview-kit/blob/main/CHANGELOG.md).

## Install

```bash
uv add cli-interview-kit
# or: pip install cli-interview-kit
```

Requires Python 3.11 or newer, on Linux, macOS or Windows. It builds on
[argparse](https://docs.python.org/3/library/argparse.html),
[questionary](https://github.com/tmbo/questionary) and [rich](https://github.com/Textualize/rich).

A complete example using every feature is in
[`examples/projects.py`](https://github.com/Northbridge-Capital/cli-interview-kit/blob/main/examples/projects.py).
From a clone, run `just example new` or `just example new --questions`.

## Concepts

| You declare | What it is |
|---|---|
| `App` | The program: its name, version and commands. `App.main()` parses, runs and returns the exit code. |
| `Command` | One command: plain `Option`s, an `Interview`, a `run` function, and any subcommands. |
| `Interview` | The command's `Question`s in order, the `Consent`s it may ask for, and the sources of dynamic choices and defaults. |
| `Question` | One answer the command needs. Its flag is derived from its key (`max_workers` is `--max-workers`). |
| `Consent` | A confirmation before something hard to undo, such as deleting. Given by `--yes`, never by a default. |
| `Option` | A flag that chooses what the command does (`--dry-run`) rather than an answer the user could be asked. |

The run function receives an `Invocation` with the `answers`, the `options`, the `console` to
print and ask through, and the `interaction` to pass to `Consent.ask`.

### Question kinds

| `kind` | Answer | Flag |
|---|---|---|
| `text` | `str` | `--flag VALUE` |
| `select` | one of `choices` | `--flag CHOICE` |
| `multiselect` | `list[str]`; every choice if omitted | repeat `--flag CHOICE` |
| `confirm` | `bool` | `--flag` or `--no-flag` |
| `int` | `int` or `None` | `--flag NUMBER` |
| `list` | `list[str]` | repeat `--flag VALUE` |
| `pairs` | `dict[str, str]` | repeat `--flag KEY=VALUE` |
| `per_item` | `dict[str, str]`, one value per item of a source | repeat `--flag ITEM=VALUE` |
| `custom` | whatever your `CustomKind` parses | your `CustomKind.flag_form` |

A question can also have:

- **conditions**: `when_all=(when("template", "service"),)` asks it only when an earlier answer,
  an option or a derived fact matches. A flag for a question that does not apply fails the run.
- **a default**, which may reference earlier answers (`default="{name}_pkg"`), or a
  `default_from` source. `required=True` means it has no safe default.
- **a validator**: any function that returns the value or raises `ValueError` with a message.
  Built in: `non_empty`, `whole_number`, `byte_size`.
- **dynamic values**: `choices_from`, `items_from` and `suggestions_from` name a function in
  `Interview.choices` that returns the current values. `suggestions_from` lists values under a
  free-text input as you type, without enforcing them.
- **a group**: questions with safe defaults can share a `group`, so an assistant asks "keep these
  defaults?" once instead of asking each.

Mistakes in a declaration, such as a `select` without choices or a reference to an undeclared
source, raise pydantic's `ValidationError` when the module is imported, not when a user runs the
command.

## Who answers

Each run decides once whether it may prompt: it may when stdin is a terminal and `--yes` was not
given.

- **At a terminal**, each applicable question its flag did not answer is asked. An invalid answer
  shows its error under the input and is asked again.
- **When nobody can be asked** (`--yes`, CI, a pipe), each question takes its default. One with
  no safe default fails the run, naming its flag.
- **Consents** are given by `--yes`. Without it they are asked at a terminal; with nobody to ask,
  a consent with a `safe_default` takes it, and any other fails the run, asking for `--yes`. A
  piped stdin never consents by itself. Asking for a consent the command did not declare raises
  `DeclarationError`, so `--questions` always lists every consent.

## AI assistants

`--questions` prints the command's interview as a JSON document: every question with its
choices, defaults, conditions and current local values, the groups, the consents, the plain
options, and a `procedure` for the assistant to follow. Any assistant that can run a shell
command can use it, whichever product it is:

1. It runs `projects new --questions`.
2. It asks the user the questions in its own chat, skipping those whose conditions do not hold,
   and describes each consent.
3. It runs `projects new --yes --name demo --template service`. If the command rejects a value,
   it asks that question again.

Point your assistant at the command in your repository's agent instructions, for example: "To
create a project, run `projects new --questions` and follow its `procedure`." The document has a
`version`, raised when a field changes meaning or is removed.

## Output and errors

`Console.print` writes a command's result to stdout. Status lines (`info`, `success`, `warning`,
`error`) and progress bars go to stderr, so output can be piped. Status lines are plain text:
values a user typed are never interpreted as rich markup.

| Outcome | Exit code |
|---|---|
| Success | 0 |
| `CliError`, or an exception type listed in `App.expected_errors`: its message | 1 |
| Any other exception: one line naming it, or the traceback with `--debug` | 1 |
| Ctrl-C: `Aborted.` | 130 |
| Usage error (unknown flag, invalid choice) | 2 |

## More

- [Requirements](https://github.com/Northbridge-Capital/cli-interview-kit/blob/main/docs/requirements.md):
  what the package must do, what it deliberately does not, and how each is verified.
- [Design](https://github.com/Northbridge-Capital/cli-interview-kit/blob/main/docs/design.md):
  how it works, the module map, decisions and trade-offs.
- [Contributing](https://github.com/Northbridge-Capital/cli-interview-kit/blob/main/CONTRIBUTING.md):
  setup, checks and the release process.
- [Security](https://github.com/Northbridge-Capital/cli-interview-kit/blob/main/SECURITY.md):
  how to report a vulnerability.

## License

MIT, see [LICENSE](https://github.com/Northbridge-Capital/cli-interview-kit/blob/main/LICENSE).
