"""Errors with stable categories for CLI, API, and integrations."""


class GlioError(Exception):
    """Base class for expected application failures."""

    code = "glio_error"


class ValidationError(GlioError):
    """Raised when an input or derived object violates a contract."""

    code = "validation_error"


class PolicyViolation(GlioError):
    """Raised when a request crosses the research-use policy boundary."""

    code = "policy_violation"


class UnsupportedCase(GlioError):
    """Raised when a case requires unavailable context or variation support."""

    code = "unsupported_case"


class StoreError(GlioError):
    """Raised for content-addressed storage failures."""

    code = "store_error"
