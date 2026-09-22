"""Immutable persistence for aggregate phased-sequence batch reports."""

from __future__ import annotations

import csv
import io
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ._safe_persistence import atomic_write_text, read_bytes
from .errors import StoreError, ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash
from .storage import ObjectStore, _filesystem_lock, _run_lock, _validate_storage_parent

BATCH_RECORD_SCHEMA = "glio-noncode.sequence-batch-record.v1"
BATCH_CATALOG_SCHEMA = "glio-noncode.sequence-batch-catalog.v1"
MAX_BATCH_REPORT_BYTES = 16 * 1024 * 1024
MAX_BATCH_RECORD_BYTES = 256 * 1024
MAX_BATCH_RECORDS = 10_000
MAX_BATCH_PAGE_SIZE = 50
MAX_BATCH_CHANGE_QUERY_LENGTH = 256
MAX_BATCH_CHANGE_EXPORT_BYTES = 4 * 1024 * 1024

_BATCH_ID_RE = re.compile(r"batch-[0-9a-f]{64}\Z")
_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REPORT_ADDRESS_RE = re.compile(r"sequence-haplotype-batch-analysis:[0-9a-f]{64}\Z")
_REPORT_FIELDS = frozenset(
    {
        "schema",
        "status",
        "source",
        "design",
        "records",
        "motif_changes",
        "limitations",
        "content_address",
    }
)
_SOURCE_FIELDS = frozenset(
    {
        "source_id",
        "source_version",
        "source_url",
        "retrieved_at",
        "response_hash",
        "sequence_interval",
        "sequence_hash",
    }
)
_DESIGN_FIELDS = frozenset(
    {
        "genome_build",
        "analysis_count",
        "supported_count",
        "abstained_count",
        "motif_count",
        "shared_context_hash",
    }
)
_RECORD_FIELDS = frozenset(
    {
        "analysis_address",
        "analysis_state",
        "variant_count",
        "motif_count",
        "created_motif_count",
        "disrupted_motif_count",
    }
)
_CHANGE_FIELDS = frozenset(
    {
        "change",
        "motif_id",
        "name",
        "matched_sequence",
        "strand",
        "source_id",
        "analysis_count",
        "analysis_fraction",
    }
)
_SUMMARY_FIELDS = frozenset(
    {
        "analysis_count",
        "supported_count",
        "abstained_count",
        "genome_build",
        "source_id",
        "created_change_count",
        "disrupted_change_count",
        "content_address",
    }
)
_PRIVATE_KEYS = frozenset(
    {
        "sample_id",
        "sample_ids",
        "subject_id",
        "subject_ids",
        "patient_id",
        "patient_ids",
        "genotype",
        "genotypes",
    }
)


