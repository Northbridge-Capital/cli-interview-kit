# Security

This package runs inside your command-line tool and has no network access, credential handling
or persistent state of its own. What it does with input:

- **Status lines are plain text.** Values a user types are printed literally and never
  interpreted as rich markup, so input cannot restyle, hide or break the tool's output.
- **Nothing is evaluated.** Answers are strings, numbers and booleans checked by your
  validators; defaults are filled with `str.format_map` over earlier answers only, and their
  placeholders are checked when the declaration is built.
- **Consents cannot be bypassed by a pipe.** A non-terminal stdin never confirms anything; only
  `--yes` or a person at a terminal does, and every consent a command can ask for is listed by
  `--questions` before the assistant runs it.

The `--questions` document is written by your tool's author and read by an AI assistant. If your
choice or suggestion sources return data from outside (files, APIs), that data reaches the
assistant too, so do not list secrets in them.

## Reporting a vulnerability

Please report vulnerabilities **privately** through GitHub: open the repository's
[Security tab](https://github.com/Northbridge-Capital/cli-interview-kit/security) and choose
"Report a vulnerability". Do not open a public issue. Include the affected version and steps to
reproduce.

## Supported versions

Only the latest release receives fixes while the project is `0.x`.

## Supply chain

Releases are built and published by GitHub Actions through PyPI trusted publishing, with no
stored token, and carry PyPI's build attestations. Workflow actions are pinned to commit SHAs and
the workflows are audited by `zizmor` on every pull request.
