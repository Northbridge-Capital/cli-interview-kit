"""The two exception types: a user-facing failure and a broken declaration."""


class CliError(Exception):
    """An expected failure, reported as its message without a traceback.

    Raise it from a command for anything the user can act on: a bad value, a
    missing resource, a check that failed. The app prints the message to
    stderr and exits 1.
    """


class DeclarationError(Exception):
    """A declaration is used in a way it does not allow.

    A programming error in the app, not the user's: for example asking for a
    consent the command never declared. Declarations that are invalid on their
    own are rejected when they are built, with pydantic's ``ValidationError``.
    """
