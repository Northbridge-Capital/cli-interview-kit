"""The README's example runs and prints what the README shows."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cli_interview_kit import App

README = Path(__file__).parent.parent / "README.md"


def readme_app() -> App:
    code = re.search(r"```python\n(.*?)```", README.read_text(encoding="utf-8"), re.S)
    assert code is not None
    namespace: dict[str, object] = {"__name__": "readme"}
    exec(code.group(1), namespace)
    app = namespace["APP"]
    assert isinstance(app, App)
    return app


@pytest.mark.usefixtures("unattended")
def test_the_readme_example_behaves_as_shown(capsys: pytest.CaptureFixture[str]) -> None:
    app = readme_app()
    assert app.main(["new", "--yes", "--name", "demo"]) == 0
    assert capsys.readouterr().out == "{'name': 'demo', 'template': 'library'}\n"
    assert app.main(["new", "--yes"]) == 1
    shown = (
        "ERROR --name is required: it has no safe default, so pass it when the run cannot prompt."
    )
    assert capsys.readouterr().err.strip() == shown
    assert shown in README.read_text(encoding="utf-8")
