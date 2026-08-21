"""GLIO-NONCODE research workbench.

The package exposes a small, deterministic vertical slice for turning a case
manifest into inspectable regulatory hypotheses. It is intentionally local
first and research-use only.
"""

from .control_plane import ControlPlaneExecutor, default_control_plane_registry
from .control_plane_app import ControlPlaneApplication
from .atlas import AtlasBundle, AtlasQuery, PublicAtlasRetriever
from .intake import VariantIndex, VariantIntake
from .lifecycle import DriftMonitor, LifecycleReclassifier, ReviewPacketBuilder
from .models import (
    CaseManifest,
    Dossier,
    EvidenceClaim,
    Hypothesis,
    ReferenceContext,
    VariantIdentity,
)
from .reference_registry import ReferenceProjector, default_reference_registry
from .runtime import CaseRuntime
from .sequence_inference import MotifDefinition, SequenceInference
from .uncertainty import OutOfDomainDetector, UncertaintyPropagator
from .validation_controls import (
    NegativeControlBuilder,
    ValidationValuePlanner,
)
from .validation_design import GuideDesigner, PowerPlanner
from .structural_reconstruction import ReconstructionResult, StructuralReconstructor

__all__ = [
    "CaseManifest",
    "AtlasBundle",
    "AtlasQuery",
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
    "DriftMonitor",
    "LifecycleReclassifier",
    "ReviewPacketBuilder",
    "default_control_plane_registry",
]

__version__ = "0.1.0"
