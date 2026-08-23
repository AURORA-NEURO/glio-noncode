"""Public aggregate data for the Domain 13 validation-beta frontier.

The fixture is intentionally made from public source receipts and synthetic
aggregate planning rows.  It contains no patient identifiers and no private
sample payloads.  Every operation has one positive path and three controls so
that context transport, missing inputs, budget boundaries, unsupported edits,
and abstention are observable in the same release object.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

VALIDATION_BETA_FRONTIER_FIXTURE_VERSION = "2026.08.d13-c05-c12.v1"
VALIDATION_BETA_FRONTIER_CONTEXT_KEY = (
    "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
)
VALIDATION_BETA_FRONTIER_FOREIGN_CONTEXT = (
    "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
)
VALIDATION_BETA_FRONTIER_BOUNDARY = "public_aggregate_research_planning"
VALIDATION_BETA_FRONTIER_SOURCE_COUNT = 7
VALIDATION_BETA_FRONTIER_RECORD_COUNT = 32
VALIDATION_BETA_FRONTIER_POSITIVE_COUNT = 8
VALIDATION_BETA_FRONTIER_CONTROL_COUNT = 24


class ValidationBetaFrontierOperation(StrEnum):
    """The eight contiguous unfinished Domain 13 operation families."""

    CRISPR_DESIGN = "crispr_design"
    BASE_EDITING = "base_editing"
    PRIME_EDITING = "prime_editing"
    ALLELE_REPORTER = "allele_specific_reporter"
    MODEL_ELIGIBILITY = "model_system_eligibility"
    GUIDE_OLIGO = "guide_oligo_design"
    CONTROLS_RANDOMIZATION = "controls_randomization"
    POWER_REPLICATION = "power_replication"


class ValidationBetaFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierSourceReceipt:
    """A public source reference retained alongside every fixture row."""

    source_id: str
    title: str
    uri: str
    access_note: str
    source_version: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "title",
            "uri",
            "access_note",
            "source_version",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValueError("validation beta frontier sources must use HTTPS")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("validation beta frontier source address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierRecord:
    """One expected-state execution row with a complete data boundary."""

    record_id: str
    operation: ValidationBetaFrontierOperation
    role: ValidationBetaFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "context_key",
            "expected_state",
            "notes",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValueError("validation beta frontier records require source IDs")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("validation beta frontier record address must be SHA-256")
        if any(not str(item).strip() for item in self.expected_issue_codes):
            raise ValueError("validation beta frontier issue codes cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierFixture:
    """A closed, addressable, public aggregate planning fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[ValidationBetaFrontierSourceReceipt, ...]
    records: tuple[ValidationBetaFrontierRecord, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "fixture_id",
            "fixture_version",
            "context_key",
            "evidence_boundary",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.sources or not self.records:
            raise ValueError("validation beta frontier fixture requires sources and records")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("validation beta frontier fixture address must be SHA-256")

    @property
    def positive_records(self) -> tuple[ValidationBetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is ValidationBetaFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[ValidationBetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is ValidationBetaFrontierRole.CONTROL)

    def record_map(self) -> dict[str, ValidationBetaFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def source_map(self) -> dict[str, ValidationBetaFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def operation_map(self) -> dict[ValidationBetaFrontierOperation, tuple[ValidationBetaFrontierRecord, ...]]:
        return {
            operation: tuple(item for item in self.records if item.operation is operation)
            for operation in ValidationBetaFrontierOperation
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierDataAudit:
    fixture_id: str
    checks: tuple[ValidationBetaFrontierDataCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def _source(source_id: str, title: str, uri: str, note: str, version: str) -> ValidationBetaFrontierSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "access_note": note,
        "source_version": version,
    }
    return ValidationBetaFrontierSourceReceipt(**body, content_address=content_hash(body))


def _context_parts(context_key: str) -> dict[str, str]:
    values = context_key.split("|")
    if len(values) != 6:
        raise ValueError("validation beta frontier context key must have six fields")
    return {
        "genome_build": values[0],
        "disease_class": values[1],
        "age_group": values[2],
        "cell_state": values[3],
        "territory": values[4],
        "treatment_phase": values[5],
    }


def _sequence(reference: str = "C", *, length: int = 41, offset: int = 20) -> str:
    if offset + len(reference) > length:
        raise ValueError("fixture sequence offset exceeds requested length")
    bases = ("ACGT" * ((length // 4) + 1))[:length]
    return bases[:offset] + reference + bases[offset + len(reference) :]


def _target(
    target_id: str,
    *,
    context_key: str = VALIDATION_BETA_FRONTIER_CONTEXT_KEY,
    reference: str = "C",
    alternate: str = "T",
    sequence: str | None = None,
    offset: int = 20,
    source_id: str = "ncbi-refseq",
) -> dict[str, Any]:
    sequence_value = sequence or _sequence(reference, offset=offset)
    return {
        "target_id": target_id,
        "variant_id": f"{target_id}-variant",
        "element_id": f"{target_id}-element",
        "gene_id": "GENE1",
        "sequence": sequence_value,
        "variant_offset": offset,
        "reference_allele": reference,
        "alternate_allele": alternate,
        "context_key": context_key,
        "source_id": source_id,
        "source_version": "GRCh38-public-window-v1",
        "raw_hash": content_hash({"target_id": target_id, "sequence": sequence_value}),
        "annotations": {
            "element_type": "candidate_enhancer",
            "aggregate_scope": "public_non_patient",
        },
    }


def _constraints(
    design_id: str,
    mode: str,
    *,
    context_key: str = VALIDATION_BETA_FRONTIER_CONTEXT_KEY,
    max_guides: int = 50,
    guide_length: int = 20,
    require_pam: bool = False,
    pbs_length: int = 13,
    rtt_length: int = 20,
    maximum_edit_length: int = 50,
) -> dict[str, Any]:
    return {
        "design_id": design_id,
        "context_key": context_key,
        "mode": mode,
        "guide_length": guide_length,
        "max_guides": max_guides,
        "minimum_on_target": 0.40,
        "minimum_specificity": 0.70,
        "maximum_off_target": 0.30,
        "require_variant_overlap": False,
        "require_pam": require_pam,
        "pam_pattern": "NGG",
        "editing_window_start": 0,
        "editing_window_end": 40,
        "pbs_length": pbs_length,
        "rtt_length": rtt_length,
        "maximum_edit_length": maximum_edit_length,
        "control_requirements": ["non_targeting", "positive_control", "mock"],
        "readout_requirements": ["editing_rate", "viability", "expression"],
        "model_system": "stem_like_organoid",
    }


def _record(
    record_id: str,
    operation: ValidationBetaFrontierOperation,
    role: ValidationBetaFrontierRole,
    payload: dict[str, Any],
    expected_state: str,
    issue_codes: tuple[str, ...],
    notes: str,
    *,
    context_key: str = VALIDATION_BETA_FRONTIER_CONTEXT_KEY,
    source_ids: tuple[str, ...] = ("ncbi-refseq", "geo", "addgene", "ensembl"),
) -> ValidationBetaFrontierRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": context_key,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": issue_codes,
        "notes": notes,
    }
    return ValidationBetaFrontierRecord(**body, content_address=content_hash(body))


def _eligibility_row(
    observation_id: str,
    target_id: str,
    *,
    context_key: str = VALIDATION_BETA_FRONTIER_CONTEXT_KEY,
    model_system: str = "stem_like_organoid",
    eligible: bool = True,
    strength: float = 0.86,
    supported_contexts: tuple[str, ...] = (VALIDATION_BETA_FRONTIER_CONTEXT_KEY,),
    blockers: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "target_id": target_id,
        "model_system": model_system,
        "context_key": context_key,
        "supported_contexts": list(supported_contexts),
        "cell_state": "stem_like",
        "evidence_strength": strength,
        "source_id": "geo",
        "source_version": "public-aggregate-v1",
        "raw_hash": content_hash({"observation_id": observation_id, "target_id": target_id}),
        "eligible": eligible,
        "blockers": list(blockers),
        "attributes": {"evidence_scope": "aggregate_public"},
    }


def _power_row(
    observation_id: str,
    design_id: str,
    *,
    context_key: str = VALIDATION_BETA_FRONTIER_CONTEXT_KEY,
    planned_replicates: int = 48,
    effect_size: float = 0.40,
    variance: float = 0.20,
) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "design_id": design_id,
        "assay_id": "amplicon-editing-v1",
        "effect_size": effect_size,
        "variance": variance,
        "alpha": 0.05,
        "target_power": 0.80,
        "planned_replicates": planned_replicates,
        "blocking_factor_count": 2,
        "context_key": context_key,
        "source_id": "geo",
        "source_version": "public-aggregate-v1",
        "raw_hash": content_hash({"observation_id": observation_id, "planned": planned_replicates}),
        "attributes": {"planning_scope": "aggregate_proxy"},
    }


def default_validation_beta_frontier_fixture() -> ValidationBetaFrontierFixture:
    """Return the deterministic 32-row public aggregate fixture."""

    sources = (
        _source(
            "ncbi-refseq",
            "NCBI Reference Sequence",
            "https://www.ncbi.nlm.nih.gov/refseq/",
            "public reference-sequence identity and coordinate receipt",
            "GRCh38-public-window-v1",
        ),
        _source(
            "geo",
            "NCBI Gene Expression Omnibus",
            "https://www.ncbi.nlm.nih.gov/geo/",
            "public aggregate assay and model-context receipt",
            "public-index",
        ),
        _source(
            "addgene",
            "Addgene CRISPR resources",
            "https://www.addgene.org/crispr/",
            "public guide and perturbation planning reference",
            "public-index",
        ),
        _source(
            "broad-gpp",
            "Broad Genetic Perturbation Platform",
            "https://portals.broadinstitute.org/gpp/public/",
            "public perturbation design reference",
            "public-index",
        ),
        _source(
            "encode",
            "ENCODE Project",
            "https://www.encodeproject.org/",
            "public context and assay metadata reference",
            "public-index",
        ),
        _source(
            "pubmed",
            "PubMed",
            "https://pubmed.ncbi.nlm.nih.gov/",
            "public literature-index receipt",
            "public-index",
        ),
        _source(
            "ensembl",
            "Ensembl genome browser",
            "https://www.ensembl.org/",
            "public genome annotation reference",
            "GRCh38-public",
        ),
    )
    target = _target("target-positive")
    records: list[ValidationBetaFrontierRecord] = []
    records.extend(
        (
            _record(
                "C05-POS-001",
                ValidationBetaFrontierOperation.CRISPR_DESIGN,
                ValidationBetaFrontierRole.POSITIVE,
                {
                    "targets": [target],
                    "modes": ["crispri", "crispra"],
                    "constraints": _constraints("crispr-positive", "crispri"),
                },
                "ready_for_review",
                (),
                "CRISPRi and CRISPRa local candidates meet declared gates.",
            ),
            _record(
                "C05-CTRL-001",
                ValidationBetaFrontierOperation.CRISPR_DESIGN,
                ValidationBetaFrontierRole.CONTROL,
                {
                    "targets": [_target("target-foreign", context_key=VALIDATION_BETA_FRONTIER_FOREIGN_CONTEXT)],
                    "modes": ["crispri", "crispra"],
                    "constraints": _constraints("crispr-foreign", "crispri"),
                },
                "blocked",
                ("context_mismatch",),
                "foreign territory and treatment context cannot be transported.",
            ),
            _record(
                "C05-CTRL-002",
                ValidationBetaFrontierOperation.CRISPR_DESIGN,
                ValidationBetaFrontierRole.CONTROL,
                {
                    "targets": [target],
                    "modes": ["crispri", "crispra"],
                    "constraints": _constraints("crispr-budget", "crispri", max_guides=1),
                },
                "blocked",
                ("max_guides_exceeded",),
                "candidate budget is retained as a blocking control.",
            ),
            _record(
                "C05-CTRL-003",
                ValidationBetaFrontierOperation.CRISPR_DESIGN,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [], "modes": ["crispri", "crispra"], "constraints": _constraints("crispr-empty", "crispri")},
                "blocked",
                ("no_validation_targets",),
                "an empty target list cannot silently become a design.",
            ),
        )
    )
    records.extend(
        (
            _record(
                "C06-POS-001",
                ValidationBetaFrontierOperation.BASE_EDITING,
                ValidationBetaFrontierRole.POSITIVE,
                {"targets": [target], "constraints": _constraints("base-positive", "base_editing")},
                "ready_for_review",
                (),
                "C-to-T single-base edit stays inside the declared planning window.",
            ),
            _record(
                "C06-CTRL-001",
                ValidationBetaFrontierOperation.BASE_EDITING,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [_target("base-unsupported", reference="G", alternate="C")], "constraints": _constraints("base-unsupported", "base_editing")},
                "blocked",
                ("unsupported_base_edit_substitution",),
                "unsupported chemistry remains blocked rather than inferred.",
            ),
            _record(
                "C06-CTRL-002",
                ValidationBetaFrontierOperation.BASE_EDITING,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [_target("base-foreign", context_key=VALIDATION_BETA_FRONTIER_FOREIGN_CONTEXT)], "constraints": _constraints("base-foreign", "base_editing")},
                "blocked",
                ("context_mismatch",),
                "foreign-context editing is not a negative biological result.",
            ),
            _record(
                "C06-CTRL-003",
                ValidationBetaFrontierOperation.BASE_EDITING,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [], "constraints": _constraints("base-empty", "base_editing")},
                "blocked",
                ("no_validation_targets",),
                "missing targets block base-editing planning.",
            ),
        )
    )
    records.extend(
        (
            _record(
                "C07-POS-001",
                ValidationBetaFrontierOperation.PRIME_EDITING,
                ValidationBetaFrontierRole.POSITIVE,
                {"targets": [target], "constraints": _constraints("prime-positive", "prime_editing")},
                "ready_for_review",
                (),
                "prime-editing PBS, RTT, and edit receipts are retained.",
            ),
            _record(
                "C07-CTRL-001",
                ValidationBetaFrontierOperation.PRIME_EDITING,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [_target("prime-long", alternate="A" * 60)], "constraints": _constraints("prime-long", "prime_editing")},
                "blocked",
                ("edit_exceeds_prime_editing_length",),
                "an edit longer than the declared maximum is blocked.",
            ),
            _record(
                "C07-CTRL-002",
                ValidationBetaFrontierOperation.PRIME_EDITING,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [_target("prime-short", sequence=_sequence("C", length=20, offset=2), offset=2)], "constraints": _constraints("prime-short", "prime_editing")},
                "blocked",
                ("prime_editing_flank_shortage",),
                "insufficient PBS flank remains a design blocker.",
            ),
            _record(
                "C07-CTRL-003",
                ValidationBetaFrontierOperation.PRIME_EDITING,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [], "constraints": _constraints("prime-empty", "prime_editing")},
                "blocked",
                ("no_validation_targets",),
                "missing targets block prime-editing planning.",
            ),
        )
    )
    records.extend(
        (
            _record(
                "C08-POS-001",
                ValidationBetaFrontierOperation.ALLELE_REPORTER,
                ValidationBetaFrontierRole.POSITIVE,
                {"targets": [target], "constraints": _constraints("reporter-positive", "allele_specific_reporter", max_guides=4)},
                "ready_for_review",
                (),
                "reference and alternate constructs remain paired.",
            ),
            _record(
                "C08-CTRL-001",
                ValidationBetaFrontierOperation.ALLELE_REPORTER,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [_target("reporter-foreign", context_key=VALIDATION_BETA_FRONTIER_FOREIGN_CONTEXT)], "constraints": _constraints("reporter-foreign", "allele_specific_reporter", max_guides=4)},
                "blocked",
                ("context_mismatch",),
                "foreign-context constructs cannot be paired with the requested context.",
            ),
            _record(
                "C08-CTRL-002",
                ValidationBetaFrontierOperation.ALLELE_REPORTER,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [target], "constraints": _constraints("reporter-budget", "allele_specific_reporter", max_guides=1)},
                "blocked",
                ("max_constructs_exceeded",),
                "the paired construct budget is a hard boundary.",
            ),
            _record(
                "C08-CTRL-003",
                ValidationBetaFrontierOperation.ALLELE_REPORTER,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [], "constraints": _constraints("reporter-empty", "allele_specific_reporter", max_guides=4)},
                "blocked",
                ("no_validation_targets",),
                "an empty allele set cannot produce a reporter package.",
            ),
        )
    )
    records.extend(
        (
            _record(
                "C09-POS-001",
                ValidationBetaFrontierOperation.MODEL_ELIGIBILITY,
                ValidationBetaFrontierRole.POSITIVE,
                {"observations": [_eligibility_row("elig-pos", "target-positive")], "model_system": "stem_like_organoid", "minimum_evidence_strength": 0.5},
                "ready_for_review",
                (),
                "model, cell state, context, and evidence floor are declared.",
                source_ids=("geo", "encode"),
            ),
            _record(
                "C09-CTRL-001",
                ValidationBetaFrontierOperation.MODEL_ELIGIBILITY,
                ValidationBetaFrontierRole.CONTROL,
                {"observations": [_eligibility_row("elig-foreign", "target-foreign", context_key=VALIDATION_BETA_FRONTIER_FOREIGN_CONTEXT, supported_contexts=(VALIDATION_BETA_FRONTIER_FOREIGN_CONTEXT,))], "model_system": "stem_like_organoid", "minimum_evidence_strength": 0.5},
                "out_of_domain",
                ("context_mismatch",),
                "foreign observations are excluded before matching.",
                source_ids=("geo", "encode"),
            ),
            _record(
                "C09-CTRL-002",
                ValidationBetaFrontierOperation.MODEL_ELIGIBILITY,
                ValidationBetaFrontierRole.CONTROL,
                {"observations": [_eligibility_row("elig-model", "target-positive", model_system="stem_like_organoid", eligible=False, strength=0.2, supported_contexts=(), blockers=("model_not_supported",))], "model_system": "stem_like_organoid", "minimum_evidence_strength": 0.5},
                "blocked",
                ("context_not_declared_supported", "no_declared_eligible_model_system"),
                "model mismatch stays a planning blocker.",
                source_ids=("geo",),
            ),
            _record(
                "C09-CTRL-003",
                ValidationBetaFrontierOperation.MODEL_ELIGIBILITY,
                ValidationBetaFrontierRole.CONTROL,
                {"observations": [], "model_system": "stem_like_organoid", "minimum_evidence_strength": 0.5},
                "abstained",
                (),
                "no observations produce an explicit abstention.",
                source_ids=("geo",),
            ),
        )
    )
    records.extend(
        (
            _record(
                "C10-POS-001",
                ValidationBetaFrontierOperation.GUIDE_OLIGO,
                ValidationBetaFrontierRole.POSITIVE,
                {"source_id": "addgene", "source_version": "public-guide-v1", "input_format": "tsv", "text": "observation_id\tdesign_id\ttarget_id\toligo_id\toligo_type\tsequence\tcontext_key\nobs-1\tdesign-1\ttarget-positive\tguide-1\tguide\tACGTACGTACGTACGTACGT\t" + VALIDATION_BETA_FRONTIER_CONTEXT_KEY + "\nobs-2\tdesign-1\ttarget-positive\tguide-2\tguide\tTGCATGCATGCATGCATGCA\t" + VALIDATION_BETA_FRONTIER_CONTEXT_KEY + "\n"},
                "ready_for_review",
                (),
                "public guide rows are adapted without rewriting sequence roles.",
                source_ids=("addgene", "broad-gpp"),
            ),
            _record(
                "C10-CTRL-001",
                ValidationBetaFrontierOperation.GUIDE_OLIGO,
                ValidationBetaFrontierRole.CONTROL,
                {"source_id": "addgene", "source_version": "public-guide-v1", "input_format": "tsv", "text": "observation_id\tdesign_id\ttarget_id\toligo_id\toligo_type\tsequence\tcontext_key\nobs-bad\tdesign-1\ttarget-positive\tguide-bad\tguide\tINVALID\t" + VALIDATION_BETA_FRONTIER_CONTEXT_KEY + "\n"},
                "partial",
                ("invalid_guide_oligo_row",),
                "malformed source rows are quarantined with their row hash.",
                source_ids=("addgene",),
            ),
            _record(
                "C10-CTRL-002",
                ValidationBetaFrontierOperation.GUIDE_OLIGO,
                ValidationBetaFrontierRole.CONTROL,
                {"source_id": "addgene", "source_version": "public-guide-v1", "input_format": "tsv", "text": "observation_id\tdesign_id\ttarget_id\toligo_id\toligo_type\tsequence\tcontext_key\nobs-foreign\tdesign-1\ttarget-foreign\tguide-foreign\tguide\tACGTACGT\t" + VALIDATION_BETA_FRONTIER_FOREIGN_CONTEXT + "\n"},
                "partial",
                ("context_mismatch",),
                "adapter output outside the request context remains reviewable.",
                source_ids=("addgene",),
            ),
            _record(
                "C10-CTRL-003",
                ValidationBetaFrontierOperation.GUIDE_OLIGO,
                ValidationBetaFrontierRole.CONTROL,
                {"source_id": "addgene", "source_version": "public-guide-v1", "input_format": "tsv", "text": "observation_id\tdesign_id\ttarget_id\toligo_id\toligo_type\tsequence\tcontext_key\n"},
                "abstained",
                (),
                "an empty design source is explicit abstention, not absence of guides.",
                source_ids=("addgene",),
            ),
        )
    )
    records.extend(
        (
            _record(
                "C11-POS-001",
                ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION,
                ValidationBetaFrontierRole.POSITIVE,
                {"targets": [{"target_id": "target-positive", "condition": "crispri", "context_key": VALIDATION_BETA_FRONTIER_CONTEXT_KEY, "source_id": "geo"}], "plan_id": "controls-positive", "control_types": ["negative", "non_targeting", "positive"], "biological_replicates": 3, "technical_replicates": 2, "randomization_seed": "public-seed-1"},
                "ready_for_review",
                (),
                "control assignments are deterministic and content-addressed.",
                source_ids=("geo", "addgene"),
            ),
            _record(
                "C11-CTRL-001",
                ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [{"target_id": "target-foreign", "condition": "crispri", "context_key": VALIDATION_BETA_FRONTIER_FOREIGN_CONTEXT, "source_id": "geo"}], "plan_id": "controls-foreign", "control_types": ["negative"], "biological_replicates": 2, "technical_replicates": 1, "randomization_seed": "public-seed-1"},
                "blocked",
                ("context_mismatch",),
                "foreign-context assignments are not transported.",
                source_ids=("geo",),
            ),
            _record(
                "C11-CTRL-002",
                ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [{"condition": "crispri", "context_key": VALIDATION_BETA_FRONTIER_CONTEXT_KEY}], "plan_id": "controls-missing-id", "control_types": ["negative"], "biological_replicates": 2, "technical_replicates": 1, "randomization_seed": "public-seed-1"},
                "blocked",
                ("missing_target_id",),
                "assignment rows require stable target identity.",
                source_ids=("geo",),
            ),
            _record(
                "C11-CTRL-003",
                ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION,
                ValidationBetaFrontierRole.CONTROL,
                {"targets": [], "plan_id": "controls-empty", "control_types": ["negative"], "biological_replicates": 2, "technical_replicates": 1, "randomization_seed": "public-seed-1"},
                "blocked",
                ("no_targets",),
                "an empty control plan remains blocked.",
                source_ids=("geo",),
            ),
        )
    )
    records.extend(
        (
            _record(
                "C12-POS-001",
                ValidationBetaFrontierOperation.POWER_REPLICATION,
                ValidationBetaFrontierRole.POSITIVE,
                {"observations": [_power_row("power-pos", "design-positive") ]},
                "ready_for_review",
                (),
                "normal-approximation requirement and achieved-power proxy are visible.",
                source_ids=("geo", "pubmed"),
            ),
            _record(
                "C12-CTRL-001",
                ValidationBetaFrontierOperation.POWER_REPLICATION,
                ValidationBetaFrontierRole.CONTROL,
                {"observations": [_power_row("power-short", "design-short", planned_replicates=1)]},
                "partial",
                (),
                "planned replicate shortfall remains partial.",
                source_ids=("geo",),
            ),
            _record(
                "C12-CTRL-002",
                ValidationBetaFrontierOperation.POWER_REPLICATION,
                ValidationBetaFrontierRole.CONTROL,
                {"observations": [_power_row("power-foreign", "design-foreign", context_key=VALIDATION_BETA_FRONTIER_FOREIGN_CONTEXT)]},
                "out_of_domain",
                ("context_mismatch",),
                "foreign power observations are retained as context review.",
                source_ids=("geo",),
            ),
            _record(
                "C12-CTRL-003",
                ValidationBetaFrontierOperation.POWER_REPLICATION,
                ValidationBetaFrontierRole.CONTROL,
                {"observations": [{"observation_id": "power-invalid", "design_id": "design-invalid", "assay_id": "assay", "effect_size": 0.4, "variance": 0, "alpha": 0.05, "target_power": 0.8, "planned_replicates": 4, "context_key": VALIDATION_BETA_FRONTIER_CONTEXT_KEY, "source_id": "geo", "source_version": "public", "raw_hash": "invalid-variance"}]},
                "abstained",
                ("invalid_power_row",),
                "invalid variance is quarantined before estimation.",
                source_ids=("geo",),
            ),
        )
    )
    body = {
        "fixture_id": "validation-beta-frontier-public-aggregate",
        "fixture_version": VALIDATION_BETA_FRONTIER_FIXTURE_VERSION,
        "context_key": VALIDATION_BETA_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": VALIDATION_BETA_FRONTIER_BOUNDARY,
        "sources": sources,
        "records": tuple(records),
    }
    return ValidationBetaFrontierFixture(**body, content_address=content_hash(body))


