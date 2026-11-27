"""The immutable pydantic base for the package's value objects."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Immutable pydantic base for every declaration and value object.

    Declarations hold callables (run functions, validators, choice sources),
    so arbitrary types are allowed.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True, extra="forbid")
