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
                    )
                    + (
                        (
                            "glio_noncode.specimen_architecture_operations.evaluate_specimen_architecture_fixture",
                            "glio_noncode.specimen_architecture_runtime.run_specimen_architecture",
                            "glio_noncode.specimen_architecture_quality.assess_specimen_architecture_quality",
                        )
                        if record.spec.capability_id.startswith("GNC-D03-")
                        else ()
                    ),
                    test_modules=tuple(str(item) for item in raw.get("test_modules", ()))
                    + (
                        (
                            "tests.test_specimen_architecture",
                            "tests.test_specimen_architecture_exports",
                        )
                        if record.spec.capability_id.startswith("GNC-D03-")
                        else ()
                    ),
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
                    "glio_noncode.intake_architecture_operations.evaluate_intake_architecture_case",
                ),
                "test_modules": (
                    "tests.test_intake",
                    "tests.test_d01_capabilities",
                    "tests.test_intake_architecture",
                ),
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
                    "glio_noncode.intake_architecture_parsing.parse_intake_architecture_case",
                ),
                "test_modules": (
                    "tests.test_intake",
                    "tests.test_bcf",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Binary BCF2 and text gVCF paths have bounded fixtures, genotype "
                    "handling, and explicit symbolic-record deferral."
                ),
            },
            "GNC-D01-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.regulatory_tracks.RegulatoryTrackParser",
                    "glio_noncode.intake_architecture_parsing.parse_regulatory_track",
                ),
                "test_modules": ("tests.test_d01_capabilities", "tests.test_intake_architecture"),
                "evidence_note": (
                    "BED, narrowPeak, GFF3, and JSON interval fixtures preserve source "
                    "coordinates, attributes, hashes, and quarantined rows."
                ),
            },
            "GNC-D01-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.variant_normalization.VRSNormalizer",
                    "glio_noncode.intake_architecture_normalization.normalize_vrs",
                ),
                "test_modules": (
                    "tests.test_d01_capabilities",
                    "tests.test_variation_fixture_eval",
                    "tests.test_variation_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "VRS-shaped Allele output, sequence-digest provenance, trimming, and "
                    "ambiguity abstention pass a public aggregate fixture with a symbolic "
                    "breakend review control; full RefGet-backed equivalence truth sets remain "
                    "a separate external validation gate."
                ),
            },
            "GNC-D01-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.variant_beta.CategoricalCatalogParser",
                    "glio_noncode.variant_beta.CatVRSNormalizer",
                    "glio_noncode.intake_architecture_normalization.normalize_cat_vrs",
                ),
                "test_modules": (
                    "tests.test_variant_beta",
                    "tests.test_variant_beta_cli",
                    "tests.test_variation_fixture_eval",
                    "tests.test_variation_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Versioned JSON/TSV/CSV categorical catalogs retain malformed rows and "
                    "support exact declared category, alias, ontology-term, and member-ID "
                    "matching in a public aggregate fixture; label-only scientific inference "
                    "and external Cat-VRS schema validation remain separate gates."
                ),
            },
            "GNC-D01-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.variant_beta.AnnotationStatement",
                    "glio_noncode.variant_beta.VAAnnotationEnvelopeBuilder",
                    "glio_noncode.intake_architecture_operations.evaluate_intake_architecture_case",
                ),
                "test_modules": (
                    "tests.test_variant_beta",
                    "tests.test_variant_beta_cli",
                    "tests.test_variation_fixture_eval",
                    "tests.test_variation_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Statement/evidence envelopes retain provenance, context, subject scope, "
                    "missing references, and contradictory supported values without averaging; "
                    "a public aggregate source receipt and context-mismatch control pass; "
                    "external VA-Spec profile/schema validation remains a release gate."
                ),
            },
            "GNC-D01-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.variant_beta.MultiAllelicDecomposer",
                    "glio_noncode.intake_architecture_parsing.parse_multiallelic",
                ),
                "test_modules": (
                    "tests.test_variant_beta",
                    "tests.test_variant_beta_cli",
                    "tests.test_variation_fixture_eval",
                    "tests.test_variation_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Literal alternate alleles become indexed child identities with parent raw "
                    "hashes, source versions, and allele-specific genotype projections; symbolic "
                    "structural forms abstain and phasing is never inferred in the public "
                    "aggregate fixture."
                ),
            },
            "GNC-D01-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.variant_beta.RepeatAwareNormalizer",
                    "glio_noncode.intake_architecture_normalization.normalize_repeat",
                ),
                "test_modules": (
                    "tests.test_variant_beta",
                    "tests.test_variant_beta_cli",
                    "tests.test_variation_fixture_eval",
                    "tests.test_variation_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Literal SNVs and indels are replayed against a supplied local reference "
                    "window to enumerate equivalent placements and expose ambiguity; the "
                    "fixture also proves reference-mismatch abstention. Global repeat truth "
                    "sets, RefGet equivalence, and structural normalization remain separate."
                ),
            },
            "GNC-D01-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.identity_beta.VariantEquivalenceResolver",
                    "glio_noncode.identity_beta.VariantIdentityRecord",
                    "glio_noncode.intake_architecture_identity.resolve_public_identity",
                ),
                "test_modules": (
                    "tests.test_identity_beta",
                    "tests.test_identity_beta_cli",
                    "tests.test_identity_fixture_eval",
                    "tests.test_identity_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Equivalence resolution normalizes build, contig, interval, allele, and "
                    "variant kind, supports explicit aliases, preserves all source records, "
                    "and returns out-of-domain and competing-key states. A public aggregate "
                    "fixture proves exact-context resolution, absent queries, and build-boundary "
                    "out-of-domain behavior; RefGet-backed truth sets and broad structural "
                    "equivalence remain separate."
                ),
            },
            "GNC-D01-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.identity_beta.DuplicateAliasReconciler",
                    "glio_noncode.identity_beta.AliasReconciliationReport",
                    "glio_noncode.intake_architecture_identity.reconcile_aliases",
                ),
                "test_modules": (
                    "tests.test_identity_beta",
                    "tests.test_identity_beta_cli",
                    "tests.test_identity_fixture_eval",
                    "tests.test_identity_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Duplicate normalized identities and explicit alias collisions are grouped "
                    "without choosing a preferred source record; ambiguous aliases, source IDs, "
                    "and ungrouped records remain visible for review. A public aggregate fixture "
                    "proves duplicate retention, ambiguous alias review, and malformed-ID "
                    "abstention without selecting a preferred source."
                ),
            },
            "GNC-D01-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.identity_beta.BatchSampleIdentityChecker",
                    "glio_noncode.identity_beta.SampleIdentityResult",
                    "glio_noncode.intake_architecture_identity.check_batch_identity",
                ),
                "test_modules": (
                    "tests.test_identity_beta",
                    "tests.test_identity_beta_cli",
                    "tests.test_identity_fixture_eval",
                    "tests.test_identity_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Batch, sample, and subject mappings retain source versions, missing fields, "
                    "cross-subject sample conflicts, batch/sample summaries, and line-addressable "
                    "issues without asserting biological authentication. A public aggregate "
                    "fixture proves a complete mapping, cross-subject contradiction, and missing "
                    "subject review with stable issue codes."
                ),
            },
            "GNC-D01-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.identity_beta.ChainOfCustodyCapture",
                    "glio_noncode.identity_beta.CustodyCaptureResult",
                    "glio_noncode.intake_architecture_provenance.build_intake_architecture_ledger",
                ),
                "test_modules": (
                    "tests.test_identity_beta",
                    "tests.test_identity_beta_cli",
                    "tests.test_identity_fixture_eval",
                    "tests.test_identity_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Custody capture records artifact event order, predecessor links, input/output "
                    "hash continuity, per-artifact digests, cross-artifact links, and broken-chain "
                    "issues; signatures, institutional custody systems, and consent enforcement "
                    "remain. A public aggregate fixture proves a three-event chain, hash-gap "
                    "contradiction, missing-link review, and invalid-timestamp abstention."
                ),
            },
            "GNC-D01-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.ConsentPolicyAttacher",
                    "glio_noncode.frontier_data_alpha.ConsentAttachmentReport",
                    "glio_noncode.intake_architecture_policy.evaluate_intake_policy",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_intake_public_data",
                    "tests.test_intake_fixture_eval",
                    "tests.test_intake_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Consent attachments retain policy identity, version, purpose, permitted uses, "
                    "record context, expiry, active-status gates, and blocked-record receipts. A "
                    "public policy/aggregate fixture proves active, withdrawn, and mismatched-context "
                    "states with source scope and exact-context auditing; institutional consent "
                    "adjudication remains external."
                ),
            },
            "GNC-D01-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.InputAnomalyQuarantine",
                    "glio_noncode.frontier_data_alpha.AnomalyQuarantineReport",
                    "glio_noncode.intake_architecture_quarantine.build_intake_quarantine",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_intake_public_data",
                    "tests.test_intake_fixture_eval",
                    "tests.test_intake_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Duplicate IDs, missing or mismatched context, invalid coordinates, and "
                    "unsupported sequence bases remain quarantined with structured reasons. A "
                    "public aggregate fixture proves duplicate-ID and invalid-sequence controls, "
                    "row retention, source traceability, and deterministic quarantine receipts."
                ),
            },
            "GNC-D01-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.DataCompletenessScorer",
                    "glio_noncode.frontier_data_alpha.CompletenessReport",
                    "glio_noncode.intake_architecture_completeness.score_intake_completeness",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_intake_public_data",
                    "tests.test_intake_fixture_eval",
                    "tests.test_intake_fixture_cli",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Weighted required-field completeness scores preserve present, missing, and "
                    "invalid fields and make review thresholds explicit. A public aggregate fixture "
                    "proves accepted coverage, missing-field review, invalid-coordinate review, "
                    "and a stable weighted score boundary."
                ),
            },
            "GNC-D01-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.IntakeBundleExporter",
                    "glio_noncode.frontier_data_alpha.IntakeBundle",
                    "glio_noncode.intake_architecture_bundle.build_intake_architecture_artifacts",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_intake_public_data",
                    "tests.test_intake_fixture_eval",
                    "tests.test_intake_fixture_cli",
                    "tests.test_intake_bundle",
                    "tests.test_intake_architecture",
                ),
                "evidence_note": (
                    "Intake bundles are deterministic, content-addressed, context-bound, and "
                    "reject blocked or quarantined records when the acceptance gate is enabled. A "
                    "public aggregate fixture proves accepted publication, blocked and cross-context "
                    "export review, compact JSON/CSV/Markdown rendering, and offline address "
                    "verification; downstream storage and publication approval remain external."
                ),
            },
            "GNC-D02-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_reconstruction.StructuralReconstructor",
                    "glio_noncode.structural_fixture_eval.evaluate_structural_fixture",
                    "glio_noncode.structural_runtime.StructuralPipeline",
                    "glio_noncode.structural_architecture_operations.evaluate_structural_architecture_fixture",
                    "glio_noncode.structural_architecture_runtime.run_structural_architecture",
                    "glio_noncode.structural_architecture_quality.evaluate_structural_architecture_quality",
                ),
                "test_modules": (
                    "tests.test_structural_reconstruction",
                    "tests.test_structural_fixture_eval",
                    "tests.test_structural_runtime",
                    "tests.test_structural_architecture",
                    "tests.test_structural_architecture_cli",
                ),
                "evidence_note": (
                    "Breakend pairing, symbolic interval checks, phased segments, and "
                    "content-addressed reconstruction are exercised through a public aggregate "
                    "fixture with reciprocal-mate, missing-mate, and non-reciprocal controls; "
                    "institutional truth-set equivalence remains external."
                ),
            },
            "GNC-D02-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_extensions.SVConsensusImporter",
                    "glio_noncode.structural_contracts.StructuralOperationContract",
                    "glio_noncode.structural_quality_gate.evaluate_structural_quality_gate",
                ),
                "test_modules": (
                    "tests.test_structural_extensions",
                    "tests.test_structural_fixture_eval",
                    "tests.test_structural_quality_gate",
                ),
                "evidence_note": (
                    "TSV/JSON caller observations retain versions, hashes, malformed rows, "
                    "and bounded consensus disagreement; positive convergence, malformed-row "
                    "quarantine, and beyond-tolerance ambiguity are replayed in a public "
                    "aggregate fixture."
                ),
            },
            "GNC-D02-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_extensions.ComplexRearrangementResolver",
                    "glio_noncode.structural_scenario_matrix.evaluate_structural_scenarios",
                    "glio_noncode.structural_bundle.StructuralEvidenceBundleBuilder",
                ),
                "test_modules": (
                    "tests.test_structural_extensions",
                    "tests.test_structural_scenario_matrix",
                    "tests.test_structural_bundle",
                ),
                "evidence_note": (
                    "Shared breakpoint components and ambiguity are retained without selecting "
                    "a canonical rearrangement identity; ambiguous shared-locus output and "
                    "no-breakpoint review controls are independently exercised and bundled."
                ),
            },
            "GNC-D02-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_extensions.CopyNumberSegmentHarmonizer",
                    "glio_noncode.structural_public_data.StructuralFixtureCatalog",
                    "glio_noncode.structural_replay.replay_structural_fixtures",
                ),
                "test_modules": (
                    "tests.test_structural_extensions",
                    "tests.test_structural_public_data",
                    "tests.test_structural_replay",
                ),
                "evidence_note": (
                    "Caller segments are split at observed boundaries and median values are "
                    "reported with disagreement; public placement scope, invalid coordinates, "
                    "negative values, deterministic replay, and compact bundle addressing are "
                    "verified while truth-set transport remains external."
                ),
            },
            "GNC-D02-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_beta.FocalAmplificationBoundaryMapper",
                    "glio_noncode.structural_beta_public_data.StructuralBetaFixtureCatalog",
                    "glio_noncode.structural_beta_fixture_eval.evaluate_structural_beta_fixture",
                    "glio_noncode.structural_beta_runtime.StructuralBetaPipeline",
                    "glio_noncode.structural_beta_bundle.StructuralBetaEvidenceBundleBuilder",
                ),
                "test_modules": (
                    "tests.test_structural_beta",
                    "tests.test_structural_beta_public_data",
                    "tests.test_structural_beta_fixture_eval",
                    "tests.test_structural_beta_quality_gate",
                    "tests.test_structural_beta_runtime",
                    "tests.test_structural_beta_cli",
                ),
                "evidence_note": (
                    "Copy-number segments are thresholded, merged only across observed gaps, "
                    "and returned with caller-specific left/right boundary support and "
                    "disagreement. The public aggregate gate exercises two positive callers, "
                    "low-copy abstention, negative-copy validation, replay, contracts, "
                    "lineage, and sanitized bundle publication; sequence-level amplification "
                    "truth and clinical focality remain external validation gates."
                ),
            },
            "GNC-D02-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_beta.ChromothripsisPatternDetector",
                    "glio_noncode.structural_beta_public_data.StructuralBetaFixtureCatalog",
                    "glio_noncode.structural_beta_fixture_eval.evaluate_structural_beta_fixture",
                    "glio_noncode.structural_beta_lineage.StructuralBetaLineageBuilder",
                    "glio_noncode.structural_beta_quality_gate.evaluate_structural_beta_quality_gate",
                ),
                "test_modules": (
                    "tests.test_structural_beta",
                    "tests.test_structural_beta_fixture_eval",
                    "tests.test_structural_beta_scenario_matrix",
                    "tests.test_structural_beta_lineage",
                    "tests.test_structural_beta_cli",
                ),
                "evidence_note": (
                    "Bounded breakpoint clusters retain orientation switches, copy-number state "
                    "oscillation, source hashes, and a descriptive evidence index. The public "
                    "aggregate gate exercises alternating positive clusters, missing-state and "
                    "far-gap controls, independent scenarios, and address-checked lineage; the "
                    "index is not a probability and does not establish a biological mechanism."
                ),
            },
            "GNC-D02-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_beta.ExtrachromosomalDnaCandidateDetector",
                    "glio_noncode.structural_beta_public_data.StructuralBetaSourceReceipt",
                    "glio_noncode.structural_beta_scenario_matrix.evaluate_structural_beta_scenarios",
                    "glio_noncode.structural_beta_contracts.StructuralBetaOperationContract",
                    "glio_noncode.structural_beta_bundle.StructuralBetaEvidenceBundleBuilder",
                ),
                "test_modules": (
                    "tests.test_structural_beta",
                    "tests.test_structural_beta_public_data",
                    "tests.test_structural_beta_scenario_matrix",
                    "tests.test_structural_beta_bundle",
                    "tests.test_structural_beta_cli",
                ),
                "evidence_note": (
                    "ecDNA candidates require explicit circular evidence, junction support, and "
                    "amplification evidence. The public aggregate gate exercises two circular "
                    "callers, high-copy-only abstention, conflicting linear evidence, scenario "
                    "replay, and compact publication; orthogonal molecule or imaging confirmation "
                    "is not inferred."
                ),
            },
            "GNC-D02-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_beta.EnhancerHijackingCandidateDetector",
                    "glio_noncode.structural_beta_public_data.StructuralBetaFixtureRecord",
                    "glio_noncode.structural_beta_fixture_eval.evaluate_structural_beta_fixture",
                    "glio_noncode.structural_beta_replay.replay_structural_beta_fixtures",
                    "glio_noncode.structural_beta_runtime.run_structural_beta_pipeline",
                ),
                "test_modules": (
                    "tests.test_structural_beta",
                    "tests.test_structural_beta_fixture_eval",
                    "tests.test_structural_beta_replay",
                    "tests.test_structural_beta_runtime",
                    "tests.test_structural_beta_cli",
                ),
                "evidence_note": (
                    "Exact-context enhancer-to-gene candidates require an explicit structural "
                    "bridge, retain activity/contact channels and alternative genes, and never "
                    "use nearest-gene proximity as a substitute for linking evidence. The public "
                    "aggregate gate exercises supported bridges, missing-bridge and context-drift "
                    "controls, runtime review propagation, replay identity, and sanitized output."
                ),
            },
            "GNC-D02-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_haplotype.PhasedHaplotypeAssembler",
                    "glio_noncode.structural_haplotype.HaplotypeAssemblyReport",
                    "glio_noncode.structural_haplotype_public_data",
                    "glio_noncode.structural_haplotype_fixture_eval",
                    "glio_noncode.structural_haplotype_contracts",
                    "glio_noncode.structural_haplotype_replay",
                    "glio_noncode.structural_haplotype_scenario_matrix",
                    "glio_noncode.structural_haplotype_quality_gate",
                    "glio_noncode.structural_haplotype_bundle",
                    "glio_noncode.structural_haplotype_lineage",
                    "glio_noncode.structural_haplotype_runtime",
                ),
                "test_modules": (
                    "tests.test_structural_haplotype",
                    "tests.test_structural_haplotype_cli",
                    "tests.test_structural_haplotype_public_data",
                    "tests.test_structural_haplotype_fixture_eval",
                    "tests.test_structural_haplotype_contracts",
                    "tests.test_structural_haplotype_replay",
                    "tests.test_structural_haplotype_scenario_matrix",
                    "tests.test_structural_haplotype_quality_gate",
                    "tests.test_structural_haplotype_bundle",
                    "tests.test_structural_haplotype_lineage",
                    "tests.test_structural_haplotype_runtime",
                ),
                "evidence_note": (
                    "Explicitly phased genotype records become ordered haplotype paths with "
                    "allele calls, phase completeness, source hashes, and retained unphased "
                    "observations. The public aggregate gate adds four positive records, "
                    "eight review controls, 72 executable assertions, replay identity, "
                    "independent scenarios, a 20-check quality gate, a 29-node lineage graph, "
                    "and a sanitized release bundle. Read-backed phasing, long-read evidence, "
                    "and sequence reconstruction remain outside this aggregate boundary."
                ),
            },
            "GNC-D02-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_haplotype.AlleleAwareSvRepresenter",
                    "glio_noncode.structural_haplotype.AlleleAwareStructuralEvent",
                    "glio_noncode.structural_haplotype_public_data",
                    "glio_noncode.structural_haplotype_fixture_eval",
                    "glio_noncode.structural_haplotype_contracts",
                    "glio_noncode.structural_haplotype_replay",
                    "glio_noncode.structural_haplotype_scenario_matrix",
                    "glio_noncode.structural_haplotype_quality_gate",
                    "glio_noncode.structural_haplotype_bundle",
                    "glio_noncode.structural_haplotype_lineage",
                    "glio_noncode.structural_haplotype_runtime",
                ),
                "test_modules": (
                    "tests.test_structural_haplotype",
                    "tests.test_structural_haplotype_cli",
                    "tests.test_structural_haplotype_public_data",
                    "tests.test_structural_haplotype_fixture_eval",
                    "tests.test_structural_haplotype_contracts",
                    "tests.test_structural_haplotype_replay",
                    "tests.test_structural_haplotype_scenario_matrix",
                    "tests.test_structural_haplotype_quality_gate",
                    "tests.test_structural_haplotype_bundle",
                    "tests.test_structural_haplotype_lineage",
                    "tests.test_structural_haplotype_runtime",
                ),
                "evidence_note": (
                    "Structural observations retain allele index, genotype dosage, zygosity, "
                    "copy number, support, and contradictory coordinates. Aggregate controls "
                    "exercise conflicting alleles and missing dosage, while receipts preserve "
                    "source/context identity and review state through runtime, replay, lineage, "
                    "and bundle boundaries. Molecule-level allele assignment and caller "
                    "truth-set validation remain."
                ),
            },
            "GNC-D02-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_haplotype.PangenomeGraphProjector",
                    "glio_noncode.structural_haplotype.GraphProjectionReport",
                    "glio_noncode.structural_haplotype_public_data",
                    "glio_noncode.structural_haplotype_fixture_eval",
                    "glio_noncode.structural_haplotype_contracts",
                    "glio_noncode.structural_haplotype_replay",
                    "glio_noncode.structural_haplotype_scenario_matrix",
                    "glio_noncode.structural_haplotype_quality_gate",
                    "glio_noncode.structural_haplotype_bundle",
                    "glio_noncode.structural_haplotype_lineage",
                    "glio_noncode.structural_haplotype_runtime",
                ),
                "test_modules": (
                    "tests.test_structural_haplotype",
                    "tests.test_structural_haplotype_cli",
                    "tests.test_structural_haplotype_public_data",
                    "tests.test_structural_haplotype_fixture_eval",
                    "tests.test_structural_haplotype_contracts",
                    "tests.test_structural_haplotype_replay",
                    "tests.test_structural_haplotype_scenario_matrix",
                    "tests.test_structural_haplotype_quality_gate",
                    "tests.test_structural_haplotype_bundle",
                    "tests.test_structural_haplotype_lineage",
                    "tests.test_structural_haplotype_runtime",
                ),
                "evidence_note": (
                    "Coordinate-bounded queries project onto supplied graph nodes and paths "
                    "with exact, contained, spanning, and ambiguous mappings. The aggregate "
                    "fixture exercises supported, ambiguous, and unmapped paths with source "
                    "receipts, deterministic replay, independent scenario checks, lineage, "
                    "and sanitized bundles. Graph sequence homology and population-scale path "
                    "validation remain."
                ),
            },
            "GNC-D02-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.structural_haplotype.RepeatMobileElementAnnotator",
                    "glio_noncode.structural_haplotype.RepeatMobileAnnotationReport",
                    "glio_noncode.structural_haplotype_public_data",
                    "glio_noncode.structural_haplotype_fixture_eval",
                    "glio_noncode.structural_haplotype_contracts",
                    "glio_noncode.structural_haplotype_replay",
                    "glio_noncode.structural_haplotype_scenario_matrix",
                    "glio_noncode.structural_haplotype_quality_gate",
                    "glio_noncode.structural_haplotype_bundle",
                    "glio_noncode.structural_haplotype_lineage",
                    "glio_noncode.structural_haplotype_runtime",
                ),
                "test_modules": (
                    "tests.test_structural_haplotype",
                    "tests.test_structural_haplotype_cli",
                    "tests.test_structural_haplotype_public_data",
                    "tests.test_structural_haplotype_fixture_eval",
                    "tests.test_structural_haplotype_contracts",
                    "tests.test_structural_haplotype_replay",
                    "tests.test_structural_haplotype_scenario_matrix",
                    "tests.test_structural_haplotype_quality_gate",
                    "tests.test_structural_haplotype_bundle",
                    "tests.test_structural_haplotype_lineage",
                    "tests.test_structural_haplotype_runtime",
                ),
                "evidence_note": (
                    "Indexed repeat intervals retain family, class, subfamily, strand, mobile "
                    "status, overlap fraction, and source versions. Mixed repeat classes and "
                    "context drift are explicit review controls, and the quality/runtime/bundle "
                    "surfaces preserve their issue codes without raw payloads. Annotation "
                    "completeness and sequence-derived transposition interpretation remain."
                ),
            },
            "GNC-D02-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.TandemRepeatInterpreter",
                    "glio_noncode.frontier_data_alpha.TandemRepeatReport",
                    "glio_noncode.structural_frontier_public_data",
                    "glio_noncode.structural_frontier_fixture_eval",
                    "glio_noncode.structural_frontier_contracts",
                    "glio_noncode.structural_frontier_replay",
                    "glio_noncode.structural_frontier_scenario_matrix",
                    "glio_noncode.structural_frontier_quality_gate",
                    "glio_noncode.structural_frontier_bundle",
                    "glio_noncode.structural_frontier_lineage",
                    "glio_noncode.structural_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_structural_frontier_cli",
                    "tests.test_structural_frontier_public_data",
                    "tests.test_structural_frontier_fixture_eval",
                    "tests.test_structural_frontier_contracts",
                    "tests.test_structural_frontier_replay",
                    "tests.test_structural_frontier_scenario_matrix",
                    "tests.test_structural_frontier_quality_gate",
                    "tests.test_structural_frontier_bundle",
                    "tests.test_structural_frontier_lineage",
                    "tests.test_structural_frontier_runtime",
                ),
                "evidence_note": (
                    "Repeat copy deltas preserve motif validation, interval checks, measurement "
                    "uncertainty, and expansion or contraction classifications. The aggregate "
                    "fixture, twelve-record evaluator, independent scenarios, twenty-check gate, "
                    "lineage graph, compact bundle, and four-stage runtime all preserve review "
                    "controls without raw payloads. Sequence-level repeat interpretation remains."
                ),
            },
            "GNC-D02-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.CompoundHaplotypeEvaluator",
                    "glio_noncode.frontier_data_alpha.HaplotypeEvaluationReport",
                    "glio_noncode.structural_frontier_public_data",
                    "glio_noncode.structural_frontier_fixture_eval",
                    "glio_noncode.structural_frontier_contracts",
                    "glio_noncode.structural_frontier_replay",
                    "glio_noncode.structural_frontier_scenario_matrix",
                    "glio_noncode.structural_frontier_quality_gate",
                    "glio_noncode.structural_frontier_bundle",
                    "glio_noncode.structural_frontier_lineage",
                    "glio_noncode.structural_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_structural_frontier_cli",
                    "tests.test_structural_frontier_public_data",
                    "tests.test_structural_frontier_fixture_eval",
                    "tests.test_structural_frontier_contracts",
                    "tests.test_structural_frontier_replay",
                    "tests.test_structural_frontier_scenario_matrix",
                    "tests.test_structural_frontier_quality_gate",
                    "tests.test_structural_frontier_bundle",
                    "tests.test_structural_frontier_lineage",
                    "tests.test_structural_frontier_runtime",
                ),
                "evidence_note": (
                    "Compound haplotypes retain required and observed alleles, missingness, phase "
                    "state, completeness, and explicit review when phase or identity is unresolved. "
                    "Positive and incomplete controls are replayable across exact contexts and "
                    "sources, with bounded export and runtime state transitions."
                ),
            },
            "GNC-D02-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.BreakpointUncertaintyPropagator",
                    "glio_noncode.frontier_data_alpha.BreakpointPropagationReport",
                    "glio_noncode.structural_frontier_public_data",
                    "glio_noncode.structural_frontier_fixture_eval",
                    "glio_noncode.structural_frontier_contracts",
                    "glio_noncode.structural_frontier_replay",
                    "glio_noncode.structural_frontier_scenario_matrix",
                    "glio_noncode.structural_frontier_quality_gate",
                    "glio_noncode.structural_frontier_bundle",
                    "glio_noncode.structural_frontier_lineage",
                    "glio_noncode.structural_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_structural_frontier_cli",
                    "tests.test_structural_frontier_public_data",
                    "tests.test_structural_frontier_fixture_eval",
                    "tests.test_structural_frontier_contracts",
                    "tests.test_structural_frontier_replay",
                    "tests.test_structural_frontier_scenario_matrix",
                    "tests.test_structural_frontier_quality_gate",
                    "tests.test_structural_frontier_bundle",
                    "tests.test_structural_frontier_lineage",
                    "tests.test_structural_frontier_runtime",
                ),
                "evidence_note": (
                    "Paired breakpoint intervals propagate left and right interval widths into a "
                    "bounded uncertainty receipt without collapsing confidence into certainty. "
                    "Inverted, low-confidence, and within-uncertainty controls are explicit, and "
                    "the graph, bundle, replay, and quality surfaces retain their decisions."
                ),
            },
            "GNC-D02-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.StructuralVariantEvidenceExporter",
                    "glio_noncode.frontier_data_alpha.StructuralEvidenceBundle",
                    "glio_noncode.structural_frontier_public_data",
                    "glio_noncode.structural_frontier_fixture_eval",
                    "glio_noncode.structural_frontier_contracts",
                    "glio_noncode.structural_frontier_replay",
                    "glio_noncode.structural_frontier_scenario_matrix",
                    "glio_noncode.structural_frontier_quality_gate",
                    "glio_noncode.structural_frontier_bundle",
                    "glio_noncode.structural_frontier_lineage",
                    "glio_noncode.structural_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_structural_frontier_cli",
                    "tests.test_structural_frontier_public_data",
                    "tests.test_structural_frontier_fixture_eval",
                    "tests.test_structural_frontier_contracts",
                    "tests.test_structural_frontier_replay",
                    "tests.test_structural_frontier_scenario_matrix",
                    "tests.test_structural_frontier_quality_gate",
                    "tests.test_structural_frontier_bundle",
                    "tests.test_structural_frontier_lineage",
                    "tests.test_structural_frontier_runtime",
                ),
                "evidence_note": (
                    "Structural evidence bundles retain required evidence identity, context, source "
                    "IDs, deterministic ordering, and a content address. Missing fields and context "
                    "drift block publication, while JSON, CSV, Markdown, lineage, and runtime "
                    "surfaces expose sanitized evidence summaries for review."
                ),
            },
            "GNC-D03-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_context.SpecimenOntologyMapper",
                    "glio_noncode.specimen_frontier_public_data.SpecimenFrontierFixtureCatalog",
                    "glio_noncode.specimen_frontier_fixture_eval.evaluate_specimen_frontier_fixture",
                    "glio_noncode.specimen_frontier_contracts.SpecimenFrontierContractRegistry",
                    "glio_noncode.specimen_frontier_replay.replay_specimen_frontier_fixtures",
                    "glio_noncode.specimen_frontier_quality_gate.evaluate_specimen_frontier_quality_gate",
                    "glio_noncode.specimen_frontier_bundle.SpecimenFrontierEvidenceBundleBuilder",
                    "glio_noncode.specimen_frontier_lineage.build_specimen_frontier_lineage",
                    "glio_noncode.specimen_frontier_runtime.run_specimen_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_specimen_context",
                    "tests.test_specimen_frontier_public_data",
                    "tests.test_specimen_frontier_fixture_eval",
                    "tests.test_specimen_frontier_contracts",
                    "tests.test_specimen_frontier_replay",
                    "tests.test_specimen_frontier_quality_gate",
                    "tests.test_specimen_frontier_bundle",
                    "tests.test_specimen_frontier_lineage",
                    "tests.test_specimen_frontier_runtime",
                    "tests.test_specimen_frontier_cli",
                ),
                "evidence_note": (
                    "Aggregate pseudonymous specimen records are checked against declared "
                    "BioSample, GDC, and ENA source receipts, exact context, deterministic "
                    "content addresses, ontology mappings, matched-normal relationships, "
                    "purity/ploidy rows, integrity results, replay, bundle, lineage, and "
                    "runtime gates."
                ),
            },
            "GNC-D03-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_context.MatchedNormalResolver",
                    "glio_noncode.specimen_frontier_public_data.SpecimenFrontierFixtureCatalog",
                    "glio_noncode.specimen_frontier_fixture_eval.evaluate_specimen_frontier_fixture",
                    "glio_noncode.specimen_frontier_contracts.SpecimenFrontierContractRegistry",
                    "glio_noncode.specimen_frontier_replay.replay_specimen_frontier_fixtures",
                    "glio_noncode.specimen_frontier_quality_gate.evaluate_specimen_frontier_quality_gate",
                    "glio_noncode.specimen_frontier_bundle.SpecimenFrontierEvidenceBundleBuilder",
                    "glio_noncode.specimen_frontier_lineage.build_specimen_frontier_lineage",
                    "glio_noncode.specimen_frontier_runtime.run_specimen_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_specimen_context",
                    "tests.test_specimen_frontier_public_data",
                    "tests.test_specimen_frontier_fixture_eval",
                    "tests.test_specimen_frontier_contracts",
                    "tests.test_specimen_frontier_replay",
                    "tests.test_specimen_frontier_quality_gate",
                    "tests.test_specimen_frontier_bundle",
                    "tests.test_specimen_frontier_lineage",
                    "tests.test_specimen_frontier_runtime",
                    "tests.test_specimen_frontier_cli",
                ),
                "evidence_note": (
                    "Matched-normal positives, missing normals, and multiple-normal controls "
                    "are evaluated from aggregate pseudonymous records with explicit result "
                    "states, issue codes, source receipts, replay, bundle, lineage, and "
                    "four-stage runtime evidence."
                ),
            },
            "GNC-D03-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_context.PurityPloidyImporter",
                    "glio_noncode.specimen_frontier_public_data.SpecimenFrontierFixtureCatalog",
                    "glio_noncode.specimen_frontier_fixture_eval.evaluate_specimen_frontier_fixture",
                    "glio_noncode.specimen_frontier_contracts.SpecimenFrontierContractRegistry",
                    "glio_noncode.specimen_frontier_replay.replay_specimen_frontier_fixtures",
                    "glio_noncode.specimen_frontier_quality_gate.evaluate_specimen_frontier_quality_gate",
                    "glio_noncode.specimen_frontier_bundle.SpecimenFrontierEvidenceBundleBuilder",
                    "glio_noncode.specimen_frontier_lineage.build_specimen_frontier_lineage",
                    "glio_noncode.specimen_frontier_runtime.run_specimen_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_specimen_context",
                    "tests.test_specimen_frontier_public_data",
                    "tests.test_specimen_frontier_fixture_eval",
                    "tests.test_specimen_frontier_contracts",
                    "tests.test_specimen_frontier_replay",
                    "tests.test_specimen_frontier_quality_gate",
                    "tests.test_specimen_frontier_bundle",
                    "tests.test_specimen_frontier_lineage",
                    "tests.test_specimen_frontier_runtime",
                    "tests.test_specimen_frontier_cli",
                ),
                "evidence_note": (
                    "Synthetic aggregate purity/ploidy rows preserve caller/version receipts, "
                    "normalized values, malformed-row quarantine, expected counts, deterministic "
                    "addresses, and review controls before bundle publication."
                ),
            },
            "GNC-D03-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_context.ContaminationSwapDetector",
                    "glio_noncode.specimen_frontier_public_data.SpecimenFrontierFixtureCatalog",
                    "glio_noncode.specimen_frontier_fixture_eval.evaluate_specimen_frontier_fixture",
                    "glio_noncode.specimen_frontier_contracts.SpecimenFrontierContractRegistry",
                    "glio_noncode.specimen_frontier_replay.replay_specimen_frontier_fixtures",
                    "glio_noncode.specimen_frontier_quality_gate.evaluate_specimen_frontier_quality_gate",
                    "glio_noncode.specimen_frontier_bundle.SpecimenFrontierEvidenceBundleBuilder",
                    "glio_noncode.specimen_frontier_lineage.build_specimen_frontier_lineage",
                    "glio_noncode.specimen_frontier_runtime.run_specimen_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_specimen_context",
                    "tests.test_specimen_frontier_public_data",
                    "tests.test_specimen_frontier_fixture_eval",
                    "tests.test_specimen_frontier_contracts",
                    "tests.test_specimen_frontier_replay",
                    "tests.test_specimen_frontier_quality_gate",
                    "tests.test_specimen_frontier_bundle",
                    "tests.test_specimen_frontier_lineage",
                    "tests.test_specimen_frontier_runtime",
                    "tests.test_specimen_frontier_cli",
                ),
                "evidence_note": (
                    "Aggregate fingerprint controls cover matching, subject mismatch, "
                    "contamination, and incomplete-metric abstention, with deterministic issue "
                    "codes, sanitization checks, source receipts, lineage, replay, and runtime "
                    "publication state."
                ),
            },
            "GNC-D03-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_beta.SomaticGermlineOriginClassifier",
                    "glio_noncode.specimen_beta_frontier_public_data.SpecimenBetaFrontierFixtureCatalog",
                    "glio_noncode.specimen_beta_frontier_fixture_eval.SpecimenBetaFrontierFixtureEvaluator",
                    "glio_noncode.specimen_beta_frontier_contracts.SpecimenBetaFrontierContractRegistry",
                    "glio_noncode.specimen_beta_frontier_replay.replay_specimen_beta_frontier_fixtures",
                    "glio_noncode.specimen_beta_frontier_quality_gate.SpecimenBetaFrontierQualityGate",
                    "glio_noncode.specimen_beta_frontier_bundle.SpecimenBetaFrontierEvidenceBundleBuilder",
                    "glio_noncode.specimen_beta_frontier_lineage.build_specimen_beta_frontier_lineage",
                    "glio_noncode.specimen_beta_frontier_runtime.run_specimen_beta_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_specimen_beta",
                    "tests.test_specimen_beta_cli",
                    "tests.test_specimen_beta_frontier_public_data",
                    "tests.test_specimen_beta_frontier_fixture_eval",
                    "tests.test_specimen_beta_frontier_contracts",
                    "tests.test_specimen_beta_frontier_replay",
                    "tests.test_specimen_beta_frontier_quality_gate",
                    "tests.test_specimen_beta_frontier_bundle",
                    "tests.test_specimen_beta_frontier_lineage",
                    "tests.test_specimen_beta_frontier_runtime",
                    "tests.test_specimen_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Aggregate variant observations retain separate tumor and normal channels, "
                    "ClinVar-shaped allele-origin vocabulary, deterministic addresses, "
                    "conflict controls, replay, bundle, lineage, and runtime evidence; "
                    "the result remains a research classification."
                ),
            },
            "GNC-D03-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_beta.MosaicismPosteriorEstimator",
                    "glio_noncode.specimen_beta_frontier_public_data.SpecimenBetaFrontierFixtureCatalog",
                    "glio_noncode.specimen_beta_frontier_fixture_eval.SpecimenBetaFrontierFixtureEvaluator",
                    "glio_noncode.specimen_beta_frontier_contracts.SpecimenBetaFrontierContractRegistry",
                    "glio_noncode.specimen_beta_frontier_replay.replay_specimen_beta_frontier_fixtures",
                    "glio_noncode.specimen_beta_frontier_quality_gate.SpecimenBetaFrontierQualityGate",
                    "glio_noncode.specimen_beta_frontier_bundle.SpecimenBetaFrontierEvidenceBundleBuilder",
                    "glio_noncode.specimen_beta_frontier_lineage.build_specimen_beta_frontier_lineage",
                    "glio_noncode.specimen_beta_frontier_runtime.run_specimen_beta_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_specimen_beta",
                    "tests.test_specimen_beta_cli",
                    "tests.test_specimen_beta_frontier_public_data",
                    "tests.test_specimen_beta_frontier_fixture_eval",
                    "tests.test_specimen_beta_frontier_contracts",
                    "tests.test_specimen_beta_frontier_replay",
                    "tests.test_specimen_beta_frontier_quality_gate",
                    "tests.test_specimen_beta_frontier_bundle",
                    "tests.test_specimen_beta_frontier_lineage",
                    "tests.test_specimen_beta_frontier_runtime",
                    "tests.test_specimen_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Repeated aggregate low-fraction tissue observations produce a deterministic "
                    "posterior-shaped estimate with contamination flags, calibration metadata, "
                    "replay, quality, bundle, lineage, and pipeline controls; uncalibrated "
                    "outputs remain explicitly uncalibrated."
                ),
            },
            "GNC-D03-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_beta.CancerCellFractionEstimator",
                    "glio_noncode.specimen_beta_frontier_public_data.SpecimenBetaFrontierFixtureCatalog",
                    "glio_noncode.specimen_beta_frontier_fixture_eval.SpecimenBetaFrontierFixtureEvaluator",
                    "glio_noncode.specimen_beta_frontier_contracts.SpecimenBetaFrontierContractRegistry",
                    "glio_noncode.specimen_beta_frontier_replay.replay_specimen_beta_frontier_fixtures",
                    "glio_noncode.specimen_beta_frontier_quality_gate.SpecimenBetaFrontierQualityGate",
                    "glio_noncode.specimen_beta_frontier_bundle.SpecimenBetaFrontierEvidenceBundleBuilder",
                    "glio_noncode.specimen_beta_frontier_lineage.build_specimen_beta_frontier_lineage",
                    "glio_noncode.specimen_beta_frontier_runtime.run_specimen_beta_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_specimen_beta",
                    "tests.test_specimen_beta_cli",
                    "tests.test_specimen_beta_frontier_public_data",
                    "tests.test_specimen_beta_frontier_fixture_eval",
                    "tests.test_specimen_beta_frontier_contracts",
                    "tests.test_specimen_beta_frontier_replay",
                    "tests.test_specimen_beta_frontier_quality_gate",
                    "tests.test_specimen_beta_frontier_bundle",
                    "tests.test_specimen_beta_frontier_lineage",
                    "tests.test_specimen_beta_frontier_runtime",
                    "tests.test_specimen_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Aggregate GDC-shaped VCF and copy-number observations preserve purity, "
                    "total CN, alternate CN, VAF, depth intervals, raw out-of-range values, "
                    "deterministic addresses, and review controls through replay, bundle, "
                    "lineage, and runtime gates."
                ),
            },
            "GNC-D03-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_beta.SubcloneAssigner",
                    "glio_noncode.specimen_beta_frontier_public_data.SpecimenBetaFrontierFixtureCatalog",
                    "glio_noncode.specimen_beta_frontier_fixture_eval.SpecimenBetaFrontierFixtureEvaluator",
                    "glio_noncode.specimen_beta_frontier_contracts.SpecimenBetaFrontierContractRegistry",
                    "glio_noncode.specimen_beta_frontier_replay.replay_specimen_beta_frontier_fixtures",
                    "glio_noncode.specimen_beta_frontier_quality_gate.SpecimenBetaFrontierQualityGate",
                    "glio_noncode.specimen_beta_frontier_bundle.SpecimenBetaFrontierEvidenceBundleBuilder",
                    "glio_noncode.specimen_beta_frontier_lineage.build_specimen_beta_frontier_lineage",
                    "glio_noncode.specimen_beta_frontier_runtime.run_specimen_beta_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_specimen_beta",
                    "tests.test_specimen_beta_cli",
                    "tests.test_specimen_beta_frontier_public_data",
                    "tests.test_specimen_beta_frontier_fixture_eval",
                    "tests.test_specimen_beta_frontier_contracts",
                    "tests.test_specimen_beta_frontier_replay",
                    "tests.test_specimen_beta_frontier_quality_gate",
                    "tests.test_specimen_beta_frontier_bundle",
                    "tests.test_specimen_beta_frontier_lineage",
                    "tests.test_specimen_beta_frontier_runtime",
                    "tests.test_specimen_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Relative within-sample CCF clusters retain cluster means, assignment "
                    "distance, invalid-row quarantine, boundary ambiguity, deterministic "
                    "addresses, replay, bundle, lineage, and runtime evidence; cluster IDs "
                    "do not claim phylogeny or named biological clones."
                ),
            },
            "GNC-D03-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_lineage.MultiRegionLineageResolver",
                    "glio_noncode.specimen_lineage.RegionLineage",
                    "glio_noncode.specimen_lineage.RegionLineageEdge",
                    "glio_noncode.specimen_lineage_public_data.SpecimenLineageFixtureCatalog",
                    "glio_noncode.specimen_lineage_fixture_eval.SpecimenLineageFixtureEvaluator",
                    "glio_noncode.specimen_lineage_lineage.SpecimenLineageGraph",
                    "glio_noncode.specimen_lineage_quality_gate.SpecimenLineageQualityGate",
                ),
                "test_modules": (
                    "tests.test_specimen_lineage",
                    "tests.test_specimen_lineage_cli",
                    "tests.test_specimen_lineage_public_data",
                    "tests.test_specimen_lineage_fixture_eval",
                    "tests.test_specimen_lineage_quality_bundle",
                ),
                "evidence_note": (
                    "Subject-local region graphs retain declared parent edges, roots, leaves, "
                    "missing parents, cycles, source hashes, and exact context; the public "
                    "aggregate fixture adds 159 assertions, replay, a 29-node/28-edge graph, "
                    "and a quality-gated bundle; specimen authentication and biological clonal "
                    "ancestry remain external."
                ),
            },
            "GNC-D03-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_lineage.LongitudinalSpecimenLinker",
                    "glio_noncode.specimen_lineage.LongitudinalLinkReport",
                    "glio_noncode.specimen_lineage_fixture_eval.SpecimenLineageFixtureEvaluator",
                    "glio_noncode.specimen_lineage_runtime.SpecimenLineagePipelineReport",
                ),
                "test_modules": (
                    "tests.test_specimen_lineage",
                    "tests.test_specimen_lineage_cli",
                    "tests.test_specimen_lineage_fixture_eval",
                    "tests.test_specimen_lineage_runtime",
                ),
                "evidence_note": (
                    "Same-subject specimen links preserve declared predecessor edges or "
                    "ordered collection times, tissue differences, gap labels, missing dates, "
                    "and source receipts; positive and review controls are independently "
                    "replayed through a four-stage runtime, and evolution and response are not inferred."
                ),
            },
            "GNC-D03-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_lineage.PrimaryRecurrencePhaseMapper",
                    "glio_noncode.specimen_lineage.PrimaryRecurrenceMappingReport",
                    "glio_noncode.specimen_lineage_contracts.SpecimenLineageOperationContract",
                    "glio_noncode.specimen_lineage_scenario_matrix.SpecimenLineageScenarioReport",
                ),
                "test_modules": (
                    "tests.test_specimen_lineage",
                    "tests.test_specimen_lineage_cli",
                    "tests.test_specimen_lineage_contracts_replay",
                    "tests.test_specimen_lineage_quality_bundle",
                ),
                "evidence_note": (
                    "Primary, recurrence, interval, and unknown assignments use explicit labels "
                    "or a declared primary predecessor; later dates alone remain unknown, "
                    "conflicting labels remain contradictory, and the scenario matrix covers "
                    "all positive and review transitions."
                ),
            },
            "GNC-D03-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.specimen_lineage.TreatmentExposureContextualizer",
                    "glio_noncode.specimen_lineage.TreatmentExposureReport",
                    "glio_noncode.specimen_lineage_bundle.SpecimenLineageEvidenceBundleBuilder",
                    "glio_noncode.specimen_lineage_replay.SpecimenLineageReplayReport",
                ),
                "test_modules": (
                    "tests.test_specimen_lineage",
                    "tests.test_specimen_lineage_cli",
                    "tests.test_specimen_lineage_quality_bundle",
                    "tests.test_specimen_lineage_runtime",
                ),
                "evidence_note": (
                    "Same-subject specimen times are compared with declared treatment intervals "
                    "to retain pre/on/post relations, overlap ambiguity, missing times, and "
                    "source versions; public GDC model receipts, bundle addresses, and runtime "
                    "stage conservation are verified, while response and resistance are not inferred."
                ),
            },
            "GNC-D03-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.BiospecimenPreanalyticQualityAssessor",
                    "glio_noncode.frontier_data_alpha.PreanalyticQualityReport",
                    "glio_noncode.specimen_preanalytic_public_data.SpecimenPreanalyticFixtureCatalog",
                    "glio_noncode.specimen_preanalytic_fixture_eval.evaluate_specimen_preanalytic_fixture",
                    "glio_noncode.specimen_preanalytic_quality_gate.evaluate_specimen_preanalytic_quality_gate",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_specimen_preanalytic_public_data",
                    "tests.test_specimen_preanalytic_fixture_eval",
                    "tests.test_specimen_preanalytic_quality_bundle",
                ),
                "evidence_note": (
                    "Preanalytic metrics are assessed against explicit min/max thresholds with "
                    "missing metrics, failed metrics, scores, and review states retained. The "
                    "public aggregate plane adds source receipts, 131 fixture checks, replay, "
                    "scenario, reconciliation, bundle, lineage, and runtime evidence."
                ),
            },
            "GNC-D03-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.AssayLineageProtocolTracker",
                    "glio_noncode.frontier_data_alpha.ProtocolLineageReport",
                    "glio_noncode.specimen_preanalytic_lineage.SpecimenPreanalyticLineageGraph",
                    "glio_noncode.specimen_preanalytic_contracts.SpecimenPreanalyticOperationContract",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_specimen_preanalytic_lineage",
                    "tests.test_specimen_preanalytic_contracts_replay",
                ),
                "evidence_note": (
                    "Assay lineage tracks specimen, protocol, operator, parent node, context, and "
                    "missing-parent conflicts in a deterministic lineage view. The release graph "
                    "contains public roots, twelve fixture records, twelve sanitized results, "
                    "typed containment edges, and address reconciliation."
                ),
            },
            "GNC-D03-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.IdentityConflictAdjudicator",
                    "glio_noncode.frontier_data_alpha.IdentityConflictReport",
                    "glio_noncode.specimen_preanalytic_replay.SpecimenPreanalyticReplayReport",
                    "glio_noncode.specimen_preanalytic_scenario_matrix.SpecimenPreanalyticScenarioReport",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_specimen_preanalytic_fixture_eval",
                    "tests.test_specimen_preanalytic_contracts_replay",
                ),
                "evidence_note": (
                    "Identity observations produce modal agreement, conflicting identifiers, ties, "
                    "and an abstaining review state below the declared agreement threshold. The "
                    "aggregate fixture retains identity-tie and conflict controls without "
                    "authenticating a specimen."
                ),
            },
            "GNC-D03-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.SpecimenContextEnvelopePublisher",
                    "glio_noncode.frontier_data_alpha.SpecimenContextEnvelope",
                    "glio_noncode.specimen_preanalytic_bundle.SpecimenPreanalyticEvidenceBundleBuilder",
                    "glio_noncode.specimen_preanalytic_runtime.run_specimen_preanalytic_pipeline",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_frontier_data_alpha_cli",
                    "tests.test_specimen_preanalytic_quality_bundle",
                    "tests.test_specimen_preanalytic_runtime",
                ),
                "evidence_note": (
                    "Specimen context envelopes bind specimen IDs, exact context, lineage, quality, "
                    "and identity receipts before publishing a content address. The public plane "
                    "adds missing-receipt controls, JSON/CSV/Markdown bundles, a four-stage runtime, "
                    "and a 25-check integrated release gate."
                ),
            },
            "GNC-D04-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_registry.ReferenceRegistry",
                    "glio_noncode.reference_coordinate_public_data.ReferenceCoordinateFixtureCatalog",
                    "glio_noncode.reference_coordinate_fixture_eval.ReferenceCoordinateFixtureEvaluator",
                    "glio_noncode.reference_coordinate_quality_gate.evaluate_reference_coordinate_quality_gate",
                ),
                "test_modules": (
                    "tests.test_reference_registry",
                    "tests.test_reference_coordinate_public_data",
                    "tests.test_reference_coordinate_fixture_eval",
                    "tests.test_reference_coordinate_quality_bundle",
                ),
                "evidence_note": (
                    "The registry resolves GRCh38/GRCh37 aliases and retains species, release, "
                    "accession, and source metadata. The public aggregate fixture adds exact "
                    "source receipts, unknown-accession controls, deterministic evaluation, "
                    "replay floors, bundle verification, lineage, reconciliation, and a "
                    "25-check integrated gate without claiming sequence equivalence."
                ),
            },
            "GNC-D04-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_extensions.LiftoverChainManager",
                    "glio_noncode.reference_coordinate_fixture_eval.ReferenceCoordinateFixtureEvaluator",
                    "glio_noncode.reference_coordinate_runtime.run_reference_coordinate_pipeline",
                ),
                "test_modules": (
                    "tests.test_reference_extensions",
                    "tests.test_reference_coordinate_fixture_eval",
                    "tests.test_reference_coordinate_runtime",
                ),
                "evidence_note": (
                    "Explicit equal-length chain-like segments are parsed with source hashes, "
                    "malformed rows remain visible, forward and reverse projections retain "
                    "mapping receipts, and controls cover unmapped and breakend abstention. "
                    "The fixture is grounded in the public UCSC chain vocabulary; it does not "
                    "pretend that a local vector is a complete downloaded chain file."
                ),
            },
            "GNC-D04-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_extensions.LiftoverAmbiguityScorer",
                    "glio_noncode.reference_coordinate_scenario_matrix.evaluate_reference_coordinate_scenarios",
                    "glio_noncode.reference_coordinate_reconciliation.reconcile_reference_coordinate_views",
                ),
                "test_modules": (
                    "tests.test_reference_extensions",
                    "tests.test_reference_coordinate_contracts_replay",
                    "tests.test_reference_coordinate_lineage",
                ),
                "evidence_note": (
                    "Absent, unique, and competing mapping candidates produce explicit states, "
                    "bounded scores, candidate IDs, and content addresses. The public controls "
                    "prove that competing segments are retained, full-interval containment is "
                    "required, and reconciliation cannot collapse ambiguity into a choice."
                ),
            },
            "GNC-D04-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_extensions.PangenomeCoordinateMapper",
                    "glio_noncode.reference_coordinate_bundle.ReferenceCoordinateBundleBuilder",
                    "glio_noncode.reference_coordinate_lineage.build_reference_coordinate_lineage",
                    "glio_noncode.reference_coordinate_runtime.run_reference_coordinate_pipeline",
                ),
                "test_modules": (
                    "tests.test_reference_extensions",
                    "tests.test_reference_coordinate_quality_bundle",
                    "tests.test_reference_coordinate_runtime",
                    "tests.test_reference_coordinate_cli",
                ),
                "evidence_note": (
                    "Declared HPRC path metadata preserves sequence IDs, path versions, source "
                    "receipts, and exact interval containment. Unique, multiple, absent, and "
                    "boundary controls are replayed through sanitized bundles, 39-node/38-edge "
                    "lineage, cross-view reconciliation, and a five-stage runtime; coordinate "
                    "containment is not treated as sequence or clinical truth."
                ),
            },
            "GNC-D04-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_beta.GencodeTranscriptAdapter",
                    "glio_noncode.reference_annotation_public_data.default_reference_annotation_fixture",
                    "glio_noncode.reference_annotation_fixture_eval.evaluate_reference_annotation_fixture",
                    "glio_noncode.reference_annotation_release.build_reference_annotation_release_manifest",
                ),
                "test_modules": (
                    "tests.test_reference_beta",
                    "tests.test_reference_annotation_public_data",
                    "tests.test_reference_annotation_fixture_eval",
                    "tests.test_reference_annotation_release",
                ),
                "evidence_note": (
                    "GENCODE-like GTF/JSON transcript records preserve transcript version, gene "
                    "identity, assembly, coordinates, attributes, source version, and malformed "
                    "rows. Five public source receipts, four record scenarios, sanitized "
                    "receipts, replay, lineage, reconciliation, and release checks verify "
                    "exact resolution and ambiguity without claiming a vendored release."
                ),
            },
            "GNC-D04-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_beta.ManeTranscriptAdapter",
                    "glio_noncode.reference_annotation_fixture_eval.evaluate_reference_annotation_fixture",
                    "glio_noncode.reference_annotation_quality_gate.evaluate_reference_annotation_quality_gate",
                    "glio_noncode.reference_annotation_runtime.run_reference_annotation_pipeline",
                ),
                "test_modules": (
                    "tests.test_reference_beta",
                    "tests.test_reference_annotation_fixture_eval",
                    "tests.test_reference_annotation_runtime",
                ),
                "evidence_note": (
                    "MANE Select/Plus Clinical TSV, CSV, and JSON records preserve RefSeq/Ensembl "
                    "cross-identifiers, status, assembly coordinates, and one-to-many resolution. "
                    "Positive, competing, missing-identifier, and unknown-query controls are "
                    "replayed through a 120-check evaluator and publication boundary."
                ),
            },
            "GNC-D04-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_beta.RegulatoryOntologyAdapter",
                    "glio_noncode.reference_annotation_contracts.default_reference_annotation_contracts",
                    "glio_noncode.reference_annotation_scenario_matrix.evaluate_reference_annotation_scenarios",
                    "glio_noncode.reference_annotation_reconciliation.reconcile_reference_annotation_views",
                ),
                "test_modules": (
                    "tests.test_reference_beta",
                    "tests.test_reference_annotation_contracts_replay",
                    "tests.test_reference_annotation_quality_bundle",
                ),
                "evidence_note": (
                    "Declared regulatory term catalogs preserve namespace, definitions, parents, "
                    "aliases, and source hashes. Exact IDs, unknown labels, duplicate IDs, and "
                    "shared aliases are covered by explicit controls; ambiguity is retained in "
                    "the bundle, graph, and reconciliation views."
                ),
            },
            "GNC-D04-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_beta.DiseaseOntologyMapper",
                    "glio_noncode.reference_annotation_bundle.ReferenceAnnotationBundleBuilder",
                    "glio_noncode.reference_annotation_lineage.build_reference_annotation_lineage",
                    "glio_noncode.reference_annotation_release.verify_reference_annotation_release_manifest",
                ),
                "test_modules": (
                    "tests.test_reference_beta",
                    "tests.test_reference_annotation_quality_bundle",
                    "tests.test_reference_annotation_release",
                    "tests.test_reference_annotation_cli",
                ),
                "evidence_note": (
                    "Disease ontology mapping catalogs retain source terms, target namespaces, "
                    "relationships, versions, and one-to-many targets. Exact mapping, multiple "
                    "target, unknown ID, and unknown label controls feed a 38-node/59-edge graph "
                    "and an independently addressed release manifest."
                ),
            },
            "GNC-D04-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_alpha.GeneAliasVersionResolver",
                    "glio_noncode.reference_alpha.GeneAliasResolutionReport",
                    "glio_noncode.reference_governance_fixture_eval.evaluate_reference_governance_fixture",
                    "glio_noncode.reference_governance_quality_gate.evaluate_reference_governance_quality_gate",
                ),
                "test_modules": (
                    "tests.test_reference_alpha",
                    "tests.test_reference_alpha_cli",
                    "tests.test_reference_governance",
                    "tests.test_reference_governance_cli",
                ),
                "evidence_note": (
                    "Public HGNC-shaped aggregate records execute exact gene ID, symbol, alias, "
                    "version, and assembly resolution with ambiguity, unknown identity, and "
                    "assembly controls; 16 receipts, replay, lineage, and release checks close "
                    "the evidence boundary."
                ),
            },
            "GNC-D04-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_alpha.PopulationFrequencyAdapter",
                    "glio_noncode.reference_alpha.PopulationFrequencyReport",
                    "glio_noncode.reference_governance_fixture_eval.evaluate_reference_governance_fixture",
                    "glio_noncode.reference_governance_metrics.build_reference_governance_metrics",
                ),
                "test_modules": (
                    "tests.test_reference_alpha",
                    "tests.test_reference_alpha_cli",
                    "tests.test_reference_governance",
                    "tests.test_reference_governance_cli",
                ),
                "evidence_note": (
                    "Public aggregate rows retain population, ancestry, AC/AN, derived or declared "
                    "frequency, genome build, source versions, and conflict controls; missing "
                    "counts and build mismatch remain review states, and frequency is not a "
                    "clinical classification."
                ),
            },
            "GNC-D04-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_alpha.ReferenceSnapshotManager",
                    "glio_noncode.reference_alpha.ReferenceSnapshot",
                    "glio_noncode.reference_governance_lineage.build_reference_governance_lineage",
                    "glio_noncode.reference_governance_release.build_reference_governance_release_manifest",
                ),
                "test_modules": (
                    "tests.test_reference_alpha",
                    "tests.test_reference_alpha_cli",
                    "tests.test_reference_governance",
                    "tests.test_reference_governance_cli",
                ),
                "evidence_note": (
                    "Public RefSeq-shaped resources form sorted content-addressed manifests with "
                    "checksums, versions, sizes, licenses, expected-hash controls, duplicate "
                    "identity controls, lineage, and release verification; resource bytes are "
                    "not fetched or validated here."
                ),
            },
            "GNC-D04-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.reference_alpha.LicenseUseRestrictionRegistry",
                    "glio_noncode.reference_alpha.LicenseEvaluationReport",
                    "glio_noncode.reference_governance_bundle.ReferenceGovernanceBundleBuilder",
                    "glio_noncode.reference_governance_quality_gate.evaluate_reference_governance_quality_gate",
                ),
                "test_modules": (
                    "tests.test_reference_alpha",
                    "tests.test_reference_alpha_cli",
                    "tests.test_reference_governance",
                    "tests.test_reference_governance_cli",
                ),
                "evidence_note": (
                    "SPDX-shaped public restriction records evaluate allowed/prohibited uses, "
                    "attribution, redistribution, commercial terms, expiry, missing permissions, "
                    "and conflicts; absent permission blocks use, and accepted-only release "
                    "bundles preserve four supported positive decisions."
                ),
            },
            "GNC-D04-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.SourceProvenanceChecker",
                    "glio_noncode.frontier_data_alpha.ProvenanceCheckReport",
                    "glio_noncode.reference_release_frontier_public_data",
                    "glio_noncode.reference_release_frontier_fixture_eval",
                    "glio_noncode.reference_release_frontier_quality_gate",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_reference_release_frontier",
                    "tests.test_reference_release_frontier_cli",
                ),
                "evidence_note": (
                    "The public C13-C16 aggregate runs matched and mismatched source receipts "
                    "through 23 data checks, 48 execution checks, replay, lineage, policy, "
                    "quality, and CLI surfaces; URI, checksum, license, context, and review "
                    "reasons remain visible."
                ),
            },
            "GNC-D04-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.AnnotationDriftDetector",
                    "glio_noncode.frontier_data_alpha.AnnotationDriftReport",
                    "glio_noncode.reference_release_frontier_fixture_eval",
                    "glio_noncode.reference_release_frontier_projection_assertions",
                    "glio_noncode.reference_release_frontier_replay",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_frontier_data_alpha_cli",
                    "tests.test_reference_release_frontier",
                ),
                "evidence_note": (
                    "Versioned annotation rows are compared field by field with ignored receipt "
                    "fields, change scores, new-row drift, stable-row controls, independent "
                    "projections, replay, and redacted release views."
                ),
            },
            "GNC-D04-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.ReproducibleReferenceBundleBuilder",
                    "glio_noncode.frontier_data_alpha.ReferenceBundle",
                    "glio_noncode.reference_release_frontier_bundle",
                    "glio_noncode.reference_release_frontier_artifacts",
                    "glio_noncode.reference_release_frontier_views",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_reference_release_frontier",
                ),
                "evidence_note": (
                    "Reference bundles retain sorted records, exact context, schema hash, "
                    "availability gates, reference IDs, and reproducible addresses; the "
                    "accepted bundle, artifact inventory, review view, and CSV/JSON exports "
                    "are independently verified."
                ),
            },
            "GNC-D04-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_data_alpha.ReferenceReleaseGate",
                    "glio_noncode.frontier_data_alpha.ReferenceReleaseDecision",
                    "glio_noncode.reference_release_frontier_policy",
                    "glio_noncode.reference_release_frontier_release",
                    "glio_noncode.reference_release_frontier_runtime",
                    "glio_noncode.reference_release_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_frontier_data_alpha",
                    "tests.test_frontier_data_alpha_cli",
                    "tests.test_reference_release_frontier",
                    "tests.test_reference_release_frontier_cli",
                ),
                "evidence_note": (
                    "Reference release decisions apply explicit checksum, schema, license, "
                    "context, and source checks with deny-by-default missing-check behavior; "
                    "the nine-stage runtime, ready manifest, review queue, threshold report, "
                    "and hosted CLI package are functionally exercised."
                ),
            },
            "GNC-D05-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_extensions.CcreTrackParser",
                    "glio_noncode.regulatory_atlas_fixture_eval.evaluate_regulatory_atlas_fixture",
                    "glio_noncode.regulatory_atlas_public_data.audit_regulatory_atlas_data",
                ),
                "test_modules": ("tests.test_atlas_extensions", "tests.test_regulatory_atlas"),
                "evidence_note": (
                    "ENCODE SCREEN-style cCRE TSV/JSON records preserve registry class, "
                    "versions, hashes, BED conversion, malformed-row quarantine, and a "
                    "public aggregate fixture with replay, lineage, policy, and release checks."
                ),
            },
            "GNC-D05-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_extensions.CcreAtlasAdapter",
                    "glio_noncode.regulatory_atlas_fixture_eval.evaluate_regulatory_atlas_fixture",
                    "glio_noncode.regulatory_atlas_quality_gate.evaluate_regulatory_atlas_quality_gate",
                ),
                "test_modules": ("tests.test_atlas_extensions", "tests.test_regulatory_atlas"),
                "evidence_note": (
                    "Brain cell-type cCRE queries are context-gated and preserve absent or "
                    "out-of-domain states; the public aggregate profile is exercised through "
                    "supported, mismatch, absent, and ambiguous scenarios."
                ),
            },
            "GNC-D05-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_extensions.CcreAtlasAdapter",
                    "glio_noncode.regulatory_atlas_fixture_eval.evaluate_regulatory_atlas_fixture",
                    "glio_noncode.regulatory_atlas_release.build_regulatory_atlas_release_manifest",
                ),
                "test_modules": ("tests.test_atlas_extensions", "tests.test_regulatory_atlas"),
                "evidence_note": (
                    "Adult glioma cCRE queries retain source IDs and context keys without "
                    "turning overlap into a mechanistic claim; accepted positives and review "
                    "controls are included in the reproducible publication boundary."
                ),
            },
            "GNC-D05-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_extensions.CcreAtlasAdapter",
                    "glio_noncode.regulatory_atlas_fixture_eval.evaluate_regulatory_atlas_fixture",
                    "glio_noncode.regulatory_atlas_runtime.run_regulatory_atlas_pipeline",
                ),
                "test_modules": ("tests.test_atlas_extensions", "tests.test_regulatory_atlas"),
                "evidence_note": (
                    "Pediatric glioma cCRE queries preserve pediatric context boundaries and "
                    "abstain or report out-of-domain when contexts do not match; pipeline "
                    "runtime and release verification preserve that boundary."
                ),
            },
            "GNC-D05-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_beta.MolecularStateAtlasAdapter",
                    "glio_noncode.molecular_atlas_fixture_eval.evaluate_molecular_atlas_fixture",
                    "glio_noncode.molecular_atlas_quality_gate.evaluate_molecular_atlas_quality_gate",
                ),
                "test_modules": ("tests.test_atlas_beta", "tests.test_molecular_atlas"),
                "evidence_note": (
                    "IDH-mutant state atlas records are stored with exact molecular state, "
                    "context, assay, signal, source version, and raw hashes; cross-state and "
                    "cross-context transport is blocked and verified through positive, absent, "
                    "mismatch, ambiguity, replay, policy, and release checks."
                ),
            },
            "GNC-D05-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_beta.MolecularStateAtlasAdapter",
                    "glio_noncode.molecular_atlas_fixture_eval.evaluate_molecular_atlas_fixture",
                    "glio_noncode.molecular_atlas_release.build_molecular_atlas_release_manifest",
                ),
                "test_modules": ("tests.test_atlas_beta", "tests.test_molecular_atlas"),
                "evidence_note": (
                    "IDH-wildtype atlas queries use the same versioned state-specific contract "
                    "and preserve out-of-domain results rather than borrowing IDH-mutant evidence; "
                    "the aggregate fixture verifies state isolation and publication closure."
                ),
            },
            "GNC-D05-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_beta.MolecularStateAtlasAdapter",
                    "glio_noncode.molecular_atlas_policy.evaluate_molecular_atlas_policy",
                    "glio_noncode.molecular_atlas_runtime.run_molecular_atlas_pipeline",
                ),
                "test_modules": ("tests.test_atlas_beta", "tests.test_molecular_atlas"),
                "evidence_note": (
                    "H3K27-altered state observations retain exact state and context keys, with "
                    "overlap ambiguity and unsupported context made explicit; age and territory "
                    "drift remain review outcomes in the C05-C08 policy plane."
                ),
            },
            "GNC-D05-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_beta.HistoneMarkTrackHarmonizer",
                    "glio_noncode.molecular_atlas_metrics.build_molecular_atlas_metrics",
                    "glio_noncode.molecular_atlas_lineage.build_molecular_atlas_lineage",
                ),
                "test_modules": ("tests.test_atlas_beta", "tests.test_molecular_atlas"),
                "evidence_note": (
                    "Histone-mark tracks are converted to atomic observed intervals with median "
                    "signal, replicate spread, callers, source versions, and disagreement states; "
                    "the result is not a calibrated activity call and now has explicit invalid-row, "
                    "single-replicate, ambiguity, replay, bundle, and release verification."
                ),
            },
            "GNC-D05-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_alpha.OpenChromatinTrackHarmonizer",
                    "glio_noncode.atlas_alpha.OpenChromatinHarmonizationReport",
                    "glio_noncode.atlas_alpha_evidence_fixture_eval.evaluate_atlas_alpha_evidence_fixture",
                    "glio_noncode.atlas_alpha_evidence_quality_gate.run_atlas_alpha_evidence_quality_gate",
                ),
                "test_modules": (
                    "tests.test_atlas_alpha",
                    "tests.test_atlas_alpha_cli",
                    "tests.test_atlas_alpha_evidence",
                ),
                "evidence_note": (
                    "Open-chromatin observations are split into atomic intervals with replicate "
                    "and caller identity, source hashes, context gating, signal spread, and "
                    "ambiguity preserved; the public aggregate C09-C12 fixture adds replay, "
                    "lineage, policy, and release floors without promoting accessibility to activity."
                ),
            },
            "GNC-D05-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_alpha.MethylationTrackHarmonizer",
                    "glio_noncode.atlas_alpha.MethylationHarmonizationReport",
                    "glio_noncode.atlas_alpha_evidence_fixture_eval.evaluate_atlas_alpha_evidence_fixture",
                    "glio_noncode.atlas_alpha_evidence_policy.evaluate_atlas_alpha_evidence_policy",
                ),
                "test_modules": (
                    "tests.test_atlas_alpha",
                    "tests.test_atlas_alpha_cli",
                    "tests.test_atlas_alpha_evidence",
                ),
                "evidence_note": (
                    "Methylation fractions retain methylated and total counts, coverage gaps, "
                    "replicate disagreement, source hashes, and exact context; silencing is not "
                    "inferred from methylation alone, and zero-coverage controls remain partial."
                ),
            },
            "GNC-D05-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_alpha.EnhancerPromoterSilencerClassifier",
                    "glio_noncode.atlas_alpha.RegulatoryRoleClassificationReport",
                    "glio_noncode.atlas_alpha_evidence_fixture_eval.evaluate_atlas_alpha_evidence_fixture",
                    "glio_noncode.atlas_alpha_evidence_scenario_matrix.evaluate_atlas_alpha_evidence_scenarios",
                ),
                "test_modules": (
                    "tests.test_atlas_alpha",
                    "tests.test_atlas_alpha_cli",
                    "tests.test_atlas_alpha_evidence",
                ),
                "evidence_note": (
                    "Declared promoter, enhancer, silencer, accessibility, methylation, contact, "
                    "and target-gene channels yield explicit multi-role, missing-channel, and "
                    "candidate states without collapsing evidence into one activity claim; the "
                    "scenario and policy layers keep role ambiguity visible."
                ),
            },
            "GNC-D05-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.atlas_alpha.SuperEnhancerCandidateAtlas",
                    "glio_noncode.atlas_alpha.SuperEnhancerAtlasReport",
                    "glio_noncode.atlas_alpha_evidence_fixture_eval.evaluate_atlas_alpha_evidence_fixture",
                    "glio_noncode.atlas_alpha_evidence_release.build_atlas_alpha_evidence_release",
                ),
                "test_modules": (
                    "tests.test_atlas_alpha",
                    "tests.test_atlas_alpha_cli",
                    "tests.test_atlas_alpha_evidence",
                ),
                "evidence_note": (
                    "Ranked enhancer constituents are grouped into proximity-bounded candidate "
                    "intervals with quantile thresholds, target-gene declarations, source hashes, "
                    "and partial activity evidence; the accepted release manifest keeps candidate "
                    "groupings explicitly non-causal."
                ),
            },
            "GNC-D05-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.InsulatorBoundaryAtlas",
                    "glio_noncode.frontier_context_alpha.BoundaryAtlasReport",
                    "glio_noncode.frontier_atlas_public_data.default_frontier_atlas_fixture",
                    "glio_noncode.frontier_atlas_fixture_eval.evaluate_frontier_atlas_fixture",
                    "glio_noncode.frontier_atlas_quality_gate.run_frontier_atlas_quality_gate",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_frontier_atlas_evidence",
                    "tests.test_frontier_atlas_evidence_cli",
                ),
                "evidence_note": (
                    "Boundary intervals retain insulation score, support, orientation, exact "
                    "context, and interval or support review states; public aggregate fixtures "
                    "exercise one accepted path plus low-support, invalid-interval, and context "
                    "controls through replay, schema, lineage, and release gates."
                ),
            },
            "GNC-D05-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.RegulatoryHotspotAtlas",
                    "glio_noncode.frontier_context_alpha.HotspotAtlasReport",
                    "glio_noncode.frontier_atlas_public_data.default_frontier_atlas_fixture",
                    "glio_noncode.frontier_atlas_fixture_eval.evaluate_frontier_atlas_fixture",
                    "glio_noncode.frontier_atlas_policy.evaluate_frontier_atlas_policy",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_frontier_atlas_evidence",
                    "tests.test_frontier_atlas_evidence_cli",
                ),
                "evidence_note": (
                    "Hotspot aggregation preserves independent sources, evidence types, direction "
                    "concordance, support count, and insufficient-source review; deterministic "
                    "fixtures expose direction disagreement, out-of-domain context, source "
                    "closure, policy, and sanitized export behavior."
                ),
            },
            "GNC-D05-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.AtlasEvidenceTierAdjudicator",
                    "glio_noncode.frontier_context_alpha.AtlasEvidenceTierReport",
                    "glio_noncode.frontier_atlas_public_data.default_frontier_atlas_fixture",
                    "glio_noncode.frontier_atlas_fixture_eval.evaluate_frontier_atlas_fixture",
                    "glio_noncode.frontier_atlas_schema.validate_frontier_atlas_schema",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_frontier_atlas_evidence",
                    "tests.test_frontier_atlas_evidence_cli",
                ),
                "evidence_note": (
                    "Atlas evidence tiers are derived from source count, consistency, and "
                    "reproducibility thresholds with low or missing evidence retained for review; "
                    "schema validation, policy vocabulary, positive and control replay, and "
                    "content-addressed metrics prevent tier labels from becoming probabilities."
                ),
            },
            "GNC-D05-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.AtlasSnapshotPublisher",
                    "glio_noncode.frontier_context_alpha.AtlasSnapshot",
                    "glio_noncode.frontier_atlas_bundle.build_frontier_atlas_bundle",
                    "glio_noncode.frontier_atlas_runtime.run_frontier_atlas_pipeline",
                    "glio_noncode.frontier_atlas_release.build_frontier_atlas_release",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_frontier_context_alpha_cli",
                    "tests.test_frontier_atlas_evidence",
                    "tests.test_frontier_atlas_evidence_cli",
                ),
                "evidence_note": (
                    "Atlas snapshots bind type, version, schema, exact context, record address, "
                    "and deterministic publication identity; a published positive snapshot, "
                    "empty abstention, context quarantine, invalid metadata control, runtime "
                    "trace, review view, and release manifest are all exercised."
                ),
            },
            "GNC-D06-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_adapters.SequenceContextEncoder",
                    "glio_noncode.sequence_effect_frontier_public_data",
                    "glio_noncode.sequence_effect_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_sequence_adapters",
                    "tests.test_sequence_effect_frontier",
                ),
                "evidence_note": (
                    "Bounded deterministic GC, ambiguity, and k-mer context features are "
                    "content-addressed with public aggregate controls, replay, schema, "
                    "lineage, and release checks; external benchmark performance is not claimed."
                ),
            },
            "GNC-D06-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_adapters.SequenceFoundationModelAdapter",
                    "glio_noncode.sequence_effect_frontier_fixture_eval",
                    "glio_noncode.sequence_effect_frontier_quality_gate",
                ),
                "test_modules": (
                    "tests.test_sequence_adapters",
                    "tests.test_sequence_effect_frontier",
                ),
                "evidence_note": (
                    "Foundation-model output rows preserve model/version/source metadata and "
                    "quarantine malformed or inconsistent deltas across positive and control "
                    "fixtures; calibration remains an explicit non-claim."
                ),
            },
            "GNC-D06-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_adapters.LongContextVariantEffectAdapter",
                    "glio_noncode.sequence_effect_frontier_schema",
                    "glio_noncode.sequence_effect_frontier_replay",
                ),
                "test_modules": (
                    "tests.test_sequence_adapters",
                    "tests.test_sequence_effect_frontier",
                ),
                "evidence_note": (
                    "Long-context outputs require a declared minimum window and preserve "
                    "short-context failures as explicit issues with deterministic replay and "
                    "schema validation."
                ),
            },
            "GNC-D06-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_adapters.RegulatoryTrackDeltaEnsemble",
                    "glio_noncode.sequence_effect_frontier_metrics",
                    "glio_noncode.sequence_effect_frontier_policy",
                ),
                "test_modules": (
                    "tests.test_sequence_adapters",
                    "tests.test_sequence_effect_frontier",
                ),
                "evidence_note": (
                    "Model deltas are grouped by variant with mean, spread, model IDs, and "
                    "ambiguity states, explicit controls, and a release policy; no delta is "
                    "promoted to a probability."
                ),
            },
            "GNC-D06-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_beta.MotifDisruptionScanner",
                    "glio_noncode.sequence_grammar_frontier_public_data",
                    "glio_noncode.sequence_grammar_frontier_adapters",
                    "glio_noncode.sequence_grammar_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_sequence_beta",
                    "tests.test_sequence_grammar_frontier",
                ),
                "evidence_note": (
                    "Declared IUPAC motif disruption scans compare reference and alternate local "
                    "windows, preserve strand, source version, sequence hashes, context, and "
                    "loss evidence; calibrated regulatory-effect performance remains pending."
                ),
            },
            "GNC-D06-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_beta.MotifCreationScanner",
                    "glio_noncode.sequence_grammar_frontier_public_data",
                    "glio_noncode.sequence_grammar_frontier_adapters",
                    "glio_noncode.sequence_grammar_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_sequence_beta",
                    "tests.test_sequence_grammar_frontier",
                ),
                "evidence_note": (
                    "Declared motif creation scans retain alternate-only hits, reference/alternate "
                    "window hashes, IUPAC source versions, strand, context, and explicit non-claim "
                    "warnings; external validation is not claimed."
                ),
            },
            "GNC-D06-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_beta.MotifSpacingGrammarAnalyzer",
                    "glio_noncode.sequence_grammar_frontier_public_data",
                    "glio_noncode.sequence_grammar_frontier_adapters",
                    "glio_noncode.sequence_grammar_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_sequence_beta",
                    "tests.test_sequence_grammar_frontier",
                ),
                "evidence_note": (
                    "Spacing and orientation rules retain every compatible motif pair, unmatched "
                    "rules, context, and ambiguity states; compatibility is not treated as proof "
                    "of cooperative binding."
                ),
            },
            "GNC-D06-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_beta.CooperativeTFGrammarModel",
                    "glio_noncode.sequence_grammar_frontier_public_data",
                    "glio_noncode.sequence_grammar_frontier_adapters",
                    "glio_noncode.sequence_grammar_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_sequence_beta",
                    "tests.test_sequence_grammar_frontier",
                ),
                "evidence_note": (
                    "Versioned cooperative grammar interactions produce a reproducible descriptive "
                    "score with per-interaction contributions and required-missing states; the "
                    "result is explicitly not a probability or clinical interpretation."
                ),
            },
            "GNC-D06-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_alpha.NucleosomeSequencePropensityModel",
                    "glio_noncode.sequence_alpha.NucleosomePropensityReport",
                    "glio_noncode.sequence_regulation_frontier_public_data.default_sequence_regulation_fixture",
                    "glio_noncode.sequence_regulation_frontier_adapters.execute_sequence_regulation_record",
                    "glio_noncode.sequence_regulation_frontier_pipeline.run_sequence_regulation_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_sequence_alpha",
                    "tests.test_sequence_alpha_cli",
                    "tests.test_sequence_regulation_frontier",
                ),
                "evidence_note": (
                    "The aggregate tranche runs phase-aware sequence features through source "
                    "receipts, positive and control records, context gates, staged quality "
                    "checks, replay, and release packaging; the result remains a transparent "
                    "index rather than calibrated occupancy."
                ),
            },
            "GNC-D06-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_alpha.SpliceRegulatoryNoncodingScanner",
                    "glio_noncode.sequence_alpha.SpliceRegulatoryScanReport",
                    "glio_noncode.sequence_regulation_frontier_public_data.default_sequence_regulation_fixture",
                    "glio_noncode.sequence_regulation_frontier_adapters.execute_sequence_regulation_record",
                    "glio_noncode.sequence_regulation_frontier_quality_gate.build_sequence_regulation_quality",
                ),
                "test_modules": (
                    "tests.test_sequence_alpha",
                    "tests.test_sequence_alpha_cli",
                    "tests.test_sequence_regulation_frontier",
                ),
                "evidence_note": (
                    "Declared splice motifs are scanned on aggregate reference and alternate "
                    "windows with source receipts, created and disrupted paths, context controls, "
                    "replay checks, and release evidence; no splice consequence is inferred."
                ),
            },
            "GNC-D06-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_alpha.UtrRegulatoryScanner",
                    "glio_noncode.sequence_alpha.UtrRegulatoryScanReport",
                    "glio_noncode.sequence_regulation_frontier_public_data.default_sequence_regulation_fixture",
                    "glio_noncode.sequence_regulation_frontier_adapters.execute_sequence_regulation_record",
                    "glio_noncode.sequence_regulation_frontier_views.build_sequence_regulation_view",
                ),
                "test_modules": (
                    "tests.test_sequence_alpha",
                    "tests.test_sequence_alpha_cli",
                    "tests.test_sequence_regulation_frontier",
                ),
                "evidence_note": (
                    "5-prime and 3-prime UTR observations and bounded upstream patterns are "
                    "wrapped with aggregate receipts, positive and control paths, ambiguity "
                    "states, review routing, and serialized views; hits are not binding, "
                    "translation, stability, or expression predictions."
                ),
            },
            "GNC-D06-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.sequence_alpha.PromoterCoreGrammarModel",
                    "glio_noncode.sequence_alpha.PromoterCoreGrammarReport",
                    "glio_noncode.sequence_regulation_frontier_public_data.default_sequence_regulation_fixture",
                    "glio_noncode.sequence_regulation_frontier_adapters.execute_sequence_regulation_record",
                    "glio_noncode.sequence_regulation_frontier_release.build_sequence_regulation_release",
                ),
                "test_modules": (
                    "tests.test_sequence_alpha",
                    "tests.test_sequence_alpha_cli",
                    "tests.test_sequence_regulation_frontier",
                ),
                "evidence_note": (
                    "Declared promoter motif pairs are evaluated by spacing, orientation, weighted "
                    "coverage, source receipts, competing-pair controls, lineage, replay, and "
                    "release gates; grammar compatibility is not promoter activity or initiation "
                    "evidence."
                ),
            },
            "GNC-D06-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.EnhancerGrammarModel",
                    "glio_noncode.frontier_context_alpha.EnhancerGrammarReport",
                    "glio_noncode.sequence_frontier_public_data.default_sequence_frontier_fixture",
                    "glio_noncode.sequence_frontier_fixture_eval.evaluate_sequence_frontier_fixture",
                    "glio_noncode.sequence_frontier_quality_gate.run_sequence_frontier_quality_gate",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_sequence_frontier_evidence",
                    "tests.test_sequence_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Motif-pair grammar evaluates declared spacing rules, motif coverage, compatible "
                    "pairs, and minimum-coverage review boundaries. The public aggregate fixture "
                    "adds explicit positive and control states, source closure, schema validation, "
                    "replay, and release quality checks."
                ),
            },
            "GNC-D06-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.AlleleSaturationSimulator",
                    "glio_noncode.frontier_context_alpha.AlleleSaturationReport",
                    "glio_noncode.sequence_frontier_fixture_eval.evaluate_sequence_frontier_fixture",
                    "glio_noncode.sequence_frontier_policy.evaluate_sequence_frontier_policy",
                    "glio_noncode.sequence_frontier_schema.validate_sequence_frontier_schema",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_sequence_frontier_evidence",
                    "tests.test_sequence_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Declared alternate alleles are scored against an explicit reference with "
                    "effect deltas and uncertainty-aware review states. The sequence frontier "
                    "contract bounds alternate points, uncertainty floors, and non-effect claims."
                ),
            },
            "GNC-D06-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.EnsembleDisagreementQuantifier",
                    "glio_noncode.frontier_context_alpha.EnsembleDisagreementReport",
                    "glio_noncode.sequence_frontier_fixture_eval.evaluate_sequence_frontier_fixture",
                    "glio_noncode.sequence_frontier_metrics.compute_sequence_frontier_metrics",
                    "glio_noncode.sequence_frontier_views.build_sequence_frontier_view",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_sequence_frontier_evidence",
                    "tests.test_sequence_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Ensemble mean, standard deviation, interval, range disagreement, and review "
                    "thresholds remain explicit for every prediction ID. Metrics, review views, "
                    "trace stages, and CSV outputs preserve descriptive disagreement without "
                    "converting spread into calibrated probability."
                ),
            },
            "GNC-D06-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.SequenceEvidencePublisher",
                    "glio_noncode.frontier_context_alpha.SequenceEvidenceBundle",
                    "glio_noncode.sequence_frontier_bundle.build_sequence_frontier_bundle",
                    "glio_noncode.sequence_frontier_runtime.run_sequence_frontier_pipeline",
                    "glio_noncode.sequence_frontier_release.build_sequence_frontier_release",
                    "glio_noncode.sequence_frontier_exports.export_sequence_frontier_receipts_csv",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_sequence_frontier_evidence",
                    "tests.test_sequence_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Sequence evidence bundles retain model IDs, sequence IDs, exact context, "
                    "record address, and publication address. The release path adds lineage, "
                    "reconciliation, quality gates, observability, replay, sanitized exports, "
                    "and deterministic command boundaries."
                ),
            },
            "GNC-D07-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_context.ChromatinTrackParser",
                    "glio_noncode.chromatin_context.ChromatinContextRetriever",
                    "glio_noncode.chromatin_context_frontier_public_data.default_chromatin_context_frontier_fixture",
                    "glio_noncode.chromatin_context_frontier_adapters.execute_chromatin_context_frontier_record",
                    "glio_noncode.chromatin_context_frontier_pipeline.run_chromatin_context_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_chromatin_context",
                    "tests.test_chromatin_context_frontier",
                ),
                "evidence_note": (
                    "ATAC and DNase BED-like TSV/JSON observations retain coordinates, assay kind, "
                    "replicate IDs, source checksums, context keys, and malformed-row quarantine; "
                    "the public aggregate C01-C04 plane adds schema, source, replay, review, and "
                    "release checks while external source anomaly evaluation remains."
                ),
            },
            "GNC-D07-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_context.AccessibilityDeltaEstimator",
                    "glio_noncode.chromatin_context_frontier_adapters.execute_chromatin_context_frontier_record",
                    "glio_noncode.chromatin_context_frontier_metrics.build_chromatin_context_frontier_metrics",
                    "glio_noncode.chromatin_context_frontier_quality_gate.build_chromatin_context_frontier_quality",
                ),
                "test_modules": (
                    "tests.test_chromatin_context",
                    "tests.test_chromatin_context_frontier",
                ),
                "evidence_note": (
                    "Measured ATAC/DNase reference-to-alternate deltas expose relative "
                    "normalization guards and abstain on missing measurements; the public "
                    "aggregate plane verifies zero-baseline, missingness, context refusal, and "
                    "release receipts while external calibration remains."
                ),
            },
            "GNC-D07-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_context.ChromatinTrackParser",
                    "glio_noncode.chromatin_context.ChromatinContextRetriever",
                    "glio_noncode.chromatin_context_frontier_public_data.default_chromatin_context_frontier_fixture",
                    "glio_noncode.chromatin_context_frontier_views.build_chromatin_context_frontier_view",
                    "glio_noncode.chromatin_context_frontier_review_queue.build_chromatin_context_frontier_review_queue",
                ),
                "test_modules": (
                    "tests.test_chromatin_context",
                    "tests.test_chromatin_context_frontier",
                ),
                "evidence_note": (
                    "Histone track observations preserve mark metadata, replicate spread, context "
                    "gating, and ambiguity; the public aggregate plane adds source registry, "
                    "review routing, deterministic replay, and explicit cross-assay limits."
                ),
            },
            "GNC-D07-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_context.H3K27acActivityEstimator",
                    "glio_noncode.chromatin_context_frontier_adapters.execute_chromatin_context_frontier_record",
                    "glio_noncode.chromatin_context_frontier_reports.build_chromatin_context_frontier_report",
                    "glio_noncode.chromatin_context_frontier_exports.export_chromatin_context_frontier_manifest",
                ),
                "test_modules": (
                    "tests.test_chromatin_context",
                    "tests.test_chromatin_context_frontier",
                ),
                "evidence_note": (
                    "H3K27ac observations are summarized with replicate-aware ambiguity and "
                    "explicit limitations; the public aggregate plane verifies activity "
                    "observation, abstention, refusal, review, and export boundaries. Enhancer "
                    "activity, target-gene linkage, and assay calibration are not inferred from "
                    "signal alone."
                ),
            },
            "GNC-D07-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.methylation_beta.MethylationRecordParser",
                    "glio_noncode.methylation_beta.MethylationContextRetriever",
                    "glio_noncode.methylation_frontier_public_data.default_methylation_frontier_fixture",
                    "glio_noncode.methylation_frontier_pipeline.run_methylation_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_methylation_beta",
                    "tests.test_methylation_beta_cli",
                    "tests.test_methylation_frontier",
                ),
                "evidence_note": (
                    "One-based or BED-like methylation records preserve beta values, coverage, "
                    "assay/sample/replicate metadata, source versions, raw hashes, exact context "
                    "queries, replicate spread, and out-of-domain context. The public aggregate "
                    "tranche adds source receipts, controls, replay, review routing, and release checks."
                ),
            },
            "GNC-D07-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.methylation_beta.CpGCreationLossAnalyzer",
                    "glio_noncode.methylation_frontier_adapters.execute_methylation_frontier_record",
                    "glio_noncode.methylation_frontier_quality_gate.build_methylation_frontier_quality",
                ),
                "test_modules": (
                    "tests.test_methylation_beta",
                    "tests.test_methylation_beta_cli",
                    "tests.test_methylation_frontier",
                ),
                "evidence_note": (
                    "Equal-length allele windows yield coordinate-safe CpG creation/loss "
                    "events and optionally attach exact methylation records; "
                    "length-changing windows abstain and "
                    "sequence changes are not treated as functional effects. Positive and "
                    "control fixture paths verify creation, loss, invalid, bounded, and "
                    "abstention behavior."
                ),
            },
            "GNC-D07-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.methylation_beta.MethylationSensitiveMotifAnalyzer",
                    "glio_noncode.methylation_frontier_views.build_methylation_frontier_review_view",
                    "glio_noncode.methylation_frontier_replay.replay_methylation_frontier",
                ),
                "test_modules": (
                    "tests.test_methylation_beta",
                    "tests.test_methylation_beta_cli",
                    "tests.test_methylation_frontier",
                ),
                "evidence_note": (
                    "Declared IUPAC motif hits retain zero-based sensitive offsets, strand, exact "
                    "methylation beta measurements, missingness, disagreement, source versions, "
                    "and context; binding or regulatory effect is not inferred. Review-safe "
                    "views retain motif, methylation, issue, context, and receipt fields."
                ),
            },
            "GNC-D07-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.methylation_beta.IdhHypermethylationContextModel",
                    "glio_noncode.methylation_frontier_source_registry.build_methylation_frontier_source_registry",
                    "glio_noncode.methylation_frontier_release.build_methylation_frontier_release",
                ),
                "test_modules": (
                    "tests.test_methylation_beta",
                    "tests.test_methylation_beta_cli",
                    "tests.test_methylation_frontier",
                ),
                "evidence_note": (
                    "Versioned IDH-mutant versus IDH-wildtype panel summaries expose thresholded "
                    "hypermethylation, coverage-weighted beta, comparator delta, source versions, "
                    "and minimum-site abstention; this is not a diagnostic classifier. The "
                    "aggregate release adds lineage, policy, reconciliation, review, replay, "
                    "and content-addressed bundle checks."
                ),
            },
            "GNC-D07-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_alpha.ChromatinStateSegmentationAdapter",
                    "glio_noncode.chromatin_alpha.ChromatinSegmentationReport",
                    "glio_noncode.chromatin_alpha_frontier_public_data.default_chromatin_alpha_frontier_fixture",
                    "glio_noncode.chromatin_alpha_frontier_pipeline.run_chromatin_alpha_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_chromatin_alpha",
                    "tests.test_chromatin_alpha_cli",
                    "tests.test_chromatin_alpha_frontier",
                ),
                "evidence_note": (
                    "Context-qualified chromatin intervals are split at observed boundaries and "
                    "assigned transparent open/intermediate/closed labels with replicate support, "
                    "signal spread, source hashes, and mixed-state ambiguity retained. The public "
                    "C09-C12 tranche adds aggregate controls, lineage, replay, policy, and release gates."
                ),
            },
            "GNC-D07-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_alpha.AlleleSpecificChromatinAnalyzer",
                    "glio_noncode.chromatin_alpha.AlleleSpecificChromatinReport",
                    "glio_noncode.chromatin_alpha_frontier_adapters.execute_chromatin_alpha_frontier_record",
                    "glio_noncode.chromatin_alpha_frontier_quality_gate.build_chromatin_alpha_frontier_quality",
                ),
                "test_modules": (
                    "tests.test_chromatin_alpha",
                    "tests.test_chromatin_alpha_cli",
                    "tests.test_chromatin_alpha_frontier",
                ),
                "evidence_note": (
                    "Reference/alternate chromatin signals are summarized per variant and assay "
                    "with replicate-aware deltas, directions, missingness, mixed-direction states, "
                    "context gates, and source hashes; deltas are not causal effects. Positive and "
                    "control paths now verify supported, mixed, foreign-context, and malformed states."
                ),
            },
            "GNC-D07-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_alpha.EpigenomicPurityDeconvolver",
                    "glio_noncode.chromatin_alpha.EpigenomicPurityReport",
                    "glio_noncode.chromatin_alpha_frontier_views.build_chromatin_alpha_frontier_view",
                    "glio_noncode.chromatin_alpha_frontier_replay.replay_chromatin_alpha_frontier",
                ),
                "test_modules": (
                    "tests.test_chromatin_alpha",
                    "tests.test_chromatin_alpha_cli",
                    "tests.test_chromatin_alpha_frontier",
                ),
                "evidence_note": (
                    "Declared tumor/normal epigenomic reference markers produce bounded mixture "
                    "estimates with marker denominators, clipping visibility, spread, minimum-site "
                    "gates, and context/source provenance; this is not a clinical purity call. The "
                    "aggregate view retains marker counts, estimates, spread, review decisions, and receipts."
                ),
            },
            "GNC-D07-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.chromatin_alpha.BatchCellCompositionCorrector",
                    "glio_noncode.chromatin_alpha.BatchCompositionCorrectionReport",
                    "glio_noncode.chromatin_alpha_frontier_runtime.run_chromatin_alpha_frontier_runtime",
                    "glio_noncode.chromatin_alpha_frontier_release.build_chromatin_alpha_frontier_release",
                ),
                "test_modules": (
                    "tests.test_chromatin_alpha",
                    "tests.test_chromatin_alpha_cli",
                    "tests.test_chromatin_alpha_frontier",
                ),
                "evidence_note": (
                    "Declared batch offsets and cell-composition coefficients retain raw signal, "
                    "batch and composition adjustment terms, target composition, missing-parameter "
                    "partial states, and source hashes; corrected values remain descriptive. The "
                    "release plane adds source registry, quality gate, review queue, validation matrix, "
                    "and content-addressed results."
                ),
            },
            "GNC-D07-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.ContextImputationWithConfidence",
                    "glio_noncode.frontier_context_alpha.ContextImputationReport",
                    "glio_noncode.chromatin_frontier_public_data.default_chromatin_frontier_fixture",
                    "glio_noncode.chromatin_frontier_fixture_eval.evaluate_chromatin_frontier_fixture",
                    "glio_noncode.chromatin_frontier_quality_gate.run_chromatin_frontier_quality_gate",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_chromatin_frontier_evidence",
                    "tests.test_chromatin_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Missing chromatin context values use only declared priors and preserve source, "
                    "confidence, and low-confidence review states. The public aggregate fixture "
                    "adds interval segmentation, replicate controls, source closure, schema "
                    "validation, replay, lineage, reconciliation, and release quality checks."
                ),
            },
            "GNC-D07-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.AssaySupportCoverageGate",
                    "glio_noncode.frontier_context_alpha.AssayCoverageReport",
                    "glio_noncode.chromatin_frontier_fixture_eval.evaluate_chromatin_frontier_fixture",
                    "glio_noncode.chromatin_frontier_policy.evaluate_chromatin_frontier_policy",
                    "glio_noncode.chromatin_frontier_schema.validate_chromatin_frontier_schema",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_chromatin_frontier_evidence",
                    "tests.test_chromatin_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Assay support gates retain required/observed assay IDs, missing assays, and "
                    "coverage thresholds before interpretation. Allele-specific chromatin "
                    "comparisons retain replicate deltas and mixed-direction review states."
                ),
            },
            "GNC-D07-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.CrossAssayConcordanceAdjudicator",
                    "glio_noncode.frontier_context_alpha.ConcordanceReport",
                    "glio_noncode.chromatin_frontier_fixture_eval.evaluate_chromatin_frontier_fixture",
                    "glio_noncode.chromatin_frontier_metrics.compute_chromatin_frontier_metrics",
                    "glio_noncode.chromatin_frontier_views.build_chromatin_frontier_view",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_chromatin_frontier_evidence",
                    "tests.test_chromatin_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Cross-assay directions are reduced to a declared mode and concordance with "
                    "insufficient-assay and disagreement review paths. Epigenomic purity retains "
                    "marker-level bounded estimates, spread, denominator abstention, and export "
                    "metrics without a clinical purity claim."
                ),
            },
            "GNC-D07-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.ChromatinEvidencePublisher",
                    "glio_noncode.frontier_context_alpha.ChromatinEvidenceBundle",
                    "glio_noncode.chromatin_frontier_bundle.build_chromatin_frontier_bundle",
                    "glio_noncode.chromatin_frontier_runtime.run_chromatin_frontier_pipeline",
                    "glio_noncode.chromatin_frontier_release.build_chromatin_frontier_release",
                    "glio_noncode.chromatin_frontier_exports.export_chromatin_frontier_receipts_csv",
                ),
                "test_modules": (
                    "tests.test_frontier_context_alpha",
                    "tests.test_chromatin_frontier_evidence",
                    "tests.test_chromatin_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Chromatin bundles bind feature IDs, assay IDs, exact context, record address, "
                    "and publication address. The release path adds batch/composition correction "
                    "terms, review views, nine-stage trace, source lineage, reconciliation, "
                    "sanitized exports, replay, and a deterministic release manifest."
                ),
            },
            "GNC-D08-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context.ContextObservationParser",
                    "glio_noncode.cell_context.DiseaseOntologyContextualizer",
                    "glio_noncode.cell_context_frontier_disease.profile_disease_context_resolution",
                    "glio_noncode.cell_context_frontier_public_data.default_cell_context_frontier_fixture",
                    "glio_noncode.cell_context_frontier_pipeline.run_cell_context_frontier_pipeline",
                ),
                "test_modules": ("tests.test_cell_context", "tests.test_cell_context_frontier"),
                "evidence_note": (
                    "Disease ontology observations preserve subject IDs, exact context keys, "
                    "candidate alternatives, source receipts, and context-gated abstention; "
                    "the public aggregate C01-C04 plane adds depth scoring, source closure, "
                    "replay, review, and release checks while external calibration remains."
                ),
            },
            "GNC-D08-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context.AdultPediatricRouter",
                    "glio_noncode.cell_context_frontier_age.profile_age_route_resolution",
                    "glio_noncode.cell_context_frontier_review_queue.build_cell_context_frontier_review_queue",
                ),
                "test_modules": ("tests.test_cell_context", "tests.test_cell_context_frontier"),
                "evidence_note": (
                    "Adult and pediatric routes are taken from the declared reference context, "
                    "unknown routes abstain, and conflicting context observations are surfaced. "
                    "The public aggregate plane verifies conflict routing, refusal, review, and "
                    "bounded release behavior while subgroup transport evaluation remains."
                ),
            },
            "GNC-D08-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context.MolecularClassStateContextualizer",
                    "glio_noncode.cell_context_frontier_molecular.profile_molecular_context_resolution",
                    "glio_noncode.cell_context_frontier_depth.audit_cell_context_frontier_depth",
                ),
                "test_modules": ("tests.test_cell_context", "tests.test_cell_context_frontier"),
                "evidence_note": (
                    "Molecular class and molecular state are resolved as separate context "
                    "dimensions with missingness, contradiction, and ambiguity retained. The "
                    "aggregate tranche adds state matrices, uncertainty depth, source receipts, "
                    "review routing, and deterministic replay; no pathogenicity or treatment "
                    "claim is made."
                ),
            },
            "GNC-D08-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context.MalignantMicroenvironmentTerritoryResolver",
                    "glio_noncode.cell_context.CellStateContextAssembler",
                    "glio_noncode.cell_context_frontier_territory.profile_territory_context_resolution",
                    "glio_noncode.cell_context_frontier_integrity.evaluate_cell_context_frontier_integrity",
                    "glio_noncode.cell_context_frontier_pipeline.run_cell_context_frontier_pipeline",
                ),
                "test_modules": ("tests.test_cell_context", "tests.test_cell_context_frontier"),
                "evidence_note": (
                    "Territory candidates expose one-to-many mappings and the assembled "
                    "GliomaStateContext propagates ambiguity without silently selecting an "
                    "unsupported malignant or microenvironment identity. The aggregate release "
                    "adds assembly depth, weakest-component integrity, review queue, and export "
                    "receipts."
                ),
            },
            "GNC-D08-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context_beta.DevelopmentalLineagePrior",
                    "glio_noncode.cell_context_beta_frontier_public_data",
                    "glio_noncode.cell_context_beta_frontier_adapters",
                    "glio_noncode.cell_context_beta_frontier_fixture_eval",
                    "glio_noncode.cell_context_beta_frontier_contracts",
                    "glio_noncode.cell_context_beta_frontier_schema",
                    "glio_noncode.cell_context_beta_frontier_metrics",
                    "glio_noncode.cell_context_beta_frontier_policy",
                    "glio_noncode.cell_context_beta_frontier_quality_gate",
                    "glio_noncode.cell_context_beta_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_cell_context_beta",
                    "tests.test_cell_context_beta_cli",
                    "tests.test_cell_context_beta_frontier",
                ),
                "evidence_note": (
                    "Adult/pediatric developmental-lineage priors aggregate exact-context, "
                    "versioned candidate observations with bounded support, uncertainty, source "
                    "receipts, ambiguity margins, and explicit non-diagnostic limitations."
                ),
            },
            "GNC-D08-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context_beta.GlioblastomaMalignantStatePrior",
                    "glio_noncode.cell_context_beta_frontier_gate_depth",
                    "glio_noncode.cell_context_beta_frontier_candidate_depth",
                    "glio_noncode.cell_context_beta_frontier_depth",
                    "glio_noncode.cell_context_beta_frontier_lineage",
                    "glio_noncode.cell_context_beta_frontier_reconciliation",
                    "glio_noncode.cell_context_beta_frontier_release",
                    "glio_noncode.cell_context_beta_frontier_bundle",
                    "glio_noncode.cell_context_beta_frontier_artifacts",
                    "glio_noncode.cell_context_beta_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_cell_context_beta",
                    "tests.test_cell_context_beta_cli",
                    "tests.test_cell_context_beta_frontier",
                ),
                "evidence_note": (
                    "Glioblastoma malignant-state priors require an explicit glioblastoma/GBM "
                    "disease gate, preserve competing state candidates and contradiction, and do "
                    "not convert a state prior into a diagnosis."
                ),
            },
            "GNC-D08-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context_beta.IdhMutantLineageStatePrior",
                    "glio_noncode.cell_context_beta_frontier_public_data",
                    "glio_noncode.cell_context_beta_frontier_source_registry",
                    "glio_noncode.cell_context_beta_frontier_observability",
                    "glio_noncode.cell_context_beta_frontier_replay",
                    "glio_noncode.cell_context_beta_frontier_exports",
                    "glio_noncode.cell_context_beta_frontier_views",
                    "glio_noncode.cell_context_beta_frontier_review_queue",
                    "glio_noncode.cell_context_beta_frontier_reports",
                    "glio_noncode.cell_context_beta_frontier_runbook",
                ),
                "test_modules": (
                    "tests.test_cell_context_beta",
                    "tests.test_cell_context_beta_cli",
                    "tests.test_cell_context_beta_frontier",
                ),
                "evidence_note": (
                    "IDH-mutant lineage/state priors require a declared molecular-state gate and "
                    "retain exact context, evidence tiers, support summaries, uncertainty, and "
                    "out-of-domain IDH-wildtype requests."
                ),
            },
            "GNC-D08-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context_beta.H3K27AlteredDevelopmentalStatePrior",
                    "glio_noncode.cell_context_beta_frontier_compliance",
                    "glio_noncode.cell_context_beta_frontier_checks",
                    "glio_noncode.cell_context_beta_frontier_thresholds",
                    "glio_noncode.cell_context_beta_frontier_validation_matrix",
                    "glio_noncode.cell_context_beta_frontier_scenario_matrix",
                    "glio_noncode.cell_context_beta_frontier_accessibility",
                    "glio_noncode.cell_context_beta_frontier_integrity",
                    "glio_noncode.cell_context_beta_frontier_catalog",
                    "glio_noncode.cell_context_beta_frontier_cli",
                    "glio_noncode.cell_context_beta_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_cell_context_beta",
                    "tests.test_cell_context_beta_cli",
                    "tests.test_cell_context_beta_frontier",
                ),
                "evidence_note": (
                    "H3K27-altered developmental-state priors preserve declared state gates, "
                    "candidate alternatives, source versions, ambiguity, and bounded research-use "
                    "limitations without inferring developmental identity clinically."
                ),
            },
            "GNC-D08-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context_alpha.SpatialNichePrior",
                    "glio_noncode.cell_context_alpha.SpatialNichePriorReport",
                    "glio_noncode.cell_context_alpha_frontier_public_data.CellContextAlphaFrontierFixture",
                    "glio_noncode.cell_context_alpha_frontier_adapters.execute_cell_context_alpha_frontier_record",
                    "glio_noncode.cell_context_alpha_frontier_candidate_depth.audit_cell_context_alpha_frontier_candidates",
                    "glio_noncode.cell_context_alpha_frontier_depth.audit_cell_context_alpha_frontier_depth",
                    "glio_noncode.cell_context_alpha_frontier_pipeline.run_cell_context_alpha_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_cell_context_alpha",
                    "tests.test_cell_context_alpha_cli",
                    "tests.test_cell_context_alpha_frontier",
                ),
                "evidence_note": (
                    "Spatial niche candidates are ranked within subject and exact context while "
                    "retaining support spread, close-candidate ambiguity, sample IDs, source "
                    "versions, raw hashes, fixture controls, replay, quality, and release "
                    "receipts; the output is a descriptive prior."
                ),
            },
            "GNC-D08-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context_alpha.CoreMarginTerritoryPrior",
                    "glio_noncode.cell_context_alpha.CoreMarginTerritoryReport",
                    "glio_noncode.cell_context_alpha_frontier_public_data.CellContextAlphaFrontierFixture",
                    "glio_noncode.cell_context_alpha_frontier_delta_depth.audit_cell_context_alpha_frontier_deltas",
                    "glio_noncode.cell_context_alpha_frontier_reconciliation.reconcile_cell_context_alpha_frontier",
                    "glio_noncode.cell_context_alpha_frontier_lineage.build_cell_context_alpha_frontier_lineage",
                    "glio_noncode.cell_context_alpha_frontier_release.build_cell_context_alpha_frontier_release",
                    "glio_noncode.cell_context_alpha_frontier_bundle.build_cell_context_alpha_frontier_bundle",
                    "glio_noncode.cell_context_alpha_frontier_runtime.run_cell_context_alpha_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_cell_context_alpha",
                    "tests.test_cell_context_alpha_cli",
                    "tests.test_cell_context_alpha_frontier",
                ),
                "evidence_note": (
                    "Core and margin scores are compared with an explicit tolerance, preserving "
                    "mixed or one-sided territory evidence, exact context, subject identity, and "
                    "source hashes without inventing localization; delta depth, reconciliation, "
                    "lineage, release, and runtime checks are deterministic."
                ),
            },
            "GNC-D08-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context_alpha.RecurrenceStatePrior",
                    "glio_noncode.cell_context_alpha.RecurrenceStatePriorReport",
                    "glio_noncode.cell_context_alpha_frontier_public_data.CellContextAlphaFrontierFixture",
                    "glio_noncode.cell_context_alpha_frontier_policy.evaluate_cell_context_alpha_frontier_policy",
                    "glio_noncode.cell_context_alpha_frontier_source_registry.build_cell_context_alpha_frontier_source_registry",
                    "glio_noncode.cell_context_alpha_frontier_observability.build_cell_context_alpha_frontier_trace",
                    "glio_noncode.cell_context_alpha_frontier_replay.replay_cell_context_alpha_frontier",
                    "glio_noncode.cell_context_alpha_frontier_exports.export_cell_context_alpha_frontier_manifest",
                    "glio_noncode.cell_context_alpha_frontier_views.build_cell_context_alpha_frontier_view",
                    "glio_noncode.cell_context_alpha_frontier_review_queue.build_cell_context_alpha_frontier_review_queue",
                ),
                "test_modules": (
                    "tests.test_cell_context_alpha",
                    "tests.test_cell_context_alpha_cli",
                    "tests.test_cell_context_alpha_frontier",
                ),
                "evidence_note": (
                    "Primary, recurrence, and progression candidates are ranked per subject and "
                    "context with phase margins, replicate support, alternatives, and ambiguity "
                    "retained; policy, source closure, replay, observability, export, view, and "
                    "review receipts are available without inferring prognosis."
                ),
            },
            "GNC-D08-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_context_alpha.TreatmentInducedStatePrior",
                    "glio_noncode.cell_context_alpha.TreatmentInducedStatePriorReport",
                    "glio_noncode.cell_context_alpha_frontier_public_data.CellContextAlphaFrontierFixture",
                    "glio_noncode.cell_context_alpha_frontier_compliance.evaluate_cell_context_alpha_frontier_boundary",
                    "glio_noncode.cell_context_alpha_frontier_checks.run_cell_context_alpha_frontier_invariants",
                    "glio_noncode.cell_context_alpha_frontier_thresholds.build_cell_context_alpha_frontier_threshold_report",
                    "glio_noncode.cell_context_alpha_frontier_validation_matrix.validate_cell_context_alpha_frontier_matrix",
                    "glio_noncode.cell_context_alpha_frontier_scenario_matrix.evaluate_cell_context_alpha_frontier_scenarios",
                    "glio_noncode.cell_context_alpha_frontier_integrity.evaluate_cell_context_alpha_frontier_integrity",
                    "glio_noncode.cell_context_alpha_frontier_accessibility.evaluate_cell_context_alpha_frontier_accessibility",
                    "glio_noncode.cell_context_alpha_frontier_catalog.build_cell_context_alpha_frontier_catalog",
                    "glio_noncode.cell_context_alpha_frontier_reports.build_cell_context_alpha_frontier_report",
                    "glio_noncode.cell_context_alpha_frontier_pipeline.run_cell_context_alpha_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_cell_context_alpha",
                    "tests.test_cell_context_alpha_cli",
                    "tests.test_cell_context_alpha_frontier",
                ),
                "evidence_note": (
                    "Baseline and post-treatment support deltas retain treatment phase, state IDs, "
                    "subject/context gates, raw hashes, and induced/stable/reduced labels as "
                    "descriptive evidence rather than response or resistance claims; boundary, "
                    "invariant, threshold, validation, scenario, integrity, accessibility, "
                    "catalog, report, and pipeline gates are deterministic."
                ),
            },
            "GNC-D08-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_state_frontier_public_data.CellStateFrontierFixture",
                    "glio_noncode.cell_state_frontier_fixture_eval.evaluate_cell_state_frontier_fixture",
                    "glio_noncode.frontier_context_alpha.CellStateAbundanceUncertaintyModel",
                ),
                "test_modules": (
                    "tests.test_cell_state_frontier_evidence",
                    "tests.test_cell_state_frontier_evidence_cli",
                    "tests.test_cell_state_frontier_depth",
                ),
                "evidence_note": (
                    "Public aggregate fixture runs include four positive and twelve control records; "
                    "binomial intervals, invalid counts, context mismatch, replay, and quality-gated "
                    "release evidence are deterministic and sanitized."
                ),
            },
            "GNC-D08-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cell_state_frontier_fixture_eval.evaluate_cell_state_frontier_fixture",
                    "glio_noncode.frontier_context_alpha.SingleCellReferenceMapper",
                    "glio_noncode.cell_state_frontier_schema.validate_cell_state_frontier_schema",
                ),
                "test_modules": (
                    "tests.test_cell_state_frontier_evidence",
                    "tests.test_cell_state_frontier_evidence_cli",
                    "tests.test_cell_state_frontier_depth",
                ),
                "evidence_note": (
                    "Single-cell mappings retain top/second score, margin, minimum-score, exact-context "
                    "gates, ambiguous controls, source lineage, and bounded review outputs."
                ),
            },
            "GNC-D08-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.CellStateOODDetector",
                    "glio_noncode.cell_state_frontier_quality_gate.run_cell_state_frontier_quality_gate",
                    "glio_noncode.cell_state_frontier_views.build_cell_state_frontier_view",
                ),
                "test_modules": (
                    "tests.test_cell_state_frontier_evidence",
                    "tests.test_cell_state_frontier_evidence_cli",
                    "tests.test_cell_state_frontier_depth",
                ),
                "evidence_note": (
                    "Cell-state OOD checks preserve distance, support score, support boundary, exact "
                    "territory controls, explicit out-of-domain findings, metrics, and review actions."
                ),
            },
            "GNC-D08-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_context_alpha.CellStateContextPublisher",
                    "glio_noncode.cell_state_frontier_release.build_cell_state_frontier_release",
                    "glio_noncode.cell_state_frontier_exports.export_cell_state_frontier_json",
                ),
                "test_modules": (
                    "tests.test_cell_state_frontier_evidence",
                    "tests.test_cell_state_frontier_evidence_cli",
                    "tests.test_cell_state_frontier_depth",
                ),
                "evidence_note": (
                    "Cell-state context envelopes bind aggregate cell IDs, mapping, abundance, OOD "
                    "receipts, exact context, release state, and content addresses before publication."
                ),
            },
            "GNC-D09-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_context.ContactMatrixParser",
                    "glio_noncode.topology_context.TadBoundaryParser",
                    "glio_noncode.topology_context_frontier_public_data.TopologyContextFrontierFixture",
                    "glio_noncode.topology_context_frontier_adapters.execute_topology_context_frontier_record",
                    "glio_noncode.topology_context_frontier_fixture_eval.evaluate_topology_context_frontier_fixture",
                    "glio_noncode.topology_context_frontier_candidate_depth.audit_topology_context_frontier_candidates",
                    "glio_noncode.topology_context_frontier_provenance.build_topology_context_frontier_provenance",
                    "glio_noncode.topology_context_frontier_pipeline.run_topology_context_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_topology_context",
                    "tests.test_topology_context_frontier",
                ),
                "evidence_note": (
                    "Hi-C and Micro-C long-form contacts and TAD boundary rows preserve assay, "
                    "source version, raw hashes, coordinate conversion, malformed-row issues, "
                    "and context keys; aggregate positive, ambiguity, foreign-context, replay, "
                    "quality, and release fixtures are deterministic."
                ),
            },
            "GNC-D09-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_context.ContactMatrixQcEvaluator",
                    "glio_noncode.topology_context.ContactMatrixNormalizer",
                    "glio_noncode.topology_context_frontier_metrics.build_topology_context_frontier_metrics",
                    "glio_noncode.topology_context_frontier_schema.validate_topology_context_frontier_schema",
                    "glio_noncode.topology_context_frontier_quality_gate.build_topology_context_frontier_quality",
                    "glio_noncode.topology_context_frontier_replay.replay_topology_context_frontier",
                ),
                "test_modules": (
                    "tests.test_topology_context",
                    "tests.test_topology_context_frontier",
                ),
                "evidence_note": (
                    "Contact QC reports duplicates, zero rows, signal summaries, and explicit "
                    "partial states; mean/max transforms retain provenance and do not claim ICE "
                    "or assay-bias correction. The public matrix controls cover empty, foreign, "
                    "duplicate, zero-signal, normalization, and release states."
                ),
            },
            "GNC-D09-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_context.TadBoundaryEnsembleBuilder",
                    "glio_noncode.topology_context_frontier_delta_depth.audit_topology_context_frontier_deltas",
                    "glio_noncode.topology_context_frontier_lineage.build_topology_context_frontier_lineage",
                    "glio_noncode.topology_context_frontier_review_queue.build_topology_context_frontier_review_queue",
                    "glio_noncode.topology_context_frontier_views.build_topology_context_frontier_view",
                ),
                "test_modules": (
                    "tests.test_topology_context",
                    "tests.test_topology_context_frontier",
                ),
                "evidence_note": (
                    "Tolerance-bounded boundary clusters retain assay identities, competing "
                    "clusters, agreement, context gating, and ambiguity; external calibration, "
                    "negative controls, transport, and OOD evaluation remain separate while "
                    "the aggregate fixture verifies positive, partial, ambiguous, and foreign paths."
                ),
            },
            "GNC-D09-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_context.InsulationScoreDeltaEstimator",
                    "glio_noncode.topology_context_frontier_policy.evaluate_topology_context_frontier_policy",
                    "glio_noncode.topology_context_frontier_integrity.evaluate_topology_context_frontier_integrity",
                    "glio_noncode.topology_context_frontier_compliance.evaluate_topology_context_frontier_boundary",
                    "glio_noncode.topology_context_frontier_bundle.build_topology_context_frontier_bundle",
                    "glio_noncode.topology_context_frontier_artifacts.build_topology_context_frontier_artifacts",
                ),
                "test_modules": (
                    "tests.test_topology_context",
                    "tests.test_topology_context_frontier",
                ),
                "evidence_note": (
                    "Reference-to-alternate insulation deltas retain direction, missingness, "
                    "zero-baseline guards, replicate count, and research-use limitations; "
                    "external benchmark calibration remains. The public release adds invalid, "
                    "missing, foreign-context, direction, lineage, policy, bundle, and artifact "
                    "receipts."
                ),
            },
            "GNC-D09-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_beta.LoopStripeAdapter",
                    "glio_noncode.topology_beta_frontier_adapters.TopologyBetaFrontierAdapterRegistry",
                    "glio_noncode.topology_beta_frontier_public_data.default_topology_beta_frontier_fixture",
                    "glio_noncode.topology_beta_frontier_fixture_eval.evaluate_topology_beta_frontier_fixture",
                    "glio_noncode.topology_beta_frontier_pipeline.run_topology_beta_frontier_pipeline",
                    "glio_noncode.topology_beta_frontier_contracts.build_topology_beta_frontier_contracts",
                    "glio_noncode.topology_beta_frontier_quality_gate.build_topology_beta_frontier_quality",
                    "glio_noncode.topology_beta_frontier_exports.export_topology_beta_frontier_manifest",
                ),
                "test_modules": (
                    "tests.test_topology_beta",
                    "tests.test_topology_beta_cli",
                    "tests.test_topology_beta_frontier",
                ),
                "evidence_note": (
                    "Loop and stripe adapters preserve two-anchor coordinates, feature kind, "
                    "signal, resolution, replicate/caller metadata, source versions, hashes, and "
                    "malformed-row quarantine; the closed aggregate fixture verifies supported, "
                    "partial, ambiguous, and foreign-context paths with contract, lineage, "
                    "quality, replay, and release receipts."
                ),
            },
            "GNC-D09-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_beta.PromoterCaptureContactAdapter",
                    "glio_noncode.topology_beta_frontier_adapters.TopologyBetaFrontierAdapterRegistry",
                    "glio_noncode.topology_beta_frontier_public_data.default_topology_beta_frontier_fixture",
                    "glio_noncode.topology_beta_frontier_fixture_eval.evaluate_topology_beta_frontier_fixture",
                    "glio_noncode.topology_beta_frontier_pipeline.run_topology_beta_frontier_pipeline",
                    "glio_noncode.topology_beta_frontier_contracts.build_topology_beta_frontier_contracts",
                    "glio_noncode.topology_beta_frontier_quality_gate.build_topology_beta_frontier_quality",
                    "glio_noncode.topology_beta_frontier_exports.export_topology_beta_frontier_manifest",
                ),
                "test_modules": (
                    "tests.test_topology_beta",
                    "tests.test_topology_beta_cli",
                    "tests.test_topology_beta_frontier",
                ),
                "evidence_note": (
                    "Promoter-capture adapters retain promoter and target-element identity, bait, "
                    "coordinates, signal, context, source versions, hashes, and parser issues; "
                    "the closed aggregate fixture verifies supported, partial, ambiguous, and "
                    "foreign-context paths with source, schema, lineage, policy, and release "
                    "receipts."
                ),
            },
            "GNC-D09-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_beta.EnhancerPromoterContactScorer",
                    "glio_noncode.topology_beta_frontier_adapters.TopologyBetaFrontierAdapterRegistry",
                    "glio_noncode.topology_beta_frontier_public_data.default_topology_beta_frontier_fixture",
                    "glio_noncode.topology_beta_frontier_fixture_eval.evaluate_topology_beta_frontier_fixture",
                    "glio_noncode.topology_beta_frontier_pipeline.run_topology_beta_frontier_pipeline",
                    "glio_noncode.topology_beta_frontier_policy.evaluate_topology_beta_frontier_policy",
                    "glio_noncode.topology_beta_frontier_provenance.build_topology_beta_frontier_provenance",
                    "glio_noncode.topology_beta_frontier_exports.export_topology_beta_frontier_manifest",
                ),
                "test_modules": (
                    "tests.test_topology_beta",
                    "tests.test_topology_beta_cli",
                    "tests.test_topology_beta_frontier",
                ),
                "evidence_note": (
                    "Exact-context enhancer-promoter contact scoring retains every observation, "
                    "replicate spread, source versions, bounded signal normalization, and "
                    "out-of-domain context; the aggregate fixture verifies ambiguity, missingness, "
                    "foreign context, bounded normalization, source lineage, review policy, and "
                    "replay closure."
                ),
            },
            "GNC-D09-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_beta.ActivityByContactScorer",
                    "glio_noncode.topology_beta_frontier_adapters.TopologyBetaFrontierAdapterRegistry",
                    "glio_noncode.topology_beta_frontier_public_data.default_topology_beta_frontier_fixture",
                    "glio_noncode.topology_beta_frontier_fixture_eval.evaluate_topology_beta_frontier_fixture",
                    "glio_noncode.topology_beta_frontier_pipeline.run_topology_beta_frontier_pipeline",
                    "glio_noncode.topology_beta_frontier_policy.evaluate_topology_beta_frontier_policy",
                    "glio_noncode.topology_beta_frontier_runtime.run_topology_beta_frontier_runtime",
                    "glio_noncode.topology_beta_frontier_exports.export_topology_beta_frontier_manifest",
                ),
                "test_modules": (
                    "tests.test_topology_beta",
                    "tests.test_topology_beta_cli",
                    "tests.test_topology_beta_frontier",
                ),
                "evidence_note": (
                    "Activity-by-contact combines exact-context activity and contact components "
                    "with model/version receipts, missingness, ambiguity, and source lineage; the "
                    "closed aggregate fixture verifies component disagreement, missing activity, "
                    "foreign context, policy, runtime limits, and release closure."
                ),
            },
            "GNC-D09-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_alpha.BoundaryMotifOrientationAnalyzer",
                    "glio_noncode.topology_alpha.BoundaryMotifOrientationReport",
                    "glio_noncode.topology_alpha_frontier_adapters.TopologyAlphaFrontierAdapterRegistry",
                    "glio_noncode.topology_alpha_frontier_public_data.default_topology_alpha_frontier_fixture",
                    "glio_noncode.topology_alpha_frontier_fixture_eval.evaluate_topology_alpha_frontier_fixture",
                    "glio_noncode.topology_alpha_frontier_pipeline.run_topology_alpha_frontier_pipeline",
                    "glio_noncode.topology_alpha_frontier_evidence_matrix.build_topology_alpha_frontier_evidence_matrix",
                    "glio_noncode.topology_alpha_frontier_claim_boundary.build_topology_alpha_frontier_claim_boundary",
                    "glio_noncode.topology_alpha_frontier_exports.export_topology_alpha_frontier_manifest",
                ),
                "test_modules": (
                    "tests.test_topology_alpha",
                    "tests.test_topology_alpha_cli",
                    "tests.test_topology_alpha_frontier",
                    "tests.test_topology_alpha_frontier_depth",
                ),
                "evidence_note": (
                    "Boundary-side motif observations preserve orientation, score, source version, "
                    "convergent/divergent/tandem alternatives, and mixed-orientation ambiguity; "
                    "the public aggregate C09-C12 fixture verifies positive, partial, ambiguous, "
                    "foreign-context, replay, evidence, policy, and release paths; orientation is "
                    "not treated as insulation proof."
                ),
            },
            "GNC-D09-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_alpha.CTCFCohesinDisruptionModel",
                    "glio_noncode.topology_alpha.CTCFCohesinDisruptionReport",
                    "glio_noncode.topology_alpha_frontier_adapters.TopologyAlphaFrontierAdapterRegistry",
                    "glio_noncode.topology_alpha_frontier_public_data.default_topology_alpha_frontier_fixture",
                    "glio_noncode.topology_alpha_frontier_fixture_eval.evaluate_topology_alpha_frontier_fixture",
                    "glio_noncode.topology_alpha_frontier_pipeline.run_topology_alpha_frontier_pipeline",
                    "glio_noncode.topology_alpha_frontier_conformance.build_topology_alpha_frontier_conformance",
                    "glio_noncode.topology_alpha_frontier_failure_catalog.build_topology_alpha_frontier_failure_catalog",
                    "glio_noncode.topology_alpha_frontier_runtime.run_topology_alpha_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_topology_alpha",
                    "tests.test_topology_alpha_cli",
                    "tests.test_topology_alpha_frontier",
                    "tests.test_topology_alpha_frontier_depth",
                ),
                "evidence_note": (
                    "Reference/alternate CTCF and cohesin channels retain independent deltas, "
                    "combined descriptive labels, missing channels, state disagreement, contexts, "
                    "and source hashes without causal interpretation; controls cover channel "
                    "disagreement, context transport, schema closure, and deterministic replay."
                ),
            },
            "GNC-D09-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_alpha.IDHInsulatorDysfunctionModel",
                    "glio_noncode.topology_alpha.IDHInsulatorDysfunctionReport",
                    "glio_noncode.topology_alpha_frontier_adapters.TopologyAlphaFrontierAdapterRegistry",
                    "glio_noncode.topology_alpha_frontier_public_data.default_topology_alpha_frontier_fixture",
                    "glio_noncode.topology_alpha_frontier_fixture_eval.evaluate_topology_alpha_frontier_fixture",
                    "glio_noncode.topology_alpha_frontier_metrics.build_topology_alpha_frontier_metrics",
                    "glio_noncode.topology_alpha_frontier_governance.build_topology_alpha_frontier_governance",
                    "glio_noncode.topology_alpha_frontier_release_notes.build_topology_alpha_frontier_release_notes",
                ),
                "test_modules": (
                    "tests.test_topology_alpha",
                    "tests.test_topology_alpha_cli",
                    "tests.test_topology_alpha_frontier",
                    "tests.test_topology_alpha_frontier_depth",
                ),
                "evidence_note": (
                    "IDH-mutant and IDH-wildtype insulator scores are compared per region with a "
                    "separate methylation channel, state gates, missingness, source versions, and "
                    "bounded dysfunction candidates; the alpha fixture retains invalid vocabulary, "
                    "foreign context, claim boundaries, and package notes; no mechanistic diagnosis "
                    "is inferred."
                ),
            },
            "GNC-D09-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.topology_alpha.SVTopologyRewiringSimulator",
                    "glio_noncode.topology_alpha.SVTopologyRewiringReport",
                    "glio_noncode.topology_alpha_frontier_adapters.TopologyAlphaFrontierAdapterRegistry",
                    "glio_noncode.topology_alpha_frontier_public_data.default_topology_alpha_frontier_fixture",
                    "glio_noncode.topology_alpha_frontier_fixture_eval.evaluate_topology_alpha_frontier_fixture",
                    "glio_noncode.topology_alpha_frontier_pipeline.run_topology_alpha_frontier_pipeline",
                    "glio_noncode.topology_alpha_frontier_source_checks.build_topology_alpha_frontier_source_checks",
                    "glio_noncode.topology_alpha_frontier_replay_ledger.build_topology_alpha_frontier_replay_ledger",
                    "glio_noncode.topology_alpha_frontier_packaging.build_topology_alpha_frontier_package_manifest",
                ),
                "test_modules": (
                    "tests.test_topology_alpha",
                    "tests.test_topology_alpha_cli",
                    "tests.test_topology_alpha_frontier",
                    "tests.test_topology_alpha_frontier_depth",
                ),
                "evidence_note": (
                    "Declared SV events simulate preserved, lost, gained, and rewired contact-edge "
                    "sets with affected nodes, contexts, edge receipts, and explicit bookkeeping; "
                    "the C09-C12 release surface adds unknown-edge controls, source closure, query "
                    "inspection, ordered stage receipts, and package validation; the simulation is "
                    "not a prediction of 3D function."
                ),
            },
            "GNC-D09-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.EcDNARegulatoryContactModel",
                    "glio_noncode.frontier_inference_alpha.EcDNAContactReport",
                    "glio_noncode.topology_frontier_fixture_eval.evaluate_topology_frontier_fixture",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_topology_frontier_evidence",
                ),
                "evidence_note": (
                    "ecDNA contacts retain element/gene identity, contact score, source count, "
                    "normalized support, exact context, review reasons, public source receipts, "
                    "replay, lineage, and release checks."
                ),
            },
            "GNC-D09-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.CompartmentSwitchEstimator",
                    "glio_noncode.frontier_inference_alpha.CompartmentSwitchReport",
                    "glio_noncode.topology_frontier_fixture_eval.evaluate_topology_frontier_fixture",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_topology_frontier_evidence",
                ),
                "evidence_note": (
                    "Signed compartment scores produce explicit A/B transitions, deltas, confidence, "
                    "and stable or threshold-review states with exact context controls, source "
                    "lineage, schema, and replay evidence."
                ),
            },
            "GNC-D09-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.TopologyUncertaintyTransportModel",
                    "glio_noncode.frontier_inference_alpha.TopologyTransportReport",
                    "glio_noncode.topology_frontier_fixture_eval.evaluate_topology_frontier_fixture",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_topology_frontier_evidence",
                ),
                "evidence_note": (
                    "Topology paths transport declared signal while accumulating edge uncertainty "
                    "and path-contiguity review; public aggregate controls, policy checks, and "
                    "content-addressed reconciliation are verified."
                ),
            },
            "GNC-D09-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.ThreeDEvidencePublisher",
                    "glio_noncode.frontier_inference_alpha.ThreeDEvidenceBundle",
                    "glio_noncode.topology_frontier_release.build_topology_frontier_release",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_topology_frontier_evidence",
                ),
                "evidence_note": (
                    "3D evidence bundles retain path IDs, assay IDs, exact context, record address, "
                    "and publication address with public source receipts, release gating, and "
                    "review exports."
                ),
            },
            "GNC-D10-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph.CoordinateOverlapLinker",
                    "glio_noncode.link_graph_foundation_frontier_adapters",
                    "glio_noncode.link_graph_foundation_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_link_graph",
                    "tests.test_link_graph_foundation_frontier",
                ),
                "evidence_note": (
                    "Sixteen public aggregate records and five source receipts replay coordinate "
                    "overlap with supported, ambiguous, absent, and out-of-domain controls; "
                    "benchmark, conformance, projection, regression, and release checks pass."
                ),
            },
            "GNC-D10-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph.GeneFeatureParser",
                    "glio_noncode.link_graph.NearestGeneBaseline",
                    "glio_noncode.link_graph_foundation_frontier_adapters",
                    "glio_noncode.link_graph_foundation_frontier_regression",
                ),
                "test_modules": (
                    "tests.test_link_graph",
                    "tests.test_link_graph_foundation_frontier",
                ),
                "evidence_note": (
                    "Public aggregate nearest-gene rows preserve distance ties, bounded-window "
                    "abstention, context controls, receipt coverage, and deterministic replay; "
                    "nearest proximity remains a bounded baseline."
                ),
            },
            "GNC-D10-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph.CcreElementAssigner",
                    "glio_noncode.link_graph_foundation_frontier_contracts",
                    "glio_noncode.link_graph_foundation_frontier_quality_dashboard",
                ),
                "test_modules": (
                    "tests.test_link_graph",
                    "tests.test_link_graph_foundation_frontier",
                ),
                "evidence_note": (
                    "cCRE aggregate assignment covers positive, multiple-element, absent, and "
                    "context-mismatch rows with schema, source, invariant, and acceptance checks."
                ),
            },
            "GNC-D10-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph.EnhancerGeneConsensusLinker",
                    "glio_noncode.link_graph_foundation_frontier_decision_trace",
                    "glio_noncode.link_graph_foundation_frontier_release_readiness",
                ),
                "test_modules": (
                    "tests.test_link_graph",
                    "tests.test_link_graph_foundation_frontier",
                ),
                "evidence_note": (
                    "Consensus aggregate records retain method-specific evidence, single-method "
                    "partial status, contradiction visibility, decision traces, risk controls, "
                    "and release readiness without causal interpretation."
                ),
            },
            "GNC-D10-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph_beta.ActivityByContactLinkAdapter",
                    "glio_noncode.link_graph_beta_frontier_adapters.execute_link_graph_beta_frontier_record",
                    "glio_noncode.link_graph_beta_frontier_pipeline.run_link_graph_beta_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_link_graph_beta_frontier",
                    "tests.test_link_graph_beta_frontier_depth",
                    "tests.test_link_graph_beta_frontier_integration",
                ),
                "evidence_note": (
                    "Activity-by-contact records now replay through a closed public aggregate fixture "
                    "with component measurements, context controls, receipts, lineage, and release "
                    "artifacts; single-method support remains partial."
                ),
            },
            "GNC-D10-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph_beta.CoaccessibilityLinker",
                    "glio_noncode.link_graph_beta_frontier_adapters.execute_link_graph_beta_frontier_record",
                    "glio_noncode.link_graph_beta_frontier_schema.validate_link_graph_beta_frontier_schema",
                ),
                "test_modules": (
                    "tests.test_link_graph_beta_frontier",
                    "tests.test_link_graph_beta_frontier_depth",
                    "tests.test_link_graph_beta_frontier_integration",
                ),
                "evidence_note": (
                    "Coaccessibility paths are evaluated with alternative-gene, missing-evidence, "
                    "and foreign-context controls while preserving exact-context graph state, "
                    "operation metrics, review entries, and replay receipts."
                ),
            },
            "GNC-D10-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph_beta.MolecularQtlLinker",
                    "glio_noncode.link_graph_beta_frontier_metrics.build_link_graph_beta_frontier_metrics",
                    "glio_noncode.link_graph_beta_frontier_quality_gate.build_link_graph_beta_frontier_quality",
                ),
                "test_modules": (
                    "tests.test_link_graph_beta_frontier",
                    "tests.test_link_graph_beta_frontier_depth",
                    "tests.test_link_graph_beta_frontier_integration",
                ),
                "evidence_note": (
                    "Molecular-QTL evidence retains effect and q-value measurements, exposes weak "
                    "q-value and missing-evidence controls, applies the declared bounded support "
                    "transform, and remains a non-causal aggregate research result."
                ),
            },
            "GNC-D10-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph_beta.AlleleSpecificLinkEvidenceIntegrator",
                    "glio_noncode.link_graph_beta_frontier_policy.evaluate_link_graph_beta_frontier_policy",
                    "glio_noncode.link_graph_beta_frontier_release.build_link_graph_beta_frontier_release",
                ),
                "test_modules": (
                    "tests.test_link_graph_beta_frontier",
                    "tests.test_link_graph_beta_frontier_depth",
                    "tests.test_link_graph_beta_frontier_integration",
                ),
                "evidence_note": (
                    "Allele-specific paths preserve gain/loss direction, retain contradiction and "
                    "missingness controls, and carry policy, lineage, review, artifact, and release "
                    "evidence without selecting a preferred gene."
                ),
            },
            "GNC-D10-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph_alpha.CRISPRPerturbationLinkAdapter",
                    "glio_noncode.link_graph_alpha.CRISPRPerturbationLinker",
                    "glio_noncode.link_graph_alpha_frontier_public_data.default_link_graph_alpha_frontier_fixture",
                    "glio_noncode.link_graph_alpha_frontier_adapters.execute_link_graph_alpha_frontier_record",
                    "glio_noncode.link_graph_alpha_frontier_pipeline.run_link_graph_alpha_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_link_graph_alpha",
                    "tests.test_link_graph_alpha_cli",
                    "tests.test_link_graph_alpha_frontier",
                ),
                "evidence_note": (
                    "CRISPR perturbation paths retain mode, direction, effect size, scale, guide "
                    "and replicate metadata, exact context, source hashes, and opposing-direction "
                    "contradiction; the aggregate fixture adds positive, weak, foreign-context, "
                    "and replay controls with source closure and release checks."
                ),
            },
            "GNC-D10-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph_alpha.ThreeDContactLinkAdapter",
                    "glio_noncode.link_graph_alpha.ThreeDContactLinker",
                    "glio_noncode.link_graph_alpha_frontier_public_data.default_link_graph_alpha_frontier_fixture",
                    "glio_noncode.link_graph_alpha_frontier_adapters.execute_link_graph_alpha_frontier_record",
                    "glio_noncode.link_graph_alpha_frontier_metrics.build_link_graph_alpha_frontier_metrics",
                ),
                "test_modules": (
                    "tests.test_link_graph_alpha",
                    "tests.test_link_graph_alpha_cli",
                    "tests.test_link_graph_alpha_frontier",
                ),
                "evidence_note": (
                    "3D contact paths preserve assay kind, raw and normalized signal, scale, "
                    "resolution, replicate identity, exact context, and source receipts before "
                    "candidate edges are emitted; the aggregate fixture retains weak contact, "
                    "alternative-gene, foreign-context, and single-assay controls."
                ),
            },
            "GNC-D10-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph_alpha.PromoterTetheringModel",
                    "glio_noncode.link_graph_alpha.PromoterTetheringReport",
                    "glio_noncode.link_graph_alpha_frontier_public_data.default_link_graph_alpha_frontier_fixture",
                    "glio_noncode.link_graph_alpha_frontier_adapters.execute_link_graph_alpha_frontier_record",
                    "glio_noncode.link_graph_alpha_frontier_review_queue.build_link_graph_alpha_frontier_review_queue",
                ),
                "test_modules": (
                    "tests.test_link_graph_alpha",
                    "tests.test_link_graph_alpha_cli",
                    "tests.test_link_graph_alpha_frontier",
                ),
                "evidence_note": (
                    "Promoter-tethering baselines expose distance prior, contact, promoter, "
                    "element, and overlap components with thresholds, alternatives, abstention, "
                    "and calibration limitations; the fixture verifies missing components, ties, "
                    "foreign context, and bounded release handling."
                ),
            },
            "GNC-D10-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.link_graph_alpha.MultiGeneElementGraphBuilder",
                    "glio_noncode.link_graph_alpha.MultiGeneElementGraph",
                    "glio_noncode.link_graph_alpha_frontier_public_data.default_link_graph_alpha_frontier_fixture",
                    "glio_noncode.link_graph_alpha_frontier_adapters.execute_link_graph_alpha_frontier_record",
                    "glio_noncode.link_graph_alpha_frontier_provenance.build_link_graph_alpha_frontier_provenance",
                ),
                "test_modules": (
                    "tests.test_link_graph_alpha",
                    "tests.test_link_graph_alpha_cli",
                    "tests.test_link_graph_alpha_frontier",
                ),
                "evidence_note": (
                    "Multi-gene/multi-element graph slices retain every aggregate edge, evidence "
                    "path, alternative gene, node degree, connected component, context gate, and "
                    "threshold receipt without selecting a preferred target; graph controls add "
                    "single-evidence, contradiction, context, lineage, and package checks."
                ),
            },
            "GNC-D10-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.LinkEvidenceDependenceCorrector",
                    "glio_noncode.link_frontier_fixture_eval",
                    "glio_noncode.link_frontier_depth",
                    "glio_noncode.link_frontier_quality_gate",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_link_frontier_evidence",
                ),
                "evidence_note": (
                    "Public aggregate dependence groups downweight correlated link support and retain "
                    "raw support, group size, corrected support, source receipts, controls, replay, "
                    "and release-gate evidence."
                ),
            },
            "GNC-D10-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.TargetGeneRanker",
                    "glio_noncode.link_frontier_fixture_eval",
                    "glio_noncode.link_frontier_depth",
                    "glio_noncode.link_frontier_views",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_link_frontier_evidence",
                ),
                "evidence_note": (
                    "Public aggregate target-gene ranking retains component scores, weights, "
                    "variant/element/gene identity, deterministic ranks, alternatives, controls, "
                    "and review exports without selecting a clinical target."
                ),
            },
            "GNC-D10-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.LinkCalibrationAndAbstention",
                    "glio_noncode.link_frontier_scenario_matrix",
                    "glio_noncode.link_frontier_replay",
                    "glio_noncode.link_frontier_depth",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_link_frontier_evidence",
                ),
                "evidence_note": (
                    "Public aggregate calibration compares optional observations, declares thresholds, "
                    "abstains on uncertainty or calibration error, and is covered by adversarial "
                    "scenarios, replay, and quality checks."
                ),
            },
            "GNC-D10-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.LinkEvidencePublisher",
                    "glio_noncode.link_frontier_public_data",
                    "glio_noncode.link_frontier_release",
                    "glio_noncode.link_frontier_exports",
                    "glio_noncode.link_frontier_depth",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_link_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Public aggregate link publication binds link/source IDs, exact context, source "
                    "receipts, record and bundle addresses, sanitized review exports, and a release "
                    "manifest with explicit limitations."
                ),
            },
            "GNC-D11-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_reasoning.TypedHypothesisObjectBuilder",
                    "glio_noncode.causal_foundation_frontier_public_data",
                    "glio_noncode.causal_foundation_frontier_adapters",
                    "glio_noncode.causal_foundation_frontier_fixture_eval",
                    "glio_noncode.causal_foundation_frontier_policy",
                    "glio_noncode.causal_foundation_frontier_quality_gate",
                    "glio_noncode.causal_foundation_frontier_runtime",
                    "glio_noncode.causal_foundation_frontier_release",
                ),
                "test_modules": (
                    "tests.test_causal_reasoning",
                    "tests.test_causal_foundation_frontier",
                    "tests.test_causal_foundation_frontier_depth",
                    "tests.test_causal_foundation_frontier_cli",
                ),
                "evidence_note": (
                    "Typed RegulatoryCausalHypothesis objects retain factor lineage, prior and "
                    "likelihood proxies, missing evidence, contradictions, and research-use "
                    "limitations. Public aggregate positive/control replay now verifies the "
                    "typed object adapter, exact-state floors, policy, release gate, and "
                    "foreign-context quarantine; external task calibration remains."
                ),
            },
            "GNC-D11-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_reasoning.FactorGraphConstructor",
                    "glio_noncode.causal_foundation_frontier_public_data",
                    "glio_noncode.causal_foundation_frontier_adapters",
                    "glio_noncode.causal_foundation_frontier_lineage",
                    "glio_noncode.causal_foundation_frontier_provenance",
                    "glio_noncode.causal_foundation_frontier_integrity",
                    "glio_noncode.causal_foundation_frontier_validation_matrix",
                ),
                "test_modules": (
                    "tests.test_causal_reasoning",
                    "tests.test_causal_foundation_frontier",
                    "tests.test_causal_foundation_frontier_depth",
                ),
                "evidence_note": (
                    "Immutable factor graph snapshots preserve parent lineage, supersession, "
                    "orphan diagnostics, contradiction edges, active views, and deterministic "
                    "replay. Public aggregate controls now verify orphan and contradiction "
                    "states, source-to-result lineage, provenance closure, and integrity; "
                    "migration fixtures remain."
                ),
            },
            "GNC-D11-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_reasoning.ContextConditionedPriorModel",
                    "glio_noncode.causal_foundation_frontier_public_data",
                    "glio_noncode.causal_foundation_frontier_adapters",
                    "glio_noncode.causal_foundation_frontier_schema",
                    "glio_noncode.causal_foundation_frontier_metrics",
                    "glio_noncode.causal_foundation_frontier_review",
                    "glio_noncode.causal_foundation_frontier_claim_boundary",
                ),
                "test_modules": (
                    "tests.test_causal_reasoning",
                    "tests.test_causal_foundation_frontier",
                    "tests.test_causal_foundation_frontier_operational",
                ),
                "evidence_note": (
                    "Exact-context prior profiles expose bounded feature contributions, missing "
                    "features, out-of-range support, and a non-probabilistic prior score; external "
                    "calibration and transport evaluation remain. The public control fixture "
                    "now verifies missing, out-of-range, foreign-context, schema, review, and "
                    "release-boundary behavior."
                ),
            },
            "GNC-D11-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_reasoning.MeasurementLikelihoodModel",
                    "glio_noncode.causal_foundation_frontier_public_data",
                    "glio_noncode.causal_foundation_frontier_adapters",
                    "glio_noncode.causal_foundation_frontier_review",
                    "glio_noncode.causal_foundation_frontier_operational",
                    "glio_noncode.causal_foundation_frontier_quality_gate",
                    "glio_noncode.causal_foundation_frontier_artifacts",
                ),
                "test_modules": (
                    "tests.test_causal_reasoning",
                    "tests.test_causal_foundation_frontier",
                    "tests.test_causal_foundation_frontier_depth",
                    "tests.test_causal_foundation_frontier_operational",
                ),
                "evidence_note": (
                    "Measurement channels are grouped for dependence-aware aggregation with "
                    "missing, contradictory, and context-mismatched states; the output remains "
                    "a likelihood proxy rather than a calibrated clinical probability. The "
                    "public control fixture now verifies single-group partial output, explicit "
                    "contradiction retention, foreign-context quarantine, review actions, and "
                    "artifact release checks."
                ),
            },
            "GNC-D11-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_beta.SequenceToElementCausalMediator",
                    "glio_noncode.causal_beta_frontier_public_data",
                    "glio_noncode.causal_beta_frontier_adapters",
                    "glio_noncode.causal_beta_frontier_fixture_eval",
                    "glio_noncode.causal_beta_frontier_contracts",
                    "glio_noncode.causal_beta_frontier_schema",
                    "glio_noncode.causal_beta_frontier_quality_gate",
                    "glio_noncode.causal_beta_frontier_runtime",
                    "glio_noncode.causal_beta_frontier_release",
                    "glio_noncode.causal_beta_frontier_exports",
                    "glio_noncode.causal_beta_frontier_claim_boundary",
                ),
                "test_modules": (
                    "tests.test_causal_beta",
                    "tests.test_causal_beta_cli",
                    "tests.test_causal_beta_frontier",
                    "tests.test_causal_beta_frontier_depth",
                    "tests.test_causal_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Sequence-to-element mediator evidence is replayed through a public aggregate "
                    "fixture with positive, minimum-source, directional-conflict, and foreign-context "
                    "controls. Contracts, schema, metrics, lineage, provenance, policy, review, "
                    "quality, release, exports, and explicit claim boundaries are verified; causal "
                    "calibration and external validation remain."
                ),
            },
            "GNC-D11-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_beta.ElementToGeneCausalMediator",
                    "glio_noncode.causal_beta_frontier_public_data",
                    "glio_noncode.causal_beta_frontier_adapters",
                    "glio_noncode.causal_beta_frontier_fixture_eval",
                    "glio_noncode.causal_beta_frontier_lineage",
                    "glio_noncode.causal_beta_frontier_provenance",
                    "glio_noncode.causal_beta_frontier_integrity",
                    "glio_noncode.causal_beta_frontier_operational",
                    "glio_noncode.causal_beta_frontier_runtime",
                    "glio_noncode.causal_beta_frontier_release",
                ),
                "test_modules": (
                    "tests.test_causal_beta",
                    "tests.test_causal_beta_cli",
                    "tests.test_causal_beta_frontier",
                    "tests.test_causal_beta_frontier_operational",
                ),
                "evidence_note": (
                    "Element-to-gene paths retain exact context, source/version lineage, directional "
                    "disagreement, independent-source support, deterministic replay, and bounded "
                    "operational dispositions. The public fixture verifies positive, incomplete, "
                    "conflicting, foreign-context, release, and excluded-use behavior; a supported "
                    "path is not a causal or clinical claim."
                ),
            },
            "GNC-D11-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_beta.GeneToStateCausalMediator",
                    "glio_noncode.causal_beta_frontier_public_data",
                    "glio_noncode.causal_beta_frontier_adapters",
                    "glio_noncode.causal_beta_frontier_fixture_eval",
                    "glio_noncode.causal_beta_frontier_metrics",
                    "glio_noncode.causal_beta_frontier_policy",
                    "glio_noncode.causal_beta_frontier_review",
                    "glio_noncode.causal_beta_frontier_quality_gate",
                    "glio_noncode.causal_beta_frontier_runtime",
                    "glio_noncode.causal_beta_frontier_assurance",
                ),
                "test_modules": (
                    "tests.test_causal_beta",
                    "tests.test_causal_beta_cli",
                    "tests.test_causal_beta_frontier",
                    "tests.test_causal_beta_frontier_depth",
                ),
                "evidence_note": (
                    "Gene-to-state evidence preserves state-specific context, negative evidence, "
                    "source disagreement, uncertainty, model receipts, explicit abstention and "
                    "out-of-domain behavior. Public aggregate controls verify negative-control "
                    "conflict, release blocking, review coverage, and the non-clinical claim "
                    "boundary; state effects require perturbation and transport validation."
                ),
            },
            "GNC-D11-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_beta.CounterfactualAlleleStateSimulator",
                    "glio_noncode.causal_beta_frontier_public_data",
                    "glio_noncode.causal_beta_frontier_adapters",
                    "glio_noncode.causal_beta_frontier_fixture_eval",
                    "glio_noncode.causal_beta_frontier_scenario_matrix",
                    "glio_noncode.causal_beta_frontier_validation_matrix",
                    "glio_noncode.causal_beta_frontier_replay",
                    "glio_noncode.causal_beta_frontier_runtime",
                    "glio_noncode.causal_beta_frontier_release",
                    "glio_noncode.causal_beta_frontier_exports",
                ),
                "test_modules": (
                    "tests.test_causal_beta",
                    "tests.test_causal_beta_cli",
                    "tests.test_causal_beta_frontier",
                    "tests.test_causal_beta_frontier_depth",
                    "tests.test_causal_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Reference/alternate allele-state comparisons report exact-context values, "
                    "replicate ambiguity, allele coverage, and alternate-minus-reference deltas "
                    "with model/version lineage. Positive, missing-alternate, ambiguity, and "
                    "foreign-context controls are replayed through policy, review, release, and "
                    "export checks; the output is descriptive and does not establish causality "
                    "or clinical effect."
                ),
            },
            "GNC-D11-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_alpha_frontier_public_data",
                    "glio_noncode.causal_alpha_frontier_runtime",
                    "glio_noncode.causal_alpha.MediationSensitivityAnalyzer",
                    "glio_noncode.causal_alpha.MediationSensitivityResult",
                ),
                "test_modules": (
                    "tests.test_causal_alpha_frontier",
                    "tests.test_causal_alpha_frontier_depth",
                    "tests.test_causal_alpha_frontier_cli",
                ),
                "evidence_note": (
                    "The public aggregate C09-C12 fixture replays positive, single-source, "
                    "fragile, and foreign-context mediation cases through source omission, "
                    "lineage, policy, review, release, replay, and export gates; sensitivity "
                    "is not causal identification."
                ),
            },
            "GNC-D11-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_alpha_frontier_public_data",
                    "glio_noncode.causal_alpha_frontier_runtime",
                    "glio_noncode.causal_alpha.ConfoundingChecklistAdjudicator",
                    "glio_noncode.causal_alpha.ConfoundingAdjudicationReport",
                ),
                "test_modules": (
                    "tests.test_causal_alpha_frontier",
                    "tests.test_causal_alpha_frontier_depth",
                    "tests.test_causal_alpha_frontier_cli",
                ),
                "evidence_note": (
                    "The public aggregate C09-C12 fixture retains addressed, unresolved, "
                    "missing, not-applicable, and foreign-context checklist cases with "
                    "severity, adjustment methods, source lineage, exact-context gates, "
                    "replay, release, and export evidence; completion does not prove no "
                    "unmeasured confounding."
                ),
            },
            "GNC-D11-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_alpha_frontier_public_data",
                    "glio_noncode.causal_alpha_frontier_runtime",
                    "glio_noncode.causal_alpha.EvidenceDependenceCorrector",
                    "glio_noncode.causal_alpha.DependenceCorrectionReport",
                ),
                "test_modules": (
                    "tests.test_causal_alpha_frontier",
                    "tests.test_causal_alpha_frontier_operational",
                    "tests.test_causal_alpha_frontier_cli",
                ),
                "evidence_note": (
                    "The public aggregate C09-C12 fixture selects one representative path per "
                    "declared group while retaining duplicate IDs, method families, uncertainty, "
                    "independent-group counts, contradictions, foreign controls, lineage, "
                    "policy, replay, and release evidence; corrected support is a bounded proxy."
                ),
            },
            "GNC-D11-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.causal_alpha_frontier_public_data",
                    "glio_noncode.causal_alpha_frontier_runtime",
                    "glio_noncode.causal_alpha.NegativeEvidenceIntegrator",
                    "glio_noncode.causal_alpha.NegativeEvidenceIntegrationReport",
                ),
                "test_modules": (
                    "tests.test_causal_alpha_frontier",
                    "tests.test_causal_alpha_frontier_operational",
                    "tests.test_causal_alpha_frontier_cli",
                ),
                "evidence_note": (
                    "The public aggregate C09-C12 fixture separates positive paths, negative "
                    "controls, measured-negative states, coverage, and positive/negative "
                    "contradictions with exact context, assay limitations, source lineage, "
                    "review, release, replay, and export gates; negative evidence is not proof "
                    "of absence."
                ),
            },
            "GNC-D11-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.PosteriorDecompositionEngine",
                    "glio_noncode.frontier_inference_alpha.PosteriorDecompositionReport",
                    "glio_noncode.causal_frontier_public_data",
                    "glio_noncode.causal_frontier_fixture_eval",
                    "glio_noncode.causal_frontier_quality_gate",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_causal_frontier_evidence",
                    "tests.test_causal_frontier_depth",
                ),
                "evidence_note": (
                    "Posterior decomposition retains prior, likelihood, measurement, dependence "
                    "penalty, raw score, normalized score, and top-hypothesis identity. Public "
                    "aggregate positive/control replay, source receipts, contracts, schema, "
                    "lineage, and release checks are verified."
                ),
            },
            "GNC-D11-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.RegulatoryDriverHypothesisPosterior",
                    "glio_noncode.frontier_inference_alpha.DriverPosteriorReport",
                    "glio_noncode.causal_frontier_contracts",
                    "glio_noncode.causal_frontier_policy",
                    "glio_noncode.causal_frontier_reconciliation",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_causal_frontier_evidence",
                ),
                "evidence_note": (
                    "Regulatory-driver posteriors retain evidence IDs, support, priors, normalized "
                    "posterior, rank, and minimum-support review. Low-support, empty, and invalid "
                    "controls are replayed under a public aggregate policy boundary."
                ),
            },
            "GNC-D11-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.SelectivePredictionAndAbstention",
                    "glio_noncode.frontier_inference_alpha.SelectivePredictionReport",
                    "glio_noncode.causal_frontier_scenario_matrix",
                    "glio_noncode.causal_frontier_metrics",
                    "glio_noncode.causal_frontier_views",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_frontier_inference_alpha_cli",
                    "tests.test_causal_frontier_evidence",
                ),
                "evidence_note": (
                    "Selective prediction applies uncertainty-aware score thresholds and records "
                    "abstentions rather than forcing weak causal outputs. A 42-scenario matrix, "
                    "issue metrics, CSV review view, and release checks exercise threshold edges."
                ),
            },
            "GNC-D11-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.CausalDossierPublisher",
                    "glio_noncode.frontier_inference_alpha.CausalDossier",
                    "glio_noncode.causal_frontier_bundle",
                    "glio_noncode.causal_frontier_release",
                    "glio_noncode.causal_frontier_exports",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_causal_frontier_evidence",
                    "tests.test_causal_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Causal dossiers bind hypothesis IDs and evidence addresses with a research-only "
                    "publication receipt and no causal conclusion upgrade. Bundle, release manifest, "
                    "observability, replay, and deterministic JSON/CSV export surfaces are verified."
                ),
            },
            "GNC-D12-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_discovery.CohortQueryBuilder",
                    "glio_noncode.cohort_foundation_frontier_public_data",
                    "glio_noncode.cohort_foundation_frontier_adapters",
                    "glio_noncode.cohort_foundation_frontier_contracts",
                    "glio_noncode.cohort_foundation_frontier_fixture_eval",
                    "glio_noncode.cohort_foundation_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_cohort_discovery",
                    "tests.test_cohort_foundation_frontier",
                    "tests.test_cohort_foundation_frontier_cli",
                ),
                "evidence_note": (
                    "Cohort queries preserve exact context, variant/origin/sample criteria, "
                    "callable requirements, exclusion reasons, source IDs, and out-of-domain "
                    "transport. The public C01-C04 aggregate fixture verifies positive, partial, "
                    "empty, and foreign-context paths through adapters, contracts, replay, "
                    "lineage, policy, quality, release, and CLI surfaces."
                ),
            },
            "GNC-D12-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_discovery.LocalBackgroundMutationModel",
                    "glio_noncode.cohort_foundation_frontier_fixture_eval",
                    "glio_noncode.cohort_foundation_frontier_metrics",
                    "glio_noncode.cohort_foundation_frontier_provenance",
                    "glio_noncode.cohort_foundation_frontier_quality_gate",
                ),
                "test_modules": (
                    "tests.test_cohort_discovery",
                    "tests.test_cohort_foundation_frontier",
                    "tests.test_cohort_foundation_frontier_cli",
                ),
                "evidence_note": (
                    "Local background summaries retain callable bases, observed records, context "
                    "rate, target-space expectation, and small-sample uncertainty without emitting "
                    "an unvalidated significance claim. The public fixture verifies supported, "
                    "zero-observation partial, missing-denominator abstention, and foreign-context "
                    "controls with deterministic release accounting."
                ),
            },
            "GNC-D12-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_discovery.SequenceContextControlMatcher",
                    "glio_noncode.cohort_foundation_frontier_adapters",
                    "glio_noncode.cohort_foundation_frontier_policy",
                    "glio_noncode.cohort_foundation_frontier_reconciliation",
                    "glio_noncode.cohort_foundation_frontier_review",
                ),
                "test_modules": (
                    "tests.test_cohort_discovery",
                    "tests.test_cohort_foundation_frontier",
                    "tests.test_cohort_foundation_frontier_cli",
                ),
                "evidence_note": (
                    "Sequence controls use exact context and bounded normalized Hamming distance, "
                    "preserving candidate count, distances, source IDs, and abstention/OOD states."
                    " The public fixture exercises supported, insufficient, absent, and foreign "
                    "candidate paths and retains review, quarantine, and export decisions."
                ),
            },
            "GNC-D12-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_discovery.ChromatinContextControlMatcher",
                    "glio_noncode.cohort_foundation_frontier_schema",
                    "glio_noncode.cohort_foundation_frontier_lineage",
                    "glio_noncode.cohort_foundation_frontier_release",
                    "glio_noncode.cohort_foundation_frontier_artifacts",
                ),
                "test_modules": (
                    "tests.test_cohort_discovery",
                    "tests.test_cohort_foundation_frontier",
                    "tests.test_cohort_foundation_frontier_cli",
                ),
                "evidence_note": (
                    "Chromatin controls use declared feature ranges and RMS distance with complete "
                    "vector requirements, context gating, candidate accounting, and explicit "
                    "negative-control limitations. The public fixture verifies matched, incomplete, "
                    "distance-excluded, and foreign-context controls through schema, lineage, "
                    "artifact, release, and runtime gates."
                ),
            },
            "GNC-D12-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_beta.RegulatoryRecurrenceTester",
                    "glio_noncode.cohort_beta_frontier_runtime",
                    "glio_noncode.cohort_beta_frontier_provenance",
                    "glio_noncode.cohort_beta_frontier_release",
                ),
                "test_modules": (
                    "tests.test_cohort_beta",
                    "tests.test_cohort_beta_cli",
                    "tests.test_cohort_beta_frontier",
                ),
                "evidence_note": (
                    "Regulatory recurrence is verified through a public aggregate fixture with "
                    "positive, absent, partial, and foreign-context paths. The release plane "
                    "retains distinct-sample recurrence, hotspot thresholds, source receipts, "
                    "lineage, reconciliation, policy, replay, and bounded claim ceilings."
                ),
            },
            "GNC-D12-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_beta.RegionalBurdenTester",
                    "glio_noncode.cohort_beta_frontier_schema",
                    "glio_noncode.cohort_beta_frontier_metrics",
                    "glio_noncode.cohort_beta_frontier_quality_gate",
                ),
                "test_modules": (
                    "tests.test_cohort_beta",
                    "tests.test_cohort_beta_cli",
                    "tests.test_cohort_beta_frontier",
                ),
                "evidence_note": (
                    "Regional burden is verified with explicit callable bases, exact-context "
                    "overlap, deduplicated variants, absent and foreign controls, comparator "
                    "receipts, source closure, and quality-gated release packaging. It remains "
                    "a descriptive callable-space comparison without a significance claim."
                ),
            },
            "GNC-D12-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_beta.FunctionalConvergenceTester",
                    "glio_noncode.cohort_beta_frontier_contracts",
                    "glio_noncode.cohort_beta_frontier_policy",
                    "glio_noncode.cohort_beta_frontier_views",
                ),
                "test_modules": (
                    "tests.test_cohort_beta",
                    "tests.test_cohort_beta_cli",
                    "tests.test_cohort_beta_frontier",
                ),
                "evidence_note": (
                    "Functional convergence is verified through observed/control support "
                    "contrasts, explicit no-control partial paths, foreign-context isolation, "
                    "state policy, review projections, deterministic replay, and a bounded "
                    "fixture-backed release report."
                ),
            },
            "GNC-D12-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_beta.PathwayRegulonConvergenceTester",
                    "glio_noncode.cohort_beta_frontier_fixture_eval",
                    "glio_noncode.cohort_beta_frontier_claim_boundary",
                    "glio_noncode.cohort_beta_frontier_replay",
                ),
                "test_modules": (
                    "tests.test_cohort_beta",
                    "tests.test_cohort_beta_cli",
                    "tests.test_cohort_beta_frontier",
                ),
                "evidence_note": (
                    "Pathway and regulon convergence is verified with namespace-preserving "
                    "membership aggregation, observed/control contrast, partial and foreign "
                    "controls, opposing directions retained as contradictory, claim evidence, "
                    "lineage, replay, and public release gates. External set transport remains "
                    "outside the bounded fixture claim."
                ),
            },
            "GNC-D12-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_alpha.ClonalityTimingIntegrator",
                    "glio_noncode.cohort_alpha.ClonalityTimingReport",
                    "glio_noncode.cohort_alpha_frontier_public_data",
                    "glio_noncode.cohort_alpha_frontier_fixture_eval",
                    "glio_noncode.cohort_alpha_frontier_contracts",
                    "glio_noncode.cohort_alpha_frontier_schema",
                    "glio_noncode.cohort_alpha_frontier_governance",
                    "glio_noncode.cohort_alpha_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_cohort_alpha",
                    "tests.test_cohort_alpha_cli",
                    "tests.test_cohort_alpha_frontier",
                    "tests.test_cohort_alpha_frontier_cli",
                ),
                "evidence_note": (
                    "Clonality and timing integration preserves CCF values, pseudonymous sample "
                    "IDs, phase labels, timepoint order, source hashes, and missing CCF/timing "
                    "states. The public C09-C12 fixture adds positive, partial, foreign, and "
                    "abstained controls with source closure, reconciliation, policy, review, "
                    "replay, package, and 70-plus-stage runtime depth; it does not establish "
                    "clonal evolution."
                ),
            },
            "GNC-D12-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_alpha.PrimaryRecurrenceComparator",
                    "glio_noncode.cohort_alpha.PrimaryRecurrenceComparatorReport",
                    "glio_noncode.cohort_alpha_frontier_public_data",
                    "glio_noncode.cohort_alpha_frontier_fixture_eval",
                    "glio_noncode.cohort_alpha_frontier_contracts",
                    "glio_noncode.cohort_alpha_frontier_schema",
                    "glio_noncode.cohort_alpha_frontier_governance",
                    "glio_noncode.cohort_alpha_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_cohort_alpha",
                    "tests.test_cohort_alpha_cli",
                    "tests.test_cohort_alpha_frontier",
                    "tests.test_cohort_alpha_frontier_cli",
                ),
                "evidence_note": (
                    "Primary/recurrence comparisons retain phase-specific frequencies, sample "
                    "IDs, treatment-exposure metadata, deltas, thresholds, and partial phase "
                    "coverage. The bounded public fixture exercises exact-context publication, "
                    "missing-phase review, foreign-context quarantine, content-addressed replay, "
                    "and explicit descriptive claim ceilings without turning recurrence into "
                    "prognosis or treatment evidence."
                ),
            },
            "GNC-D12-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_alpha.TreatmentSelectionSignalDetector",
                    "glio_noncode.cohort_alpha.TreatmentSelectionReport",
                    "glio_noncode.cohort_alpha_frontier_public_data",
                    "glio_noncode.cohort_alpha_frontier_fixture_eval",
                    "glio_noncode.cohort_alpha_frontier_contracts",
                    "glio_noncode.cohort_alpha_frontier_schema",
                    "glio_noncode.cohort_alpha_frontier_governance",
                    "glio_noncode.cohort_alpha_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_cohort_alpha",
                    "tests.test_cohort_alpha_cli",
                    "tests.test_cohort_alpha_frontier",
                    "tests.test_cohort_alpha_frontier_cli",
                ),
                "evidence_note": (
                    "Pre/post treatment frequency signals preserve treatment ID, sample and "
                    "response metadata, phase coverage, effect direction, threshold receipts, "
                    "and context. The release plane adds positive and incomplete controls, "
                    "policy partitions, review SLA, safety controls, report accessibility, and "
                    "deterministic package receipts; it is not resistance, benefit, or response "
                    "evidence."
                ),
            },
            "GNC-D12-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.cohort_alpha.CrossCohortReplicationEngine",
                    "glio_noncode.cohort_alpha.CrossCohortReplicationReport",
                    "glio_noncode.cohort_alpha_frontier_public_data",
                    "glio_noncode.cohort_alpha_frontier_fixture_eval",
                    "glio_noncode.cohort_alpha_frontier_contracts",
                    "glio_noncode.cohort_alpha_frontier_schema",
                    "glio_noncode.cohort_alpha_frontier_governance",
                    "glio_noncode.cohort_alpha_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_cohort_alpha",
                    "tests.test_cohort_alpha_cli",
                    "tests.test_cohort_alpha_frontier",
                    "tests.test_cohort_alpha_frontier_cli",
                ),
                "evidence_note": (
                    "Cross-cohort replication retains cohort-specific effects, support, sample "
                    "counts, direction concordance, heterogeneous sources, and minimum coverage "
                    "without claiming transportability or generalization. The fixture explicitly "
                    "retains one ambiguous direction case, source matrix, boundary explanations, "
                    "state distribution, safety gate, and reproducibility receipt."
                ),
            },
            "GNC-D12-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.SubgroupFairnessStratifier",
                    "glio_noncode.frontier_inference_alpha.FairnessStratificationReport",
                    "glio_noncode.cohort_frontier_public_data",
                    "glio_noncode.cohort_frontier_fixture_eval",
                    "glio_noncode.cohort_frontier_quality_gate",
                    "glio_noncode.cohort_frontier_release",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_cohort_frontier_evidence",
                    "tests.test_cohort_frontier_depth",
                    "tests.test_cohort_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Subgroup rates retain group size, positive count, rate, parity gap, and review "
                    "thresholds without hiding small strata. A public aggregate fixture exercises "
                    "balanced and high-gap controls through evaluation, reconciliation, release, "
                    "and CSV review surfaces."
                ),
            },
            "GNC-D12-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.TransportabilityEstimator",
                    "glio_noncode.frontier_inference_alpha.TransportabilityReport",
                    "glio_noncode.cohort_frontier_scenario_matrix",
                    "glio_noncode.cohort_frontier_thresholds",
                    "glio_noncode.cohort_frontier_replay",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_cohort_frontier_evidence",
                    "tests.test_cohort_frontier_depth",
                    "tests.test_cohort_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Transportability estimates retain source/target feature sets, overlap, shift "
                    "score, and feature-gap or shift review. Threshold probes, scenario matrices, "
                    "deterministic replay, and release gating make both review boundaries visible."
                ),
            },
            "GNC-D12-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.FederatedSummaryAnalyzer",
                    "glio_noncode.frontier_inference_alpha.FederatedSummaryReport",
                    "glio_noncode.cohort_frontier_adapters",
                    "glio_noncode.cohort_frontier_contracts",
                    "glio_noncode.cohort_frontier_policy",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_frontier_inference_alpha_cli",
                    "tests.test_cohort_frontier_evidence",
                    "tests.test_cohort_frontier_depth",
                    "tests.test_cohort_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Federated summaries aggregate site counts and means while retaining privacy-floor "
                    "violations and between-site spread without raw cross-site records. Adapter, "
                    "contract, policy, and aggregate export checks preserve the privacy boundary."
                ),
            },
            "GNC-D12-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.frontier_inference_alpha.CohortDiscoveryPublisher",
                    "glio_noncode.frontier_inference_alpha.CohortDiscoveryBundle",
                    "glio_noncode.cohort_frontier_bundle",
                    "glio_noncode.cohort_frontier_lineage",
                    "glio_noncode.cohort_frontier_views",
                    "glio_noncode.cohort_frontier_exports",
                ),
                "test_modules": (
                    "tests.test_frontier_inference_alpha",
                    "tests.test_cohort_frontier_evidence",
                    "tests.test_cohort_frontier_depth",
                    "tests.test_cohort_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Cohort discovery bundles retain aggregate feature IDs, analysis IDs, exact "
                    "context, record address, and publication address. Lineage, artifact inventory, "
                    "review views, release checks, and public CSV export are fixture-backed."
                ),
            },
            "GNC-D13-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.validation_design_frontier_operations.evaluate_gap_analysis",
                    "glio_noncode.validation_design_frontier_contracts.ValidationDesignOperationResult",
                    "glio_noncode.validation_design_frontier_public_data",
                    "glio_noncode.validation_design_frontier_fixture_eval",
                    "glio_noncode.validation_design_frontier_quality_gate",
                    "glio_noncode.validation_design_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_planning",
                    "tests.test_validation_frontier_evidence",
                    "tests.test_validation_frontier_depth",
                    "tests.test_validation_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Typed hypotheses are converted into ranked evidence gaps with required "
                    "channels, impact, context, and review warnings; external planning benchmarks "
                    "and calibration remain. The public aggregate frontier verifies missing "
                    "measurement, uncertainty, context mismatch, and complete-snapshot controls."
                ),
            },
            "GNC-D13-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.validation_design_frontier_operations.evaluate_assay_eligibility",
                    "glio_noncode.validation_design_frontier_contracts.ValidationDesignOperationResult",
                    "glio_noncode.validation_design_frontier_adapters",
                    "glio_noncode.validation_design_frontier_fixture_eval",
                    "glio_noncode.validation_design_frontier_policy",
                    "glio_noncode.validation_design_frontier_reconciliation",
                    "glio_noncode.validation_design_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_planning",
                    "tests.test_validation_frontier_evidence",
                    "tests.test_validation_frontier_depth",
                    "tests.test_validation_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Assay routes check model, insert, control, and readout constraints while "
                    "preserving blockers, alternatives, sensitivity, and human-review boundaries."
                    " The fixture verifies ready, blocked, missing-control, model-mismatch, and "
                    "empty-inventory states."
                ),
            },
            "GNC-D13-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.validation_design_frontier_operations.evaluate_mpra_package",
                    "glio_noncode.validation_design_frontier_schema",
                    "glio_noncode.validation_design_frontier_scenario_matrix",
                    "glio_noncode.validation_design_frontier_thresholds",
                    "glio_noncode.validation_design_frontier_controls",
                    "glio_noncode.validation_design_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_planning",
                    "tests.test_validation_frontier_evidence",
                    "tests.test_validation_frontier_depth",
                    "tests.test_validation_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "MPRA packages validate reference alleles, generate reference/alternate "
                    "constructs, enforce context and construct bounds, and retain controls and "
                    "research-use limitations. Scenario and threshold surfaces verify paired "
                    "constructs, context mismatch, empty targets, and budget overflow."
                ),
            },
            "GNC-D13-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.validation_design_frontier_operations.evaluate_starrseq_package",
                    "glio_noncode.validation_design_frontier_bundle",
                    "glio_noncode.validation_design_frontier_lineage",
                    "glio_noncode.validation_design_frontier_exports",
                    "glio_noncode.validation_design_frontier_validation_matrix",
                    "glio_noncode.validation_design_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_planning",
                    "tests.test_validation_frontier_evidence",
                    "tests.test_validation_frontier_depth",
                    "tests.test_validation_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "STARR-seq packages share the allele-aware bounded planner contract and block "
                    "context mismatch or construct-budget overflow without claiming assay efficacy. "
                    "Release, lineage, review CSV, and aggregate manifest checks preserve the "
                    "bounded planning boundary."
                ),
            },
            "GNC-D13-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.editing_design_frontier_operations.evaluate_crispr_design",
                    "glio_noncode.editing_design_frontier_contracts.EditingDesignOperationResult",
                    "glio_noncode.editing_design_frontier_public_data",
                    "glio_noncode.editing_design_frontier_fixture_eval",
                    "glio_noncode.editing_design_frontier_quality_gate",
                    "glio_noncode.editing_design_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_beta",
                    "tests.test_validation_beta_cli",
                    "tests.test_validation_beta_frontier",
                    "tests.test_validation_beta_frontier_cli",
                ),
                "evidence_note": (
                    "CRISPRi design packages generate context-gated guide candidates with declared "
                    "overlap, heuristic score, specificity, PAM, control, readout, and budget "
                    "receipts; the public aggregate frontier verifies positive and boundary paths, "
                    "while guide efficacy and off-target validation remain external."
                ),
            },
            "GNC-D13-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.editing_design_frontier_operations.evaluate_base_editing",
                    "glio_noncode.editing_design_frontier_contracts.EditingDesignOperationResult",
                    "glio_noncode.editing_design_frontier_adapters",
                    "glio_noncode.editing_design_frontier_fixture_eval",
                    "glio_noncode.editing_design_frontier_reconciliation",
                    "glio_noncode.editing_design_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_beta",
                    "tests.test_validation_beta_cli",
                    "tests.test_validation_beta_frontier",
                    "tests.test_validation_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Base-editing planning checks single-base substitution compatibility and a "
                    "declared editing window while retaining candidate guides, edit payload, "
                    "bystander warnings, controls, and blocked unsupported chemistry. The public "
                    "aggregate frontier verifies paired positive and control receipts."
                ),
            },
            "GNC-D13-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.editing_design_frontier_operations.evaluate_prime_editing",
                    "glio_noncode.editing_design_frontier_schema",
                    "glio_noncode.editing_design_frontier_fixture_eval",
                    "glio_noncode.editing_design_frontier_depth",
                    "glio_noncode.editing_design_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_beta",
                    "tests.test_validation_beta_cli",
                    "tests.test_validation_beta_frontier",
                    "tests.test_validation_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Prime-editing packages generate declared guide, PBS, RTT, and edit payload "
                    "placeholders with flank and edit-length gates; pegRNA efficacy, nicking, "
                    "off-target, and bystander validation remain required. The public aggregate "
                    "frontier verifies PBS/RTT, edit-length, flank, context, and empty-target controls."
                ),
            },
            "GNC-D13-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.editing_design_frontier_operations.evaluate_allele_reporter",
                    "glio_noncode.editing_design_frontier_bundle",
                    "glio_noncode.editing_design_frontier_evidence_matrix",
                    "glio_noncode.editing_design_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_beta",
                    "tests.test_validation_beta_cli",
                    "tests.test_validation_beta_frontier",
                    "tests.test_validation_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Allele-specific reporter packages keep reference and alternate constructs "
                    "paired under exact context, controls, readouts, and construct budgets; "
                    "reporter activity does not establish endogenous causality or clinical effect. "
                    "The public aggregate frontier verifies paired alleles, budget, context, and "
                    "empty-target controls."
                ),
            },
            "GNC-D13-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.planning_frontier_operations.evaluate_model_system_eligibility",
                    "glio_noncode.planning_frontier_contracts.PlanningOperation",
                    "glio_noncode.planning_frontier_public_data",
                    "glio_noncode.planning_frontier_fixture_eval",
                    "glio_noncode.planning_frontier_provenance",
                    "glio_noncode.planning_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_planning_frontier",
                    "tests.test_planning_frontier_cli",
                    "tests.test_planning_frontier_depth",
                ),
                "evidence_note": (
                    "Model-system eligibility matches exact context, declared model support, "
                    "cell state, evidence strength, blockers, and source receipts; it is a "
                    "planning gate and not proof of model fidelity or validation success. The public "
                    "aggregate frontier verifies eligible, blocked, and out-of-domain paths."
                ),
            },
            "GNC-D13-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.planning_frontier_operations.evaluate_guide_oligo_adaptation",
                    "glio_noncode.planning_frontier_adapters.PlanningAdapterRegistry",
                    "glio_noncode.planning_frontier_public_data",
                    "glio_noncode.planning_frontier_fixture_eval",
                    "glio_noncode.planning_frontier_exports",
                    "glio_noncode.planning_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_planning_frontier",
                    "tests.test_planning_frontier_cli",
                    "tests.test_planning_frontier_depth",
                ),
                "evidence_note": (
                    "Guide and oligo adaptation preserves design IDs, target IDs, sequences, "
                    "strand, offsets, PAM, context, versions, row hashes, and malformed-row "
                    "quarantine; sequence adaptation does not establish efficacy or safety. The "
                    "public aggregate frontier verifies source closure, malformed rows, context "
                    "review, and empty-source abstention."
                ),
            },
            "GNC-D13-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.planning_frontier_operations.evaluate_controls_randomization",
                    "glio_noncode.planning_frontier_contracts.PlanningExecution",
                    "glio_noncode.planning_frontier_public_data",
                    "glio_noncode.planning_frontier_fixture_eval",
                    "glio_noncode.planning_frontier_review_queue",
                    "glio_noncode.planning_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_planning_frontier",
                    "tests.test_planning_frontier_cli",
                    "tests.test_planning_frontier_depth",
                ),
                "evidence_note": (
                    "Control and replicate plans generate deterministic content-addressed "
                    "assignments for biological and technical replicates while retaining context "
                    "blockers and review boundaries; they do not guarantee balance or assay "
                    "validity. The public aggregate frontier verifies deterministic assignments, "
                    "three control rows, context isolation, missing IDs, and empty plans."
                ),
            },
            "GNC-D13-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.planning_frontier_operations.evaluate_power_replication",
                    "glio_noncode.planning_frontier_contracts.PlanningState",
                    "glio_noncode.planning_frontier_public_data",
                    "glio_noncode.planning_frontier_fixture_eval",
                    "glio_noncode.planning_frontier_quality_gate",
                    "glio_noncode.planning_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_planning_frontier",
                    "tests.test_planning_frontier_cli",
                    "tests.test_planning_frontier_depth",
                ),
                "evidence_note": (
                    "Power planning exposes effect, variance, alpha, target power, replicate "
                    "requirements, blocking factors, shortfalls, assumptions, and source receipts "
                    "under a transparent approximation; it is not a statistical guarantee or a "
                    "clinical claim. The public aggregate frontier verifies ready, partial, "
                    "out-of-domain, abstained, and invalid-observation controls."
                ),
            },
            "GNC-D13-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.validation_release_frontier_operations.evaluate_off_target_risk",
                    "glio_noncode.validation_release_frontier_public_data",
                    "glio_noncode.validation_release_frontier_fixture_eval",
                    "glio_noncode.validation_release_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_release_frontier",
                    "tests.test_validation_release_frontier_depth",
                    "tests.test_validation_release_frontier_cli",
                    "tests.test_validation_release_frontier_extensions",
                ),
                "evidence_note": (
                    "Off-target estimates retain candidate scores, weights, maximum and weighted "
                    "burden, specificity, thresholds, and review or blocking issues. The dedicated "
                    "public aggregate fixture verifies low-risk, high-risk, foreign-context, and "
                    "malformed-score controls through five checks per row."
                ),
            },
            "GNC-D13-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.validation_release_frontier_operations.evaluate_value_of_information",
                    "glio_noncode.validation_release_frontier_execution_plan",
                    "glio_noncode.validation_release_frontier_depth",
                    "glio_noncode.validation_release_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_release_frontier",
                    "tests.test_validation_release_frontier_depth",
                    "tests.test_validation_release_frontier_cli",
                ),
                "evidence_note": (
                    "Validation value-of-information planning selects dependency-safe experiments "
                    "by information/risk value density under a declared budget. Controls exercise "
                    "budget insufficiency, missing dependencies, cycles, and foreign context."
                ),
            },
            "GNC-D13-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.validation_release_frontier_operations.evaluate_experiment_package",
                    "glio_noncode.validation_release_frontier_artifacts",
                    "glio_noncode.validation_release_frontier_package",
                    "glio_noncode.validation_release_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_release_frontier",
                    "tests.test_validation_release_frontier_depth",
                    "tests.test_validation_release_frontier_cli",
                ),
                "evidence_note": (
                    "Experiment packages retain experiment, control, and protocol IDs with per-file "
                    "content addresses and a deterministic manifest. Controls exercise empty input, "
                    "identity collision, and foreign-context package boundaries."
                ),
            },
            "GNC-D13-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.validation_release_frontier_operations.evaluate_claim_update",
                    "glio_noncode.validation_release_frontier_reconciliation",
                    "glio_noncode.validation_release_frontier_release_checks",
                    "glio_noncode.validation_release_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_validation_release_frontier",
                    "tests.test_validation_release_frontier_depth",
                    "tests.test_validation_release_frontier_cli",
                ),
                "evidence_note": (
                    "Result ingestion updates known claims only with exact context, result identity, "
                    "changed fields, evidence address, and unknown-claim review. Controls preserve "
                    "unknown-claim, foreign-context, and missing-receipt states."
                ),
            },
            "GNC-D14-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.evidence_lifecycle.VersionedEvidenceGraphConstructor",
                    "glio_noncode.evidence_lifecycle_frontier_public_data",
                    "glio_noncode.evidence_lifecycle_frontier_fixture_eval",
                    "glio_noncode.evidence_lifecycle_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_evidence_lifecycle",
                    "tests.test_evidence_lifecycle_frontier_evidence",
                    "tests.test_evidence_lifecycle_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Immutable graph snapshots preserve claims, citations, lineage, supersession, "
                    "replay addresses, and a review-required research dossier integrity envelope. "
                    "The public aggregate fixture verifies graph history, controls, replay, and release gates."
                ),
            },
            "GNC-D14-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.evidence_lifecycle.CitationResolver",
                    "glio_noncode.evidence_lifecycle.EvidenceCitation",
                    "glio_noncode.evidence_lifecycle_frontier_public_data",
                    "glio_noncode.evidence_lifecycle_frontier_fixture_eval",
                ),
                "test_modules": (
                    "tests.test_evidence_lifecycle",
                    "tests.test_evidence_lifecycle_frontier_evidence",
                    "tests.test_evidence_lifecycle_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "TSV, CSV, and JSON citation fixtures retain source versions, row hashes, "
                    "raw records, and malformed-row quarantine. The public fixture verifies valid, malformed, duplicate, and empty-manifest paths."
                ),
            },
            "GNC-D14-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.evidence_lifecycle.ClaimEvidenceEdgeValidator",
                    "glio_noncode.evidence_lifecycle_frontier_fixture_eval",
                    "glio_noncode.evidence_lifecycle_frontier_quality_gate",
                ),
                "test_modules": (
                    "tests.test_evidence_lifecycle",
                    "tests.test_evidence_lifecycle_frontier_evidence",
                    "tests.test_evidence_lifecycle_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Edge validation checks active lineage, citation coverage, exact graph "
                    "context, "
                    "contradiction state, and abstention conditions without averaging conflicting "
                    "claims. The public fixture verifies supported, missing-source, context, and absent-edge controls."
                ),
            },
            "GNC-D14-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.evidence_lifecycle.ContradictionDisagreementTracker",
                    "glio_noncode.evidence_lifecycle_frontier_fixture_eval",
                    "glio_noncode.evidence_lifecycle_frontier_views",
                ),
                "test_modules": (
                    "tests.test_evidence_lifecycle",
                    "tests.test_evidence_lifecycle_frontier_evidence",
                    "tests.test_evidence_lifecycle_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "Disagreement reports retain positive and negative claims, declared value "
                    "groups, source IDs, unresolved state, and out-of-domain handling. The public fixture verifies clear, incomplete, contradictory, and out-of-domain states."
                ),
            },
            "GNC-D14-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.lifecycle_beta.EvidenceTierAdjudicator",
                    "glio_noncode.lifecycle_beta_frontier_adapters",
                    "glio_noncode.lifecycle_beta_frontier_fixture_eval",
                    "glio_noncode.lifecycle_beta_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_lifecycle_beta_frontier",
                    "tests.test_lifecycle_beta_frontier_cli",
                    "tests.test_lifecycle_beta_frontier_depth",
                ),
                "evidence_note": (
                    "Evidence-tier adjudication preserves all declared tier observations, source "
                    "versions, support/against directions, highest-tier summaries, unresolved "
                    "claims, and exact-context gates; tier validity remains project-specific."
                ),
            },
            "GNC-D14-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.lifecycle_beta.ProvenanceLineageViewer",
                    "glio_noncode.lifecycle_beta_frontier_lineage",
                    "glio_noncode.lifecycle_beta_frontier_validation_matrix",
                ),
                "test_modules": (
                    "tests.test_lifecycle_beta_frontier",
                    "tests.test_lifecycle_beta_frontier_surfaces",
                ),
                "evidence_note": (
                    "Provenance lineage views expose parent and supersession relations, active and "
                    "historical claims, source versions, citation nodes, hashes, and graph context "
                    "without changing the immutable graph."
                ),
            },
            "GNC-D14-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.lifecycle_beta.UncertaintyLedgerBuilder",
                    "glio_noncode.lifecycle_beta_frontier_metrics",
                    "glio_noncode.lifecycle_beta_frontier_thresholds",
                ),
                "test_modules": (
                    "tests.test_lifecycle_beta_frontier",
                    "tests.test_lifecycle_beta_frontier_depth",
                ),
                "evidence_note": (
                    "Uncertainty ledgers retain dimension-labeled measurement, context, "
                    "provenance, "
                    "transport, calibration, dependence, and review drivers with conservative "
                    "claim summaries; the ledger is not a calibrated probability."
                ),
            },
            "GNC-D14-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.lifecycle_beta.ReviewerAssignmentRouter",
                    "glio_noncode.lifecycle_beta_frontier_review_queue",
                    "glio_noncode.lifecycle_beta_frontier_operational",
                ),
                "test_modules": (
                    "tests.test_lifecycle_beta_frontier",
                    "tests.test_lifecycle_beta_frontier_operations",
                ),
                "evidence_note": (
                    "Reviewer routing maps active claims to explicit domain, provenance, "
                    "statistical, "
                    "assay, computational, and context roles while retaining contradiction, tier, "
                    "uncertainty, priority, blockers, and research-use boundaries."
                ),
            },
            "GNC-D14-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.lifecycle_alpha.BlindedAdjudicationWorkflow",
                    "glio_noncode.lifecycle_alpha.BlindedAdjudicationPlan",
                    "glio_noncode.lifecycle_beta_frontier_fixture_eval",
                    "glio_noncode.lifecycle_beta_frontier_replay",
                ),
                "test_modules": (
                    "tests.test_lifecycle_beta_frontier",
                    "tests.test_lifecycle_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Blinded adjudication packets mask claim and source receipts, preserve exact "
                    "context and deterministic reviewer tokens, retain abstentions and split "
                    "decisions, and never treat reviewer consensus as causal validation."
                ),
            },
            "GNC-D14-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.lifecycle_alpha.ReviewerCommentChangeLogger",
                    "glio_noncode.lifecycle_alpha.ReviewerCommentChangeLog",
                    "glio_noncode.lifecycle_beta_frontier_exports",
                    "glio_noncode.lifecycle_beta_frontier_views",
                ),
                "test_modules": (
                    "tests.test_lifecycle_beta_frontier",
                    "tests.test_lifecycle_beta_frontier_supporting",
                ),
                "evidence_note": (
                    "Reviewer comments and before/after changes are immutable, context-gated, "
                    "content-addressed, and appendable with duplicate and malformed-row checks; "
                    "the log records process rather than evidentiary truth."
                ),
            },
            "GNC-D14-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.lifecycle_alpha.ReleaseDecisionRecorder",
                    "glio_noncode.lifecycle_alpha.ReleaseDecisionRecord",
                    "glio_noncode.lifecycle_beta_frontier_policy",
                    "glio_noncode.lifecycle_beta_frontier_release",
                    "glio_noncode.lifecycle_beta_frontier_bundle",
                ),
                "test_modules": (
                    "tests.test_lifecycle_beta_frontier",
                    "tests.test_lifecycle_beta_frontier_mutations",
                ),
                "evidence_note": (
                    "Research-only release records retain graph address, gate results, reviewer "
                    "roles, failed conditions, comment-log address, and explicit approval or "
                    "review-required decisions; they never authorize clinical or treatment use."
                ),
            },
            "GNC-D14-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.lifecycle_alpha.EvidenceDeltaDetector",
                    "glio_noncode.lifecycle_alpha.EvidenceDeltaReport",
                    "glio_noncode.lifecycle_beta_frontier_reconciliation",
                    "glio_noncode.lifecycle_beta_frontier_integrity",
                ),
                "test_modules": (
                    "tests.test_lifecycle_beta_frontier",
                    "tests.test_lifecycle_beta_frontier_mutations",
                ),
                "evidence_note": (
                    "Evidence delta reports classify added, removed, and changed claims and "
                    "citations plus graph-state or context changes with before/after addresses "
                    "and review severity; a delta does not decide which snapshot is correct."
                ),
            },
            "GNC-D14-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.evidence_release_frontier_operations.evaluate_reclassification",
                    "glio_noncode.evidence_release_frontier_contracts.EvidenceReleaseOperationResult",
                    "glio_noncode.evidence_release_frontier_fixture_eval.evaluate_evidence_release_fixture",
                    "glio_noncode.evidence_release_frontier_runtime.run_evidence_release_runtime",
                ),
                "test_modules": (
                    "tests.test_evidence_release_frontier",
                    "tests.test_evidence_release_frontier_extensions",
                    "tests.test_evidence_release_frontier_cli",
                ),
                "evidence_note": (
                    "Reclassification requires an exact context, a score threshold, two independent "
                    "reviewer IDs, and two public source receipts. Positive and low-score, reviewer, "
                    "and foreign-context controls are replayed through the release runtime."
                ),
            },
            "GNC-D14-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.evidence_release_frontier_operations.evaluate_supersession",
                    "glio_noncode.evidence_release_frontier_context_boundary.evaluate_evidence_release_context_boundary",
                    "glio_noncode.evidence_release_frontier_decision_ledger.build_evidence_release_decision_ledger",
                ),
                "test_modules": (
                    "tests.test_evidence_release_frontier",
                    "tests.test_evidence_release_frontier_extensions",
                    "tests.test_evidence_release_frontier_cli",
                ),
                "evidence_note": (
                    "Supersession retains prior records, detects missing targets, self-links, context "
                    "mismatches, and cycles, and writes an append-only decision ledger. A positive "
                    "exact-context chain and three controls are included in the public fixture."
                ),
            },
            "GNC-D14-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.evidence_release_frontier_operations.evaluate_reproducibility_bundle",
                    "glio_noncode.evidence_release_frontier_reproducibility.build_evidence_release_reproducibility_packet",
                    "glio_noncode.evidence_release_frontier_bundle.assemble_evidence_release_bundle",
                ),
                "test_modules": (
                    "tests.test_evidence_release_frontier",
                    "tests.test_evidence_release_frontier_extensions",
                    "tests.test_evidence_release_frontier_cli",
                ),
                "evidence_note": (
                    "Audit bundles require evidence, review, and release sections, item addresses, "
                    "unique section identity, and exact context. Replay, artifact inventory, review "
                    "routing, and a safe package manifest close the reproducibility boundary."
                ),
            },
            "GNC-D14-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.evidence_release_frontier_operations.sign_dossier",
                    "glio_noncode.evidence_release_frontier_operations.verify_signed_dossier",
                    "glio_noncode.evidence_release_frontier_publication_policy.evaluate_evidence_release_publication_policy",
                    "glio_noncode.evidence_release_frontier_runtime.run_evidence_release_runtime",
                ),
                "test_modules": (
                    "tests.test_evidence_release_frontier",
                    "tests.test_evidence_release_frontier_extensions",
                    "tests.test_evidence_release_frontier_cli",
                ),
                "evidence_note": (
                    "Research dossier signing uses an explicit key ID, audience, expiry, payload "
                    "address, HMAC receipt, and recomputed verification state. Shared-secret signing "
                    "is not treated as a public-key identity and no signing material is emitted."
                ),
            },
            "GNC-D15-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace.CaseWorkspaceBuilder",
                    "glio_noncode.workspace.WorkspaceBrowser",
                    "glio_noncode.workspace_frontier_fixture_eval",
                    "glio_noncode.workspace_frontier_review_queue",
                ),
                "test_modules": (
                    "tests.test_workspace",
                    "tests.test_workspace_frontier_evidence",
                    "tests.test_workspace_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "The public aggregate fixture verifies immutable case sections, exact context, "
                    "facets, pagination, accessibility metadata, source receipts, control states, "
                    "replay stability, and release accounting."
                ),
            },
            "GNC-D15-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace.CohortWorkspaceBuilder",
                    "glio_noncode.workspace_frontier_fixture_eval",
                    "glio_noncode.workspace_frontier_metrics",
                ),
                "test_modules": (
                    "tests.test_workspace",
                    "tests.test_workspace_frontier_evidence",
                    "tests.test_workspace_frontier_depth",
                ),
                "evidence_note": (
                    "The public aggregate fixture verifies selected records, callability exclusion, "
                    "exact-context withholding, bounded facets, section separation, source receipts, "
                    "replay stability, and descriptive metric accounting."
                ),
            },
            "GNC-D15-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace.VariantExplorer",
                    "glio_noncode.workspace_frontier_fixture_eval",
                    "glio_noncode.workspace_frontier_contracts",
                ),
                "test_modules": (
                    "tests.test_workspace",
                    "tests.test_workspace_frontier_evidence",
                    "tests.test_workspace_frontier_evidence_cli",
                ),
                "evidence_note": (
                    "The public aggregate fixture verifies canonical variant resolution, declared "
                    "relationship grouping, absent-variant abstention, context mismatch withholding, "
                    "content addresses, and stable CLI output."
                ),
            },
            "GNC-D15-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace.RegulatoryTrackBrowser",
                    "glio_noncode.workspace_frontier_fixture_eval",
                    "glio_noncode.workspace_frontier_thresholds",
                ),
                "test_modules": (
                    "tests.test_workspace",
                    "tests.test_workspace_frontier_evidence",
                    "tests.test_workspace_frontier_depth",
                ),
                "evidence_note": (
                    "The public aggregate fixture verifies source-accounted interval records, row "
                    "hashes, normalized coordinate overlap, parse-issue visibility, facets, exact "
                    "context, accessibility labels, bounded threshold probes, and release evidence."
                ),
            },
            "GNC-D15-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace_beta.TopologyViewer",
                    "glio_noncode.workspace_beta.TopologyViewport",
                    "glio_noncode.workspace_beta_frontier_fixture_eval",
                    "glio_noncode.workspace_beta_frontier_quality_gate",
                    "glio_noncode.workspace_beta_frontier_runtime",
                ),
                "test_modules": (
                    "tests.test_workspace_beta",
                    "tests.test_workspace_beta_cli",
                    "tests.test_workspace_beta_frontier",
                    "tests.test_workspace_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Topology viewports join loop/stripe anchors, promoter-capture contacts, "
                    "contact scores, and activity-by-contact summaries with exact context, "
                    "interval focus, source versions, observation IDs, deterministic bounds, "
                    "and explicit non-causal limitations. The C05-C08 public aggregate package "
                    "adds sixteen rows, four positive paths, twelve controls, replay, lineage, "
                    "quality gating, review exports, and an eight-stage runtime."
                ),
            },
            "GNC-D15-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace_beta.CausalChainExplorer",
                    "glio_noncode.workspace_beta.CausalChainView",
                    "glio_noncode.workspace_beta_frontier_public_data",
                    "glio_noncode.workspace_beta_frontier_reconciliation",
                    "glio_noncode.workspace_beta_frontier_observability",
                ),
                "test_modules": (
                    "tests.test_workspace_beta",
                    "tests.test_workspace_beta_cli",
                    "tests.test_workspace_beta_frontier",
                    "tests.test_workspace_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Causal-chain views join all three mediator kinds, retain alternative paths, "
                    "negative evidence, source versions, missing mediator kinds, contradiction, "
                    "and context mismatch. The public package verifies complete, incomplete, "
                    "foreign-context, contradiction, alternative-path, and replay controls with "
                    "explicit policy and review state."
                ),
            },
            "GNC-D15-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace_beta.PosteriorDecompositionViewer",
                    "glio_noncode.workspace_beta.PosteriorDecompositionView",
                    "glio_noncode.workspace_beta_frontier_metrics",
                    "glio_noncode.workspace_beta_frontier_release",
                    "glio_noncode.workspace_beta_frontier_artifacts",
                ),
                "test_modules": (
                    "tests.test_workspace_beta",
                    "tests.test_workspace_beta_cli",
                    "tests.test_workspace_beta_frontier",
                    "tests.test_workspace_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Posterior decomposition views expose declared prior, exact-context support "
                    "components, normalized descriptive shares, calibration status, and an "
                    "unexplained residual without inventing missing evidence or clinical "
                    "probability. The public package verifies reconciled, foreign-component, "
                    "unreconciled, missing-support, threshold, artifact, and release controls."
                ),
            },
            "GNC-D15-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace_beta.EvidenceTableAndFilters",
                    "glio_noncode.workspace_beta.EvidenceTableFilter",
                    "glio_noncode.workspace_beta_frontier_views",
                    "glio_noncode.workspace_beta_frontier_review_queue",
                    "glio_noncode.workspace_beta_frontier_exports",
                ),
                "test_modules": (
                    "tests.test_workspace_beta",
                    "tests.test_workspace_beta_cli",
                    "tests.test_workspace_beta_frontier",
                    "tests.test_workspace_beta_frontier_cli",
                ),
                "evidence_note": (
                    "Evidence tables support exact-context text, channel, tier, state, source, "
                    "confidence, pagination, and deterministic facets while retaining partial "
                    "and unresolved evidence rows. The public package verifies foreign-context, "
                    "empty-result, pagination, facet, review-queue, CSV, and release behavior."
                ),
            },
            "GNC-D15-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace_alpha.ValidationExperimentBoardBuilder",
                    "glio_noncode.workspace_alpha.ValidationExperimentBoard",
                    "glio_noncode.workspace_gamma_frontier_public_data",
                    "glio_noncode.workspace_gamma_frontier_fixture_eval",
                    "glio_noncode.workspace_gamma_frontier_projection_assertions",
                    "glio_noncode.workspace_gamma_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_workspace_alpha",
                    "tests.test_workspace_alpha_cli",
                    "tests.test_workspace_gamma_frontier",
                    "tests.test_workspace_gamma_frontier_cli",
                ),
                "evidence_note": (
                    "Validation experiment boards group exact-context cards by declared status, "
                    "priority, dependencies, blockers, owners, readouts, and accessible column "
                    "metadata. The public C09-C12 package executes four board cases plus three "
                    "controls, verifies six columns and dependency edges, retains malformed and "
                    "foreign-context receipts, and carries the board through lineage, replay, "
                    "projection assertions, reconciliation, quality gate, review queue, and release."
                ),
            },
            "GNC-D15-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace_alpha.NotebookSDKLauncher",
                    "glio_noncode.workspace_alpha.NotebookLaunchPlan",
                    "glio_noncode.workspace_gamma_frontier_public_data",
                    "glio_noncode.workspace_gamma_frontier_fixture_eval",
                    "glio_noncode.workspace_gamma_frontier_projection_assertions",
                    "glio_noncode.workspace_gamma_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_workspace_alpha",
                    "tests.test_workspace_alpha_cli",
                    "tests.test_workspace_gamma_frontier",
                    "tests.test_workspace_gamma_frontier_cli",
                ),
                "evidence_note": (
                    "Notebook and SDK launch plans produce bounded runtime, artifact, parameter, "
                    "resource, network-policy, and source receipts without executing code or "
                    "silently enabling external access. The public C09-C12 package verifies "
                    "offline descriptors, foreign context, unsupported runtime, and unbounded "
                    "resource controls, then carries parameter hashes and network policy through "
                    "schema, replay, lineage, policy, quality, review, release, and export layers."
                ),
            },
            "GNC-D15-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace_alpha.ShareableSnapshotPublisher",
                    "glio_noncode.workspace_alpha.ShareableSignedSnapshot",
                    "glio_noncode.workspace_gamma_frontier_public_data",
                    "glio_noncode.workspace_gamma_frontier_fixture_eval",
                    "glio_noncode.workspace_gamma_frontier_projection_assertions",
                    "glio_noncode.workspace_gamma_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_workspace_alpha",
                    "tests.test_workspace_alpha_cli",
                    "tests.test_workspace_gamma_frontier",
                    "tests.test_workspace_gamma_frontier_cli",
                ),
                "evidence_note": (
                    "Shareable snapshots carry payload addresses, audience, expiry, key IDs, and "
                    "HMAC verification receipts while retaining research-use limitations; shared "
                    "secret possession is not a public-key identity or scientific validation. The "
                    "public C09-C12 package verifies valid, tampered, expired, and foreign-context "
                    "envelopes; compact output omits secret values and carries verification state "
                    "through boundary checks, replay, lineage, policy, bundle, release, and CSV."
                ),
            },
            "GNC-D15-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workspace_alpha.RoleBasedCollaborationEvaluator",
                    "glio_noncode.workspace_alpha.CollaborationAccessReport",
                    "glio_noncode.workspace_gamma_frontier_public_data",
                    "glio_noncode.workspace_gamma_frontier_fixture_eval",
                    "glio_noncode.workspace_gamma_frontier_policy",
                    "glio_noncode.workspace_gamma_frontier_pipeline",
                ),
                "test_modules": (
                    "tests.test_workspace_alpha",
                    "tests.test_workspace_alpha_cli",
                    "tests.test_workspace_gamma_frontier",
                    "tests.test_workspace_gamma_frontier_cli",
                ),
                "evidence_note": (
                    "Role-based collaboration evaluation applies an explicit deny-by-default "
                    "permission matrix, exact-context gates, inactive-member handling, policy "
                    "receipts, and access decisions without replacing institutional controls. The "
                    "public C09-C12 package verifies allowed, foreign, inactive, and unknown-member "
                    "cases, preserves reasons and policy receipts, and carries decisions through "
                    "metrics, lineage, reconciliation, quality, review queue, release, and export."
                ),
            },
            "GNC-D15-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workbench_release_frontier_operations.evaluate_review_form",
                    "glio_noncode.workbench_release_frontier_contracts.WorkbenchReleaseOperationResult",
                    "glio_noncode.workbench_release_frontier_fixture_eval.evaluate_workbench_release_fixture",
                    "glio_noncode.workbench_release_frontier_runtime.run_workbench_release_runtime",
                ),
                "test_modules": (
                    "tests.test_workbench_release_frontier",
                    "tests.test_workbench_release_frontier_extensions",
                    "tests.test_workbench_release_frontier_cli",
                ),
                "evidence_note": (
                    "Structured review forms retain field identity, labels, required flags, choices, "
                    "completion, reviewer identity, exact context, and content addresses. The public "
                    "fixture verifies complete, missing-field, invalid-choice, and foreign-context paths."
                ),
            },
            "GNC-D15-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workbench_release_frontier_operations.evaluate_report_export",
                    "glio_noncode.workbench_release_frontier_views.build_workbench_release_view",
                    "glio_noncode.workbench_release_frontier_runtime.run_workbench_release_runtime",
                ),
                "test_modules": (
                    "tests.test_workbench_release_frontier",
                    "tests.test_workbench_release_frontier_extensions",
                    "tests.test_workbench_release_frontier_cli",
                ),
                "evidence_note": (
                    "Report export preserves JSON, Markdown, and CSV-oriented projections, ordered "
                    "sections, line counts, section addresses, duplicate identity controls, empty "
                    "report review, and foreign-context blocking through the release runtime."
                ),
            },
            "GNC-D15-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workbench_release_frontier_operations.evaluate_search_palette",
                    "glio_noncode.workbench_release_frontier_queue.build_workbench_release_queue",
                    "glio_noncode.workbench_release_frontier_runtime.run_workbench_release_runtime",
                ),
                "test_modules": (
                    "tests.test_workbench_release_frontier",
                    "tests.test_workbench_release_frontier_extensions",
                    "tests.test_workbench_release_frontier_cli",
                ),
                "evidence_note": (
                    "Global search ranks identity, title, ordinary-field, and command matches "
                    "deterministically with bounded results and exact context. The fixture verifies "
                    "positive matches, no-match review, malformed identity rejection, and quarantine."
                ),
            },
            "GNC-D15-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.workbench_release_frontier_operations.evaluate_accessibility",
                    "glio_noncode.workbench_release_frontier_evidence_matrix.build_workbench_release_evidence_matrix",
                    "glio_noncode.workbench_release_frontier_runtime.run_workbench_release_runtime",
                ),
                "test_modules": (
                    "tests.test_workbench_release_frontier",
                    "tests.test_workbench_release_frontier_extensions",
                    "tests.test_workbench_release_frontier_cli",
                ),
                "evidence_note": (
                    "Accessibility evaluation retains keyboard, labels, focus order, contrast, motion, "
                    "reading order, severity, remediation text, pass/fail counts, score, exact context, "
                    "and content addresses. Positive, partial, failed, and foreign controls replay."
                ),
            },
            "GNC-D16-C01": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.mission_runtime.MissionPlanBuilder",
                    "glio_noncode.coordination_architecture_plan.compile_coordination_plan",
                ),
                "test_modules": (
                    "tests.test_mission_runtime",
                    "tests.test_platform_frontier",
                    "tests.test_platform_frontier_depth",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "The platform frontier adds a public aggregate fixture with one positive "
                    "and three controls for planning. It verifies dependency expansion, empty "
                    "requests, unknown roles, claim-ceiling rejection, registry addressing, "
                    "replay, review routing, and release-boundary evidence."
                ),
            },
            "GNC-D16-C02": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.platform_frontier_operations.run_platform_frontier_operation",
                    "glio_noncode.platform_frontier_schema.PlatformFrontierSchema",
                    "glio_noncode.platform_frontier_depth.audit_platform_frontier_depth",
                    "glio_noncode.coordination_architecture_plan.compile_coordination_plan",
                ),
                "test_modules": (
                    "tests.test_platform_frontier",
                    "tests.test_platform_frontier_depth",
                    "tests.test_platform_frontier_cli",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "Workflow compilation is exercised through dependency-safe positive work, "
                    "cycle and missing-dependency controls, and network or nondeterministic "
                    "warning retention. Schema, thresholds, validation, evidence, replay, and "
                    "runtime depth surfaces close the module boundary."
                ),
            },
            "GNC-D16-C03": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.platform_frontier_adapters.PlatformFrontierAdapterRegistry",
                    "glio_noncode.platform_frontier_operations.run_platform_frontier_operation",
                    "glio_noncode.platform_frontier_compatibility.PlatformFrontierCompatibilityReport",
                    "glio_noncode.coordination_architecture_tools.build_coordination_tool_registry",
                ),
                "test_modules": (
                    "tests.test_platform_frontier",
                    "tests.test_platform_frontier_depth",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "The registry adapter resolves typed contracts, exposes safety and mutation "
                    "metadata, verifies the 96-tool cardinality, and retains missing-tool, "
                    "contract-mismatch, and cardinality controls. Compatibility and migration "
                    "receipts are deterministic."
                ),
            },
            "GNC-D16-C04": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.mission_runtime.ExecutionSandbox",
                    "glio_noncode.platform_frontier_operations.run_platform_frontier_operation",
                    "glio_noncode.platform_frontier_integrity.PlatformFrontierIntegrityReport",
                    "glio_noncode.coordination_architecture_sandbox.execute_coordination_sandbox",
                ),
                "test_modules": (
                    "tests.test_mission_runtime",
                    "tests.test_platform_frontier",
                    "tests.test_platform_frontier_cli",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "Sandbox execution verifies registered local handlers, policy admission, "
                    "resource scheduling, provenance, event IDs, idempotent replay, local network "
                    "denial, unregistered-handler denial, and direct-identifier rejection. "
                    "Nested receipt integrity is recomputed before release."
                ),
            },
            "GNC-D16-C05": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.control_frontier_policy.ControlFrontierPolicy",
                    "glio_noncode.control_frontier_operations.run_control_frontier_operation",
                    "glio_noncode.control_frontier_fixture_eval.evaluate_control_frontier_fixture",
                    "glio_noncode.coordination_architecture_policy.evaluate_coordination_policy",
                ),
                "test_modules": (
                    "tests.test_control_frontier",
                    "tests.test_control_frontier_cli",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "The aggregate fixture covers claim ceilings, source allowlist gaps, mutation "
                    "scope, sensitive paths, and control visibility. Five retained checks per row "
                    "close the positive and negative policy boundaries."
                ),
            },
            "GNC-D16-C06": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.control_frontier_operations.run_control_frontier_operation",
                    "glio_noncode.control_frontier_thresholds.build_control_frontier_threshold_report",
                    "glio_noncode.control_frontier_operational.build_control_frontier_operational_matrix",
                    "glio_noncode.coordination_architecture_scheduler.schedule_coordination_plan",
                ),
                "test_modules": (
                    "tests.test_control_frontier",
                    "tests.test_control_frontier_depth",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "The scheduler adapter exercises dependency, capacity, network, and cycle "
                    "controls. Threshold probes, operational rows, and retained receipts make "
                    "resource admission observable without running external work."
                ),
            },
            "GNC-D16-C07": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.control_frontier_operations.run_control_frontier_operation",
                    "glio_noncode.control_frontier_scenario_matrix.evaluate_control_frontier_scenarios",
                    "glio_noncode.control_frontier_failure_injection.run_control_frontier_failure_injections",
                    "glio_noncode.coordination_architecture_fallback.route_coordination_fallback",
                ),
                "test_modules": (
                    "tests.test_control_frontier",
                    "tests.test_control_frontier_depth",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "The fallback adapter selects a deterministic eligible route and retains "
                    "non-retryable, network-only, and missing-input controls. Scenario and "
                    "failure-injection reports verify explicit abstention paths."
                ),
            },
            "GNC-D16-C08": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.control_frontier_review_queue.ControlFrontierReviewQueue",
                    "glio_noncode.control_frontier_review_sla.build_control_frontier_review_sla",
                    "glio_noncode.control_frontier_handoff.build_control_frontier_handoff",
                    "glio_noncode.coordination_architecture_review.build_coordination_review_queue",
                ),
                "test_modules": (
                    "tests.test_control_frontier",
                    "tests.test_control_frontier_cli",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "Review routing preserves blockers, stable priority, declared roles, source "
                    "receipts, queue bounds, SLA bands, and handoff state. The omitted and blocked "
                    "controls remain visible in the public review projection."
                ),
            },
            "GNC-D16-C09": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.control_frontier_operations.run_control_frontier_operation",
                    "glio_noncode.control_frontier_audit_log.verify_control_frontier_audit_log",
                    "glio_noncode.control_frontier_replay.replay_control_frontier_evaluation",
                    "glio_noncode.coordination_architecture_ledger.build_coordination_ledger",
                ),
                "test_modules": (
                    "tests.test_control_frontier",
                    "tests.test_control_frontier_depth",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "Ledger execution retains event transitions, duplicate and foreign-context "
                    "controls, replay receipts, audit-log verification, and exact context closure. "
                    "The public runtime exposes this as an operational receipt."
                ),
            },
            "GNC-D16-C10": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.control_frontier_operations.run_control_frontier_operation",
                    "glio_noncode.control_frontier_compatibility.evaluate_control_frontier_compatibility",
                    "glio_noncode.control_frontier_source_registry.build_control_frontier_source_registry",
                    "glio_noncode.coordination_architecture_registries.build_coordination_compute_registry",
                ),
                "test_modules": (
                    "tests.test_control_frontier",
                    "tests.test_control_frontier_depth",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "Model resolution retains digest, version, input/output contracts, exact-context "
                    "support, status, license, evaluation receipt, and explicit compatibility "
                    "blockers. This is registry compatibility evidence, not performance evidence."
                ),
            },
            "GNC-D16-C11": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.control_frontier_operations.run_control_frontier_operation",
                    "glio_noncode.control_frontier_source_registry.ControlFrontierSourceRegistry",
                    "glio_noncode.control_frontier_data_dictionary.default_control_frontier_data_dictionary",
                    "glio_noncode.coordination_architecture_registries.build_coordination_reference_registry",
                ),
                "test_modules": (
                    "tests.test_control_frontier",
                    "tests.test_control_frontier_cli",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "Reference resolution retains URI, checksum, schema, coordinate system, exact "
                    "context, license, retrieval receipt, and availability. Foreign, coordinate, "
                    "license, and missing-reference controls are retained."
                ),
            },
            "GNC-D16-C12": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.control_frontier_operations.run_control_frontier_operation",
                    "glio_noncode.control_frontier_thresholds.build_control_frontier_threshold_report",
                    "glio_noncode.control_frontier_scenario_matrix.evaluate_control_frontier_scenarios",
                    "glio_noncode.coordination_architecture_monitoring.build_coordination_observations",
                ),
                "test_modules": (
                    "tests.test_control_frontier",
                    "tests.test_control_frontier_depth",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "Drift and out-of-domain monitoring retains watch, drift, and support-boundary "
                    "controls with declared thresholds, source receipts, and review states. The "
                    "receipt does not make a model-failure or clinical claim."
                ),
            },
            "GNC-D16-C13": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.deployment_frontier_operations.run_deployment_frontier_operation",
                    "glio_noncode.deployment_frontier_policy.DeploymentFrontierPolicy",
                    "glio_noncode.deployment_frontier_quality_gate.run_deployment_frontier_quality_gate",
                    "glio_noncode.coordination_architecture_security.evaluate_coordination_security",
                ),
                "test_modules": (
                    "tests.test_deployment_frontier",
                    "tests.test_deployment_frontier_depth",
                    "tests.test_deployment_frontier_cli",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "Privacy/security policy evaluation is deny-by-default and retains roles, sensitive "
                    "access, network, retention, context, matched policies, and reasons. The new "
                    "deployment frontier fixture verifies an allowed aggregate read and three distinct "
                    "policy-boundary controls."
                ),
            },
            "GNC-D16-C14": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.deployment_frontier_operations.run_deployment_frontier_operation",
                    "glio_noncode.deployment_frontier_artifacts.DeploymentFrontierArtifactInventory",
                    "glio_noncode.deployment_frontier_package.DeploymentFrontierPackageManifest",
                    "glio_noncode.coordination_architecture_deployment.build_coordination_deployment_artifacts",
                ),
                "test_modules": (
                    "tests.test_deployment_frontier",
                    "tests.test_deployment_frontier_depth",
                    "tests.test_deployment_frontier_cli",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "Local deployment bundles retain artifact digests, service manifests, runtime and "
                    "environment requirements, offline mode, and readiness state. The deployment frontier "
                    "fixture verifies a digest-addressed offline bundle and three independent hold controls."
                ),
            },
            "GNC-D16-C15": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.deployment_frontier_operations.run_deployment_frontier_operation",
                    "glio_noncode.deployment_frontier_lineage.DeploymentFrontierLineage",
                    "glio_noncode.deployment_frontier_review_queue.DeploymentFrontierReviewQueue",
                    "glio_noncode.coordination_architecture_deployment.build_coordination_assignments",
                ),
                "test_modules": (
                    "tests.test_deployment_frontier",
                    "tests.test_deployment_frontier_depth",
                    "tests.test_deployment_frontier_cli",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "Federated coordination retains site-local eligibility, context support, sample "
                    "minimums, privacy costs, assignments, and denied tasks. The deployment frontier "
                    "fixture verifies eligible aggregate sites plus availability, budget, and context controls."
                ),
            },
            "GNC-D16-C16": {
                "state": CapabilityState.VERIFIED.value,
                "implementation_modules": (
                    "glio_noncode.deployment_frontier_release.DeploymentFrontierReleaseManifest",
                    "glio_noncode.deployment_frontier_rollback.DeploymentFrontierRollbackPlan",
                    "glio_noncode.deployment_frontier_release_checks.DeploymentFrontierReleaseCheckReport",
                    "glio_noncode.coordination_architecture_release.build_coordination_release",
                ),
                "test_modules": (
                    "tests.test_deployment_frontier",
                    "tests.test_deployment_frontier_depth",
                    "tests.test_deployment_frontier_cli",
                    "tests.test_coordination_architecture",
                ),
                "evidence_note": (
                    "Release and rollback decisions apply explicit tests, integrity, compatibility, "
                    "policy, version, and previous-version gates with content-addressed receipts. The "
                    "deployment frontier fixture verifies a released version and three failed-transition controls."
                ),
            },
        }
    )
