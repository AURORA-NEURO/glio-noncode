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


class SourceError(GlioError):
    """Raised when a declared public or controlled source cannot be read."""

    code = "source_error"

    def __init__(self, message: str, *, receipt: object | None = None) -> None:
        super().__init__(message)
        self.receipt = receipt


class SourceRateLimitError(SourceError):
    """Raised when a source rate limit prevents a safe request."""

    code = "source_rate_limit"


class SourceNotFoundError(SourceError):
    """Raised when a source returns an explicit not-found response."""

    code = "source_not_found"
