"""Stable D12 cohort architecture export surface."""

# Re-export the complete typed, evaluated, and release-gated surface.
# ruff: noqa: F401, F403, E501

from .cohort_architecture_artifacts import *  # noqa: F401,F403
from .cohort_architecture_audit import *  # noqa: F401,F403
from .cohort_architecture_compliance import *  # noqa: F401,F403
from .cohort_architecture_contract_matrix import *  # noqa: F401,F403
from .cohort_architecture_contracts import *  # noqa: F401,F403
from .cohort_architecture_controls import *  # noqa: F401,F403
from .cohort_architecture_data_dictionary import *  # noqa: F401,F403
from .cohort_architecture_depth import *  # noqa: F401,F403
from .cohort_architecture_ledger import *  # noqa: F401,F403
from .cohort_architecture_lineage import *  # noqa: F401,F403
from .cohort_architecture_metrics import *  # noqa: F401,F403
from .cohort_architecture_operations import *  # noqa: F401,F403
from .cohort_architecture_plan import *  # noqa: F401,F403
from .cohort_architecture_public_data import *  # noqa: F401,F403
from .cohort_architecture_quality import *  # noqa: F401,F403
from .cohort_architecture_query import *  # noqa: F401,F403
from .cohort_architecture_release import *  # noqa: F401,F403
from .cohort_architecture_replay import *  # noqa: F401,F403
from .cohort_architecture_reporting import *  # noqa: F401,F403
from .cohort_architecture_review import *  # noqa: F401,F403
from .cohort_architecture_runbook import *  # noqa: F401,F403
from .cohort_architecture_runtime import *  # noqa: F401,F403
from .cohort_architecture_schema import *  # noqa: F401,F403
from .cohort_architecture_views import *  # noqa: F401,F403

__all__ = [
    name
    for name in globals()
    if name.startswith("CohortArchitecture")
    or name.startswith("COHORT_ARCHITECTURE")
    or name.startswith("assess_cohort_architecture")
    or name.startswith("audit_cohort_architecture")
    or name.startswith("build_cohort_architecture")
    or name.startswith("cohort_architecture")
    or name.startswith("deep_audit_cohort_architecture")
    or name.startswith("default_cohort_architecture")
    or name.startswith("evaluate_cohort_architecture")
    or name.startswith("execute_cohort_architecture")
    or name.startswith("load_cohort_architecture")
    or name.startswith("normalize_cohort_architecture")
    or name.startswith("query_cohort_architecture")
    or name.startswith("replay_cohort_architecture")
    or name.startswith("run_cohort_architecture")
    or name.startswith("validate_cohort_architecture")
    or name == "addressed"
]
