"""Bounded archive review projections for saved phased-sequence reports.

The sequence analysis and sequence batch stores deliberately keep their own
immutable records.  This module is the read-only review boundary over those
stores.  It never edits either catalog and it only emits aggregate projections:
raw reference bases, genotype strings, sample keys, and subject keys remain
outside every response produced here.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from pathlib import Path
from typing import Any

from .errors import StoreError, ValidationError
from .sequence_batch_store import SequenceBatchStore
from .sequence_haplotype_store import SequenceHaplotypeStore
from .serialization import content_hash

SEQUENCE_REVIEW_SUMMARY_SCHEMA = "glio-noncode.sequence-review-summary.v1"
SEQUENCE_REVIEW_VERIFY_SCHEMA = "glio-noncode.sequence-review-verification.v1"
SEQUENCE_REVIEW_MOTIFS_SCHEMA = "glio-noncode.sequence-review-motifs.v1"
SEQUENCE_REVIEW_MOTIFS_CSV_SCHEMA = "glio-noncode.sequence-review-motifs-csv.v1"
SEQUENCE_REVIEW_CAPABILITIES_SCHEMA = "glio-noncode.sequence-review-capabilities.v1"

MAX_REVIEW_CATALOG_RECORDS = 10_000
MAX_REVIEW_MOTIF_ROWS = 5_000
MAX_REVIEW_PAGE_SIZE = 100
MAX_REVIEW_QUERY_LENGTH = 256
MAX_REVIEW_CSV_BYTES = 4 * 1024 * 1024


def _json_schema_object(
    title: str, required: tuple[str, ...], properties: dict[str, Any]
) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title,
        "type": "object",
        "additionalProperties": False,
        "required": list(required),
        "properties": properties,
    }


def sequence_review_summary_schema() -> dict[str, Any]:
    """Return the closed root contract for the sequence archive summary."""

    catalog = {
        "type": "object",
        "required": ["record_count"],
        "properties": {
            "record_count": {"type": "integer", "minimum": 0},
            "analysis_count": {"type": "integer", "minimum": 0},
            "supported_count": {"type": "integer", "minimum": 0},
            "abstained_count": {"type": "integer", "minimum": 0},
            "supported_fraction": {"type": "number", "minimum": 0, "maximum": 1},
            "created_motif_count": {"type": "integer", "minimum": 0},
            "disrupted_motif_count": {"type": "integer", "minimum": 0},
            "created_change_count": {"type": "integer", "minimum": 0},
            "disrupted_change_count": {"type": "integer", "minimum": 0},
            "genome_build_counts": {
                "type": "object",
                "additionalProperties": {"type": "integer", "minimum": 0},
            },
            "source_id_counts": {
                "type": "object",
                "additionalProperties": {"type": "integer", "minimum": 0},
            },
            "state_counts": {
                "type": "object",
                "additionalProperties": {"type": "integer", "minimum": 0},
            },
            "interval_count": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": True,
    }
    return _json_schema_object(
        "GLIO-NONCODE sequence review summary",
        (
            "schema",
            "catalogs",
            "integrity",
            "limitations",
            "content_address",
        ),
        {
            "schema": {"const": SEQUENCE_REVIEW_SUMMARY_SCHEMA},
            "catalogs": {"type": "object", "additionalProperties": catalog},
            "integrity": _json_schema_object(
                "GLIO-NONCODE sequence review integrity",
                (
                    "catalog_records",
                    "report_objects",
                    "raw_bases_emitted",
                    "individual_identifiers_emitted",
                ),
                {
                    "catalog_records": {"const": "validated"},
                    "report_objects": {"const": "not_opened"},
                    "raw_bases_emitted": {"const": False},
                    "individual_identifiers_emitted": {"const": False},
                },
            ),
            "limitations": {"type": "array", "items": {"type": "string"}},
            "content_address": {"type": "string"},
        },
    )


def sequence_review_verification_schema() -> dict[str, Any]:
    """Return the closed root contract for sequence object verification."""

    result = _json_schema_object(
        "GLIO-NONCODE sequence review verification row",
        ("kind", "record_id", "status"),
        {
            "kind": {"enum": ["sequence_analysis", "sequence_batch"]},
            "record_id": {"type": "string"},
            "status": {"enum": ["verified", "failed"]},
            "content_address": {"type": "string"},
            "error": {
                "type": "object",
                "required": ["code", "message"],
                "properties": {"code": {"type": "string"}, "message": {"type": "string"}},
                "additionalProperties": False,
            },
        },
    )
    return _json_schema_object(
        "GLIO-NONCODE sequence review verification",
        (
            "schema",
            "record_count",
            "verified_count",
            "failed_count",
            "results",
            "privacy",
            "content_address",
        ),
        {
            "schema": {"const": SEQUENCE_REVIEW_VERIFY_SCHEMA},
            "record_count": {"type": "integer", "minimum": 0},
            "verified_count": {"type": "integer", "minimum": 0},
            "failed_count": {"type": "integer", "minimum": 0},
            "results": {"type": "array", "items": result},
            "privacy": _json_schema_object(
                "GLIO-NONCODE sequence review verification privacy",
                ("raw_bases_emitted", "sample_or_subject_identifiers_emitted"),
                {
                    "raw_bases_emitted": {"const": False},
                    "sample_or_subject_identifiers_emitted": {"const": False},
                },
            ),
            "content_address": {"type": "string"},
        },
    )


def sequence_review_motifs_schema() -> dict[str, Any]:
    """Return the closed root contract for a paged motif activity response."""

    row = _json_schema_object(
        "GLIO-NONCODE sequence review motif row",
        (
            "change",
            "motif_id",
            "name",
            "matched_sequence",
            "strand",
            "source_id",
            "single_analysis_count",
            "batch_count",
            "occurrence_count",
            "max_analysis_fraction",
            "max_batch_fraction",
        ),
        {
            "change": {"enum": ["created", "disrupted"]},
            "motif_id": {"type": "string"},
            "name": {"type": "string"},
            "matched_sequence": {"type": "string"},
            "strand": {"enum": ["+", "-"]},
            "source_id": {"type": "string"},
            "single_analysis_count": {"type": "integer", "minimum": 0},
            "batch_count": {"type": "integer", "minimum": 0},
            "occurrence_count": {"type": "integer", "minimum": 0},
            "max_analysis_fraction": {"type": "number", "minimum": 0, "maximum": 1},
            "max_batch_fraction": {"type": "number", "minimum": 0, "maximum": 1},
        },
    )
    filtered_summary = _json_schema_object(
        "GLIO-NONCODE filtered sequence motif summary",
        (
            "row_count",
            "created_row_count",
            "disrupted_row_count",
            "occurrence_count",
            "single_analysis_occurrence_count",
            "batch_occurrence_count",
            "motif_source_id_counts",
        ),
        {
            "row_count": {"type": "integer", "minimum": 0},
            "created_row_count": {"type": "integer", "minimum": 0},
            "disrupted_row_count": {"type": "integer", "minimum": 0},
            "occurrence_count": {"type": "integer", "minimum": 0},
            "single_analysis_occurrence_count": {"type": "integer", "minimum": 0},
            "batch_occurrence_count": {"type": "integer", "minimum": 0},
            "motif_source_id_counts": {
                "type": "object",
                "additionalProperties": {"type": "integer", "minimum": 0},
            },
        },
    )
    return _json_schema_object(
        "GLIO-NONCODE sequence review motifs",
        (
            "schema",
            "offset",
            "limit",
            "total_count",
            "has_more",
            "filters",
            "filtered_motif_summary",
            "rows",
            "privacy",
            "content_address",
        ),
        {
            "schema": {"const": SEQUENCE_REVIEW_MOTIFS_SCHEMA},
            "offset": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_REVIEW_PAGE_SIZE},
            "total_count": {"type": "integer", "minimum": 0},
            "has_more": {"type": "boolean"},
            "filters": _json_schema_object(
                "GLIO-NONCODE sequence review motif filters",
                ("source_id", "genome_build", "change", "motif_contains"),
                {
                    "source_id": {"type": ["string", "null"]},
                    "genome_build": {"type": ["string", "null"]},
                    "change": {"enum": ["created", "disrupted", None]},
                    "motif_contains": {"type": ["string", "null"]},
                },
            ),
            "filtered_motif_summary": filtered_summary,
            "rows": {"type": "array", "items": row},
            "privacy": _json_schema_object(
                "GLIO-NONCODE sequence review motif privacy",
                ("raw_bases_emitted", "sample_or_subject_identifiers_emitted"),
                {
                    "raw_bases_emitted": {"const": False},
                    "sample_or_subject_identifiers_emitted": {"const": False},
                },
            ),
            "content_address": {"type": "string"},
        },
    )


def sequence_review_capabilities() -> dict[str, Any]:
    """Describe the public sequence archive review surface."""

    return {
        "schema": SEQUENCE_REVIEW_CAPABILITIES_SCHEMA,
        "public": True,
        "read_only": True,
        "verification": "catalog projections or reopened immutable report objects",
        "documents": {
            "summary": SEQUENCE_REVIEW_SUMMARY_SCHEMA,
            "verification": SEQUENCE_REVIEW_VERIFY_SCHEMA,
            "motifs": SEQUENCE_REVIEW_MOTIFS_SCHEMA,
            "motifs_csv": SEQUENCE_REVIEW_MOTIFS_CSV_SCHEMA,
        },
        "formats": ["json", "csv"],
        "operations": ["summary", "verify", "motifs", "motifs_csv", "schema_discovery"],
        "limits": {
            "max_catalog_records": MAX_REVIEW_CATALOG_RECORDS,
            "max_motif_rows": MAX_REVIEW_MOTIF_ROWS,
            "max_page_size": MAX_REVIEW_PAGE_SIZE,
            "max_csv_bytes": MAX_REVIEW_CSV_BYTES,
        },
        "endpoints": {
            "summary": "/v1/sequence-review/summary",
            "verification": "/v1/sequence-review/verify",
            "motifs": "/v1/sequence-review/motifs",
            "motifs_csv": "/v1/sequence-review/motifs.csv",
            "schema_summary": "/v1/sequence-review/schema?document=summary",
            "schema_verification": "/v1/sequence-review/schema?document=verification",
            "schema_motifs": "/v1/sequence-review/schema?document=motifs",
            "capabilities": "/v1/sequence-review/capabilities",
        },
    }


def _text(value: object, label: str, *, maximum: int = MAX_REVIEW_QUERY_LENGTH) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValidationError(f"sequence review {label} is outside its supported bound")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValidationError(f"sequence review {label} contains a control character")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _page(value: object, label: str, *, maximum: int = 10_000) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValidationError(f"sequence review {label} is outside its supported range")
    return value


def _limit(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MAX_REVIEW_PAGE_SIZE:
        raise ValidationError("sequence review limit is outside its supported range")
    return value


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _public_record_count(
    rows: list[dict[str, Any]], *, batch: bool = False
) -> dict[str, Any]:
    states = Counter(str(row["analysis_state"]) for row in rows if "analysis_state" in row)
    if batch or (rows and "batch_id" in rows[0]):
        supported = sum(int(row["supported_count"]) for row in rows)
        analyses = sum(int(row["analysis_count"]) for row in rows)
        created = sum(int(row["created_change_count"]) for row in rows)
        disrupted = sum(int(row["disrupted_change_count"]) for row in rows)
        genomes = Counter(str(row["genome_build"]) for row in rows)
        sources = Counter(str(row["source_id"]) for row in rows)
        return {
            "record_count": len(rows),
            "analysis_count": analyses,
            "supported_count": supported,
            "abstained_count": sum(int(row["abstained_count"]) for row in rows),
            "supported_fraction": supported / analyses if analyses else 0.0,
            "created_change_count": created,
            "disrupted_change_count": disrupted,
            "genome_build_counts": _counter_dict(genomes),
            "source_id_counts": _counter_dict(sources),
        }
    created = sum(int(row["created_motif_count"]) for row in rows)
    disrupted = sum(int(row["disrupted_motif_count"]) for row in rows)
    genomes = Counter(str(row["genome_build"]) for row in rows)
    sources = Counter(str(row["source_id"]) for row in rows)
    intervals = {
        (str(row["chromosome"]), int(row["start"]), int(row["end"])) for row in rows
    }
    return {
        "record_count": len(rows),
        "created_motif_count": created,
        "disrupted_motif_count": disrupted,
        "genome_build_counts": _counter_dict(genomes),
        "source_id_counts": _counter_dict(sources),
        "interval_count": len(intervals),
        "supported_count": states.get("supported", 0),
        "abstained_count": states.get("abstained", 0),
        "state_counts": _counter_dict(states),
    }


def _record_error(error: BaseException) -> dict[str, str]:
    """Return a stable, path-free error projection for archive verification."""

    if isinstance(error, KeyError):
        code = "missing_record"
    elif isinstance(error, ValidationError):
        code = "invalid_record"
    elif isinstance(error, StoreError):
        code = "store_integrity_failure"
    elif isinstance(error, OSError):
        code = "storage_read_failure"
    else:
        code = "unexpected_verification_failure"
    return {"code": code, "message": str(error)[:512] or code}


class SequenceReviewStore:
    """Read-only, bounded review projections over both sequence catalogs."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.analyses = SequenceHaplotypeStore(self.root)
        self.batches = SequenceBatchStore(self.root)

    def _analysis_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self.analyses.list_reports(offset=offset, limit=50)
            rows.extend(page["rows"])
            if len(rows) > MAX_REVIEW_CATALOG_RECORDS or not page["has_more"]:
                break
            offset += len(page["rows"])
        if len(rows) > MAX_REVIEW_CATALOG_RECORDS:
            raise StoreError("sequence review analysis catalog exceeds its record limit")
        return rows

    def _batch_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self.batches.list_reports(offset=offset, limit=50)
            rows.extend(page["rows"])
            if len(rows) > MAX_REVIEW_CATALOG_RECORDS or not page["has_more"]:
                break
            offset += len(page["rows"])
        if len(rows) > MAX_REVIEW_CATALOG_RECORDS:
            raise StoreError("sequence review batch catalog exceeds its record limit")
        return rows

    def summary(self) -> dict[str, Any]:
        """Summarize catalog records without opening report objects."""

        analysis_rows = self._analysis_rows()
        batch_rows = self._batch_rows()
        body = {
            "schema": SEQUENCE_REVIEW_SUMMARY_SCHEMA,
            "catalogs": {
                "sequence_analyses": _public_record_count(analysis_rows),
                "sequence_batches": _public_record_count(batch_rows, batch=True),
            },
            "integrity": {
                "catalog_records": "validated",
                "report_objects": "not_opened",
                "raw_bases_emitted": False,
                "individual_identifiers_emitted": False,
            },
            "limitations": [
                (
                    "This summary validates immutable catalog records but does not open "
                    "every report object."
                ),
                "Counts describe saved reports and are not prevalence estimates for a population.",
                (
                    "A supported sequence-only state does not establish binding, chromatin "
                    "activity, target gene, or causality."
                ),
            ],
        }
        return body | {"content_address": content_hash(body, prefix="sequence-review-summary")}

    def verify(self) -> dict[str, Any]:
        """Reopen every saved report and return a public integrity ledger."""

        analysis_rows = self._analysis_rows()
        batch_rows = self._batch_rows()
        results: list[dict[str, Any]] = []
        for row in analysis_rows:
            analysis_id = str(row["analysis_id"])
            try:
                saved = self.analyses.get_report(analysis_id)
                results.append(
                    {
                        "kind": "sequence_analysis",
                        "record_id": analysis_id,
                        "status": "verified",
                        "content_address": saved["report_address"],
                    }
                )
            except (KeyError, OSError, StoreError, ValidationError) as error:
                results.append(
                    {
                        "kind": "sequence_analysis",
                        "record_id": analysis_id,
                        "status": "failed",
                        "error": _record_error(error),
                    }
                )
        for row in batch_rows:
            batch_id = str(row["batch_id"])
            try:
                saved = self.batches.get_report(batch_id)
                results.append(
                    {
                        "kind": "sequence_batch",
                        "record_id": batch_id,
                        "status": "verified",
                        "content_address": saved["report_address"],
                    }
                )
            except (KeyError, OSError, StoreError, ValidationError) as error:
                results.append(
                    {
                        "kind": "sequence_batch",
                        "record_id": batch_id,
                        "status": "failed",
                        "error": _record_error(error),
                    }
                )
        results.sort(key=lambda item: (item["kind"], item["record_id"]))
        body = {
            "schema": SEQUENCE_REVIEW_VERIFY_SCHEMA,
            "record_count": len(results),
            "verified_count": sum(item["status"] == "verified" for item in results),
            "failed_count": sum(item["status"] == "failed" for item in results),
            "results": results,
            "privacy": {
                "raw_bases_emitted": False,
                "sample_or_subject_identifiers_emitted": False,
            },
        }
        return body | {"content_address": content_hash(body, prefix="sequence-review-verification")}

    @staticmethod
    def _validate_filters(
        *,
        source_id: str | None,
        genome_build: str | None,
        change: str | None,
        motif_contains: str | None,
        offset: int,
        limit: int,
    ) -> tuple[str | None, str | None, str | None, str | None, int, int]:
        source_id = _optional_text(source_id, "source_id")
        genome_build = _optional_text(genome_build, "genome_build")
        motif_contains = _optional_text(motif_contains, "motif_contains")
        if motif_contains is not None:
            motif_contains = motif_contains.casefold()
        if change is not None and change not in {"created", "disrupted"}:
            raise ValidationError("sequence review change must be created or disrupted")
        return (
            source_id,
            genome_build,
            change,
            motif_contains,
            _page(offset, "offset"),
            _limit(limit),
        )

    def motif_activity(
        self,
        *,
        source_id: str | None = None,
        genome_build: str | None = None,
        change: str | None = None,
        motif_contains: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Aggregate exact motif deltas across all saved reports."""

        source_id, genome_build, change, motif_contains, offset, limit = self._validate_filters(
            source_id=source_id,
            genome_build=genome_build,
            change=change,
            motif_contains=motif_contains,
            offset=offset,
            limit=limit,
        )
        analysis_rows = self._analysis_rows()
        batch_rows = self._batch_rows()
        grouped: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}

        def add_hit(
            key: tuple[str, str, str, str, str, str],
            *,
            kind: str,
            fraction: float,
        ) -> None:
            row = grouped.setdefault(
                key,
                {
                    "change": key[0],
                    "motif_id": key[1],
                    "name": key[2],
                    "matched_sequence": key[3],
                    "strand": key[4],
                    "source_id": key[5],
                    "single_analysis_count": 0,
                    "batch_count": 0,
                    "occurrence_count": 0,
                    "max_analysis_fraction": 0.0,
                    "max_batch_fraction": 0.0,
                },
            )
            row["occurrence_count"] += 1
            if kind == "sequence_analysis":
                row["single_analysis_count"] += 1
                row["max_analysis_fraction"] = max(row["max_analysis_fraction"], fraction)
            else:
                row["batch_count"] += 1
                row["max_batch_fraction"] = max(row["max_batch_fraction"], fraction)

        for catalog_row in analysis_rows:
            if source_id is not None and catalog_row["source_id"] != source_id:
                continue
            if genome_build is not None and catalog_row["genome_build"] != genome_build:
                continue
            saved = self.analyses.get_report(catalog_row["analysis_id"])
            analysis = saved["report"]["analysis"]
            for direction in ("created", "disrupted"):
                if change is not None and direction != change:
                    continue
                for hit in analysis[f"{direction}_hits"]:
                    if motif_contains is not None and (
                        motif_contains not in hit["motif_id"].casefold()
                        and motif_contains not in hit["name"].casefold()
                    ):
                        continue
                    key = (
                        direction,
                        hit["motif_id"],
                        hit["name"],
                        hit["matched_sequence"],
                        hit["strand"],
                        hit["source_id"],
                    )
                    add_hit(key, kind="sequence_analysis", fraction=1.0)

        for catalog_row in batch_rows:
            if source_id is not None and catalog_row["source_id"] != source_id:
                continue
            if genome_build is not None and catalog_row["genome_build"] != genome_build:
                continue
            saved = self.batches.get_report(catalog_row["batch_id"])
            for hit in saved["report"]["motif_changes"]:
                if change is not None and hit["change"] != change:
                    continue
                if motif_contains is not None and (
                    motif_contains not in hit["motif_id"].casefold()
                    and motif_contains not in hit["name"].casefold()
                ):
                    continue
                key = (
                    hit["change"],
                    hit["motif_id"],
                    hit["name"],
                    hit["matched_sequence"],
                    hit["strand"],
                    hit["source_id"],
                )
                add_hit(key, kind="sequence_batch", fraction=float(hit["analysis_fraction"]))

        rows = sorted(
            grouped.values(),
            key=lambda item: (
                -int(item["occurrence_count"]),
                item["change"],
                item["motif_id"],
                item["matched_sequence"],
                item["strand"],
                item["source_id"],
            ),
        )
        if len(rows) > MAX_REVIEW_MOTIF_ROWS:
            raise StoreError("sequence review motif catalog exceeds its row limit")
        filtered_motif_summary = {
            "row_count": len(rows),
            "created_row_count": sum(row["change"] == "created" for row in rows),
            "disrupted_row_count": sum(row["change"] == "disrupted" for row in rows),
            "occurrence_count": sum(int(row["occurrence_count"]) for row in rows),
            "single_analysis_occurrence_count": sum(
                int(row["single_analysis_count"]) for row in rows
            ),
            "batch_occurrence_count": sum(int(row["batch_count"]) for row in rows),
            "motif_source_id_counts": _counter_dict(
                Counter(str(row["source_id"]) for row in rows)
            ),
        }
        body = {
            "schema": SEQUENCE_REVIEW_MOTIFS_SCHEMA,
            "offset": offset,
            "limit": limit,
            "total_count": len(rows),
            "has_more": offset + limit < len(rows),
            "filters": {
                "source_id": source_id,
                "genome_build": genome_build,
                "change": change,
                "motif_contains": motif_contains,
            },
            "filtered_motif_summary": filtered_motif_summary,
            "rows": rows[offset : offset + limit],
            "privacy": {
                "raw_bases_emitted": False,
                "sample_or_subject_identifiers_emitted": False,
            },
        }
        return body | {"content_address": content_hash(body, prefix="sequence-review-motifs")}

    def motifs_csv(self, **filters: Any) -> str:
        """Export a bounded exact motif-activity page as aggregate CSV."""

        page = self.motif_activity(offset=0, limit=MAX_REVIEW_PAGE_SIZE, **filters)
        if page["total_count"] > MAX_REVIEW_PAGE_SIZE:
            raise StoreError("sequence review motif CSV requires a narrower filter")
        fields = (
            "change",
            "motif_id",
            "name",
            "matched_sequence",
            "strand",
            "source_id",
            "single_analysis_count",
            "batch_count",
            "occurrence_count",
            "max_analysis_fraction",
            "max_batch_fraction",
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(fields)
        for row in page["rows"]:
            writer.writerow(tuple(row[field] for field in fields))
        rendered = output.getvalue()
        if len(rendered.encode("utf-8")) > MAX_REVIEW_CSV_BYTES:
            raise StoreError("sequence review motif CSV exceeds its byte limit")
        return rendered


__all__ = [
    "MAX_REVIEW_PAGE_SIZE",
    "SEQUENCE_REVIEW_MOTIFS_CSV_SCHEMA",
    "SEQUENCE_REVIEW_MOTIFS_SCHEMA",
    "SEQUENCE_REVIEW_CAPABILITIES_SCHEMA",
    "SEQUENCE_REVIEW_SUMMARY_SCHEMA",
    "SEQUENCE_REVIEW_VERIFY_SCHEMA",
    "sequence_review_capabilities",
    "sequence_review_motifs_schema",
    "sequence_review_summary_schema",
    "sequence_review_verification_schema",
    "SequenceReviewStore",
]
