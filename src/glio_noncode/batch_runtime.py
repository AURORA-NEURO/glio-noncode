"""Content-addressed batch evaluation and reopening contracts.

The case runtime remains the source of truth for one manifest.  This module
adds a durable orchestration envelope around it: each manifest is evaluated
independently, a failed item is retained beside successful items, and the batch
result can be reopened by its content-derived identifier.  Batch execution does
not weaken the research-only policy or convert a partial batch into an accepted
result.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data_sources import PublicReferenceRetriever
from .errors import GlioError, StoreError, ValidationError
from .models import CaseManifest
from .module_fabric_support import contains_private_key
from .runtime import CaseRuntime
from .serialization import _strict_json_loads, canonical_bytes, canonical_json, content_hash, utc_now
from .storage import _address_digest, _atomic_write_text, _filesystem_lock, _run_lock

BATCH_RUNTIME_VERSION = "batch-runtime-v1"
BATCH_DEFAULT_MAX_ITEMS = 100
BATCH_HARD_MAX_ITEMS = 1000
BATCH_CATALOG_DEFAULT_LIMIT = 25
BATCH_CATALOG_MAX_LIMIT = 100
BATCH_ITEM_STATES = ("accepted", "failed")
_HARD_MAX_BATCH_INDEX_BYTES = 64 * 1024
_HARD_MAX_BATCH_INPUT_BYTES = 128 * 1024 * 1024
_HARD_MAX_BATCH_RESULT_BYTES = 32 * 1024 * 1024
_HARD_MAX_BATCH_ITEM_INPUT_BYTES = 128 * 1024 * 1024
MAX_BATCH_INDEX_BYTES = _HARD_MAX_BATCH_INDEX_BYTES
MAX_BATCH_INPUT_BYTES = _HARD_MAX_BATCH_INPUT_BYTES
MAX_BATCH_RESULT_BYTES = _HARD_MAX_BATCH_RESULT_BYTES
MAX_BATCH_ITEM_INPUT_BYTES = _HARD_MAX_BATCH_ITEM_INPUT_BYTES
_BATCH_LOCK_ATTEMPTS = 20
_BATCH_RUN_ID_RE = re.compile(r"run-[0-9a-f]{24}\Z")
_BATCH_ITEM_FIELDS = frozenset(
    {
        "index",
        "case_id",
        "state",
        "input_address",
        "run_id",
        "dossier_address",
        "error_code",
        "error_message",
        "accepted",
        "content_address",
    }
)
_BATCH_RESULT_FIELDS = frozenset(
    {
        "batch_version",
        "batch_id",
        "label",
        "input_address",
        "created_at",
        "requested_count",
        "completed_count",
        "accepted_count",
        "failed_count",
        "items",
        "options",
        "accepted",
    }
)
_BATCH_OPTION_FIELDS = frozenset({"live_reference", "window_bp", "max_items"})
_BATCH_INDEX_FIELDS = frozenset(
    {"batch_id", "result_address", "input_address", "created_at", "accepted"}
)
_BATCH_INPUT_FIELDS = frozenset(
    {"batch_id", "manifests", "live_reference", "window_bp", "max_items"}
)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object field: {key}")
        value[key] = item
    return value


def _invalid_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _require_exact_fields(raw: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = frozenset(raw)
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "none"
        unexpected = ", ".join(sorted(str(field) for field in actual - expected)) or "none"
        raise ValidationError(
            f"{label} fields are invalid (missing: {missing}; unexpected: {unexpected})"
        )


def _required_field(raw: Mapping[str, Any], field: str) -> Any:
    if field not in raw:
        raise ValidationError(f"batch payload is missing {field}")
    return raw[field]


def _required_string(raw: Mapping[str, Any], field: str, *, allow_empty: bool = False) -> str:
    value = _required_field(raw, field)
    if type(value) is not str or (not allow_empty and not value.strip()):
        raise ValidationError(f"batch {field} must be a string")
    return value


def _optional_string(raw: Mapping[str, Any], field: str) -> str | None:
    value = _required_field(raw, field)
    if value is None:
        return None
    if type(value) is not str:
        raise ValidationError(f"batch {field} must be a string or null")
    return value


def _required_integer(raw: Mapping[str, Any], field: str) -> int:
    value = _required_field(raw, field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"batch {field} must be an integer")
    return value


def _required_boolean(raw: Mapping[str, Any], field: str) -> bool:
    value = _required_field(raw, field)
    if type(value) is not bool:
        raise ValidationError(f"batch {field} must be a boolean")
    return value


def _exact_integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValidationError(f"{label} must be an integer")
    return value


def _exact_boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ValidationError(f"{label} must be a boolean")
    return value


def _required_sha256_address(raw: Mapping[str, Any], field: str) -> str:
    value = _required_string(raw, field)
    try:
        _address_digest(value, label=field)
    except StoreError as exc:
        raise ValidationError(f"batch {field} must be a valid sha256 address") from exc
    return value


@contextmanager
def _batch_filesystem_lock(path: Path) -> Iterator[None]:
    """Wait through bounded store-lock windows for a long-running batch winner."""

    try:
        if path.is_symlink():
            raise StoreError(f"batch lock path is unsafe: {path.name}")
    except StoreError:
        raise
    except OSError as exc:
        raise StoreError(f"batch lock path could not be inspected: {path.name}") from exc
    for attempt in range(_BATCH_LOCK_ATTEMPTS):
        stack = ExitStack()
        try:
            stack.enter_context(_filesystem_lock(path))
        except StoreError as exc:
            stack.close()
            is_timeout = str(exc).startswith("timed out acquiring filesystem lock:")
            if not is_timeout or attempt + 1 == _BATCH_LOCK_ATTEMPTS:
                raise
            continue
        with stack:
            yield
        return
    raise StoreError(f"timed out acquiring batch filesystem lock: {path.name}")


def _batch_digest(batch_id: str) -> str:
    value = str(batch_id).strip()
    if len(value) != 70 or not value.startswith("batch-"):
        raise StoreError("invalid batch identifier")
    digest = value.split("-", 1)[1]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise StoreError("invalid batch identifier")
    return digest


def _case_id(raw: Any) -> str:
    return str(raw.get("case_id", "")).strip() if isinstance(raw, Mapping) else ""


@dataclass(frozen=True, slots=True)
class BatchItemResult:
    """One independently evaluated manifest within a batch."""

    index: int
    case_id: str
    state: str
    input_address: str | None
    run_id: str | None
    dossier_address: str | None
    error_code: str | None
    error_message: str | None
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == "accepted" and bool(self.run_id and self.dossier_address)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "case_id": self.case_id,
            "state": self.state,
            "input_address": self.input_address,
            "run_id": self.run_id,
            "dossier_address": self.dossier_address,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> BatchItemResult:
        _require_exact_fields(raw, _BATCH_ITEM_FIELDS, "batch item")
        index = _required_integer(raw, "index")
        case_id = _required_string(raw, "case_id", allow_empty=True)
        state = _required_string(raw, "state")
        input_address = _optional_string(raw, "input_address")
        run_id = _optional_string(raw, "run_id")
        dossier_address = _optional_string(raw, "dossier_address")
        error_code = _optional_string(raw, "error_code")
        error_message = _optional_string(raw, "error_message")
        serialized_accepted = _required_boolean(raw, "accepted")
        serialized_address = _required_string(raw, "content_address")
        if index < 0:
            raise ValidationError("batch item index must be non-negative")
        if state not in BATCH_ITEM_STATES:
            raise ValidationError("batch item state is invalid")
        if input_address is None:
            raise ValidationError("batch item input_address must not be null")
        try:
            _address_digest(input_address, label="batch item input_address")
        except StoreError as exc:
            raise ValidationError(
                "batch item input_address must be a valid sha256 address"
            ) from exc
        if state == "accepted":
            if not run_id or not _BATCH_RUN_ID_RE.fullmatch(run_id) or dossier_address is None:
                raise ValidationError("accepted batch item must retain run and dossier addresses")
            try:
                _address_digest(dossier_address, label="batch item dossier_address")
            except StoreError as exc:
                raise ValidationError(
                    "batch item dossier_address must be a valid sha256 address"
                ) from exc
            if error_code is not None or error_message is not None:
                raise ValidationError("accepted batch item must not retain error fields")
        elif run_id is not None or dossier_address is not None:
            raise ValidationError("failed batch item must not retain run or dossier addresses")
        elif not error_code or not error_message:
            raise ValidationError("failed batch item must retain error fields")
        body = {
            "index": index,
            "case_id": case_id,
            "state": state,
            "input_address": input_address,
            "run_id": run_id,
            "dossier_address": dossier_address,
            "error_code": error_code,
            "error_message": error_message,
        }
        expected_address = content_hash(body, prefix="batch-item")
        if serialized_address != expected_address:
            raise ValidationError("batch item content address does not match its fields")
        item = cls(
            index=index,
            case_id=case_id,
            state=state,
            input_address=input_address,
            run_id=run_id,
            dossier_address=dossier_address,
            error_code=error_code,
            error_message=error_message,
            content_address=serialized_address,
        )
        if serialized_accepted != item.accepted:
            raise ValidationError("batch item accepted state does not match its fields")
        return item


@dataclass(frozen=True, slots=True)
class BatchResult:
    """Reopenable aggregate of successful and failed item evaluations."""

    batch_id: str
    label: str | None
    input_address: str
    result_address: str
    created_at: str
    requested_count: int
    completed_count: int
    accepted_count: int
    failed_count: int
    items: tuple[BatchItemResult, ...]
    options: dict[str, Any]
    accepted: bool
    content_address: str

    @property
    def partial(self) -> bool:
        return self.accepted_count > 0 and self.failed_count > 0

    def _payload(self) -> dict[str, Any]:
        return {
            "batch_version": BATCH_RUNTIME_VERSION,
            "batch_id": self.batch_id,
            "label": self.label,
            "input_address": self.input_address,
            "created_at": self.created_at,
            "requested_count": self.requested_count,
            "completed_count": self.completed_count,
            "accepted_count": self.accepted_count,
            "failed_count": self.failed_count,
            "items": [item.to_dict() for item in self.items],
            "options": self.options,
            "accepted": self.accepted,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload()
        return payload | {
            "result_address": self.result_address,
            "partial": self.partial,
            "content_address": self.content_address,
        }

    @classmethod
    def from_payload(cls, raw: Mapping[str, Any], *, result_address: str) -> BatchResult:
        _require_exact_fields(raw, _BATCH_RESULT_FIELDS, "batch result")
        if _required_string(raw, "batch_version") != BATCH_RUNTIME_VERSION:
            raise ValidationError("batch result version is invalid")
        batch_id = _required_string(raw, "batch_id")
        try:
            batch_digest = _batch_digest(batch_id)
        except StoreError as exc:
            raise ValidationError("batch result identifier is invalid") from exc
        label = _optional_string(raw, "label")
        input_address = _required_sha256_address(raw, "input_address")
        try:
            result_digest = _address_digest(result_address, label="result_address")
        except StoreError as exc:
            raise ValidationError("batch result_address must be a valid sha256 address") from exc
        if batch_digest != _address_digest(input_address, label="input_address"):
            raise ValidationError("batch result identifier does not match its input address")
        if content_hash(raw) != f"sha256:{result_digest}":
            raise ValidationError("batch result content address does not match its payload")
        created_at = _required_string(raw, "created_at")
        requested_count = _required_integer(raw, "requested_count")
        completed_count = _required_integer(raw, "completed_count")
        accepted_count = _required_integer(raw, "accepted_count")
        failed_count = _required_integer(raw, "failed_count")
        accepted = _required_boolean(raw, "accepted")
        items_raw = _required_field(raw, "items")
        if not isinstance(items_raw, Sequence) or isinstance(items_raw, (str, bytes, bytearray)):
            raise ValidationError("batch items must be an array")
        hydrated_items: list[BatchItemResult] = []
        for item in items_raw:
            if not isinstance(item, Mapping):
                raise ValidationError("batch items must contain only objects")
            hydrated_items.append(BatchItemResult.from_dict(item))
        items = tuple(hydrated_items)
        options_raw = _required_field(raw, "options")
        if not isinstance(options_raw, Mapping):
            raise ValidationError("batch options must be an object")
        _require_exact_fields(options_raw, _BATCH_OPTION_FIELDS, "batch options")
        options = dict(options_raw)
        live_reference = _required_boolean(options, "live_reference")
        window_bp = _required_integer(options, "window_bp")
        max_items = _required_integer(options, "max_items")
        if requested_count < 1 or requested_count > BATCH_HARD_MAX_ITEMS:
            raise ValidationError("batch requested_count is outside the supported bounds")
        if completed_count != requested_count or len(items) != requested_count:
            raise ValidationError("batch item and completion counts do not match requested_count")
        if tuple(item.index for item in items) != tuple(range(requested_count)):
            raise ValidationError("batch item indexes must be contiguous and ordered")
        observed_accepted = sum(item.accepted for item in items)
        observed_failed = len(items) - observed_accepted
        if accepted_count != observed_accepted or failed_count != observed_failed:
            raise ValidationError("batch accepted and failed counts do not match its items")
        if accepted_count + failed_count != completed_count:
            raise ValidationError("batch result counts are not conserved")
        if accepted != (accepted_count == requested_count):
            raise ValidationError("batch accepted state does not match its item counts")
        if window_bp < 0:
            raise ValidationError("batch window_bp must be non-negative")
        if max_items < 1 or max_items > BATCH_HARD_MAX_ITEMS or requested_count > max_items:
            raise ValidationError("batch max_items is inconsistent with requested_count")
        result = cls(
            batch_id=batch_id,
            label=label,
            input_address=input_address,
            result_address=result_address,
            created_at=created_at,
            requested_count=requested_count,
            completed_count=completed_count,
            accepted_count=accepted_count,
            failed_count=failed_count,
            items=items,
            options={
                **options,
                "live_reference": live_reference,
                "window_bp": window_bp,
                "max_items": max_items,
            },
            accepted=accepted,
            content_address=result_address,
        )
        if content_hash(result._payload()) != result_address:
            raise ValidationError("hydrated batch result does not match its content address")
        return result


@dataclass(frozen=True, slots=True)
class BatchCatalogRow:
    """Bounded public summary for a persisted batch result."""

    batch_id: str
    label: str | None
    created_at: str
    requested_count: int
    accepted_count: int
    failed_count: int
    partial: bool
    result_address: str | None
    accepted: bool
    error: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "label": self.label,
            "created_at": self.created_at,
            "requested_count": self.requested_count,
            "accepted_count": self.accepted_count,
            "failed_count": self.failed_count,
            "partial": self.partial,
            "result_address": self.result_address,
            "accepted": self.accepted,
            "error": self.error,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class BatchCatalogPage:
    """Deterministic bounded catalog of persisted batch results."""

    rows: tuple[BatchCatalogRow, ...]
    total_count: int
    offset: int
    limit: int
    has_more: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_version": BATCH_RUNTIME_VERSION,
            "rows": [row.to_dict() for row in self.rows],
            "count": len(self.rows),
            "total_count": self.total_count,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.has_more,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class _BatchIndex:
    batch_id: str
    result_address: str
    input_address: str
    created_at: str
    accepted: bool


def _item(
    *,
    index: int,
    case_id: str,
    state: str,
    input_address: str | None = None,
    run_id: str | None = None,
    dossier_address: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> BatchItemResult:
    body = {
        "index": index,
        "case_id": case_id,
        "state": state,
        "input_address": input_address,
        "run_id": run_id,
        "dossier_address": dossier_address,
        "error_code": error_code,
        "error_message": error_message,
    }
    return BatchItemResult(
        index=index,
        case_id=case_id,
        state=state,
        input_address=input_address,
        run_id=run_id,
        dossier_address=dossier_address,
        error_code=error_code,
        error_message=error_message,
        content_address=content_hash(body, prefix="batch-item"),
    )


def _error_fields(exc: Exception) -> tuple[str, str]:
    code = str(getattr(exc, "code", "batch_item_error"))
    message = str(exc).strip() or "batch item evaluation failed"
    return code, message


class BatchRuntime:
    """Compose case evaluation into durable, independently inspectable batches."""

    def __init__(
        self,
        data_root: str | Path = ".glio",
        *,
        runtime: CaseRuntime | None = None,
    ) -> None:
        self.runtime = runtime or CaseRuntime(data_root)
        self.root = Path(self.runtime.store.root) / "batches"
        try:
            if self.root.is_symlink():
                raise StoreError("batch store root must be a regular directory")
            self.root.mkdir(parents=True, exist_ok=True)
            if not self.root.is_dir():
                raise StoreError("batch store root must be a regular directory")
            locks_root = Path(self.runtime.store.root) / ".locks"
            if locks_root.is_symlink() or not locks_root.is_dir():
                raise StoreError("batch lock root must be a regular directory")
            self._locks = locks_root / "batches"
            if self._locks.is_symlink():
                raise StoreError("batch lock directory must be a regular directory")
            self._locks.mkdir(parents=True, exist_ok=True)
            if not self._locks.is_dir():
                raise StoreError("batch lock directory must be a regular directory")
        except StoreError:
            raise
        except OSError as exc:
            raise StoreError("batch store directories could not be inspected") from exc

    def _index_path(self, batch_id: str) -> Path:
        return self.root / f"{_batch_digest(batch_id)}.json"

    def _lock_path(self, batch_id: str) -> Path:
        return self._locks / f"{_batch_digest(batch_id)}.lock"

    @staticmethod
    def _read_index_unlocked(path: Path, batch_id: str) -> _BatchIndex:
        try:
            unsafe = path.is_symlink()
            present = path.exists()
        except OSError as exc:
            raise StoreError("batch index path could not be inspected") from exc
        if unsafe:
            raise StoreError("batch index path is unsafe")
        if not present:
            raise StoreError("batch not found")
        try:
            with path.open("rb") as handle:
                payload = handle.read(_HARD_MAX_BATCH_INDEX_BYTES + 1)
        except OSError as exc:
            raise StoreError("batch index could not be read") from exc
        if len(payload) > _HARD_MAX_BATCH_INDEX_BYTES:
            raise StoreError("batch index exceeds its byte ceiling")
        try:
            raw = _strict_json_loads(
                payload.decode("utf-8"),
                object_pairs_hook=_unique_json_object,
                parse_constant=_invalid_json_constant,
            )
        except (UnicodeDecodeError, RecursionError, ValueError) as exc:
            raise StoreError("invalid batch index") from exc
        if type(raw) is not dict:
            raise StoreError("invalid batch index")
        try:
            if canonical_json(raw).encode("utf-8") != payload:
                raise ValidationError("batch index must use canonical UTF-8 JSON")
            _require_exact_fields(raw, _BATCH_INDEX_FIELDS, "batch index")
            stored_batch_id = _required_string(raw, "batch_id")
            result_address = _required_sha256_address(raw, "result_address")
            input_address = _required_sha256_address(raw, "input_address")
            created_at = _required_string(raw, "created_at")
            accepted = _required_boolean(raw, "accepted")
            input_digest = _address_digest(input_address, label="input_address")
            if stored_batch_id != batch_id:
                raise ValidationError("batch index identifier does not match its filename")
            if _batch_digest(stored_batch_id) != input_digest:
                raise ValidationError("batch index identifier does not match its input address")
        except (StoreError, ValidationError) as exc:
            raise StoreError("invalid batch index") from exc
        return _BatchIndex(
            batch_id=stored_batch_id,
            result_address=result_address,
            input_address=input_address,
            created_at=created_at,
            accepted=accepted,
        )

    def _get_unlocked(self, batch_id: str, path: Path) -> BatchResult:
        index = self._read_index_unlocked(path, batch_id)
        try:
            input_payload = self.runtime.store.store.get_verified(
                index.input_address,
                max_bytes=_HARD_MAX_BATCH_INPUT_BYTES,
            )
        except (OSError, StoreError, UnicodeError) as exc:
            raise StoreError("batch input object could not be read") from exc
        if type(input_payload) is not dict:
            raise StoreError("batch input address mismatch")
        try:
            _require_exact_fields(input_payload, _BATCH_INPUT_FIELDS, "batch input")
        except ValidationError as exc:
            raise StoreError("invalid batch input payload") from exc
        try:
            payload = self.runtime.store.store.get_verified(
                index.result_address,
                max_bytes=_HARD_MAX_BATCH_RESULT_BYTES,
            )
        except (OSError, StoreError, UnicodeError) as exc:
            raise StoreError("batch result object could not be read") from exc
        if type(payload) is not dict:
            raise StoreError("batch result address mismatch")
        try:
            result = BatchResult.from_payload(payload, result_address=index.result_address)
        except ValidationError as exc:
            raise StoreError("invalid batch result") from exc
        if result.batch_id != batch_id:
            raise StoreError("batch result identifier mismatch")
        if result.input_address != index.input_address:
            raise StoreError("batch input pointer mismatch")
        if result.created_at != index.created_at:
            raise StoreError("batch index created_at does not match its result")
        if result.accepted != index.accepted:
            raise StoreError("batch index accepted state does not match its result")
        manifests = input_payload.get("manifests")
        if not isinstance(manifests, Sequence) or isinstance(manifests, (str, bytes, bytearray)):
            raise StoreError("invalid batch input payload")
        if len(manifests) != result.requested_count:
            raise StoreError("batch input manifest count mismatch")
        if input_payload.get("batch_id") != result.label:
            raise StoreError("batch input label mismatch")
        for field in ("live_reference", "window_bp", "max_items"):
            if input_payload.get(field) != result.options[field]:
                raise StoreError(f"batch input {field} mismatch")
        for item, raw_manifest in zip(result.items, manifests, strict=True):
            item_input = {
                "batch_id": batch_id,
                "index": item.index,
                "manifest": raw_manifest,
            }
            expected_item_address = content_hash(item_input)
            if item.input_address != expected_item_address:
                raise StoreError("batch item input pointer mismatch")
            try:
                stored_item_input = self.runtime.store.store.get_verified(
                    expected_item_address,
                    max_bytes=_HARD_MAX_BATCH_ITEM_INPUT_BYTES,
                )
            except (OSError, StoreError, UnicodeError) as exc:
                raise StoreError("batch item input object could not be read") from exc
            if stored_item_input != item_input:
                raise StoreError("batch item input object mismatch")
            if not item.accepted:
                if item.case_id != _case_id(raw_manifest):
                    raise StoreError("failed batch item case_id mismatch")
                continue
            if not isinstance(raw_manifest, Mapping):
                raise StoreError("accepted batch item manifest must be an object")
            try:
                manifest = CaseManifest.from_dict(raw_manifest)
                snapshot = self.runtime.load_run_snapshot(item.run_id or "")
            except (GlioError, OSError, KeyError, TypeError, ValueError) as exc:
                raise StoreError("accepted batch item closure could not be reopened") from exc
            run_record = snapshot.run_record
            dossier = snapshot.dossier
            if (
                item.case_id != manifest.case_id
                or item.run_id != CaseRuntime._run_id(manifest)
                or run_record.get("run_id") != item.run_id
                or run_record.get("input_address") != manifest.content_address
                or dossier.content_address != item.dossier_address
                or dossier.run_id != item.run_id
                or dossier.case_id != item.case_id
                or dossier.input_address != manifest.content_address
            ):
                raise StoreError("accepted batch item run closure mismatch")
        return result

    @staticmethod
    def _document_parts(
        document: Mapping[str, Any] | Sequence[Any],
        *,
        live_reference: bool,
        window_bp: int,
        max_items: int,
    ) -> tuple[str | None, tuple[Any, ...], bool, int, int]:
        effective_live_reference = _exact_boolean(live_reference, "live_reference")
        effective_window_bp = _exact_integer(window_bp, "window_bp")
        effective_max_items = _exact_integer(max_items, "max_items")
        if isinstance(document, Mapping):
            if "batch_id" in document and "label" in document:
                raise ValidationError("batch input must use batch_id or label, not both")
            raw_label = document.get("batch_id", document.get("label"))
            if raw_label is not None and not isinstance(raw_label, str):
                raise ValidationError("batch_id must be a string or null")
            label = None if raw_label is None else raw_label.strip() or None
            if "manifests" in document:
                raw_rows = document.get("manifests", ())
            elif "case_id" in document and "variants" in document:
                raw_rows = (document,)
            else:
                raise ValidationError("batch input must contain manifests or one case manifest")
            if "live_reference" in document:
                effective_live_reference = _exact_boolean(
                    document["live_reference"], "live_reference"
                )
            if "window_bp" in document:
                effective_window_bp = _exact_integer(document["window_bp"], "window_bp")
            if "max_items" in document:
                effective_max_items = _exact_integer(document["max_items"], "max_items")
        elif isinstance(document, Sequence) and not isinstance(document, (str, bytes, bytearray)):
            label = None
            raw_rows = document
        else:
            raise ValidationError("batch input must be an object with manifests or a manifest list")
        if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes, bytearray)):
            raise ValidationError("batch manifests must be a list")
        if effective_window_bp < 0:
            raise ValidationError("window_bp must be non-negative")
        if effective_max_items < 1 or effective_max_items > BATCH_HARD_MAX_ITEMS:
            raise ValidationError(f"max_items must be between 1 and {BATCH_HARD_MAX_ITEMS}")
        rows = tuple(raw_rows)
        if not rows:
            raise ValidationError("batch manifests must not be empty")
        if len(rows) > effective_max_items:
            raise ValidationError(
                f"batch contains {len(rows)} items but max_items is {effective_max_items}"
            )
        return label, rows, effective_live_reference, effective_window_bp, effective_max_items

    def _evaluate_new(
        self,
        *,
        label: str | None,
        rows: tuple[Any, ...],
        effective_live: bool,
        effective_window: int,
        effective_max: int,
        input_address: str,
        batch_id: str,
        index_path: Path,
    ) -> BatchResult:
        if effective_live:
            self.runtime.reference_retriever = PublicReferenceRetriever(
                cache_root=Path(self.runtime.store.root) / "source-cache",
                window_bp=effective_window,
            )

        seen_case_ids: set[str] = set()
        results: list[BatchItemResult] = []
        for index, raw_manifest in enumerate(rows):
            case_id = _case_id(raw_manifest)
            item_input = {"batch_id": batch_id, "index": index, "manifest": raw_manifest}
            if len(canonical_bytes(item_input)) > _HARD_MAX_BATCH_ITEM_INPUT_BYTES:
                raise ValidationError("batch item input exceeds its byte ceiling")
            item_input_address = self.runtime.store.store.put(item_input)
            try:
                if not isinstance(raw_manifest, Mapping):
                    raise ValidationError("manifest item must be an object")
                manifest = CaseManifest.from_dict(raw_manifest)
                if manifest.case_id in seen_case_ids:
                    raise ValidationError(f"duplicate case_id in batch: {manifest.case_id}")
                seen_case_ids.add(manifest.case_id)
                dossier = self.runtime.evaluate(manifest, live_reference=effective_live)
                run_record = self.runtime.get_run(dossier.run_id)
                results.append(
                    _item(
                        index=index,
                        case_id=manifest.case_id,
                        state="accepted",
                        input_address=item_input_address,
                        run_id=dossier.run_id,
                        dossier_address=str(run_record["dossier_address"]),
                    )
                )
            except (GlioError, OSError, ValueError, TypeError, KeyError) as exc:
                error_code, error_message = _error_fields(exc)
                results.append(
                    _item(
                        index=index,
                        case_id=case_id,
                        state="failed",
                        input_address=item_input_address,
                        error_code=error_code,
                        error_message=error_message,
                    )
                )
            except Exception:  # pragma: no cover - isolated batch process boundary
                results.append(
                    _item(
                        index=index,
                        case_id=case_id,
                        state="failed",
                        input_address=item_input_address,
                        error_code="batch_item_error",
                        error_message="batch item evaluation failed",
                    )
                )

        accepted_count = sum(item.accepted for item in results)
        failed_count = len(results) - accepted_count
        payload = BatchResult(
            batch_id=batch_id,
            label=label,
            input_address=input_address,
            result_address="",
            created_at=utc_now().isoformat(),
            requested_count=len(rows),
            completed_count=len(results),
            accepted_count=accepted_count,
            failed_count=failed_count,
            items=tuple(results),
            options={
                "live_reference": effective_live,
                "window_bp": effective_window,
                "max_items": effective_max,
            },
            accepted=accepted_count == len(rows),
            content_address="",
        )
        result_payload = payload._payload()
        if len(canonical_bytes(result_payload)) > _HARD_MAX_BATCH_RESULT_BYTES:
            raise ValidationError("batch result exceeds its byte ceiling")
        result_address = self.runtime.store.store.put(result_payload)
        final = BatchResult(
            batch_id=payload.batch_id,
            label=payload.label,
            input_address=payload.input_address,
            result_address=result_address,
            created_at=payload.created_at,
            requested_count=payload.requested_count,
            completed_count=payload.completed_count,
            accepted_count=payload.accepted_count,
            failed_count=payload.failed_count,
            items=payload.items,
            options=payload.options,
            accepted=payload.accepted,
            content_address=result_address,
        )
        index_record = {
            "batch_id": final.batch_id,
            "result_address": result_address,
            "input_address": final.input_address,
            "created_at": final.created_at,
            "accepted": final.accepted,
        }
        _atomic_write_text(index_path, canonical_json(index_record))
        return final

    def evaluate(
        self,
        document: Mapping[str, Any] | Sequence[Any],
        *,
        live_reference: bool = False,
        window_bp: int = 2_000,
        max_items: int = BATCH_DEFAULT_MAX_ITEMS,
    ) -> BatchResult:
        """Evaluate every item independently and persist one batch closure."""

        label, rows, effective_live, effective_window, effective_max = self._document_parts(
            document,
            live_reference=live_reference,
            window_bp=window_bp,
            max_items=max_items,
        )
        if label:
            self.runtime.policy.enforce_texts((label,))
        raw_document = {
            "batch_id": label,
            "manifests": list(rows),
            "live_reference": effective_live,
            "window_bp": effective_window,
            "max_items": effective_max,
        }
        if len(canonical_bytes(raw_document)) > _HARD_MAX_BATCH_INPUT_BYTES:
            raise ValidationError("batch input exceeds its byte ceiling")
        input_address = self.runtime.store.store.put(raw_document)
        batch_id = f"batch-{input_address.split(':', 1)[1]}"
        index_path = self._index_path(batch_id)
        process_lock = _run_lock(index_path)
        with process_lock, _batch_filesystem_lock(self._lock_path(batch_id)):
            try:
                unsafe = index_path.is_symlink()
                present = index_path.exists()
            except OSError as exc:
                raise StoreError("batch index path could not be inspected") from exc
            if unsafe:
                raise StoreError("batch index path is unsafe")
            if present:
                return self._get_unlocked(batch_id, index_path)
            return self._evaluate_new(
                label=label,
                rows=rows,
                effective_live=effective_live,
                effective_window=effective_window,
                effective_max=effective_max,
                input_address=input_address,
                batch_id=batch_id,
                index_path=index_path,
            )

    def get(self, batch_id: str) -> BatchResult:
        """Reopen and verify one persisted batch result."""

        path = self._index_path(batch_id)
        process_lock = _run_lock(path)
        with process_lock, _batch_filesystem_lock(self._lock_path(batch_id)):
            return self._get_unlocked(batch_id, path)

    def catalog(
        self,
        *,
        offset: int = 0,
        limit: int = BATCH_CATALOG_DEFAULT_LIMIT,
        text: str | None = None,
    ) -> BatchCatalogPage:
        """Return a bounded catalog while retaining corrupt entries as failures."""

        if offset < 0:
            raise ValidationError("offset must be non-negative")
        if limit < 1 or limit > BATCH_CATALOG_MAX_LIMIT:
            raise ValidationError(f"limit must be between 1 and {BATCH_CATALOG_MAX_LIMIT}")
        normalized_text = text.strip().lower() if text else None
        rows: list[BatchCatalogRow] = []
        for path in sorted(self.root.glob("*.json"), key=lambda item: item.name):
            batch_id = f"batch-{path.stem}"
            try:
                result = self.get(batch_id)
                row_body = {
                    "batch_id": result.batch_id,
                    "label": result.label,
                    "created_at": result.created_at,
                    "requested_count": result.requested_count,
                    "accepted_count": result.accepted_count,
                    "failed_count": result.failed_count,
                    "partial": result.partial,
                    "result_address": result.result_address,
                    "accepted": result.accepted,
                    "error": None,
                }
                row = BatchCatalogRow(
                    batch_id=result.batch_id,
                    label=result.label,
                    created_at=result.created_at,
                    requested_count=result.requested_count,
                    accepted_count=result.accepted_count,
                    failed_count=result.failed_count,
                    partial=result.partial,
                    result_address=result.result_address,
                    accepted=result.accepted,
                    error=None,
                    content_address=content_hash(row_body, prefix="batch-catalog-row"),
                )
            except (GlioError, OSError, ValueError, TypeError, KeyError):
                row_body = {
                    "batch_id": batch_id,
                    "label": None,
                    "created_at": "",
                    "requested_count": 0,
                    "accepted_count": 0,
                    "failed_count": 0,
                    "partial": False,
                    "result_address": None,
                    "accepted": False,
                    "error": "batch could not be reopened or verified",
                }
                row = BatchCatalogRow(
                    batch_id=batch_id,
                    label=None,
                    created_at="",
                    requested_count=0,
                    accepted_count=0,
                    failed_count=0,
                    partial=False,
                    result_address=None,
                    accepted=False,
                    error="batch could not be reopened or verified",
                    content_address=content_hash(row_body, prefix="batch-catalog-row"),
                )
            haystack = " ".join((row.batch_id, row.label or "", row.error or "")).lower()
            if normalized_text and normalized_text not in haystack:
                continue
            rows.append(row)
        rows.sort(key=lambda row: (row.created_at, row.batch_id))
        selected = tuple(rows[offset : offset + limit])
        has_more = offset + len(selected) < len(rows)
        body = {
            "rows": selected,
            "total_count": len(rows),
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "text": text,
        }
        public_body = body | {"rows": [row.to_dict() for row in selected]}
        accepted = all(row.accepted for row in rows) and not contains_private_key(public_body)
        return BatchCatalogPage(
            rows=selected,
            total_count=len(rows),
            offset=offset,
            limit=limit,
            has_more=has_more,
            accepted=accepted,
            content_address=content_hash(
                body | {"accepted": accepted}, prefix="batch-catalog-page"
            ),
        )


__all__ = [
    "BATCH_CATALOG_DEFAULT_LIMIT",
    "BATCH_CATALOG_MAX_LIMIT",
    "BATCH_DEFAULT_MAX_ITEMS",
    "BATCH_HARD_MAX_ITEMS",
    "BATCH_ITEM_STATES",
    "BATCH_RUNTIME_VERSION",
    "BatchCatalogPage",
    "BatchCatalogRow",
    "BatchItemResult",
    "BatchResult",
    "BatchRuntime",
]
