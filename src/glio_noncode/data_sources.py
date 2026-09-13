"""Versioned public-data clients with cache, provenance, and safe failure.

The clients in this module are deliberately small and dependency-free. They
are not a replacement for bulk reference downloads; they provide bounded
lookups for case exploration and retain enough provenance to replay or reject
the result later. The supported live endpoints are:

* Ensembl REST for sequence, gene-symbol lookup, and regional feature overlap;
* UCSC Genome Browser REST for GRCh38/hg38 sequence and track queries; and
* the ENCODE portal REST API for experiment and object metadata.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import Field, dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from errno import EACCES, EAGAIN
from itertools import islice
from pathlib import Path
from types import FunctionType
from typing import Any, Protocol, cast

from . import _callback_isolation
from ._callback_isolation import (
    detached_callback_guard,
    source_callback_scope,
    source_manifest_callback_scope,
)
from .adapters import AdapterMetadata
from .errors import SourceError, SourceNotFoundError, SourceRateLimitError, ValidationError
from .identity import normalize_chromosome, variant_interval
from .models import CandidateElement, CaseManifest, ReferenceContext, VariantIdentity
from .serialization import (
    _strict_json_loads,
    canonical_bytes,
    canonical_json,
    content_hash,
    freeze_json,
    jsonable,
    utc_now,
)

MAX_SOURCE_URL_LENGTH = 8_192
MAX_SOURCE_TEXT_LENGTH = 4_096
MAX_SOURCE_RESPONSE_BYTES = 100_000_000
MAX_SOURCE_TIMEOUT_SECONDS = 120.0
MAX_SOURCE_CACHE_TTL_SECONDS = 31_536_000
MAX_SOURCE_RETRY_ATTEMPTS = 8
MAX_SOURCE_BACKOFF_SECONDS = 60.0
MAX_SOURCE_CATALOG_ENTRIES = 128
MAX_SOURCE_QUERY_PARAMETERS = 256
MAX_REFERENCE_FEATURES = 20_000
MAX_REFERENCE_VARIANTS = 1_000
MAX_REFERENCE_SEQUENCE_BP = 10_000_000
MAX_REFERENCE_BUNDLE_BYTES = 128 * 1024 * 1024
MAX_REFERENCE_RECEIPTS = 128
MAX_REFERENCE_WARNINGS = 2 * MAX_REFERENCE_VARIANTS
MAX_REFERENCE_WINDOW_BP = 5_000_000
MAX_ENRICHED_ELEMENTS = 100_000
MAX_ENRICHMENT_CANONICAL_BYTES = 256 * 1024 * 1024
MAX_ENRICHMENT_SEQUENCE_BP = 10_000_000

_REFERENCE_CONTEXT_IDENTITY_SCHEMA = "glio-noncode/reference-context"
_REFERENCE_CONTEXT_IDENTITY_VERSION = 1

_SOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_SHA256_ADDRESS = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CACHE_FIELDS = frozenset(
    {
        "request_hash",
        "source_id",
        "source_version",
        "url",
        "response_hash",
        "content_type",
        "body_hex",
        "retrieved_at",
        "expires_at",
    }
)
_CACHE_LOCKS: dict[str, threading.RLock] = {}
_CACHE_LOCKS_GUARD = threading.Lock()
_RLOCK_TYPE = type(threading.RLock())


class _SourceCallbackMutationError(ValidationError):
    """A callback altered semantic state owned by a public-source invocation."""


def _validated_utf8(value: str, label: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(f"{label} must be valid UTF-8") from exc
    return value


def _validated_canonical_bytes(value: Any, label: str) -> bytes:
    try:
        return canonical_bytes(value)
    except UnicodeError as exc:
        raise ValidationError(f"{label} must contain valid UTF-8 text") from exc
    except Exception as exc:  # noqa: BLE001 - canonical JSON is a trust boundary
        raise ValidationError(f"{label} must be representable as canonical JSON") from exc


def _validated_canonical_json(value: Any, label: str) -> str:
    return _validated_canonical_bytes(value, label).decode("utf-8")


def _canonical_reference_context(
    value: object,
    label: str,
) -> ReferenceContext:
    """Detach and validate a complete persisted reference context."""

    if type(value) is not ReferenceContext:
        raise ValidationError(f"{label} must be a ReferenceContext")
    try:
        raw = value.to_dict()
        detached = ReferenceContext.from_dict(raw, persisted=True)
        detached_raw = detached.to_dict()
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass trust boundary
        raise ValidationError(f"{label} is malformed") from exc
    if _validated_canonical_bytes(raw, label) != _validated_canonical_bytes(
        detached_raw,
        label,
    ):
        raise ValidationError(f"{label} is not an exact canonical representation")
    return detached


def _reference_context_address(context: ReferenceContext) -> str:
    """Address every context field under an explicit identity-schema version."""

    payload = {
        "schema": _REFERENCE_CONTEXT_IDENTITY_SCHEMA,
        "version": _REFERENCE_CONTEXT_IDENTITY_VERSION,
        "context": context.to_dict(),
    }
    canonical_payload = _validated_canonical_bytes(
        payload,
        "reference context identity",
    )
    return f"sha256:{hashlib.sha256(canonical_payload).hexdigest()}"


def _cache_thread_lock(path: Path) -> threading.RLock:
    key = os.path.normcase(str(path.resolve()))
    with _CACHE_LOCKS_GUARD:
        return _CACHE_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _cache_filesystem_lock(path: Path) -> Iterator[None]:
    """Serialize cache replacement across processes; locks are crash-released."""

    deadline = time.monotonic() + 30.0
    with path.open("a+b", buffering=0) as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        acquired = False
        while not acquired:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(  # type: ignore[attr-defined]
                        handle.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB,  # type: ignore[attr-defined]
                    )
                acquired = True
            except OSError as exc:
                if exc.errno not in {EACCES, EAGAIN} and getattr(exc, "winerror", None) not in {
                    33,
                    36,
                }:
                    raise
                if time.monotonic() >= deadline:
                    raise SourceError("timed out acquiring source-cache lock") from exc
                time.sleep(0.01)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(  # type: ignore[attr-defined]
                    handle.fileno(),
                    fcntl.LOCK_UN,  # type: ignore[attr-defined]
                )


def _required_text(value: object, label: str, *, maximum: int = MAX_SOURCE_TEXT_LENGTH) -> str:
    if type(value) is not str or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string")
    if len(value) > maximum:
        raise ValidationError(f"{label} exceeds the maximum length of {maximum}")
    _validated_utf8(value, label)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValidationError(f"{label} must not contain control characters")
    return value


def _bounded_int(value: object, label: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValidationError(f"{label} must be an integer between {minimum} and {maximum}")
    return value


def _bounded_number(
    value: object,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if type(value) not in {int, float}:
        raise ValidationError(f"{label} must be a finite number")
    try:
        numeric = float(cast(int | float, value))
    except OverflowError as exc:
        raise ValidationError(f"{label} must be a finite number") from exc
    if not math.isfinite(numeric) or not minimum <= numeric <= maximum:
        raise ValidationError(f"{label} must be between {minimum} and {maximum}")
    return numeric


def _http_url(value: object, label: str, *, base: bool = False) -> str:
    url = _required_text(value, label, maximum=MAX_SOURCE_URL_LENGTH)
    if url != url.strip() or "\\" in url:
        raise ValidationError(f"{label} must use canonical URL spelling")
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError(f"{label} must be a valid HTTP(S) URL") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValidationError(f"{label} must be an HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValidationError(f"{label} must not contain URL credentials")
    if port is not None and not 1 <= port <= 65_535:
        raise ValidationError(f"{label} contains an invalid port")
    if base and (parsed.query or parsed.fragment):
        raise ValidationError(f"{label} must not contain a query or fragment")
    return url


def _url_origin(value: str) -> tuple[str, str, int]:
    parsed = urllib.parse.urlsplit(_http_url(value, "source response URL"))
    scheme = parsed.scheme.lower()
    default_port = 443 if scheme == "https" else 80
    assert parsed.hostname is not None
    return scheme, parsed.hostname.rstrip(".").lower(), parsed.port or default_port


def _utc_timestamp(value: object, label: str) -> str:
    timestamp = _required_text(value, label, maximum=128)
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ValidationError(f"{label} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValidationError(f"{label} must use the UTC +00:00 offset")
    if parsed.isoformat() != timestamp:
        raise ValidationError(f"{label} must use canonical datetime.isoformat() spelling")
    return timestamp


def _sha256_address(value: object, label: str) -> str:
    address = _required_text(value, label, maximum=71)
    if _SHA256_ADDRESS.fullmatch(address) is None:
        raise ValidationError(f"{label} must be a canonical sha256 content address")
    return address


def _content_type(value: object, label: str) -> str:
    if type(value) is not str or len(value) > 256:
        raise ValidationError(f"{label} must be a string of at most 256 characters")
    _validated_utf8(value, label)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValidationError(f"{label} must not contain control characters")
    return value


def _safe_error_message(value: object) -> str:
    text = str(value)
    normalized = "".join(
        (
            " "
            if ord(character) < 32 or ord(character) == 127
            else "\ufffd"
            if 0xD800 <= ord(character) <= 0xDFFF
            else character
        )
        for character in text
    ).strip()
    return normalized[:MAX_SOURCE_TEXT_LENGTH].rstrip() or "unknown source failure"


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object field: {key}")
        value[key] = item
    return value


def _invalid_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


@dataclass(frozen=True, slots=True)
class ReferenceRetrievalLimits:
    """Downward-configurable work ceilings for live reference enrichment.

    The aggregate defaults cap one complete enrichment closure at 256 MiB of
    canonical JSON and ten million retained reference-sequence bases.
    """

    max_window_bp: int = MAX_REFERENCE_WINDOW_BP
    max_features_per_variant: int = MAX_REFERENCE_FEATURES
    max_variants: int = MAX_REFERENCE_VARIANTS
    max_total_elements: int = MAX_ENRICHED_ELEMENTS
    max_total_canonical_bytes: int = MAX_ENRICHMENT_CANONICAL_BYTES
    max_total_sequence_bp: int = MAX_ENRICHMENT_SEQUENCE_BP

    def __post_init__(self) -> None:
        for field_name, ceiling in (
            ("max_window_bp", MAX_REFERENCE_WINDOW_BP),
            ("max_features_per_variant", MAX_REFERENCE_FEATURES),
            ("max_variants", MAX_REFERENCE_VARIANTS),
            ("max_total_elements", MAX_ENRICHED_ELEMENTS),
            ("max_total_canonical_bytes", MAX_ENRICHMENT_CANONICAL_BYTES),
            ("max_total_sequence_bp", MAX_ENRICHMENT_SEQUENCE_BP),
        ):
            _bounded_int(
                getattr(self, field_name),
                f"reference limits {field_name}",
                minimum=1,
                maximum=ceiling,
            )


DEFAULT_REFERENCE_RETRIEVAL_LIMITS = ReferenceRetrievalLimits()


class SourceKind(str, Enum):  # noqa: UP042 - persisted enum string behavior is compatibility-sensitive.
    STANDARD = "standard"
    REFERENCE_PORTAL = "reference_portal"
    REFERENCE_ANNOTATION = "reference_annotation"
    GENOME_BROWSER = "genome_browser"
    FUNCTIONAL_GENOMICS = "functional_genomics"
    COHORT = "cohort"


class SourceAccess(str, Enum):  # noqa: UP042 - persisted enum string behavior is compatibility-sensitive.
    PUBLIC_API = "public_api"
    PUBLIC_DOWNLOAD = "public_download"
    CONTROLLED = "controlled"
    LOCAL_ONLY = "local_only"


class FetchStatus(str, Enum):  # noqa: UP042 - persisted enum string behavior is compatibility-sensitive.
    FETCHED = "fetched"
    CACHE_HIT = "cache_hit"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Machine-readable identity and access contract for one source."""

    source_id: str
    name: str
    kind: SourceKind
    access: SourceAccess
    base_url: str
    canonical_url: str
    version: str
    license: str
    rate_limit_per_minute: int = 60
    max_response_bytes: int = 25_000_000
    max_region_bp: int | None = None
    terms: str = ""
    enabled: bool = True

    def __post_init__(self) -> None:
        source_id = _required_text(self.source_id, "source source_id", maximum=128)
        if _SOURCE_ID.fullmatch(source_id) is None:
            raise ValidationError("source source_id contains unsupported characters")
        for name in ("name", "version", "license"):
            _required_text(getattr(self, name), f"source {name}")
        if type(self.terms) is not str or len(self.terms) > MAX_SOURCE_TEXT_LENGTH:
            raise ValidationError(
                f"source terms must be a string of at most {MAX_SOURCE_TEXT_LENGTH} characters"
            )
        _validated_utf8(self.terms, "source terms")
        if any(ord(character) < 32 or ord(character) == 127 for character in self.terms):
            raise ValidationError("source terms must not contain control characters")
        if not isinstance(self.kind, SourceKind) or not isinstance(self.access, SourceAccess):
            raise ValidationError("source kind and access must use their declared enums")
        _http_url(self.base_url, "source base_url", base=True)
        _http_url(self.canonical_url, "source canonical_url")
        _bounded_int(
            self.rate_limit_per_minute,
            "source rate_limit_per_minute",
            minimum=1,
            maximum=1_000_000,
        )
        _bounded_int(
            self.max_response_bytes,
            "source max_response_bytes",
            minimum=1_024,
            maximum=MAX_SOURCE_RESPONSE_BYTES,
        )
        if self.max_region_bp is not None:
            _bounded_int(
                self.max_region_bp,
                "source max_region_bp",
                minimum=1,
                maximum=1_000_000_000,
            )
        if type(self.enabled) is not bool:
            raise ValidationError("source enabled must be a boolean")

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], jsonable(self))


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry only transport/server failures with unchanged request semantics."""

    attempts: int = 3
    initial_backoff_seconds: float = 0.25
    maximum_backoff_seconds: float = 4.0
    retry_statuses: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)

    def __post_init__(self) -> None:
        _bounded_int(
            self.attempts,
            "retry attempts",
            minimum=1,
            maximum=MAX_SOURCE_RETRY_ATTEMPTS,
        )
        initial = _bounded_number(
            self.initial_backoff_seconds,
            "retry initial_backoff_seconds",
            minimum=0.0,
            maximum=MAX_SOURCE_BACKOFF_SECONDS,
        )
        maximum = _bounded_number(
            self.maximum_backoff_seconds,
            "retry maximum_backoff_seconds",
            minimum=0.0,
            maximum=MAX_SOURCE_BACKOFF_SECONDS,
        )
        if maximum < initial:
            raise ValidationError("retry maximum backoff must not be below initial backoff")
        if type(self.retry_statuses) is not tuple or not self.retry_statuses:
            raise ValidationError("retry statuses must be a non-empty tuple")
        if len(self.retry_statuses) > 500:
            raise ValidationError("retry statuses cannot exceed 500 entries")
        statuses = tuple(
            _bounded_int(status, "retry HTTP status", minimum=100, maximum=599)
            for status in self.retry_statuses
        )
        if len(statuses) != len(set(statuses)):
            raise ValidationError("retry statuses must be unique")
        if statuses != tuple(sorted(statuses)):
            raise ValidationError("retry statuses must use canonical ascending order")
        if any(status not in {408, 425, 429} and status < 500 for status in statuses):
            raise ValidationError(
                "retry statuses must identify timeout, rate-limit, or 5xx failures"
            )

    def backoff(self, retry_number: int) -> float:
        _bounded_int(
            retry_number,
            "retry number",
            minimum=0,
            maximum=self.attempts - 1,
        )
        return float(
            min(
                self.maximum_backoff_seconds,
                self.initial_backoff_seconds * (2**retry_number),
            )
        )


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """Raw bounded HTTP response before source-specific decoding."""

    status: int
    url: str
    headers: Mapping[str, str]
    body: bytes
    elapsed_seconds: float

    def __post_init__(self) -> None:
        _bounded_int(self.status, "transport status", minimum=100, maximum=599)
        _http_url(self.url, "transport response URL")
        if not isinstance(self.headers, Mapping):
            raise ValidationError("transport response headers must be an object")
        if len(self.headers) > MAX_SOURCE_QUERY_PARAMETERS:
            raise ValidationError(
                f"transport response cannot exceed {MAX_SOURCE_QUERY_PARAMETERS} headers"
            )
        copied_headers: dict[str, str] = {}
        for key, value in self.headers.items():
            header_name = _required_text(key, "transport header name", maximum=256).lower()
            header_value = _required_text(value, "transport header value", maximum=8_192)
            if header_name in copied_headers:
                raise ValidationError(f"duplicate transport response header: {header_name}")
            copied_headers[header_name] = header_value
        if type(self.body) is not bytes:
            raise ValidationError("transport response body must be bytes")
        if len(self.body) > MAX_SOURCE_RESPONSE_BYTES:
            raise ValidationError(
                f"transport response body exceeds {MAX_SOURCE_RESPONSE_BYTES} bytes"
            )
        _bounded_number(
            self.elapsed_seconds,
            "transport elapsed_seconds",
            minimum=0.0,
            maximum=86_400.0,
        )
        object.__setattr__(
            self,
            "headers",
            freeze_json(copied_headers, field="transport response headers"),
        )

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";", 1)[0].strip().lower()


class HttpTransport(Protocol):
    """Minimal transport seam used by live code and deterministic tests."""

    def request(
        self, method: str, url: str, headers: Mapping[str, str], timeout_seconds: float
    ) -> TransportResponse: ...


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject a redirect before urllib contacts a different origin."""

    def __init__(self, origin: tuple[str, str, int]) -> None:
        super().__init__()
        self.origin = origin

    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> urllib.request.Request | None:
        if _url_origin(new_url) != self.origin:
            raise ValidationError("source redirect escaped the configured request origin")
        return super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            new_url,
        )


class UrllibTransport:
    """Standard-library HTTPS transport with a hard response-size limit."""

    def __init__(self, *, max_response_bytes: int = 25_000_000) -> None:
        self.max_response_bytes = _bounded_int(
            max_response_bytes,
            "transport max_response_bytes",
            minimum=1_024,
            maximum=MAX_SOURCE_RESPONSE_BYTES,
        )

    def request(
        self, method: str, url: str, headers: Mapping[str, str], timeout_seconds: float
    ) -> TransportResponse:
        method = _required_text(method, "transport method", maximum=16).upper()
        if method != "GET":
            raise ValidationError("public source transport only supports GET")
        _http_url(url, "transport request URL")
        _bounded_number(
            timeout_seconds,
            "transport timeout_seconds",
            minimum=0.001,
            maximum=MAX_SOURCE_TIMEOUT_SECONDS,
        )
        started = time.monotonic()
        request = urllib.request.Request(url, method=method, headers=dict(headers))
        opener = urllib.request.build_opener(_SameOriginRedirectHandler(_url_origin(url)))
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = response.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise ValidationError(
                        f"source response exceeded {self.max_response_bytes} bytes"
                    )
                response_headers = {key.lower(): value for key, value in response.headers.items()}
                return TransportResponse(
                    status=int(response.status),
                    url=response.geturl(),
                    headers=response_headers,
                    body=body,
                    elapsed_seconds=round(time.monotonic() - started, 6),
                )
        except urllib.error.HTTPError as error:
            body = error.read(self.max_response_bytes + 1)
            if len(body) > self.max_response_bytes:
                raise ValidationError(
                    f"source error response exceeded {self.max_response_bytes} bytes"
                ) from error
            response_headers = {key.lower(): value for key, value in error.headers.items()}
            return TransportResponse(
                status=int(error.code),
                url=error.geturl(),
                headers=response_headers,
                body=body,
                elapsed_seconds=round(time.monotonic() - started, 6),
            )
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise SourceError(f"transport failure for {url}: {error}") from error


