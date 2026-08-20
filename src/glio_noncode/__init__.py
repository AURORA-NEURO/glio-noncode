"""GLIO-NONCODE research workbench.

The package exposes a small, deterministic vertical slice for turning a case
manifest into inspectable regulatory hypotheses. It is intentionally local
first and research-use only.
"""

from .control_plane import ControlPlaneExecutor, default_control_plane_registry
from .models import (
    CaseManifest,
    Dossier,
    EvidenceClaim,
    Hypothesis,
    ReferenceContext,
    VariantIdentity,
)
from .runtime import CaseRuntime

__all__ = [
    "CaseManifest",
    "CaseRuntime",
    "ControlPlaneExecutor",
    "Dossier",
    "EvidenceClaim",
    "Hypothesis",
    "ReferenceContext",
    "VariantIdentity",
    "default_control_plane_registry",
]

__version__ = "0.1.0"
