# Design

## How it works

```
App.main(argv)
  -> build_parser(): one argparse subparser per Command
       Option        -> a plain flag or positional
       Question      -> a flag derived from its key, grouped by section
       interactive   -> --yes and --questions
  -> parse_args
  -> --questions?  Interview.document() -> JSON on stdout, exit 0
  -> Interaction.resolve(--yes, stdin is a terminal, declared consents)
  -> Interview.run(): for each question in order
       does it apply?    conditions over options, earlier answers and facts
       flag given?       validate it, or fail naming the flag
       can prompt?       ask, validating at the prompt until it passes
       otherwise         its default, or fail if it has no safe default
  -> Command.run(Invocation(console, interaction, answers, options))
       Consent.ask(...)  --yes, a person, the safe default, or fail
  -> one error policy -> exit code
```

## Modules

| Module | Responsibility |
|---|---|
| `app.py` | `App`: builds the parser from the commands, dispatches, and owns the error policy and exit codes. |
| `command.py` | `Command`, `Option` and `Invocation`: what a command is and what its run receives. Checks names do not clash. |
| `interview.py` | `Question`, `Condition`/`when`, `CustomKind`, `Interview`, and the engine answering questions from flags, prompts or defaults. Renders `--questions`. |
| `interaction.py` | `Interaction` (may the run prompt; did `--yes` consent; which consents are declared) and `Consent`. |
| `console.py` | `Console`: output to stdout and stderr, and the prompts. |
| `validators.py` | The `Validator` shape and the built-in validators. |
| `errors.py` | `CliError` (the user's problem) and `DeclarationError` (the app author's). |
| `_prompts.py` | Prompt loops for answers with several items, and `KEY=VALUE` parsing. |
| `_suggest.py` | The free-text prompt listing suggestions under the input. |
| `_help.py` | Rich-rendered help and usage. |
| `_model.py` | The frozen pydantic base of every declaration. |

Everything public is exported from `cli_interview_kit`; modules starting with an underscore are
internal and may change in any release.

## Decisions

- **Declarations are data.** A command is a frozen pydantic model, not decorated functions. The
  same declaration then yields the parser, the interview, the unattended behaviour and the
  `--questions` document, and pydantic validates it when it is built. *Rejected:* decorators in
  the style of Click or Typer, which spread a command's prompts through its code where neither
  the framework nor an assistant can list them.
- **argparse, not Click or Typer.** The parser is generated, so argparse's standard-library
  stability matters more than a nicer authoring API, and it adds no dependency.
- **questionary for prompts, plus one custom prompt.** questionary covers select, checkbox,
  confirm and text. Free text with suggestions is a small prompt_toolkit application
  (`_suggest.py`) that lists matches as plain lines under the input; prompt_toolkit's own
  completion menu floats in a framed box at the cursor and was rejected as hard to read.
- **Answers and consents are different things.** An answer has a default and is safe to take
  unattended; a consent allows something hard to undo and is never given by a default unless the
  author declares a safe one. A piped stdin never consents, so `yes | tool delete` does not
  delete.
- **The assistant procedure travels with the document.** `--questions` carries the `procedure`
  and `rules`, so the behaviour is the same in every assistant and nothing has to be installed
  per assistant or per repository.
- **Validators are plain functions** of the form `(str) -> str` raising `ValueError`. The same
  function checks a prompt answer (shown under the input) and a flag value (fails the run).
- **Status on stderr, plain text.** Results stay pipeable, and a user's input cannot be read as
  rich markup. Status lines are not hard-wrapped, so a log or an assistant sees one line per
  message.

## Trade-offs

- **Answers are a `dict[str, Any]`** keyed by question key, not a typed object. Typed answers
  would need a model per command; a key typo fails at run time with a `KeyError`.
- **The help renderer reads argparse's underscored attributes** (`_actions`, `_action_groups`).
  They have been stable for many releases, and CI runs the help tests on the oldest and newest
  supported Python to catch a change.
- **Dynamic sources run when needed.** `choices_from` and similar sources are called during the
  interview, and by `--questions` only when listed in `offline`, so a slow or remote source never
  delays the document.
- **Conditions on facts are checked at run time.** Facts are computed by a function, so a
  condition naming a fact that does not exist is not caught when the declaration is built; it
  simply never holds.

## Extending

- **A new question kind** that most apps need belongs in `QuestionKind`, `HOW_TO_ANSWER`, the
  kind rules in `Question._check_kind`, `Interview.add_arguments` and `_Asker`. One app's own
  kind should be a `CustomKind` instead.
- **A new field in `--questions`** is additive and needs no version change; changing or removing
  one raises `QUESTIONS_FORMAT_VERSION`, and the snapshot test shows the difference.

Anything that adds a runtime dependency, an option kept "just in case", or a second way to do an
existing thing should be discussed in an issue first (see CONTRIBUTING.md).
