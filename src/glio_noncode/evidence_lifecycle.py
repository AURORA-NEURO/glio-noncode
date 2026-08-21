"""Versioned evidence lifecycle and provenance controls.

Domain 14 keeps scientific evidence auditable after the first computation. The
module accepts source citations, retains malformed input as quarantine issues,
and builds immutable graph snapshots whose active view is derived from their
append-only history. Lineage, citation coverage, contradictions, and
out-of-domain requests remain explicit diagnostics. The integrity envelope is
content-addressed for reproducibility; it is not a cryptographic identity
signature and it does not authorize a clinical or treatment conclusion.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .models import EvidenceClaim, EvidenceState
from .serialization import content_hash, hash_bytes, jsonable, require_non_empty, utc_now


class LifecycleState(StrEnum):
    """State of a versioned claim or graph evaluation."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    ABSTAINED = "abstained"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"
    SUPERSEDED = "superseded"
    ABSENT = "absent"
    MEASURED_NEGATIVE = "measured_negative"


class DisagreementState(StrEnum):
    """State used by the disagreement report, separate from claim state."""

    CLEAR = "clear"
    CONTRADICTORY = "contradictory"
    INCOMPLETE = "incomplete"
    OUT_OF_DOMAIN = "out_of_domain"


@dataclass(frozen=True, slots=True)
class CitationIssue:
    """A malformed or quarantined source-citation row."""

    row_number: int
    code: str
    message: str
    raw_hash: str
    raw_record: Mapping[str, Any] = field(default_factory=dict)
    quarantined: bool = True

    def __post_init__(self) -> None:
        if self.row_number < 1:
            raise ValidationError("citation issue row_number must be positive")
        require_non_empty(self.code, "citation issue code")
        require_non_empty(self.message, "citation issue message")
        require_non_empty(self.raw_hash, "citation issue raw_hash")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceCitation:
    """A source citation with version, checksum, and raw-record provenance."""

    citation_id: str
    source_id: str
    source_uri: str
    title: str
    version: str
    raw_hash: str
    citation_text: str
    retrieved_at: str
    context_key: str | None = None
    source_checksum: str | None = None
    raw_record: Mapping[str, Any] = field(default_factory=dict)
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "citation_id",
            "source_id",
            "source_uri",
            "title",
            "version",
            "raw_hash",
            "citation_text",
            "retrieved_at",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.context_key is not None and not self.context_key.strip():
            raise ValidationError("citation context_key cannot be blank")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        fallback_source_id: str,
        fallback_version: str,
        fallback_row_number: int,
        raw_hash_value: str | None = None,
    ) -> EvidenceCitation:
        """Parse one normalized row while retaining unknown fields."""

        if not isinstance(raw, Mapping):
            raise ValidationError("citation row must be a mapping")
        known = {
            "citation_id",
            "id",
            "source_id",
            "source_uri",
            "uri",
            "url",
            "canonical_url",
            "title",
            "version",
            "source_version",
            "raw_hash",
            "checksum",
            "source_checksum",
            "citation",
            "citation_text",
            "retrieved_at",
            "context_key",
        }
        source_id = str(raw.get("source_id", fallback_source_id))
        version = str(raw.get("version", raw.get("source_version", fallback_version)))
        raw_hash = str(raw_hash_value or raw.get("raw_hash") or content_hash(dict(raw)))
        uri = str(
            raw.get("source_uri", raw.get("uri", raw.get("url", raw.get("canonical_url", ""))))
        )
        citation_text = str(raw.get("citation_text", raw.get("citation", "")))
        retrieved_at = str(raw.get("retrieved_at", utc_now().isoformat()))
        attributes = {str(key): value for key, value in raw.items() if str(key) not in known}
        attributes.setdefault("input_row_number", fallback_row_number)
        return cls(
            citation_id=str(
                raw.get("citation_id", raw.get("id", f"{source_id}:{fallback_row_number}"))
            ),
            source_id=source_id,
            source_uri=uri,
            title=str(raw.get("title", "")),
            version=version,
            raw_hash=raw_hash,
            citation_text=citation_text,
            retrieved_at=retrieved_at,
            context_key=(None if raw.get("context_key") in (None, "") else str(raw["context_key"])),
            source_checksum=(
                None
                if raw.get("source_checksum", raw.get("checksum")) in (None, "")
                else str(raw.get("source_checksum", raw.get("checksum")))
            ),
            raw_record=dict(raw),
            attributes=attributes,
        )

    @property
    def content_address(self) -> str:
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CitationBatch:
    """Parsed citations plus lossless accounting for rows that were rejected."""

    source_id: str
    source_version: str
    input_hash: str
    citations: tuple[EvidenceCitation, ...]
    issues: tuple[CitationIssue, ...]
    content_address: str

    @property
    def state(self) -> LifecycleState:
        if not self.citations:
            return LifecycleState.ABSTAINED
        return LifecycleState.PARTIAL if self.issues else LifecycleState.SUPPORTED

    @property
    def quarantined_count(self) -> int:
        return sum(issue.quarantined for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "state": self.state.value,
            "quarantined_count": self.quarantined_count,
        }