def _object(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != fields:
        raise ValidationError(f"sequence batch {label} has an invalid v1 shape")
    return value


def _text(value: object, label: str, *, maximum: int = 8_192) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValidationError(f"sequence batch {label} is outside its text bound")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValidationError(f"sequence batch {label} contains a control character")
    return value


def _count(value: object, label: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ValidationError(f"sequence batch {label} is outside its supported range")
    return value


def _address(value: object, label: str) -> str:
    if type(value) is not str or _ADDRESS_RE.fullmatch(value) is None:
        raise ValidationError(f"sequence batch {label} is not a sha256 address")
    return value


def _public_only(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is str and key.casefold() in _PRIVATE_KEYS:
                raise ValidationError("sequence batch contains a private individual key")
            _public_only(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _public_only(item)


def _interval(value: object) -> tuple[str, int, int]:
    if type(value) not in {list, tuple} or len(value) != 3:
        raise ValidationError("sequence batch interval must contain chromosome, start, and end")
    chromosome = _text(value[0], "interval chromosome", maximum=256)
    start = _count(value[1], "interval start", minimum=1)
    end = _count(value[2], "interval end", minimum=start)
    return chromosome, start, end


def validate_sequence_batch_report(report: object) -> dict[str, Any]:
    """Validate one complete aggregate report and its content address."""

    if type(report) is not dict or frozenset(report) != _REPORT_FIELDS:
        raise ValidationError("sequence batch must be a complete v1 report")
    _public_only(report)
    if report["schema"] != "glio-noncode.sequence-haplotype-batch-analysis.v1":
        raise ValidationError("sequence batch report schema is unsupported")
    if report["status"] != "completed":
        raise ValidationError("sequence batch report must be completed")
    source = _object(report["source"], _SOURCE_FIELDS, "source")
    for key in ("source_id", "source_version", "retrieved_at"):
        _text(source[key], f"source {key}")
    parsed_url = urlsplit(_text(source["source_url"], "source URL"))
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValidationError("sequence batch source URL must be absolute HTTP text")
    _address(source["response_hash"], "response hash")
    _address(source["sequence_hash"], "sequence hash")
    _interval(source["sequence_interval"])
    design = _object(report["design"], _DESIGN_FIELDS, "design")
    _text(design["genome_build"], "genome build", maximum=256)
    analysis_count = _count(design["analysis_count"], "analysis count", minimum=1, maximum=128)
    supported_count = _count(design["supported_count"], "supported count")
    abstained_count = _count(design["abstained_count"], "abstained count")
    if supported_count + abstained_count != analysis_count:
        raise ValidationError("sequence batch state counts do not reconcile")
    _count(design["motif_count"], "motif count", maximum=2_048)
    _address(design["shared_context_hash"], "shared context hash")
    records = report["records"]
    if type(records) is not list or len(records) != analysis_count:
        raise ValidationError("sequence batch record count does not reconcile")
    observed_supported = 0
    for index, item in enumerate(records):
        record = _object(item, _RECORD_FIELDS, f"record {index + 1}")
        _address(record["analysis_address"], f"record {index + 1} address")
        if record["analysis_state"] not in {
            "supported",
            "abstained",
            "reference_mismatch",
            "out_of_window",
        }:
            raise ValidationError(f"sequence batch record {index + 1} state is unsupported")
        observed_supported += record["analysis_state"] == "supported"
        for key, maximum in (
            ("variant_count", 1_024),
            ("motif_count", 2_048),
            ("created_motif_count", 50_000),
            ("disrupted_motif_count", 50_000),
        ):
            _count(record[key], f"record {index + 1} {key}", maximum=maximum)
    if observed_supported != supported_count:
        raise ValidationError("sequence batch supported count does not reconcile with records")
    changes = report["motif_changes"]
    if type(changes) is not list or len(changes) > 100_000:
        raise ValidationError("sequence batch motif changes exceed the supported limit")
    for index, item in enumerate(changes):
        change = _object(item, _CHANGE_FIELDS, f"motif change {index + 1}")
        if change["change"] not in {"created", "disrupted"}:
            raise ValidationError("sequence batch motif change direction is unsupported")
        for key in ("motif_id", "name", "matched_sequence", "source_id"):
            _text(change[key], f"motif change {key}", maximum=4_096)
        if change["strand"] not in {"+", "-"}:
            raise ValidationError("sequence batch motif change strand is unsupported")
        _count(
            change["analysis_count"],
            "motif change analysis count",
            minimum=1,
            maximum=analysis_count,
        )
        fraction = change["analysis_fraction"]
        if (
            type(fraction) not in {int, float}
            or not math.isfinite(fraction)
            or not 0.0 < fraction <= 1.0
        ):
            raise ValidationError("sequence batch motif change fraction is invalid")
    limitations = report["limitations"]
    if type(limitations) is not list or any(
        type(item) is not str or not item for item in limitations
    ):
        raise ValidationError("sequence batch limitations are invalid")
    address = report["content_address"]
    if type(address) is not str or _REPORT_ADDRESS_RE.fullmatch(address) is None:
        raise ValidationError("sequence batch content address is invalid")
    expected = content_hash(
        {key: value for key, value in report.items() if key != "content_address"},
        prefix="sequence-haplotype-batch-analysis",
    )
    if address != expected:
        raise ValidationError("sequence batch content address does not verify")
    return report


def summarize_sequence_batch_report(report: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_sequence_batch_report(dict(report))
    design = validated["design"]
    changes = validated["motif_changes"]
    return {
        "analysis_count": design["analysis_count"],
        "supported_count": design["supported_count"],
        "abstained_count": design["abstained_count"],
        "genome_build": design["genome_build"],
        "source_id": validated["source"]["source_id"],
        "created_change_count": sum(item["change"] == "created" for item in changes),
        "disrupted_change_count": sum(item["change"] == "disrupted" for item in changes),
        "content_address": validated["content_address"],
    }


class SequenceBatchStore:
    """Immutable catalog for aggregate batch projections."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = ObjectStore(self.root)
        self.records = self.root / "sequence-batches"
        self.locks = self.root / ".locks" / "sequence-batches"
        try:
            _validate_storage_parent(self.records, "sequence batch store")
            if self.records.is_symlink():
                raise StoreError("sequence batch store must be a regular directory")
            self.records.mkdir(parents=True, exist_ok=True)
            _validate_storage_parent(self.locks, "sequence batch lock directory")
            if self.locks.is_symlink():
                raise StoreError("sequence batch lock directory must be regular")
            self.locks.mkdir(parents=True, exist_ok=True)
        except StoreError:
            raise
        except OSError as exc:
            raise StoreError("sequence batch store could not be initialized") from exc
        self._lock = _run_lock(self.records)

    @staticmethod
    def _batch_id(body: Mapping[str, Any]) -> str:
        return f"batch-{content_hash(body).split(':', 1)[1]}"

    def _record_path(self, batch_id: str) -> Path:
        if type(batch_id) is not str or _BATCH_ID_RE.fullmatch(batch_id) is None:
            raise ValidationError("sequence batch identifier is invalid")
        return self.records / f"{batch_id}.json"

    def _decode_record(self, path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise StoreError("sequence batch catalog contains an unsafe record")
        try:
            raw = _strict_json_loads(
                read_bytes(
                    path, field="sequence batch catalog record", max_bytes=MAX_BATCH_RECORD_BYTES
                )
            )
        except (OSError, UnicodeError, ValueError, ValidationError) as exc:
            raise StoreError("sequence batch catalog record could not be verified") from exc
        if type(raw) is not dict or frozenset(raw) != {
            "schema",
            "batch_id",
            "report_address",
            "summary",
        }:
            raise StoreError("sequence batch catalog record has an invalid shape")
        if raw["schema"] != BATCH_RECORD_SCHEMA:
            raise StoreError("sequence batch catalog record schema is unsupported")
        batch_id = raw["batch_id"]
        if (
            type(batch_id) is not str
            or path.stem != batch_id
            or _BATCH_ID_RE.fullmatch(batch_id) is None
        ):
            raise StoreError("sequence batch identifier does not match its filename")
        _address(raw["report_address"], "catalog report address")
        if type(raw["summary"]) is not dict or frozenset(raw["summary"]) != _SUMMARY_FIELDS:
            raise StoreError("sequence batch catalog summary has an invalid shape")
        body = {key: value for key, value in raw.items() if key != "batch_id"}
        if self._batch_id(body) != batch_id:
            raise StoreError("sequence batch catalog address does not verify")
        return raw

    def save(self, report: object) -> dict[str, Any]:
        validated = validate_sequence_batch_report(report)
        if len(canonical_json(validated).encode("utf-8")) > MAX_BATCH_REPORT_BYTES:
            raise StoreError("sequence batch report exceeds its byte limit")
        report_address = self.objects.put(validated)
        body = {
            "schema": BATCH_RECORD_SCHEMA,
            "report_address": report_address,
            "summary": summarize_sequence_batch_report(validated),
        }
        batch_id = self._batch_id(body)
        record = body | {"batch_id": batch_id}
        path = self._record_path(batch_id)
        try:
            with self._lock, _filesystem_lock(self.locks / f"{batch_id}.lock"):
                if path.exists():
                    current = self._decode_record(path)
                    if canonical_json(current) != canonical_json(record):
                        raise StoreError(
                            "sequence batch record differs at its immutable identifier"
                        )
                else:
                    atomic_write_text(
                        path, canonical_json(record), field="sequence batch catalog record"
                    )
        except (OSError, ValidationError) as exc:
            raise StoreError("sequence batch record could not be saved") from exc
        return record

    def list_reports(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= 10_000:
            raise ValidationError("sequence batch offset is outside its supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_BATCH_PAGE_SIZE:
            raise ValidationError("sequence batch limit is outside its supported range")
        paths = sorted(self.records.glob("batch-*.json"), key=lambda item: item.name)
        if len(paths) > MAX_BATCH_RECORDS:
            raise StoreError("sequence batch catalog exceeds its record limit")
        records = [self._decode_record(path) for path in paths]
        rows = [
            {"batch_id": item["batch_id"], **item["summary"]}
            for item in records[offset : offset + limit]
        ]
        return {
            "schema": BATCH_CATALOG_SCHEMA,
            "offset": offset,
            "limit": limit,
            "total_count": len(records),
            "has_more": offset + len(rows) < len(records),
            "rows": rows,
        }

    def get_report(self, batch_id: str) -> dict[str, Any]:
        path = self._record_path(batch_id)
        if not path.exists():
            raise KeyError(batch_id)
        record = self._decode_record(path)
        report = validate_sequence_batch_report(
            self.objects.get_canonical(record["report_address"], max_bytes=MAX_BATCH_REPORT_BYTES)
        )
        if summarize_sequence_batch_report(report) != record["summary"]:
            raise StoreError("sequence batch summary does not match its report")
        return {
            "schema": BATCH_RECORD_SCHEMA,
            "batch_id": batch_id,
            "report_address": record["report_address"],
            "summary": record["summary"],
            "report": report,
        }

    def page_changes(
        self,
        batch_id: str,
        *,
        offset: int = 0,
        limit: int = 25,
        change: str | None = None,
        motif_contains: str | None = None,
    ) -> dict[str, Any]:
        """Page aggregate motif prevalence rows from one verified batch."""

        if type(offset) is not int or not 0 <= offset <= 10_000:
            raise ValidationError("sequence batch change offset is outside its supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_BATCH_PAGE_SIZE:
            raise ValidationError("sequence batch change limit is outside its supported range")
        if change is not None and change not in {"created", "disrupted"}:
            raise ValidationError("sequence batch change must be created or disrupted")
        if motif_contains is not None:
            if (
                type(motif_contains) is not str
                or not motif_contains.strip()
                or len(motif_contains) > MAX_BATCH_CHANGE_QUERY_LENGTH
                or any(ord(character) < 32 or ord(character) == 127 for character in motif_contains)
            ):
                raise ValidationError("sequence batch motif query is outside its supported range")
            motif_contains = motif_contains.casefold()
        saved = self.get_report(batch_id)
        changes = saved["report"]["motif_changes"]
        filtered = [
            item
            for item in changes
            if (change is None or item["change"] == change)
            and (
                motif_contains is None
                or motif_contains in item["motif_id"].casefold()
                or motif_contains in item["name"].casefold()
            )
        ]
        filtered_change_summary = {
            "change_count": len(filtered),
            "created_count": sum(item["change"] == "created" for item in filtered),
            "disrupted_count": sum(item["change"] == "disrupted" for item in filtered),
            "analysis_count_total": sum(int(item["analysis_count"]) for item in filtered),
            "mean_analysis_fraction": (
                sum(float(item["analysis_fraction"]) for item in filtered) / len(filtered)
                if filtered
                else 0.0
            ),
            "max_analysis_fraction": max(
                (float(item["analysis_fraction"]) for item in filtered), default=0.0
            ),
        }
        return {
            "schema": "glio-noncode.sequence-haplotype-batch-changes.v1",
            "batch_id": batch_id,
            "offset": offset,
            "limit": limit,
            "total_changes": len(filtered),
            "unfiltered_change_count": len(changes),
            "has_more": offset + limit < len(filtered),
            "filters": {"change": change, "motif_contains": motif_contains},
            "filtered_change_summary": filtered_change_summary,
            "changes": filtered[offset : offset + limit],
        }

    def changes_csv(
        self,
        batch_id: str,
        *,
        change: str | None = None,
        motif_contains: str | None = None,
    ) -> str:
        """Render bounded aggregate motif prevalence as stable CSV."""

        page = self.page_changes(
            batch_id,
            offset=0,
            limit=MAX_BATCH_PAGE_SIZE,
            change=change,
            motif_contains=motif_contains,
        )
        if page["total_changes"] > MAX_BATCH_PAGE_SIZE:
            raise StoreError("sequence batch motif CSV requires a narrower filter")
        fields = (
            "change",
            "motif_id",
            "name",
            "matched_sequence",
            "strand",
            "source_id",
            "analysis_count",
            "analysis_fraction",
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(fields)
        for item in page["changes"]:
            writer.writerow(tuple(item[field] for field in fields))
        rendered = output.getvalue()
        if len(rendered.encode("utf-8")) > MAX_BATCH_CHANGE_EXPORT_BYTES:
            raise StoreError("sequence batch motif CSV exceeds the export byte limit")
        return rendered


__all__ = [
    "BATCH_CATALOG_SCHEMA",
    "BATCH_RECORD_SCHEMA",
    "MAX_BATCH_CHANGE_QUERY_LENGTH",
    "MAX_BATCH_CHANGE_EXPORT_BYTES",
    "SequenceBatchStore",
    "summarize_sequence_batch_report",
    "validate_sequence_batch_report",
]
