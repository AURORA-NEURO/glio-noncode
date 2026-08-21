"""Blueprint-backed capability catalog and implementation coverage ledger.

The catalog is product data, not executable starter code.  It is loaded from
``schemas/capability_catalog.csv`` and validated against the blueprint's
256-capability / 16-domain contract.  Coverage is intentionally separate from
the 48-agent registry: an agent can own a role while many finer-grained
capabilities remain planned or only partially implemented.
"""

from __future__ import annotations

import csv
import sysconfig
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


class CapabilityState(StrEnum):
    """Evidence-backed implementation state for one capability work package."""

    PLANNED = "planned"
    PARTIAL = "partial"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    """One immutable capability row from the approved product blueprint."""

    capability_id: str
    domain_id: str
    domain: str
    layer: str
    capability_order: int
    capability: str
    kind: str
    primary_agent_id: str
    release_wave: str
    mvp_64: bool
    blueprint_status: str

    def __post_init__(self) -> None:
        for name in (
            "capability_id",
            "domain_id",
            "domain",
            "layer",
            "capability",
            "kind",
            "primary_agent_id",
            "release_wave",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"capability {name} is required")
        if self.capability_order < 1:
            raise ValidationError("capability_order must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CapabilityCoverage:
    """Coverage counts with an explicit denominator and no hidden exclusions."""

    total_capabilities: int
    mvp_capabilities: int
    mvp_implemented: int
    mvp_started: int
    planned: int
    partial: int
    implemented: int
    verified: int
    by_domain: Mapping[str, Mapping[str, int]]

    @property
    def implementation_percent(self) -> float:
        return round(
            100.0 * (self.implemented + self.verified) / max(1, self.total_capabilities),
            2,
        )

    @property
    def verified_percent(self) -> float:
        return round(100.0 * self.verified / max(1, self.total_capabilities), 2)

    @property
    def mvp_implementation_percent(self) -> float:
        return round(100.0 * self.mvp_implemented / max(1, self.mvp_capabilities), 2)

    @property
    def started(self) -> int:
        """Capabilities with code or tests started, including partial work."""

        return self.partial + self.implemented + self.verified

    @property
    def started_percent(self) -> float:
        return round(100.0 * self.started / max(1, self.total_capabilities), 2)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "implementation_percent": self.implementation_percent,
            "verified_percent": self.verified_percent,
            "mvp_implementation_percent": self.mvp_implementation_percent,
            "started": self.started,
            "started_percent": self.started_percent,
            "mvp_started": self.mvp_started,
            "mvp_started_percent": round(
                100.0 * self.mvp_started / max(1, self.mvp_capabilities), 2
            ),
        }


@dataclass(frozen=True, slots=True)
class CapabilityRecord:
    """A capability plus the repository evidence used to assign its state."""

    spec: CapabilitySpec
    state: CapabilityState
    implementation_modules: tuple[str, ...] = ()
    test_modules: tuple[str, ...] = ()
    evidence_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "state": self.state.value,
            "implementation_modules": list(self.implementation_modules),
            "test_modules": list(self.test_modules),
            "evidence_note": self.evidence_note,
        }


def _default_catalog_path() -> Path:
    candidates = (
        Path(__file__).resolve().parents[2] / "schemas" / "capability_catalog.csv",
        Path.cwd() / "schemas" / "capability_catalog.csv",
        Path(sysconfig.get_path("data")) / "schemas" / "capability_catalog.csv",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValidationError(
        "capability catalog is not installed; expected schemas/capability_catalog.csv"
    )


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"yes", "no"}:
        raise ValidationError(f"capability mvp_64 must be yes or no, got {value!r}")
    return normalized == "yes"