def build_validation_beta_frontier_catalog(fixture: ValidationBetaFrontierFixture) -> dict[str, Any]:
    """Build a deterministic catalog of records, sources, and operation counts."""

    operation_counts = {
        operation.value: len(fixture.operation_map()[operation])
        for operation in ValidationBetaFrontierOperation
    }
    body = {
        "fixture_id": fixture.fixture_id,
        "record_ids": tuple(item.record_id for item in fixture.records),
        "source_ids": tuple(item.source_id for item in fixture.sources),
        "operations": tuple(item.value for item in ValidationBetaFrontierOperation),
        "operation_counts": operation_counts,
        "context_key": fixture.context_key,
    }
    return body | {"content_address": content_hash(body)}


def audit_validation_beta_frontier_data(
    fixture: ValidationBetaFrontierFixture,
) -> ValidationBetaFrontierDataAudit:
    """Validate source closure, row balance, context shape, and addresses."""

    catalog = build_validation_beta_frontier_catalog(fixture)
    source_ids = set(catalog["source_ids"])
    operation_values = {item.operation for item in fixture.records}
    expected_operations = set(ValidationBetaFrontierOperation)
    checks_raw: tuple[tuple[str, bool, Any, Any, str], ...] = (
        ("fixture-id", fixture.fixture_id == "validation-beta-frontier-public-aggregate", fixture.fixture_id, "validation-beta-frontier-public-aggregate", "fixture identity is stable"),
        ("fixture-version", fixture.fixture_version == VALIDATION_BETA_FRONTIER_FIXTURE_VERSION, fixture.fixture_version, VALIDATION_BETA_FRONTIER_FIXTURE_VERSION, "fixture version is explicit"),
        ("boundary", fixture.evidence_boundary == VALIDATION_BETA_FRONTIER_BOUNDARY, fixture.evidence_boundary, VALIDATION_BETA_FRONTIER_BOUNDARY, "aggregate evidence boundary is explicit"),
        ("source-count", len(fixture.sources) == VALIDATION_BETA_FRONTIER_SOURCE_COUNT, len(fixture.sources), VALIDATION_BETA_FRONTIER_SOURCE_COUNT, "all public sources are retained"),
        ("record-count", len(fixture.records) == VALIDATION_BETA_FRONTIER_RECORD_COUNT, len(fixture.records), VALIDATION_BETA_FRONTIER_RECORD_COUNT, "all operation records are retained"),
        ("positive-count", len(fixture.positive_records) == VALIDATION_BETA_FRONTIER_POSITIVE_COUNT, len(fixture.positive_records), VALIDATION_BETA_FRONTIER_POSITIVE_COUNT, "one positive record per operation"),
        ("control-count", len(fixture.control_records) == VALIDATION_BETA_FRONTIER_CONTROL_COUNT, len(fixture.control_records), VALIDATION_BETA_FRONTIER_CONTROL_COUNT, "three controls per operation"),
        ("unique-records", len(set(catalog["record_ids"])) == len(fixture.records), len(set(catalog["record_ids"])), len(fixture.records), "record identifiers are unique"),
        ("operation-closure", operation_values == expected_operations, sorted(item.value for item in operation_values), sorted(item.value for item in expected_operations), "all eight operation families are represented"),
        ("source-closure", all(set(item.source_ids).issubset(source_ids) for item in fixture.records), True, True, "record source IDs resolve to receipts"),
        ("context-shape", all(len(item.context_key.split("|")) == 6 for item in fixture.records), True, True, "record contexts use six-field keys"),
        ("https-sources", all(item.uri.startswith("https://") for item in fixture.sources), True, True, "source receipts use HTTPS"),
        ("address-closure", all(item.content_address.startswith("sha256:") for item in fixture.records + fixture.sources), True, True, "source and record addresses are present"),
    )
    checks = tuple(
        ValidationBetaFrontierDataCheck(
            check_id=check_id,
            passed=passed,
            observed=observed,
            required=required,
            detail=detail,
            content_address=content_hash({"check_id": check_id, "passed": passed, "observed": observed, "required": required}),
        )
        for check_id, passed, observed, required, detail in checks_raw
    )
    failed = tuple(item.check_id for item in checks if not item.passed)
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "accepted": not failed, "failed_check_ids": failed}
    return ValidationBetaFrontierDataAudit(**body, content_address=content_hash(body))


