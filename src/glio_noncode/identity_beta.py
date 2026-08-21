"""Deep variant identity and custody-governance contracts.

Domain 01's first beta layer normalizes individual variants. This module
handles the cross-record problems that appear once multiple sources, aliases,
samples, and processing batches are present:

* equivalence resolution compares normalized build/contig/interval/allele
  identities while preserving every source record;
* duplicate and alias reconciliation groups exact identities, exposes alias
  collisions, and never selects a preferred record implicitly;
* batch/sample identity checks detect missing IDs and cross-subject reuse;
* chain-of-custody capture records immutable artifact transitions, hashes,
  event order, and broken-link diagnostics.

The outputs are research data-governance artifacts. They do not assert sample
provenance beyond the supplied receipts and do not replace institutional chain
of-custody, consent, or privacy controls.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .identity import normalize_allele, normalize_chromosome
from .models import VariantIdentity
from .serialization import content_hash, jsonable, require_non_empty


class IdentityBetaState(StrEnum):
    """State vocabulary shared by identity and custody projections."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    ABSENT = "absent"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class VariantIdentityRecord:
    """One source-qualified variant record presented to identity resolution."""

    record_id: str
    variant: VariantIdentity
    source_id: str
    source_version: str
    raw_hash: str
    aliases: tuple[str, ...] = ()
    sample_id: str | None = None
    batch_id: str | None = None
    context_key: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("record_id", "source_id", "source_version", "raw_hash"):
            require_non_empty(getattr(self, name), name)
        if len(self.aliases) != len(set(self.aliases)):
            raise ValidationError("variant identity aliases must be unique")
        for name in ("sample_id", "batch_id", "context_key"):
            value = getattr(self, name)
            if value is not None and not value.strip():
                raise ValidationError(f"variant identity {name} cannot be blank")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> VariantIdentityRecord:
        raw_variant = value.get("variant", value)
        if not isinstance(raw_variant, Mapping):
            raise ValidationError("variant identity record variant must be an object")
        variant = VariantIdentity.from_dict(raw_variant)
        return cls(
            record_id=str(value.get("record_id", value.get("id", variant.variant_id))),
            variant=variant,
            source_id=str(value.get("source_id", "unspecified")),
            source_version=str(value.get("source_version", value.get("version", "unspecified"))),
            raw_hash=str(value.get("raw_hash", content_hash(value))),
            aliases=tuple(str(item) for item in value.get("aliases", ())),
            sample_id=str(value["sample_id"]) if value.get("sample_id") is not None else None,
            batch_id=str(value["batch_id"]) if value.get("batch_id") is not None else None,
            context_key=str(value["context_key"]) if value.get("context_key") is not None else None,
            attributes=dict(value.get("attributes", {})),
        )

    @property
    def equivalence_key(self) -> str:
        return normalized_variant_key(self.variant)

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        payload["equivalence_key"] = self.equivalence_key
        return payload