class CitationResolver:
    """Resolve TSV or JSON citation manifests without discarding bad rows."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
    ) -> CitationBatch:
        require_non_empty(source_id, "source_id")
        require_non_empty(source_version, "source_version")
        selected = (input_format or "").lower().strip()
        if not selected:
            selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
        if selected == "json":
            return self.parse_json(text, source_id=source_id, source_version=source_version)
        if selected not in {"tsv", "csv"}:
            raise ValidationError(f"unsupported citation input format: {selected}")
        reader = csv.DictReader(io.StringIO(text), delimiter="\t" if selected == "tsv" else ",")
        if reader.fieldnames is None:
            issue = CitationIssue(
                1, "missing_header", "citation table has no header", hash_bytes(text.encode())
            )
            return self._batch(source_id, source_version, text, (), (issue,))
        rows: list[tuple[int, Mapping[str, Any], str]] = []
        lines = text.splitlines()
        for row_number, row in enumerate(reader, start=2):
            raw_line = lines[row_number - 1] if row_number - 1 < len(lines) else ""
            rows.append((row_number, row, hash_bytes(raw_line.encode("utf-8"))))
        return self._resolve_rows(source_id, source_version, text, rows)

    def parse_json(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
    ) -> CitationBatch:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            issue = CitationIssue(
                1,
                "invalid_json",
                f"citation JSON could not be decoded: {exc.msg}",
                hash_bytes(text.encode("utf-8")),
            )
            return self._batch(source_id, source_version, text, (), (issue,))
        if isinstance(payload, Mapping):
            raw_rows = payload.get("citations", payload.get("records"))
            if raw_rows is None:
                raw_rows = [payload]
        else:
            raw_rows = payload
        if not isinstance(raw_rows, list):
            issue = CitationIssue(
                1,
                "invalid_shape",
                "citation JSON must be a record object or a list of records",
                content_hash(payload),
            )
            return self._batch(source_id, source_version, text, (), (issue,))
        rows = tuple(
            (
                index,
                item,
                content_hash(item) if isinstance(item, Mapping) else content_hash({"raw": item}),
            )
            for index, item in enumerate(raw_rows, start=1)
        )
        return self._resolve_rows(source_id, source_version, text, rows)

    def _resolve_rows(
        self,
        source_id: str,
        source_version: str,
        text: str,
        rows: Iterable[tuple[int, Mapping[str, Any], str]],
    ) -> CitationBatch:
        citations: list[EvidenceCitation] = []
        issues: list[CitationIssue] = []
        seen: set[str] = set()
        for row_number, row, raw_hash in rows:
            if not isinstance(row, Mapping):
                issues.append(
                    CitationIssue(
                        row_number, "row_not_object", "citation row is not an object", raw_hash
                    )
                )
                continue
            missing = tuple(
                name
                for name, aliases in (
                    ("source_uri", ("source_uri", "uri", "url", "canonical_url")),
                    ("title", ("title",)),
                    ("citation_text", ("citation_text", "citation")),
                )
                if not any(str(row.get(alias, "")).strip() for alias in aliases)
            )
            citation_id = str(row.get("citation_id", row.get("id", f"{source_id}:{row_number}")))
            if missing:
                issues.append(
                    CitationIssue(
                        row_number,
                        "missing_required_field",
                        f"citation is missing required fields: {', '.join(missing)}",
                        raw_hash,
                        dict(row),
                    )
                )
                continue
            if citation_id in seen:
                issues.append(
                    CitationIssue(
                        row_number,
                        "duplicate_citation_id",
                        f"citation ID is duplicated: {citation_id}",
                        raw_hash,
                        dict(row),
                    )
                )
                continue
            try:
                citation = EvidenceCitation.from_mapping(
                    row,
                    fallback_source_id=source_id,
                    fallback_version=source_version,
                    fallback_row_number=row_number,
                    raw_hash_value=raw_hash,
                )
            except ValidationError as exc:
                issues.append(
                    CitationIssue(row_number, "invalid_citation", str(exc), raw_hash, dict(row))
                )
                continue
            seen.add(citation.citation_id)
            citations.append(citation)
        return self._batch(source_id, source_version, text, tuple(citations), tuple(issues))

    @staticmethod
    def _batch(
        source_id: str,
        source_version: str,
        text: str,
        citations: tuple[EvidenceCitation, ...],
        issues: tuple[CitationIssue, ...],
    ) -> CitationBatch:
        body = {
            "source_id": source_id,
            "source_version": source_version,
            "input_hash": hash_bytes(text.encode("utf-8")),
            "citations": citations,
            "issues": issues,
        }
        return CitationBatch(
            source_id=source_id,
            source_version=source_version,
            input_hash=body["input_hash"],
            citations=citations,
            issues=issues,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class VersionedEvidenceClaim:
    """Append-only typed claim with explicit source and lineage references."""

    claim_id: str
    edge_id: str
    context_key: str
    state: LifecycleState
    support: float | None
    confidence: float
    claim_type: str
    summary: str
    source_ids: tuple[str, ...]
    source_versions: Mapping[str, str]
    raw_hash: str
    parent_claim_ids: tuple[str, ...] = ()
    supersedes: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: utc_now().isoformat())

    def __post_init__(self) -> None:
        for name in (
            "claim_id",
            "edge_id",
            "context_key",
            "claim_type",
            "summary",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValidationError("versioned claim requires at least one source ID")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("versioned claim source IDs must be unique")
        if self.support is not None and not 0.0 <= self.support <= 1.0:
            raise ValidationError("claim support must be between 0 and 1")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationError("claim confidence must be between 0 and 1")
        if self.supersedes == self.claim_id:
            raise ValidationError("a claim cannot supersede itself")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        fallback_id: str,
        context_key: str,
    ) -> VersionedEvidenceClaim:
        if not isinstance(raw, Mapping):
            raise ValidationError("claim input must be a mapping")
        source_values = raw.get("source_ids", raw.get("source_id", ("declared_input",)))
        if isinstance(source_values, str):
            source_ids = (source_values,)
        else:
            source_ids = tuple(str(item) for item in source_values)
        support_raw = raw.get("support")
        return cls(
            claim_id=str(raw.get("claim_id", raw.get("evidence_id", fallback_id))),
            edge_id=str(raw.get("edge_id", "")),
            context_key=str(raw.get("context_key", context_key)),
            state=LifecycleState(str(raw.get("state", LifecycleState.SUPPORTED.value))),
            support=None if support_raw is None else float(support_raw),
            confidence=float(raw.get("confidence", 1.0)),
            claim_type=str(raw.get("claim_type", raw.get("channel", "unspecified"))),
            summary=str(raw.get("summary", "")),
            source_ids=source_ids,
            source_versions={
                str(key): str(value) for key, value in dict(raw.get("source_versions", {})).items()
            },
            raw_hash=str(raw.get("raw_hash", content_hash(dict(raw)))),
            parent_claim_ids=tuple(str(item) for item in raw.get("parent_claim_ids", ())),
            supersedes=(None if raw.get("supersedes") is None else str(raw["supersedes"])),
            attributes=dict(raw.get("attributes", {})),
            created_at=str(raw.get("created_at", utc_now().isoformat())),
        )

    @classmethod
    def from_evidence_claim(cls, claim: EvidenceClaim) -> VersionedEvidenceClaim:
        state_map = {
            EvidenceState.SUPPORTED: LifecycleState.SUPPORTED,
            EvidenceState.MEASURED_NEGATIVE: LifecycleState.MEASURED_NEGATIVE,
            EvidenceState.CONTRADICTORY: LifecycleState.CONTRADICTORY,
            EvidenceState.ABSENT: LifecycleState.ABSENT,
            EvidenceState.OUT_OF_DOMAIN: LifecycleState.OUT_OF_DOMAIN,
            EvidenceState.ABSTAINED: LifecycleState.ABSTAINED,
            EvidenceState.UNSUPPORTED: LifecycleState.PARTIAL,
        }
        return cls(
            claim_id=claim.evidence_id,
            edge_id=claim.edge_id,
            context_key=claim.context.key,
            state=state_map[claim.state],
            support=claim.score,
            confidence=claim.confidence,
            claim_type=claim.channel,
            summary=claim.summary,
            source_ids=(claim.source_id,),
            source_versions={claim.source_id: claim.context.source_version},
            raw_hash=content_hash(claim.to_dict()),
            parent_claim_ids=claim.depends_on,
            supersedes=claim.supersedes,
            attributes=dict(claim.payload),
            created_at=claim.created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceGraphSnapshot:
    """Immutable versioned graph view with replay and integrity diagnostics."""

    graph_id: str
    graph_version: int
    context_key: str
    claims: tuple[VersionedEvidenceClaim, ...]
    citations: tuple[EvidenceCitation, ...]
    active_claim_ids: tuple[str, ...]
    superseded_claim_ids: tuple[str, ...]
    orphan_claim_ids: tuple[str, ...]
    context_mismatch_claim_ids: tuple[str, ...]
    contradictory_edge_ids: tuple[str, ...]
    state: LifecycleState
    warnings: tuple[str, ...]
    content_address: str

    def active_claims(self) -> tuple[VersionedEvidenceClaim, ...]:
        active = set(self.active_claim_ids)
        return tuple(claim for claim in self.claims if claim.claim_id in active)

    def claims_for_edge(
        self, edge_id: str, *, active_only: bool = False
    ) -> tuple[VersionedEvidenceClaim, ...]:
        claims = tuple(claim for claim in self.claims if claim.edge_id == edge_id)
        if not active_only:
            return claims
        active = set(self.active_claim_ids)
        return tuple(claim for claim in claims if claim.claim_id in active)

    def citation_matches(self, source_id: str) -> tuple[EvidenceCitation, ...]:
        return tuple(
            citation
            for citation in self.citations
            if citation.citation_id == source_id or citation.source_id == source_id
        )

    def replay(self) -> EvidenceGraphSnapshot:
        """Rebuild this exact snapshot from retained history and citations."""

        return VersionedEvidenceGraphConstructor().construct(
            self.claims,
            citations=self.citations,
            graph_id=self.graph_id,
            context_key=self.context_key,
            graph_version=self.graph_version,
        )

    def append(
        self,
        claim: VersionedEvidenceClaim,
        *,
        citations: Iterable[EvidenceCitation] = (),
    ) -> EvidenceGraphSnapshot:
        """Return a new snapshot without mutating any prior version."""

        if claim.context_key != self.context_key:
            raise ValidationError("claim context does not match graph context")
        merged = {citation.citation_id: citation for citation in self.citations}
        for citation in citations:
            if citation.citation_id in merged and merged[citation.citation_id] != citation:
                raise ValidationError(
                    f"citation ID already exists with different content: {citation.citation_id}"
                )
            merged[citation.citation_id] = citation
        return VersionedEvidenceGraphConstructor().construct(
            self.claims + (claim,),
            citations=tuple(merged.values()),
            graph_id=self.graph_id,
            context_key=self.context_key,
            graph_version=self.graph_version + 1,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class VersionedEvidenceGraphConstructor:
    """Build immutable graph snapshots while preserving every historical claim."""

    def construct(
        self,
        claims: Iterable[VersionedEvidenceClaim],
        *,
        citations: Iterable[EvidenceCitation] = (),
        graph_id: str = "evidence-graph",
        context_key: str,
        graph_version: int = 1,
    ) -> EvidenceGraphSnapshot:
        require_non_empty(graph_id, "graph_id")
        require_non_empty(context_key, "context_key")
        if graph_version < 1:
            raise ValidationError("graph_version must be positive")
        claim_values = tuple(claims)
        citation_values = tuple(citations)
        claim_ids = tuple(claim.claim_id for claim in claim_values)
        citation_ids = tuple(citation.citation_id for citation in citation_values)
        if len(claim_ids) != len(set(claim_ids)):
            raise ValidationError("claim IDs must be unique")
        if len(citation_ids) != len(set(citation_ids)):
            raise ValidationError("citation IDs must be unique")
        mismatched = tuple(
            claim.claim_id for claim in claim_values if claim.context_key != context_key
        )
        if mismatched:
            raise ValidationError("all claims must share the graph context")
        known = set(claim_ids)
        citation_index: dict[str, EvidenceCitation] = {}
        for citation in citation_values:
            citation_index[citation.citation_id] = citation
            citation_index.setdefault(citation.source_id, citation)
        orphan: set[str] = set()
        context_mismatch: set[str] = set()
        for claim in claim_values:
            if any(parent not in known for parent in claim.parent_claim_ids):
                orphan.add(claim.claim_id)
            if claim.supersedes is not None and claim.supersedes not in known:
                orphan.add(claim.claim_id)
            if any(source_id not in citation_index for source_id in claim.source_ids):
                orphan.add(claim.claim_id)
            for source_id in claim.source_ids:
                citation = citation_index.get(source_id)
                if citation is not None and citation.context_key not in (None, context_key):
                    context_mismatch.add(claim.claim_id)
        superseded = tuple(
            sorted({claim.supersedes for claim in claim_values if claim.supersedes in known})
        )
        superseded_set = set(superseded)
        active_ids = tuple(claim_id for claim_id in claim_ids if claim_id not in superseded_set)
        active = tuple(claim for claim in claim_values if claim.claim_id in set(active_ids))
        edge_states: dict[str, set[LifecycleState]] = defaultdict(set)
        edge_values: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for claim in active:
            edge_states[claim.edge_id].add(claim.state)
            value = claim.attributes.get("claim_value", claim.attributes.get("value"))
            if value is not None:
                edge_values[claim.edge_id][str(value)].append(claim.claim_id)
        contradictory = tuple(
            sorted(
                edge_id
                for edge_id, states in edge_states.items()
                if LifecycleState.CONTRADICTORY in states
                or (
                    LifecycleState.SUPPORTED in states
                    and (
                        LifecycleState.MEASURED_NEGATIVE in states
                        or LifecycleState.ABSENT in states
                    )
                )
                or len(edge_values.get(edge_id, {})) > 1
            )
        )
        if not claim_values:
            state = LifecycleState.ABSTAINED
        elif not active:
            state = LifecycleState.SUPERSEDED
        elif orphan:
            state = LifecycleState.PARTIAL
        elif context_mismatch:
            state = LifecycleState.OUT_OF_DOMAIN
        elif contradictory:
            state = LifecycleState.CONTRADICTORY
        elif any(claim.state == LifecycleState.OUT_OF_DOMAIN for claim in active):
            state = LifecycleState.OUT_OF_DOMAIN
        elif any(claim.state == LifecycleState.ABSTAINED for claim in active):
            state = LifecycleState.ABSTAINED
        elif all(claim.state == LifecycleState.SUPPORTED for claim in active):
            state = LifecycleState.SUPPORTED
        elif all(
            claim.state in {LifecycleState.ABSENT, LifecycleState.MEASURED_NEGATIVE}
            for claim in active
        ):
            state = LifecycleState.ABSENT
        else:
            state = LifecycleState.PARTIAL
        warnings: list[str] = []
        if orphan:
            warnings.append("claims with missing lineage or citations were retained for review")
        if context_mismatch:
            warnings.append("citation context does not match the graph context")
        if contradictory:
            warnings.append("contradictory active claims remain attached to one or more edges")
        if superseded:
            warnings.append(
                "superseded claims remain in history and are excluded only from active views"
            )
        body = {
            "graph_id": graph_id,
            "graph_version": graph_version,
            "context_key": context_key,
            "claims": claim_values,
            "citations": citation_values,
            "active_claim_ids": active_ids,
            "superseded_claim_ids": superseded,
            "orphan_claim_ids": tuple(sorted(orphan)),
            "context_mismatch_claim_ids": tuple(sorted(context_mismatch)),
            "contradictory_edge_ids": contradictory,
            "state": state,
        }
        return EvidenceGraphSnapshot(
            graph_id=graph_id,
            graph_version=graph_version,
            context_key=context_key,
            claims=claim_values,
            citations=citation_values,
            active_claim_ids=active_ids,
            superseded_claim_ids=superseded,
            orphan_claim_ids=tuple(sorted(orphan)),
            context_mismatch_claim_ids=tuple(sorted(context_mismatch)),
            contradictory_edge_ids=contradictory,
            state=state,
            warnings=tuple(warnings),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class EdgeValidationReport:
    """Validation result for one graph edge with no aggregate claim score."""

    edge_id: str
    context_key: str
    state: LifecycleState
    claim_ids: tuple[str, ...]
    active_claim_ids: tuple[str, ...]
    orphan_claim_ids: tuple[str, ...]
    missing_source_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    contradiction: bool
    uncertainty: float
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.edge_id, "edge_id")
        require_non_empty(self.context_key, "context_key")
        if not 0.0 <= self.uncertainty <= 1.0:
            raise ValidationError("edge validation uncertainty must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ClaimEvidenceEdgeValidator:
    """Check edge integrity, context, source coverage, and claim disagreement."""

    def validate(
        self,
        graph: EvidenceGraphSnapshot,
        edge_id: str,
        *,
        expected_context_key: str | None = None,
    ) -> EdgeValidationReport:
        require_non_empty(edge_id, "edge_id")
        claims = graph.claims_for_edge(edge_id)
        active = graph.claims_for_edge(edge_id, active_only=True)
        all_source_ids = tuple(
            sorted({source_id for claim in claims for source_id in claim.source_ids})
        )
        missing_sources = tuple(
            source_id for source_id in all_source_ids if not graph.citation_matches(source_id)
        )
        orphan_ids = tuple(
            claim.claim_id for claim in claims if claim.claim_id in graph.orphan_claim_ids
        )
        warnings: list[str] = []
        if expected_context_key is not None and expected_context_key != graph.context_key:
            warnings.append("requested edge context does not match graph context")
        if not claims:
            state = LifecycleState.ABSTAINED
        elif expected_context_key is not None and expected_context_key != graph.context_key:
            state = LifecycleState.OUT_OF_DOMAIN
        elif not active:
            state = LifecycleState.SUPERSEDED
        elif any(claim.claim_id in graph.context_mismatch_claim_ids for claim in active):
            state = LifecycleState.OUT_OF_DOMAIN
        elif edge_id in graph.contradictory_edge_ids:
            state = LifecycleState.CONTRADICTORY
        elif orphan_ids or missing_sources:
            state = LifecycleState.PARTIAL
        elif any(claim.state == LifecycleState.OUT_OF_DOMAIN for claim in active):
            state = LifecycleState.OUT_OF_DOMAIN
        elif any(claim.state == LifecycleState.ABSTAINED for claim in active):
            state = LifecycleState.ABSTAINED
        elif all(claim.state == LifecycleState.SUPPORTED for claim in active):
            state = LifecycleState.SUPPORTED
        elif all(
            claim.state in {LifecycleState.ABSENT, LifecycleState.MEASURED_NEGATIVE}
            for claim in active
        ):
            state = LifecycleState.ABSENT
        else:
            state = LifecycleState.PARTIAL
        if orphan_ids:
            warnings.append("one or more claims have missing lineage or citation references")
        if missing_sources:
            warnings.append("one or more claim sources lack a resolved citation")
        if edge_id in graph.contradictory_edge_ids:
            warnings.append("conflicting claims are reported separately; no value was averaged")
        confidences = [claim.confidence for claim in active]
        uncertainty = (
            1.0 if not confidences else round(1.0 - sum(confidences) / len(confidences), 6)
        )
        body = {
            "edge_id": edge_id,
            "context_key": graph.context_key,
            "state": state,
            "claim_ids": tuple(claim.claim_id for claim in claims),
            "active_claim_ids": tuple(claim.claim_id for claim in active),
            "orphan_claim_ids": orphan_ids,
            "missing_source_ids": missing_sources,
            "source_ids": all_source_ids,
            "contradiction": edge_id in graph.contradictory_edge_ids,
            "uncertainty": uncertainty,
            "warnings": tuple(warnings),
        }
        return EdgeValidationReport(
            edge_id=edge_id,
            context_key=graph.context_key,
            state=state,
            claim_ids=body["claim_ids"],
            active_claim_ids=body["active_claim_ids"],
            orphan_claim_ids=orphan_ids,
            missing_source_ids=missing_sources,
            source_ids=all_source_ids,
            contradiction=edge_id in graph.contradictory_edge_ids,
            uncertainty=uncertainty,
            warnings=tuple(warnings),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class DisagreementRecord:
    """One edge-level disagreement without collapsing competing observations."""

    edge_id: str
    state: DisagreementState
    claim_ids: tuple[str, ...]
    positive_claim_ids: tuple[str, ...]
    negative_claim_ids: tuple[str, ...]
    value_groups: Mapping[str, tuple[str, ...]]
    source_ids: tuple[str, ...]
    unresolved: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DisagreementReport:
    """Complete edge disagreement inventory for one graph snapshot."""

    graph_id: str
    graph_version: int
    records: tuple[DisagreementRecord, ...]
    contradictory_edge_ids: tuple[str, ...]
    unresolved_edge_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ContradictionDisagreementTracker:
    """Track disagreement by edge, source, state, and declared claim value."""

    def track(
        self,
        graph: EvidenceGraphSnapshot,
        *,
        edge_ids: Iterable[str] = (),
    ) -> DisagreementReport:
        selected = tuple(sorted(set(edge_ids))) or tuple(
            sorted({claim.edge_id for claim in graph.active_claims()})
        )
        records: list[DisagreementRecord] = []
        for edge_id in selected:
            claims = graph.claims_for_edge(edge_id, active_only=True)
            positive = tuple(
                claim.claim_id for claim in claims if claim.state == LifecycleState.SUPPORTED
            )
            negative = tuple(
                claim.claim_id
                for claim in claims
                if claim.state in {LifecycleState.MEASURED_NEGATIVE, LifecycleState.ABSENT}
            )
            values: dict[str, list[str]] = defaultdict(list)
            for claim in claims:
                value = claim.attributes.get("claim_value", claim.attributes.get("value"))
                if value is not None:
                    values[str(value)].append(claim.claim_id)
            value_groups = {key: tuple(value) for key, value in sorted(values.items())}
            sources = tuple(
                sorted({source_id for claim in claims for source_id in claim.source_ids})
            )
            if any(claim.state == LifecycleState.OUT_OF_DOMAIN for claim in claims):
                state = DisagreementState.OUT_OF_DOMAIN
                rationale = "At least one active claim is out of the declared graph domain."
            elif edge_id in graph.contradictory_edge_ids:
                state = DisagreementState.CONTRADICTORY
                rationale = (
                    "Positive, negative, contradictory, or non-matching value claims coexist."
                )
            elif not claims or any(claim.claim_id in graph.orphan_claim_ids for claim in claims):
                state = DisagreementState.INCOMPLETE
                rationale = "The edge lacks active claims or has unresolved provenance/lineage."
            else:
                state = DisagreementState.CLEAR
                rationale = (
                    "Active claims agree on state and declared value, with resolved provenance."
                )
            records.append(
                DisagreementRecord(
                    edge_id=edge_id,
                    state=state,
                    claim_ids=tuple(claim.claim_id for claim in claims),
                    positive_claim_ids=positive,
                    negative_claim_ids=negative,
                    value_groups=value_groups,
                    source_ids=sources,
                    unresolved=state != DisagreementState.CLEAR,
                    rationale=rationale,
                )
            )
        contradictory = tuple(
            record.edge_id for record in records if record.state == DisagreementState.CONTRADICTORY
        )
        unresolved = tuple(record.edge_id for record in records if record.unresolved)
        body = {
            "graph_id": graph.graph_id,
            "graph_version": graph.graph_version,
            "records": records,
            "contradictory_edge_ids": contradictory,
            "unresolved_edge_ids": unresolved,
        }
        return DisagreementReport(
            graph_id=graph.graph_id,
            graph_version=graph.graph_version,
            records=tuple(records),
            contradictory_edge_ids=contradictory,
            unresolved_edge_ids=unresolved,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class ResearchEvidenceDossier:
    """Research-only release envelope with a deterministic integrity digest."""

    dossier_id: str
    graph_id: str
    graph_version: int
    graph_address: str
    graph_state: LifecycleState
    edge_reports: tuple[EdgeValidationReport, ...]
    disagreement: DisagreementReport
    citation_ids: tuple[str, ...]
    release_state: str
    integrity_digest: str
    integrity_method: str
    research_use_only: bool
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.dossier_id, "dossier_id")
        require_non_empty(self.graph_id, "graph_id")
        require_non_empty(self.integrity_digest, "integrity_digest")
        if not self.research_use_only:
            raise ValidationError("research evidence dossier must be research_use_only")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EvidenceDossierPublisher:
    """Package graph checks without silently promoting unresolved evidence."""

    def __init__(
        self,
        validator: ClaimEvidenceEdgeValidator | None = None,
        tracker: ContradictionDisagreementTracker | None = None,
    ) -> None:
        self.validator = validator or ClaimEvidenceEdgeValidator()
        self.tracker = tracker or ContradictionDisagreementTracker()

    def publish(
        self,
        graph: EvidenceGraphSnapshot,
        *,
        edge_ids: Iterable[str] = (),
        dossier_id: str | None = None,
    ) -> ResearchEvidenceDossier:
        selected = tuple(sorted(set(edge_ids))) or tuple(
            sorted({claim.edge_id for claim in graph.claims})
        )
        reports = tuple(self.validator.validate(graph, edge_id) for edge_id in selected)
        disagreement = self.tracker.track(graph, edge_ids=selected)
        warnings = list(graph.warnings)
        warnings.extend(message for report in reports for message in report.warnings)
        if graph.state != LifecycleState.SUPPORTED:
            warnings.append("graph is not fully supported; dossier remains review-required")
        if disagreement.unresolved_edge_ids:
            warnings.append("unresolved disagreement requires explicit review")
        body = {
            "graph_id": graph.graph_id,
            "graph_version": graph.graph_version,
            "graph_address": graph.content_address,
            "edge_reports": reports,
            "disagreement": disagreement,
            "citation_ids": tuple(citation.citation_id for citation in graph.citations),
        }
        integrity = content_hash(body)
        dossier_body = body | {
            "integrity_digest": integrity,
            "release_state": "review_required",
            "research_use_only": True,
        }
        return ResearchEvidenceDossier(
            dossier_id=dossier_id or "evidence-dossier-" + integrity.split(":", 1)[1][:20],
            graph_id=graph.graph_id,
            graph_version=graph.graph_version,
            graph_address=graph.content_address,
            graph_state=graph.state,
            edge_reports=reports,
            disagreement=disagreement,
            citation_ids=tuple(citation.citation_id for citation in graph.citations),
            release_state="review_required",
            integrity_digest=integrity,
            integrity_method="sha256-content-addressed-integrity-only",
            research_use_only=True,
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(dossier_body),
        )
