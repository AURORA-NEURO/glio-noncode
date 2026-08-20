"""Small machine-readable contract document for clients and adapters."""

from __future__ import annotations

from .models import (
    AssayType,
    EdgeType,
    EvidenceState,
    EvidenceTier,
    ResearchStatus,
    SupportLevel,
    VariantKind,
    VariantOrigin,
    enum_values,
)


def schema_document() -> dict[str, object]:
    """Return a stable summary schema for the first public API surface."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/AURORA-NEURO/glio-noncode/schemas/v0.1",
        "title": "GLIO-NONCODE Case Manifest and Research Dossier",
        "type": "object",
        "required": ["case_id", "subject_id", "context", "variants"],
        "properties": {
            "case_id": {"type": "string", "minLength": 1},
            "subject_id": {"type": "string", "minLength": 1},
            "context": {"$ref": "#/$defs/reference_context"},
            "variants": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/variant"}},
            "candidate_elements": {"type": "array", "items": {"$ref": "#/$defs/candidate_element"}},
            "metadata": {"type": "object"},
            "input_versions": {"type": "object", "additionalProperties": {"type": "string"}},
        },
        "$defs": {
            "reference_context": {
                "type": "object",
                "required": ["genome_build", "disease_class", "age_group", "cell_state"],
                "properties": {
                    "genome_build": {"type": "string"},
                    "disease_class": {"type": "string"},
                    "age_group": {"type": "string"},
                    "cell_state": {"type": "string"},
                    "territory": {"type": "string"},
                    "treatment_phase": {"type": "string"},
                    "assay_support": {"type": "array", "items": {"type": "string"}},
                    "source_version": {"type": "string"},
                },
            },
            "variant": {
                "type": "object",
                "required": ["variant_id", "kind", "chromosome", "start", "end", "reference", "alternate", "genome_build"],
                "properties": {
                    "variant_id": {"type": "string"},
                    "kind": {"enum": enum_values(VariantKind)},
                    "chromosome": {"type": "string"},
                    "start": {"type": "integer", "minimum": 1},
                    "end": {"type": "integer", "minimum": 1},
                    "reference": {"type": "string"},
                    "alternate": {"type": "string"},
                    "genome_build": {"type": "string"},
                    "origin": {"enum": enum_values(VariantOrigin)},
                    "clonality": {"type": "string"},
                    "sample_id": {"type": "string"},
                    "annotations": {"type": "object"},
                },
            },
            "candidate_element": {
                "type": "object",
                "required": ["element_id", "chromosome", "start", "end", "element_type", "source_id"],
                "properties": {
                    "element_id": {"type": "string"},
                    "chromosome": {"type": "string"},
                    "start": {"type": "integer", "minimum": 1},
                    "end": {"type": "integer", "minimum": 1},
                    "element_type": {"type": "string"},
                    "source_id": {"type": "string"},
                    "target_genes": {"type": "array", "items": {"type": "string"}},
                    "state_ids": {"type": "array", "items": {"type": "string"}},
                    "features": {"type": "object", "additionalProperties": {"type": "number"}},
                },
            },
        },
        "enums": {
            "assay_type": enum_values(AssayType),
            "edge_type": enum_values(EdgeType),
            "evidence_state": enum_values(EvidenceState),
            "evidence_tier": enum_values(EvidenceTier),
            "research_status": enum_values(ResearchStatus),
            "support_level": enum_values(SupportLevel),
        },
    }
