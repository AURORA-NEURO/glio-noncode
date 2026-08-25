"""Content-addressed batch evaluation and reopening contracts.

The case runtime remains the source of truth for one manifest.  This module
adds a durable orchestration envelope around it: each manifest is evaluated
independently, a failed item is retained beside successful items, and the batch
result can be reopened by its content-derived identifier.  Batch execution does
not weaken the research-only policy or convert a partial batch into an accepted
result.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data_sources import PublicReferenceRetriever
from .errors import GlioError, StoreError, ValidationError
from .models import CaseManifest
from .module_fabric_support import contains_private_key
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash, utc_now

BATCH_RUNTIME_VERSION = "batch-runtime-v1"
BATCH_DEFAULT_MAX_ITEMS = 100
BATCH_HARD_MAX_ITEMS = 1000
BATCH_CATALOG_DEFAULT_LIMIT = 25
BATCH_CATALOG_MAX_LIMIT = 100
BATCH_ITEM_STATES = ("accepted", "failed")


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
        return cls(
            index=int(raw.get("index", 0)),
            case_id=str(raw.get("case_id", "")),
            state=str(raw.get("state", "failed")),
            input_address=str(raw["input_address"]) if raw.get("input_address") else None,
            run_id=str(raw["run_id"]) if raw.get("run_id") else None,
            dossier_address=str(raw["dossier_address"]) if raw.get("dossier_address") else None,
            error_code=str(raw["error_code"]) if raw.get("error_code") else None,
            error_message=str(raw["error_message"]) if raw.get("error_message") else None,
            content_address=str(raw.get("content_address", "")),
        )


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
        items = tuple(
            BatchItemResult.from_dict(item)
            for item in raw.get("items", ())
            if isinstance(item, Mapping)
        )
        return cls(
            batch_id=str(raw.get("batch_id", "")),
            label=str(raw["label"]) if raw.get("label") else None,
            input_address=str(raw.get("input_address", "")),
            result_address=result_address,
            created_at=str(raw.get("created_at", "")),
            requested_count=int(raw.get("requested_count", len(items))),
            completed_count=int(raw.get("completed_count", 0)),
            accepted_count=int(raw.get("accepted_count", 0)),
            failed_count=int(raw.get("failed_count", 0)),
            items=items,
            options=dict(raw.get("options", {})),
            accepted=bool(raw.get("accepted", False)),
            content_address=result_address,
        )


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
    return BatchItemResult(**body, content_address=content_hash(body, prefix="batch-item"))


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
        self.root.mkdir(parents=True, exist_ok=True)

    def _index_path(self, batch_id: str) -> Path:
        return self.root / f"{_batch_digest(batch_id)}.json"

    @staticmethod
    def _document_parts(
        document: Mapping[str, Any] | Sequence[Any],
        *,
        live_reference: bool,
        window_bp: int,
        max_items: int,
    ) -> tuple[str | None, tuple[Any, ...], bool, int, int]:
        if isinstance(document, Mapping):
            label = str(document.get("batch_id", document.get("label", ""))).strip() or None
            if "manifests" in document:
                raw_rows = document.get("manifests", ())
            elif "case_id" in document and "variants" in document:
                raw_rows = (document,)
            else:
                raise ValidationError("batch input must contain manifests or one case manifest")
            effective_live_reference = bool(document.get("live_reference", live_reference))
            effective_window_bp = int(document.get("window_bp", window_bp))
            effective_max_items = int(document.get("max_items", max_items))
        elif isinstance(document, Sequence) and not isinstance(document, (str, bytes, bytearray)):
            label = None
            raw_rows = document
            effective_live_reference = live_reference
            effective_window_bp = window_bp
            effective_max_items = max_items
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
            raise ValidationError(f"batch contains {len(rows)} items but max_items is {effective_max_items}")
        return label, rows, effective_live_reference, effective_window_bp, effective_max_items

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
        input_address = self.runtime.store.store.put(raw_document)
        batch_id = f"batch-{input_address.split(':', 1)[1]}"
        index_path = self._index_path(batch_id)
        if index_path.exists():
            return self.get(batch_id)
        if effective_live:
            self.runtime.reference_retriever = PublicReferenceRetriever(
                cache_root=Path(self.runtime.store.root) / "source-cache",
                window_bp=effective_window,
            )

        seen_case_ids: set[str] = set()
        results: list[BatchItemResult] = []
        for index, raw_manifest in enumerate(rows):
            case_id = _case_id(raw_manifest)
            item_input_address = self.runtime.store.store.put(
                {"batch_id": batch_id, "index": index, "manifest": raw_manifest}
            )
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
                        input_address=str(run_record["input_address"]),
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
        result_address = self.runtime.store.store.put(payload._payload())
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
        temporary = index_path.with_suffix(".tmp")
        temporary.write_text(canonical_json(index_record), encoding="utf-8")
        temporary.replace(index_path)
        return final

    def get(self, batch_id: str) -> BatchResult:
        """Reopen and verify one persisted batch result."""

        path = self._index_path(batch_id)
        if not path.exists():
            raise StoreError("batch not found")
        try:
            index = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreError("invalid batch index") from exc
        if not isinstance(index, Mapping) or str(index.get("batch_id", "")) != batch_id:
            raise StoreError("batch index identifier mismatch")
        input_address = str(index.get("input_address", ""))
        input_payload = self.runtime.store.store.get(input_address)
        if content_hash(input_payload) != input_address:
            raise StoreError("batch input address mismatch")
        result_address = str(index.get("result_address", ""))
        payload = self.runtime.store.store.get(result_address)
        if not isinstance(payload, Mapping) or content_hash(payload) != result_address:
            raise StoreError("batch result address mismatch")
        result = BatchResult.from_payload(payload, result_address=result_address)
        if result.batch_id != batch_id:
            raise StoreError("batch result identifier mismatch")
        if result.input_address != input_address:
            raise StoreError("batch input pointer mismatch")
        return result

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
                    **row_body,
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
                    **row_body,
                    content_address=content_hash(row_body, prefix="batch-catalog-row"),
                )
            haystack = " ".join((row.batch_id, row.label or "", row.error or "")).lower()
            if normalized_text and normalized_text not in haystack:
                continue
            rows.append(row)
        rows.sort(key=lambda row: (row.created_at, row.batch_id))
        selected = tuple(rows[offset : offset + limit])
        body = {
            "rows": selected,
            "total_count": len(rows),
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(selected) < len(rows),
            "text": text,
        }
        public_body = body | {"rows": [row.to_dict() for row in selected]}
        accepted = all(row.accepted for row in rows) and not contains_private_key(public_body)
        return BatchCatalogPage(
            rows=selected,
            total_count=len(rows),
            offset=offset,
            limit=limit,
            has_more=body["has_more"],
            accepted=accepted,
            content_address=content_hash(body | {"accepted": accepted}, prefix="batch-catalog-page"),
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
