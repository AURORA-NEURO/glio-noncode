"""Named contract migration assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_contract_migrations_plane(fixture, evaluation):
    return build_named_planning_plane("contract-migrations", "engineering", fixture, evaluation, lambda f, e: bool(f.fixture_version), "contract version is explicit")
__all__ = ["build_planning_contract_migrations_plane"]
