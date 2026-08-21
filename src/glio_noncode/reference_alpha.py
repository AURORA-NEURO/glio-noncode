"""Deep reference and annotation governance contracts.

This module extends the Domain 04 reference boundary with four independent
operations:

* gene alias and version resolution from a declared local catalog;
* population-frequency adaptation with allele-count derivation and source
  receipts;
* content-addressed reference snapshot manifests and comparisons; and
* license/use-restriction evaluation for declared resources.

The adapters are intentionally local and deterministic. They do not download
reference data, infer gene identity from a free-text description, turn a
population frequency into a clinical classification, or treat a missing
license as permission. Ambiguity, stale versions, missing counts, checksum
drift, and conflicting restrictions remain explicit.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from statistics import mean
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class ReferenceAlphaState(StrEnum):
    """Evidence state shared by the reference alpha adapters."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class ReferenceAlphaIssue:
    """A source-row-addressable reference governance issue."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "issue code")
        require_non_empty(self.message, "issue message")
        require_non_empty(self.raw_hash, "issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("issue row_number must be positive")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GeneAliasRecord:
    """One versioned gene identity and its declared aliases."""

    gene_id: str
    symbol: str
    aliases: tuple[str, ...]
    version: str | None
    assembly: str
    source_id: str
    source_version: str
    raw_hash: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.gene_id, "gene_id"),
            (self.symbol, "symbol"),
            (self.assembly, "assembly"),
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
            (self.raw_hash, "raw_hash"),
        ):
            require_non_empty(value, field_name)

    @property
    def versioned_id(self) -> str:
        return f"{self.gene_id}.{self.version}" if self.version else self.gene_id

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"versioned_id": self.versioned_id}


@dataclass(frozen=True, slots=True)
class GeneAliasMatch:
    """One catalog record matched to a query and the exact basis used."""

    query_id: str
    gene_id: str
    versioned_id: str
    symbol: str
    assembly: str
    match_basis: tuple[str, ...]
    source_id: str
    source_version: str
    raw_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GeneAliasResolution:
    """One alias/version query with zero, one, or many matches."""

    query_id: str
    query_value: str
    state: ReferenceAlphaState
    matches: tuple[GeneAliasMatch, ...]
    issues: tuple[ReferenceAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GeneAliasResolutionReport:
    """Batch gene alias resolution with parsed catalog records."""

    input_hash: str
    assembly: str | None
    state: ReferenceAlphaState
    records: tuple[GeneAliasRecord, ...]
    resolutions: tuple[GeneAliasResolution, ...]
    issues: tuple[ReferenceAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class GeneAliasVersionResolver:
    """Resolve only identifiers, symbols, aliases, and declared versions."""

    def resolve(
        self,
        queries: Iterable[Mapping[str, Any] | str],
        records: Iterable[Mapping[str, Any]],
        *,
        assembly: str | None = None,
    ) -> GeneAliasResolutionReport:
        query_values = tuple(queries)
        record_values = tuple(records)
        input_hash = content_hash({"queries": query_values, "records": record_values})
        issues: list[ReferenceAlphaIssue] = []
        parsed_records: list[GeneAliasRecord] = []
        for row_number, row in enumerate(record_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    ReferenceAlphaIssue(
                        "record_not_object",
                        "gene alias record must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            try:
                record = self._parse_record(row, raw_hash)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ReferenceAlphaIssue(
                        "invalid_gene_alias_record",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            if assembly and record.assembly.casefold() != assembly.casefold():
                continue
            parsed_records.append(record)
        index: dict[str, list[tuple[GeneAliasRecord, str]]] = defaultdict(list)
        for record in parsed_records:
            values = {
                (record.gene_id, "gene_id"),
                (record.versioned_id, "versioned_gene_id"),
                (record.symbol, "symbol"),
            }
            values.update((alias, "alias") for alias in record.aliases)
            for value, basis in values:
                index[_gene_key(value)].append((record, basis))
        resolutions: list[GeneAliasResolution] = []
        for row_number, query in enumerate(query_values, start=1):
            query_value = str(
                query
                if isinstance(query, str)
                else _value(query, "query", "gene", "gene_id", "symbol", "alias", default="")
            ).strip()
            query_id = (
                str(query.get("query_id", f"query-{row_number}"))
                if isinstance(query, Mapping)
                else f"query-{row_number}"
            )
            if not query_value:
                resolutions.append(
                    GeneAliasResolution(
                        query_id,
                        query_value,
                        ReferenceAlphaState.INVALID,
                        (),
                        (
                            ReferenceAlphaIssue(
                                "missing_gene_query",
                                "gene alias query must not be empty",
                                content_hash(query),
                                row_number,
                                severity="error",
                            ),
                        ),
                        (),
                        content_hash({"query_id": query_id, "state": "invalid"}),
                    )
                )
                continue
            candidates = index.get(_gene_key(query_value), [])
            query_base, query_version = _split_version(query_value)
            if query_version:
                candidates = [
                    (record, basis)
                    for record, basis in candidates
                    if record.version == query_version
                    or record.versioned_id.casefold() == query_value.casefold()
                ]
            matches: list[GeneAliasMatch] = []
            seen_keys: set[tuple[str, str, str]] = set()
            for record, basis in candidates:
                key = (record.gene_id, record.version or "", record.assembly)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                body = {
                    "query_id": query_id,
                    "query_value": query_value,
                    "record": record.versioned_id,
                    "basis": basis,
                }
                matches.append(
                    GeneAliasMatch(
                        query_id=query_id,
                        gene_id=record.gene_id,
                        versioned_id=record.versioned_id,
                        symbol=record.symbol,
                        assembly=record.assembly,
                        match_basis=(basis,) if not query_version else (basis, "version_exact"),
                        source_id=record.source_id,
                        source_version=record.source_version,
                        raw_hash=record.raw_hash,
                        content_address=content_hash(body),
                    )
                )
            if not matches:
                state = ReferenceAlphaState.ABSTAINED
                resolution_issues = (
                    ReferenceAlphaIssue(
                        "gene_not_resolved",
                        f"no declared gene record matched query: {query_value}",
                        content_hash(query),
                        row_number,
                        severity="warning",
                    ),
                )
            elif len(matches) > 1:
                state = ReferenceAlphaState.AMBIGUOUS
                resolution_issues = (
                    ReferenceAlphaIssue(
                        "gene_match_ambiguous",
                        "query matched multiple declared gene records",
                        content_hash(query),
                        row_number,
                        severity="warning",
                    ),
                )
            else:
                state = ReferenceAlphaState.SUPPORTED
                resolution_issues = ()
            resolutions.append(
                GeneAliasResolution(
                    query_id,
                    query_value,
                    state,
                    tuple(sorted(matches, key=lambda item: item.versioned_id)),
                    resolution_issues,
                    (
                        "Gene resolution uses declared catalog identifiers and aliases; "
                        "free-text function descriptions are not identity evidence.",
                    ),
                    content_hash(
                        {
                            "query_id": query_id,
                            "query": query_value,
                            "matches": matches,
                            "state": state,
                        }
                    ),
                )
            )
        if not parsed_records and record_values:
            state = ReferenceAlphaState.OUT_OF_DOMAIN if assembly else ReferenceAlphaState.ABSTAINED
        elif any(item.state == ReferenceAlphaState.AMBIGUOUS for item in resolutions):
            state = ReferenceAlphaState.AMBIGUOUS
        elif any(item.state == ReferenceAlphaState.INVALID for item in resolutions) or issues:
            state = ReferenceAlphaState.PARTIAL
        elif any(item.state == ReferenceAlphaState.ABSTAINED for item in resolutions):
            state = ReferenceAlphaState.PARTIAL
        elif not resolutions:
            state = ReferenceAlphaState.ABSTAINED
        else:
            state = ReferenceAlphaState.SUPPORTED
        return GeneAliasResolutionReport(
            input_hash=input_hash,
            assembly=assembly,
            state=state,
            records=tuple(parsed_records),
            resolutions=tuple(resolutions),
            issues=tuple(issues),
            warnings=(
                "Versionless IDs can remain ambiguous when multiple catalog versions exist.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "records": parsed_records,
                    "resolutions": resolutions,
                }
            ),
        )

    @staticmethod
    def _parse_record(row: Mapping[str, Any], raw_hash: str) -> GeneAliasRecord:
        gene_value = str(_value(row, "gene_id", "id", "gene"))
        gene_id, embedded_version = _split_version(gene_value)
        version = _optional_text(_value(row, "version", "gene_version", default=embedded_version))
        return GeneAliasRecord(
            gene_id=gene_id,
            symbol=str(_value(row, "symbol", "gene_symbol", "name")),
            aliases=_text_tuple(_value(row, "aliases", "alias", "synonyms", default=())),
            version=version,
            assembly=str(_value(row, "assembly", "genome_build", default="unspecified")),
            source_id=_source_id(row),
            source_version=_source_version(row),
            raw_hash=raw_hash,
            attributes=dict(row),
        )


@dataclass(frozen=True, slots=True)
class PopulationFrequencyObservation:
    """One variant/population frequency observation."""

    variant_id: str
    population_id: str
    allele_frequency: float | None
    allele_count: int | None
    allele_number: int | None
    homozygote_count: int | None
    genome_build: str
    ancestry: str | None
    source_id: str
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.variant_id, "variant_id"),
            (self.population_id, "population_id"),
            (self.genome_build, "genome_build"),
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
            (self.raw_hash, "raw_hash"),
        ):
            require_non_empty(value, field_name)
        if self.allele_frequency is not None and not 0 <= self.allele_frequency <= 1:
            raise ValidationError("allele frequency must be between 0 and 1")
        if self.allele_count is not None and self.allele_count < 0:
            raise ValidationError("allele count cannot be negative")
        if self.allele_number is not None and self.allele_number <= 0:
            raise ValidationError("allele number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PopulationFrequencySummary:
    """Per-variant population summary retaining every population row."""

    variant_id: str
    observations: tuple[PopulationFrequencyObservation, ...]
    population_ids: tuple[str, ...]
    minimum_frequency: float | None
    maximum_frequency: float | None
    mean_frequency: float | None
    state: ReferenceAlphaState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PopulationFrequencyReport:
    """Adapted population frequencies and input issues."""

    input_hash: str
    genome_build: str | None
    state: ReferenceAlphaState
    observations: tuple[PopulationFrequencyObservation, ...]
    summaries: tuple[PopulationFrequencySummary, ...]
    issues: tuple[ReferenceAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PopulationFrequencyAdapter:
    """Normalize frequency rows while retaining counts and population scope."""

    def adapt(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        genome_build: str | None = None,
        variant_id: str | None = None,
    ) -> PopulationFrequencyReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[ReferenceAlphaIssue] = []
        observations: list[PopulationFrequencyObservation] = []
        context_mismatch = False
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    ReferenceAlphaIssue(
                        "row_not_object",
                        "population frequency row must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            selected_variant = str(_value(row, "variant_id", "variant", "id", default=""))
            if variant_id and selected_variant != variant_id:
                continue
            row_build = str(_value(row, "genome_build", "assembly", "build", default="unspecified"))
            if genome_build and row_build.casefold() != genome_build.casefold():
                context_mismatch = True
                issues.append(
                    ReferenceAlphaIssue(
                        "genome_build_mismatch",
                        "population frequency row is outside the requested genome build",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                allele_count = _optional_int(
                    _value(row, "allele_count", "AC", "alt_count", default=None)
                )
                allele_number = _optional_int(
                    _value(row, "allele_number", "AN", "total_alleles", default=None)
                )
                homozygote_count = _optional_int(
                    _value(row, "homozygote_count", "nhomalt", "hom_count", default=None)
                )
                frequency = _optional_float(
                    _value(row, "allele_frequency", "AF", "frequency", "freq", default=None)
                )
                if frequency is None and allele_count is not None and allele_number is not None:
                    if allele_number <= 0:
                        raise ValidationError(
                            "allele number must be positive when deriving frequency"
                        )
                    frequency = allele_count / allele_number
                if frequency is not None and not 0 <= frequency <= 1:
                    raise ValidationError("allele frequency must be between 0 and 1")
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ReferenceAlphaIssue(
                        "invalid_population_frequency",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            observations.append(
                PopulationFrequencyObservation(
                    variant_id=selected_variant,
                    population_id=str(
                        _value(row, "population_id", "population", "pop", default="unspecified")
                    ),
                    allele_frequency=round(frequency, 12) if frequency is not None else None,
                    allele_count=allele_count,
                    allele_number=allele_number,
                    homozygote_count=homozygote_count,
                    genome_build=row_build,
                    ancestry=_optional_text(
                        _value(row, "ancestry", "superpopulation", default=None)
                    ),
                    source_id=_source_id(row),
                    source_version=_source_version(row),
                    raw_hash=raw_hash,
                )
            )
        grouped: dict[str, list[PopulationFrequencyObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.variant_id].append(observation)
        summaries = tuple(
            self._summary(variant, group) for variant, group in sorted(grouped.items())
        )
        if context_mismatch and not observations:
            state = ReferenceAlphaState.OUT_OF_DOMAIN
        elif any(summary.state == ReferenceAlphaState.CONTRADICTORY for summary in summaries):
            state = ReferenceAlphaState.CONTRADICTORY
        elif issues or any(summary.state == ReferenceAlphaState.PARTIAL for summary in summaries):
            state = ReferenceAlphaState.PARTIAL
        elif not observations:
            state = ReferenceAlphaState.ABSTAINED
        elif context_mismatch:
            state = ReferenceAlphaState.PARTIAL
        else:
            state = ReferenceAlphaState.SUPPORTED
        return PopulationFrequencyReport(
            input_hash=input_hash,
            genome_build=genome_build,
            state=state,
            observations=tuple(observations),
            summaries=summaries,
            issues=tuple(issues),
            warnings=(
                "Population frequencies are descriptive source observations and not "
                "clinical classifications.",
                "Rows with missing allele counts remain visible instead of being "
                "treated as zero frequency.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "observations": observations,
                    "summaries": summaries,
                }
            ),
        )

    @staticmethod
    def _summary(
        variant_id: str, observations: Sequence[PopulationFrequencyObservation]
    ) -> PopulationFrequencySummary:
        frequencies = [
            item.allele_frequency for item in observations if item.allele_frequency is not None
        ]
        by_population: dict[str, set[float]] = defaultdict(set)
        for item in observations:
            if item.allele_frequency is not None:
                by_population[item.population_id].add(item.allele_frequency)
        contradictory = any(len(values) > 1 for values in by_population.values())
        state = (
            ReferenceAlphaState.CONTRADICTORY if contradictory else ReferenceAlphaState.SUPPORTED
        )
        if not frequencies:
            state = ReferenceAlphaState.PARTIAL
        body = {
            "variant_id": variant_id,
            "observations": observations,
            "state": state,
        }
        return PopulationFrequencySummary(
            variant_id=variant_id,
            observations=tuple(observations),
            population_ids=tuple(sorted({item.population_id for item in observations})),
            minimum_frequency=round(min(frequencies), 12) if frequencies else None,
            maximum_frequency=round(max(frequencies), 12) if frequencies else None,
            mean_frequency=round(mean(frequencies), 12) if frequencies else None,
            state=state,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class ReferenceResource:
    """One immutable resource entry in a reference snapshot."""

    resource_id: str
    kind: str
    uri: str
    checksum: str
    size_bytes: int | None
    source_id: str
    source_version: str
    license_id: str | None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.resource_id, "resource_id"),
            (self.kind, "kind"),
            (self.uri, "uri"),
            (self.checksum, "checksum"),
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
        ):
            require_non_empty(value, field_name)
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValidationError("resource size_bytes cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceSnapshot:
    """Content-addressed snapshot manifest for a reference assembly."""

    snapshot_id: str
    assembly: str
    source_id: str
    source_version: str
    resources: tuple[ReferenceResource, ...]
    manifest_hash: str
    state: ReferenceAlphaState
    issues: tuple[ReferenceAlphaIssue, ...]
    content_address: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.snapshot_id, "snapshot_id"),
            (self.assembly, "assembly"),
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
            (self.manifest_hash, "manifest_hash"),
        ):
            require_non_empty(value, field_name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SnapshotComparison:
    """Manifest comparison between two named snapshots."""

    left_snapshot_id: str
    right_snapshot_id: str
    added_resource_ids: tuple[str, ...]
    removed_resource_ids: tuple[str, ...]
    changed_resource_ids: tuple[str, ...]
    unchanged_resource_ids: tuple[str, ...]
    state: ReferenceAlphaState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReferenceSnapshotManager:
    """Build and compare manifests without fetching resource bytes."""

    def build(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        snapshot_id: str,
        assembly: str,
        source_id: str,
        source_version: str = "unspecified",
        expected_manifest_hash: str | None = None,
    ) -> ReferenceSnapshot:
        values = tuple(records)
        issues: list[ReferenceAlphaIssue] = []
        resources: list[ReferenceResource] = []
        seen_ids: set[str] = set()
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    ReferenceAlphaIssue(
                        "resource_not_object",
                        "reference resource must be an object",
                        content_hash({"row": row}),
                        row_number,
                        source_id=source_id,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            try:
                resource = self._parse_resource(row, source_id, source_version)
                if resource.resource_id in seen_ids:
                    raise ValidationError(f"duplicate resource ID: {resource.resource_id}")
                seen_ids.add(resource.resource_id)
                resources.append(resource)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ReferenceAlphaIssue(
                        "invalid_reference_resource",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        ordered = tuple(sorted(resources, key=lambda item: item.resource_id))
        manifest_hash = content_hash(
            {
                "snapshot_id": snapshot_id,
                "assembly": assembly,
                "source_id": source_id,
                "source_version": source_version,
                "resources": ordered,
            }
        )
        if expected_manifest_hash and expected_manifest_hash != manifest_hash:
            issues.append(
                ReferenceAlphaIssue(
                    "manifest_hash_mismatch",
                    "computed reference manifest differs from the expected hash",
                    manifest_hash,
                    source_id=source_id,
                    severity="error",
                )
            )
        if not ordered:
            state = ReferenceAlphaState.ABSTAINED
        elif issues:
            state = ReferenceAlphaState.CONTRADICTORY
        else:
            state = ReferenceAlphaState.SUPPORTED
        body = {
            "snapshot_id": snapshot_id,
            "assembly": assembly,
            "manifest_hash": manifest_hash,
            "resources": ordered,
            "issues": issues,
        }
        return ReferenceSnapshot(
            snapshot_id=snapshot_id,
            assembly=assembly,
            source_id=source_id,
            source_version=source_version,
            resources=ordered,
            manifest_hash=manifest_hash,
            state=state,
            issues=tuple(issues),
            content_address=content_hash(body),
        )

    def compare(self, left: ReferenceSnapshot, right: ReferenceSnapshot) -> SnapshotComparison:
        left_by_id = {item.resource_id: item for item in left.resources}
        right_by_id = {item.resource_id: item for item in right.resources}
        added = tuple(sorted(set(right_by_id) - set(left_by_id)))
        removed = tuple(sorted(set(left_by_id) - set(right_by_id)))
        changed = tuple(
            sorted(
                resource_id
                for resource_id in set(left_by_id) & set(right_by_id)
                if left_by_id[resource_id].checksum != right_by_id[resource_id].checksum
                or left_by_id[resource_id].source_version != right_by_id[resource_id].source_version
            )
        )
        unchanged = tuple(sorted(set(left_by_id) & set(right_by_id) - set(changed)))
        state = (
            ReferenceAlphaState.PARTIAL
            if added or removed or changed or left.assembly != right.assembly
            else ReferenceAlphaState.SUPPORTED
        )
        body = {
            "left": left.snapshot_id,
            "right": right.snapshot_id,
            "added": added,
            "removed": removed,
            "changed": changed,
            "unchanged": unchanged,
        }
        return SnapshotComparison(
            left_snapshot_id=left.snapshot_id,
            right_snapshot_id=right.snapshot_id,
            added_resource_ids=added,
            removed_resource_ids=removed,
            changed_resource_ids=changed,
            unchanged_resource_ids=unchanged,
            state=state,
            content_address=content_hash(body),
        )

    @staticmethod
    def _parse_resource(
        row: Mapping[str, Any], source_id: str, source_version: str
    ) -> ReferenceResource:
        checksum = str(_value(row, "checksum", "sha256", "digest"))
        if ":" not in checksum:
            checksum = "sha256:" + checksum
        return ReferenceResource(
            resource_id=str(_value(row, "resource_id", "id", "name")),
            kind=str(_value(row, "kind", "resource_kind", "type", default="reference")),
            uri=str(_value(row, "uri", "path", "location")),
            checksum=checksum,
            size_bytes=_optional_int(_value(row, "size_bytes", "size", default=None)),
            source_id=str(row.get("source_id", source_id)),
            source_version=str(row.get("source_version", source_version)),
            license_id=_optional_text(_value(row, "license_id", "license", default=None)),
            attributes=dict(row),
        )


@dataclass(frozen=True, slots=True)
class LicenseRestriction:
    """Declared use restrictions for one resource or license family."""

    resource_id: str
    license_id: str
    allowed_uses: tuple[str, ...]
    prohibited_uses: tuple[str, ...]
    attribution_text: str | None
    redistribution_allowed: bool
    commercial_allowed: bool
    expires_on: str | None
    source_id: str
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.resource_id, "resource_id"),
            (self.license_id, "license_id"),
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
            (self.raw_hash, "raw_hash"),
        ):
            require_non_empty(value, field_name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LicenseDecision:
    """One resource/use decision with explicit reasons."""

    resource_id: str
    license_id: str | None
    requested_use: str
    allowed: bool
    needs_attribution: bool
    reasons: tuple[str, ...]
    state: ReferenceAlphaState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LicenseEvaluationReport:
    """Use decisions for requested resources and missing restrictions."""

    input_hash: str
    requested_use: str
    decisions: tuple[LicenseDecision, ...]
    missing_resource_ids: tuple[str, ...]
    issues: tuple[ReferenceAlphaIssue, ...]
    state: ReferenceAlphaState
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LicenseUseRestrictionRegistry:
    """Evaluate explicit restrictions without treating absence as permission."""

    def evaluate(
        self,
        resources: Iterable[Mapping[str, Any]],
        restrictions: Iterable[Mapping[str, Any]],
        *,
        requested_use: str,
        redistribution: bool = False,
        commercial: bool = False,
        as_of: str | None = None,
    ) -> LicenseEvaluationReport:
        resource_values = tuple(resources)
        restriction_values = tuple(restrictions)
        input_hash = content_hash(
            {
                "resources": resource_values,
                "restrictions": restriction_values,
                "requested_use": requested_use,
                "redistribution": redistribution,
                "commercial": commercial,
            }
        )
        issues: list[ReferenceAlphaIssue] = []
        parsed_restrictions: list[LicenseRestriction] = []
        for row_number, row in enumerate(restriction_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    ReferenceAlphaIssue(
                        "restriction_not_object",
                        "license restriction must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            try:
                parsed_restrictions.append(self._parse_restriction(row, raw_hash))
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ReferenceAlphaIssue(
                        "invalid_license_restriction",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
        by_resource: dict[str, list[LicenseRestriction]] = defaultdict(list)
        for restriction in parsed_restrictions:
            by_resource[restriction.resource_id].append(restriction)
        decisions: list[LicenseDecision] = []
        missing: set[str] = set()
        for row_number, resource in enumerate(resource_values, start=1):
            if not isinstance(resource, Mapping):
                issues.append(
                    ReferenceAlphaIssue(
                        "resource_not_object",
                        "license evaluation resource must be an object",
                        content_hash({"row": resource}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            resource_id = str(_value(resource, "resource_id", "id", "name"))
            candidates = by_resource.get(resource_id, [])
            if not candidates:
                missing.add(resource_id)
                decisions.append(
                    LicenseDecision(
                        resource_id,
                        None,
                        requested_use,
                        False,
                        False,
                        ("no restriction record was supplied; use is blocked",),
                        ReferenceAlphaState.ABSTAINED,
                        content_hash({"resource_id": resource_id, "state": "abstained"}),
                    )
                )
                continue
            signatures = {
                (
                    item.license_id,
                    item.allowed_uses,
                    item.prohibited_uses,
                    item.redistribution_allowed,
                    item.commercial_allowed,
                    item.expires_on,
                )
                for item in candidates
            }
            if len(signatures) > 1:
                issues.append(
                    ReferenceAlphaIssue(
                        "conflicting_license_restrictions",
                        "multiple restriction records disagree for the resource",
                        content_hash(sorted(signatures, key=str)),
                        source_id=candidates[0].source_id,
                        severity="error",
                    )
                )
                decisions.append(
                    LicenseDecision(
                        resource_id,
                        None,
                        requested_use,
                        False,
                        False,
                        ("conflicting restriction records require review",),
                        ReferenceAlphaState.CONTRADICTORY,
                        content_hash({"resource_id": resource_id, "state": "contradictory"}),
                    )
                )
                continue
            restriction = candidates[0]
            reasons: list[str] = []
            normalized_use = requested_use.casefold().strip()
            allowed_uses = {item.casefold() for item in restriction.allowed_uses}
            prohibited_uses = {item.casefold() for item in restriction.prohibited_uses}
            allowed = True
            if normalized_use in prohibited_uses:
                allowed = False
                reasons.append("requested use is explicitly prohibited")
            elif allowed_uses and "all" not in allowed_uses and normalized_use not in allowed_uses:
                allowed = False
                reasons.append("requested use is not in the allowed-use declaration")
            if redistribution and not restriction.redistribution_allowed:
                allowed = False
                reasons.append("redistribution is not allowed")
            if commercial and not restriction.commercial_allowed:
                allowed = False
                reasons.append("commercial use is not allowed")
            expiry = _parse_date(restriction.expires_on)
            requested_date = _parse_date(as_of)
            if expiry and requested_date and requested_date > expiry:
                allowed = False
                reasons.append("restriction record is expired for the requested date")
            if allowed:
                reasons.append("requested use satisfies the declared restrictions")
            state = ReferenceAlphaState.SUPPORTED if allowed else ReferenceAlphaState.PARTIAL
            decisions.append(
                LicenseDecision(
                    resource_id=resource_id,
                    license_id=restriction.license_id,
                    requested_use=requested_use,
                    allowed=allowed,
                    needs_attribution=bool(restriction.attribution_text),
                    reasons=tuple(reasons),
                    state=state,
                    content_address=content_hash(
                        {
                            "resource_id": resource_id,
                            "license_id": restriction.license_id,
                            "requested_use": requested_use,
                            "allowed": allowed,
                            "reasons": reasons,
                        }
                    ),
                )
            )
        if any(item.state == ReferenceAlphaState.CONTRADICTORY for item in decisions):
            state = ReferenceAlphaState.CONTRADICTORY
        elif missing or issues or any(not item.allowed for item in decisions):
            state = ReferenceAlphaState.PARTIAL
        elif not decisions:
            state = ReferenceAlphaState.ABSTAINED
        else:
            state = ReferenceAlphaState.SUPPORTED
        return LicenseEvaluationReport(
            input_hash=input_hash,
            requested_use=requested_use,
            decisions=tuple(decisions),
            missing_resource_ids=tuple(sorted(missing)),
            issues=tuple(issues),
            state=state,
            warnings=(
                "A missing or conflicting license record blocks use until reviewed.",
                "Attribution requirements remain attached to allowed decisions.",
            ),
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "decisions": decisions, "issues": issues}
            ),
        )

    @staticmethod
    def _parse_restriction(row: Mapping[str, Any], raw_hash: str) -> LicenseRestriction:
        return LicenseRestriction(
            resource_id=str(_value(row, "resource_id", "id", "resource")),
            license_id=str(_value(row, "license_id", "license")),
            allowed_uses=_text_tuple(_value(row, "allowed_uses", "allowed", default=())),
            prohibited_uses=_text_tuple(
                _value(row, "prohibited_uses", "prohibited", "forbidden", default=())
            ),
            attribution_text=_optional_text(
                _value(row, "attribution_text", "attribution", default=None)
            ),
            redistribution_allowed=_as_bool(
                _value(row, "redistribution_allowed", "redistribution", default=False)
            ),
            commercial_allowed=_as_bool(
                _value(row, "commercial_allowed", "commercial", default=False)
            ),
            expires_on=_optional_text(_value(row, "expires_on", "expiry", default=None)),
            source_id=_source_id(row),
            source_version=_source_version(row),
            raw_hash=raw_hash,
        )


def _gene_key(value: str) -> str:
    return " ".join(str(value).strip().casefold().split())


def _split_version(value: str) -> tuple[str, str | None]:
    text = str(value).strip()
    if "." not in text:
        return text, None
    identifier, version = text.rsplit(".", 1)
    if version.isdigit():
        return identifier, version
    return text, None


_MISSING = object()


def _value(row: Mapping[str, Any], *keys: str, default: Any = _MISSING) -> Any:
    for key in keys:
        if key not in row:
            continue
        value = row[key]
        if value is not None and value != "":
            return value
    if default is not _MISSING:
        return default
    raise ValidationError(f"missing required field; expected one of {keys}")


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = value.replace(";", "|").replace(",", "|").split("|")
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        values = [str(item) for item in value]
    else:
        values = [str(value)]
    return tuple(dict.fromkeys(item.strip() for item in values if item.strip()))


def _optional_text(value: Any) -> str | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValidationError("integer value cannot be negative")
    return parsed


def _optional_float(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    parsed = float(value)
    return parsed


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "allowed"}


def _parse_date(value: str | None) -> date | None:
    if value is None or not str(value).strip():
        return None
    return date.fromisoformat(str(value).replace("Z", "")[:10])


def _raw_hash(row: Mapping[str, Any]) -> str:
    return content_hash(dict(row))


def _source_id(row: Mapping[str, Any]) -> str:
    return str(row.get("source_id", row.get("source", "unspecified"))) or "unspecified"


def _source_version(row: Mapping[str, Any]) -> str:
    return str(row.get("source_version", row.get("version", "unspecified"))) or "unspecified"


__all__ = [
    "GeneAliasMatch",
    "GeneAliasRecord",
    "GeneAliasResolution",
    "GeneAliasResolutionReport",
    "GeneAliasVersionResolver",
    "LicenseDecision",
    "LicenseEvaluationReport",
    "LicenseRestriction",
    "LicenseUseRestrictionRegistry",
    "PopulationFrequencyAdapter",
    "PopulationFrequencyObservation",
    "PopulationFrequencyReport",
    "PopulationFrequencySummary",
    "ReferenceAlphaIssue",
    "ReferenceAlphaState",
    "ReferenceResource",
    "ReferenceSnapshot",
    "ReferenceSnapshotManager",
    "SnapshotComparison",
]