class RateLimiter:
    """Thread-safe spacing limiter for one public source."""

    def __init__(self, requests_per_minute: int) -> None:
        _bounded_int(
            requests_per_minute,
            "requests_per_minute",
            minimum=1,
            maximum=1_000_000,
        )
        self.interval_seconds = 60.0 / requests_per_minute
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self, *, max_wait_seconds: float = 30.0) -> float:
        _bounded_number(
            max_wait_seconds,
            "max_wait_seconds",
            minimum=0.0,
            maximum=MAX_SOURCE_TIMEOUT_SECONDS,
        )
        with self._lock:
            now = time.monotonic()
            wait_seconds = max(0.0, self._next_allowed - now)
            if wait_seconds > max_wait_seconds:
                raise SourceRateLimitError(
                    f"source spacing would require waiting {wait_seconds:.2f}s"
                )
            if wait_seconds:
                time.sleep(wait_seconds)
            self._next_allowed = max(time.monotonic(), self._next_allowed) + self.interval_seconds
            return round(wait_seconds, 6)


@dataclass(frozen=True, slots=True)
class FetchReceipt:
    """Provenance for one source request or cache result."""

    source_id: str
    source_version: str
    url: str
    request_hash: str
    response_hash: str | None
    status: FetchStatus
    http_status: int | None
    attempts: int
    retrieved_at: str
    elapsed_seconds: float | None
    cache_expires_at: str | None
    warnings: tuple[str, ...] = ()
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        source_id = _required_text(self.source_id, "receipt source_id", maximum=128)
        if _SOURCE_ID.fullmatch(source_id) is None:
            raise ValidationError("receipt source_id contains unsupported characters")
        _required_text(self.source_version, "receipt source_version")
        _http_url(self.url, "receipt URL")
        _sha256_address(self.request_hash, "receipt request_hash")
        if self.response_hash is not None:
            _sha256_address(self.response_hash, "receipt response_hash")
        if type(self.status) is not FetchStatus:
            raise ValidationError("receipt status must be a FetchStatus")
        if self.http_status is not None:
            _bounded_int(
                self.http_status,
                "receipt http_status",
                minimum=100,
                maximum=599,
            )
        _bounded_int(
            self.attempts,
            "receipt attempts",
            minimum=0,
            maximum=MAX_SOURCE_RETRY_ATTEMPTS,
        )
        retrieved_at = datetime.fromisoformat(
            _utc_timestamp(self.retrieved_at, "receipt retrieved_at")
        )
        if self.elapsed_seconds is not None:
            _bounded_number(
                self.elapsed_seconds,
                "receipt elapsed_seconds",
                minimum=0.0,
                maximum=86_400.0,
            )
        if self.cache_expires_at is not None:
            expires_at = datetime.fromisoformat(
                _utc_timestamp(self.cache_expires_at, "receipt cache_expires_at")
            )
            if expires_at <= retrieved_at:
                raise ValidationError("receipt cache expiry must follow retrieval")
            if expires_at - retrieved_at > timedelta(seconds=MAX_SOURCE_CACHE_TTL_SECONDS):
                raise ValidationError("receipt cache expiry exceeds the maximum cache TTL")
        if type(self.warnings) is not tuple or len(self.warnings) > MAX_SOURCE_QUERY_PARAMETERS:
            raise ValidationError(
                f"receipt warnings must be a tuple of at most {MAX_SOURCE_QUERY_PARAMETERS} items"
            )
        for warning in self.warnings:
            _required_text(warning, "receipt warning")
        if len(self.warnings) != len(set(self.warnings)):
            raise ValidationError("receipt warnings must be unique")
        if (self.error_type is None) != (self.error_message is None):
            raise ValidationError("receipt error_type and error_message must appear together")
        if self.error_type is not None:
            _required_text(self.error_type, "receipt error_type", maximum=256)
            _required_text(self.error_message, "receipt error_message")

        success_statuses = {
            FetchStatus.FETCHED,
            FetchStatus.CACHE_HIT,
            FetchStatus.NOT_FOUND,
        }
        failure_statuses = {FetchStatus.FAILED, FetchStatus.RATE_LIMITED}
        if self.status in success_statuses and self.response_hash is None:
            raise ValidationError("successful or not-found receipt requires a response hash")
        if self.status in failure_statuses and self.error_type is None:
            raise ValidationError("failed receipt requires error details")
        if self.status in success_statuses and self.error_type is not None:
            raise ValidationError("non-failure receipt must not contain error details")
        if self.http_status is not None and self.response_hash is None:
            raise ValidationError("receipt with an HTTP status requires a response hash")
        if self.status is FetchStatus.CACHE_HIT:
            if self.attempts != 0 or self.http_status != 200:
                raise ValidationError("cache-hit receipt requires zero attempts and HTTP 200")
        elif self.status is FetchStatus.FETCHED:
            if self.attempts < 1 or self.http_status is None or not 200 <= self.http_status < 300:
                raise ValidationError("fetched receipt requires an attempt and a 2xx status")
        elif self.status is FetchStatus.NOT_FOUND:
            if self.attempts < 1 or self.http_status != 404:
                raise ValidationError("not-found receipt requires an attempt and HTTP 404")
        elif self.status is FetchStatus.FAILED and self.attempts < 1:
            raise ValidationError("failed receipt requires at least one attempted request")
        elif (
            self.status is FetchStatus.RATE_LIMITED
            and self.attempts == 0
            and self.http_status is not None
        ):
            raise ValidationError(
                "rate-limited receipt with zero attempts must not claim an HTTP status"
            )
        elif (
            self.status is FetchStatus.RATE_LIMITED
            and self.http_status is not None
            and self.http_status != 429
        ):
            raise ValidationError("rate-limited receipt HTTP status must be 429")

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], jsonable(self))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> FetchReceipt:
        """Rehydrate one exact persisted receipt through all source invariants."""

        expected_fields = frozenset(
            {
                "source_id",
                "source_version",
                "url",
                "request_hash",
                "response_hash",
                "status",
                "http_status",
                "attempts",
                "retrieved_at",
                "elapsed_seconds",
                "cache_expires_at",
                "warnings",
                "error_type",
                "error_message",
            }
        )
        if not isinstance(raw, Mapping) or any(type(key) is not str for key in raw):
            raise ValidationError("fetch receipt must be an exact JSON object")
        if frozenset(raw) != expected_fields:
            raise ValidationError("fetch receipt fields are not exact")
        if type(raw["status"]) is not str:
            raise ValidationError("fetch receipt status must be a string")
        if type(raw["warnings"]) is not list:
            raise ValidationError("fetch receipt warnings must be an exact array")
        if len(raw["warnings"]) > MAX_SOURCE_QUERY_PARAMETERS:
            raise ValidationError("fetch receipt warnings exceed their hard ceiling")
        try:
            result = cls(
                source_id=raw["source_id"],
                source_version=raw["source_version"],
                url=raw["url"],
                request_hash=raw["request_hash"],
                response_hash=raw["response_hash"],
                status=FetchStatus(raw["status"]),
                http_status=raw["http_status"],
                attempts=raw["attempts"],
                retrieved_at=raw["retrieved_at"],
                elapsed_seconds=raw["elapsed_seconds"],
                cache_expires_at=raw["cache_expires_at"],
                warnings=tuple(raw["warnings"]),
                error_type=raw["error_type"],
                error_message=raw["error_message"],
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError("fetch receipt is invalid") from exc
        if _validated_canonical_bytes(
            result.to_dict(), "fetch receipt"
        ) != _validated_canonical_bytes(raw, "fetch receipt"):
            raise ValidationError("fetch receipt is not an exact canonical representation")
        return result


@dataclass(frozen=True, slots=True)
class SourcePayload:
    """Decoded payload plus its receipt; payloads are never anonymous."""

    value: Any
    receipt: FetchReceipt
    content_type: str

    def __post_init__(self) -> None:
        if type(self.receipt) is not FetchReceipt:
            raise ValidationError("source payload receipt must be a FetchReceipt")
        _content_type(self.content_type, "source payload content_type")
        frozen_value = freeze_json(self.value, field="source payload value")
        _validated_canonical_bytes(frozen_value, "source payload value")
        object.__setattr__(
            self,
            "value",
            frozen_value,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "receipt": self.receipt.to_dict(),
            "content_type": self.content_type,
        }


@dataclass(frozen=True, slots=True)
class CacheEntry:
    request_hash: str
    source_id: str
    source_version: str
    url: str
    response_hash: str
    content_type: str
    body: bytes
    retrieved_at: str
    expires_at: str

    def __post_init__(self) -> None:
        _sha256_address(self.request_hash, "cache request_hash")
        source_id = _required_text(self.source_id, "cache source_id", maximum=128)
        if _SOURCE_ID.fullmatch(source_id) is None:
            raise ValidationError("cache source_id contains unsupported characters")
        _required_text(self.source_version, "cache source_version")
        _http_url(self.url, "cache URL")
        if type(self.response_hash) is not str or re.fullmatch(
            r"[0-9a-f]{64}", self.response_hash
        ) is None:
            raise ValidationError("cache response_hash must be a lowercase SHA-256 digest")
        _content_type(self.content_type, "cache content_type")
        if type(self.body) is not bytes or len(self.body) > MAX_SOURCE_RESPONSE_BYTES:
            raise ValidationError(
                f"cache body must be bytes within {MAX_SOURCE_RESPONSE_BYTES} bytes"
            )
        if hashlib.sha256(self.body).hexdigest() != self.response_hash:
            raise ValidationError("cache response hash does not match its body")
        retrieved_at = datetime.fromisoformat(
            _utc_timestamp(self.retrieved_at, "cache retrieved_at")
        )
        expires_at = datetime.fromisoformat(_utc_timestamp(self.expires_at, "cache expires_at"))
        if expires_at <= retrieved_at:
            raise ValidationError("cache expiry must follow retrieval")
        if expires_at - retrieved_at > timedelta(seconds=MAX_SOURCE_CACHE_TTL_SECONDS):
            raise ValidationError("cache expiry exceeds the maximum cache TTL")


class SourceCache:
    """Filesystem cache keyed by request hash and protected by atomic writes."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks = self.root / ".locks"
        self._locks.mkdir(parents=True, exist_ok=True)
        self._lock = _cache_thread_lock(self.root)

    def _path(self, request_hash: str) -> Path:
        if type(request_hash) is not str or _SHA256_ADDRESS.fullmatch(request_hash) is None:
            raise ValidationError(f"invalid request hash: {request_hash}")
        digest = request_hash[7:]
        return self.root / f"{digest}.json"

    def get(
        self,
        request_hash: str,
        *,
        now: datetime | None = None,
        source: SourceSpec | None = None,
        expected_url: str | None = None,
        max_response_bytes: int = MAX_SOURCE_RESPONSE_BYTES,
    ) -> CacheEntry | None:
        """Return an exact, unexpired cache entry or fail closed as a cache miss."""

        if source is not None and not isinstance(source, SourceSpec):
            raise ValidationError("cache source must be a SourceSpec")
        if expected_url is not None:
            expected_url = _http_url(expected_url, "cache expected_url")
            if source is not None and _url_origin(expected_url) != _url_origin(source.base_url):
                raise ValidationError("cache expected_url must remain on the source origin")
        if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
            raise ValidationError("cache now must be a timezone-aware datetime")
        maximum = _bounded_int(
            max_response_bytes,
            "cache max_response_bytes",
            minimum=1_024,
            maximum=MAX_SOURCE_RESPONSE_BYTES,
        )
        path = self._path(request_hash)
        if not path.exists():
            return None
        try:
            if path.stat().st_size > maximum * 2 + 32_768:
                return None
            raw = _strict_json_loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=_unique_json_object,
                parse_constant=_invalid_json_constant,
            )
            if type(raw) is not dict or frozenset(raw) != _CACHE_FIELDS:
                return None
            if any(type(key) is not str for key in raw):
                return None
            if raw["request_hash"] != request_hash:
                return None
            source_id = _required_text(raw["source_id"], "cache source_id", maximum=128)
            source_version = _required_text(raw["source_version"], "cache source_version")
            url = _http_url(raw["url"], "cache URL")
            if expected_url is not None and url != expected_url:
                return None
            response_hash = raw["response_hash"]
            if (
                type(response_hash) is not str
                or re.fullmatch(r"[0-9a-f]{64}", response_hash) is None
            ):
                return None
            content_type = _content_type(raw["content_type"], "cache content_type")
            body_hex = raw["body_hex"]
            if type(body_hex) is not str or len(body_hex) > maximum * 2:
                return None
            if len(body_hex) % 2 or re.fullmatch(r"[0-9a-f]*", body_hex) is None:
                return None
            body = bytes.fromhex(body_hex)
            if len(body) > maximum or hashlib.sha256(body).hexdigest() != response_hash:
                return None
            retrieved_text = _utc_timestamp(raw["retrieved_at"], "cache retrieved_at")
            expires_text = _utc_timestamp(raw["expires_at"], "cache expires_at")
            retrieved_at = datetime.fromisoformat(retrieved_text)
            expires_at = datetime.fromisoformat(expires_text)
            current = now or datetime.now(UTC)
            if not isinstance(current, datetime) or current.tzinfo is None:
                return None
            if expires_at <= retrieved_at or expires_at <= current:
                return None
            if expires_at - retrieved_at > timedelta(seconds=MAX_SOURCE_CACHE_TTL_SECONDS):
                return None
            if source is not None:
                if source_id != source.source_id or source_version != source.version:
                    return None
                if _url_origin(url) != _url_origin(source.base_url):
                    return None
            return CacheEntry(
                request_hash=request_hash,
                source_id=source_id,
                source_version=source_version,
                url=url,
                response_hash=response_hash,
                content_type=content_type,
                body=body,
                retrieved_at=retrieved_text,
                expires_at=expires_text,
            )
        except (OSError, RecursionError, TypeError, ValueError, ValidationError):
            return None

    def put(
        self,
        *,
        request_hash: str,
        source: SourceSpec,
        url: str,
        body: bytes,
        content_type: str,
        ttl_seconds: int,
    ) -> CacheEntry:
        if not isinstance(source, SourceSpec):
            raise ValidationError("cache source must be a SourceSpec")
        if type(body) is not bytes or len(body) > source.max_response_bytes:
            raise ValidationError(
                f"cache body must be bytes within {source.max_response_bytes} bytes"
            )
        _http_url(url, "cache URL")
        if _url_origin(url) != _url_origin(source.base_url):
            raise ValidationError("cache URL must remain on the configured source origin")
        content_type = _content_type(content_type, "cache content_type")
        ttl_seconds = _bounded_int(
            ttl_seconds,
            "cache TTL",
            minimum=1,
            maximum=MAX_SOURCE_CACHE_TTL_SECONDS,
        )
        retrieved = datetime.now(UTC)
        entry = CacheEntry(
            request_hash=request_hash,
            source_id=source.source_id,
            source_version=source.version,
            url=url,
            response_hash=hashlib.sha256(body).hexdigest(),
            content_type=content_type,
            body=body,
            retrieved_at=retrieved.isoformat(),
            expires_at=(retrieved + timedelta(seconds=ttl_seconds)).isoformat(),
        )
        path = self._path(request_hash)
        serialized = canonical_json(
            {
                "request_hash": entry.request_hash,
                "source_id": entry.source_id,
                "source_version": entry.source_version,
                "url": entry.url,
                "response_hash": entry.response_hash,
                "content_type": entry.content_type,
                "body_hex": entry.body.hex(),
                "retrieved_at": entry.retrieved_at,
                "expires_at": entry.expires_at,
            }
        )
        with self._lock, _cache_filesystem_lock(self._locks / f"{path.stem}.lock"):
            descriptor, temporary_name = tempfile.mkstemp(
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                text=True,
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                    handle.write(serialized)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        return entry


class SourceCatalog:
    """Registry of source metadata used by clients and release reports."""

    def __init__(self, specs: Iterable[SourceSpec] = ()) -> None:
        self._specs: dict[str, SourceSpec] = {}
        self._lock = threading.RLock()
        try:
            iterator = iter(specs)
        except TypeError as exc:
            raise ValidationError("source specs must be iterable") from exc
        for spec in iterator:
            self.register(spec)

    def register(self, spec: SourceSpec) -> None:
        if not isinstance(spec, SourceSpec):
            raise ValidationError("source catalog entries must be SourceSpec objects")
        with self._lock:
            if spec.source_id in self._specs:
                raise ValidationError(f"source already registered: {spec.source_id}")
            if len(self._specs) >= MAX_SOURCE_CATALOG_ENTRIES:
                raise ValidationError(
                    f"source catalog cannot exceed {MAX_SOURCE_CATALOG_ENTRIES} entries"
                )
            self._specs[spec.source_id] = spec

    def get(self, source_id: str) -> SourceSpec:
        if type(source_id) is not str or _SOURCE_ID.fullmatch(source_id) is None:
            raise SourceError("source identifier is invalid")
        with self._lock:
            try:
                return self._specs[source_id]
            except KeyError as exc:
                raise SourceError(f"source is not registered: {source_id}") from exc

    def list(self) -> tuple[SourceSpec, ...]:
        with self._lock:
            return tuple(self._specs[key] for key in sorted(self._specs))

    def manifest(self) -> dict[str, Any]:
        specs = self.list()
        return {
            "sources": [spec.to_dict() for spec in specs],
            "content_address": content_hash([spec.to_dict() for spec in specs]),
        }


def default_source_catalog() -> SourceCatalog:
    """Return source metadata for the live adapters implemented here."""

    return SourceCatalog(
        (
            SourceSpec(
                source_id="SRC-ENSEMBL-REST",
                name="Ensembl REST",
                kind=SourceKind.REFERENCE_ANNOTATION,
                access=SourceAccess.PUBLIC_API,
                base_url="https://rest.ensembl.org",
                canonical_url="https://rest.ensembl.org/",
                version="live",
                license="Ensembl data use terms",
                rate_limit_per_minute=45,
                max_region_bp=5_000_000,
                terms=(
                    "Regional overlap is bounded; feature semantics and release version "
                    "must be recorded."
                ),
            ),
            SourceSpec(
                source_id="SRC-UCSC-REST",
                name="UCSC Genome Browser REST",
                kind=SourceKind.GENOME_BROWSER,
                access=SourceAccess.PUBLIC_API,
                base_url="https://api.genome.ucsc.edu",
                canonical_url="https://www.genome.ucsc.edu/goldenPath/help/api.html",
                version="live",
                license="UCSC Genome Browser data use terms",
                rate_limit_per_minute=45,
                max_region_bp=10_000_000,
                terms=(
                    "Small-window sequence and track requests only; bulk data should use "
                    "downloads."
                ),
            ),
            SourceSpec(
                source_id="SRC-ENCODE-REST",
                name="ENCODE Project REST",
                kind=SourceKind.FUNCTIONAL_GENOMICS,
                access=SourceAccess.PUBLIC_API,
                base_url="https://www.encodeproject.org",
                canonical_url="https://www.encodeproject.org/help/rest-api/",
                version="live",
                license="ENCODE data use and licensing terms",
                rate_limit_per_minute=30,
                terms=(
                    "Metadata retrieval only in this module; assay files require separate "
                    "access and QC."
                ),
            ),
        )
    )


class SourceClient:
    """Shared request, cache, retry, and receipt implementation."""

    def __init__(
        self,
        catalog: SourceCatalog | None = None,
        *,
        cache_root: str | Path = ".glio/source-cache",
        transport: HttpTransport | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout_seconds: float = 20.0,
        cache_ttl_seconds: int = 86_400,
        user_agent: str = "glio-noncode/0.2 (research-use-only)",
    ) -> None:
        selected_catalog = default_source_catalog() if catalog is None else catalog
        if not isinstance(selected_catalog, SourceCatalog):
            raise ValidationError("catalog must be a SourceCatalog")
        catalog_specs = selected_catalog.list()
        catalog_snapshot = SourceCatalog(catalog_specs)
        selected_transport = (
            UrllibTransport(
                max_response_bytes=max(
                    (spec.max_response_bytes for spec in catalog_specs),
                    default=25_000_000,
                )
            )
            if transport is None
            else transport
        )
        if not callable(getattr(selected_transport, "request", None)):
            raise ValidationError("transport must provide a request method")
        selected_retry_policy = RetryPolicy() if retry_policy is None else retry_policy
        if not isinstance(selected_retry_policy, RetryPolicy):
            raise ValidationError("retry_policy must be a RetryPolicy")
        selected_timeout = _bounded_number(
            timeout_seconds,
            "source timeout_seconds",
            minimum=0.001,
            maximum=MAX_SOURCE_TIMEOUT_SECONDS,
        )
        selected_cache_ttl = _bounded_int(
            cache_ttl_seconds,
            "source cache_ttl_seconds",
            minimum=1,
            maximum=MAX_SOURCE_CACHE_TTL_SECONDS,
        )
        selected_user_agent = _required_text(user_agent, "source user_agent", maximum=512)
        self.catalog = catalog_snapshot
        self.transport = selected_transport
        self.retry_policy = selected_retry_policy
        self.timeout_seconds = selected_timeout
        self.cache_ttl_seconds = selected_cache_ttl
        self.user_agent = selected_user_agent
        self.cache = SourceCache(cache_root)
        self._limiters = {
            spec.source_id: RateLimiter(spec.rate_limit_per_minute) for spec in self.catalog.list()
        }

    def build_url(
        self, source: SourceSpec, path: str, params: Mapping[str, Any] | None = None
    ) -> str:
        if not isinstance(source, SourceSpec):
            raise ValidationError("source must be a SourceSpec")
        path = _required_text(path, "source request path", maximum=4_096)
        parsed_path = urllib.parse.urlsplit(path)
        if parsed_path.scheme or parsed_path.netloc or parsed_path.query or parsed_path.fragment:
            raise ValidationError(
                "source request path must be a relative path with no query or fragment"
            )
        if not path.startswith("/"):
            path = "/" + path
        url = source.base_url.rstrip("/") + path
        if params is not None and not isinstance(params, Mapping):
            raise ValidationError("source request parameters must be an object")
        if params is not None and len(params) > MAX_SOURCE_QUERY_PARAMETERS:
            raise ValidationError(
                f"source request cannot exceed {MAX_SOURCE_QUERY_PARAMETERS} parameters"
            )
        clean: dict[str, Any] = {}
        parameter_items = () if params is None else params.items()
        for index, (key, value) in enumerate(parameter_items):
            if index >= MAX_SOURCE_QUERY_PARAMETERS:
                raise ValidationError(
                    f"source request cannot exceed {MAX_SOURCE_QUERY_PARAMETERS} parameters"
                )
            name = _required_text(key, "source request parameter name", maximum=256)
            if name in clean:
                raise ValidationError(f"duplicate source request parameter: {name}")
            if value is None:
                continue
            values = value if isinstance(value, (list, tuple)) else (value,)
            if not values:
                raise ValidationError("source request parameter values must not be empty")
            if len(values) > MAX_SOURCE_QUERY_PARAMETERS:
                raise ValidationError("source request parameter contains too many values")
            normalized: list[str | int | float] = []
            for item in values:
                if type(item) is str:
                    normalized.append(
                        _required_text(item, "source request parameter value", maximum=4_096)
                    )
                elif type(item) is int:
                    normalized.append(item)
                elif type(item) is float and math.isfinite(item):
                    normalized.append(item)
                else:
                    raise ValidationError(
                        "source request parameter values must be finite strings or numbers"
                    )
            clean[name] = normalized if isinstance(value, (list, tuple)) else normalized[0]
        if clean:
            url += "?" + urllib.parse.urlencode(sorted(clean.items()), doseq=True)
        if len(url) > MAX_SOURCE_URL_LENGTH:
            raise ValidationError(f"source request URL exceeds {MAX_SOURCE_URL_LENGTH} characters")
        if _url_origin(url) != _url_origin(source.base_url):
            raise ValidationError("source request URL escaped the configured source origin")
        return url

    def fetch_json(
        self,
        source_id: str,
        path: str,
        params: Mapping[str, Any] | None = None,
        *,
        allow_not_found: bool = False,
        cache: bool = True,
        _integrity_guard: Callable[[], None] | None = None,
    ) -> SourcePayload:
        return self._fetch(
            source_id,
            path,
            params,
            expect_json=True,
            allow_not_found=allow_not_found,
            cache=cache,
            _integrity_guard=_integrity_guard,
        )

    def fetch_text(
        self,
        source_id: str,
        path: str,
        params: Mapping[str, Any] | None = None,
        *,
        allow_not_found: bool = False,
        cache: bool = True,
        _integrity_guard: Callable[[], None] | None = None,
    ) -> SourcePayload:
        return self._fetch(
            source_id,
            path,
            params,
            expect_json=False,
            allow_not_found=allow_not_found,
            cache=cache,
            _integrity_guard=_integrity_guard,
        )

    def _fetch(
        self,
        source_id: str,
        path: str,
        params: Mapping[str, Any] | None,
        *,
        expect_json: bool,
        allow_not_found: bool,
        cache: bool,
        _integrity_guard: Callable[[], None] | None,
    ) -> SourcePayload:
        for value, label in (
            (expect_json, "expect_json"),
            (allow_not_found, "allow_not_found"),
            (cache, "cache"),
        ):
            if type(value) is not bool:
                raise ValidationError(f"source {label} must be a boolean")
        if _integrity_guard is not None and not callable(_integrity_guard):
            raise ValidationError("source integrity guard must be callable or None")
        source = self.catalog.get(source_id)
        if not source.enabled:
            raise SourceError(f"source is disabled: {source_id}")
        url = self.build_url(source, path, params)
        request_hash = content_hash(
            {
                "source_id": source.source_id,
                "source_version": source.version,
                "url": url,
                "expect_json": expect_json,
            }
        )
        cached = (
            self.cache.get(
                request_hash,
                source=source,
                expected_url=url,
                max_response_bytes=source.max_response_bytes,
            )
            if cache
            else None
        )
        if cached is not None:
            receipt = FetchReceipt(
                source_id=source.source_id,
                source_version=source.version,
                url=cached.url,
                request_hash=request_hash,
                response_hash=f"sha256:{cached.response_hash}",
                status=FetchStatus.CACHE_HIT,
                http_status=200,
                attempts=0,
                retrieved_at=cached.retrieved_at,
                elapsed_seconds=0.0,
                cache_expires_at=cached.expires_at,
                warnings=("served from local source cache",),
            )
            try:
                return self._decode(cached.body, receipt, cached.content_type, expect_json)
            except SourceError:
                # A hash-valid legacy cache entry may still violate the requested media contract.
                # Treat it as a miss so a current response can repair the entry.
                pass
        limiter = self._limiters[source.source_id]
        headers = {
            "Accept": "application/json" if expect_json else "text/plain,application/json",
            "User-Agent": self.user_agent,
        }
        source_rate_limit_error_type = SourceRateLimitError
        validation_error_type = ValidationError
        source_error_type = SourceError
        exception_type = Exception
        last_response: TransportResponse | None = None
        last_error: Exception | None = None
        attempts_made = 0
        for attempt in range(1, self.retry_policy.attempts + 1):
            last_response = None
            try:
                limiter.wait()
            except SourceRateLimitError as error:
                last_error = error
                break
            attempts_made = attempt
            callback_mutation_error = _SourceCallbackMutationError
            limiter_states = (
                tuple(
                    (
                        candidate,
                        object.__getattribute__(candidate, "_next_allowed"),
                    )
                    for candidate in self._limiters.values()
                )
                if _integrity_guard is not None
                else ()
            )

            def check_transport_integrity(
                limiter_states: tuple[tuple[RateLimiter, float], ...] = limiter_states,
                callback_mutation_error: type[
                    _SourceCallbackMutationError
                ] = callback_mutation_error,
                integrity_guard: Callable[[], None] | None = _integrity_guard,
            ) -> None:
                if integrity_guard is None:
                    return
                limiter_mutated = False
                for candidate, expected_next_allowed in limiter_states:
                    try:
                        current_next_allowed = object.__getattribute__(
                            candidate,
                            "_next_allowed",
                        )
                    except Exception:  # noqa: BLE001 - callback mutation boundary
                        current_next_allowed = None
                    if (
                        type(current_next_allowed) is not type(expected_next_allowed)
                        or current_next_allowed != expected_next_allowed
                    ):
                        limiter_mutated = True
                        try:
                            object.__setattr__(
                                candidate,
                                "_next_allowed",
                                expected_next_allowed,
                            )
                        except Exception:  # noqa: BLE001 - outer restoration reports failure
                            pass
                if limiter_mutated:
                    raise callback_mutation_error(
                        "public reference callback mutated invocation scope or retriever "
                        "configuration"
                    )
                integrity_guard()

            check_transport_integrity = cast(
                Any,
                detached_callback_guard(check_transport_integrity),
            )

            try:
                response = self.transport.request("GET", url, headers, self.timeout_seconds)
            except source_rate_limit_error_type as error:
                check_transport_integrity()
                last_error = error
                break
            except validation_error_type as error:
                check_transport_integrity()
                last_error = source_error_type(
                    f"transport returned an invalid response: {error}"
                )
                break
            except source_error_type as error:
                check_transport_integrity()
                last_error = error
            except exception_type as error:  # pragma: no cover - defensive transport boundary
                check_transport_integrity()
                last_error = source_error_type(_safe_error_message(error))
            else:
                check_transport_integrity()
                if not isinstance(response, TransportResponse):
                    last_error = SourceError("transport did not return a TransportResponse")
                    break
                last_response = response
                if _url_origin(response.url) != _url_origin(source.base_url):
                    last_error = SourceError(
                        "source response redirected outside the configured source origin"
                    )
                    break
                if len(response.body) > source.max_response_bytes:
                    last_error = SourceError(
                        f"source response exceeded {source.max_response_bytes} bytes"
                    )
                    break
                response_hash = f"sha256:{hashlib.sha256(response.body).hexdigest()}"
                content_type = response.content_type or "application/octet-stream"
                if 200 <= response.status < 300:
                    provisional_receipt = FetchReceipt(
                        source_id=source.source_id,
                        source_version=source.version,
                        url=response.url,
                        request_hash=request_hash,
                        response_hash=response_hash,
                        status=FetchStatus.FETCHED,
                        http_status=response.status,
                        attempts=attempt,
                        retrieved_at=utc_now().isoformat(),
                        elapsed_seconds=response.elapsed_seconds,
                        cache_expires_at=None,
                    )
                    try:
                        decoded = self._decode(
                            response.body,
                            provisional_receipt,
                            content_type,
                            expect_json,
                        )
                    except SourceError as error:
                        last_error = error
                        break
                    entry: CacheEntry | None = None
                    cache_warnings: tuple[str, ...] = ()
                    if cache:
                        try:
                            entry = self.cache.put(
                                request_hash=request_hash,
                                source=source,
                                url=response.url,
                                body=response.body,
                                content_type=content_type,
                                ttl_seconds=self.cache_ttl_seconds,
                            )
                        except (OSError, SourceError, ValidationError):
                            cache_warnings = (
                                "source response was valid but could not be retained in cache",
                            )
                    receipt = FetchReceipt(
                        source_id=source.source_id,
                        source_version=source.version,
                        url=response.url,
                        request_hash=request_hash,
                        response_hash=response_hash,
                        status=FetchStatus.FETCHED,
                        http_status=response.status,
                        attempts=attempt,
                        retrieved_at=(
                            entry.retrieved_at
                            if entry
                            else provisional_receipt.retrieved_at
                        ),
                        elapsed_seconds=response.elapsed_seconds,
                        cache_expires_at=entry.expires_at if entry else None,
                        warnings=cache_warnings,
                    )
                    return SourcePayload(decoded.value, receipt, content_type)
                if response.status == 404:
                    receipt = FetchReceipt(
                        source_id=source.source_id,
                        source_version=source.version,
                        url=response.url,
                        request_hash=request_hash,
                        response_hash=response_hash,
                        status=FetchStatus.NOT_FOUND,
                        http_status=response.status,
                        attempts=attempt,
                        retrieved_at=utc_now().isoformat(),
                        elapsed_seconds=response.elapsed_seconds,
                        cache_expires_at=None,
                    )
                    if allow_not_found:
                        try:
                            return SourcePayload(None, receipt, content_type)
                        except ValidationError:
                            last_error = SourceError(
                                f"source returned invalid response metadata for {url}"
                            )
                            break
                    raise SourceNotFoundError(
                        f"source object was not found: {url}",
                        receipt=receipt,
                    )
                if response.status == 429:
                    last_error = SourceRateLimitError("source returned HTTP 429")
                else:
                    last_error = SourceError(f"source returned HTTP {response.status}: {url}")
                if response.status not in self.retry_policy.retry_statuses:
                    break
            if attempt < self.retry_policy.attempts:
                time.sleep(self.retry_policy.backoff(attempt - 1))
        failure_status = (
            FetchStatus.RATE_LIMITED
            if isinstance(last_error, SourceRateLimitError)
            else FetchStatus.FAILED
        )
        failure_receipt = FetchReceipt(
            source_id=source.source_id,
            source_version=source.version,
            url=last_response.url if last_response is not None else url,
            request_hash=request_hash,
            response_hash=(
                f"sha256:{hashlib.sha256(last_response.body).hexdigest()}"
                if last_response is not None
                else None
            ),
            status=failure_status,
            http_status=last_response.status if last_response is not None else None,
            attempts=attempts_made,
            retrieved_at=utc_now().isoformat(),
            elapsed_seconds=last_response.elapsed_seconds if last_response is not None else None,
            cache_expires_at=None,
            warnings=("source failure is not a negative measurement",),
            error_type=(
                type(last_error).__name__[:256] if last_error is not None else "unknown"
            ),
            error_message=_safe_error_message(
                last_error if last_error is not None else "unknown source failure"
            ),
        )
        if isinstance(last_error, SourceRateLimitError):
            raise SourceRateLimitError(str(last_error), receipt=failure_receipt) from last_error
        if last_response is not None:
            raise SourceError(
                f"source failed after {attempts_made} attempts: HTTP {last_response.status} {url}",
                receipt=failure_receipt,
            ) from last_error
        raise SourceError(
            f"source failed after {attempts_made} attempts: {url}",
            receipt=failure_receipt,
        ) from last_error

    @staticmethod
    def _decode(
        body: bytes, receipt: FetchReceipt, content_type: str, expect_json: bool
    ) -> SourcePayload:
        if expect_json:
            try:
                value = _strict_json_loads(
                    body.decode("utf-8"),
                    object_pairs_hook=_unique_json_object,
                    parse_constant=_invalid_json_constant,
                )
                value = freeze_json(value, field="source JSON response")
                return SourcePayload(value, receipt, content_type)
            except (RecursionError, UnicodeDecodeError, ValueError, ValidationError) as error:
                raise SourceError(f"source returned invalid JSON for {receipt.url}") from error
        else:
            try:
                value = body.decode("utf-8")
                return SourcePayload(value, receipt, content_type)
            except UnicodeDecodeError as error:
                raise SourceError(f"source returned non-UTF8 text for {receipt.url}") from error
            except ValidationError as error:
                raise SourceError(
                    f"source returned invalid text metadata for {receipt.url}"
                ) from error

    @staticmethod
    def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        return _unique_json_object(pairs)

    @staticmethod
    def _invalid_json_constant(value: str) -> None:
        _invalid_json_constant(value)


@dataclass(frozen=True, slots=True)
class SequenceSlice:
    """A real reference sequence window and its source receipt."""

    assembly: str
    chromosome: str
    start: int
    end: int
    sequence: str
    source_id: str
    receipt: FetchReceipt

    def __post_init__(self) -> None:
        for value, label in (
            (self.assembly, "sequence assembly"),
            (self.chromosome, "sequence chromosome"),
            (self.source_id, "sequence source_id"),
        ):
            _required_text(value, label, maximum=256)
        if type(self.start) is not int or type(self.end) is not int:
            raise ValidationError("sequence interval coordinates must be integers")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("sequence interval is invalid")
        if self.end - self.start + 1 > MAX_REFERENCE_SEQUENCE_BP:
            raise ValidationError(
                f"sequence interval cannot exceed {MAX_REFERENCE_SEQUENCE_BP} bases"
            )
        if type(self.sequence) is not str:
            raise ValidationError("sequence must be a string")
        if len(self.sequence) != self.end - self.start + 1:
            raise ValidationError("sequence length does not match its inclusive interval")
        if self.sequence != self.sequence.upper():
            raise ValidationError("sequence must use canonical uppercase bases")
        if any(base.upper() not in "ACGTN" for base in self.sequence):
            raise ValidationError("sequence contains characters outside A/C/G/T/N")
        if normalize_chromosome(self.chromosome) != self.chromosome:
            raise ValidationError("sequence chromosome must use canonical chr spelling")
        if type(self.receipt) is not FetchReceipt:
            raise ValidationError("sequence receipt must be a FetchReceipt")
        if self.receipt.source_id != self.source_id:
            raise ValidationError("sequence source_id does not match its receipt")
        if self.receipt.status not in {FetchStatus.FETCHED, FetchStatus.CACHE_HIT}:
            raise ValidationError("sequence receipt must describe retrieved source content")

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], jsonable(self))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> SequenceSlice:
        """Rehydrate one exact persisted sequence window and its receipt."""

        expected_fields = frozenset(
            {"assembly", "chromosome", "start", "end", "sequence", "source_id", "receipt"}
        )
        if not isinstance(raw, Mapping) or any(type(key) is not str for key in raw):
            raise ValidationError("sequence slice must be an exact JSON object")
        if frozenset(raw) != expected_fields:
            raise ValidationError("sequence slice fields are not exact")
        receipt_raw = raw["receipt"]
        if type(receipt_raw) is not dict:
            raise ValidationError("sequence slice receipt must be an exact JSON object")
        result = cls(
            assembly=raw["assembly"],
            chromosome=raw["chromosome"],
            start=raw["start"],
            end=raw["end"],
            sequence=raw["sequence"],
            source_id=raw["source_id"],
            receipt=FetchReceipt.from_dict(receipt_raw),
        )
        if _validated_canonical_bytes(
            result.to_dict(), "sequence slice"
        ) != _validated_canonical_bytes(raw, "sequence slice"):
            raise ValidationError("sequence slice is not an exact canonical representation")
        return result


@dataclass(frozen=True, slots=True)
class ReferenceBundle:
    """All live observations retrieved for one bounded variant request."""

    variant_id: str
    context_key: str
    context_address: str
    sequence: SequenceSlice | None
    elements: tuple[CandidateElement, ...]
    raw_features: tuple[Mapping[str, Any], ...]
    receipts: tuple[FetchReceipt, ...]
    warnings: tuple[str, ...]
    content_address: str

    @staticmethod
    def _content_payload(
        *,
        variant_id: str,
        context_key: str,
        context_address: str,
        sequence: SequenceSlice | None,
        elements: tuple[CandidateElement, ...],
        raw_features: tuple[Mapping[str, Any], ...],
        receipts: tuple[FetchReceipt, ...],
        warnings: tuple[str, ...],
    ) -> dict[str, Any]:
        return {
            "variant_id": variant_id,
            "context_key": context_key,
            "context_address": context_address,
            "sequence": sequence.to_dict() if sequence else None,
            "elements": [element.to_dict() for element in elements],
            "raw_features": list(raw_features),
            "receipts": [receipt.to_dict() for receipt in receipts],
            "warnings": list(warnings),
        }

    @classmethod
    def create(
        cls,
        *,
        variant_id: str,
        context: ReferenceContext,
        sequence: SequenceSlice | None,
        elements: tuple[CandidateElement, ...],
        raw_features: tuple[Mapping[str, Any], ...],
        receipts: tuple[FetchReceipt, ...],
        warnings: tuple[str, ...],
    ) -> ReferenceBundle:
        """Create a bundle with its canonical payload address closed automatically."""

        selected_context = _canonical_reference_context(
            context,
            "reference bundle context",
        )
        context_address = _reference_context_address(selected_context)
        if sequence is not None and type(sequence) is not SequenceSlice:
            raise ValidationError("reference bundle sequence must be a SequenceSlice or None")
        if (
            type(elements) is not tuple
            or len(elements) > MAX_REFERENCE_FEATURES
            or any(type(item) is not CandidateElement for item in elements)
        ):
            raise ValidationError(
                f"reference bundle elements must be a tuple of at most {MAX_REFERENCE_FEATURES}"
            )
        if (
            type(raw_features) is not tuple
            or len(raw_features) > MAX_REFERENCE_FEATURES
            or any(not isinstance(item, Mapping) for item in raw_features)
        ):
            raise ValidationError(
                f"reference bundle raw_features must be a tuple of at most {MAX_REFERENCE_FEATURES}"
            )
        if (
            type(receipts) is not tuple
            or len(receipts) > MAX_REFERENCE_RECEIPTS
            or any(type(item) is not FetchReceipt for item in receipts)
        ):
            raise ValidationError(
                f"reference bundle receipts must be a tuple of at most {MAX_REFERENCE_RECEIPTS}"
            )
        if (
            type(warnings) is not tuple
            or len(warnings) > MAX_REFERENCE_WARNINGS
            or any(type(item) is not str for item in warnings)
        ):
            raise ValidationError(
                f"reference bundle warnings must be a tuple of at most {MAX_REFERENCE_WARNINGS}"
            )
        payload = cls._content_payload(
            variant_id=variant_id,
            context_key=selected_context.key,
            context_address=context_address,
            sequence=sequence,
            elements=elements,
            raw_features=raw_features,
            receipts=receipts,
            warnings=warnings,
        )
        canonical_payload = _validated_canonical_bytes(
            payload,
            "reference bundle payload",
        )
        if len(canonical_payload) > MAX_REFERENCE_BUNDLE_BYTES:
            raise ValidationError(
                "reference bundle exceeds the maximum canonical size of "
                f"{MAX_REFERENCE_BUNDLE_BYTES} bytes"
            )
        return cls(
            variant_id=variant_id,
            context_key=selected_context.key,
            context_address=context_address,
            sequence=sequence,
            elements=elements,
            raw_features=raw_features,
            receipts=receipts,
            warnings=warnings,
            content_address=f"sha256:{hashlib.sha256(canonical_payload).hexdigest()}",
        )

    def __post_init__(self) -> None:
        _required_text(self.variant_id, "reference bundle variant_id", maximum=1_024)
        _required_text(self.context_key, "reference bundle context_key", maximum=4_096)
        _sha256_address(self.context_address, "reference bundle context_address")
        if self.sequence is not None and type(self.sequence) is not SequenceSlice:
            raise ValidationError("reference bundle sequence must be a SequenceSlice or None")
        if (
            self.sequence is not None
            and self.sequence.assembly != self.context_key.split("|", 1)[0]
        ):
            raise ValidationError("reference bundle sequence assembly does not match its context")
        if type(self.elements) is not tuple or any(
            type(item) is not CandidateElement for item in self.elements
        ):
            raise ValidationError("reference bundle elements must be a tuple of CandidateElement")
        if len(self.elements) > MAX_REFERENCE_FEATURES:
            raise ValidationError(
                f"reference bundle cannot exceed {MAX_REFERENCE_FEATURES} elements"
            )
        element_ids = tuple(item.element_id for item in self.elements)
        if len(element_ids) != len(set(element_ids)):
            raise ValidationError("reference bundle element identifiers must be unique")
        if element_ids != tuple(sorted(element_ids)):
            raise ValidationError("reference bundle elements must use canonical identifier order")
        if any(item.context.key != self.context_key for item in self.elements):
            raise ValidationError("reference bundle element context does not match the bundle")
        for item in self.elements:
            raw = item.to_dict()
            canonical = CandidateElement.from_dict(raw, item.context).to_dict()
            if _validated_canonical_bytes(
                raw, "reference bundle element"
            ) != _validated_canonical_bytes(canonical, "reference bundle element"):
                raise ValidationError(
                    f"reference bundle element is not canonical: {item.element_id}"
                )
        if type(self.raw_features) is not tuple or len(self.raw_features) > MAX_REFERENCE_FEATURES:
            raise ValidationError(
                f"reference bundle raw_features must be a tuple of at most {MAX_REFERENCE_FEATURES}"
            )
        frozen_features: list[Mapping[str, Any]] = []
        feature_keys_list: list[str] = []
        for feature in self.raw_features:
            if not isinstance(feature, Mapping):
                raise ValidationError("reference bundle raw_features entries must be objects")
            frozen_feature = freeze_json(feature, field="reference bundle raw feature")
            feature_key = _validated_canonical_json(
                frozen_feature,
                "reference bundle raw feature",
            )
            frozen_features.append(frozen_feature)
            feature_keys_list.append(feature_key)
        feature_keys = tuple(feature_keys_list)
        if len(feature_keys) != len(set(feature_keys)):
            raise ValidationError("reference bundle raw_features must be unique")
        if feature_keys != tuple(sorted(feature_keys)):
            raise ValidationError("reference bundle raw_features must use canonical order")
        if type(self.receipts) is not tuple or any(
            type(item) is not FetchReceipt for item in self.receipts
        ):
            raise ValidationError("reference bundle receipts must be a tuple of FetchReceipt")
        if len(self.receipts) > MAX_REFERENCE_RECEIPTS:
            raise ValidationError(
                f"reference bundle cannot exceed {MAX_REFERENCE_RECEIPTS} receipts"
            )
        request_hashes = tuple(item.request_hash for item in self.receipts)
        if len(request_hashes) != len(set(request_hashes)):
            raise ValidationError("reference bundle receipts must identify unique requests")
        if self.sequence is not None and self.sequence.receipt not in self.receipts:
            raise ValidationError("reference bundle receipts must include the sequence receipt")
        if type(self.warnings) is not tuple or any(
            type(item) is not str
            for item in self.warnings
        ):
            raise ValidationError("reference bundle warnings must be a tuple of strings")
        if len(self.warnings) > MAX_REFERENCE_WARNINGS:
            raise ValidationError(
                f"reference bundle cannot exceed {MAX_REFERENCE_WARNINGS} warnings"
            )
        if len(self.warnings) != len(set(self.warnings)):
            raise ValidationError("reference bundle warnings must be unique")
        for warning in self.warnings:
            _required_text(warning, "reference bundle warning")
        object.__setattr__(self, "raw_features", tuple(frozen_features))
        _sha256_address(self.content_address, "reference bundle content_address")
        content_payload = self._content_payload(
            variant_id=self.variant_id,
            context_key=self.context_key,
            context_address=self.context_address,
            sequence=self.sequence,
            elements=self.elements,
            raw_features=self.raw_features,
            receipts=self.receipts,
            warnings=self.warnings,
        )
        canonical_payload = _validated_canonical_bytes(
            content_payload,
            "reference bundle payload",
        )
        if len(canonical_payload) > MAX_REFERENCE_BUNDLE_BYTES:
            raise ValidationError(
                "reference bundle exceeds the maximum canonical size of "
                f"{MAX_REFERENCE_BUNDLE_BYTES} bytes"
            )
        expected_address = f"sha256:{hashlib.sha256(canonical_payload).hexdigest()}"
        if self.content_address != expected_address:
            raise ValidationError("reference bundle content_address does not match its payload")

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], jsonable(self))

    @staticmethod
    def _preflight_dict(raw: Mapping[str, Any]) -> tuple[int, int, int, int]:
        """Validate persisted container shape and return bounded item counts."""

        expected_fields = frozenset(
            {
                "variant_id",
                "context_key",
                "context_address",
                "sequence",
                "elements",
                "raw_features",
                "receipts",
                "warnings",
                "content_address",
            }
        )
        if not isinstance(raw, Mapping) or any(type(key) is not str for key in raw):
            raise ValidationError("reference bundle must be an exact JSON object")
        if frozenset(raw) != expected_fields:
            raise ValidationError("reference bundle fields are not exact")
        limits = (
            ("elements", MAX_REFERENCE_FEATURES),
            ("raw_features", MAX_REFERENCE_FEATURES),
            ("receipts", MAX_REFERENCE_RECEIPTS),
            ("warnings", MAX_REFERENCE_WARNINGS),
        )
        counts: list[int] = []
        for field_name, limit in limits:
            items = raw[field_name]
            if type(items) is not list:
                raise ValidationError(f"reference bundle {field_name} must be an exact array")
            if len(items) > limit:
                label = field_name.replace("_", " ")
                raise ValidationError(
                    f"reference bundle {label} exceed their hard ceiling"
                )
            counts.append(len(items))
        sequence_raw = raw["sequence"]
        if sequence_raw is not None and type(sequence_raw) is not dict:
            raise ValidationError("reference bundle sequence must be an object or null")
        for field_name in ("elements", "raw_features", "receipts"):
            if any(type(item) is not dict for item in raw[field_name]):
                label = field_name.replace("_", " ")
                raise ValidationError(
                    f"reference bundle {label} must be exact JSON objects"
                )
        return counts[0], counts[1], counts[2], counts[3]

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
        context: ReferenceContext,
    ) -> ReferenceBundle:
        """Rehydrate an exact persisted bundle through every nested invariant."""

        selected_context = _canonical_reference_context(
            context,
            "reference bundle context",
        )
        cls._preflight_dict(raw)
        if (
            type(raw["context_key"]) is not str
            or raw["context_key"] != selected_context.key
        ):
            raise ValidationError(
                "reference bundle context_key does not match the supplied context"
            )
        expected_context_address = _reference_context_address(selected_context)
        raw_context_address = _sha256_address(
            raw["context_address"],
            "reference bundle context_address",
        )
        if raw_context_address != expected_context_address:
            raise ValidationError(
                "reference bundle context_address does not match the supplied context"
            )
        sequence_raw = raw["sequence"]
        result = cls(
            variant_id=raw["variant_id"],
            context_key=raw["context_key"],
            context_address=raw_context_address,
            sequence=(
                None if sequence_raw is None else SequenceSlice.from_dict(sequence_raw)
            ),
            elements=tuple(
                CandidateElement.from_dict(item, selected_context)
                for item in raw["elements"]
            ),
            raw_features=tuple(raw["raw_features"]),
            receipts=tuple(FetchReceipt.from_dict(item) for item in raw["receipts"]),
            warnings=tuple(raw["warnings"]),
            content_address=raw["content_address"],
        )
        if _validated_canonical_bytes(
            result.to_dict(), "reference bundle"
        ) != _validated_canonical_bytes(raw, "reference bundle"):
            raise ValidationError("reference bundle is not an exact canonical representation")
        return result


_ENRICHMENT_ADDRESS_PLACEHOLDER = "sha256:" + "0" * 64
_ENRICHMENT_RESULT_FIXED_BYTES = len(
    b'{"bundles":'
    b',"content_address":'
    b',"manifest":'
    b',"warnings":'
    b"}"
)
_ENRICHMENT_ADDRESS_CANONICAL_BYTES = len(
    canonical_bytes(_ENRICHMENT_ADDRESS_PLACEHOLDER)
)


def _canonical_array_size(*, item_bytes: int, item_count: int) -> int:
    """Return the exact canonical JSON size of an array from encoded item sizes."""

    return 2 + item_bytes + max(0, item_count - 1)


def _enrichment_result_size(
    *,
    manifest_bytes: int,
    bundle_bytes: int,
    bundle_count: int,
    warning_bytes: int,
    warning_count: int,
) -> int:
    """Return the exact canonical size of one serialized enrichment result."""

    return (
        _ENRICHMENT_RESULT_FIXED_BYTES
        + _canonical_array_size(item_bytes=bundle_bytes, item_count=bundle_count)
        + _ENRICHMENT_ADDRESS_CANONICAL_BYTES
        + manifest_bytes
        + _canonical_array_size(item_bytes=warning_bytes, item_count=warning_count)
    )


def _enrichment_content_address(
    *,
    manifest_raw: Mapping[str, Any],
    bundles: Iterable[ReferenceBundle],
    warnings: tuple[str, ...],
    maximum_canonical_bytes: int,
    over_limit_message: str,
) -> str:
    """Hash an enrichment closure incrementally and reject before whole-result encoding."""

    manifest_encoded = _validated_canonical_bytes(
        manifest_raw,
        "enrichment manifest",
    )
    warning_bytes = sum(
        len(_validated_canonical_bytes(warning, "enrichment warning"))
        for warning in warnings
    )
    result_size = _enrichment_result_size(
        manifest_bytes=len(manifest_encoded),
        bundle_bytes=0,
        bundle_count=0,
        warning_bytes=warning_bytes,
        warning_count=len(warnings),
    )
    if result_size > maximum_canonical_bytes:
        raise ValidationError(over_limit_message)

    digest = hashlib.sha256()
    digest.update(b'{"bundles":[')
    bundle_count = 0
    bundle_bytes = 0
    for bundle in bundles:
        encoded = _validated_canonical_bytes(
            bundle.to_dict(),
            "enrichment reference bundle",
        )
        if bundle_count:
            digest.update(b",")
        digest.update(encoded)
        bundle_count += 1
        bundle_bytes += len(encoded)
        result_size = _enrichment_result_size(
            manifest_bytes=len(manifest_encoded),
            bundle_bytes=bundle_bytes,
            bundle_count=bundle_count,
            warning_bytes=warning_bytes,
            warning_count=len(warnings),
        )
        if result_size > maximum_canonical_bytes:
            raise ValidationError(over_limit_message)

    digest.update(b'],"manifest":')
    digest.update(manifest_encoded)
    digest.update(b',"warnings":[')
    for index, warning in enumerate(warnings):
        if index:
            digest.update(b",")
        digest.update(_validated_canonical_bytes(warning, "enrichment warning"))
    digest.update(b"]}")
    return f"sha256:{digest.hexdigest()}"


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    """Manifest plus live source bundles; failures remain explicit warnings."""

    manifest: CaseManifest
    bundles: tuple[ReferenceBundle, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.manifest) is not CaseManifest:
            raise ValidationError("enrichment manifest must be a CaseManifest")
        if len(self.manifest.candidate_elements) > MAX_ENRICHED_ELEMENTS:
            raise ValidationError(
                "enrichment manifest candidate elements exceed their hard ceiling"
            )
        manifest_raw = self.manifest.to_dict()
        if _validated_canonical_bytes(
            manifest_raw, "enrichment manifest"
        ) != _validated_canonical_bytes(
            CaseManifest.from_dict(manifest_raw).to_dict(),
            "enrichment manifest",
        ):
            raise ValidationError("enrichment manifest is not canonical")
        if type(self.bundles) is not tuple or len(self.bundles) > MAX_REFERENCE_VARIANTS:
            raise ValidationError(
                f"enrichment bundles must be a tuple of at most {MAX_REFERENCE_VARIANTS}"
            )
        if any(type(item) is not ReferenceBundle for item in self.bundles):
            raise ValidationError("enrichment bundles must contain ReferenceBundle objects")
        if sum(len(item.elements) for item in self.bundles) > MAX_ENRICHED_ELEMENTS:
            raise ValidationError(
                "enrichment aggregate bundle element occurrences exceed their hard ceiling"
            )
        if sum(len(item.raw_features) for item in self.bundles) > MAX_ENRICHED_ELEMENTS:
            raise ValidationError(
                "enrichment aggregate bundle raw feature occurrences exceed their hard ceiling"
            )
        if sum(len(item.receipts) for item in self.bundles) > (
            MAX_REFERENCE_VARIANTS * MAX_REFERENCE_RECEIPTS
        ):
            raise ValidationError(
                "enrichment aggregate bundle receipt occurrences exceed their hard ceiling"
            )
        if sum(len(item.warnings) for item in self.bundles) > MAX_REFERENCE_WARNINGS:
            raise ValidationError(
                "enrichment aggregate bundle warning occurrences exceed their hard ceiling"
            )
        bundle_ids = tuple(item.variant_id for item in self.bundles)
        if len(bundle_ids) != len(set(bundle_ids)):
            raise ValidationError("enrichment bundle variant identifiers must be unique")
        manifest_ids = tuple(item.variant_id for item in self.manifest.variants)
        if bundle_ids != manifest_ids:
            raise ValidationError("enrichment must contain exactly one bundle per manifest variant")
        if any(item.context_key != self.manifest.context.key for item in self.bundles):
            raise ValidationError("enrichment bundle context does not match the manifest")
        manifest_context = _canonical_reference_context(
            self.manifest.context,
            "enrichment manifest context",
        )
        manifest_context_address = _reference_context_address(manifest_context)
        if any(
            item.context_address != manifest_context_address for item in self.bundles
        ):
            raise ValidationError(
                "enrichment bundle context does not exactly match the manifest"
            )
        manifest_elements = {
            item.element_id: _validated_canonical_bytes(
                item.to_dict(),
                "enrichment manifest element",
            )
            for item in self.manifest.candidate_elements
        }
        for bundle in self.bundles:
            for element in bundle.elements:
                if manifest_elements.get(element.element_id) != _validated_canonical_bytes(
                    element.to_dict(),
                    "enrichment bundle element",
                ):
                    raise ValidationError(
                        "enrichment manifest does not contain the exact bundle element "
                        f"{element.element_id}"
                    )
        if type(self.warnings) is not tuple or any(
            type(item) is not str
            for item in self.warnings
        ):
            raise ValidationError("enrichment warnings must be a tuple of strings")
        if len(self.warnings) > MAX_REFERENCE_WARNINGS:
            raise ValidationError(
                f"enrichment cannot exceed {MAX_REFERENCE_WARNINGS} warnings"
            )
        if len(self.warnings) != len(set(self.warnings)):
            raise ValidationError("enrichment warnings must be unique")
        for warning in self.warnings:
            _required_text(warning, "enrichment warning")
        bundle_warnings = {warning for bundle in self.bundles for warning in bundle.warnings}
        if not bundle_warnings.issubset(self.warnings):
            raise ValidationError("enrichment warnings omit a bundle warning")
        total_sequence_bp = sum(
            len(bundle.sequence.sequence)
            for bundle in self.bundles
            if bundle.sequence is not None
        )
        if total_sequence_bp > MAX_ENRICHMENT_SEQUENCE_BP:
            raise ValidationError(
                "enrichment aggregate sequence work exceeds its hard base-pair ceiling"
            )
        _enrichment_content_address(
            manifest_raw=manifest_raw,
            bundles=self.bundles,
            warnings=self.warnings,
            maximum_canonical_bytes=MAX_ENRICHMENT_CANONICAL_BYTES,
            over_limit_message="enrichment result exceeds its hard canonical byte ceiling",
        )

    def to_dict(self) -> dict[str, Any]:
        manifest_raw = self.manifest.to_dict()
        content_address = _enrichment_content_address(
            manifest_raw=manifest_raw,
            bundles=self.bundles,
            warnings=self.warnings,
            maximum_canonical_bytes=MAX_ENRICHMENT_CANONICAL_BYTES,
            over_limit_message="enrichment result exceeds its hard canonical byte ceiling",
        )
        return {
            "manifest": manifest_raw,
            "bundles": [bundle.to_dict() for bundle in self.bundles],
            "warnings": list(self.warnings),
            "content_address": content_address,
        }

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
        *,
        limits: ReferenceRetrievalLimits | None = None,
    ) -> EnrichmentResult:
        """Rehydrate one exact enrichment closure, including every nested bundle."""

        selected_limits = DEFAULT_REFERENCE_RETRIEVAL_LIMITS if limits is None else limits
        if type(selected_limits) is not ReferenceRetrievalLimits:
            raise ValidationError("reference limits must be ReferenceRetrievalLimits")

        expected_fields = frozenset(
            {"manifest", "bundles", "warnings", "content_address"}
        )
        if not isinstance(raw, Mapping) or any(type(key) is not str for key in raw):
            raise ValidationError("enrichment result must be an exact JSON object")
        if frozenset(raw) != expected_fields:
            raise ValidationError("enrichment result fields are not exact")
        manifest_raw = raw["manifest"]
        bundles_raw = raw["bundles"]
        warnings_raw = raw["warnings"]
        if type(manifest_raw) is not dict:
            raise ValidationError("enrichment manifest must be an exact JSON object")
        if type(bundles_raw) is not list:
            raise ValidationError("enrichment bundles must be an exact array")
        if type(warnings_raw) is not list:
            raise ValidationError("enrichment warnings must be an exact array")
        if len(bundles_raw) > MAX_REFERENCE_VARIANTS:
            raise ValidationError("enrichment bundles exceed their hard ceiling")
        if len(bundles_raw) > selected_limits.max_variants:
            raise ValidationError("enrichment bundles exceed their configured variant ceiling")
        if len(warnings_raw) > MAX_REFERENCE_WARNINGS:
            raise ValidationError("enrichment warnings exceed their hard ceiling")
        if any(type(item) is not str for item in warnings_raw):
            raise ValidationError("enrichment warnings must contain exact strings")
        if len(warnings_raw) != len(set(warnings_raw)):
            raise ValidationError("enrichment warnings must be unique")
        warning_bytes = 0
        for warning in warnings_raw:
            _required_text(warning, "enrichment warning")
            warning_bytes += len(
                _validated_canonical_bytes(warning, "enrichment warning")
            )
        _sha256_address(raw["content_address"], "enrichment content_address")
        if any(type(item) is not dict for item in bundles_raw):
            raise ValidationError("enrichment bundles must be exact JSON objects")

        manifest_fields = frozenset(
            {
                "case_id",
                "subject_id",
                "context",
                "variants",
                "candidate_elements",
                "metadata",
                "input_versions",
                "requested_by",
            }
        )
        if any(type(key) is not str for key in manifest_raw):
            raise ValidationError("enrichment manifest must be an exact JSON object")
        if frozenset(manifest_raw) != manifest_fields:
            raise ValidationError("enrichment manifest fields are not exact")
        if type(manifest_raw["context"]) is not dict:
            raise ValidationError("enrichment manifest context must be an exact JSON object")
        if type(manifest_raw["variants"]) is not list:
            raise ValidationError("enrichment manifest variants must be an exact array")
        if type(manifest_raw["candidate_elements"]) is not list:
            raise ValidationError(
                "enrichment manifest candidate_elements must be an exact array"
            )
        if type(manifest_raw["metadata"]) is not dict:
            raise ValidationError("enrichment manifest metadata must be an exact JSON object")
        if type(manifest_raw["input_versions"]) is not dict:
            raise ValidationError(
                "enrichment manifest input_versions must be an exact JSON object"
            )
        variants_raw = manifest_raw["variants"]
        manifest_elements_raw = manifest_raw["candidate_elements"]
        if len(variants_raw) > MAX_REFERENCE_VARIANTS:
            raise ValidationError("enrichment manifest variants exceed their hard ceiling")
        if len(variants_raw) > selected_limits.max_variants:
            raise ValidationError(
                "enrichment manifest variants exceed their configured variant ceiling"
            )
        if len(manifest_elements_raw) > MAX_ENRICHED_ELEMENTS:
            raise ValidationError(
                "enrichment manifest candidate elements exceed their hard ceiling"
            )
        if len(manifest_elements_raw) > selected_limits.max_total_elements:
            raise ValidationError(
                "enrichment manifest candidate elements exceed their configured total ceiling"
            )
        if any(type(item) is not dict for item in variants_raw):
            raise ValidationError("enrichment manifest variants must be exact JSON objects")
        if any(type(item) is not dict for item in manifest_elements_raw):
            raise ValidationError(
                "enrichment manifest candidate elements must be exact JSON objects"
            )
        if len(bundles_raw) != len(variants_raw):
            raise ValidationError(
                "enrichment must contain exactly one bundle per manifest variant"
            )

        bundle_element_occurrences = 0
        bundle_raw_feature_occurrences = 0
        bundle_receipt_occurrences = 0
        bundle_warning_occurrences = 0
        aggregate_sequence_bp = 0
        manifest_size = len(
            _validated_canonical_bytes(manifest_raw, "enrichment manifest")
        )
        bundle_bytes = 0
        if _enrichment_result_size(
            manifest_bytes=manifest_size,
            bundle_bytes=bundle_bytes,
            bundle_count=0,
            warning_bytes=warning_bytes,
            warning_count=len(warnings_raw),
        ) > selected_limits.max_total_canonical_bytes:
            raise ValidationError(
                "enrichment result exceeds its configured canonical byte ceiling"
            )
        for bundle_index, bundle_raw in enumerate(bundles_raw, start=1):
            element_count, raw_feature_count, receipt_count, warning_count = (
                ReferenceBundle._preflight_dict(bundle_raw)
            )
            if (
                element_count > selected_limits.max_features_per_variant
                or raw_feature_count > selected_limits.max_features_per_variant
            ):
                raise ValidationError(
                    "enrichment reference bundle features exceed their configured per-variant "
                    "ceiling"
                )
            bundle_size = len(
                _validated_canonical_bytes(bundle_raw, "enrichment reference bundle")
            )
            if bundle_size > MAX_REFERENCE_BUNDLE_BYTES:
                raise ValidationError(
                    "enrichment reference bundle exceeds its hard canonical byte ceiling"
                )
            bundle_bytes += bundle_size
            if _enrichment_result_size(
                manifest_bytes=manifest_size,
                bundle_bytes=bundle_bytes,
                bundle_count=bundle_index,
                warning_bytes=warning_bytes,
                warning_count=len(warnings_raw),
            ) > selected_limits.max_total_canonical_bytes:
                raise ValidationError(
                    "enrichment result exceeds its configured canonical byte ceiling"
                )
            bundle_element_occurrences += element_count
            if bundle_element_occurrences > MAX_ENRICHED_ELEMENTS:
                raise ValidationError(
                    "enrichment aggregate bundle element occurrences exceed their hard ceiling"
                )
            bundle_raw_feature_occurrences += raw_feature_count
            if bundle_raw_feature_occurrences > MAX_ENRICHED_ELEMENTS:
                raise ValidationError(
                    "enrichment aggregate bundle raw feature occurrences "
                    "exceed their hard ceiling"
                )
            bundle_receipt_occurrences += receipt_count
            if bundle_receipt_occurrences > (
                MAX_REFERENCE_VARIANTS * MAX_REFERENCE_RECEIPTS
            ):
                raise ValidationError(
                    "enrichment aggregate bundle receipt occurrences exceed their hard ceiling"
                )
            bundle_warning_occurrences += warning_count
            if bundle_warning_occurrences > MAX_REFERENCE_WARNINGS:
                raise ValidationError(
                    "enrichment aggregate bundle warning occurrences exceed their hard ceiling"
                )
            sequence_raw = bundle_raw["sequence"]
            if sequence_raw is not None:
                sequence_value = sequence_raw.get("sequence")
                if type(sequence_value) is not str:
                    raise ValidationError(
                        "enrichment bundle sequence must contain a sequence string"
                    )
                aggregate_sequence_bp += len(sequence_value)
                if aggregate_sequence_bp > selected_limits.max_total_sequence_bp:
                    raise ValidationError(
                        "enrichment aggregate sequence work exceeds its configured "
                        "base-pair ceiling"
                    )

        manifest = CaseManifest.from_dict(manifest_raw)
        result = cls(
            manifest=manifest,
            bundles=tuple(
                ReferenceBundle.from_dict(item, manifest.context)
                for item in bundles_raw
            ),
            warnings=tuple(warnings_raw),
        )
        expected_address = _sha256_address(
            raw["content_address"],
            "enrichment content_address",
        )
        if result.to_dict()["content_address"] != expected_address:
            raise ValidationError("enrichment content_address does not match its payload")
        if _validated_canonical_bytes(
            result.to_dict(), "enrichment result"
        ) != _validated_canonical_bytes(raw, "enrichment result"):
            raise ValidationError("enrichment result is not an exact canonical representation")
        return result


class EnsemblRestClient:
    """Bounded Ensembl REST operations used by the reference retriever."""

    source_id = "SRC-ENSEMBL-REST"

    def __init__(self, client: SourceClient) -> None:
        if type(client) is not SourceClient:
            raise ValidationError("Ensembl client must be a SourceClient")
        self.client = client

    def sequence_region(
        self, chromosome: str, start: int, end: int, *, species: str = "homo_sapiens"
    ) -> SourcePayload:
        if type(start) is not int or type(end) is not int or start < 1 or end < start:
            raise ValidationError("Ensembl sequence interval must use positive integers")
        if end - start + 1 > 10_000_000:
            raise ValidationError("Ensembl sequence request exceeds the 10 Mb endpoint limit")
        species = _required_text(species, "Ensembl species", maximum=64)
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", species) is None:
            raise ValidationError("Ensembl species contains unsupported characters")
        region = f"{normalize_chromosome(chromosome)[3:]}:{start}..{end}:1"
        return self.client.fetch_text(self.source_id, f"/sequence/region/{species}/{region}")

    def lookup_symbol(
        self, symbol: str, *, species: str = "homo_sapiens", expand: bool = False
    ) -> SourcePayload:
        symbol = _required_text(symbol, "gene symbol", maximum=256).strip()
        species = _required_text(species, "Ensembl species", maximum=64)
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", species) is None:
            raise ValidationError("Ensembl species contains unsupported characters")
        if type(expand) is not bool:
            raise ValidationError("Ensembl expand must be a boolean")
        params = {"expand": "1"} if expand else None
        encoded = urllib.parse.quote(symbol, safe="")
        return self.client.fetch_json(self.source_id, f"/lookup/symbol/{species}/{encoded}", params)

    def overlap_region(
        self,
        chromosome: str,
        start: int,
        end: int,
        *,
        features: Iterable[str],
        species: str = "homo_sapiens",
        _integrity_guard: Callable[[], None] | None = None,
    ) -> SourcePayload:
        source = self.client.catalog.get(self.source_id)
        if (
            type(start) is not int
            or type(end) is not int
            or start < 1
            or end < start
            or end - start + 1 > (source.max_region_bp or 5_000_000)
        ):
            raise ValidationError("Ensembl regional overlap exceeds the configured source limit")
        species = _required_text(species, "Ensembl species", maximum=64)
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", species) is None:
            raise ValidationError("Ensembl species contains unsupported characters")
        try:
            feature_values = tuple(islice(iter(features), 33))
        except TypeError as exc:
            raise ValidationError("Ensembl features must be iterable") from exc
        if not feature_values or len(feature_values) > 32:
            raise ValidationError("Ensembl features must contain between 1 and 32 values")
        normalized_features = tuple(
            sorted(
                {
                    _required_text(feature, "Ensembl feature", maximum=64)
                    for feature in feature_values
                }
            )
        )
        region = f"{normalize_chromosome(chromosome)[3:]}:{start}-{end}"
        return self.client.fetch_json(
            self.source_id,
            f"/overlap/region/{species}/{region}",
            {"feature": normalized_features},
            _integrity_guard=_integrity_guard,
        )


class UcscRestClient:
    """Small-window UCSC sequence and track operations."""

    source_id = "SRC-UCSC-REST"

    _assemblies = {"GRCh38": "hg38", "hg38": "hg38", "GRCh37": "hg19", "hg19": "hg19"}

    def __init__(self, client: SourceClient) -> None:
        if type(client) is not SourceClient:
            raise ValidationError("UCSC client must be a SourceClient")
        self.client = client

    def assembly_name(self, genome_build: str) -> str:
        if type(genome_build) is not str:
            raise ValidationError("UCSC genome_build must be a string")
        try:
            return self._assemblies[genome_build]
        except KeyError as exc:
            raise ValidationError(f"UCSC assembly is not configured for {genome_build}") from exc

    def sequence(
        self,
        chromosome: str,
        start: int,
        end: int,
        *,
        genome_build: str,
        _integrity_guard: Callable[[], None] | None = None,
    ) -> SourcePayload:
        source = self.client.catalog.get(self.source_id)
        if (
            type(start) is not int
            or type(end) is not int
            or start < 1
            or end < start
            or end - start + 1 > (source.max_region_bp or 10_000_000)
        ):
            raise ValidationError("UCSC sequence request exceeds the configured source limit")
        return self.client.fetch_json(
            self.source_id,
            "/getData/sequence",
            {
                "genome": self.assembly_name(genome_build),
                "chrom": normalize_chromosome(chromosome),
                "start": start - 1,
                "end": end,
            },
            _integrity_guard=_integrity_guard,
        )

    def track(
        self,
        track: str,
        chromosome: str,
        start: int,
        end: int,
        *,
        genome_build: str,
        max_items: int = 1000,
    ) -> SourcePayload:
        source = self.client.catalog.get(self.source_id)
        track = _required_text(track, "UCSC track", maximum=256)
        if (
            type(start) is not int
            or type(end) is not int
            or start < 1
            or end < start
            or end - start + 1 > (source.max_region_bp or 10_000_000)
        ):
            raise ValidationError("UCSC track interval exceeds the configured source limit")
        _bounded_int(max_items, "UCSC max_items", minimum=1, maximum=100_000)
        return self.client.fetch_json(
            self.source_id,
            "/getData/track",
            {
                "genome": self.assembly_name(genome_build),
                "track": track,
                "chrom": normalize_chromosome(chromosome),
                "start": start - 1,
                "end": end,
                "maxItemsOutput": max_items,
            },
        )


class EncodeRestClient:
    """ENCODE metadata search and object retrieval."""

    source_id = "SRC-ENCODE-REST"

    def __init__(self, client: SourceClient) -> None:
        if type(client) is not SourceClient:
            raise ValidationError("ENCODE client must be a SourceClient")
        self.client = client

    def search_experiments(
        self,
        *,
        assay_title: str | None = None,
        biosample_ontology_term_name: str | None = None,
        organism: str = "Homo sapiens",
        limit: int = 25,
    ) -> SourcePayload:
        _bounded_int(limit, "ENCODE limit", minimum=1, maximum=1_000)
        organism = _required_text(organism, "ENCODE organism", maximum=256)
        params: dict[str, Any] = {
            "type": "Experiment",
            "format": "json",
            "limit": limit,
            "organism.scientific_name": organism,
        }
        if assay_title is not None:
            params["assay_title"] = _required_text(
                assay_title,
                "ENCODE assay_title",
                maximum=256,
            )
        if biosample_ontology_term_name is not None:
            params["biosample_ontology.term_name"] = _required_text(
                biosample_ontology_term_name,
                "ENCODE biosample term",
                maximum=256,
            )
        return self.client.fetch_json(self.source_id, "/search/", params)

    def object(self, accession: str) -> SourcePayload:
        normalized = _required_text(accession, "ENCODE accession", maximum=256).strip()
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", normalized) is None or ".." in normalized:
            raise ValidationError("ENCODE accession is invalid")
        return self.client.fetch_json(
            self.source_id,
            f"/{urllib.parse.quote(normalized, safe='')}/",
            {"format": "json", "frame": "object"},
        )


def _capture_public_reference_semantic_guard() -> tuple[
    Callable[[], bool],
    Callable[[], None],
]:
    """Snapshot package semantics that a public-source callback could rewrite."""

    error_type = ValidationError
    source_namespace = globals()
    function_type = FunctionType
    field_type = Field
    field_slots = tuple(cast(Any, Field).__slots__)
    class_setattr = type.__setattr__
    class_delattr = type.__delattr__

    def descriptor_functions(values: tuple[object, ...]) -> tuple[FunctionType, ...]:
        selected: list[FunctionType] = []
        for descriptor in values:
            if type(descriptor) is function_type:
                selected.append(cast(FunctionType, descriptor))
            elif type(descriptor) in {staticmethod, classmethod}:
                selected.append(cast(Any, descriptor).__func__)
            elif type(descriptor) is property:
                selected.extend(
                    cast(FunctionType, function)
                    for function in (
                        cast(property, descriptor).fget,
                        cast(property, descriptor).fset,
                        cast(property, descriptor).fdel,
                    )
                    if function is not None
                )
        return tuple(selected)

    class_by_id: dict[int, type[Any]] = {}
    module_by_id: dict[int, dict[str, object]] = {id(source_namespace): source_namespace}
    while True:
        previous_shape = (len(module_by_id), len(class_by_id))
        for namespace in tuple(module_by_id.values()):
            for candidate in namespace.values():
                if not isinstance(candidate, type):
                    continue
                owner = getattr(candidate, "__module__", "")
                if type(owner) is str and (
                    owner == "glio_noncode" or owner.startswith("glio_noncode.")
                ):
                    class_by_id[id(candidate)] = candidate
            for function in descriptor_functions(tuple(namespace.values())):
                function_namespace = function.__globals__
                package = function_namespace.get("__package__")
                if type(package) is str and (
                    package == "glio_noncode" or package.startswith("glio_noncode.")
                ):
                    module_by_id[id(function_namespace)] = function_namespace
        for target in tuple(class_by_id.values()):
            for function in descriptor_functions(tuple(vars(target).values())):
                function_namespace = function.__globals__
                package = function_namespace.get("__package__")
                if type(package) is str and (
                    package == "glio_noncode" or package.startswith("glio_noncode.")
                ):
                    module_by_id[id(function_namespace)] = function_namespace
        if (len(module_by_id), len(class_by_id)) == previous_shape:
            break

    class_targets = tuple(class_by_id.values())
    module_namespaces = tuple(module_by_id.values())
    function_by_id: dict[int, FunctionType] = {}
    for namespace in module_namespaces:
        for function in descriptor_functions(tuple(namespace.values())):
            function_by_id[id(function)] = function
    for target in class_targets:
        for function in descriptor_functions(tuple(vars(target).values())):
            function_by_id[id(function)] = function

    pending_functions = list(function_by_id.values())
    function_index = 0
    while function_index < len(pending_functions):
        function = pending_functions[function_index]
        function_index += 1
        wrapped = vars(function).get("__wrapped__")
        nested_functions: list[object] = [wrapped]
        for cell in function.__closure__ or ():
            try:
                nested_functions.append(cell.cell_contents)
            except ValueError:
                continue
        for candidate in nested_functions:
            if type(candidate) is not function_type or id(candidate) in function_by_id:
                continue
            if len(function_by_id) >= 65_536:
                raise error_type("public reference semantic function graph exceeds limit")
            selected_function = cast(FunctionType, candidate)
            function_by_id[id(selected_function)] = selected_function
            pending_functions.append(selected_function)

    while True:
        function_graph_shape = (len(module_by_id), len(class_by_id), len(function_by_id))
        for function in tuple(function_by_id.values()):
            function_namespace = function.__globals__
            package = function_namespace.get("__package__")
            if type(package) is str and (
                package == "glio_noncode" or package.startswith("glio_noncode.")
            ):
                module_by_id[id(function_namespace)] = function_namespace
            nested_function_values: list[object] = [vars(function).get("__wrapped__")]
            for cell in function.__closure__ or ():
                try:
                    nested_function_values.append(cell.cell_contents)
                except ValueError:
                    continue
            for candidate in nested_function_values:
                if type(candidate) is not function_type or id(candidate) in function_by_id:
                    continue
                if len(function_by_id) >= 65_536:
                    raise error_type("public reference semantic function graph exceeds limit")
                selected_function = cast(FunctionType, candidate)
                function_by_id[id(selected_function)] = selected_function
        for namespace in tuple(module_by_id.values()):
            for candidate in namespace.values():
                if not isinstance(candidate, type):
                    continue
                owner = getattr(candidate, "__module__", "")
                if type(owner) is str and (
                    owner == "glio_noncode" or owner.startswith("glio_noncode.")
                ):
                    class_by_id[id(candidate)] = candidate
            for function in descriptor_functions(tuple(namespace.values())):
                function_by_id[id(function)] = function
        for target in tuple(class_by_id.values()):
            for function in descriptor_functions(tuple(vars(target).values())):
                function_by_id[id(function)] = function
        if (len(module_by_id), len(class_by_id), len(function_by_id)) == function_graph_shape:
            break

    class_targets = tuple(class_by_id.values())
    module_namespaces = tuple(module_by_id.values())

    function_states: list[tuple[Any, ...]] = []
    for function in function_by_id.values():
        kwdefaults = function.__kwdefaults__
        annotations = function.__annotations__
        function_dict = vars(function)
        if kwdefaults is not None and type(kwdefaults) is not dict:
            raise error_type("public reference function kwdefaults are invalid")
        if type(annotations) is not dict:
            raise error_type("public reference function annotations are invalid")
        closure_states: list[tuple[object, bool, object | None]] = []
        for cell in function.__closure__ or ():
            try:
                closure_states.append((cell, True, cell.cell_contents))
            except ValueError:
                closure_states.append((cell, False, None))
        function_states.append(
            (
                function,
                function.__code__,
                function.__defaults__,
                kwdefaults,
                () if kwdefaults is None else tuple(kwdefaults.items()),
                annotations,
                tuple(annotations.items()),
                function_dict,
                tuple(function_dict.items()),
                tuple(closure_states),
            )
        )

    module_states = tuple(
        (namespace, tuple(namespace.items())) for namespace in module_namespaces
    )
    class_states: list[tuple[Any, ...]] = []
    for target in class_targets:
        attributes = tuple(vars(target).items())
        mappings = tuple(
            (value, tuple(value.items()))
            for _name, value in attributes
            if type(value) is dict
        )
        dataclass_fields = vars(target).get("__dataclass_fields__")
        field_states: tuple[tuple[Field[Any], tuple[tuple[str, object], ...]], ...] = ()
        if type(dataclass_fields) is dict:
            if any(type(item) is not field_type for item in dataclass_fields.values()):
                raise error_type("public reference dataclass field registry is invalid")
            field_states = tuple(
                (
                    item,
                    tuple((name, getattr(item, name)) for name in field_slots),
                )
                for item in dataclass_fields.values()
            )
        class_states.append((target, attributes, mappings, field_states))

    def same_items(
        mapping: Mapping[Any, Any],
        expected: tuple[tuple[Any, Any], ...],
    ) -> bool:
        try:
            current = tuple(mapping.items())
            return len(current) == len(expected) and all(
                current_key == expected_key and current_value is expected_value
                for (current_key, current_value), (expected_key, expected_value) in zip(
                    current,
                    expected,
                    strict=True,
                )
            )
        except Exception:  # noqa: BLE001 - callback-mutated semantic mapping
            return False

    def cell_is_empty(cell: object) -> bool:
        try:
            _ = cast(Any, cell).cell_contents
        except ValueError:
            return True
        return False

    def function_unchanged(state: tuple[Any, ...]) -> bool:
        (
            function,
            code,
            defaults,
            kwdefaults,
            kwdefault_items,
            annotations,
            annotation_items,
            function_dict,
            function_dict_items,
            closure_states,
        ) = state
        try:
            current_closure = function.__closure__ or ()
            return (
                function.__code__ is code
                and function.__defaults__ is defaults
                and function.__kwdefaults__ is kwdefaults
                and (kwdefaults is None or same_items(kwdefaults, kwdefault_items))
                and function.__annotations__ is annotations
                and same_items(annotations, annotation_items)
                and vars(function) is function_dict
                and same_items(function_dict, function_dict_items)
                and len(current_closure) == len(closure_states)
                and all(
                    current_cell is expected_cell
                    and (
                        (had_value and current_cell.cell_contents is value)
                        or (not had_value and cell_is_empty(current_cell))
                    )
                    for current_cell, (expected_cell, had_value, value) in zip(
                        current_closure,
                        closure_states,
                        strict=True,
                    )
                )
            )
        except Exception:  # noqa: BLE001 - callback-mutated function
            return False

    # Preserve a detached helper chain for every check that can run after the
    # transport callback has had access to package-module globals.
    same_items = cast(Any, detached_callback_guard(same_items))
    cell_is_empty = cast(Any, detached_callback_guard(cell_is_empty))
    function_unchanged = cast(Any, detached_callback_guard(function_unchanged))

    def unchanged() -> bool:
        try:
            if any(
                not same_items(namespace, attributes)
                for namespace, attributes in module_states
            ):
                return False
            if any(not function_unchanged(state) for state in function_states):
                return False
            for target, attributes, mappings, field_states in class_states:
                if not same_items(vars(target), attributes):
                    return False
                if any(not same_items(mapping, items) for mapping, items in mappings):
                    return False
                if any(
                    any(getattr(item, name) is not value for name, value in values)
                    for item, values in field_states
                ):
                    return False
            return True
        except Exception:  # noqa: BLE001 - unreadable package semantics
            return False

    unchanged = cast(Any, detached_callback_guard(unchanged))

    def restore() -> None:
        try:
            for namespace, attributes in module_states:
                expected = dict(attributes)
                for name in set(namespace) - set(expected):
                    del namespace[name]
                for name, value in attributes:
                    if name not in namespace or namespace[name] is not value:
                        namespace[name] = value
            for target, attributes, mappings, field_states in class_states:
                expected = dict(attributes)
                for name in set(vars(target)) - set(expected):
                    class_delattr(target, name)
                for name, value in attributes:
                    if name not in vars(target) or vars(target)[name] is not value:
                        class_setattr(target, name, value)
                for mapping, items in mappings:
                    mapping.clear()
                    mapping.update(dict(items))
                for item, values in field_states:
                    for name, value in values:
                        setattr(item, name, value)
            for state in function_states:
                (
                    function,
                    code,
                    defaults,
                    kwdefaults,
                    kwdefault_items,
                    annotations,
                    annotation_items,
                    function_dict,
                    function_dict_items,
                    closure_states,
                ) = state
                function.__code__ = code
                function.__defaults__ = defaults
                function.__kwdefaults__ = kwdefaults
                if kwdefaults is not None:
                    kwdefaults.clear()
                    kwdefaults.update(dict(kwdefault_items))
                function.__annotations__ = annotations
                annotations.clear()
                annotations.update(dict(annotation_items))
                function.__dict__ = function_dict
                function_dict.clear()
                function_dict.update(dict(function_dict_items))
                current_closure = function.__closure__ or ()
                if len(current_closure) != len(closure_states):
                    raise error_type("public reference function closure could not be restored")
                for current_cell, (expected_cell, had_value, value) in zip(
                    current_closure,
                    closure_states,
                    strict=True,
                ):
                    if current_cell is not expected_cell:
                        raise error_type(
                            "public reference function closure could not be restored"
                        )
                    if had_value:
                        current_cell.cell_contents = value
                    else:
                        try:
                            del current_cell.cell_contents
                        except ValueError:
                            pass
        except Exception as exc:  # noqa: BLE001 - semantic restoration boundary
            if isinstance(exc, error_type):
                raise
            raise error_type("public reference semantic state could not be restored") from exc
        if not unchanged():
            raise error_type("public reference semantic state could not be restored")

    return (
        cast(Callable[[], bool], unchanged),
        cast(Callable[[], None], detached_callback_guard(restore)),
    )


@dataclass(frozen=True, slots=True)
class _ObjectConfigurationSnapshot:
    target: object
    target_type: type[Any]
    attributes: tuple[tuple[str, object], ...]
    namespace_names: frozenset[str] | None


@dataclass(frozen=True, slots=True)
class _MappingConfigurationSnapshot:
    target: dict[Any, Any]
    items: tuple[tuple[Any, Any], ...]


@dataclass(frozen=True, slots=True)
class _MutableContainerSnapshot:
    target: dict[Any, Any] | list[Any]
    target_type: type[Any]
    items: tuple[Any, ...]
    is_mapping: bool


@dataclass(frozen=True, slots=True)
class _PublicReferenceInvocationSnapshot:
    object_states: tuple[_ObjectConfigurationSnapshot, ...]
    mapping_states: tuple[_MappingConfigurationSnapshot, ...]
    mutable_states: tuple[_MutableContainerSnapshot, ...]
    semantic_unchanged: Callable[[], bool]
    restore_semantics: Callable[[], None]


def _configuration_value_is_same(current: object, original: object) -> bool:
    if current is original:
        return True
    if type(original) in {str, int, float, bool, tuple, frozenset, type(None)}:
        return type(current) is type(original) and current == original
    return False


def _capture_mutable_container_configuration(
    values: Iterable[object],
) -> tuple[_MutableContainerSnapshot, ...]:
    """Snapshot every JSON dict/list without losing caller-visible aliases."""

    pending = list(reversed(tuple(values)))
    selected: list[_MutableContainerSnapshot] = []
    seen: set[int] = set()
    while pending:
        value = pending.pop()
        if type(value) is tuple:
            pending.extend(reversed(value))
            continue
        if not isinstance(value, (dict, list)) or id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, dict):
            items = tuple(value.items())
            selected.append(
                _MutableContainerSnapshot(
                    target=value,
                    target_type=type(value),
                    items=items,
                    is_mapping=True,
                )
            )
            pending.extend(reversed(tuple(item for _key, item in items)))
        else:
            items = tuple(value)
            selected.append(
                _MutableContainerSnapshot(
                    target=value,
                    target_type=type(value),
                    items=items,
                    is_mapping=False,
                )
            )
            pending.extend(reversed(items))
    return tuple(selected)


def _mutable_container_configuration_is_unchanged(
    states: tuple[_MutableContainerSnapshot, ...],
) -> bool:
    try:
        for state in states:
            if type(state.target) is not state.target_type:
                return False
            if state.is_mapping:
                current_items = tuple(cast(dict[Any, Any], state.target).items())
                if len(current_items) != len(state.items) or any(
                    not _configuration_value_is_same(current_key, expected_key)
                    or not _configuration_value_is_same(current_value, expected_value)
                    for (current_key, current_value), (expected_key, expected_value) in zip(
                        current_items,
                        cast(tuple[tuple[Any, Any], ...], state.items),
                        strict=True,
                    )
                ):
                    return False
            else:
                current_items = tuple(cast(list[Any], state.target))
                if len(current_items) != len(state.items) or any(
                    not _configuration_value_is_same(current, expected)
                    for current, expected in zip(
                        current_items,
                        state.items,
                        strict=True,
                    )
                ):
                    return False
        return True
    except Exception:  # noqa: BLE001 - callback-mutated recursive container
        return False


def _restore_mutable_container_configuration(
    states: tuple[_MutableContainerSnapshot, ...],
) -> None:
    for state in states:
        if type(state.target) is not state.target_type:
            object.__setattr__(state.target, "__class__", state.target_type)
        if state.is_mapping:
            target_mapping = cast(dict[Any, Any], state.target)
            dict.clear(target_mapping)
            for key, value in cast(tuple[tuple[Any, Any], ...], state.items):
                dict.__setitem__(target_mapping, key, value)
        else:
            target_list = cast(list[Any], state.target)
            list.clear(target_list)
            list.extend(target_list, state.items)


def _capture_object_configuration_guard(
    states: tuple[_ObjectConfigurationSnapshot, ...],
    *,
    message: str,
) -> tuple[Callable[[], None], Callable[[], None]]:
    """Return detached assertion/restoration callbacks for an object graph."""

    error_type = _SourceCallbackMutationError
    object_setattr = object.__setattr__
    mutable_states = _capture_mutable_container_configuration(
        value for state in states for _name, value in state.attributes
    )

    def assert_unchanged() -> None:
        try:
            for state in states:
                if type(state.target) is not state.target_type:
                    raise error_type
                if state.namespace_names is not None and frozenset(vars(state.target)) != (
                    state.namespace_names
                ):
                    raise error_type
                for name, value in state.attributes:
                    if not _configuration_value_is_same(
                        getattr(state.target, name),
                        value,
                    ):
                        raise error_type
            if not _mutable_container_configuration_is_unchanged(mutable_states):
                raise error_type
        except Exception as exc:
            if type(exc) is error_type:
                raise error_type(message) from None
            raise error_type(message) from exc

    def restore() -> None:
        try:
            mutable_drifted = not _mutable_container_configuration_is_unchanged(
                mutable_states
            )
            for state in states:
                if type(state.target) is not state.target_type:
                    object_setattr(state.target, "__class__", state.target_type)
                if state.namespace_names is not None:
                    namespace = vars(state.target)
                    for name in tuple(namespace):
                        if name not in state.namespace_names:
                            del namespace[name]
                for name, value in state.attributes:
                    object_setattr(state.target, name, value)
            if mutable_drifted:
                _restore_mutable_container_configuration(mutable_states)
        except Exception as exc:  # noqa: BLE001 - callback recovery boundary
            raise ValidationError("public reference callback scope could not be restored") from exc

    return assert_unchanged, restore


class PublicReferenceRetriever:
    """Retrieve real sequence and nearby regulatory/gene features for a variant."""

    def __init__(
        self,
        client: SourceClient | None = None,
        *,
        cache_root: str | Path = ".glio/source-cache",
        window_bp: int = 2_000,
        limits: ReferenceRetrievalLimits | None = None,
    ) -> None:
        selected_limits = (
            DEFAULT_REFERENCE_RETRIEVAL_LIMITS if limits is None else limits
        )
        if type(selected_limits) is not ReferenceRetrievalLimits:
            raise ValidationError("reference limits must be ReferenceRetrievalLimits")
        _bounded_int(
            window_bp,
            "window_bp",
            minimum=1,
            maximum=selected_limits.max_window_bp,
        )
        if client is not None and type(client) is not SourceClient:
            raise ValidationError("public reference client must be a SourceClient")
        self.client = SourceClient(cache_root=cache_root) if client is None else client
        self.ensembl = EnsemblRestClient(self.client)
        self.ucsc = UcscRestClient(self.client)
        self.window_bp = window_bp
        self.limits = ReferenceRetrievalLimits(
            max_window_bp=selected_limits.max_window_bp,
            max_features_per_variant=selected_limits.max_features_per_variant,
            max_variants=selected_limits.max_variants,
            max_total_elements=selected_limits.max_total_elements,
            max_total_canonical_bytes=selected_limits.max_total_canonical_bytes,
            max_total_sequence_bp=selected_limits.max_total_sequence_bp,
        )
        self._lock = threading.RLock()

    @staticmethod
    def _object_configuration(
        target: object,
        names: tuple[str, ...] | None = None,
    ) -> _ObjectConfigurationSnapshot:
        namespace: dict[str, object] | None
        try:
            namespace = vars(target)
        except TypeError:
            namespace = None
        selected_names = (
            tuple(sorted(namespace))
            if names is None and namespace is not None
            else names
        )
        if selected_names is None:
            raise ValidationError("public reference configuration fields are missing")
        try:
            attributes = tuple((name, getattr(target, name)) for name in selected_names)
        except Exception as exc:  # noqa: BLE001 - mutable configuration boundary
            raise ValidationError("public reference configuration is malformed") from exc
        return _ObjectConfigurationSnapshot(
            target=target,
            target_type=type(target),
            attributes=attributes,
            namespace_names=None if namespace is None else frozenset(namespace),
        )

    def _capture_manifest_configuration(
        self,
        manifest: CaseManifest,
    ) -> tuple[Callable[[], None], Callable[[], None]]:
        manifest_fields = (
            "case_id",
            "subject_id",
            "context",
            "variants",
            "candidate_elements",
            "metadata",
            "input_versions",
            "requested_by",
        )
        context_fields = (
            "genome_build",
            "disease_class",
            "age_group",
            "cell_state",
            "territory",
            "treatment_phase",
            "assay_support",
            "source_version",
        )
        variant_fields = (
            "variant_id",
            "kind",
            "chromosome",
            "start",
            "end",
            "reference",
            "alternate",
            "genome_build",
            "origin",
            "clonality",
            "sample_id",
            "annotations",
        )
        element_fields = (
            "element_id",
            "chromosome",
            "start",
            "end",
            "element_type",
            "context",
            "source_id",
            "target_genes",
            "state_ids",
            "features",
            "annotations",
        )
        objects: list[tuple[object, tuple[str, ...]]] = [
            (manifest, manifest_fields),
            (manifest.context, context_fields),
            *((variant, variant_fields) for variant in manifest.variants),
            *((element, element_fields) for element in manifest.candidate_elements),
            *((element.context, context_fields) for element in manifest.candidate_elements),
        ]
        selected: list[_ObjectConfigurationSnapshot] = []
        seen: set[int] = set()
        for target, fields in objects:
            if id(target) in seen:
                continue
            seen.add(id(target))
            selected.append(self._object_configuration(target, fields))
        return _capture_object_configuration_guard(
            tuple(selected),
            message="public reference callback mutated enrichment manifest scope",
        )

    def _capture_invocation_configuration(
        self,
        caller_variant: VariantIdentity,
        caller_context: ReferenceContext,
        selected_variant: VariantIdentity,
        selected_context: ReferenceContext,
    ) -> _PublicReferenceInvocationSnapshot:
        client = self.client
        ensembl = self.ensembl
        ucsc = self.ucsc
        limits = self.limits
        lock = self._lock
        if type(client) is not SourceClient:
            raise ValidationError("public reference client configuration is invalid")
        if type(ensembl) is not EnsemblRestClient or ensembl.client is not client:
            raise ValidationError("public Ensembl client configuration is invalid")
        if type(ucsc) is not UcscRestClient or ucsc.client is not client:
            raise ValidationError("public UCSC client configuration is invalid")
        if type(limits) is not ReferenceRetrievalLimits:
            raise ValidationError("public reference limits configuration is invalid")
        if type(lock) is not _RLOCK_TYPE:
            raise ValidationError("public reference retrieval lock is invalid")
        _bounded_int(
            self.window_bp,
            "window_bp",
            minimum=1,
            maximum=limits.max_window_bp,
        )
        ReferenceRetrievalLimits(
            max_window_bp=limits.max_window_bp,
            max_features_per_variant=limits.max_features_per_variant,
            max_variants=limits.max_variants,
            max_total_elements=limits.max_total_elements,
            max_total_canonical_bytes=limits.max_total_canonical_bytes,
            max_total_sequence_bp=limits.max_total_sequence_bp,
        )

        if frozenset(vars(client)) != frozenset(
            {
                "catalog",
                "transport",
                "retry_policy",
                "timeout_seconds",
                "cache_ttl_seconds",
                "user_agent",
                "cache",
                "_limiters",
            }
        ):
            raise ValidationError("public source client has non-canonical configuration")
        catalog = client.catalog
        retry_policy = client.retry_policy
        cache = client.cache
        limiters = client._limiters  # noqa: SLF001 - public-source integrity boundary
        if type(catalog) is not SourceCatalog or type(catalog._specs) is not dict:  # noqa: SLF001
            raise ValidationError("public source catalog configuration is invalid")
        if type(retry_policy) is not RetryPolicy:
            raise ValidationError("public source retry configuration is invalid")
        if type(cache) is not SourceCache:
            raise ValidationError("public source cache configuration is invalid")
        if type(limiters) is not dict:
            raise ValidationError("public source limiter configuration is invalid")
        if not callable(getattr(client.transport, "request", None)):
            raise ValidationError("public source transport configuration is invalid")
        RetryPolicy(
            attempts=retry_policy.attempts,
            initial_backoff_seconds=retry_policy.initial_backoff_seconds,
            maximum_backoff_seconds=retry_policy.maximum_backoff_seconds,
            retry_statuses=retry_policy.retry_statuses,
        )
        _bounded_number(
            client.timeout_seconds,
            "source timeout_seconds",
            minimum=0.001,
            maximum=MAX_SOURCE_TIMEOUT_SECONDS,
        )
        _bounded_int(
            client.cache_ttl_seconds,
            "source cache_ttl_seconds",
            minimum=1,
            maximum=MAX_SOURCE_CACHE_TTL_SECONDS,
        )
        _required_text(client.user_agent, "source user_agent", maximum=512)
        if frozenset(vars(cache)) != frozenset({"root", "_locks", "_lock"}):
            raise ValidationError("public source cache has non-canonical configuration")
        if not isinstance(cache.root, Path) or not isinstance(cache._locks, Path):  # noqa: SLF001
            raise ValidationError("public source cache paths are invalid")
        if type(cache._lock) is not _RLOCK_TYPE:  # noqa: SLF001
            raise ValidationError("public source cache lock is invalid")
        if frozenset(vars(catalog)) != frozenset({"_specs", "_lock"}):
            raise ValidationError("public source catalog has non-canonical configuration")
        if type(catalog._lock) is not _RLOCK_TYPE:  # noqa: SLF001
            raise ValidationError("public source catalog lock is invalid")

        source_specs = tuple(catalog._specs[key] for key in sorted(catalog._specs))  # noqa: SLF001
        if len(source_specs) > MAX_SOURCE_CATALOG_ENTRIES or any(
            type(item) is not SourceSpec for item in source_specs
        ):
            raise ValidationError("public source catalog entries are invalid")
        source_field_names = (
            "source_id",
            "name",
            "kind",
            "access",
            "base_url",
            "canonical_url",
            "version",
            "license",
            "rate_limit_per_minute",
            "max_response_bytes",
            "max_region_bp",
            "terms",
            "enabled",
        )
        for spec in source_specs:
            SourceSpec(**{name: getattr(spec, name) for name in source_field_names})
        if frozenset(limiters) != frozenset(spec.source_id for spec in source_specs):
            raise ValidationError("public source limiters do not match the source catalog")
        limiter_states: list[_ObjectConfigurationSnapshot] = []
        for spec in source_specs:
            limiter = limiters[spec.source_id]
            if type(limiter) is not RateLimiter:
                raise ValidationError("public source limiter entry is invalid")
            if type(limiter._lock) is not type(threading.Lock()):  # noqa: SLF001
                raise ValidationError("public source limiter lock is invalid")
            if limiter.interval_seconds != 60.0 / spec.rate_limit_per_minute:
                raise ValidationError("public source limiter interval does not match its catalog")
            limiter_states.append(
                self._object_configuration(limiter, ("interval_seconds", "_lock"))
            )

        if EnsemblRestClient.source_id != "SRC-ENSEMBL-REST":
            raise ValidationError("public Ensembl source identity is invalid")
        if UcscRestClient.source_id != "SRC-UCSC-REST":
            raise ValidationError("public UCSC source identity is invalid")
        expected_assemblies = {
            "GRCh38": "hg38",
            "hg38": "hg38",
            "GRCh37": "hg19",
            "hg19": "hg19",
        }
        if (
            type(UcscRestClient._assemblies) is not dict
            or UcscRestClient._assemblies != expected_assemblies
        ):
            raise ValidationError("public UCSC assembly configuration is invalid")

        variant_fields = (
            "variant_id",
            "kind",
            "chromosome",
            "start",
            "end",
            "reference",
            "alternate",
            "genome_build",
            "origin",
            "clonality",
            "sample_id",
            "annotations",
        )
        context_fields = (
            "genome_build",
            "disease_class",
            "age_group",
            "cell_state",
            "territory",
            "treatment_phase",
            "assay_support",
            "source_version",
        )
        retry_fields = (
            "attempts",
            "initial_backoff_seconds",
            "maximum_backoff_seconds",
            "retry_statuses",
        )
        limit_fields = (
            "max_window_bp",
            "max_features_per_variant",
            "max_variants",
            "max_total_elements",
            "max_total_canonical_bytes",
            "max_total_sequence_bp",
        )
        scope_object_states = (
            self._object_configuration(caller_variant, variant_fields),
            self._object_configuration(caller_context, context_fields),
            self._object_configuration(selected_variant, variant_fields),
            self._object_configuration(selected_context, context_fields),
        )
        object_states = (
            *scope_object_states,
            self._object_configuration(self),
            self._object_configuration(client),
            self._object_configuration(ensembl),
            self._object_configuration(ucsc),
            self._object_configuration(catalog),
            self._object_configuration(cache),
            self._object_configuration(retry_policy, retry_fields),
            self._object_configuration(limits, limit_fields),
            *(
                self._object_configuration(spec, source_field_names)
                for spec in source_specs
            ),
            *limiter_states,
        )
        mapping_states = (
            _MappingConfigurationSnapshot(
                catalog._specs,  # noqa: SLF001 - public-source integrity boundary
                tuple(catalog._specs.items()),  # noqa: SLF001
            ),
            _MappingConfigurationSnapshot(limiters, tuple(limiters.items())),
            _MappingConfigurationSnapshot(
                UcscRestClient._assemblies,
                tuple(UcscRestClient._assemblies.items()),
            ),
        )
        semantic_unchanged, restore_semantics = _capture_public_reference_semantic_guard()
        return _PublicReferenceInvocationSnapshot(
            object_states=object_states,
            mapping_states=mapping_states,
            mutable_states=_capture_mutable_container_configuration(
                value
                for state in scope_object_states
                for _name, value in state.attributes
            ),
            semantic_unchanged=semantic_unchanged,
            restore_semantics=restore_semantics,
        )

    @staticmethod
    def _assert_invocation_configuration(
        expected: _PublicReferenceInvocationSnapshot,
    ) -> None:
        mutation_error_type = _SourceCallbackMutationError

        try:
            if not expected.semantic_unchanged():
                raise mutation_error_type
            for object_state in expected.object_states:
                if type(object_state.target) is not object_state.target_type:
                    raise mutation_error_type
                if object_state.namespace_names is not None and frozenset(
                    vars(object_state.target)
                ) != (
                    object_state.namespace_names
                ):
                    raise mutation_error_type
                for name, value in object_state.attributes:
                    if not _configuration_value_is_same(
                        getattr(object_state.target, name),
                        value,
                    ):
                        raise mutation_error_type
            for mapping_state in expected.mapping_states:
                current_items = tuple(mapping_state.target.items())
                if len(current_items) != len(mapping_state.items) or any(
                    not _configuration_value_is_same(current_key, expected_key)
                    or not _configuration_value_is_same(
                        current_value,
                        expected_value,
                    )
                    for (current_key, current_value), (expected_key, expected_value) in zip(
                        current_items,
                        mapping_state.items,
                        strict=True,
                    )
                ):
                    raise mutation_error_type
            if not _mutable_container_configuration_is_unchanged(
                expected.mutable_states
            ):
                raise mutation_error_type
        except Exception as exc:
            if type(exc) is mutation_error_type:
                raise mutation_error_type(
                    "public reference callback mutated invocation scope or "
                    "retriever configuration"
                ) from None
            raise mutation_error_type(
                "public reference callback mutated invocation scope or retriever configuration"
            ) from exc

    @staticmethod
    def _restore_invocation_configuration(
        expected: _PublicReferenceInvocationSnapshot,
    ) -> None:
        try:
            mutable_drifted = not _mutable_container_configuration_is_unchanged(
                expected.mutable_states
            )
            if not expected.semantic_unchanged():
                expected.restore_semantics()
            for object_state in expected.object_states:
                if type(object_state.target) is not object_state.target_type:
                    object.__setattr__(
                        object_state.target,
                        "__class__",
                        object_state.target_type,
                    )
                if object_state.namespace_names is not None:
                    object_namespace = vars(object_state.target)
                    for name in tuple(object_namespace):
                        if name not in object_state.namespace_names:
                            del object_namespace[name]
                for name, value in object_state.attributes:
                    object.__setattr__(object_state.target, name, value)
            for mapping_state in expected.mapping_states:
                mapping_state.target.clear()
                mapping_state.target.update(mapping_state.items)
            if mutable_drifted:
                _restore_mutable_container_configuration(expected.mutable_states)
        except Exception as exc:  # noqa: BLE001 - callback mutation recovery boundary
            raise ValidationError(
                "public reference callback configuration could not be restored"
            ) from exc

    def retrieve(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        *,
        window_bp: int | None = None,
        _external_integrity_guard: Callable[[], None] | None = None,
    ) -> ReferenceBundle:
        if _external_integrity_guard is not None and not callable(_external_integrity_guard):
            raise ValidationError("public reference external integrity guard must be callable")
        selected_scope = source_callback_scope
        if selected_scope is not _callback_isolation.source_callback_scope:
            raise ValidationError("public reference callback scope is invalid")
        with selected_scope():
            return self._retrieve_invocation(
                variant,
                context,
                window_bp=window_bp,
                _external_integrity_guard=_external_integrity_guard,
            )

    def _retrieve_invocation(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        *,
        window_bp: int | None = None,
        _external_integrity_guard: Callable[[], None] | None = None,
    ) -> ReferenceBundle:
        if type(variant) is not VariantIdentity:
            raise ValidationError("public reference variant must be a VariantIdentity")
        if type(context) is not ReferenceContext:
            raise ValidationError("public reference context must be a ReferenceContext")
        retrieval_lock = self._lock
        if type(retrieval_lock) is not _RLOCK_TYPE:
            raise ValidationError("public reference retrieval lock is invalid")
        with retrieval_lock:
            variant_raw = variant.to_dict()
            context_raw = context.to_dict()
            selected_variant = VariantIdentity.from_dict(variant_raw)
            selected_context = ReferenceContext.from_dict(context_raw, persisted=True)
            if _validated_canonical_bytes(
                variant_raw, "public reference variant"
            ) != _validated_canonical_bytes(
                selected_variant.to_dict(),
                "public reference variant",
            ):
                raise ValidationError("public reference variant is not canonical")
            if _validated_canonical_bytes(
                context_raw, "public reference context"
            ) != _validated_canonical_bytes(
                selected_context.to_dict(),
                "public reference context",
            ):
                raise ValidationError("public reference context is not canonical")
            if selected_variant.genome_build != selected_context.genome_build:
                raise ValidationError(
                    "variant and context genome builds must match for public retrieval"
                )
            selected_window = self.window_bp if window_bp is None else window_bp
            _bounded_int(
                selected_window,
                "window_bp",
                minimum=1,
                maximum=self.limits.max_window_bp,
            )
            snapshot_configuration = PublicReferenceRetriever._capture_invocation_configuration
            assert_configuration = cast(
                Callable[[_PublicReferenceInvocationSnapshot], None],
                detached_callback_guard(
                    PublicReferenceRetriever._assert_invocation_configuration
                ),
            )
            restore_configuration = cast(
                Callable[[_PublicReferenceInvocationSnapshot], None],
                detached_callback_guard(
                    PublicReferenceRetriever._restore_invocation_configuration
                ),
            )
            expected = snapshot_configuration(
                self,
                variant,
                context,
                selected_variant,
                selected_context,
            )
            semantic_unchanged = expected.semantic_unchanged
            restore_semantics = expected.restore_semantics
            mutation_error_type = _SourceCallbackMutationError
            base_exception_type = BaseException

            def integrity_guard() -> None:
                if _external_integrity_guard is not None:
                    _external_integrity_guard()
                if not semantic_unchanged():
                    restore_semantics()
                    raise mutation_error_type(
                        "public reference callback mutated invocation scope or retriever "
                        "configuration"
                    )
                assert_configuration(expected)

            try:
                integrity_guard()
                result = self._retrieve_guarded(
                    selected_variant,
                    selected_context,
                    selected_window,
                    integrity_guard,
                )
                integrity_guard()
                return result
            finally:
                semantic_drifted = not semantic_unchanged()
                restoration_error: BaseException | None = None
                if semantic_drifted:
                    try:
                        restore_semantics()
                    except base_exception_type as exc:  # noqa: BLE001 - recovery must continue
                        restoration_error = exc
                try:
                    restore_configuration(expected)
                except base_exception_type as exc:  # noqa: BLE001 - recovery must continue
                    restoration_error = restoration_error or exc
                if restoration_error is not None:
                    raise mutation_error_type(
                        "public reference callback configuration could not be restored"
                    ) from restoration_error
                if semantic_drifted:
                    raise mutation_error_type(
                        "public reference callback mutated invocation scope or retriever "
                        "configuration"
                    )

    def _retrieve_guarded(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        selected_window: int,
        integrity_guard: Callable[[], None],
    ) -> ReferenceBundle:
        chromosome, start, end = variant_interval(variant)
        query_start = max(1, start - selected_window)
        query_end = end + selected_window
        receipts: list[FetchReceipt] = []
        warnings: list[str] = []
        sequence: SequenceSlice | None = None
        mutation_error_type = _SourceCallbackMutationError
        ucsc = self.ucsc
        ensembl = self.ensembl
        limits = self.limits
        sequence_type = SequenceSlice
        bundle_create = ReferenceBundle.create
        candidate_converter = PublicReferenceRetriever._candidate_elements
        try:
            sequence_payload = UcscRestClient.sequence(
                ucsc,
                chromosome,
                query_start,
                query_end,
                genome_build=context.genome_build,
                _integrity_guard=integrity_guard,
            )
            integrity_guard()
            receipts.append(sequence_payload.receipt)
            raw_sequence = sequence_payload.value
            if not isinstance(raw_sequence, Mapping) or type(raw_sequence.get("dna")) is not str:
                raise SourceError("UCSC sequence response did not contain a dna string")
            sequence = sequence_type(
                assembly=context.genome_build,
                chromosome=normalize_chromosome(chromosome),
                start=query_start,
                end=query_end,
                sequence=str(raw_sequence["dna"]).upper(),
                source_id="SRC-UCSC-REST",
                receipt=sequence_payload.receipt,
            )
        except mutation_error_type:
            raise
        except (SourceError, ValidationError) as error:
            error_receipt = getattr(error, "receipt", None)
            if type(error_receipt) is FetchReceipt:
                receipts.append(error_receipt)
            warnings.append(f"sequence retrieval abstained: {error}"[:MAX_SOURCE_TEXT_LENGTH])
        integrity_guard()
        raw_features: list[Mapping[str, Any]] = []
        elements: list[CandidateElement] = []
        try:
            feature_payload = EnsemblRestClient.overlap_region(
                ensembl,
                chromosome,
                query_start,
                query_end,
                features=("regulatory", "motif", "gene"),
                _integrity_guard=integrity_guard,
            )
            integrity_guard()
            receipts.append(feature_payload.receipt)
            if not isinstance(feature_payload.value, list):
                raise SourceError("Ensembl overlap response was not an array")
            if len(feature_payload.value) > limits.max_features_per_variant:
                raise SourceError(
                    "Ensembl overlap response exceeded "
                    f"{limits.max_features_per_variant} features"
                )
            if any(not isinstance(item, Mapping) for item in feature_payload.value):
                raise SourceError("Ensembl overlap response contained a non-object feature")
            unique_features = {
                _validated_canonical_json(item, "reference feature"): item
                for item in feature_payload.value
            }
            raw_features.extend(unique_features[key] for key in sorted(unique_features))
        except mutation_error_type:
            raise
        except (SourceError, ValidationError) as error:
            error_receipt = getattr(error, "receipt", None)
            if type(error_receipt) is FetchReceipt:
                receipts.append(error_receipt)
            warnings.append(f"feature retrieval abstained: {error}"[:MAX_SOURCE_TEXT_LENGTH])
        else:
            try:
                elements = candidate_converter(
                    raw_features,
                    context,
                    variant,
                    query_start=query_start,
                    query_end=query_end,
                    max_features=limits.max_features_per_variant,
                )
            except ValidationError as error:
                # The source response and receipt remain valuable audit evidence even
                # when it cannot safely be promoted into typed candidate elements.
                warnings.append(
                    f"candidate materialization abstained: {error}"[
                        :MAX_SOURCE_TEXT_LENGTH
                    ]
                )
        integrity_guard()
        return bundle_create(
            variant_id=variant.variant_id,
            context=context,
            sequence=sequence,
            elements=tuple(elements),
            raw_features=tuple(raw_features),
            receipts=tuple(receipts),
            warnings=tuple(warnings),
        )

    def enrich_manifest(self, manifest: CaseManifest) -> EnrichmentResult:
        """Augment one detached manifest while restoring callback-visible caller state."""

        if type(manifest) is not CaseManifest:
            raise ValidationError("enrichment manifest must be a CaseManifest")
        selected_scope = source_manifest_callback_scope
        if selected_scope is not _callback_isolation.source_manifest_callback_scope:
            raise ValidationError("public reference manifest callback scope is invalid")
        with selected_scope():
            return self._enrich_manifest_entry(manifest)

    def _enrich_manifest_entry(self, manifest: CaseManifest) -> EnrichmentResult:
        """Run one source-manifest invocation inside the shared callback scope."""

        manifest_raw = manifest.to_dict()
        selected_manifest = CaseManifest.from_dict(manifest_raw)
        if _validated_canonical_bytes(
            manifest_raw,
            "enrichment manifest",
        ) != _validated_canonical_bytes(
            selected_manifest.to_dict(),
            "enrichment manifest",
        ):
            raise ValidationError("enrichment manifest is not canonical")
        retrieval_lock = self._lock
        if type(retrieval_lock) is not _RLOCK_TYPE:
            raise ValidationError("public reference retrieval lock is invalid")
        with retrieval_lock:
            capture_manifest = PublicReferenceRetriever._capture_manifest_configuration
            assert_manifest, restore_manifest = capture_manifest(self, manifest)
            try:
                assert_manifest()
                result = self._enrich_manifest_invocation(
                    selected_manifest,
                    _manifest_integrity_guard=assert_manifest,
                )
                assert_manifest()
                return result
            finally:
                restore_manifest()

    def _enrich_manifest_invocation(
        self,
        manifest: CaseManifest,
        *,
        _manifest_integrity_guard: Callable[[], None],
    ) -> EnrichmentResult:
        """Augment a manifest with live regulatory candidates without coercion."""

        if type(manifest) is not CaseManifest:
            raise ValidationError("enrichment manifest must be a CaseManifest")
        manifest_raw = manifest.to_dict()
        manifest_bytes = _validated_canonical_bytes(
            manifest_raw,
            "enrichment manifest",
        )
        if manifest_bytes != _validated_canonical_bytes(
            CaseManifest.from_dict(manifest_raw).to_dict(),
            "enrichment manifest",
        ):
            raise ValidationError("enrichment manifest is not canonical")
        if len(manifest_bytes) > self.limits.max_total_canonical_bytes:
            raise ValidationError(
                "live reference enrichment exceeds its configured canonical byte ceiling"
            )
        elements: dict[str, CandidateElement] = {
            element.element_id: element for element in manifest.candidate_elements
        }
        if len(elements) > self.limits.max_total_elements:
            raise ValidationError(
                "manifest candidate elements exceed the live reference total limit of "
                f"{self.limits.max_total_elements}"
            )
        catalog_input_versions = dict(manifest.input_versions) | {
            "live_reference_catalog": self.client.catalog.manifest()["content_address"]
        }
        manifest_static_bytes = (
            len(manifest_bytes)
            - len(
                _validated_canonical_bytes(
                    manifest_raw["candidate_elements"],
                    "enrichment manifest candidate elements",
                )
            )
            - len(
                _validated_canonical_bytes(
                    manifest_raw["input_versions"],
                    "enrichment manifest input versions",
                )
            )
        )
        candidate_element_bytes = sum(
            len(
                _validated_canonical_bytes(
                    element.to_dict(),
                    "live reference element",
                )
            )
            for element in elements.values()
        )
        projected_input_version_bytes = len(
            _validated_canonical_bytes(
                catalog_input_versions,
                "enrichment manifest input versions",
            )
        )
        bundles: list[ReferenceBundle] = []
        warnings: list[str] = []
        bundle_bytes = 0
        warning_bytes_by_value: dict[str, int] = {}
        warning_bytes = 0
        aggregate_sequence_bp = 0
        aggregate_bundle_elements = 0
        aggregate_raw_features = 0
        aggregate_receipts = 0
        aggregate_bundle_warnings = 0
        if len(manifest.variants) > self.limits.max_variants:
            raise ValidationError(
                "live reference enrichment cannot exceed "
                f"{self.limits.max_variants} variants"
            )
        projected_manifest_bytes = (
            manifest_static_bytes
            + _canonical_array_size(
                item_bytes=candidate_element_bytes,
                item_count=len(elements),
            )
            + projected_input_version_bytes
        )
        if _enrichment_result_size(
            manifest_bytes=projected_manifest_bytes,
            bundle_bytes=0,
            bundle_count=0,
            warning_bytes=0,
            warning_count=0,
        ) > self.limits.max_total_canonical_bytes:
            raise ValidationError(
                "live reference enrichment exceeds its configured canonical byte ceiling"
            )
        for variant in manifest.variants:
            bundle = self.retrieve(
                variant,
                manifest.context,
                _external_integrity_guard=_manifest_integrity_guard,
            )
            _manifest_integrity_guard()
            aggregate_bundle_elements += len(bundle.elements)
            if aggregate_bundle_elements > MAX_ENRICHED_ELEMENTS:
                raise ValidationError(
                    "live reference aggregate bundle element occurrences exceed their hard ceiling"
                )
            aggregate_raw_features += len(bundle.raw_features)
            if aggregate_raw_features > MAX_ENRICHED_ELEMENTS:
                raise ValidationError(
                    "live reference aggregate bundle raw feature occurrences exceed their hard "
                    "ceiling"
                )
            aggregate_receipts += len(bundle.receipts)
            if aggregate_receipts > MAX_REFERENCE_VARIANTS * MAX_REFERENCE_RECEIPTS:
                raise ValidationError(
                    "live reference aggregate bundle receipt occurrences exceed their hard ceiling"
                )
            aggregate_bundle_warnings += len(bundle.warnings)
            if aggregate_bundle_warnings > MAX_REFERENCE_WARNINGS:
                raise ValidationError(
                    "live reference aggregate bundle warning occurrences exceed their hard ceiling"
                )
            bundle_size = len(
                _validated_canonical_bytes(
                    bundle.to_dict(),
                    "live reference bundle",
                )
            )
            bundle_bytes += bundle_size
            if bundle.sequence is not None:
                aggregate_sequence_bp += len(bundle.sequence.sequence)
                if aggregate_sequence_bp > self.limits.max_total_sequence_bp:
                    raise ValidationError(
                        "live reference enrichment exceeds its configured sequence "
                        "base-pair ceiling"
                    )
            bundles.append(bundle)
            warnings.extend(bundle.warnings)
            for warning in bundle.warnings:
                if warning not in warning_bytes_by_value:
                    encoded_warning_size = len(
                        _validated_canonical_bytes(warning, "live reference warning")
                    )
                    warning_bytes_by_value[warning] = encoded_warning_size
                    warning_bytes += encoded_warning_size
            for element in bundle.elements:
                existing = elements.get(element.element_id)
                element_encoded = _validated_canonical_bytes(
                    element.to_dict(),
                    "live reference element",
                )
                if existing is not None and _validated_canonical_bytes(
                    existing.to_dict(),
                    "live reference element",
                ) != element_encoded:
                    raise ValidationError(
                        "live reference element conflicts with an existing manifest element: "
                        f"{element.element_id}"
                    )
                if existing is None:
                    if len(elements) >= self.limits.max_total_elements:
                        raise ValidationError(
                            "live reference enrichment cannot exceed "
                            f"{self.limits.max_total_elements} total elements"
                        )
                    elements[element.element_id] = element
                    candidate_element_bytes += len(element_encoded)
            projected_manifest_bytes = (
                manifest_static_bytes
                + _canonical_array_size(
                    item_bytes=candidate_element_bytes,
                    item_count=len(elements),
                )
                + projected_input_version_bytes
            )
            if _enrichment_result_size(
                manifest_bytes=projected_manifest_bytes,
                bundle_bytes=bundle_bytes,
                bundle_count=len(bundles),
                warning_bytes=warning_bytes,
                warning_count=len(warning_bytes_by_value),
            ) > self.limits.max_total_canonical_bytes:
                raise ValidationError(
                    "live reference enrichment exceeds its configured canonical byte ceiling"
                )
        enriched = replace(
            manifest,
            candidate_elements=tuple(elements[key] for key in sorted(elements)),
            input_versions=catalog_input_versions,
        )
        result = EnrichmentResult(
            enriched,
            tuple(bundles),
            tuple(dict.fromkeys(warnings)),
        )
        _manifest_integrity_guard()
        return result

    @staticmethod
    def _candidate_elements(
        features: Iterable[Mapping[str, Any]],
        context: ReferenceContext,
        variant: VariantIdentity,
        *,
        query_start: int | None = None,
        query_end: int | None = None,
        max_features: int = MAX_REFERENCE_FEATURES,
    ) -> list[CandidateElement]:
        if type(context) is not ReferenceContext or type(variant) is not VariantIdentity:
            raise ValidationError(
                "reference feature conversion requires typed context and variant objects"
            )
        if (query_start is None) != (query_end is None):
            raise ValidationError("reference query bounds must be supplied together")
        if query_start is not None and (
            type(query_start) is not int
            or type(query_end) is not int
            or query_start < 1
            or query_end < query_start
        ):
            raise ValidationError("reference query bounds are invalid")
        max_features = _bounded_int(
            max_features,
            "reference max_features",
            minimum=1,
            maximum=MAX_REFERENCE_FEATURES,
        )
        try:
            feature_rows = tuple(islice(iter(features), max_features + 1))
        except TypeError as exc:
            raise ValidationError("reference features must be iterable") from exc
        if len(feature_rows) > max_features:
            raise ValidationError(
                f"reference features cannot exceed {max_features} entries"
            )
        if any(not isinstance(feature, Mapping) for feature in feature_rows):
            raise ValidationError("reference feature entries must be objects")
        supported_feature_types = frozenset({"gene", "regulatory", "motif"})
        for feature in feature_rows:
            feature_type_raw = feature.get("feature_type")
            if (
                type(feature_type_raw) is not str
                or feature_type_raw.lower() not in supported_feature_types
            ):
                raise ValidationError(
                    "reference feature has a missing or unsupported feature_type"
                )
        expected_chromosome = normalize_chromosome(variant.chromosome)
        gene_identifiers: set[str] = set()
        for feature in feature_rows:
            feature_type_raw = cast(str, feature.get("feature_type"))
            if feature_type_raw.lower() != "gene":
                continue
            identifier = _required_text(
                feature.get("external_name") or feature.get("id"),
                "reference gene identifier",
                maximum=256,
            )
            if identifier != identifier.strip():
                raise ValidationError("reference gene identifier must use canonical spelling")
            if query_start is not None and query_end is not None:
                gene_start = feature.get("start")
                gene_end = feature.get("end")
                if (
                    type(gene_start) is not int
                    or type(gene_end) is not int
                    or gene_start < 1
                    or gene_end < gene_start
                ):
                    raise ValidationError("reference gene feature has invalid coordinates")
                raw_chromosome = feature.get("seq_region_name", variant.chromosome)
                if type(raw_chromosome) is not str:
                    raise ValidationError("reference gene chromosome must be a string")
                if normalize_chromosome(raw_chromosome) != expected_chromosome:
                    raise ValidationError("reference gene escaped the requested chromosome")
                if gene_end < query_start or gene_start > query_end:
                    raise ValidationError("reference gene escaped the requested interval")
            gene_identifiers.add(identifier)
        gene_ids = tuple(sorted(gene_identifiers))
        elements: list[CandidateElement] = []
        seen: dict[str, str] = {}
        for feature in feature_rows:
            feature_type_raw = cast(str, feature.get("feature_type"))
            feature_type = feature_type_raw.lower()
            if feature_type not in {"regulatory", "motif"}:
                continue
            start = feature.get("start")
            end = feature.get("end")
            if type(start) is not int or type(end) is not int or start < 1 or end < start:
                raise ValidationError("reference regulatory feature has invalid coordinates")
            raw_id = feature.get("id") or f"ensembl-{feature_type}-{start}-{end}"
            element_id = _required_text(
                raw_id,
                "reference element identifier",
                maximum=1_024,
            )
            if element_id != element_id.strip():
                raise ValidationError("reference element identifier must use canonical spelling")
            raw_chromosome = feature.get("seq_region_name", variant.chromosome)
            if type(raw_chromosome) is not str:
                raise ValidationError("reference feature chromosome must be a string")
            chromosome = normalize_chromosome(raw_chromosome)
            if chromosome != expected_chromosome:
                raise ValidationError("reference feature escaped the requested chromosome")
            if query_start is not None and query_end is not None and (
                end < query_start or start > query_end
            ):
                raise ValidationError("reference feature escaped the requested interval")
            feature_identity = _validated_canonical_json(feature, "reference feature")
            previous_identity = seen.get(element_id)
            if previous_identity is not None:
                if previous_identity != feature_identity:
                    raise ValidationError(
                        f"reference element identifier has conflicting features: {element_id}"
                    )
                continue
            if not gene_ids:
                continue
            seen[element_id] = feature_identity
            description_raw = feature.get("description") or feature.get("logic_name") or ""
            if type(description_raw) is not str or len(description_raw) > MAX_SOURCE_TEXT_LENGTH:
                raise ValidationError("reference feature description must be a bounded string")
            _validated_utf8(description_raw, "reference feature description")
            if any(ord(character) < 32 or ord(character) == 127 for character in description_raw):
                raise ValidationError("reference feature description contains control characters")
            elements.append(
                CandidateElement(
                    element_id=element_id,
                    chromosome=chromosome,
                    start=start,
                    end=end,
                    element_type=feature_type,
                    context=context,
                    source_id="SRC-ENSEMBL-REST",
                    target_genes=gene_ids,
                    state_ids=(),
                    features={"regulatory_overlap": 1.0},
                    annotations={
                        "link_method": "regional_overlap_baseline",
                        "source_feature": feature,
                        "description": description_raw,
                        "alternative_explanations": (
                            "nearby gene assignment is a baseline, not a causal link",
                        ),
                    },
                )
            )
        return sorted(elements, key=lambda item: item.element_id)


class LiveReferenceAdapter:
    """Adapter-registry compatible view over the public retriever."""

    def __init__(self, retriever: PublicReferenceRetriever | None = None) -> None:
        if retriever is not None and type(retriever) is not PublicReferenceRetriever:
            raise ValidationError("live reference adapter requires a PublicReferenceRetriever")
        self.retriever = PublicReferenceRetriever() if retriever is None else retriever
        self.metadata = AdapterMetadata(
            adapter_id="live-public-reference",
            display_name="Ensembl and UCSC live public reference",
            version="0.2",
            license="source-specific terms",
            data_access="public_api",
            supported_contexts=("GRCh38", "GRCh37"),
            channels=("reference_sequence", "regulatory_overlap", "gene_overlap"),
            failure_modes=(
                "rate_limit",
                "source_unavailable",
                "assembly_unsupported",
                "empty_overlap",
            ),
            validation_status="integration-tested",
            documentation_url="docs/OPERATIONS.md",
            source_ids=("SRC-ENSEMBL-REST", "SRC-UCSC-REST"),
        )

    def resolve_elements(
        self, variant_id: str, context: ReferenceContext
    ) -> tuple[CandidateElement, ...]:
        raise ValidationError(
            "LiveReferenceAdapter.resolve_elements requires a VariantIdentity; use resolve_variant"
        )

    def resolve_variant(
        self, variant: VariantIdentity, context: ReferenceContext
    ) -> ReferenceBundle:
        return self.retriever.retrieve(variant, context)

    def resolve_variant_elements(
        self, variant: VariantIdentity, context: ReferenceContext
    ) -> tuple[CandidateElement, ...]:
        """Resolve elements through the registry's typed variant-aware path."""

        return self.resolve_variant(variant, context).elements

    def enrich_manifest(self, manifest: CaseManifest) -> EnrichmentResult:
        return self.retriever.enrich_manifest(manifest)

    def collect_claims(
        self, variant_id: str, element_id: str, context: ReferenceContext
    ) -> tuple[Any, ...]:
        return ()
