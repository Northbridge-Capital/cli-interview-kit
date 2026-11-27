# Contributing

Thanks for helping. Bug reports, fixes, docs and features are all welcome; for anything
larger than a small fix, please open an issue first so we can agree on the approach.

## Setup and checks

Requires [uv](https://docs.astral.sh/uv/) and [just](https://github.com/casey/just).

```bash
just sync   # install dependencies
just lint   # ruff, ruff format, basedpyright
just test   # pytest with coverage
```

CI runs the same checks on every pull request (the aggregate `ci-required` job passes only when all
of them do, and is the single check meant for branch protection): lint and types, the tests on Linux, macOS and
Windows with Python 3.11 and 3.14, the tests against the **lowest** dependency versions that
`pyproject.toml` allows, and a build check (`twine check`, clean-environment import).

### Testing prompts

The tests drive the real prompts: `tests/conftest.py`'s `terminal` fixture types keystrokes into
a prompt_toolkit pipe, and `unattended` makes stdin a pipe. Use them rather than mocking
`Console`, so a change in questionary or prompt_toolkit is caught. Still try a changed prompt in a
real terminal (`just example new`): the tests check answers, not how a prompt looks.

### The `--questions` snapshot

`tests/snapshots/projects_new_questions.json` pins the document assistants read. When a change
to it is intended, regenerate it with
`UPDATE_SNAPSHOTS=1 uv run pytest tests/test_questions_document.py`, review the diff, and raise
`QUESTIONS_FORMAT_VERSION` if a field changed meaning or was removed.

## Where things are

- [docs/requirements.md](docs/requirements.md): what the project must do and the conditions it
  works under. A change that alters a requirement updates it in the same pull request.
- [docs/design.md](docs/design.md): how it works, the module map, decisions, and where to extend.

## Design rules

- **Lean.** The runtime dependencies are pydantic, questionary, prompt-toolkit and rich; adding
  another needs a strong case. Delete rather than deprecate, and no options kept "just in case".
- **One source of truth.** No logic or constant maintained in two places.
- **Docs move with the code.** README, docstrings, comments and `CHANGELOG.md` (under
  `[Unreleased]`) must be correct in the same pull request.
- **Declarations fail early.** A setting that cannot work is rejected when the declaration is
  built, not when a user runs the command.
- **Every prompt has a flag,** and every consent is declared, so `--questions` describes the
  whole command.

## Pull requests

1. Fork the repository (or branch, if you are a maintainer) and branch off `main` using
   `feature/…`, `fix/…`, `docs/…` or `chore/…`.
2. Open a pull request against `main`. Branches are merged by **squash**, so the pull request
   title becomes the commit message: make it a short imperative summary.
3. A code owner must approve before merging (`.github/CODEOWNERS`); other reviews are welcome
   but do not satisfy the merge rule. An author cannot approve their own pull request, so a
   code owner should not open the pull request they are meant to approve.

## Releasing

Releases are tags on `main`, published to PyPI. Tags matching `v*` are protected: they
cannot be moved or deleted except by organisation admins, so check before you tag, and never
reuse a version.

1. In a pull request, bump `version` in `pyproject.toml`, run `uv lock` (CI uses `--locked`),
   and in `CHANGELOG.md` move the `[Unreleased]` entries under the new version with its date.
   Merge it.
2. Dry-run the release: Actions > **Release** > Run workflow, on `main`. It performs the same
   checks and build as a real release but publishes nothing (tick `testpypi` to also upload the
   build to TestPyPI, once per version). Fix anything it reports; tags cannot be undone, so do
   not skip this.
3. A maintainer tags the merge commit and pushes the tag:

   ```bash
   git switch main && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

4. The `Release` workflow checks that the tag is on `main` and equals the `pyproject.toml`
   version, builds the package, and publishes a GitHub Release (that version's `CHANGELOG.md`
   section as the notes, wheel and sdist attached; it fails if the changelog has no section for
   the version). The PyPI upload then waits for a reviewer to approve the `pypi` environment
   (Actions run > Review deployments).
5. Consumers widen their version range when they need the release.

### How PyPI publishing is configured

The `Release` workflow publishes with PyPI **trusted publishing** (GitHub's OIDC identity), so no
token or secret is stored anywhere. It relies on two settings outside this repository's code:

- A trusted publisher on the PyPI project: owner `Northbridge-Capital`, repository
  `cli-interview-kit`, workflow `release.yml`, environment `pypi`.
- A GitHub environment named `pypi` on this repository (managed in the infrastructure repo's
  Terraform) with a required reviewer, limited to `main` and `v*` tags.

The `testpypi` dry run uploads to test.pypi.org, which is a separate site with separate accounts;
it has its own trusted publisher with the same values.

PyPI files are immutable: a version can be uploaded exactly once. If the publish step fails
before uploading (for example a misconfigured publisher), fix the setting and re-run only the
failed job; no new version is needed. If a bad release does get uploaded, yank it and cut a new
version.
