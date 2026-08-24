"""Stable D13 planning architecture export surface."""

# Re-export the complete typed, evaluated, and release-gated surface.
# ruff: noqa: F401, F403, E501

from .planning_architecture_artifacts import *  # noqa: F401,F403
from .planning_architecture_audit import *  # noqa: F401,F403
from .planning_architecture_compliance import *  # noqa: F401,F403
from .planning_architecture_contract_matrix import *  # noqa: F401,F403
from .planning_architecture_contracts import *  # noqa: F401,F403
from .planning_architecture_controls import *  # noqa: F401,F403
from .planning_architecture_data_dictionary import *  # noqa: F401,F403
from .planning_architecture_depth import *  # noqa: F401,F403
from .planning_architecture_ledger import *  # noqa: F401,F403
from .planning_architecture_lineage import *  # noqa: F401,F403
from .planning_architecture_metrics import *  # noqa: F401,F403
from .planning_architecture_operations import *  # noqa: F401,F403
from .planning_architecture_plan import *  # noqa: F401,F403
from .planning_architecture_public_data import *  # noqa: F401,F403
from .planning_architecture_quality import *  # noqa: F401,F403
from .planning_architecture_query import *  # noqa: F401,F403
from .planning_architecture_release import *  # noqa: F401,F403
from .planning_architecture_replay import *  # noqa: F401,F403
from .planning_architecture_reporting import *  # noqa: F401,F403
from .planning_architecture_review import *  # noqa: F401,F403
from .planning_architecture_runbook import *  # noqa: F401,F403
from .planning_architecture_runtime import *  # noqa: F401,F403
from .planning_architecture_schema import *  # noqa: F401,F403
from .planning_architecture_views import *  # noqa: F401,F403

__all__ = [
    name
    for name in globals()
    if name.startswith("PlanningArchitecture")
    or name.startswith("PLANNING_ARCHITECTURE")
    or name.startswith("assess_planning_architecture")
    or name.startswith("audit_planning_architecture")
    or name.startswith("build_planning_architecture")
    or name.startswith("deep_audit_planning_architecture")
    or name.startswith("default_planning_architecture")
    or name.startswith("evaluate_planning_architecture")
    or name.startswith("execute_planning_architecture")
    or name.startswith("load_planning_architecture")
    or name.startswith("normalize_planning_architecture")
    or name.startswith("planning_architecture")
    or name.startswith("query_planning_architecture")
    or name.startswith("replay_planning_architecture")
    or name.startswith("run_planning_architecture")
    or name.startswith("validate_planning_architecture")
    or name == "addressed"
]
