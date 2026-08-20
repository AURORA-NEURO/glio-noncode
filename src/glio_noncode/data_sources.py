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
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from .errors import SourceError, SourceNotFoundError, SourceRateLimitError, ValidationError
from .identity import normalize_chromosome, variant_interval
from .models import CandidateElement, CaseManifest, ReferenceContext, VariantIdentity
from .serialization import canonical_json, content_hash, jsonable, utc_now
from .adapters import AdapterMetadata


class SourceKind(str, Enum):
    STANDARD = "standard"
    REFERENCE_PORTAL = "reference_portal"
    REFERENCE_ANNOTATION = "reference_annotation"
    GENOME_BROWSER = "genome_browser"
    FUNCTIONAL_GENOMICS = "functional_genomics"
    COHORT = "cohort"


class SourceAccess(str, Enum):
    PUBLIC_API = "public_api"
    PUBLIC_DOWNLOAD = "public_download"
    CONTROLLED = "controlled"
    LOCAL_ONLY = "local_only"


class FetchStatus(str, Enum):
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
        for name in ("source_id", "name", "base_url", "canonical_url", "version", "license"):
            value = getattr(self, name)
            if not value or not value.strip():
                raise ValidationError(f"source field must not be empty: {name}")
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError(f"source base_url must be an HTTP(S) URL: {self.base_url}")
        if self.rate_limit_per_minute < 1:
            raise ValidationError("rate_limit_per_minute must be positive")
        if self.max_response_bytes < 1024:
            raise ValidationError("max_response_bytes is too small")
        if self.max_region_bp is not None and self.max_region_bp < 1:
            raise ValidationError("max_region_bp must be positive or None")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry only transport/server failures with unchanged request semantics."""

    attempts: int = 3
    initial_backoff_seconds: float = 0.25
    maximum_backoff_seconds: float = 4.0
    retry_statuses: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValidationError("retry attempts must be positive")
        if (
            self.initial_backoff_seconds < 0
            or self.maximum_backoff_seconds < self.initial_backoff_seconds
        ):
            raise ValidationError("retry backoff values are invalid")

    def backoff(self, retry_number: int) -> float:
        return min(self.maximum_backoff_seconds, self.initial_backoff_seconds * (2**retry_number))


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """Raw bounded HTTP response before source-specific decoding."""

    status: int
    url: str
    headers: Mapping[str, str]
    body: bytes
    elapsed_seconds: float

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";", 1)[0].strip().lower()


class HttpTransport(Protocol):
    """Minimal transport seam used by live code and deterministic tests."""

    def request(
        self, method: str, url: str, headers: Mapping[str, str], timeout_seconds: float
    ) -> TransportResponse: ...


class UrllibTransport:
    """Standard-library HTTPS transport with a hard response-size limit."""

    def __init__(self, *, max_response_bytes: int = 25_000_000) -> None:
        if max_response_bytes < 1024:
            raise ValidationError("max_response_bytes is too small")
        self.max_response_bytes = max_response_bytes

    def request(
        self, method: str, url: str, headers: Mapping[str, str], timeout_seconds: float
    ) -> TransportResponse:
        started = time.monotonic()
        request = urllib.request.Request(url, method=method, headers=dict(headers))
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise SourceError(f"response exceeded {self.max_response_bytes} bytes")
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
                body = body[: self.max_response_bytes]
            response_headers = {key.lower(): value for key, value in error.headers.items()}
            return TransportResponse(
                status=int(error.code),
                url=url,
                headers=response_headers,
                body=body,
                elapsed_seconds=round(time.monotonic() - started, 6),
            )
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise SourceError(f"transport failure for {url}: {error}") from error


class RateLimiter:
    """Thread-safe spacing limiter for one public source."""

    def __init__(self, requests_per_minute: int) -> None:
        if requests_per_minute < 1:
            raise ValidationError("requests_per_minute must be positive")
        self.interval_seconds = 60.0 / requests_per_minute
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self, *, max_wait_seconds: float = 30.0) -> float:
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

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SourcePayload:
    """Decoded payload plus its receipt; payloads are never anonymous."""

    value: Any
    receipt: FetchReceipt
    content_type: str

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


class SourceCache:
    """Filesystem cache keyed by request hash and protected by atomic writes."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, request_hash: str) -> Path:
        digest = request_hash.split(":", 1)[-1]
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValidationError(f"invalid request hash: {request_hash}")
        return self.root / f"{digest}.json"

    def get(self, request_hash: str, *, now: datetime | None = None) -> CacheEntry | None:
        path = self._path(request_hash)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            expires_at = datetime.fromisoformat(str(raw["expires_at"]))
            current = now or datetime.now(timezone.utc)
            if expires_at <= current:
                return None
            body = bytes.fromhex(str(raw["body_hex"]))
            return CacheEntry(
                request_hash=str(raw["request_hash"]),
                source_id=str(raw["source_id"]),
                source_version=str(raw["source_version"]),
                url=str(raw["url"]),
                response_hash=str(raw["response_hash"]),
                content_type=str(raw["content_type"]),
                body=body,
                retrieved_at=str(raw["retrieved_at"]),
                expires_at=str(raw["expires_at"]),
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
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
        if ttl_seconds < 1:
            raise ValidationError("cache TTL must be positive")
        retrieved = datetime.now(timezone.utc)
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
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            canonical_json(
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
            ),
            encoding="utf-8",
        )
        temporary.replace(path)
        return entry


