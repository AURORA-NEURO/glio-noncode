"""Immutable persistence and bounded review projections for sequence reports.

Sequence windows and caller-provided phased calls are analyzed once, then the
public report can be cataloged without retaining the source bases or sample
identifiers in the review projection.
"""

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

SEQUENCE_ANALYSIS_RECORD_SCHEMA = "glio-noncode.sequence-haplotype-record.v1"
SEQUENCE_ANALYSIS_CATALOG_SCHEMA = "glio-noncode.sequence-haplotype-catalog.v1"
MAX_SEQUENCE_ANALYSIS_REPORT_BYTES = 8 * 1024 * 1024
MAX_SEQUENCE_ANALYSIS_RECORD_BYTES = 256 * 1024
MAX_SEQUENCE_ANALYSIS_RECORDS = 10_000
MAX_SEQUENCE_ANALYSIS_PAGE_SIZE = 50
MAX_SEQUENCE_ANALYSIS_OFFSET = 10_000
MAX_SEQUENCE_CHANGE_QUERY_LENGTH = 256
MAX_SEQUENCE_CHANGE_EXPORT_BYTES = 8 * 1024 * 1024

_ANALYSIS_ID_RE = re.compile(r"seq-[0-9a-f]{64}\Z")
_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REPORT_ADDRESS_RE = re.compile(r"sequence-haplotype-analysis:[0-9a-f]{64}\Z")
_REPORT_FIELDS = frozenset(
    {
        "schema",
        "status",
        "analysis_state",
        "source",
        "inputs",
        "analysis",
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
_SOURCE_OPTIONAL_FIELDS = frozenset({"downloaded_inputs"})
_DOWNLOAD_FIELDS = frozenset(
    {
        "role",
        "source_id",
        "source_url",
        "source_version",
        "retrieved_at",
        "sha256",
        "size_bytes",
        "compression",
    }
)
_INPUT_FIELDS = frozenset(
    {"genome_build", "variant_count", "motif_count", "variants", "motifs"}
)
_VARIANT_FIELDS = frozenset(
    {"variant_id", "canonical_key", "phase_set", "haplotype_index"}
)
_MOTIF_FIELDS = frozenset({"motif_id", "name", "pattern", "source_id"})
_ANALYSIS_FIELDS = frozenset(
    {
        "phase_set",
        "haplotype_index",
        "variant_ids",
        "state",
        "source_id",
        "reference_interval",
        "reference_sequence_hash",
        "alternate_sequence_hash",
        "alternate_length_delta",
        "gc_fraction_reference",
        "gc_fraction_alternate",
        "motif_set_hash",
        "created_hits",
        "disrupted_hits",
        "limitations",
        "content_address",
    }
)
_HIT_FIELDS = frozenset(
    {
        "change",
        "motif_id",
        "name",
        "strand",
        "matched_sequence",
        "source_id",
        "reference_interval",
        "haplotype_interval",
        "variant_ids",
    }
)
_SUMMARY_FIELDS = frozenset(
    {
        "analysis_state",
        "genome_build",
        "source_id",
        "source_version",
        "chromosome",
        "start",
        "end",
        "variant_count",
        "motif_count",
        "created_motif_count",
        "disrupted_motif_count",
        "content_address",
    }
)
_SUMMARY_OPTIONAL_FIELDS = frozenset({"download_receipt_count", "download_receipt_roles"})
_PRIVATE_KEYS = frozenset(
    {
        "sample_id",
        "sample_ids",
        "subject_id",
        "subject_ids",
        "patient_id",
        "patient_ids",
        "individual_id",
        "individual_ids",
        "genotype",
        "genotypes",
    }
)


def _object(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != fields:
        raise ValidationError(f"sequence {label} has an invalid v1 shape")
    return value


def _text(value: object, label: str, *, maximum: int = 4_096) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValidationError(f"sequence {label} must be non-empty text within its bound")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValidationError(f"sequence {label} contains a control character")
    return value


def _count(value: object, label: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ValidationError(f"sequence {label} is outside its supported range")
    return value


def _address(value: object, label: str) -> str:
    if type(value) is not str or _ADDRESS_RE.fullmatch(value) is None:
        raise ValidationError(f"sequence {label} is not a sha256 address")
    return value


def _check_public_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is str and key.casefold() in _PRIVATE_KEYS:
                raise ValidationError("sequence report contains a private individual key")
            _check_public_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_public_keys(item)


def _validate_interval(value: object, label: str) -> tuple[str, int, int]:
    if type(value) not in {list, tuple} or len(value) != 3:
        raise ValidationError(f"sequence {label} must be a three-part interval")
    chromosome = _text(value[0], f"{label} chromosome", maximum=256)
    start = _count(value[1], f"{label} start", minimum=1)
    end = _count(value[2], f"{label} end", minimum=start)
    return chromosome, start, end


def _validate_fraction(value: object, label: str) -> None:
    if value is None:
        return
    if type(value) not in {int, float} or not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValidationError(f"sequence {label} must be a finite fraction or null")


def _validate_hit(value: object, *, expected_change: str) -> dict[str, Any]:
    hit = _object(value, _HIT_FIELDS, "motif hit")
    if hit["change"] != expected_change:
        raise ValidationError("sequence motif hit change does not match its collection")
    for key in ("motif_id", "name", "matched_sequence", "source_id"):
        _text(hit[key], f"motif hit {key}")
    if hit["strand"] not in {"+", "-"}:
        raise ValidationError("sequence motif hit strand is unsupported")
    if hit["reference_interval"] is not None:
        _validate_interval(hit["reference_interval"], "motif reference interval")
    if hit["haplotype_interval"] is not None:
        interval = hit["haplotype_interval"]
        if type(interval) not in {list, tuple} or len(interval) != 2:
            raise ValidationError("sequence motif haplotype interval is invalid")
        _count(interval[0], "motif haplotype start", minimum=1)
        _count(interval[1], "motif haplotype end", minimum=interval[0])
    variants = hit["variant_ids"]
    if type(variants) is not list or not all(type(item) is str and item for item in variants):
        raise ValidationError("sequence motif hit variant IDs are invalid")
    if len(variants) != len(set(variants)):
        raise ValidationError("sequence motif hit variant IDs must be unique")
    return hit


def _validate_downloaded_inputs(value: object) -> None:
    if type(value) is not list or not 1 <= len(value) <= 2:
        raise ValidationError("sequence downloaded inputs must contain one or two receipts")
    roles: set[str] = set()
    for index, item in enumerate(value):
        receipt = _object(item, _DOWNLOAD_FIELDS, f"downloaded input {index + 1}")
        role = _text(receipt["role"], f"downloaded input {index + 1} role", maximum=32)
        if role not in {"fasta", "vcf"} or role in roles:
            raise ValidationError("sequence downloaded input roles must be unique FASTA/VCF values")
        roles.add(role)
        for key, maximum in (
            ("source_id", 128),
            ("source_version", 256),
            ("retrieved_at", 128),
        ):
            _text(receipt[key], f"downloaded input {index + 1} {key}", maximum=maximum)
        source_url = _text(
            receipt["source_url"], f"downloaded input {index + 1} URL", maximum=8_192
        )
        parsed_url = urlsplit(source_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValidationError(f"downloaded input {index + 1} URL is not absolute HTTP")
        sha256 = _text(receipt["sha256"], f"downloaded input {index + 1} SHA-256", maximum=71)
        if _ADDRESS_RE.fullmatch(sha256) is None:
            raise ValidationError(f"downloaded input {index + 1} SHA-256 is invalid")
        _count(
            receipt["size_bytes"],
            f"downloaded input {index + 1} size",
            maximum=128 * 1024 * 1024,
        )
        compression = _text(
            receipt["compression"], f"downloaded input {index + 1} compression", maximum=16
        )
        if compression not in {"none", "gzip"}:
            raise ValidationError(f"downloaded input {index + 1} compression is unsupported")


def _validate_analysis(value: object) -> dict[str, Any]:
    analysis = _object(value, _ANALYSIS_FIELDS, "analysis")
    _text(analysis["phase_set"], "analysis phase set", maximum=256)
    haplotype_index = _count(analysis["haplotype_index"], "analysis haplotype index", minimum=1)
    if haplotype_index > 32:
        raise ValidationError("sequence analysis haplotype index is outside its bound")
    variant_ids = analysis["variant_ids"]
    if type(variant_ids) is not list or any(
        type(item) is not str or not item for item in variant_ids
    ):
        raise ValidationError("sequence analysis variant IDs are invalid")
    if len(variant_ids) != len(set(variant_ids)):
        raise ValidationError("sequence analysis variant IDs must be unique")
    if analysis["state"] not in {"supported", "reference_mismatch", "out_of_window", "abstained"}:
        raise ValidationError("sequence analysis state is unsupported")
    _text(analysis["source_id"], "analysis source ID", maximum=256)
    _validate_interval(analysis["reference_interval"], "analysis reference interval")
    for key in ("reference_sequence_hash", "motif_set_hash"):
        _address(analysis[key], f"analysis {key}")
    if analysis["alternate_sequence_hash"] is not None:
        _address(analysis["alternate_sequence_hash"], "analysis alternate sequence hash")
    if analysis["alternate_length_delta"] is not None and type(
        analysis["alternate_length_delta"]
    ) is not int:
        raise ValidationError("sequence alternate length delta must be an integer or null")
    _validate_fraction(analysis["gc_fraction_reference"], "reference GC fraction")
    _validate_fraction(analysis["gc_fraction_alternate"], "alternate GC fraction")
    for key, change in (("created_hits", "created"), ("disrupted_hits", "disrupted")):
        hits = analysis[key]
        if type(hits) is not list:
            raise ValidationError(f"sequence {key} must be an array")
        for hit in hits:
            _validate_hit(hit, expected_change=change)
    limitations = analysis["limitations"]
    if type(limitations) is not list or any(
        type(item) is not str or not item for item in limitations
    ):
        raise ValidationError("sequence analysis limitations are invalid")
    _address(analysis["content_address"], "analysis content address")
    return analysis


def validate_sequence_haplotype_report(report: object) -> dict[str, Any]:
    """Validate one complete, public, content-addressed sequence report."""

    if type(report) is not dict or frozenset(report) != _REPORT_FIELDS:
        raise ValidationError("sequence analysis must be a complete v1 report")
    _check_public_keys(report)
    if report["schema"] != "glio-noncode.sequence-haplotype-analysis.v1":
        raise ValidationError("sequence analysis report schema is unsupported")
    if report["status"] != "completed":
        raise ValidationError("sequence analysis report must be completed")
    if report["analysis_state"] not in {
        "supported", "reference_mismatch", "out_of_window", "abstained"
    }:
        raise ValidationError("sequence analysis report state is unsupported")
    source_value = report["source"]
    if (
        type(source_value) is not dict
        or not _SOURCE_FIELDS.issubset(source_value)
        or not frozenset(source_value).issubset(_SOURCE_FIELDS | _SOURCE_OPTIONAL_FIELDS)
    ):
        raise ValidationError("sequence source has an invalid v1 shape")
    source = source_value
    for key in ("source_id", "source_version", "retrieved_at"):
        _text(source[key], f"source {key}")
    source_url = _text(source["source_url"], "source URL", maximum=8_192)
    parsed_url = urlsplit(source_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValidationError("sequence source URL must be an absolute HTTP URL")
    _address(source["response_hash"], "source response hash")
    _address(source["sequence_hash"], "source sequence hash")
    interval = _validate_interval(source["sequence_interval"], "source interval")
    if "downloaded_inputs" in source:
        _validate_downloaded_inputs(source["downloaded_inputs"])
    inputs = _object(report["inputs"], _INPUT_FIELDS, "inputs")
    _text(inputs["genome_build"], "genome build", maximum=256)
    variant_count = _count(inputs["variant_count"], "variant count", minimum=1, maximum=1_024)
    motif_count = _count(inputs["motif_count"], "motif count", maximum=2_048)
    variants = inputs["variants"]
    if type(variants) is not list or len(variants) != variant_count:
        raise ValidationError("sequence variant count does not match variant records")
    for index, item in enumerate(variants):
        variant = _object(item, _VARIANT_FIELDS, f"variant {index + 1}")
        for key in ("variant_id", "canonical_key", "phase_set"):
            _text(variant[key], f"variant {index + 1} {key}", maximum=512)
        haplotype_index = _count(
            variant["haplotype_index"],
            f"variant {index + 1} haplotype",
            minimum=1,
        )
        if haplotype_index > 32:
            raise ValidationError("sequence variant haplotype is outside its bound")
    motifs = inputs["motifs"]
    if type(motifs) is not list or len(motifs) != motif_count:
        raise ValidationError("sequence motif count does not match motif records")
    for index, item in enumerate(motifs):
        motif = _object(item, _MOTIF_FIELDS, f"motif {index + 1}")
        for key in _MOTIF_FIELDS:
            _text(motif[key], f"motif {index + 1} {key}", maximum=4_096)
    analysis = _validate_analysis(report["analysis"])
    if report["analysis_state"] != analysis["state"]:
        raise ValidationError("sequence report state does not match analysis state")
    if analysis["source_id"] != source["source_id"]:
        raise ValidationError("sequence report source IDs do not match")
    if tuple(analysis["reference_interval"]) != interval:
        raise ValidationError("sequence report intervals do not match")
    limitations = report["limitations"]
    if type(limitations) is not list or any(
        type(item) is not str or not item for item in limitations
    ):
        raise ValidationError("sequence report limitations are invalid")
    content_address = report["content_address"]
    if type(content_address) is not str or _REPORT_ADDRESS_RE.fullmatch(content_address) is None:
        raise ValidationError("sequence report content address is invalid")
    expected = content_hash(
        {key: value for key, value in report.items() if key != "content_address"},
        prefix="sequence-haplotype-analysis",
    )
    if content_address != expected:
        raise ValidationError("sequence report content address does not verify")
    return report


def summarize_sequence_haplotype_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Build a compact catalog row with no sequence payload or sample keys."""

    validated = validate_sequence_haplotype_report(dict(report))
    source = validated["source"]
    inputs = validated["inputs"]
    analysis = validated["analysis"]
    chromosome, start, end = source["sequence_interval"]
    summary = {
        "analysis_state": validated["analysis_state"],
        "genome_build": inputs["genome_build"],
        "source_id": source["source_id"],
        "source_version": source["source_version"],
        "chromosome": chromosome,
        "start": start,
        "end": end,
        "variant_count": inputs["variant_count"],
        "motif_count": inputs["motif_count"],
        "created_motif_count": len(analysis["created_hits"]),
        "disrupted_motif_count": len(analysis["disrupted_hits"]),
        "content_address": validated["content_address"],
    }
    if "downloaded_inputs" in source:
        summary.update(
            {
                "download_receipt_count": len(source["downloaded_inputs"]),
                "download_receipt_roles": sorted(
                    item["role"] for item in source["downloaded_inputs"]
                ),
            }
        )
    return summary


class SequenceHaplotypeStore:
    """Immutable content-addressed sequence reports colocated with a data root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = ObjectStore(self.root)
        self.records = self.root / "sequence-analyses"
        self.locks = self.root / ".locks" / "sequence-analyses"
        try:
            _validate_storage_parent(self.records, "sequence analysis store")
            if self.records.is_symlink():
                raise StoreError("sequence analysis store must be a regular directory")
            self.records.mkdir(parents=True, exist_ok=True)
            if self.records.is_symlink() or not self.records.is_dir():
                raise StoreError("sequence analysis store must be a regular directory")
            _validate_storage_parent(self.locks, "sequence analysis lock directory")
            if self.locks.is_symlink():
                raise StoreError("sequence analysis lock directory must be regular")
            self.locks.mkdir(parents=True, exist_ok=True)
            if self.locks.is_symlink() or not self.locks.is_dir():
                raise StoreError("sequence analysis lock directory must be regular")
        except StoreError:
            raise
        except OSError as exc:
            raise StoreError("sequence analysis store could not be initialized") from exc
        self._lock = _run_lock(self.records)

    @staticmethod
    def _analysis_id(body: Mapping[str, Any]) -> str:
        return f"seq-{content_hash(body).split(':', 1)[1]}"

    def _record_path(self, analysis_id: str) -> Path:
        if type(analysis_id) is not str or _ANALYSIS_ID_RE.fullmatch(analysis_id) is None:
            raise ValidationError("sequence analysis identifier is invalid")
        return self.records / f"{analysis_id}.json"

    def _decode_record(self, path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise StoreError("sequence analysis catalog contains an unsafe record")
        try:
            payload = read_bytes(
                path,
                field="sequence analysis catalog record",
                max_bytes=MAX_SEQUENCE_ANALYSIS_RECORD_BYTES,
            )
            raw = _strict_json_loads(payload)
        except (OSError, UnicodeError, ValueError, ValidationError) as exc:
            raise StoreError("sequence analysis catalog record could not be verified") from exc
        if type(raw) is not dict or frozenset(raw) != frozenset(
            {"schema", "analysis_id", "report_address", "summary"}
        ):
            raise StoreError("sequence analysis catalog record has an invalid shape")
        if raw["schema"] != SEQUENCE_ANALYSIS_RECORD_SCHEMA:
            raise StoreError("sequence analysis catalog record schema is unsupported")
        analysis_id = raw["analysis_id"]
        if (
            type(analysis_id) is not str
            or path.stem != analysis_id
            or _ANALYSIS_ID_RE.fullmatch(analysis_id) is None
        ):
            raise StoreError("sequence analysis identifier does not match its filename")
        report_address = raw["report_address"]
        if type(report_address) is not str or _ADDRESS_RE.fullmatch(report_address) is None:
            raise StoreError("sequence report object address is invalid")
        summary = raw["summary"]
        if type(summary) is not dict or not _SUMMARY_FIELDS.issubset(summary):
            raise StoreError("sequence analysis summary has an invalid shape")
        summary_fields = frozenset(summary)
        if not summary_fields.issubset(_SUMMARY_FIELDS | _SUMMARY_OPTIONAL_FIELDS):
            raise StoreError("sequence analysis summary has an invalid shape")
        has_receipt_count = "download_receipt_count" in summary
        has_receipt_roles = "download_receipt_roles" in summary
        if has_receipt_count != has_receipt_roles:
            raise StoreError("sequence analysis summary has incomplete receipt coverage")
        if has_receipt_count:
            receipt_count = summary["download_receipt_count"]
            receipt_roles = summary["download_receipt_roles"]
            if (
                type(receipt_count) is not int
                or not 1 <= receipt_count <= 2
                or type(receipt_roles) is not list
                or receipt_roles != sorted(receipt_roles)
                or len(receipt_roles) != receipt_count
                or len(set(receipt_roles)) != receipt_count
                or not all(role in {"fasta", "vcf"} for role in receipt_roles)
            ):
                raise StoreError("sequence analysis summary has invalid receipt coverage")
        body = {key: value for key, value in raw.items() if key != "analysis_id"}
        if self._analysis_id(body) != analysis_id:
            raise StoreError("sequence analysis catalog address does not verify")
        return raw

    def save(self, report: object) -> dict[str, Any]:
        """Persist one complete report and return its deterministic catalog row."""

        validated = validate_sequence_haplotype_report(report)
        if len(canonical_json(validated).encode("utf-8")) > MAX_SEQUENCE_ANALYSIS_REPORT_BYTES:
            raise StoreError("sequence analysis report exceeds its byte limit")
        report_address = self.objects.put(validated)
        body = {
            "schema": SEQUENCE_ANALYSIS_RECORD_SCHEMA,
            "report_address": report_address,
            "summary": summarize_sequence_haplotype_report(validated),
        }
        analysis_id = self._analysis_id(body)
        record = body | {"analysis_id": analysis_id}
        path = self._record_path(analysis_id)
        try:
            with self._lock, _filesystem_lock(self.locks / f"{analysis_id}.lock"):
                if path.is_symlink():
                    raise StoreError("sequence analysis record path is unsafe")
                if path.exists():
                    current = self._decode_record(path)
                    if canonical_json(current) != canonical_json(record):
                        raise StoreError(
                            "sequence analysis record differs at its immutable identifier"
                        )
                else:
                    atomic_write_text(
                        path,
                        canonical_json(record),
                        field="sequence analysis catalog record",
                    )
        except (OSError, ValidationError) as exc:
            raise StoreError("sequence analysis record could not be saved") from exc
        return record

    def list_reports(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        """Return a deterministic bounded catalog page."""

        if type(offset) is not int or not 0 <= offset <= MAX_SEQUENCE_ANALYSIS_OFFSET:
            raise ValidationError("sequence analysis offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_SEQUENCE_ANALYSIS_PAGE_SIZE:
            raise ValidationError("sequence analysis limit is outside the supported range")
        paths = sorted(self.records.glob("seq-*.json"), key=lambda item: item.name)
        if len(paths) > MAX_SEQUENCE_ANALYSIS_RECORDS:
            raise StoreError("sequence analysis catalog exceeds its record limit")
        records = [self._decode_record(path) for path in paths]
        rows = [
            {"analysis_id": item["analysis_id"], **item["summary"]}
            for item in records[offset : offset + limit]
        ]
        return {
            "schema": SEQUENCE_ANALYSIS_CATALOG_SCHEMA,
            "offset": offset,
            "limit": limit,
            "total_count": len(records),
            "has_more": offset + len(rows) < len(records),
            "rows": rows,
        }

    def get_report(self, analysis_id: str) -> dict[str, Any]:
        """Load and independently revalidate one complete stored report."""

        path = self._record_path(analysis_id)
        if not path.exists():
            raise KeyError(analysis_id)
        record = self._decode_record(path)
        report = self.objects.get_canonical(
            record["report_address"], max_bytes=MAX_SEQUENCE_ANALYSIS_REPORT_BYTES
        )
        validated = validate_sequence_haplotype_report(report)
        current_summary = summarize_sequence_haplotype_report(validated)
        legacy_summary = {
            key: value
            for key, value in current_summary.items()
            if key not in _SUMMARY_OPTIONAL_FIELDS
        }
        if record["summary"] != current_summary and record["summary"] != legacy_summary:
            raise StoreError("sequence analysis summary does not match its report")
        return {
            "schema": SEQUENCE_ANALYSIS_RECORD_SCHEMA,
            "analysis_id": analysis_id,
            "report_address": record["report_address"],
            "summary": record["summary"],
            "report": validated,
        }

    def page_changes(
        self,
        analysis_id: str,
        *,
        offset: int = 0,
        limit: int = 25,
        change: str | None = None,
        motif_contains: str | None = None,
    ) -> dict[str, Any]:
        """Page aggregate motif changes without returning source sequence data."""

        if type(offset) is not int or not 0 <= offset <= MAX_SEQUENCE_ANALYSIS_OFFSET:
            raise ValidationError("sequence change offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_SEQUENCE_ANALYSIS_PAGE_SIZE:
            raise ValidationError("sequence change limit is outside the supported range")
        if change is not None and change not in {"created", "disrupted"}:
            raise ValidationError("sequence motif change must be created or disrupted")
        if motif_contains is not None:
            if (
                type(motif_contains) is not str
                or not motif_contains.strip()
                or len(motif_contains) > MAX_SEQUENCE_CHANGE_QUERY_LENGTH
                or any(ord(character) < 32 or ord(character) == 127 for character in motif_contains)
            ):
                raise ValidationError("sequence motif query is outside the supported range")
            motif_contains = motif_contains.casefold()
        saved = self.get_report(analysis_id)
        analysis = saved["report"]["analysis"]
        changes = analysis["created_hits"] + analysis["disrupted_hits"]
        filtered = [
            hit
            for hit in changes
            if (change is None or hit["change"] == change)
            and (
                motif_contains is None
                or motif_contains in hit["motif_id"].casefold()
                or motif_contains in hit["name"].casefold()
            )
        ]
        linked_variant_ids = {
            variant_id
            for hit in filtered
            for variant_id in hit["variant_ids"]
        }
        filtered_change_summary = {
            "change_count": len(filtered),
            "created_count": sum(hit["change"] == "created" for hit in filtered),
            "disrupted_count": sum(hit["change"] == "disrupted" for hit in filtered),
            "variant_link_count": sum(len(hit["variant_ids"]) for hit in filtered),
            "distinct_variant_count": len(linked_variant_ids),
            "reference_interval_count": sum(
                hit["reference_interval"] is not None for hit in filtered
            ),
            "haplotype_interval_count": sum(
                hit["haplotype_interval"] is not None for hit in filtered
            ),
        }
        return {
            "schema": "glio-noncode.sequence-haplotype-changes.v1",
            "analysis_id": analysis_id,
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
        analysis_id: str,
        *,
        change: str | None = None,
        motif_contains: str | None = None,
    ) -> str:
        """Render bounded aggregate motif changes as stable CSV."""

        page = self.page_changes(
            analysis_id,
            offset=0,
            limit=MAX_SEQUENCE_ANALYSIS_PAGE_SIZE,
            change=change,
            motif_contains=motif_contains,
        )
        if page["total_changes"] > MAX_SEQUENCE_ANALYSIS_PAGE_SIZE:
            raise StoreError("sequence motif CSV requires a narrower filter")
        fields = (
            "change",
            "motif_id",
            "name",
            "strand",
            "matched_sequence",
            "source_id",
            "reference_interval",
            "haplotype_interval",
            "variant_ids",
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(fields)
        for hit in page["changes"]:
            writer.writerow(
                (
                    hit["change"],
                    hit["motif_id"],
                    hit["name"],
                    hit["strand"],
                    hit["matched_sequence"],
                    hit["source_id"],
                    hit["reference_interval"],
                    hit["haplotype_interval"],
                    hit["variant_ids"],
                )
            )
        rendered = output.getvalue()
        if len(rendered.encode("utf-8")) > MAX_SEQUENCE_CHANGE_EXPORT_BYTES:
            raise StoreError("sequence motif CSV exceeds the export byte limit")
        return rendered


__all__ = [
    "MAX_SEQUENCE_ANALYSIS_PAGE_SIZE",
    "SEQUENCE_ANALYSIS_CATALOG_SCHEMA",
    "SEQUENCE_ANALYSIS_RECORD_SCHEMA",
    "SequenceHaplotypeStore",
    "summarize_sequence_haplotype_report",
    "validate_sequence_haplotype_report",
]
