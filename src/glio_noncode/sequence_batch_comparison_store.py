"""Immutable persistence for exact, aggregate sequence-batch comparisons."""

from __future__ import annotations

import csv
import io
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ._safe_persistence import atomic_write_text, read_bytes
from .errors import StoreError, ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash
from .storage import ObjectStore, _filesystem_lock, _run_lock, _validate_storage_parent

COMPARISON_RECORD_SCHEMA = "glio-noncode.sequence-batch-comparison-record.v1"
COMPARISON_CATALOG_SCHEMA = "glio-noncode.sequence-batch-comparison-catalog.v1"
COMPARISON_CHANGES_SCHEMA = "glio-noncode.sequence-batch-comparison-changes.v1"
MAX_COMPARISON_REPORT_BYTES = 16 * 1024 * 1024
MAX_COMPARISON_RECORD_BYTES = 256 * 1024
MAX_COMPARISON_RECORDS = 10_000
MAX_COMPARISON_PAGE_SIZE = 50
MAX_COMPARISON_QUERY_LENGTH = 256
MAX_COMPARISON_CSV_BYTES = 4 * 1024 * 1024

_COMPARISON_ID_RE = re.compile(r"comparison-[0-9a-f]{64}\Z")
_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REPORT_ADDRESS_RE = re.compile(r"sequence-batch-comparison:[0-9a-f]{64}\Z")
_BATCH_REPORT_ADDRESS_RE = re.compile(r"sequence-haplotype-batch-analysis:[0-9a-f]{64}\Z")
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
_SUMMARY_FIELDS = frozenset(
    {"content_address", "analysis_count", "supported_count", "abstained_count"}
)
_CHANGE_FIELDS = frozenset(
    {
        "change",
        "motif_id",
        "name",
        "matched_sequence",
        "strand",
        "source_id",
        "left_analysis_count",
        "right_analysis_count",
        "left_analysis_fraction",
        "right_analysis_fraction",
        "delta_fraction",
        "direction",
    }
)
_REPORT_FIELDS = frozenset(
    {"schema", "status", "source", "left", "right", "changes", "limitations", "content_address"}
)
_RECORD_SUMMARY_FIELDS = frozenset(
    {"left_analysis_count", "right_analysis_count", "change_count", "content_address"}
)


def _text(value: object, label: str, *, maximum: int = 8_192) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValidationError(f"sequence comparison {label} is outside its text bound")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValidationError(f"sequence comparison {label} contains a control character")
    return value


def _count(value: object, label: str, *, minimum: int = 0, maximum: int = 10_000) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        raise ValidationError(f"sequence comparison {label} is outside its supported range")
    return value


def _address(value: object, label: str) -> str:
    if type(value) is not str or _ADDRESS_RE.fullmatch(value) is None:
        raise ValidationError(f"sequence comparison {label} is not a sha256 address")
    return value


def _interval(value: object) -> tuple[str, int, int]:
    if type(value) not in {list, tuple} or len(value) != 3:
        raise ValidationError("sequence comparison interval is invalid")
    chromosome = _text(value[0], "interval chromosome", maximum=256)
    start = _count(value[1], "interval start", minimum=1, maximum=2**63 - 1)
    end = _count(value[2], "interval end", minimum=start, maximum=2**63 - 1)
    return chromosome, start, end