class CapabilityRegistry:
    """Load and validate the full capability ledger."""

    def __init__(self, records: Iterable[CapabilityRecord]) -> None:
        values = tuple(records)
        self._records = {record.spec.capability_id: record for record in values}
        if len(self._records) != len(values):
            raise ValidationError("capability IDs must be unique")
        self.validate()

    @classmethod
    def from_csv(cls, path: str | Path | None = None) -> CapabilityRegistry:
        catalog_path = Path(path) if path is not None else _default_catalog_path()
        try:
            with catalog_path.open("r", encoding="utf-8", newline="") as handle:
                rows = tuple(csv.DictReader(handle))
        except OSError as exc:
            raise ValidationError(f"unable to read capability catalog: {catalog_path}") from exc
        records: list[CapabilityRecord] = []
        for row in rows:
            try:
                spec = CapabilitySpec(
                    capability_id=str(row["capability_id"]),
                    domain_id=str(row["domain_id"]),
                    domain=str(row["domain"]),
                    layer=str(row["layer"]),
                    capability_order=int(row["capability_order"]),
                    capability=str(row["capability"]),
                    kind=str(row["kind"]),
                    primary_agent_id=str(row["primary_agent_id"]),
                    release_wave=str(row["release_wave"]),
                    mvp_64=_bool(str(row["mvp_64"])),
                    blueprint_status=str(row["status"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValidationError(f"invalid capability row: {row!r}") from exc
            records.append(CapabilityRecord(spec, CapabilityState.PLANNED))
        return cls(records)

    def validate(self) -> None:
        if len(self._records) != 256:
            raise ValidationError(
                f"capability catalog requires 256 rows, found {len(self._records)}"
            )
        domains = Counter(record.spec.domain_id for record in self._records.values())
        if len(domains) != 16 or set(domains.values()) != {16}:
            raise ValidationError(f"capability catalog must contain 16 rows per domain: {domains}")
        mvp_count = sum(record.spec.mvp_64 for record in self._records.values())
        if mvp_count != 64:
            raise ValidationError(f"capability catalog requires 64 MVP rows, found {mvp_count}")
        for domain_id in domains:
            orders = sorted(
                record.spec.capability_order
                for record in self._records.values()
                if record.spec.domain_id == domain_id
            )
            if orders != list(range(1, 17)):
                raise ValidationError(f"capability order is not complete for {domain_id}: {orders}")

    def records(self) -> tuple[CapabilityRecord, ...]:
        return tuple(
            sorted(
                self._records.values(),
                key=lambda record: (record.spec.domain_id, record.spec.capability_order),
            )
        )

    def record(self, capability_id: str) -> CapabilityRecord:
        try:
            return self._records[capability_id]
        except KeyError as exc:
            raise ValidationError(f"unknown capability: {capability_id}") from exc

    def by_domain(self, domain_id: str) -> tuple[CapabilityRecord, ...]:
        return tuple(record for record in self.records() if record.spec.domain_id == domain_id)

    def mvp(self) -> tuple[CapabilityRecord, ...]:
        return tuple(record for record in self.records() if record.spec.mvp_64)

    def with_evidence(
        self,
        evidence: Mapping[str, Mapping[str, Any]],
    ) -> CapabilityRegistry:
        """Return a new ledger with state only where repository evidence is declared."""

        updated: list[CapabilityRecord] = []
        for record in self.records():
            raw = evidence.get(record.spec.capability_id)
            if raw is None:
                updated.append(record)
                continue
            try:
                state = CapabilityState(str(raw["state"]))
            except (KeyError, ValueError) as exc:
                raise ValidationError(
                    f"invalid implementation state for {record.spec.capability_id}"
                ) from exc
            if state in {CapabilityState.IMPLEMENTED, CapabilityState.VERIFIED} and not raw.get(
                "implementation_modules"
            ):
                raise ValidationError(
                    f"implemented capability {record.spec.capability_id} "
                    "requires implementation_modules"
                )
            updated.append(
                CapabilityRecord(
                    spec=record.spec,
                    state=state,
                    implementation_modules=tuple(
                        str(item) for item in raw.get("implementation_modules", ())
                    ),
                    test_modules=tuple(str(item) for item in raw.get("test_modules", ())),
                    evidence_note=str(raw.get("evidence_note", "")),
                )
            )
        return CapabilityRegistry(updated)

    def coverage(self) -> CapabilityCoverage:
        counts = Counter(record.state.value for record in self._records.values())
        domain_counts: dict[str, dict[str, int]] = {}
        for domain_id in sorted({record.spec.domain_id for record in self._records.values()}):
            domain_counts[domain_id] = dict(
                Counter(record.state.value for record in self.by_domain(domain_id))
            )
        return CapabilityCoverage(
            total_capabilities=len(self._records),
            mvp_capabilities=len(self.mvp()),
            mvp_implemented=sum(
                record.state in {CapabilityState.IMPLEMENTED, CapabilityState.VERIFIED}
                for record in self.mvp()
            ),
            mvp_started=sum(record.state != CapabilityState.PLANNED for record in self.mvp()),
            planned=counts[CapabilityState.PLANNED.value],
            partial=counts[CapabilityState.PARTIAL.value],
            implemented=counts[CapabilityState.IMPLEMENTED.value],
            verified=counts[CapabilityState.VERIFIED.value],
            by_domain=domain_counts,
        )

    def manifest(self) -> dict[str, Any]:
        coverage = self.coverage()
        return {
            "catalog_version": "blueprint-2026-08-20",
            "catalog_hash": content_hash([record.spec.to_dict() for record in self.records()]),
            "coverage": coverage.to_dict(),
            "records": [record.to_dict() for record in self.records()],
        }


def default_capability_registry() -> CapabilityRegistry:
    """Load the checked-in catalog with only repository-backed evidence applied."""

    registry = CapabilityRegistry.from_csv()
    return registry.with_evidence(
        {
            "GNC-D01-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.intake.VariantIntake",
                    "glio_noncode.models.CaseManifest",
                ),
                "test_modules": ("tests.test_intake", "tests.test_d01_capabilities"),
                "evidence_note": (
                    "VCF/TSV/JSON/BCF fixtures preserve source accounting and can be "
                    "projected into a CaseManifest; malformed records remain reviewable."
                ),
            },
            "GNC-D01-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.intake.VariantIntake",
                    "glio_noncode.bcf.BcfReader",
                ),
                "test_modules": ("tests.test_intake", "tests.test_bcf"),
                "evidence_note": (
                    "Binary BCF2 and text gVCF paths have bounded fixtures, genotype "
                    "handling, and explicit symbolic-record deferral."
                ),
            },
            "GNC-D01-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": ("glio_noncode.regulatory_tracks.RegulatoryTrackParser",),
                "test_modules": ("tests.test_d01_capabilities",),
                "evidence_note": (
                    "BED, narrowPeak, GFF3, and JSON interval fixtures preserve source "
                    "coordinates, attributes, hashes, and quarantined rows."
                ),
            },
            "GNC-D01-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.variant_normalization.VRSNormalizer",),
                "test_modules": ("tests.test_d01_capabilities",),
                "evidence_note": (
                    "VRS-shaped Allele output, sequence-digest provenance, trimming, and "
                    "ambiguity abstention are implemented; full RefGet-backed equivalence "
                    "truth sets remain to be built."
                ),
            },
            "GNC-D01-C05": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.variant_beta.CategoricalCatalogParser",
                    "glio_noncode.variant_beta.CatVRSNormalizer",
                ),
                "test_modules": ("tests.test_variant_beta", "tests.test_variant_beta_cli"),
                "evidence_note": (
                    "Versioned JSON/TSV/CSV categorical catalogs retain malformed rows and "
                    "support exact declared category, alias, ontology-term, and member-ID "
                    "matching; label-only scientific inference and external Cat-VRS schema "
                    "validation remain out of scope."
                ),
            },
            "GNC-D01-C06": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.variant_beta.AnnotationStatement",
                    "glio_noncode.variant_beta.VAAnnotationEnvelopeBuilder",
                ),
                "test_modules": ("tests.test_variant_beta", "tests.test_variant_beta_cli"),
                "evidence_note": (
                    "Statement/evidence envelopes retain provenance, context, subject scope, "
                    "missing references, and contradictory supported values without averaging; "
                    "external VA-Spec profile/schema validation remains a release gate."
                ),
            },
            "GNC-D01-C07": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.variant_beta.MultiAllelicDecomposer",),
                "test_modules": ("tests.test_variant_beta", "tests.test_variant_beta_cli"),
                "evidence_note": (
                    "Literal alternate alleles become indexed child identities with parent raw "
                    "hashes, source versions, and allele-specific genotype projections; symbolic "
                    "structural forms abstain and phasing is never inferred."
                ),
            },
            "GNC-D01-C08": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.variant_beta.RepeatAwareNormalizer",),
                "test_modules": ("tests.test_variant_beta", "tests.test_variant_beta_cli"),
                "evidence_note": (
                    "Literal SNVs and indels are replayed against a supplied local reference "
                    "window to enumerate equivalent placements and expose ambiguity; global "
                    "repeat truth sets, RefGet equivalence, and structural normalization remain."
                ),
            },
            "GNC-D02-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.structural_reconstruction.StructuralReconstructor",
                ),
                "test_modules": ("tests.test_structural_reconstruction",),
                "evidence_note": (
                    "Breakend pairing, symbolic interval checks, phased segments, and "
                    "content-addressed reconstruction are implemented; multi-event graph "
                    "supersession is still being expanded."
                ),
            },
            "GNC-D02-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.structural_extensions.SVConsensusImporter",
                ),
                "test_modules": ("tests.test_structural_extensions",),
                "evidence_note": (
                    "TSV/JSON caller observations retain versions, hashes, malformed rows, "
                    "and bounded consensus disagreement; external caller conformance is pending."
                ),
            },
            "GNC-D02-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.structural_extensions.ComplexRearrangementResolver",
                ),
                "test_modules": ("tests.test_structural_extensions",),
                "evidence_note": (
                    "Shared breakpoint components and ambiguity are retained without selecting "
                    "a canonical rearrangement identity; locked truth-set equivalence remains."
                ),
            },
            "GNC-D02-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.structural_extensions.CopyNumberSegmentHarmonizer",
                ),
                "test_modules": ("tests.test_structural_extensions",),
                "evidence_note": (
                    "Caller segments are split at observed boundaries and median values are "
                    "reported with disagreement; truth-set and transport evaluation remain."
                ),
            },
            "GNC-D02-C05": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.structural_beta.FocalAmplificationBoundaryMapper",
                ),
                "test_modules": ("tests.test_structural_beta", "tests.test_structural_beta_cli"),
                "evidence_note": (
                    "Copy-number segments are thresholded, merged only across observed gaps, "
                    "and returned with caller-specific left/right boundary support and "
                    "disagreement; sequence-level amplification truth and clinical focality "
                    "remain external validation gates."
                ),
            },
            "GNC-D02-C06": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.structural_beta.ChromothripsisPatternDetector",
                ),
                "test_modules": ("tests.test_structural_beta", "tests.test_structural_beta_cli"),
                "evidence_note": (
                    "Bounded breakpoint clusters retain orientation switches, copy-number state "
                    "oscillation, source hashes, and a descriptive evidence index; the index is "
                    "not a probability and does not establish a biological mechanism."
                ),
            },
            "GNC-D02-C07": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.structural_beta.ExtrachromosomalDnaCandidateDetector",
                ),
                "test_modules": ("tests.test_structural_beta", "tests.test_structural_beta_cli"),
                "evidence_note": (
                    "ecDNA candidates require explicit circular evidence, junction support, and "
                    "amplification evidence; conflicting linear evidence remains ambiguous and "
                    "orthogonal molecule or imaging confirmation is not inferred."
                ),
            },
            "GNC-D02-C08": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.structural_beta.EnhancerHijackingCandidateDetector",
                ),
                "test_modules": ("tests.test_structural_beta", "tests.test_structural_beta_cli"),
                "evidence_note": (
                    "Exact-context enhancer-to-gene candidates require an explicit structural "
                    "bridge, retain activity/contact channels and alternative genes, and never "
                    "use nearest-gene proximity as a substitute for linking evidence."
                ),
            },
            "GNC-D03-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.specimen_context.SpecimenOntologyMapper",),
                "test_modules": ("tests.test_specimen_context",),
                "evidence_note": (
                    "Project-local sample/specimen rows map to explicit candidates and expose "
                    "missing or conflicting subject and relationship labels; canonical ontology "
                    "equivalence fixtures remain."
                ),
            },
            "GNC-D03-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.specimen_context.MatchedNormalResolver",),
                "test_modules": ("tests.test_specimen_context",),
                "evidence_note": (
                    "Same-subject normal resolution handles unique, missing, and one-to-many "
                    "normal declarations without manufacturing a match."
                ),
            },
            "GNC-D03-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.specimen_context.PurityPloidyImporter",),
                "test_modules": ("tests.test_specimen_context",),
                "evidence_note": (
                    "TSV/JSON purity and ploidy records preserve caller versions, hashes, "
                    "percent normalization, and malformed-row quarantine."
                ),
            },
            "GNC-D03-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.specimen_context.ContaminationSwapDetector",
                ),
                "test_modules": ("tests.test_specimen_context",),
                "evidence_note": (
                    "Declared fingerprint mismatches are flagged and incomplete metrics abstain; "
                    "external benchmark calibration is not claimed."
                ),
            },
            "GNC-D04-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.reference_registry.ReferenceRegistry",),
                "test_modules": ("tests.test_reference_registry",),
                "evidence_note": (
                    "Assembly aliases, species separation, and identity/mapped/abstained "
                    "projection states are covered locally; canonical reference equivalence "
                    "fixtures remain a release gate."
                ),
            },
            "GNC-D04-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.reference_extensions.LiftoverChainManager",
                ),
                "test_modules": ("tests.test_reference_extensions",),
                "evidence_note": (
                    "Chain-like equal-length mapping segments can be imported with source "
                    "checksums and malformed-row quarantine; external chain conformance is pending."
                ),
            },
            "GNC-D04-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.reference_extensions.LiftoverAmbiguityScorer",
                ),
                "test_modules": ("tests.test_reference_extensions",),
                "evidence_note": (
                    "Absent, unique, and competing mapping candidates produce explicit states "
                    "and bounded scores without selecting a mapping."
                ),
            },
            "GNC-D04-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.reference_extensions.PangenomeCoordinateMapper",
                ),
                "test_modules": ("tests.test_reference_extensions",),
                "evidence_note": (
                    "Declared pangenome paths preserve sequence IDs and report unique, multiple, "
                    "or absent mappings; truth-set path equivalence remains."
                ),
            },
            "GNC-D05-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.atlas_extensions.CcreTrackParser",),
                "test_modules": ("tests.test_atlas_extensions",),
                "evidence_note": (
                    "ENCODE SCREEN-style cCRE TSV/JSON records preserve registry class, "
                    "versions, hashes, BED conversion, and malformed-row quarantine."
                ),
            },
            "GNC-D05-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.atlas_extensions.CcreAtlasAdapter",),
                "test_modules": ("tests.test_atlas_extensions",),
                "evidence_note": (
                    "Brain cell-type cCRE queries are context-gated and preserve absent or "
                    "out-of-domain states; external atlas evaluation is pending."
                ),
            },
            "GNC-D05-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.atlas_extensions.CcreAtlasAdapter",),
                "test_modules": ("tests.test_atlas_extensions",),
                "evidence_note": (
                    "Adult glioma cCRE queries retain source IDs and context keys without "
                    "turning overlap into a mechanistic claim."
                ),
            },
            "GNC-D05-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.atlas_extensions.CcreAtlasAdapter",),
                "test_modules": ("tests.test_atlas_extensions",),
                "evidence_note": (
                    "Pediatric glioma cCRE queries preserve pediatric context boundaries and "
                    "abstain or report out-of-domain when contexts do not match."
                ),
            },
            "GNC-D06-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.sequence_adapters.SequenceContextEncoder",
                ),
                "test_modules": ("tests.test_sequence_adapters",),
                "evidence_note": (
                    "Bounded deterministic GC, ambiguity, and k-mer context features are "
                    "content-addressed; external benchmark performance is not claimed."
                ),
            },
            "GNC-D06-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.sequence_adapters.SequenceFoundationModelAdapter",
                ),
                "test_modules": ("tests.test_sequence_adapters",),
                "evidence_note": (
                    "Foundation-model output rows preserve model/version/source metadata and "
                    "quarantine malformed or inconsistent deltas; model calibration remains."
                ),
            },
            "GNC-D06-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.sequence_adapters.LongContextVariantEffectAdapter",
                ),
                "test_modules": ("tests.test_sequence_adapters",),
                "evidence_note": (
                    "Long-context outputs require a declared minimum window and preserve "
                    "short-context failures as explicit issues."
                ),
            },
            "GNC-D06-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.sequence_adapters.RegulatoryTrackDeltaEnsemble",
                ),
                "test_modules": ("tests.test_sequence_adapters",),
                "evidence_note": (
                    "Model deltas are grouped by variant with mean, spread, model IDs, and "
                    "ambiguity states; no delta is promoted to a probability."
                ),
            },
            "GNC-D07-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_context.ChromatinTrackParser",
                    "glio_noncode.chromatin_context.ChromatinContextRetriever",
                ),
                "test_modules": ("tests.test_chromatin_context",),
                "evidence_note": (
                    "ATAC and DNase BED-like TSV/JSON observations retain coordinates, assay kind, "
                    "replicate IDs, source checksums, context keys, and malformed-row quarantine; "
                    "external schema fixtures and source anomaly evaluation remain."
                ),
            },
            "GNC-D07-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_context.AccessibilityDeltaEstimator",
                ),
                "test_modules": ("tests.test_chromatin_context",),
                "evidence_note": (
                    "Measured ATAC/DNase reference-to-alternate deltas expose relative "
                    "normalization "
                    "guards and abstain on missing measurements; external calibration, transport, "
                    "and out-of-distribution benchmarks remain."
                ),
            },
            "GNC-D07-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_context.ChromatinTrackParser",
                    "glio_noncode.chromatin_context.ChromatinContextRetriever",
                ),
                "test_modules": ("tests.test_chromatin_context",),
                "evidence_note": (
                    "Histone track observations preserve mark metadata, replicate spread, context "
                    "gating, and ambiguity; canonical source schemas and cross-assay calibration "
                    "remain."
                ),
            },
            "GNC-D07-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_context.H3K27acActivityEstimator",
                ),
                "test_modules": ("tests.test_chromatin_context",),
                "evidence_note": (
                    "H3K27ac observations are summarized with replicate-aware ambiguity and "
                    "explicit limitations; enhancer activity, target-gene linkage, and assay "
                    "calibration are "
                    "not inferred from signal alone."
                ),
            },
            "GNC-D08-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.cell_context.ContextObservationParser",
                    "glio_noncode.cell_context.DiseaseOntologyContextualizer",
                ),
                "test_modules": ("tests.test_cell_context",),
                "evidence_note": (
                    "Disease ontology observations preserve subject IDs, exact context keys, "
                    "candidate alternatives, source receipts, and context-gated abstention; "
                    "locked external benchmarks, calibration, transport, and OOD gates remain."
                ),
            },
            "GNC-D08-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.cell_context.AdultPediatricRouter",),
                "test_modules": ("tests.test_cell_context",),
                "evidence_note": (
                    "Adult and pediatric routes are taken from the declared reference context, "
                    "unknown routes abstain, and conflicting context observations are surfaced; "
                    "subgroup calibration and transport evaluation remain."
                ),
            },
            "GNC-D08-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.cell_context.MolecularClassStateContextualizer",
                ),
                "test_modules": ("tests.test_cell_context",),
                "evidence_note": (
                    "Molecular class and molecular state are resolved as separate context "
                    "dimensions with missingness, contradiction, and ambiguity retained; no "
                    "pathogenicity or treatment claim is made."
                ),
            },
            "GNC-D08-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.cell_context.MalignantMicroenvironmentTerritoryResolver",
                    "glio_noncode.cell_context.CellStateContextAssembler",
                ),
                "test_modules": ("tests.test_cell_context",),
                "evidence_note": (
                    "Territory candidates expose one-to-many mappings and the assembled "
                    "GliomaStateContext propagates ambiguity without silently selecting an "
                    "unsupported malignant or microenvironment identity."
                ),
            },
            "GNC-D09-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.topology_context.ContactMatrixParser",
                    "glio_noncode.topology_context.TadBoundaryParser",
                ),
                "test_modules": ("tests.test_topology_context",),
                "evidence_note": (
                    "Hi-C and Micro-C long-form contacts and TAD boundary rows preserve assay, "
                    "source version, raw hashes, coordinate conversion, malformed-row issues, "
                    "and context keys; locked source conformance fixtures remain."
                ),
            },
            "GNC-D09-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.topology_context.ContactMatrixQcEvaluator",
                    "glio_noncode.topology_context.ContactMatrixNormalizer",
                ),
                "test_modules": ("tests.test_topology_context",),
                "evidence_note": (
                    "Contact QC reports duplicates, zero rows, signal summaries, and explicit "
                    "partial states; mean/max transforms retain provenance and do not claim ICE "
                    "or assay-bias correction."
                ),
            },
            "GNC-D09-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.topology_context.TadBoundaryEnsembleBuilder",
                ),
                "test_modules": ("tests.test_topology_context",),
                "evidence_note": (
                    "Tolerance-bounded boundary clusters retain assay identities, competing "
                    "clusters, agreement, context gating, and ambiguity; external calibration, "
                    "negative controls, transport, and OOD evaluation remain."
                ),
            },
            "GNC-D09-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.topology_context.InsulationScoreDeltaEstimator",
                ),
                "test_modules": ("tests.test_topology_context",),
                "evidence_note": (
                    "Reference-to-alternate insulation deltas retain direction, missingness, "
                    "zero-baseline guards, replicate count, and research-use limitations; "
                    "external benchmark calibration remains."
                ),
            },
            "GNC-D10-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.link_graph.CoordinateOverlapLinker",),
                "test_modules": ("tests.test_link_graph",),
                "evidence_note": (
                    "Coordinate-overlap candidates require exact element context and preserve "
                    "source IDs, alternatives, out-of-domain overlap, and baseline limitations; "
                    "external benchmark, calibration, transport, and OOD evaluation remain."
                ),
            },
            "GNC-D10-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.link_graph.GeneFeatureParser",
                    "glio_noncode.link_graph.NearestGeneBaseline",
                ),
                "test_modules": ("tests.test_link_graph",),
                "evidence_note": (
                    "Gene intervals preserve coordinate conversion, source checksums, malformed "
                    "rows, nearest distance, ties, and distance-window abstention; nearest-gene "
                    "assignment is not presented as a mechanism."
                ),
            },
            "GNC-D10-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.link_graph.CcreElementAssigner",),
                "test_modules": ("tests.test_link_graph",),
                "evidence_note": (
                    "cCRE assignments retain every context-matched overlapping element and report "
                    "one-to-many ambiguity or context transport without silently selecting an ID."
                ),
            },
            "GNC-D10-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.link_graph.EnhancerGeneConsensusLinker",
                ),
                "test_modules": ("tests.test_link_graph",),
                "evidence_note": (
                    "Enhancer-gene consensus retains method-specific evidence, confidence-weighted "
                    "support, alternatives, single-method partial status, and contradictions; "
                    "consensus is not a causal or clinical conclusion."
                ),
            },
            "GNC-D11-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.causal_reasoning.TypedHypothesisObjectBuilder",
                ),
                "test_modules": ("tests.test_causal_reasoning",),
                "evidence_note": (
                    "Typed RegulatoryCausalHypothesis objects retain factor lineage, prior and "
                    "likelihood proxies, missing evidence, contradictions, and research-use "
                    "limitations; external task calibration and OOD evaluation remain."
                ),
            },
            "GNC-D11-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.causal_reasoning.FactorGraphConstructor",
                ),
                "test_modules": ("tests.test_causal_reasoning",),
                "evidence_note": (
                    "Immutable factor graph snapshots preserve parent lineage, supersession, "
                    "orphan diagnostics, contradiction edges, active views, and deterministic "
                    "replay; migration fixtures remain."
                ),
            },
            "GNC-D11-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.causal_reasoning.ContextConditionedPriorModel",
                ),
                "test_modules": ("tests.test_causal_reasoning",),
                "evidence_note": (
                    "Exact-context prior profiles expose bounded feature contributions, missing "
                    "features, out-of-range support, and a non-probabilistic prior score; external "
                    "calibration and transport evaluation remain."
                ),
            },
            "GNC-D11-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.causal_reasoning.MeasurementLikelihoodModel",
                ),
                "test_modules": ("tests.test_causal_reasoning",),
                "evidence_note": (
                    "Measurement channels are grouped for dependence-aware aggregation with "
                    "missing, contradictory, and context-mismatched states; the output remains "
                    "a likelihood proxy rather than a calibrated clinical probability."
                ),
            },
            "GNC-D12-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.cohort_discovery.CohortQueryBuilder",
                ),
                "test_modules": ("tests.test_cohort_discovery",),
                "evidence_note": (
                    "Cohort queries preserve exact context, variant/origin/sample criteria, "
                    "callable requirements, exclusion reasons, source IDs, and out-of-domain "
                    "transport; external task calibration remains."
                ),
            },
            "GNC-D12-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.cohort_discovery.LocalBackgroundMutationModel",
                ),
                "test_modules": ("tests.test_cohort_discovery",),
                "evidence_note": (
                    "Local background summaries retain callable bases, observed records, context "
                    "rate, target-space expectation, and small-sample uncertainty without emitting "
                    "an unvalidated significance claim."
                ),
            },
            "GNC-D12-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.cohort_discovery.SequenceContextControlMatcher",
                ),
                "test_modules": ("tests.test_cohort_discovery",),
                "evidence_note": (
                    "Sequence controls use exact context and bounded normalized Hamming distance, "
                    "preserving candidate count, distances, source IDs, and abstention/OOD states."
                ),
            },
            "GNC-D12-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.cohort_discovery.ChromatinContextControlMatcher",
                ),
                "test_modules": ("tests.test_cohort_discovery",),
                "evidence_note": (
                    "Chromatin controls use declared feature ranges and RMS distance with complete "
                    "vector requirements, context gating, candidate accounting, and explicit "
                    "negative-control limitations."
                ),
            },
            "GNC-D13-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.validation_planning.EvidenceGapAnalyzer",
                ),
                "test_modules": ("tests.test_validation_planning",),
                "evidence_note": (
                    "Typed hypotheses are converted into ranked evidence gaps with required "
                    "channels, impact, context, and review warnings; external planning benchmarks "
                    "and calibration remain."
                ),
            },
            "GNC-D13-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.validation_planning.AssayEligibilityRouter",
                ),
                "test_modules": ("tests.test_validation_planning",),
                "evidence_note": (
                    "Assay routes check model, insert, control, and readout constraints while "
                    "preserving blockers, alternatives, sensitivity, and human-review boundaries."
                ),
            },
            "GNC-D13-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.validation_planning.MPRAPlanner",),
                "test_modules": ("tests.test_validation_planning",),
                "evidence_note": (
                    "MPRA packages validate reference alleles, generate reference/alternate "
                    "constructs, enforce context and construct bounds, and retain controls and "
                    "research-use limitations."
                ),
            },
            "GNC-D13-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.validation_planning.STARRSeqPlanner",
                ),
                "test_modules": ("tests.test_validation_planning",),
                "evidence_note": (
                    "STARR-seq packages share the allele-aware bounded planner contract and block "
                    "context mismatch or construct-budget overflow without claiming assay efficacy."
                ),
            },
            "GNC-D14-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.evidence_lifecycle.VersionedEvidenceGraphConstructor",
                    "glio_noncode.evidence_lifecycle.EvidenceDossierPublisher",
                ),
                "test_modules": ("tests.test_evidence_lifecycle",),
                "evidence_note": (
                    "Immutable graph snapshots preserve claims, citations, lineage, supersession, "
                    "replay addresses, and a review-required research dossier integrity envelope; "
                    "migration fixtures and cryptographic release signing remain."
                ),
            },
            "GNC-D14-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.evidence_lifecycle.CitationResolver",
                    "glio_noncode.evidence_lifecycle.EvidenceCitation",
                ),
                "test_modules": ("tests.test_evidence_lifecycle",),
                "evidence_note": (
                    "TSV, CSV, and JSON citation fixtures retain source versions, row hashes, "
                    "raw records, and malformed-row quarantine; broader source-schema conformance "
                    "and live citation reconciliation remain."
                ),
            },
            "GNC-D14-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.evidence_lifecycle.ClaimEvidenceEdgeValidator",
                ),
                "test_modules": ("tests.test_evidence_lifecycle",),
                "evidence_note": (
                    "Edge validation checks active lineage, citation coverage, exact graph "
                    "context, "
                    "contradiction state, and abstention conditions without averaging conflicting "
                    "claims; external benchmark calibration and negative controls remain."
                ),
            },
            "GNC-D14-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.evidence_lifecycle.ContradictionDisagreementTracker",
                ),
                "test_modules": ("tests.test_evidence_lifecycle",),
                "evidence_note": (
                    "Disagreement reports retain positive and negative claims, declared value "
                    "groups, source IDs, unresolved state, and out-of-domain handling; external "
                    "adjudication benchmarks and calibrated disagreement metrics remain."
                ),
            },
            "GNC-D15-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.workspace.CaseWorkspaceBuilder",
                    "glio_noncode.workspace.WorkspaceBrowser",
                ),
                "test_modules": ("tests.test_workspace", "tests.test_cli_api"),
                "evidence_note": (
                    "Case workspaces expose immutable variant, element, hypothesis, evidence, "
                    "and validation sections with exact context, facets, pagination, and research "
                    "limitations; UI rendering and accessibility conformance remain."
                ),
            },
            "GNC-D15-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.workspace.CohortWorkspaceBuilder",),
                "test_modules": ("tests.test_workspace",),
                "evidence_note": (
                    "Cohort workspaces retain selected records, callable/background summaries, "
                    "and control candidates as separate filterable records; cohort-scale rendering "
                    "and performance benchmarks remain."
                ),
            },
            "GNC-D15-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.workspace.VariantExplorer",),
                "test_modules": ("tests.test_workspace",),
                "evidence_note": (
                    "Variant detail resolution keeps exact context, declared related records, "
                    "absent variants, and out-of-domain requests explicit; multi-view interaction "
                    "and external usability evaluation remain."
                ),
            },
            "GNC-D15-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.workspace.RegulatoryTrackBrowser",),
                "test_modules": ("tests.test_workspace", "tests.test_cli_api"),
                "evidence_note": (
                    "Regulatory tracks become interval-searchable records with source IDs, row "
                    "hashes, coordinate overlap, facets, and exact-context out-of-domain behavior; "
                    "large-track rendering and accessibility tests remain."
                ),
            },
            "GNC-D16-C01": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.mission_runtime.MissionPlanBuilder",),
                "test_modules": ("tests.test_mission_runtime",),
                "evidence_note": (
                    "Mission plans expand declared dependencies, claim ceilings, review "
                    "requirements, and registry provenance into a replayable decision; "
                    "adaptive planning benchmarks "
                    "and production policy review remain."
                ),
            },
            "GNC-D16-C02": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.mission_runtime.MissionPlanBuilder",
                    "glio_noncode.workflow.WorkflowCompiler",
                ),
                "test_modules": ("tests.test_mission_runtime", "tests.test_workflow"),
                "evidence_note": (
                    "Mission plans compile dependency-safe workflows with resource summaries and "
                    "nondeterminism/network warnings; scheduling performance and migration "
                    "fixtures "
                    "remain."
                ),
            },
            "GNC-D16-C03": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": ("glio_noncode.mission_runtime.TypedToolRegistry",),
                "test_modules": ("tests.test_mission_runtime", "tests.test_control_plane"),
                "evidence_note": (
                    "The typed registry exposes owner-checked input/output contracts, safety "
                    "class, sources, mutation scope, determinism, and review requirements for "
                    "all 96 tools; "
                    "external contract consumers and version migration remain."
                ),
            },
            "GNC-D16-C04": {
                "state": CapabilityState.PARTIAL.value,
                "implementation_modules": (
                    "glio_noncode.mission_runtime.ExecutionSandbox",
                    "glio_noncode.control_plane.ControlPlaneExecutor",
                ),
                "test_modules": ("tests.test_mission_runtime", "tests.test_control_plane"),
                "evidence_note": (
                    "Sandbox execution requires registered allowlisted handlers, local/network "
                    "isolation, policy admission, resource scheduling, provenance, event IDs, and "
                    "idempotent replay; process-level deployment hardening remains."
                ),
            },
        }
    )
