"""Scientific-beta methylation and CpG context contracts.

Domain 07 keeps measured methylation separate from sequence-derived CpG
changes and from an IDH-associated context model. The operations are local,
versioned, context-gated, and content-addressed. They do not impute methylation
silently, treat a CpG change as a functional effect, or turn an IDH pattern
into a diagnosis.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .serialization import content_hash, jsonable, require_non_empty

_MISSING = object()


class MethylationBetaState(StrEnum):
    """Evidence state shared by methylation retrieval and beta models."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSENT = "absent"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class MethylationIssue:
    """Addressable parsing or interpretation issue with raw provenance."""

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
            raise ValidationError("methylation issue row_number must be positive")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("methylation issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationRecord:
    """One context-qualified CpG methylation observation."""

    record_id: str
    chromosome: str
    position: int
    beta_value: float | None
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    assay: str = "methylation"
    coverage: int | None = None
    molecular_state: str | None = None
    sample_id: str | None = None
    replicate_id: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "chromosome",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
            "assay",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.position < 1:
            raise ValidationError("methylation position must be positive")
        if self.beta_value is not None and not 0 <= self.beta_value <= 1:
            raise ValidationError("methylation beta_value must be between zero and one")
        if self.coverage is not None and self.coverage < 0:
            raise ValidationError("methylation coverage cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationBatch:
    """Parsed methylation observations and quarantined input rows."""

    source_id: str
    input_hash: str
    records: tuple[MethylationRecord, ...]
    issues: tuple[MethylationIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MethylationRecordParser:
    """Parse one-based or BED-like methylation records without silent coercion."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
        coordinate_system: str = "one_based",
    ) -> MethylationBatch:
        require_non_empty(source_id, "source_id")
        require_non_empty(source_version, "source_version")
        if coordinate_system not in {"one_based", "bed"}:
            raise ValidationError("methylation coordinate_system must be one_based or bed")
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("methylation input must not be empty")
        selected = (input_format or "").lower().strip()
        if not selected:
            selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
        if selected == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"invalid methylation JSON: {exc}") from exc
            if isinstance(payload, Mapping):
                rows = payload.get("records", payload.get("methylation", payload))
                if isinstance(rows, Mapping) and any(
                    key in rows for key in ("chromosome", "chrom", "position", "start")
                ):
                    rows = [rows]
            else:
                rows = payload
            if not isinstance(rows, list):
                raise ValidationError("methylation JSON must contain a records list")
            json_mode = True
        elif selected == "tsv":
            reader = csv.DictReader(io.StringIO(text), delimiter="\t")
            if not reader.fieldnames:
                raise ValidationError("methylation TSV requires a header")
            rows = tuple(reader)
            json_mode = False
        else:
            raise ValidationError(f"unsupported methylation format: {selected}")

        records: list[MethylationRecord] = []
        issues: list[MethylationIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                raw_hash = content_hash(row)
                issues.append(
                    MethylationIssue(
                        "invalid_methylation_row",
                        "row must be an object",
                        raw_hash,
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                    )
                )
                continue
            raw_hash = content_hash(row)
            try:
                chromosome = normalize_chromosome(str(self._value(row, "chromosome", "chrom")))
                position = self._position(row, coordinate_system)
                beta_raw = self._value(
                    row,
                    "beta_value",
                    "beta",
                    "methylation",
                    "methylation_value",
                    "value",
                    default=None,
                )
                beta_value = None if beta_raw is None else float(beta_raw)
                coverage_raw = self._value(row, "coverage", "read_depth", "depth", default=None)
                coverage = None if coverage_raw is None else int(coverage_raw)
                records.append(
                    MethylationRecord(
                        record_id=str(
                            self._value(row, "record_id", "id", default=f"{source_id}:{index}")
                        ),
                        chromosome=chromosome,
                        position=position,
                        beta_value=beta_value,
                        context_key=str(
                            self._value(row, "context_key", "context", default="unspecified")
                        ),
                        source_id=source_id,
                        source_version=str(
                            self._value(row, "source_version", "version", default=source_version)
                        ),
                        raw_hash=raw_hash,
                        assay=str(self._value(row, "assay", default="methylation")),
                        coverage=coverage,
                        molecular_state=self._optional_text(
                            row, "molecular_state", "state", "molecular_class"
                        ),
                        sample_id=self._optional_text(row, "sample_id", "sample"),
                        replicate_id=self._optional_text(row, "replicate_id", "replicate"),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    MethylationIssue(
                        "invalid_methylation_row",
                        str(exc),
                        raw_hash,
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        input_hash = content_hash(text)
        return MethylationBatch(
            source_id=source_id,
            input_hash=input_hash,
            records=tuple(records),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "input_hash": input_hash,
                    "records": records,
                    "issues": issues,
                }
            ),
        )

    @staticmethod
    def _value(row: Mapping[str, Any], *names: str, default: Any = _MISSING) -> Any:
        for name in names:
            value = row.get(name)
            if value is not None and value != "":
                return value
        if default is not _MISSING:
            return default
        raise ValidationError(f"methylation field {names[0]} is required")

    @classmethod
    def _optional_text(cls, row: Mapping[str, Any], *names: str) -> str | None:
        value = None
        for name in names:
            candidate = row.get(name)
            if candidate is not None and candidate != "":
                value = candidate
                break
        return None if value is None else str(value)

    @classmethod
    def _position(cls, row: Mapping[str, Any], coordinate_system: str) -> int:
        position = row.get("position")
        if position is not None and position != "":
            return int(position)
        start = cls._value(row, "start", "chrom_start")
        start_value = int(start)
        if coordinate_system == "bed":
            return start_value + 1
        return start_value


@dataclass(frozen=True, slots=True)
class MethylationQueryResult:
    """Exact-context methylation query with replicate-aware summary."""

    chromosome: str
    start: int
    end: int
    context_key: str
    state: MethylationBetaState
    records: tuple[MethylationRecord, ...]
    median_beta: float | None
    beta_spread: float | None
    median_coverage: float | None
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MethylationContextRetriever:
    """Retrieve methylation records only when coordinates and context agree."""

    def __init__(self, records: Iterable[MethylationRecord]) -> None:
        self._records = tuple(records)

    def query(
        self,
        chromosome: str,
        start: int,
        end: int,
        *,
        context_key: str,
        beta_spread_tolerance: float = 0.20,
    ) -> MethylationQueryResult:
        if start < 1 or end < start:
            raise ValidationError("methylation query interval must satisfy 1 <= start <= end")
        require_non_empty(context_key, "context_key")
        if beta_spread_tolerance < 0:
            raise ValidationError("beta_spread_tolerance cannot be negative")
        normalized = normalize_chromosome(chromosome)
        overlap = tuple(
            row
            for row in self._records
            if normalize_chromosome(row.chromosome) == normalized and start <= row.position <= end
        )
        exact = tuple(row for row in overlap if row.context_key == context_key)
        if not exact:
            state = MethylationBetaState.OUT_OF_DOMAIN if overlap else MethylationBetaState.ABSENT
            reason = (
                "overlapping methylation records exist only for another context"
                if overlap
                else "no methylation records overlap the requested interval"
            )
            return self._result(
                normalized,
                start,
                end,
                context_key,
                state,
                (),
                None,
                None,
                None,
                reason,
            )
        values = tuple(row.beta_value for row in exact if row.beta_value is not None)
        coverages = tuple(float(row.coverage) for row in exact if row.coverage is not None)
        median_beta = median(values) if values else None
        spread = max(values) - min(values) if len(values) > 1 else 0.0 if values else None
        if spread is not None and spread > beta_spread_tolerance:
            state = MethylationBetaState.AMBIGUOUS
            reason = "exact-context methylation replicates disagree beyond the declared tolerance"
        elif len(values) != len(exact):
            state = MethylationBetaState.PARTIAL
            reason = "exact-context records include missing beta values"
        else:
            state = MethylationBetaState.SUPPORTED
            reason = "exact-context methylation records support the requested interval"
        return self._result(
            normalized,
            start,
            end,
            context_key,
            state,
            exact,
            median_beta,
            spread,
            median(coverages) if coverages else None,
            reason,
        )

    @staticmethod
    def _result(
        chromosome: str,
        start: int,
        end: int,
        context_key: str,
        state: MethylationBetaState,
        records: tuple[MethylationRecord, ...],
        median_beta: float | None,
        beta_spread: float | None,
        median_coverage: float | None,
        reason: str,
    ) -> MethylationQueryResult:
        return MethylationQueryResult(
            chromosome=chromosome,
            start=start,
            end=end,
            context_key=context_key,
            state=state,
            records=records,
            median_beta=median_beta,
            beta_spread=beta_spread,
            median_coverage=median_coverage,
            reason=reason,
            content_address=content_hash(
                {
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "context_key": context_key,
                    "state": state,
                    "records": records,
                    "median_beta": median_beta,
                    "beta_spread": beta_spread,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class CpGChange:
    """One reference-only or alternate-only CpG dinucleotide."""

    change_type: str
    sequence_start: int
    sequence_end: int
    genomic_start: int
    chromosome: str
    reference_dinucleotide: str
    alternate_dinucleotide: str
    methylation_beta: float | None
    methylation_state: str
    methylation_record_ids: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.change_type, "CpG change_type")
        if self.change_type not in {"created", "lost"}:
            raise ValidationError("CpG change_type must be created or lost")
        if self.sequence_start < 1 or self.sequence_end != self.sequence_start + 1:
            raise ValidationError("CpG sequence interval must contain two bases")
        if self.genomic_start < 1:
            raise ValidationError("CpG genomic_start must be positive")
        if self.methylation_state not in {
            "methylated",
            "unmethylated",
            "missing",
            "ambiguous",
            "not_requested",
        }:
            raise ValidationError("unsupported CpG methylation_state")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CpGChangeReport:
    """Allele-specific CpG changes with optional measured methylation context."""

    variant_id: str
    chromosome: str
    window_start: int
    context_key: str | None
    state: MethylationBetaState
    reference_cpg_starts: tuple[int, ...]
    alternate_cpg_starts: tuple[int, ...]
    created: tuple[CpGChange, ...]
    lost: tuple[CpGChange, ...]
    methylation_context_state: MethylationBetaState
    issues: tuple[MethylationIssue, ...]
    warnings: tuple[str, ...]
    reference_sequence_hash: str
    alternate_sequence_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CpGCreationLossAnalyzer:
    """Detect CpG creation/loss in equal-length local allele windows."""

    def analyze(
        self,
        reference_sequence: str,
        alternate_sequence: str,
        *,
        variant_id: str,
        window_start: int = 1,
        chromosome: str = "unspecified",
        context_key: str | None = None,
        methylation_records: Iterable[MethylationRecord | Mapping[str, Any]] = (),
        methylated_threshold: float = 0.50,
        methylation_spread_tolerance: float = 0.20,
    ) -> CpGChangeReport:
        require_non_empty(variant_id, "variant_id")
        if window_start < 1:
            raise ValidationError("CpG window_start must be positive")
        if not 0 <= methylated_threshold <= 1:
            raise ValidationError("methylated_threshold must be between zero and one")
        if methylation_spread_tolerance < 0:
            raise ValidationError("methylation_spread_tolerance cannot be negative")
        ref = reference_sequence.strip().upper()
        alt = alternate_sequence.strip().upper()
        input_hash = content_hash(
            {
                "variant_id": variant_id,
                "reference": ref,
                "alternate": alt,
                "window_start": window_start,
            }
        )
        if not ref or not alt:
            issue = MethylationIssue(
                "empty_sequence_window",
                "reference and alternate sequence windows are required",
                input_hash,
                severity="error",
            )
            return self._report(
                variant_id,
                chromosome,
                window_start,
                context_key,
                MethylationBetaState.INVALID,
                (),
                (),
                (),
                (),
                MethylationBetaState.ABSTAINED,
                (issue,),
            )
        if any(base not in "ACGTN" for base in ref + alt):
            issue = MethylationIssue(
                "invalid_sequence_alphabet",
                "sequence windows must contain only A/C/G/T/N",
                input_hash,
                severity="error",
            )
            return self._report(
                variant_id,
                chromosome,
                window_start,
                context_key,
                MethylationBetaState.INVALID,
                (),
                (),
                (),
                (),
                MethylationBetaState.ABSTAINED,
                (issue,),
            )
        if len(ref) != len(alt):
            issue = MethylationIssue(
                "length_changing_variant_out_of_domain",
                "CpG creation/loss requires equal-length local windows for coordinate replay",
                input_hash,
                severity="error",
            )
            return self._report(
                variant_id,
                chromosome,
                window_start,
                context_key,
                MethylationBetaState.OUT_OF_DOMAIN,
                (),
                (),
                (),
                (),
                MethylationBetaState.ABSTAINED,
                (issue,),
            )
        normalized_chromosome = normalize_chromosome(chromosome)
        records = tuple(_coerce_methylation_record(record) for record in methylation_records)
        ref_sites = _cpg_sites(ref)
        alt_sites = _cpg_sites(alt)
        created_sites = tuple(site for site in alt_sites if site not in ref_sites)
        lost_sites = tuple(site for site in ref_sites if site not in alt_sites)
        created = tuple(
            self._change(
                "created",
                site,
                ref,
                alt,
                window_start,
                normalized_chromosome,
                context_key,
                records,
                methylated_threshold,
                methylation_spread_tolerance,
            )
            for site in created_sites
        )
        lost = tuple(
            self._change(
                "lost",
                site,
                ref,
                alt,
                window_start,
                normalized_chromosome,
                context_key,
                records,
                methylated_threshold,
                methylation_spread_tolerance,
            )
            for site in lost_sites
        )
        change_values = created + lost
        if not change_values or not records:
            methylation_state = (
                MethylationBetaState.ABSTAINED if not records else MethylationBetaState.ABSENT
            )
        elif any(change.methylation_state == "ambiguous" for change in change_values):
            methylation_state = MethylationBetaState.AMBIGUOUS
        elif any(change.methylation_state == "missing" for change in change_values):
            methylation_state = MethylationBetaState.PARTIAL
        else:
            methylation_state = MethylationBetaState.SUPPORTED
        return self._report(
            variant_id,
            normalized_chromosome,
            window_start,
            context_key,
            MethylationBetaState.SUPPORTED,
            tuple(window_start + site for site in ref_sites),
            tuple(window_start + site for site in alt_sites),
            created,
            lost,
            methylation_state,
            (),
            reference=ref,
            alternate=alt,
        )

    @staticmethod
    def _change(
        change_type: str,
        site: int,
        reference: str,
        alternate: str,
        window_start: int,
        chromosome: str,
        context_key: str | None,
        records: tuple[MethylationRecord, ...],
        methylated_threshold: float,
        methylation_spread_tolerance: float,
    ) -> CpGChange:
        genomic_start = window_start + site
        matching = tuple(
            record
            for record in records
            if normalize_chromosome(record.chromosome) == chromosome
            and record.position == genomic_start
            and (context_key is None or record.context_key == context_key)
        )
        values = tuple(record.beta_value for record in matching if record.beta_value is not None)
        if not matching or not values:
            beta_value = None
            methylation_state = "missing" if records else "not_requested"
        else:
            beta_value = median(values)
            spread = max(values) - min(values) if len(values) > 1 else 0.0
            methylation_state = (
                "ambiguous"
                if spread > methylation_spread_tolerance
                else "methylated"
                if beta_value >= methylated_threshold
                else "unmethylated"
            )
        ref_dinucleotide = reference[site : site + 2]
        alt_dinucleotide = alternate[site : site + 2]
        body = {
            "change_type": change_type,
            "genomic_start": genomic_start,
            "chromosome": chromosome,
            "reference": ref_dinucleotide,
            "alternate": alt_dinucleotide,
            "context_key": context_key,
            "record_ids": tuple(record.record_id for record in matching),
        }
        return CpGChange(
            change_type=change_type,
            sequence_start=site + 1,
            sequence_end=site + 2,
            genomic_start=genomic_start,
            chromosome=chromosome,
            reference_dinucleotide=ref_dinucleotide,
            alternate_dinucleotide=alt_dinucleotide,
            methylation_beta=beta_value,
            methylation_state=methylation_state,
            methylation_record_ids=tuple(record.record_id for record in matching),
            content_address=content_hash(body),
        )

    @staticmethod
    def _report(
        variant_id: str,
        chromosome: str,
        window_start: int,
        context_key: str | None,
        state: MethylationBetaState,
        reference_sites: tuple[int, ...],
        alternate_sites: tuple[int, ...],
        created: tuple[CpGChange, ...],
        lost: tuple[CpGChange, ...],
        methylation_context_state: MethylationBetaState,
        issues: tuple[MethylationIssue, ...],
        *,
        reference: str = "",
        alternate: str = "",
    ) -> CpGChangeReport:
        return CpGChangeReport(
            variant_id=variant_id,
            chromosome=chromosome,
            window_start=window_start,
            context_key=context_key,
            state=state,
            reference_cpg_starts=reference_sites,
            alternate_cpg_starts=alternate_sites,
            created=created,
            lost=lost,
            methylation_context_state=methylation_context_state,
            issues=issues,
            warnings=(
                "CpG creation or loss is a sequence observation, not proof of methylation "
                "change or regulatory effect.",
                "Methylation records are used only when chromosome, coordinate, and "
                "context key agree exactly.",
                "Window-boundary CpG partners outside the supplied sequence are not evaluated.",
            ),
            reference_sequence_hash=content_hash(reference),
            alternate_sequence_hash=content_hash(alternate),
            content_address=content_hash(
                {
                    "variant_id": variant_id,
                    "chromosome": chromosome,
                    "window_start": window_start,
                    "context_key": context_key,
                    "state": state,
                    "reference_sites": reference_sites,
                    "alternate_sites": alternate_sites,
                    "created": created,
                    "lost": lost,
                    "methylation_context_state": methylation_context_state,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class MethylationSensitiveMotifDefinition:
    """Declared motif with zero-based methylation-sensitive motif offsets."""

    motif_id: str
    name: str
    consensus: str
    source_id: str
    source_version: str
    sensitive_positions: tuple[int, ...]
    threshold: float = 1.0
    methylated_threshold: float = 0.50
    strand_aware: bool = True
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "motif_id",
            "name",
            "consensus",
            "source_id",
            "source_version",
        ):
            require_non_empty(str(getattr(self, name)), name)
        consensus = self.consensus.upper()
        if any(base not in _IUPAC for base in consensus):
            raise ValidationError("methylation-sensitive motif has unsupported IUPAC symbols")
        if not 0 < self.threshold <= 1:
            raise ValidationError("motif threshold must be between zero and one")
        if not 0 <= self.methylated_threshold <= 1:
            raise ValidationError("motif methylated_threshold must be between zero and one")
        if any(position < 0 or position >= len(consensus) for position in self.sensitive_positions):
            raise ValidationError(
                "motif sensitive_positions must be zero-based offsets in consensus"
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationSensitiveMotifHit:
    """One motif hit with measured methylation at sensitive positions."""

    motif_id: str
    motif_name: str
    start: int
    end: int
    strand: str
    matched_sequence: str
    score: float
    sensitive_genomic_positions: tuple[int, ...]
    methylation_betas: tuple[float, ...]
    methylation_state: str
    source_id: str
    source_version: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.motif_id, "motif_id")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("methylation-sensitive motif interval is invalid")
        if self.strand not in {"+", "-"}:
            raise ValidationError("methylation-sensitive motif strand must be + or -")
        if not 0 <= self.score <= 1:
            raise ValidationError("methylation-sensitive motif score must be between zero and one")
        if self.methylation_state not in {
            "methylated",
            "unmethylated",
            "missing",
            "ambiguous",
            "not_sensitive",
        }:
            raise ValidationError("unsupported methylation-sensitive motif state")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationSensitiveMotifReport:
    """Methylation-sensitive motif observations with exact source context."""

    sequence_id: str
    chromosome: str
    window_start: int
    context_key: str | None
    state: MethylationBetaState
    hits: tuple[MethylationSensitiveMotifHit, ...]
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    issues: tuple[MethylationIssue, ...]
    warnings: tuple[str, ...]
    sequence_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MethylationSensitiveMotifAnalyzer:
    """Scan declared motifs and annotate sensitive bases with measured beta values."""

    def analyze(
        self,
        sequence: str,
        *,
        sequence_id: str,
        motifs: Iterable[MethylationSensitiveMotifDefinition],
        methylation_records: Iterable[MethylationRecord | Mapping[str, Any]] = (),
        window_start: int = 1,
        chromosome: str = "unspecified",
        context_key: str | None = None,
        methylation_spread_tolerance: float = 0.20,
    ) -> MethylationSensitiveMotifReport:
        require_non_empty(sequence_id, "sequence_id")
        if window_start < 1:
            raise ValidationError("motif window_start must be positive")
        if methylation_spread_tolerance < 0:
            raise ValidationError("methylation_spread_tolerance cannot be negative")
        normalized = sequence.strip().upper()
        motifs_values = tuple(motifs)
        records = tuple(_coerce_methylation_record(record) for record in methylation_records)
        input_hash = content_hash(
            {
                "sequence_id": sequence_id,
                "sequence": normalized,
                "window_start": window_start,
                "chromosome": chromosome,
                "context_key": context_key,
            }
        )
        if not normalized or any(base not in "ACGTN" for base in normalized):
            issue = MethylationIssue(
                "invalid_sequence_window",
                "motif sequence must contain only A/C/G/T/N and must not be empty",
                input_hash,
                severity="error",
            )
            return self._report(
                sequence_id,
                chromosome,
                window_start,
                context_key,
                MethylationBetaState.INVALID,
                (),
                motifs_values,
                (issue,),
                normalized,
            )
        if not motifs_values:
            return self._report(
                sequence_id,
                chromosome,
                window_start,
                context_key,
                MethylationBetaState.ABSTAINED,
                (),
                motifs_values,
                (),
                normalized,
            )
        normalized_chromosome = normalize_chromosome(chromosome)
        hits = tuple(
            self._hits_for_motif(
                normalized,
                motif,
                window_start,
                normalized_chromosome,
                context_key,
                records,
                methylation_spread_tolerance,
            )
            for motif in motifs_values
        )
        flat_hits = tuple(hit for group in hits for hit in group)
        if not flat_hits:
            state = MethylationBetaState.ABSENT
        elif any(hit.methylation_state == "ambiguous" for hit in flat_hits):
            state = MethylationBetaState.AMBIGUOUS
        elif any(hit.methylation_state == "missing" for hit in flat_hits):
            state = MethylationBetaState.PARTIAL
        else:
            state = MethylationBetaState.SUPPORTED
        return self._report(
            sequence_id,
            normalized_chromosome,
            window_start,
            context_key,
            state,
            flat_hits,
            motifs_values,
            (),
            normalized,
        )

    @staticmethod
    def _hits_for_motif(
        sequence: str,
        motif: MethylationSensitiveMotifDefinition,
        window_start: int,
        chromosome: str,
        context_key: str | None,
        records: tuple[MethylationRecord, ...],
        methylation_spread_tolerance: float,
    ) -> tuple[MethylationSensitiveMotifHit, ...]:
        consensus = motif.consensus.upper()
        strands = (
            (("+", consensus), ("-", _reverse_complement(consensus)))
            if motif.strand_aware
            else (("+", consensus),)
        )
        hits: list[MethylationSensitiveMotifHit] = []
        for strand, pattern in strands:
            for index in range(len(sequence) - len(pattern) + 1):
                matched = sequence[index : index + len(pattern)]
                score = sum(
                    base in _IUPAC[pattern[offset]] for offset, base in enumerate(matched)
                ) / len(pattern)
                if score < motif.threshold:
                    continue
                sensitive_positions = tuple(
                    (
                        window_start + index + position
                        if strand == "+"
                        else window_start + index + len(pattern) - 1 - position
                    )
                    for position in motif.sensitive_positions
                )
                matching_values: list[float] = []
                matching_records: list[MethylationRecord] = []
                for position in sensitive_positions:
                    site_records = tuple(
                        record
                        for record in records
                        if normalize_chromosome(record.chromosome) == chromosome
                        and record.position == position
                        and (context_key is None or record.context_key == context_key)
                    )
                    site_values = tuple(
                        record.beta_value
                        for record in site_records
                        if record.beta_value is not None
                    )
                    if site_values:
                        matching_values.append(median(site_values))
                        matching_records.extend(site_records)
                if not motif.sensitive_positions:
                    methylation_state = "not_sensitive"
                elif len(matching_values) != len(sensitive_positions):
                    methylation_state = "missing"
                else:
                    spread = max(matching_values) - min(matching_values)
                    methylation_state = (
                        "ambiguous"
                        if spread > methylation_spread_tolerance
                        else "methylated"
                        if median(matching_values) >= motif.methylated_threshold
                        else "unmethylated"
                    )
                body = {
                    "motif_id": motif.motif_id,
                    "strand": strand,
                    "start": window_start + index,
                    "matched": matched,
                    "sensitive_positions": sensitive_positions,
                    "record_ids": tuple(record.record_id for record in matching_records),
                }
                hits.append(
                    MethylationSensitiveMotifHit(
                        motif_id=motif.motif_id,
                        motif_name=motif.name,
                        start=window_start + index,
                        end=window_start + index + len(pattern) - 1,
                        strand=strand,
                        matched_sequence=matched,
                        score=round(score, 6),
                        sensitive_genomic_positions=sensitive_positions,
                        methylation_betas=tuple(round(value, 6) for value in matching_values),
                        methylation_state=methylation_state,
                        source_id=motif.source_id,
                        source_version=motif.source_version,
                        content_address=content_hash(body),
                    )
                )
        return tuple(sorted(hits, key=lambda hit: (hit.start, hit.end, hit.motif_id, hit.strand)))

    @staticmethod
    def _report(
        sequence_id: str,
        chromosome: str,
        window_start: int,
        context_key: str | None,
        state: MethylationBetaState,
        hits: tuple[MethylationSensitiveMotifHit, ...],
        motifs: tuple[MethylationSensitiveMotifDefinition, ...],
        issues: tuple[MethylationIssue, ...],
        sequence: str,
    ) -> MethylationSensitiveMotifReport:
        return MethylationSensitiveMotifReport(
            sequence_id=sequence_id,
            chromosome=chromosome,
            window_start=window_start,
            context_key=context_key,
            state=state,
            hits=hits,
            source_ids=tuple(sorted({motif.source_id for motif in motifs})),
            source_versions=tuple(sorted({motif.source_version for motif in motifs})),
            issues=issues,
            warnings=(
                "Methylation-sensitive motif state is a declared sequence/methylation "
                "observation, not a binding prediction.",
                "Sensitive offsets are zero-based within the declared motif consensus "
                "and require exact context coordinates.",
                "Missing methylation is reported explicitly and is not imputed from "
                "neighboring CpGs.",
            ),
            sequence_hash=content_hash(sequence),
            content_address=content_hash(
                {
                    "sequence_id": sequence_id,
                    "chromosome": chromosome,
                    "window_start": window_start,
                    "context_key": context_key,
                    "state": state,
                    "hits": hits,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class IdhHypermethylationContextResult:
    """Versioned descriptive IDH-associated methylation context result."""

    context_key: str
    molecular_state: str
    comparator_state: str
    model_id: str
    model_version: str
    state: MethylationBetaState
    measured_site_count: int
    high_methylation_site_count: int
    high_methylation_fraction: float | None
    mean_beta: float | None
    median_beta: float | None
    coverage_weighted_beta: float | None
    comparator_site_count: int
    comparator_mean_beta: float | None
    delta_vs_comparator: float | None
    hypermethylated: bool | None
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class IdhHypermethylationContextModel:
    """Summarize declared IDH-mutant methylation panels against a comparator."""

    def assess(
        self,
        target_records: Iterable[MethylationRecord | Mapping[str, Any]],
        *,
        context_key: str,
        molecular_state: str = "IDH-mutant",
        comparator_records: Iterable[MethylationRecord | Mapping[str, Any]] = (),
        comparator_state: str = "IDH-wildtype",
        model_id: str,
        model_version: str,
        methylated_threshold: float = 0.70,
        minimum_sites: int = 3,
    ) -> IdhHypermethylationContextResult:
        require_non_empty(context_key, "context_key")
        require_non_empty(molecular_state, "molecular_state")
        require_non_empty(comparator_state, "comparator_state")
        require_non_empty(model_id, "model_id")
        require_non_empty(model_version, "model_version")
        if not 0 <= methylated_threshold <= 1:
            raise ValidationError("methylated_threshold must be between zero and one")
        if minimum_sites < 1:
            raise ValidationError("minimum_sites must be positive")
        target_values = tuple(_coerce_methylation_record(record) for record in target_records)
        comparator_values = tuple(
            _coerce_methylation_record(record) for record in comparator_records
        )
        target = tuple(
            record
            for record in target_values
            if record.context_key == context_key
            and record.molecular_state == molecular_state
            and record.beta_value is not None
        )
        comparator = tuple(
            record
            for record in comparator_values
            if record.context_key == context_key
            and record.molecular_state == comparator_state
            and record.beta_value is not None
        )
        target_betas = tuple(
            record.beta_value for record in target if record.beta_value is not None
        )
        comparator_betas = tuple(
            record.beta_value for record in comparator if record.beta_value is not None
        )
        high_count = sum(value >= methylated_threshold for value in target_betas)
        fraction = high_count / len(target_betas) if target_betas else None
        mean_beta = sum(target_betas) / len(target_betas) if target_betas else None
        median_beta = median(target_betas) if target_betas else None
        weighted_beta = self._weighted_beta(target)
        comparator_mean = (
            sum(comparator_betas) / len(comparator_betas) if comparator_betas else None
        )
        delta = (
            mean_beta - comparator_mean
            if mean_beta is not None and comparator_mean is not None
            else None
        )
        if len(target) < minimum_sites:
            state = (
                MethylationBetaState.OUT_OF_DOMAIN
                if target_values
                and not any(record.context_key == context_key for record in target_values)
                else MethylationBetaState.ABSTAINED
            )
            reason = "fewer than the declared minimum IDH-state methylation sites are measured"
            hypermethylated = None
        elif len(comparator) < minimum_sites:
            state = MethylationBetaState.PARTIAL
            reason = "target state is measured but comparator methylation support is incomplete"
            hypermethylated = bool(
                fraction is not None
                and fraction >= 0.5
                and mean_beta is not None
                and mean_beta >= methylated_threshold
            )
        else:
            state = MethylationBetaState.SUPPORTED
            reason = (
                "target and comparator IDH-state methylation panels meet the declared site minimum"
            )
            hypermethylated = bool(
                fraction is not None
                and fraction >= 0.5
                and mean_beta is not None
                and mean_beta >= methylated_threshold
            )
        source_records = target + comparator
        return IdhHypermethylationContextResult(
            context_key=context_key,
            molecular_state=molecular_state,
            comparator_state=comparator_state,
            model_id=model_id,
            model_version=model_version,
            state=state,
            measured_site_count=len(target),
            high_methylation_site_count=high_count,
            high_methylation_fraction=round(fraction, 9) if fraction is not None else None,
            mean_beta=round(mean_beta, 9) if mean_beta is not None else None,
            median_beta=round(median_beta, 9) if median_beta is not None else None,
            coverage_weighted_beta=(round(weighted_beta, 9) if weighted_beta is not None else None),
            comparator_site_count=len(comparator),
            comparator_mean_beta=(
                round(comparator_mean, 9) if comparator_mean is not None else None
            ),
            delta_vs_comparator=round(delta, 9) if delta is not None else None,
            hypermethylated=hypermethylated,
            source_ids=tuple(sorted({record.source_id for record in source_records})),
            source_versions=tuple(sorted({record.source_version for record in source_records})),
            reason=reason,
            warnings=(
                "This is a descriptive IDH-associated methylation context model, not a "
                "diagnostic classifier.",
                "The hypermethylated flag is a declared panel threshold result, not a "
                "genome-wide epigenetic state.",
                "Calibration, matched external validation, subgroup transport, and "
                "assay harmonization remain required.",
            ),
            content_address=content_hash(
                {
                    "context_key": context_key,
                    "molecular_state": molecular_state,
                    "comparator_state": comparator_state,
                    "model_id": model_id,
                    "model_version": model_version,
                    "state": state,
                    "target": target,
                    "comparator": comparator,
                    "threshold": methylated_threshold,
                    "minimum_sites": minimum_sites,
                }
            ),
        )

    @staticmethod
    def _weighted_beta(records: tuple[MethylationRecord, ...]) -> float | None:
        weighted = tuple(
            (record.beta_value, record.coverage)
            for record in records
            if record.beta_value is not None and record.coverage is not None and record.coverage > 0
        )
        if not weighted:
            return None
        denominator = sum(coverage for _, coverage in weighted)
        return sum(beta * coverage for beta, coverage in weighted) / denominator


def _cpg_sites(sequence: str) -> tuple[int, ...]:
    return tuple(index for index in range(len(sequence) - 1) if sequence[index : index + 2] == "CG")


def _coerce_methylation_record(value: MethylationRecord | Mapping[str, Any]) -> MethylationRecord:
    if isinstance(value, MethylationRecord):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("methylation record must be a MethylationRecord or mapping")
    beta_raw = value.get("beta_value", value.get("beta", value.get("methylation")))
    return MethylationRecord(
        record_id=str(value.get("record_id", value.get("id", "methylation-input"))),
        chromosome=normalize_chromosome(str(value.get("chromosome", value.get("chrom", "")))),
        position=int(value.get("position", value.get("start", 0))),
        beta_value=None if beta_raw is None else float(beta_raw),
        context_key=str(value.get("context_key", value.get("context", "unspecified"))),
        source_id=str(value.get("source_id", "methylation-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        assay=str(value.get("assay", "methylation")),
        coverage=(
            None
            if value.get("coverage", value.get("read_depth")) is None
            else int(value.get("coverage", value.get("read_depth")))
        ),
        molecular_state=(
            None
            if value.get("molecular_state", value.get("state")) is None
            else str(value.get("molecular_state", value.get("state")))
        ),
        sample_id=None if value.get("sample_id") is None else str(value.get("sample_id")),
        replicate_id=(
            None if value.get("replicate_id") is None else str(value.get("replicate_id"))
        ),
        attributes=dict(value),
    )


def _reverse_complement(sequence: str) -> str:
    complement = {
        "A": "T",
        "C": "G",
        "G": "C",
        "T": "A",
        "R": "Y",
        "Y": "R",
        "S": "S",
        "W": "W",
        "K": "M",
        "M": "K",
        "B": "V",
        "V": "B",
        "D": "H",
        "H": "D",
        "N": "N",
    }
    return "".join(complement.get(base, "N") for base in reversed(sequence))


_IUPAC: dict[str, set[str]] = {
    "A": {"A"},
    "C": {"C"},
    "G": {"G"},
    "T": {"T"},
    "R": {"A", "G"},
    "Y": {"C", "T"},
    "S": {"G", "C"},
    "W": {"A", "T"},
    "K": {"G", "T"},
    "M": {"A", "C"},
    "B": {"C", "G", "T"},
    "D": {"A", "G", "T"},
    "H": {"A", "C", "T"},
    "V": {"A", "C", "G"},
    "N": {"A", "C", "G", "T", "N"},
}


__all__ = [
    "CpGChange",
    "CpGChangeReport",
    "CpGCreationLossAnalyzer",
    "IdhHypermethylationContextModel",
    "IdhHypermethylationContextResult",
    "MethylationBatch",
    "MethylationBetaState",
    "MethylationContextRetriever",
    "MethylationIssue",
    "MethylationQueryResult",
    "MethylationRecord",
    "MethylationRecordParser",
    "MethylationSensitiveMotifAnalyzer",
    "MethylationSensitiveMotifDefinition",
    "MethylationSensitiveMotifHit",
    "MethylationSensitiveMotifReport",
]
