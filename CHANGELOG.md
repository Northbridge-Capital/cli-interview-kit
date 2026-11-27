# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/) (while `0.x`, a breaking change bumps the minor
version).

## [Unreleased]

## [0.1.1] - 2026-11-27

No behavior changes.

### Added

- A Code of Conduct.

### Changed

- Docstrings follow the NumPy convention (parameters, returns, raises, attributes and methods,
  without types) and are checked in CI.
- CI now lints for common security issues (ruff's `S`/bandit rules), matching the scrutiny a
  package installed by third parties warrants.

## [0.1.0] - 2026-11-27

First release.

### Added

- Declare commands as data: `App`, `Command`, `Option`, `Interview`, `Question`, `Consent`,
  `CustomKind`, and `when` conditions.
- Nine question kinds: `text`, `select`, `multiselect`, `confirm`, `int`, `list`, `pairs`,
  `per_item` and `custom`, each with a flag derived from its key.
- A terminal interview that validates every answer and asks again until it passes, with
  suggestions listed under free-text inputs as you type.
- Unattended runs: `--yes` and non-terminal stdin answer from flags and defaults, and fail naming
  the flag of an answer with no safe default. Consents are given only by `--yes` or a person.
- `--questions`: the interview as a versioned JSON document with a procedure, so any AI assistant
  can interview a user and run the command.
- Declarations are validated when they are built; asking for an undeclared consent raises
  `DeclarationError`.
- One error policy with documented exit codes, `--debug` for tracebacks, and `--version`.
- `Console`: results on stdout, plain-text status lines and progress on stderr.
- Built-in validators `non_empty`, `whole_number` and `byte_size`, and `parse_kv` for custom
  kinds.
