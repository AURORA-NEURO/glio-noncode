"""Portable, record-minimized evidence bundles for D493 release evaluations."""
from __future__ import annotations

# ruff: noqa: E501, I001
import hashlib
import io
import stat
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff as diff_model
from . import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime as runtime_model
from . import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_audit as runtime_audit_model
from . import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_query as query_model
from . import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_query_audit as query_audit_model
from ._safe_persistence import atomic_write_bytes, read_bytes
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = query_audit_model.VERSION + "-evidence-archive-v1"
BOUNDARY = query_audit_model.BOUNDARY + "_evidence_archive"
ARCHIVE_PREFIX = runtime_model.RUNTIME_PREFIX + "-evidence-archive"
MANIFEST_PREFIX = ARCHIVE_PREFIX + "-manifest"
ENTRY_PREFIX = ARCHIVE_PREFIX + "-entry"
DEFAULT_ARCHIVE_ID = ARCHIVE_PREFIX
FILE_NAMES = (
    "comparison/diff-summary.json", "runtime/strict.json", "runtime/release.json",
    "audit/strict.json", "audit/release.json", "query/release.json", "audit/query.json", "report.md",
)
ARCHIVE_NAMES = ("manifest.json",) + FILE_NAMES
MAX_FILES = len(FILE_NAMES)
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 24 * 1024 * 1024
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
MEDIA_TYPES = {name: "text/markdown" if name.endswith(".md") else "application/json" for name in FILE_NAMES}
ENTRY_FIELDS = ("path", "media_type", "size", "sha256", "content_address")
MANIFEST_FIELDS = (
    "bundle_id", "version", "boundary", "diff_id", "diff_address", "strict_runtime_id",
    "strict_runtime_address", "strict_audit_address", "release_runtime_id", "release_runtime_address",
    "release_audit_address", "query_id", "query_address", "query_audit_address", "state",
    "release_ready", "files", "file_count", "total_size", "content_address",
)
ARCHIVE_FIELDS = ("manifest", "payload_addresses", "content_address")
STATES = ("ready", "blocked")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(c.isspace() for c in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 4096)
    if (not value.startswith("pending:") and not value.startswith(prefix + ":")) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    if set(value) != expected:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


