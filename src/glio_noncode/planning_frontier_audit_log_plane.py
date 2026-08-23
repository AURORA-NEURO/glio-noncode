"""Named audit-log assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_audit_log_plane(fixture, evaluation):
    return build_named_planning_plane("audit-log", "operations", fixture, evaluation, lambda f, e: all(c.content_address.startswith("sha256:") for c in e.checks), "checks have addresses")
__all__ = ["build_planning_audit_log_plane"]
