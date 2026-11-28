API reference
=============

Generated from the docstrings, type annotations and pydantic models in ``src/``. Every public name
is exported by ``cli_interview_kit``.

.. currentmodule:: cli_interview_kit

App and commands
----------------

.. autosummary::
   :toctree: generated/
   :nosignatures:

   App
   Command
   Option
   Invocation

Interviews
----------

.. autosummary::
   :toctree: generated/
   :nosignatures:

   Interview
   Question
   Condition
   CustomKind

.. autosummary::
   :toctree: generated/
   :nosignatures:

   when

Consent and interaction
-----------------------

.. autosummary::
   :toctree: generated/
   :nosignatures:

   Consent
   Interaction

Console
-------

.. autosummary::
   :toctree: generated/
   :nosignatures:

   Console

Validators
----------

.. autosummary::
   :toctree: generated/
   :nosignatures:

   non_empty
   whole_number
   byte_size
   parse_kv

Type aliases
------------

.. autodata:: Validator
.. autodata:: QuestionKind
.. autodata:: ChoiceSource
.. autodata:: DefaultSource
.. autodata:: Facts

Errors
------

.. autosummary::
   :toctree: generated/
   :nosignatures:

   CliError
   DeclarationError
