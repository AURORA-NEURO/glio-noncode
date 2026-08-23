"""Operational runbook for the D01 public aggregate intake boundary."""

from __future__ import annotations

from .intake_architecture_contracts import IntakeArchitectureRuntime, addressed


def build_intake_architecture_runbook(runtime: IntakeArchitectureRuntime) -> dict[str, object]:
    body = {
        "runbook_id": "intake-runbook-d01",
        "preflight": ("verify HTTPS receipts", "verify public aggregate scope", "verify exact context key"),
        "execution": ("load fixture", "parse source formats", "normalize identities", "route controls", "materialize offline artifacts"),
        "held_control_action": "do not promote held controls; preserve input address and issue code for review",
        "rollback": runtime.release.rollback_version,
        "current_release": runtime.release.version,
        "privacy_boundary": "public aggregate identifiers only",
        "accepted": runtime.state.value == "accepted" and not runtime.release.blockers,
    }
    return body | {"content_address": addressed(body, "intake-runbook")}


__all__ = ["build_intake_architecture_runbook"]