def _source(value: object) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != _SOURCE_FIELDS:
        raise ValidationError("sequence comparison source has an invalid shape")
    for key in ("source_id", "source_version", "retrieved_at"):
        _text(value[key], f"source {key}")
    source_url = _text(value["source_url"], "source URL")
    parsed_url = urlsplit(source_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValidationError("sequence comparison source URL must be absolute HTTP text")
    _address(value["response_hash"], "source response hash")
    _address(value["sequence_hash"], "source sequence hash")
    _interval(value["sequence_interval"])
    return value


def _summary(value: object, label: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != _SUMMARY_FIELDS:
        raise ValidationError(f"sequence comparison {label} summary has an invalid shape")
    if (
        type(value["content_address"]) is not str
        or _BATCH_REPORT_ADDRESS_RE.fullmatch(value["content_address"]) is None
    ):
        raise ValidationError(f"sequence comparison {label} address is invalid")
    analysis_count = _count(
        value["analysis_count"], f"{label} analysis count", minimum=1, maximum=128
    )
    supported_count = _count(
        value["supported_count"], f"{label} supported count", maximum=analysis_count
    )
    abstained_count = _count(
        value["abstained_count"], f"{label} abstained count", maximum=analysis_count
    )
    if supported_count + abstained_count != analysis_count:
        raise ValidationError(f"sequence comparison {label} state counts do not reconcile")
    return value


def _nullable_count(value: object, label: str, maximum: int = 128) -> int | None:
    if value is None:
        return None
    return _count(value, label, minimum=1, maximum=maximum)


def _nullable_fraction(value: object, label: str) -> float | None:
    if value is None:
        return None
    if (
        type(value) not in {int, float}
        or not math.isfinite(value)
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValidationError(f"sequence comparison {label} is invalid")
    return float(value)


def validate_sequence_batch_comparison(report: object) -> dict[str, Any]:
    """Validate an exact comparison while keeping both batch results separate."""

    if type(report) is not dict or frozenset(report) != _REPORT_FIELDS:
        raise ValidationError("sequence comparison must be a complete v1 report")
    if report["schema"] != "glio-noncode.sequence-haplotype-batch-comparison.v1":
        raise ValidationError("sequence comparison schema is unsupported")
    if report["status"] != "completed":
        raise ValidationError("sequence comparison report must be completed")
    _source(report["source"])
    _summary(report["left"], "left")
    _summary(report["right"], "right")
    changes = report["changes"]
    if type(changes) is not list or len(changes) > 100_000:
        raise ValidationError("sequence comparison changes exceed their supported limit")
    for index, item in enumerate(changes):
        if type(item) is not dict or frozenset(item) != _CHANGE_FIELDS:
            raise ValidationError(f"sequence comparison change {index + 1} has an invalid shape")
        if item["change"] not in {"created", "disrupted"}:
            raise ValidationError("sequence comparison change direction is unsupported")
        for key in ("motif_id", "name", "matched_sequence", "source_id"):
            _text(item[key], f"change {key}", maximum=4_096)
        if item["strand"] not in {"+", "-"}:
            raise ValidationError("sequence comparison change strand is unsupported")
        _nullable_count(item["left_analysis_count"], "left analysis count")
        _nullable_count(item["right_analysis_count"], "right analysis count")
        left_fraction = _nullable_fraction(item["left_analysis_fraction"], "left fraction")
        right_fraction = _nullable_fraction(item["right_analysis_fraction"], "right fraction")
        delta = item["delta_fraction"]
        if delta is not None:
            if (
                type(delta) not in {int, float}
                or not math.isfinite(delta)
                or not -1.0 <= delta <= 1.0
            ):
                raise ValidationError("sequence comparison delta is invalid")
        if (
            (left_fraction is None) != (right_fraction is None)
            or (left_fraction is None and delta is not None)
            or (left_fraction is not None and delta is None)
        ):
            raise ValidationError("sequence comparison fractions and delta do not reconcile")
        expected_direction = (
            "not_reported_in_one_batch"
            if left_fraction is None or right_fraction is None
            else "increased"
            if float(delta) > 0
            else "decreased"
            if float(delta) < 0
            else "unchanged"
        )
        if item["direction"] != expected_direction:
            raise ValidationError("sequence comparison direction does not match its fractions")
    limitations = report["limitations"]
    if type(limitations) is not list or any(
        type(item) is not str or not item for item in limitations
    ):
        raise ValidationError("sequence comparison limitations are invalid")
    address = report["content_address"]
    if type(address) is not str or _REPORT_ADDRESS_RE.fullmatch(address) is None:
        raise ValidationError("sequence comparison content address is invalid")
    expected = content_hash(
        {key: value for key, value in report.items() if key != "content_address"},
        prefix="sequence-batch-comparison",
    )
    if address != expected:
        raise ValidationError("sequence comparison content address does not verify")
    return report


def summarize_sequence_batch_comparison(report: dict[str, Any]) -> dict[str, Any]:
    validated = validate_sequence_batch_comparison(report)
    return {
        "left_analysis_count": validated["left"]["analysis_count"],
        "right_analysis_count": validated["right"]["analysis_count"],
        "change_count": len(validated["changes"]),
        "content_address": validated["content_address"],
    }


class SequenceBatchComparisonStore:
    """Immutable catalog for stored aggregate batch comparisons."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = ObjectStore(self.root)
        self.records = self.root / "sequence-comparisons"
        self.locks = self.root / ".locks" / "sequence-comparisons"
        _validate_storage_parent(self.records, "sequence comparison store")
        _validate_storage_parent(self.locks, "sequence comparison lock directory")
        try:
            self.records.mkdir(parents=True, exist_ok=True)
            self.locks.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StoreError("sequence comparison store could not be initialized") from exc
        if (
            self.records.is_symlink()
            or not self.records.is_dir()
            or self.locks.is_symlink()
            or not self.locks.is_dir()
        ):
            raise StoreError("sequence comparison storage must be regular directories")
        self._lock = _run_lock(self.records)

    @staticmethod
    def _comparison_id(body: dict[str, Any]) -> str:
        return f"comparison-{content_hash(body).split(':', 1)[1]}"

    def _record_path(self, comparison_id: str) -> Path:
        if type(comparison_id) is not str or _COMPARISON_ID_RE.fullmatch(comparison_id) is None:
            raise ValidationError("sequence comparison identifier is invalid")
        return self.records / f"{comparison_id}.json"

    def _decode_record(self, path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise StoreError("sequence comparison catalog contains an unsafe record")
        try:
            raw = _strict_json_loads(
                read_bytes(
                    path,
                    field="sequence comparison catalog record",
                    max_bytes=MAX_COMPARISON_RECORD_BYTES,
                )
            )
        except (OSError, UnicodeError, ValueError, ValidationError) as exc:
            raise StoreError("sequence comparison catalog record could not be verified") from exc
        if type(raw) is not dict or frozenset(raw) != {
            "schema",
            "comparison_id",
            "report_address",
            "summary",
        }:
            raise StoreError("sequence comparison catalog record has an invalid shape")
        if raw["schema"] != COMPARISON_RECORD_SCHEMA:
            raise StoreError("sequence comparison catalog record schema is unsupported")
        comparison_id = raw["comparison_id"]
        if (
            type(comparison_id) is not str
            or path.stem != comparison_id
            or _COMPARISON_ID_RE.fullmatch(comparison_id) is None
        ):
            raise StoreError("sequence comparison identifier does not match its filename")
        if (
            type(raw["report_address"]) is not str
            or _ADDRESS_RE.fullmatch(raw["report_address"]) is None
        ):
            raise StoreError("sequence comparison object address is invalid")
        if type(raw["summary"]) is not dict or frozenset(raw["summary"]) != _RECORD_SUMMARY_FIELDS:
            raise StoreError("sequence comparison summary has an invalid shape")
        body = {key: value for key, value in raw.items() if key != "comparison_id"}
        if self._comparison_id(body) != comparison_id:
            raise StoreError("sequence comparison catalog address does not verify")
        return raw

    def save(self, report: object) -> dict[str, Any]:
        validated = validate_sequence_batch_comparison(report)
        if len(canonical_json(validated).encode("utf-8")) > MAX_COMPARISON_REPORT_BYTES:
            raise StoreError("sequence comparison report exceeds its byte limit")
        report_address = self.objects.put(validated)
        body = {
            "schema": COMPARISON_RECORD_SCHEMA,
            "report_address": report_address,
            "summary": summarize_sequence_batch_comparison(validated),
        }
        comparison_id = self._comparison_id(body)
        record = body | {"comparison_id": comparison_id}
        path = self._record_path(comparison_id)
        try:
            with self._lock, _filesystem_lock(self.locks / f"{comparison_id}.lock"):
                if path.exists():
                    current = self._decode_record(path)
                    if canonical_json(current) != canonical_json(record):
                        raise StoreError(
                            "sequence comparison record differs at its immutable identifier"
                        )
                else:
                    atomic_write_text(
                        path, canonical_json(record), field="sequence comparison catalog record"
                    )
        except (OSError, ValidationError) as exc:
            raise StoreError("sequence comparison record could not be saved") from exc
        return record

    def list_reports(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= MAX_COMPARISON_RECORDS:
            raise ValidationError("sequence comparison offset is outside its supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_COMPARISON_PAGE_SIZE:
            raise ValidationError("sequence comparison limit is outside its supported range")
        paths = sorted(self.records.glob("comparison-*.json"), key=lambda item: item.name)
        if len(paths) > MAX_COMPARISON_RECORDS:
            raise StoreError("sequence comparison catalog exceeds its record limit")
        records = [self._decode_record(path) for path in paths]
        rows = [
            {"comparison_id": item["comparison_id"], **item["summary"]}
            for item in records[offset : offset + limit]
        ]
        return {
            "schema": COMPARISON_CATALOG_SCHEMA,
            "offset": offset,
            "limit": limit,
            "total_count": len(records),
            "has_more": offset + len(rows) < len(records),
            "rows": rows,
        }

    def get_report(self, comparison_id: str) -> dict[str, Any]:
        path = self._record_path(comparison_id)
        if not path.exists():
            raise KeyError(comparison_id)
        record = self._decode_record(path)
        report = validate_sequence_batch_comparison(
            self.objects.get_canonical(
                record["report_address"], max_bytes=MAX_COMPARISON_REPORT_BYTES
            )
        )
        if summarize_sequence_batch_comparison(report) != record["summary"]:
            raise StoreError("sequence comparison summary does not match its report")
        return {
            "schema": COMPARISON_RECORD_SCHEMA,
            "comparison_id": comparison_id,
            "report_address": record["report_address"],
            "summary": record["summary"],
            "report": report,
        }

    def page_changes(
        self,
        comparison_id: str,
        *,
        offset: int = 0,
        limit: int = 25,
        change: str | None = None,
        direction: str | None = None,
        motif_contains: str | None = None,
    ) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= 10_000:
            raise ValidationError(
                "sequence comparison change offset is outside its supported range"
            )
        if type(limit) is not int or not 1 <= limit <= MAX_COMPARISON_PAGE_SIZE:
            raise ValidationError("sequence comparison change limit is outside its supported range")
        if change is not None and change not in {"created", "disrupted"}:
            raise ValidationError("sequence comparison change must be created or disrupted")
        if direction is not None and direction not in {
            "increased",
            "decreased",
            "unchanged",
            "not_reported_in_one_batch",
        }:
            raise ValidationError("sequence comparison direction is unsupported")
        if motif_contains is not None:
            if (
                type(motif_contains) is not str
                or not motif_contains.strip()
                or len(motif_contains) > MAX_COMPARISON_QUERY_LENGTH
            ):
                raise ValidationError(
                    "sequence comparison motif query is outside its supported range"
                )
            motif_contains = motif_contains.casefold()
        saved = self.get_report(comparison_id)
        filtered = [
            item
            for item in saved["report"]["changes"]
            if (change is None or item["change"] == change)
            and (direction is None or item["direction"] == direction)
            and (
                motif_contains is None
                or motif_contains in item["motif_id"].casefold()
                or motif_contains in item["name"].casefold()
            )
        ]
        deltas = [
            float(item["delta_fraction"])
            for item in filtered
            if item["delta_fraction"] is not None
        ]
        filtered_change_summary = {
            "change_count": len(filtered),
            "created_count": sum(item["change"] == "created" for item in filtered),
            "disrupted_count": sum(item["change"] == "disrupted" for item in filtered),
            "increased_count": sum(item["direction"] == "increased" for item in filtered),
            "decreased_count": sum(item["direction"] == "decreased" for item in filtered),
            "unchanged_count": sum(item["direction"] == "unchanged" for item in filtered),
            "not_reported_count": sum(
                item["direction"] == "not_reported_in_one_batch" for item in filtered
            ),
            "delta_count": len(deltas),
            "mean_delta_fraction": sum(deltas) / len(deltas) if deltas else 0.0,
            "mean_absolute_delta_fraction": (
                sum(abs(delta) for delta in deltas) / len(deltas) if deltas else 0.0
            ),
        }
        return {
            "schema": COMPARISON_CHANGES_SCHEMA,
            "comparison_id": comparison_id,
            "offset": offset,
            "limit": limit,
            "total_changes": len(filtered),
            "unfiltered_change_count": len(saved["report"]["changes"]),
            "has_more": offset + limit < len(filtered),
            "filters": {"change": change, "direction": direction, "motif_contains": motif_contains},
            "filtered_change_summary": filtered_change_summary,
            "changes": filtered[offset : offset + limit],
        }

    def changes_csv(self, comparison_id: str, **filters: str | None) -> str:
        page = self.page_changes(comparison_id, offset=0, limit=MAX_COMPARISON_PAGE_SIZE, **filters)
        if page["total_changes"] > MAX_COMPARISON_PAGE_SIZE:
            raise StoreError("sequence comparison CSV requires a narrower filter")
        fields = (
            "change",
            "motif_id",
            "name",
            "matched_sequence",
            "strand",
            "source_id",
            "left_analysis_fraction",
            "right_analysis_fraction",
            "delta_fraction",
            "direction",
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(fields)
        for item in page["changes"]:
            writer.writerow(tuple(item[field] for field in fields))
        rendered = output.getvalue()
        if len(rendered.encode("utf-8")) > MAX_COMPARISON_CSV_BYTES:
            raise StoreError("sequence comparison CSV exceeds its byte limit")
        return rendered


__all__ = [
    "COMPARISON_CATALOG_SCHEMA",
    "COMPARISON_CHANGES_SCHEMA",
    "COMPARISON_RECORD_SCHEMA",
    "SequenceBatchComparisonStore",
    "summarize_sequence_batch_comparison",
    "validate_sequence_batch_comparison",
]
