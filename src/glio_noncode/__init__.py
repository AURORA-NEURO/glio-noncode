"""GLIO-NONCODE research workbench.

The package exposes a small, deterministic vertical slice for turning a case
manifest into inspectable regulatory hypotheses. It is intentionally local
first and research-use only.
"""

from .control_plane import ControlPlaneExecutor, default_control_plane_registry
from .atlas import AtlasBundle, AtlasQuery, PublicAtlasRetriever
from .intake import VariantIndex, VariantIntake
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
from .structural_reconstruction import ReconstructionResult, StructuralReconstructor

__all__ = [
    "CaseManifest",
    "AtlasBundle",
    "AtlasQuery",
    "CaseRuntime",
    "ControlPlaneExecutor",
    "Dossier",
    "EvidenceClaim",
    "Hypothesis",
    "ReferenceContext",
    "ReconstructionResult",
    "ReferenceProjector",
    "PublicAtlasRetriever",
    "StructuralReconstructor",
    "default_reference_registry",
    "VariantIdentity",
    "VariantIndex",
    "VariantIntake",
    "default_control_plane_registry",
]

__version__ = "0.1.0"