class SourceCatalog:
    """Registry of source metadata used by clients and release reports."""

    def __init__(self, specs: Iterable[SourceSpec] = ()) -> None:
        self._specs: dict[str, SourceSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: SourceSpec) -> None:
        if spec.source_id in self._specs:
            raise ValidationError(f"source already registered: {spec.source_id}")
        self._specs[spec.source_id] = spec

    def get(self, source_id: str) -> SourceSpec:
        try:
            return self._specs[source_id]
        except KeyError as exc:
            raise SourceError(f"source is not registered: {source_id}") from exc

    def list(self) -> tuple[SourceSpec, ...]:
        return tuple(self._specs[key] for key in sorted(self._specs))

    def manifest(self) -> dict[str, Any]:
        return {
            "sources": [spec.to_dict() for spec in self.list()],
            "content_address": content_hash([spec.to_dict() for spec in self.list()]),
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
                terms="Regional overlap is bounded; feature semantics and release version must be recorded.",
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
                terms="Small-window sequence and track requests only; bulk data should use downloads.",
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
                terms="Metadata retrieval only in this module; assay files require separate access and QC.",
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
        self.catalog = catalog or default_source_catalog()
        self.cache = SourceCache(cache_root)
        self.transport = transport or UrllibTransport()
        self.retry_policy = retry_policy or RetryPolicy()
        if timeout_seconds <= 0:
            raise ValidationError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self.user_agent = user_agent
        self._limiters = {
            spec.source_id: RateLimiter(spec.rate_limit_per_minute) for spec in self.catalog.list()
        }

    def build_url(
        self, source: SourceSpec, path: str, params: Mapping[str, Any] | None = None
    ) -> str:
        if not path.startswith("/"):
            path = "/" + path
        url = source.base_url.rstrip("/") + path
        clean = {key: value for key, value in (params or {}).items() if value is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean, doseq=True)
        return url

    def fetch_json(
        self,
        source_id: str,
        path: str,
        params: Mapping[str, Any] | None = None,
        *,
        allow_not_found: bool = False,
        cache: bool = True,
    ) -> SourcePayload:
        return self._fetch(
            source_id, path, params, expect_json=True, allow_not_found=allow_not_found, cache=cache
        )

    def fetch_text(
        self,
        source_id: str,
        path: str,
        params: Mapping[str, Any] | None = None,
        *,
        allow_not_found: bool = False,
        cache: bool = True,
    ) -> SourcePayload:
        return self._fetch(
            source_id, path, params, expect_json=False, allow_not_found=allow_not_found, cache=cache
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
    ) -> SourcePayload:
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
        cached = self.cache.get(request_hash) if cache else None
        if cached is not None:
            receipt = FetchReceipt(
                source_id=source.source_id,
                source_version=source.version,
                url=url,
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
            return self._decode(cached.body, receipt, cached.content_type, expect_json)
        limiter = self._limiters[source.source_id]
        headers = {
            "Accept": "application/json" if expect_json else "text/plain,application/json",
            "User-Agent": self.user_agent,
        }
        last_response: TransportResponse | None = None
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.attempts + 1):
            try:
                limiter.wait()
                response = self.transport.request("GET", url, headers, self.timeout_seconds)
                last_response = response
                if 200 <= response.status < 300:
                    if len(response.body) > source.max_response_bytes:
                        raise SourceError(
                            f"source response exceeded {source.max_response_bytes} bytes"
                        )
                    response_hash = f"sha256:{hashlib.sha256(response.body).hexdigest()}"
                    entry = (
                        self.cache.put(
                            request_hash=request_hash,
                            source=source,
                            url=response.url,
                            body=response.body,
                            content_type=response.content_type,
                            ttl_seconds=self.cache_ttl_seconds,
                        )
                        if cache
                        else None
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
                        retrieved_at=utc_now().isoformat(),
                        elapsed_seconds=response.elapsed_seconds,
                        cache_expires_at=entry.expires_at if entry else None,
                    )
                    return self._decode(response.body, receipt, response.content_type, expect_json)
                if response.status == 404:
                    receipt = FetchReceipt(
                        source_id=source.source_id,
                        source_version=source.version,
                        url=response.url,
                        request_hash=request_hash,
                        response_hash=f"sha256:{hashlib.sha256(response.body).hexdigest()}",
                        status=FetchStatus.NOT_FOUND,
                        http_status=response.status,
                        attempts=attempt,
                        retrieved_at=utc_now().isoformat(),
                        elapsed_seconds=response.elapsed_seconds,
                        cache_expires_at=None,
                    )
                    if allow_not_found:
                        return SourcePayload(None, receipt, response.content_type)
                    raise SourceNotFoundError(f"source object was not found: {url}")
                if response.status not in self.retry_policy.retry_statuses:
                    raise SourceError(f"source returned HTTP {response.status}: {url}")
                if attempt < self.retry_policy.attempts:
                    time.sleep(self.retry_policy.backoff(attempt - 1))
            except SourceNotFoundError:
                raise
            except SourceRateLimitError:
                last_error = SourceRateLimitError("source request spacing limit exceeded")
                break
            except (SourceError, ValueError, json.JSONDecodeError) as error:
                last_error = error
                if attempt < self.retry_policy.attempts:
                    time.sleep(self.retry_policy.backoff(attempt - 1))
            except Exception as error:  # pragma: no cover - defensive transport boundary
                last_error = SourceError(str(error))
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
            attempts=self.retry_policy.attempts,
            retrieved_at=utc_now().isoformat(),
            elapsed_seconds=last_response.elapsed_seconds if last_response is not None else None,
            cache_expires_at=None,
            warnings=("source failure is not a negative measurement",),
            error_type=type(last_error).__name__ if last_error is not None else "unknown",
            error_message=str(last_error) if last_error is not None else "unknown source failure",
        )
        if isinstance(last_error, SourceRateLimitError):
            raise SourceRateLimitError(str(last_error), receipt=failure_receipt) from last_error
        if last_response is not None:
            raise SourceError(
                f"source failed after {self.retry_policy.attempts} attempts: HTTP {last_response.status} {url}",
                receipt=failure_receipt,
            ) from last_error
        raise SourceError(
            f"source failed after {self.retry_policy.attempts} attempts: {url}",
            receipt=failure_receipt,
        ) from last_error

    @staticmethod
    def _decode(
        body: bytes, receipt: FetchReceipt, content_type: str, expect_json: bool
    ) -> SourcePayload:
        if expect_json:
            try:
                value = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise SourceError(f"source returned invalid JSON for {receipt.url}") from error
        else:
            try:
                value = body.decode("utf-8")
            except UnicodeDecodeError as error:
                raise SourceError(f"source returned non-UTF8 text for {receipt.url}") from error
        return SourcePayload(value, receipt, content_type)


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
        if self.start < 1 or self.end < self.start:
            raise ValidationError("sequence interval is invalid")
        if len(self.sequence) != self.end - self.start + 1:
            raise ValidationError("sequence length does not match its inclusive interval")
        if any(base.upper() not in "ACGTN" for base in self.sequence):
            raise ValidationError("sequence contains characters outside A/C/G/T/N")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceBundle:
    """All live observations retrieved for one bounded variant request."""

    variant_id: str
    context_key: str
    sequence: SequenceSlice | None
    elements: tuple[CandidateElement, ...]
    raw_features: tuple[Mapping[str, Any], ...]
    receipts: tuple[FetchReceipt, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    """Manifest plus live source bundles; failures remain explicit warnings."""

    manifest: CaseManifest
    bundles: tuple[ReferenceBundle, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "bundles": [bundle.to_dict() for bundle in self.bundles],
            "warnings": list(self.warnings),
            "content_address": content_hash(
                {
                    "manifest": self.manifest.to_dict(),
                    "bundles": [bundle.to_dict() for bundle in self.bundles],
                    "warnings": list(self.warnings),
                }
            ),
        }


class EnsemblRestClient:
    """Bounded Ensembl REST operations used by the reference retriever."""

    source_id = "SRC-ENSEMBL-REST"

    def __init__(self, client: SourceClient) -> None:
        self.client = client

    def sequence_region(
        self, chromosome: str, start: int, end: int, *, species: str = "homo_sapiens"
    ) -> SourcePayload:
        if end - start + 1 > 10_000_000:
            raise ValidationError("Ensembl sequence request exceeds the 10 Mb endpoint limit")
        region = f"{normalize_chromosome(chromosome)[3:]}:{start}..{end}:1"
        return self.client.fetch_text(self.source_id, f"/sequence/region/{species}/{region}")

    def lookup_symbol(
        self, symbol: str, *, species: str = "homo_sapiens", expand: bool = False
    ) -> SourcePayload:
        if not symbol.strip():
            raise ValidationError("gene symbol must not be empty")
        params = {"expand": "1"} if expand else None
        encoded = urllib.parse.quote(symbol.strip(), safe="")
        return self.client.fetch_json(self.source_id, f"/lookup/symbol/{species}/{encoded}", params)

    def overlap_region(
        self,
        chromosome: str,
        start: int,
        end: int,
        *,
        features: Iterable[str],
        species: str = "homo_sapiens",
    ) -> SourcePayload:
        source = self.client.catalog.get(self.source_id)
        if end < start or end - start + 1 > (source.max_region_bp or 5_000_000):
            raise ValidationError("Ensembl regional overlap exceeds the configured source limit")
        region = f"{normalize_chromosome(chromosome)[3:]}:{start}-{end}"
        params: list[tuple[str, str]] = [("feature", str(feature)) for feature in features]
        query = urllib.parse.urlencode(params)
        return self.client.fetch_json(self.source_id, f"/overlap/region/{species}/{region}?{query}")


class UcscRestClient:
    """Small-window UCSC sequence and track operations."""

    source_id = "SRC-UCSC-REST"

    _assemblies = {"GRCh38": "hg38", "hg38": "hg38", "GRCh37": "hg19", "hg19": "hg19"}

    def __init__(self, client: SourceClient) -> None:
        self.client = client

    def assembly_name(self, genome_build: str) -> str:
        try:
            return self._assemblies[genome_build]
        except KeyError as exc:
            raise ValidationError(f"UCSC assembly is not configured for {genome_build}") from exc

    def sequence(
        self, chromosome: str, start: int, end: int, *, genome_build: str
    ) -> SourcePayload:
        source = self.client.catalog.get(self.source_id)
        if end < start or end - start + 1 > (source.max_region_bp or 10_000_000):
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
        if max_items < 1 or max_items > 100_000:
            raise ValidationError("max_items must be between 1 and 100000")
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
        self.client = client

    def search_experiments(
        self,
        *,
        assay_title: str | None = None,
        biosample_ontology_term_name: str | None = None,
        organism: str = "Homo sapiens",
        limit: int = 25,
    ) -> SourcePayload:
        if limit < 1 or limit > 1000:
            raise ValidationError("ENCODE limit must be between 1 and 1000")
        params: dict[str, Any] = {
            "type": "Experiment",
            "format": "json",
            "limit": limit,
            "organism.scientific_name": organism,
        }
        if assay_title:
            params["assay_title"] = assay_title
        if biosample_ontology_term_name:
            params["biosample_ontology.term_name"] = biosample_ontology_term_name
        return self.client.fetch_json(self.source_id, "/search/", params)

    def object(self, accession: str) -> SourcePayload:
        normalized = accession.strip().strip("/")
        if not normalized or any(char in normalized for char in "?#"):
            raise ValidationError("ENCODE accession is invalid")
        return self.client.fetch_json(
            self.source_id,
            f"/{urllib.parse.quote(normalized, safe='/')}/",
            {"format": "json", "frame": "object"},
        )


class PublicReferenceRetriever:
    """Retrieve real sequence and nearby regulatory/gene features for a variant."""

    def __init__(
        self,
        client: SourceClient | None = None,
        *,
        cache_root: str | Path = ".glio/source-cache",
        window_bp: int = 2_000,
    ) -> None:
        if window_bp < 1 or window_bp > 5_000_000:
            raise ValidationError("window_bp must be between 1 and 5000000")
        self.client = client or SourceClient(cache_root=cache_root)
        self.ensembl = EnsemblRestClient(self.client)
        self.ucsc = UcscRestClient(self.client)
        self.window_bp = window_bp

    def retrieve(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        *,
        window_bp: int | None = None,
    ) -> ReferenceBundle:
        if variant.genome_build != context.genome_build:
            raise ValidationError(
                "variant and context genome builds must match for public retrieval"
            )
        selected_window = self.window_bp if window_bp is None else window_bp
        if selected_window < 1 or selected_window > 5_000_000:
            raise ValidationError("window_bp must be between 1 and 5000000")
        chromosome, start, end = variant_interval(variant)
        query_start = max(1, start - selected_window)
        query_end = end + selected_window
        receipts: list[FetchReceipt] = []
        warnings: list[str] = []
        sequence: SequenceSlice | None = None
        try:
            sequence_payload = self.ucsc.sequence(
                chromosome, query_start, query_end, genome_build=context.genome_build
            )
            receipts.append(sequence_payload.receipt)
            raw_sequence = sequence_payload.value
            if not isinstance(raw_sequence, Mapping) or not isinstance(
                raw_sequence.get("dna"), str
            ):
                raise SourceError("UCSC sequence response did not contain a dna string")
            sequence = SequenceSlice(
                assembly=context.genome_build,
                chromosome=normalize_chromosome(chromosome),
                start=query_start,
                end=query_end,
                sequence=str(raw_sequence["dna"]).upper(),
                source_id="SRC-UCSC-REST",
                receipt=sequence_payload.receipt,
            )
        except SourceError as error:
            if getattr(error, "receipt", None) is not None:
                receipts.append(error.receipt)
            warnings.append(f"sequence retrieval abstained: {error}")
        raw_features: list[Mapping[str, Any]] = []
        elements: list[CandidateElement] = []
        try:
            feature_payload = self.ensembl.overlap_region(
                chromosome,
                query_start,
                query_end,
                features=("regulatory", "motif", "gene"),
            )
            receipts.append(feature_payload.receipt)
            if isinstance(feature_payload.value, list):
                raw_features.extend(
                    item for item in feature_payload.value if isinstance(item, Mapping)
                )
            elements = self._candidate_elements(raw_features, context, variant)
        except SourceError as error:
            if getattr(error, "receipt", None) is not None:
                receipts.append(error.receipt)
            warnings.append(f"feature retrieval abstained: {error}")
        bundle_payload = {
            "variant_id": variant.variant_id,
            "context_key": context.key,
            "sequence": sequence.to_dict() if sequence else None,
            "elements": [element.to_dict() for element in elements],
            "raw_features": raw_features,
            "receipts": [receipt.to_dict() for receipt in receipts],
            "warnings": warnings,
        }
        return ReferenceBundle(
            variant_id=variant.variant_id,
            context_key=context.key,
            sequence=sequence,
            elements=tuple(elements),
            raw_features=tuple(raw_features),
            receipts=tuple(receipts),
            warnings=tuple(warnings),
            content_address=content_hash(bundle_payload),
        )

    def enrich_manifest(self, manifest: CaseManifest) -> EnrichmentResult:
        """Augment a manifest with live regulatory candidates without coercion."""

        elements: dict[str, CandidateElement] = {
            element.element_id: element for element in manifest.candidate_elements
        }
        bundles: list[ReferenceBundle] = []
        warnings: list[str] = []
        for variant in manifest.variants:
            bundle = self.retrieve(variant, manifest.context)
            bundles.append(bundle)
            warnings.extend(bundle.warnings)
            for element in bundle.elements:
                elements.setdefault(element.element_id, element)
        enriched = replace(
            manifest,
            candidate_elements=tuple(elements[key] for key in sorted(elements)),
            input_versions=dict(manifest.input_versions)
            | {"live_reference_catalog": self.client.catalog.manifest()["content_address"]},
        )
        return EnrichmentResult(enriched, tuple(bundles), tuple(dict.fromkeys(warnings)))

    @staticmethod
    def _candidate_elements(
        features: Iterable[Mapping[str, Any]],
        context: ReferenceContext,
        variant: VariantIdentity,
    ) -> list[CandidateElement]:
        genes = [
            feature
            for feature in features
            if str(feature.get("feature_type", "")).lower() == "gene"
        ]
        gene_ids = tuple(
            str(feature.get("external_name") or feature.get("id"))
            for feature in genes
            if feature.get("external_name") or feature.get("id")
        )
        elements: list[CandidateElement] = []
        seen: set[str] = set()
        for feature in features:
            feature_type = str(feature.get("feature_type", "")).lower()
            if feature_type not in {"regulatory", "motif"}:
                continue
            try:
                element_id = str(
                    feature.get("id")
                    or f"ensembl-{feature_type}-{feature['start']}-{feature['end']}"
                )
                chromosome = normalize_chromosome(
                    str(feature.get("seq_region_name", variant.chromosome))
                )
                start = int(feature["start"])
                end = int(feature["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if element_id in seen or not gene_ids:
                continue
            seen.add(element_id)
            description = str(feature.get("description") or feature.get("logic_name") or "")
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
                        "description": description,
                        "alternative_explanations": (
                            "nearby gene assignment is a baseline, not a causal link",
                        ),
                    },
                )
            )
        return elements


class LiveReferenceAdapter:
    """Adapter-registry compatible view over the public retriever."""

    def __init__(self, retriever: PublicReferenceRetriever | None = None) -> None:
        self.retriever = retriever or PublicReferenceRetriever()
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

    def enrich_manifest(self, manifest):
        return self.retriever.enrich_manifest(manifest)

    def collect_claims(
        self, variant_id: str, element_id: str, context: ReferenceContext
    ) -> tuple[Any, ...]:
        return ()