@dataclass(frozen=True, slots=True)
class VariantEquivalenceMatch:
    """Resolution result for one query identity or alias."""

    query: str
    state: IdentityBetaState
    equivalence_key: str | None
    record_ids: tuple[str, ...]
    variant_ids: tuple[str, ...]
    aliases: tuple[str, ...]
    source_ids: tuple[str, ...]
    methods: tuple[str, ...]
    competing_keys: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.query, "equivalence query")
        for name in (
            "record_ids",
            "variant_ids",
            "aliases",
            "source_ids",
            "methods",
            "competing_keys",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValidationError(f"equivalence {name} must be unique")

    @property
    def is_unique(self) -> bool:
        return self.state == IdentityBetaState.SUPPORTED and len(self.record_ids) == 1

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class VariantEquivalenceResolver:
    """Resolve canonical keys, normalized notation, and explicit aliases."""

    def resolve(
        self,
        records: Iterable[VariantIdentityRecord | Mapping[str, Any]],
        query: str,
        *,
        genome_build: str | None = None,
        context_key: str | None = None,
    ) -> VariantEquivalenceMatch:
        require_non_empty(query, "equivalence query")
        values = tuple(_coerce_identity_record(value) for value in records)
        scoped = tuple(
            value
            for value in values
            if (genome_build is None or value.variant.genome_build == genome_build)
            and (context_key is None or value.context_key == context_key)
        )
        out_of_scope = tuple(value for value in values if value not in scoped)
        normalized_query = _normalize_query(query)
        exact = tuple(
            value
            for value in scoped
            if normalized_query
            in {
                value.equivalence_key.casefold(),
                normalized_variant_id(value.variant),
                *(_normalize_query(alias) for alias in value.aliases),
            }
        )
        if not exact:
            same_alias_other_scope = tuple(
                value
                for value in out_of_scope
                if normalized_query
                in {
                    value.equivalence_key.casefold(),
                    normalized_variant_id(value.variant),
                    *(_normalize_query(alias) for alias in value.aliases),
                }
            )
            state = (
                IdentityBetaState.OUT_OF_DOMAIN
                if same_alias_other_scope
                else IdentityBetaState.ABSENT
            )
            warning = (
                "matching records exist only outside the requested build or context"
                if same_alias_other_scope
                else "no matching variant identity or explicit alias was supplied"
            )
            return self._result(
                query,
                state,
                None,
                (),
                (),
                (),
                (),
                (),
                (),
                (warning,),
            )
        keys = tuple(sorted({value.equivalence_key for value in exact}))
        methods = tuple(
            sorted(
                {
                    "canonical_key"
                    if value.equivalence_key.casefold() == normalized_query
                    else "variant_id"
                    if normalized_variant_id(value.variant) == normalized_query
                    else "explicit_alias"
                    for value in exact
                }
            )
        )
        state = IdentityBetaState.SUPPORTED if len(keys) == 1 else IdentityBetaState.AMBIGUOUS
        warnings: list[str] = [
            "Equivalence resolution groups declared identities; it does not rewrite source "
            "records.",
            "Same-key records remain separate so source, version, sample, and custody receipts "
            "survive.",
        ]
        if len(keys) > 1:
            warnings.append(
                "The query matched competing normalized identities and remains ambiguous."
            )
        return self._result(
            query,
            state,
            keys[0] if len(keys) == 1 else None,
            tuple(value.record_id for value in exact),
            tuple(sorted({value.variant.variant_id for value in exact})),
            tuple(sorted({alias for value in exact for alias in value.aliases})),
            tuple(sorted({value.source_id for value in exact})),
            methods,
            keys,
            tuple(dict.fromkeys(warnings)),
        )

    def resolve_all(
        self,
        records: Iterable[VariantIdentityRecord | Mapping[str, Any]],
        *,
        genome_build: str | None = None,
        context_key: str | None = None,
    ) -> tuple[VariantEquivalenceMatch, ...]:
        values = tuple(_coerce_identity_record(value) for value in records)
        queries = tuple(
            sorted(
                {
                    value.equivalence_key
                    for value in values
                    if (genome_build is None or value.variant.genome_build == genome_build)
                    and (context_key is None or value.context_key == context_key)
                }
            )
        )
        return tuple(
            self.resolve(values, query, genome_build=genome_build, context_key=context_key)
            for query in queries
        )

    @staticmethod
    def _result(
        query: str,
        state: IdentityBetaState,
        key: str | None,
        record_ids: tuple[str, ...],
        variant_ids: tuple[str, ...],
        aliases: tuple[str, ...],
        source_ids: tuple[str, ...],
        methods: tuple[str, ...],
        competing_keys: tuple[str, ...],
        warnings: tuple[str, ...],
    ) -> VariantEquivalenceMatch:
        body = {
            "query": query,
            "state": state,
            "equivalence_key": key,
            "record_ids": record_ids,
            "variant_ids": variant_ids,
            "aliases": aliases,
            "source_ids": source_ids,
            "methods": methods,
            "competing_keys": competing_keys,
            "warnings": warnings,
        }
        return VariantEquivalenceMatch(
            query=query,
            state=state,
            equivalence_key=key,
            record_ids=record_ids,
            variant_ids=variant_ids,
            aliases=aliases,
            source_ids=source_ids,
            methods=methods,
            competing_keys=competing_keys,
            warnings=warnings,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class ReconciliationGroup:
    """One duplicate/alias group with every source record retained."""

    group_id: str
    state: IdentityBetaState
    equivalence_key: str | None
    record_ids: tuple[str, ...]
    variant_ids: tuple[str, ...]
    aliases: tuple[str, ...]
    source_ids: tuple[str, ...]
    conflict_keys: tuple[str, ...]
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AliasReconciliationReport:
    """Reconciliation report over a complete input batch."""

    state: IdentityBetaState
    groups: tuple[ReconciliationGroup, ...]
    duplicate_record_ids: tuple[str, ...]
    ambiguous_aliases: tuple[str, ...]
    ungrouped_record_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len({group.group_id for group in self.groups}) != len(self.groups):
            raise ValidationError("reconciliation group IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class DuplicateAliasReconciler:
    """Group exact normalized identities and explicit aliases conservatively."""

    def reconcile(
        self,
        records: Iterable[VariantIdentityRecord | Mapping[str, Any]],
    ) -> AliasReconciliationReport:
        values = tuple(_coerce_identity_record(value) for value in records)
        if len({value.record_id for value in values}) != len(values):
            raise ValidationError("reconciliation record IDs must be unique")
        by_key: dict[str, list[VariantIdentityRecord]] = defaultdict(list)
        by_alias: dict[str, list[VariantIdentityRecord]] = defaultdict(list)
        for value in values:
            by_key[value.equivalence_key].append(value)
            for alias in value.aliases:
                by_alias[_normalize_query(alias)].append(value)
        groups: list[ReconciliationGroup] = []
        grouped_records: set[str] = set()
        ambiguous_aliases: set[str] = set()
        for key, group_values in sorted(by_key.items()):
            aliases = tuple(sorted({alias for value in group_values for alias in value.aliases}))
            aliases_with_collisions = tuple(
                alias
                for alias in aliases
                if len({value.equivalence_key for value in by_alias[_normalize_query(alias)]}) > 1
            )
            ambiguous_aliases.update(aliases_with_collisions)
            state = (
                IdentityBetaState.AMBIGUOUS
                if aliases_with_collisions
                else IdentityBetaState.SUPPORTED
            )
            reason = (
                "explicit alias maps to competing normalized identities"
                if aliases_with_collisions
                else "records share one normalized build/interval/allele identity"
            )
            record_ids = tuple(sorted(value.record_id for value in group_values))
            grouped_records.update(record_ids)
            groups.append(
                self._group(
                    key,
                    state,
                    key,
                    record_ids,
                    tuple(sorted({value.variant.variant_id for value in group_values})),
                    aliases,
                    tuple(sorted({value.source_id for value in group_values})),
                    tuple(sorted({value.equivalence_key for value in group_values})),
                    reason,
                )
            )
        for alias, alias_values in sorted(by_alias.items()):
            keys = tuple(sorted({value.equivalence_key for value in alias_values}))
            if len(keys) < 2:
                continue
            ambiguous_aliases.add(alias)
            group_id = f"alias:{alias}"
            record_ids = tuple(sorted({value.record_id for value in alias_values}))
            groups.append(
                self._group(
                    group_id,
                    IdentityBetaState.AMBIGUOUS,
                    None,
                    record_ids,
                    tuple(sorted({value.variant.variant_id for value in alias_values})),
                    (alias,),
                    tuple(sorted({value.source_id for value in alias_values})),
                    keys,
                    "explicit alias maps to more than one normalized identity",
                )
            )
        duplicate_ids = tuple(
            sorted(
                record_id
                for values_for_key in by_key.values()
                if len(values_for_key) > 1
                for record_id in (value.record_id for value in values_for_key)
            )
        )
        ungrouped = tuple(sorted({value.record_id for value in values} - grouped_records))
        warnings: list[str] = [
            "Reconciliation keeps all source records and does not select a winning alias.",
            "Duplicate identity is not proof that records came from the same specimen or batch.",
        ]
        if duplicate_ids:
            warnings.append("At least one normalized identity has multiple source records.")
        if ambiguous_aliases:
            warnings.append("At least one alias is ambiguous and requires review.")
        if ungrouped:
            warnings.append("At least one input record was not placed in a reconciliation group.")
        if not values:
            state = IdentityBetaState.ABSTAINED
        elif ambiguous_aliases:
            state = IdentityBetaState.AMBIGUOUS
        elif duplicate_ids:
            state = IdentityBetaState.PARTIAL
        else:
            state = IdentityBetaState.SUPPORTED
        body = {
            "state": state,
            "groups": groups,
            "duplicate_record_ids": duplicate_ids,
            "ambiguous_aliases": tuple(sorted(ambiguous_aliases)),
            "ungrouped_record_ids": ungrouped,
            "warnings": warnings,
        }
        return AliasReconciliationReport(
            state=state,
            groups=tuple(groups),
            duplicate_record_ids=duplicate_ids,
            ambiguous_aliases=tuple(sorted(ambiguous_aliases)),
            ungrouped_record_ids=ungrouped,
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(body),
        )

    @staticmethod
    def _group(
        group_id: str,
        state: IdentityBetaState,
        key: str | None,
        record_ids: tuple[str, ...],
        variant_ids: tuple[str, ...],
        aliases: tuple[str, ...],
        source_ids: tuple[str, ...],
        conflict_keys: tuple[str, ...],
        reason: str,
    ) -> ReconciliationGroup:
        body = {
            "group_id": group_id,
            "state": state,
            "equivalence_key": key,
            "record_ids": record_ids,
            "variant_ids": variant_ids,
            "aliases": aliases,
            "source_ids": source_ids,
            "conflict_keys": conflict_keys,
            "reason": reason,
        }
        return ReconciliationGroup(
            group_id=group_id,
            state=state,
            equivalence_key=key,
            record_ids=record_ids,
            variant_ids=variant_ids,
            aliases=aliases,
            source_ids=source_ids,
            conflict_keys=conflict_keys,
            reason=reason,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class SampleIdentityObservation:
    """Declared batch/sample/subject identity metadata for one source row."""

    observation_id: str
    batch_id: str | None
    sample_id: str | None
    subject_id: str | None
    source_id: str
    source_version: str
    raw_hash: str
    specimen_type: str | None = None
    collection_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("observation_id", "source_id", "source_version", "raw_hash"):
            require_non_empty(getattr(self, name), name)
        for name in ("batch_id", "sample_id", "subject_id", "specimen_type", "collection_label"):
            value = getattr(self, name)
            if value is not None and not value.strip():
                raise ValidationError(f"sample identity {name} cannot be blank")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SampleIdentityObservation:
        return cls(
            observation_id=str(value.get("observation_id", value.get("id", ""))),
            batch_id=str(value["batch_id"]) if value.get("batch_id") is not None else None,
            sample_id=str(value["sample_id"]) if value.get("sample_id") is not None else None,
            subject_id=str(value["subject_id"]) if value.get("subject_id") is not None else None,
            source_id=str(value.get("source_id", "unspecified")),
            source_version=str(value.get("source_version", "unspecified")),
            raw_hash=str(value.get("raw_hash", content_hash(value))),
            specimen_type=str(value["specimen_type"])
            if value.get("specimen_type") is not None
            else None,
            collection_label=(
                str(value["collection_label"])
                if value.get("collection_label") is not None
                else None
            ),
            metadata=dict(value.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SampleIdentityIssue:
    """Lineage-preserving issue for sample identity review."""

    code: str
    message: str
    observation_ids: tuple[str, ...]
    severity: str = "warning"

    def __post_init__(self) -> None:
        require_non_empty(self.code, "sample identity issue code")
        require_non_empty(self.message, "sample identity issue message")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("sample identity issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SampleIdentityResult:
    """Batch/sample identity check with explicit conflict groups."""

    state: IdentityBetaState
    observations: tuple[SampleIdentityObservation, ...]
    batch_to_samples: Mapping[str, tuple[str, ...]]
    sample_to_subjects: Mapping[str, tuple[str, ...]]
    issues: tuple[SampleIdentityIssue, ...]
    missing_observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class BatchSampleIdentityChecker:
    """Check uniqueness and completeness of declared batch/sample mappings."""

    def check(
        self,
        observations: Iterable[SampleIdentityObservation | Mapping[str, Any]],
        *,
        require_batch: bool = True,
        require_sample: bool = True,
        require_subject: bool = False,
    ) -> SampleIdentityResult:
        values = tuple(
            item
            if isinstance(item, SampleIdentityObservation)
            else SampleIdentityObservation.from_mapping(item)
            for item in observations
        )
        if len({item.observation_id for item in values}) != len(values):
            raise ValidationError("sample identity observation IDs must be unique")
        issues: list[SampleIdentityIssue] = []
        missing: set[str] = set()
        for item in values:
            missing_fields = tuple(
                field_name
                for field_name, required, actual in (
                    ("batch_id", require_batch, item.batch_id),
                    ("sample_id", require_sample, item.sample_id),
                    ("subject_id", require_subject, item.subject_id),
                )
                if required and actual is None
            )
            if missing_fields:
                missing.add(item.observation_id)
                issues.append(
                    SampleIdentityIssue(
                        "missing_identity_field",
                        f"required identity field(s) missing: {', '.join(missing_fields)}",
                        (item.observation_id,),
                        "error",
                    )
                )
        batch_to_samples: dict[str, set[str]] = defaultdict(set)
        sample_to_subjects: dict[str, set[str]] = defaultdict(set)
        sample_to_observations: dict[str, list[str]] = defaultdict(list)
        for item in values:
            if item.batch_id is not None and item.sample_id is not None:
                batch_to_samples[item.batch_id].add(item.sample_id)
            if item.sample_id is not None:
                sample_to_observations[item.sample_id].append(item.observation_id)
                if item.subject_id is not None:
                    sample_to_subjects[item.sample_id].add(item.subject_id)
        for sample_id, subjects in sorted(sample_to_subjects.items()):
            if len(subjects) > 1:
                observation_ids = tuple(sorted(sample_to_observations[sample_id]))
                issues.append(
                    SampleIdentityIssue(
                        "sample_maps_to_multiple_subjects",
                        f"sample {sample_id} maps to multiple subjects: {sorted(subjects)}",
                        observation_ids,
                        "error",
                    )
                )
        for batch_id, samples in sorted(batch_to_samples.items()):
            if len(samples) > 1:
                observation_ids = tuple(
                    sorted(item.observation_id for item in values if item.batch_id == batch_id)
                )
                issues.append(
                    SampleIdentityIssue(
                        "batch_contains_multiple_samples",
                        f"batch {batch_id} contains multiple sample IDs: {sorted(samples)}",
                        observation_ids,
                        "warning",
                    )
                )
        warnings = [
            "Identity checking validates declared metadata only; it does not authenticate a "
            "specimen.",
            "A consistent sample/subject map does not establish consent or biological identity.",
        ]
        if missing:
            warnings.append("Required identity metadata is missing for at least one observation.")
        if issues:
            warnings.append(
                "Identity conflicts remain attached for review and are not auto-corrected."
            )
        if not values:
            state = IdentityBetaState.ABSTAINED
        elif any(issue.severity == "error" for issue in issues):
            state = IdentityBetaState.CONTRADICTORY
        elif issues or missing:
            state = IdentityBetaState.PARTIAL
        else:
            state = IdentityBetaState.SUPPORTED
        body = {
            "state": state,
            "observations": values,
            "batch_to_samples": batch_to_samples,
            "sample_to_subjects": sample_to_subjects,
            "issues": issues,
            "missing": missing,
            "warnings": warnings,
        }
        return SampleIdentityResult(
            state=state,
            observations=values,
            batch_to_samples={
                key: tuple(sorted(value)) for key, value in sorted(batch_to_samples.items())
            },
            sample_to_subjects={
                key: tuple(sorted(value)) for key, value in sorted(sample_to_subjects.items())
            },
            issues=tuple(issues),
            missing_observation_ids=tuple(sorted(missing)),
            source_ids=tuple(sorted({item.source_id for item in values})),
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(body),
        )


class CustodyEventKind(StrEnum):
    """Allowed artifact transition labels."""

    RECEIVED = "received"
    VALIDATED = "validated"
    TRANSFORMED = "transformed"
    EXPORTED = "exported"
    REVIEWED = "reviewed"
    QUARANTINED = "quarantined"


@dataclass(frozen=True, slots=True)
class CustodyEvent:
    """One immutable artifact transition with predecessor and hash receipts."""

    event_id: str
    artifact_id: str
    event_kind: CustodyEventKind
    actor_id: str
    occurred_at: str
    input_hashes: tuple[str, ...]
    output_hashes: tuple[str, ...]
    source_id: str
    previous_event_id: str | None = None
    notes: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("event_id", "artifact_id", "actor_id", "occurred_at", "source_id"):
            require_non_empty(getattr(self, name), name)
        if not self.input_hashes and self.event_kind != CustodyEventKind.RECEIVED:
            raise ValidationError("non-receipt custody events require input hashes")
        if not self.output_hashes and self.event_kind not in {CustodyEventKind.QUARANTINED}:
            raise ValidationError("custody events require output hashes unless quarantined")
        _parse_timestamp(self.occurred_at)
        if len(self.input_hashes) != len(set(self.input_hashes)):
            raise ValidationError("custody input hashes must be unique")
        if len(self.output_hashes) != len(set(self.output_hashes)):
            raise ValidationError("custody output hashes must be unique")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> CustodyEvent:
        return cls(
            event_id=str(value.get("event_id", value.get("id", ""))),
            artifact_id=str(value.get("artifact_id", "")),
            event_kind=CustodyEventKind(
                str(value.get("event_kind", value.get("kind", "received")))
            ),
            actor_id=str(value.get("actor_id", value.get("actor", ""))),
            occurred_at=str(value.get("occurred_at", value.get("timestamp", ""))),
            input_hashes=tuple(str(item) for item in value.get("input_hashes", ())),
            output_hashes=tuple(str(item) for item in value.get("output_hashes", ())),
            source_id=str(value.get("source_id", "unspecified")),
            previous_event_id=(
                str(value["previous_event_id"])
                if value.get("previous_event_id") is not None
                else None
            ),
            notes=str(value.get("notes", "")),
            metadata=dict(value.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CustodyIssue:
    """Chain-link or hash continuity diagnostic."""

    code: str
    message: str
    artifact_id: str
    event_ids: tuple[str, ...]
    severity: str = "error"

    def __post_init__(self) -> None:
        require_non_empty(self.code, "custody issue code")
        require_non_empty(self.message, "custody issue message")
        require_non_empty(self.artifact_id, "custody issue artifact_id")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("custody issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CustodyChain:
    """Ordered event chain for one artifact."""

    artifact_id: str
    state: IdentityBetaState
    event_ids: tuple[str, ...]
    input_hashes: tuple[str, ...]
    output_hashes: tuple[str, ...]
    issues: tuple[CustodyIssue, ...]
    chain_digest: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CustodyCaptureResult:
    """Full custody capture with per-artifact chains and global receipt."""

    state: IdentityBetaState
    chains: tuple[CustodyChain, ...]
    issues: tuple[CustodyIssue, ...]
    event_count: int
    artifact_count: int
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ChainOfCustodyCapture:
    """Capture and validate artifact event chains without claiming signatures."""

    def capture(
        self,
        events: Iterable[CustodyEvent | Mapping[str, Any]],
    ) -> CustodyCaptureResult:
        values = tuple(
            item if isinstance(item, CustodyEvent) else CustodyEvent.from_mapping(item)
            for item in events
        )
        if len({event.event_id for event in values}) != len(values):
            raise ValidationError("custody event IDs must be unique")
        by_id = {event.event_id: event for event in values}
        by_artifact: dict[str, list[CustodyEvent]] = defaultdict(list)
        for event in values:
            by_artifact[event.artifact_id].append(event)
        chains: list[CustodyChain] = []
        issues: list[CustodyIssue] = []
        for artifact_id, artifact_events in sorted(by_artifact.items()):
            ordered = tuple(
                sorted(
                    artifact_events,
                    key=lambda event: (_parse_timestamp(event.occurred_at), event.event_id),
                )
            )
            chain_issues: list[CustodyIssue] = []
            expected_previous: str | None = None
            previous_outputs: set[str] = set()
            for index, event in enumerate(ordered):
                if index == 0 and event.event_kind != CustodyEventKind.RECEIVED:
                    chain_issues.append(
                        CustodyIssue(
                            "chain_does_not_start_with_receipt",
                            "first artifact event is not a received event",
                            artifact_id,
                            (event.event_id,),
                        )
                    )
                if index > 0 and event.previous_event_id != expected_previous:
                    chain_issues.append(
                        CustodyIssue(
                            "broken_previous_event_link",
                            f"expected previous event {expected_previous!r}, got "
                            f"{event.previous_event_id!r}",
                            artifact_id,
                            tuple(item.event_id for item in ordered[max(0, index - 1) : index + 1]),
                        )
                    )
                if event.previous_event_id is not None and event.previous_event_id not in by_id:
                    chain_issues.append(
                        CustodyIssue(
                            "missing_previous_event",
                            "previous event ID is not present in the supplied capture",
                            artifact_id,
                            (event.event_id, event.previous_event_id),
                        )
                    )
                elif (
                    event.previous_event_id is not None
                    and by_id[event.previous_event_id].artifact_id != artifact_id
                ):
                    chain_issues.append(
                        CustodyIssue(
                            "cross_artifact_previous_event",
                            "previous event belongs to a different artifact chain",
                            artifact_id,
                            (event.event_id, event.previous_event_id),
                        )
                    )
                if index > 0 and event.input_hashes and previous_outputs:
                    if not set(event.input_hashes).intersection(previous_outputs):
                        chain_issues.append(
                            CustodyIssue(
                                "hash_continuity_gap",
                                "event inputs do not reference an output hash from the prior event",
                                artifact_id,
                                tuple(
                                    item.event_id for item in ordered[max(0, index - 1) : index + 1]
                                ),
                            )
                        )
                expected_previous = event.event_id
                previous_outputs = set(event.output_hashes)
            issues.extend(chain_issues)
            state = IdentityBetaState.CONTRADICTORY if chain_issues else IdentityBetaState.SUPPORTED
            input_hashes = tuple(
                sorted({hash_value for event in ordered for hash_value in event.input_hashes})
            )
            output_hashes = tuple(
                sorted({hash_value for event in ordered for hash_value in event.output_hashes})
            )
            digest = content_hash(
                {
                    "artifact_id": artifact_id,
                    "event_ids": tuple(event.event_id for event in ordered),
                    "input_hashes": input_hashes,
                    "output_hashes": output_hashes,
                }
            )
            chains.append(
                CustodyChain(
                    artifact_id=artifact_id,
                    state=state,
                    event_ids=tuple(event.event_id for event in ordered),
                    input_hashes=input_hashes,
                    output_hashes=output_hashes,
                    issues=tuple(chain_issues),
                    chain_digest=digest,
                )
            )
        warnings = [
            "Custody capture records supplied events and hashes; it does not create a "
            "signature or authenticate an actor.",
            "Missing events cannot be inferred from a continuous-looking hash sequence.",
        ]
        if issues:
            warnings.append("At least one custody chain has a broken link or hash continuity gap.")
        if not values:
            state = IdentityBetaState.ABSTAINED
        elif issues:
            state = IdentityBetaState.CONTRADICTORY
        else:
            state = IdentityBetaState.SUPPORTED
        body = {
            "state": state,
            "chains": chains,
            "issues": issues,
            "event_count": len(values),
            "warnings": warnings,
        }
        return CustodyCaptureResult(
            state=state,
            chains=tuple(chains),
            issues=tuple(issues),
            event_count=len(values),
            artifact_count=len(chains),
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(body),
        )


def normalized_variant_key(variant: VariantIdentity) -> str:
    """Build a source-independent key without changing the input identity."""

    return ":".join(
        (
            variant.genome_build.strip(),
            normalize_chromosome(variant.chromosome),
            str(variant.start),
            str(variant.end),
            normalize_allele(variant.reference),
            normalize_allele(variant.alternate),
            variant.kind.value,
        )
    )


def normalized_variant_id(variant: VariantIdentity) -> str:
    """Normalize a declared variant ID for case-insensitive alias matching."""

    return variant.variant_id.strip().casefold()


def _normalize_query(query: str) -> str:
    return query.strip().casefold()


def _coerce_identity_record(
    value: VariantIdentityRecord | Mapping[str, Any],
) -> VariantIdentityRecord:
    return (
        value
        if isinstance(value, VariantIdentityRecord)
        else VariantIdentityRecord.from_mapping(value)
    )


def _parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError(f"custody occurred_at must be ISO-8601: {value!r}") from exc


__all__ = [
    "AliasReconciliationReport",
    "BatchSampleIdentityChecker",
    "ChainOfCustodyCapture",
    "CustodyCaptureResult",
    "CustodyChain",
    "CustodyEvent",
    "CustodyEventKind",
    "CustodyIssue",
    "DuplicateAliasReconciler",
    "IdentityBetaState",
    "ReconciliationGroup",
    "SampleIdentityIssue",
    "SampleIdentityObservation",
    "SampleIdentityResult",
    "VariantEquivalenceMatch",
    "VariantEquivalenceResolver",
    "VariantIdentityRecord",
    "normalized_variant_id",
    "normalized_variant_key",
]