class EvidenceFile:
    FIELDS = ENTRY_FIELDS

    def __init__(self, path: str, media_type: str, size: int, sha256: str, content_address: str) -> None:
        self.path = _text(path, "D494 file path", 256)
        self.media_type = _text(media_type, "D494 media type", 128)
        self.size = _count(size, "D494 file size", MAX_FILE_BYTES)
        self.sha256 = _text(sha256, "D494 SHA-256", 64)
        self.content_address = _address(content_address, "D494 file address", ENTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.path not in FILE_NAMES or self.media_type != MEDIA_TYPES[self.path]:
            raise ValidationError("D494 file path or media type is not in the fixed archive contract")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValidationError("D494 SHA-256 must be lowercase hexadecimal")
        if not self.content_address.startswith("pending:") and _address_for(self, ENTRY_PREFIX) != self.content_address:
            raise ValidationError("D494 file address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in ENTRY_FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceFile":
        value = _mapping(value, "D494 archive file")
        _strict(value, set(cls.FIELDS), "D494 archive file")
        return cls(*(value[key] for key in cls.FIELDS))


def address_file(value: EvidenceFile) -> str:
    if not isinstance(value, EvidenceFile):
        raise ValidationError("D494 addressing requires a typed archive file")
    return _address_for(value, ENTRY_PREFIX)


class EvidenceManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, bundle_id: str, version: str, boundary: str, diff_id: str, diff_address: str,
                 strict_runtime_id: str, strict_runtime_address: str, strict_audit_address: str,
                 release_runtime_id: str, release_runtime_address: str, release_audit_address: str,
                 query_id: str, query_address: str, query_audit_address: str, state: str,
                 release_ready: bool, files: Sequence[EvidenceFile | Mapping[str, Any]],
                 file_count: int, total_size: int, content_address: str) -> None:
        self.bundle_id = _label(bundle_id, "D494 bundle ID")
        self.version = _text(version, "D494 version", 512)
        self.boundary = _text(boundary, "D494 boundary", 512)
        self.diff_id = _label(diff_id, "D494 diff ID")
        self.diff_address = _address(diff_address, "D494 diff address", diff_model.DIFF_PREFIX)
        self.strict_runtime_id = _label(strict_runtime_id, "D494 strict runtime ID")
        self.strict_runtime_address = _address(strict_runtime_address, "D494 strict runtime address", runtime_model.RUNTIME_PREFIX)
        self.strict_audit_address = _address(strict_audit_address, "D494 strict audit address", runtime_audit_model.AUDIT_PREFIX)
        self.release_runtime_id = _label(release_runtime_id, "D494 release runtime ID")
        self.release_runtime_address = _address(release_runtime_address, "D494 release runtime address", runtime_model.RUNTIME_PREFIX)
        self.release_audit_address = _address(release_audit_address, "D494 release audit address", runtime_audit_model.AUDIT_PREFIX)
        self.query_id = _label(query_id, "D494 query ID")
        self.query_address = _address(query_address, "D494 query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "D494 query audit address", query_audit_model.AUDIT_PREFIX)
        self.state = _text(state, "D494 state", 16)
        self.release_ready = _bool(release_ready, "D494 release readiness")
        self.files = tuple(x if isinstance(x, EvidenceFile) else EvidenceFile.from_mapping(_mapping(x, "D494 file")) for x in _sequence(files, "D494 files", MAX_FILES))
        self.file_count = _count(file_count, "D494 file count", MAX_FILES)
        self.total_size = _count(total_size, "D494 total size", MAX_TOTAL_BYTES)
        self.content_address = _address(content_address, "D494 manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.state not in STATES or (self.state == "ready") != self.release_ready:
            raise ValidationError("D494 manifest identity or disposition does not replay")
        if self.strict_runtime_id == self.release_runtime_id or self.strict_runtime_address == self.release_runtime_address:
            raise ValidationError("D494 strict and release runtimes must be distinct")
        if tuple(item.path for item in self.files) != FILE_NAMES or self.file_count != len(FILE_NAMES):
            raise ValidationError("D494 manifest file inventory is not exact and ordered")
        if self.total_size != sum(item.size for item in self.files):
            raise ValidationError("D494 manifest total size does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address:
            raise ValidationError("D494 manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        result = {key: getattr(self, key) for key in MANIFEST_FIELDS[:-1]}
        result["files"] = [item.to_dict() for item in self.files]
        return result | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceManifest":
        value = _mapping(value, "D494 manifest")
        _strict(value, set(cls.FIELDS), "D494 manifest")
        return cls(*(value[key] for key in cls.FIELDS))


def address_manifest(value: EvidenceManifest) -> str:
    if not isinstance(value, EvidenceManifest):
        raise ValidationError("D494 addressing requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class EvidenceArchive:
    FIELDS = ARCHIVE_FIELDS

    def __init__(self, manifest: EvidenceManifest | Mapping[str, Any], payloads: Sequence[bytes], content_address: str) -> None:
        self.manifest = manifest if isinstance(manifest, EvidenceManifest) else EvidenceManifest.from_mapping(_mapping(manifest, "D494 manifest"))
        self.payloads = tuple(payloads)
        self.content_address = _address(content_address, "D494 archive address", ARCHIVE_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if len(self.payloads) != self.manifest.file_count or len(self.payloads) != len(self.manifest.files):
            raise ValidationError("D494 archive payload count does not match its manifest")
        if any(not isinstance(payload, bytes) or len(payload) > MAX_FILE_BYTES for payload in self.payloads):
            raise ValidationError("D494 archive payload is invalid or oversized")
        for entry, payload in zip(self.manifest.files, self.payloads, strict=True):
            if entry.size != len(payload) or entry.sha256 != hashlib.sha256(payload).hexdigest() or entry.content_address != address_file(entry):
                raise ValidationError("D494 archive payload does not match its manifest digest")
        if sum(map(len, self.payloads)) > MAX_TOTAL_BYTES:
            raise ValidationError("D494 archive total payload exceeds its size bound")
        if not self.content_address.startswith("pending:") and _address_for(self, ARCHIVE_PREFIX) != self.content_address:
            raise ValidationError("D494 archive address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"manifest": self.manifest.to_dict(), "payload_addresses": [x.content_address for x in self.manifest.files], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], payloads: Sequence[bytes]) -> "EvidenceArchive":
        value = _mapping(value, "D494 archive")
        _strict(value, set(cls.FIELDS), "D494 archive")
        result = cls(value["manifest"], payloads, value["content_address"])
        if tuple(value["payload_addresses"]) != tuple(x.content_address for x in result.manifest.files):
            raise ValidationError("D494 payload address list does not replay")
        return result


def address_archive(value: EvidenceArchive) -> str:
    if not isinstance(value, EvidenceArchive):
        raise ValidationError("D494 addressing requires a typed archive")
    return _address_for(value, ARCHIVE_PREFIX)


def _strict_policy(strict: runtime_model.RuntimePolicy, release: runtime_model.RuntimePolicy) -> bool:
    return (
        strict.minimum_items >= release.minimum_items
        and strict.maximum_added <= release.maximum_added
        and strict.maximum_removed <= release.maximum_removed
        and strict.maximum_changed <= release.maximum_changed
        and set(strict.allowed_directions).issubset(release.allowed_directions)
        and (not release.require_accepted or strict.require_accepted)
        and (not release.require_state_change or strict.require_state_change)
        and (not strict.allow_unchanged or release.allow_unchanged)
    )


def _query_complete(query: query_model.RuntimeQuery) -> bool:
    return (
        query.resources == query_model.RESOURCES
        and query.offset == 0
        and query.passed_filter is None
        and not query.state_filter
        and not query.severity_filter
        and not query.text_filter
        and query.returned_count == query.total_count
        and not query.truncated
    )


def _json_payload(value: Mapping[str, Any]) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def _report(summary: Mapping[str, Any], strict: runtime_model.HistoryDiffRuntime, release: runtime_model.HistoryDiffRuntime, strict_audit: Any, release_audit: Any, query: query_model.RuntimeQuery, query_audit: Any) -> str:
    lines = [
        "# D494 release evidence bundle", "",
        f"- Comparison: `{summary['diff_id']}` ({summary['diff_address']})",
        f"- Direction: **{summary['direction']}** (`{summary['state_transition']}`)",
        f"- Comparison items: {summary['added_count'] + summary['removed_count'] + summary['changed_count'] + summary['unchanged_count']} ({summary['added_count']} added, {summary['removed_count']} removed, {summary['changed_count']} changed, {summary['unchanged_count']} unchanged)",
        "", "## Policy results", "",
        f"- Strict: **{strict.state}**, {strict.passed_count}/{strict.check_count} checks; addition ceiling {strict.policy.maximum_added}.",
        f"- Release: **{release.state}**, {release.passed_count}/{release.check_count} checks; addition ceiling {release.policy.maximum_added}.",
        f"- Runtime audits: strict {strict_audit.passed_count}/{strict_audit.check_count}; release {release_audit.passed_count}/{release_audit.check_count}.",
        "", "## Release projection", "",
        f"- Query: {query.returned_count}/{query.total_count} rows; truncated: `{str(query.truncated).lower()}`.",
        f"- Query audit: {query_audit.passed_count}/{query_audit.check_count}; accepted: `{str(query_audit.accepted).lower()}`.",
        "", "Only comparison summary metadata is included; source snapshots and payloads are excluded.",
    ]
    return "\n".join(lines) + "\n"


def _make_manifest(bundle_id: str, diff: diff_model.HistoryDiff, strict: runtime_model.HistoryDiffRuntime, strict_audit: Any, release: runtime_model.HistoryDiffRuntime, release_audit: Any, query: query_model.RuntimeQuery, query_audit: Any, payloads: Sequence[bytes]) -> EvidenceManifest:
    entries = []
    for name, payload in zip(FILE_NAMES, payloads, strict=True):
        row = EvidenceFile(name, MEDIA_TYPES[name], len(payload), hashlib.sha256(payload).hexdigest(), f"pending:{ENTRY_PREFIX}")
        entries.append(EvidenceFile.from_mapping(row.to_dict() | {"content_address": address_file(row)}))
    ready = release.release_ready and strict_audit.accepted and release_audit.accepted and query_audit.accepted and _query_complete(query)
    manifest = EvidenceManifest(
        bundle_id, VERSION, BOUNDARY, diff.diff_id, diff.content_address,
        strict.runtime_id, strict.content_address, strict_audit.content_address,
        release.runtime_id, release.content_address, release_audit.content_address,
        query.query_id, query.content_address, query_audit.content_address,
        "ready" if ready else "blocked", ready, entries, len(entries),
        sum(len(payload) for payload in payloads), f"pending:{MANIFEST_PREFIX}",
    )
    return EvidenceManifest.from_mapping(manifest.to_dict() | {"content_address": address_manifest(manifest)})


def _decode_json(payload: bytes, name: str) -> Mapping[str, Any]:
    try:
        raw = payload.decode("utf-8")
        value = _strict_json_loads(raw)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValidationError(f"D494 {name} is not valid strict JSON") from error
    value = _mapping(value, f"D494 {name}")
    if raw != canonical_json(value) + "\n":
        raise ValidationError(f"D494 {name} is not canonical JSON")
    return value


def _verify_linked_audit(runtime: runtime_model.HistoryDiffRuntime, stored: Any, summary: Mapping[str, Any]) -> None:
    runtime_audit_model.verify_audit(stored)
    detached = runtime_audit_model.audit_runtime(runtime)
    for expected, actual in zip(detached.checks, stored.checks, strict=True):
        if expected.check_id not in ("diff_link", "comparison_link"):
            if expected.to_dict() != actual.to_dict():
                raise ValidationError("D494 runtime audit check does not independently replay")
            continue
        if expected.check_id == "diff_link":
            pair = canonical_json((summary["diff_id"], summary["diff_address"]))
            matches = (actual.actual, actual.expected, actual.detail) == (
                pair, pair, "runtime binds to the exact evaluated comparison",
            )
        else:
            pair = canonical_json((runtime.item_count, runtime.added_count, runtime.removed_count,
                                   runtime.changed_count, runtime.unchanged_count))
            source_pair = canonical_json((
                sum(summary[key] for key in ("added_count", "removed_count", "changed_count", "unchanged_count")),
                summary["added_count"], summary["removed_count"], summary["changed_count"],
                summary["unchanged_count"],
            ))
            matches = (actual.actual, actual.expected, actual.detail) == (
                pair, source_pair, "comparison counters and acceptance link to source diff",
            ) and pair == source_pair
        if actual.check_id != expected.check_id or not actual.passed or not matches or runtime_audit_model.address_check(actual) != actual.content_address:
            raise ValidationError("D494 runtime audit comparison link does not match the redacted summary")


def _replay_members(archive: EvidenceArchive) -> dict[str, Any]:
    docs = dict(zip(FILE_NAMES, archive.payloads, strict=True))
    summary = _decode_json(docs[FILE_NAMES[0]], "comparison summary")
    _strict(summary, set(diff_model.SUMMARY_FIELDS) | {"diff_address"}, "D494 comparison summary")
    typed_summary = diff_model.DiffSummary.from_mapping({key: summary[key] for key in diff_model.SUMMARY_FIELDS})
    if diff_model.address_summary(typed_summary) != typed_summary.content_address:
        raise ValidationError("D494 redacted comparison summary address does not replay")
    strict = runtime_model.runtime_from_mapping(_decode_json(docs["runtime/strict.json"], "strict runtime"))
    release = runtime_model.runtime_from_mapping(_decode_json(docs["runtime/release.json"], "release runtime"))
    strict_audit = runtime_audit_model.audit_from_mapping(_decode_json(docs["audit/strict.json"], "strict runtime audit"))
    release_audit = runtime_audit_model.audit_from_mapping(_decode_json(docs["audit/release.json"], "release runtime audit"))
    query = query_model.query_from_mapping(_decode_json(docs["query/release.json"], "release query"))
    query_audit = query_audit_model.audit_from_mapping(_decode_json(docs["audit/query.json"], "query audit"))
    manifest = archive.manifest
    if (summary["diff_id"], summary["diff_address"]) != (manifest.diff_id, manifest.diff_address):
        raise ValidationError("D494 summary does not link to the declared source comparison")
    shared = ("added_count", "removed_count", "changed_count", "unchanged_count", "direction", "state_transition", "accepted")
    for runtime in (strict, release):
        counts = tuple(getattr(runtime, key) for key in shared)
        source_counts = tuple(summary[key] for key in shared)
        item_count_matches = runtime.item_count == sum(source_counts[:4])
        if (runtime.diff_id, runtime.diff_address) != (manifest.diff_id, manifest.diff_address) or source_counts != counts or not item_count_matches:
            raise ValidationError("D494 runtime does not link to the redacted comparison summary")
    if (strict.runtime_id, strict.content_address, strict_audit.runtime_id, strict_audit.runtime_address, strict_audit.content_address) != (
        manifest.strict_runtime_id, manifest.strict_runtime_address, manifest.strict_runtime_id,
        manifest.strict_runtime_address, manifest.strict_audit_address,
    ):
        raise ValidationError("D494 strict runtime or audit identity does not link")
    if (release.runtime_id, release.content_address, release_audit.runtime_id, release_audit.runtime_address, release_audit.content_address) != (
        manifest.release_runtime_id, manifest.release_runtime_address, manifest.release_runtime_id,
        manifest.release_runtime_address, manifest.release_audit_address,
    ):
        raise ValidationError("D494 release runtime or audit identity does not link")
    if not _strict_policy(strict.policy, release.policy):
        raise ValidationError("D494 strict policy is not at least as restrictive as release policy")
    _verify_linked_audit(strict, strict_audit, summary)
    _verify_linked_audit(release, release_audit, summary)
    query_model.verify_query(query)
    if (query.query_id, query.content_address, query.runtime_id, query.diff_id, query.runtime_address) != (
        manifest.query_id, manifest.query_address, release.runtime_id, release.diff_id, release.content_address,
    ):
        raise ValidationError("D494 query does not link to the release runtime")
    replayed_query = query_model.query_runtime(
        release, query_id=query.query_id, resources=query.resources, state_filter=query.state_filter,
        passed_filter=query.passed_filter, severity_filter=query.severity_filter, text_filter=query.text_filter,
        offset=query.offset, limit=query.limit,
    )
    if replayed_query.content_address != query.content_address:
        raise ValidationError("D494 stored query does not replay from its runtime")
    query_audit_model.verify_audit(query_audit)
    replayed_audit = query_audit_model.audit_query(query, release)
    if (query_audit.query_id, query_audit.runtime_id, query_audit.query_address, query_audit.content_address) != (
        manifest.query_id, release.runtime_id, query.content_address, manifest.query_audit_address,
    ) or replayed_audit.content_address != query_audit.content_address:
        raise ValidationError("D494 query audit does not replay")
    try:
        report = docs["report.md"].decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError("D494 report is not valid UTF-8") from error
    if report != _report(summary, strict, release, strict_audit, release_audit, query, query_audit):
        raise ValidationError("D494 human-readable report does not replay")
    ready = release.release_ready and strict_audit.accepted and release_audit.accepted and query_audit.accepted and _query_complete(query)
    if (manifest.release_ready, manifest.state) != (ready, "ready" if ready else "blocked"):
        raise ValidationError("D494 release disposition does not replay")
    return {"summary": summary, "strict_runtime": strict, "release_runtime": release,
            "strict_audit": strict_audit, "release_audit": release_audit, "query": query, "query_audit": query_audit}


def build_archive(diff: diff_model.HistoryDiff, strict: runtime_model.HistoryDiffRuntime, strict_audit: Any,
                  release: runtime_model.HistoryDiffRuntime, release_audit: Any,
                  query: query_model.RuntimeQuery, query_audit: Any, *,
                  bundle_id: str = DEFAULT_ARCHIVE_ID) -> EvidenceArchive:
    """Build a strict/release bundle that omits raw snapshot payloads."""
    diff_model.verify_diff(diff)
    runtime_model.verify_runtime(strict, diff)
    runtime_model.verify_runtime(release, diff)
    if not _strict_policy(strict.policy, release.policy):
        raise ValidationError("D494 strict policy must be at least as restrictive as release policy")
    if strict.runtime_id == release.runtime_id or strict.content_address == release.content_address:
        raise ValidationError("D494 requires distinct strict and release runtime results")
    if runtime_audit_model.audit_runtime(strict, diff).content_address != strict_audit.content_address:
        raise ValidationError("D494 strict audit does not replay against the comparison")
    if runtime_audit_model.audit_runtime(release, diff).content_address != release_audit.content_address:
        raise ValidationError("D494 release audit does not replay against the comparison")
    query_model.verify_query(query)
    if query.runtime_address != release.content_address or query.diff_id != diff.diff_id:
        raise ValidationError("D494 query does not target the release runtime")
    if query_audit_model.audit_query(query, release).content_address != query_audit.content_address:
        raise ValidationError("D494 query audit does not replay")
    summary = diff.summary.to_dict() | {"diff_address": diff.content_address}
    payloads_by_name = {
        "comparison/diff-summary.json": _json_payload(summary),
        "runtime/strict.json": (runtime_model.runtime_json(strict) + "\n").encode("utf-8"),
        "runtime/release.json": (runtime_model.runtime_json(release) + "\n").encode("utf-8"),
        "audit/strict.json": (runtime_audit_model.audit_json(strict_audit) + "\n").encode("utf-8"),
        "audit/release.json": (runtime_audit_model.audit_json(release_audit) + "\n").encode("utf-8"),
        "query/release.json": (query_model.query_json(query) + "\n").encode("utf-8"),
        "audit/query.json": (query_audit_model.audit_json(query_audit) + "\n").encode("utf-8"),
        "report.md": _report(summary, strict, release, strict_audit, release_audit, query, query_audit).encode("utf-8"),
    }
    payloads = tuple(payloads_by_name[name] for name in FILE_NAMES)
    if any(len(item) > MAX_FILE_BYTES for item in payloads) or sum(map(len, payloads)) > MAX_TOTAL_BYTES:
        raise ValidationError("D494 archive payload exceeds its size bound")
    manifest = _make_manifest(bundle_id, diff, strict, strict_audit, release, release_audit, query, query_audit, payloads)
    pending = EvidenceArchive(manifest, payloads, f"pending:{ARCHIVE_PREFIX}")
    result = EvidenceArchive(manifest, payloads, address_archive(pending))
    return verify_archive(result)


def verify_archive(value: EvidenceArchive) -> EvidenceArchive:
    if not isinstance(value, EvidenceArchive):
        raise ValidationError("D494 verification requires a typed archive")
    value._validate()
    _replay_members(value)
    return value


def archive_manifest_json(value: EvidenceArchive) -> str:
    return canonical_json(verify_archive(value).manifest.to_dict())


def archive_bytes(value: EvidenceArchive) -> bytes:
    value = verify_archive(value)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False) as output:
        members = (("manifest.json", (canonical_json(value.manifest.to_dict()) + "\n").encode("utf-8")), *zip(FILE_NAMES, value.payloads, strict=True))
        for name, payload in members:
            info = zipfile.ZipInfo(filename=name, date_time=ZIP_EPOCH)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            output.writestr(info, payload)
    result = buffer.getvalue()
    if len(result) > MAX_ARCHIVE_BYTES:
        raise ValidationError("D494 ZIP archive exceeds its byte limit")
    return result


def persist_archive(value: EvidenceArchive, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_archive(value)
    target = Path(destination)
    if target.exists() and not overwrite:
        raise ValidationError("D494 destination already exists")
    return atomic_write_bytes(target, archive_bytes(value), field="D494 archive destination")


def _load_bytes(raw: bytes) -> EvidenceArchive:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as archive:
            infos = archive.infolist()
            if len(infos) != len(ARCHIVE_NAMES) or tuple(item.filename for item in infos) != ARCHIVE_NAMES:
                raise ValidationError("D494 ZIP member names, order, or count are not exact")
            payload_map: dict[str, bytes] = {}
            total = 0
            for info in infos:
                if (info.flag_bits & 0x1) or info.compress_type != zipfile.ZIP_STORED or info.is_dir() or "\\" in info.filename or info.filename.startswith("/"):
                    raise ValidationError("D494 ZIP contains unsupported or unsafe member metadata")
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                if unix_mode and stat.S_IFMT(unix_mode) not in (0, stat.S_IFREG):
                    raise ValidationError("D494 ZIP members must be regular files")
                if info.file_size > MAX_FILE_BYTES or info.compress_size != info.file_size:
                    raise ValidationError("D494 ZIP member exceeds bounds or is not stored")
                total += info.file_size
                if total > MAX_TOTAL_BYTES + MAX_FILE_BYTES:
                    raise ValidationError("D494 ZIP total payload exceeds bounds")
                try:
                    payload_map[info.filename] = archive.read(info)
                except (OSError, RuntimeError, zipfile.BadZipFile) as error:
                    raise ValidationError("D494 ZIP member failed CRC validation") from error
            manifest_raw = payload_map.pop("manifest.json")
    except (OSError, zipfile.BadZipFile, EOFError) as error:
        raise ValidationError("D494 input is not a valid ZIP archive") from error
    manifest = EvidenceManifest.from_mapping(_decode_json(manifest_raw, "manifest"))
    payloads = tuple(payload_map[name] for name in FILE_NAMES)
    pending = EvidenceArchive(manifest, payloads, f"pending:{ARCHIVE_PREFIX}")
    result = EvidenceArchive(manifest, payloads, address_archive(pending))
    verify_archive(result)
    if archive_bytes(result) != raw:
        raise ValidationError("D494 ZIP encoding is not canonical")
    return result


def load_archive(path: str | Path) -> EvidenceArchive:
    return _load_bytes(read_bytes(path, field="D494 archive input", max_bytes=MAX_ARCHIVE_BYTES))


def inspect_archive(value: EvidenceArchive) -> dict[str, Any]:
    value = verify_archive(value)
    return {
        "bundle_id": value.manifest.bundle_id,
        "diff_id": value.manifest.diff_id,
        "diff_address": value.manifest.diff_address,
        "state": value.manifest.state,
        "release_ready": value.manifest.release_ready,
        "file_count": value.manifest.file_count,
        "total_size": value.manifest.total_size,
        "archive_address": value.content_address,
        "manifest_address": value.manifest.content_address,
        "files": [item.to_dict() for item in value.manifest.files],
    }


def capabilities() -> dict[str, Any]:
    return {
        "public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY,
        "files": ARCHIVE_NAMES, "max_archive_bytes": MAX_ARCHIVE_BYTES,
        "max_file_bytes": MAX_FILE_BYTES,
        "features": (
            "deterministic stored ZIP bundles", "strict and release runtime and audit packaging",
            "redacted comparison summary without source snapshots or paths",
            "query and query-audit replay", "exact allowlisted members and canonical encoding",
            "SHA-256 payload manifests and content-addressed identities", "bounded safe load and atomic persistence",
        ),
        "public_boundary": {"source_paths": False, "source_snapshots": False, "payload_bytes": False, "private_metadata": False},
    }


__all__ = [
    "VERSION", "BOUNDARY", "ARCHIVE_PREFIX", "MANIFEST_PREFIX", "ENTRY_PREFIX",
    "DEFAULT_ARCHIVE_ID", "FILE_NAMES", "ARCHIVE_NAMES", "MAX_FILES", "MAX_FILE_BYTES",
    "MAX_ARCHIVE_BYTES", "MAX_TOTAL_BYTES", "ENTRY_FIELDS", "MANIFEST_FIELDS", "ARCHIVE_FIELDS",
    "EvidenceFile", "EvidenceManifest", "EvidenceArchive", "address_file", "address_manifest",
    "address_archive", "build_archive", "verify_archive", "archive_manifest_json", "archive_bytes",
    "persist_archive", "load_archive", "inspect_archive", "capabilities",
]
