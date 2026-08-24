"""Stable D16 platform execution architecture export surface."""

# Re-export the complete typed, evaluated, and release-gated surface.
# ruff: noqa: F401, F403, E501

from .platform_execution_architecture_artifacts import *  # noqa: F401,F403
from .platform_execution_architecture_compliance import *  # noqa: F401,F403
from .platform_execution_architecture_contracts import *  # noqa: F401,F403
from .platform_execution_architecture_depth import *  # noqa: F401,F403
from .platform_execution_architecture_ledger import *  # noqa: F401,F403
from .platform_execution_architecture_matrix import *  # noqa: F401,F403
from .platform_execution_architecture_metrics import *  # noqa: F401,F403
from .platform_execution_architecture_operations import *  # noqa: F401,F403
from .platform_execution_architecture_plan import *  # noqa: F401,F403
from .platform_execution_architecture_public_data import *  # noqa: F401,F403
from .platform_execution_architecture_quality import *  # noqa: F401,F403
from .platform_execution_architecture_query import *  # noqa: F401,F403
from .platform_execution_architecture_release import *  # noqa: F401,F403
from .platform_execution_architecture_replay import *  # noqa: F401,F403
from .platform_execution_architecture_reporting import *  # noqa: F401,F403
from .platform_execution_architecture_review import *  # noqa: F401,F403
from .platform_execution_architecture_runtime import *  # noqa: F401,F403
from .platform_execution_architecture_schema import *  # noqa: F401,F403

__all__ = [
    name
    for name in globals()
    if name.startswith("PlatformExecution")
    or name.startswith("PLATFORM_EXECUTION")
    or name.startswith(
        (
            "assess_platform_execution",
            "audit_platform_execution",
            "build_platform_execution",
            "default_platform_execution",
            "evaluate_platform_execution",
            "execute_platform_execution",
            "load_platform_execution",
            "normalize_platform_execution",
            "platform_execution",
            "query_platform_execution",
            "replay_platform_execution",
            "run_platform_execution",
            "validate_platform_execution",
        )
    )
    or name == "addressed"
]
