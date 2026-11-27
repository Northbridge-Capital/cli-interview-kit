"""A free-text prompt with its suggestions listed under the input.

prompt_toolkit's completion menu floats at the cursor's column in a framed
box. This prompt instead lists the matching suggestions as plain lines
directly under the input, filtered as the user types (a match anywhere in a
suggestion counts):

- Up/Down highlight a suggestion, Tab copies it into the input, Enter
  accepts the highlighted suggestion or else what was typed. Any value can
  be entered; suggestions are never enforced.
- A failed validation shows as a red line under the input until fixed.
- When done, the list is erased and the answered line stays, like
  questionary's own prompts.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText, StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.shortcuts import print_formatted_text
from prompt_toolkit.styles import BaseStyle
from pydantic import BaseModel
from questionary.constants import DEFAULT_SELECTED_POINTER

MAX_SHOWN = 8
"""How many matching suggestions are listed at once."""


class _State(BaseModel):
    """The prompt's mutable state: its suggestions, the highlight and the error."""

    suggestions: list[str]
    highlighted: int | None = None
    error: str = ""

    def matches(self, typed: str) -> list[str]:
        """Return the suggestions containing ``typed``, case-insensitively."""
        needle = typed.strip().lower()
        found = [s for s in self.suggestions if needle in s.lower() and s != typed]
        return found[:MAX_SHOWN]


# ``validate`` returns ``True`` when valid, else the message to show. ``style`` uses the ``qmark``,
# ``question``, ``answer``, ``pointer``, ``suggestion`` and ``validation-toolbar`` classes, like
# the other prompts. The answer is ``None`` when the user cancels with Ctrl-C.
def suggest_text(
    prompt: str,
    suggestions: Sequence[str],
    *,
    default: str = "",
    validate: Callable[[str], bool | str] | None = None,
    style: BaseStyle | None = None,
) -> str | None:
    """Ask for free text with suggestions listed under the input."""
    state = _State(suggestions=list(dict.fromkeys(suggestions)))
    buffer = Buffer(document=Document(default, len(default)), multiline=False)
    buffer.on_text_changed += lambda _buffer: _reset(state)  # pyright: ignore[reportUnknownLambdaType]

    question: StyleAndTextTuples = [
        ("class:qmark", "? "),
        ("class:question", f"{prompt} "),
    ]
    layout = Layout(
        HSplit(
            [
                VSplit(
                    [
                        Window(
                            FormattedTextControl(question),
                            dont_extend_width=True,
                        ),
                        Window(BufferControl(buffer=buffer), height=1),
                    ]
                ),
                Window(
                    FormattedTextControl(lambda: _lines(state, buffer.text)),
                    dont_extend_height=True,
                ),
            ]
        ),
        focused_element=buffer,
    )
    app: Application[str | None] = Application(
        layout=layout,
        key_bindings=_bindings(state, buffer, validate),
        style=style,
        erase_when_done=True,
    )
    answer = app.run()
    if answer is not None:
        print_formatted_text(
            FormattedText([*question, ("class:answer", answer)]),
            style=style,
        )
    return answer


def _lines(state: _State, typed: str) -> StyleAndTextTuples:
    """Return the matching suggestions, the highlighted one, and any error."""
    lines: StyleAndTextTuples = []
    for index, match in enumerate(state.matches(typed)):
        if index == state.highlighted:
            lines.append(("class:pointer", f"  {DEFAULT_SELECTED_POINTER} {match}\n"))
        else:
            lines.append(("class:suggestion", f"    {match}\n"))
    if state.error:
        lines.append(("class:validation-toolbar", f"  ✗ {state.error}\n"))
    return lines


def _bindings(
    state: _State,
    buffer: Buffer,
    validate: Callable[[str], bool | str] | None,
) -> KeyBindings:
    """Return the keys: move the highlight, complete, accept, cancel."""
    bindings = KeyBindings()

    @bindings.add("down")
    def _down(_event: KeyPressEvent) -> None:
        _move(state, buffer.text, 1)

    @bindings.add("up")
    def _up(_event: KeyPressEvent) -> None:
        _move(state, buffer.text, -1)

    @bindings.add("tab")
    def _complete(_event: KeyPressEvent) -> None:
        chosen = _chosen(state, buffer.text, first=True)
        if chosen is not None:
            buffer.document = Document(chosen, len(chosen))

    @bindings.add("enter")
    def _accept(event: KeyPressEvent) -> None:
        value = _chosen(state, buffer.text, first=False) or buffer.text
        verdict = validate(value) if validate is not None else True
        if verdict is not True:
            state.error = str(verdict)
            return
        event.app.exit(result=value)

    @bindings.add("c-c")
    def _cancel(event: KeyPressEvent) -> None:
        event.app.exit(result=None)

    return bindings


def _reset(state: _State) -> None:
    """Forget the highlight and the error once the input changes."""
    state.highlighted = None
    state.error = ""


def _move(state: _State, typed: str, step: int) -> None:
    """Move the highlight through the current matches."""
    matches = state.matches(typed)
    if not matches:
        state.highlighted = None
        return
    if state.highlighted is None:
        state.highlighted = 0 if step > 0 else len(matches) - 1
    else:
        state.highlighted = (state.highlighted + step) % len(matches)


def _chosen(state: _State, typed: str, *, first: bool) -> str | None:
    """Return the highlighted match, or the first one when ``first``."""
    matches = state.matches(typed)
    if state.highlighted is not None and state.highlighted < len(matches):
        return matches[state.highlighted]
    if first and matches:
        return matches[0]
    return None
