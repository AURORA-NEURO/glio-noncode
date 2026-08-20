"""GLIO-NONCODE research workbench.

The package exposes a small, deterministic vertical slice for turning a case
manifest into inspectable regulatory hypotheses. It is intentionally local
first and research-use only.
"""

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
    "Dossier",
    "EvidenceClaim",
    "Hypothesis",
    "ReferenceContext",
    "VariantIdentity",
]

__version__ = "0.1.0"
