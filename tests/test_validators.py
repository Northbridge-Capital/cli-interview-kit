"""The built-in validators."""

from __future__ import annotations

import pytest

from cli_interview_kit import byte_size, non_empty, whole_number


@pytest.mark.parametrize("value", ["x", " x "])
def test_non_empty_accepts(value: str) -> None:
    assert non_empty(value) == value


@pytest.mark.parametrize("value", ["", "   "])
def test_non_empty_rejects(value: str) -> None:
    with pytest.raises(ValueError, match="A value is required"):
        non_empty(value)


@pytest.mark.parametrize("value", ["", "0", "42", "-7", " 3 "])
def test_whole_number_accepts(value: str) -> None:
    assert whole_number(value) == value


@pytest.mark.parametrize("value", ["1.5", "x", "--1", "1e3"])
def test_whole_number_rejects(value: str) -> None:
    with pytest.raises(ValueError, match="whole number"):
        whole_number(value)


@pytest.mark.parametrize("value", ["", "512", "512m", "1g", "1GB", "10kb", "2t"])
def test_byte_size_accepts(value: str) -> None:
    assert byte_size(value) == value


@pytest.mark.parametrize("value", ["m", "1.5g", "1x", "-1g", "1 g"])
def test_byte_size_rejects(value: str) -> None:
    with pytest.raises(ValueError, match="size such as 512m"):
        byte_size(value)
