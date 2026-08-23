"""Named compliance assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_compliance_plane(fixture, evaluation):
    return build_named_planning_plane("compliance", "boundary", fixture, evaluation, lambda f, e: all("patient_id" not in str(x.output).lower() for x in e.executions), "private markers are excluded")
__all__ = ["build_planning_compliance_plane"]
