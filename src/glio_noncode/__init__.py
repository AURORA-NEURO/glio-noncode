"""GLIO-NONCODE research workbench.

The package exposes a small, deterministic vertical slice for turning a case
manifest into inspectable regulatory hypotheses. It is intentionally local
first and research-use only.
"""

from .assay_qc import AssayQCEvaluator
from .atlas import AtlasBundle, AtlasQuery, PublicAtlasRetriever
from .atlas_context import ContextEvidenceBuilder, ContextObservation
from .control_plane import ControlPlaneExecutor, default_control_plane_registry
from .control_plane_app import ControlPlaneApplication
from .inference_extensions import InferenceExtensionSuite
from .intake import VariantIndex, VariantIntake
from .lifecycle import DriftMonitor, LifecycleReclassifier, ReviewPacketBuilder
from .lineage import LineageResolver
from .models import (
    CaseManifest,
    Dossier,
    EvidenceClaim,
    Hypothesis,
    ReferenceContext,
    VariantIdentity,
)
from .origin import OriginClonalityAssessor
from .reference_registry import ReferenceProjector, default_reference_registry
from .runtime import CaseRuntime
from .sequence_inference import MotifDefinition, SequenceInference
from .structural_reconstruction import ReconstructionResult, StructuralReconstructor
from .uncertainty import OutOfDomainDetector, UncertaintyPropagator
from .validation_controls import (
    NegativeControlBuilder,
    ValidationValuePlanner,
)
from .validation_design import GuideDesigner, PowerPlanner

__all__ = [
    "CaseManifest",
    "AssayQCEvaluator",
    "ContextEvidenceBuilder",
    "ContextObservation",
    "AtlasBundle",
    "AtlasQuery",
    "InferenceExtensionSuite",
    "CaseRuntime",
    "ControlPlaneExecutor",
    "ControlPlaneApplication",
    "Dossier",
    "EvidenceClaim",
    "Hypothesis",
    "ReferenceContext",
    "ReconstructionResult",
    "ReferenceProjector",
    "MotifDefinition",
    "PublicAtlasRetriever",
    "StructuralReconstructor",
    "SequenceInference",
    "OutOfDomainDetector",
    "UncertaintyPropagator",
    "GuideDesigner",
    "NegativeControlBuilder",
    "PowerPlanner",
    "ValidationValuePlanner",
    "default_reference_registry",
    "VariantIdentity",
    "VariantIndex",
    "VariantIntake",
    "LineageResolver",
    "OriginClonalityAssessor",
    "DriftMonitor",
    "LifecycleReclassifier",
    "ReviewPacketBuilder",
    "default_control_plane_registry",
]

__version__ = "0.1.0"