def validation_beta_frontier_fixture_json(
    fixture: ValidationBetaFrontierFixture | None = None,
) -> str:
    """Serialize the fixture using the repository's canonical JSON encoder."""

    return json.dumps((fixture or default_validation_beta_frontier_fixture()).to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load_validation_beta_frontier_fixture(path: str | Path) -> ValidationBetaFrontierFixture:
    """Load a serialized fixture while rehydrating its declared enums."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("validation beta frontier fixture JSON must be an object")
    sources = tuple(ValidationBetaFrontierSourceReceipt(**item) for item in raw.get("sources", ()))
    records = tuple(
        ValidationBetaFrontierRecord(
            record_id=str(item["record_id"]),
            operation=ValidationBetaFrontierOperation(item["operation"]),
            role=ValidationBetaFrontierRole(item["role"]),
            context_key=str(item["context_key"]),
            source_ids=tuple(str(value) for value in item["source_ids"]),
            payload=dict(item["payload"]),
            expected_state=str(item["expected_state"]),
            expected_issue_codes=tuple(str(value) for value in item.get("expected_issue_codes", ())),
            notes=str(item["notes"]),
            content_address=str(item["content_address"]),
        )
        for item in raw.get("records", ())
    )
    return ValidationBetaFrontierFixture(
        fixture_id=str(raw["fixture_id"]),
        fixture_version=str(raw["fixture_version"]),
        context_key=str(raw["context_key"]),
        evidence_boundary=str(raw["evidence_boundary"]),
        sources=sources,
        records=records,
        content_address=str(raw["content_address"]),
    )


__all__ = [
    "VALIDATION_BETA_FRONTIER_BOUNDARY",
    "VALIDATION_BETA_FRONTIER_CONTEXT_KEY",
    "VALIDATION_BETA_FRONTIER_CONTROL_COUNT",
    "VALIDATION_BETA_FRONTIER_FOREIGN_CONTEXT",
    "VALIDATION_BETA_FRONTIER_FIXTURE_VERSION",
    "VALIDATION_BETA_FRONTIER_POSITIVE_COUNT",
    "VALIDATION_BETA_FRONTIER_RECORD_COUNT",
    "VALIDATION_BETA_FRONTIER_SOURCE_COUNT",
    "ValidationBetaFrontierDataAudit",
    "ValidationBetaFrontierDataCheck",
    "ValidationBetaFrontierFixture",
    "ValidationBetaFrontierOperation",
    "ValidationBetaFrontierRecord",
    "ValidationBetaFrontierRole",
    "ValidationBetaFrontierSourceReceipt",
    "audit_validation_beta_frontier_data",
    "build_validation_beta_frontier_catalog",
    "default_validation_beta_frontier_fixture",
    "load_validation_beta_frontier_fixture",
    "validation_beta_frontier_fixture_json",
]
