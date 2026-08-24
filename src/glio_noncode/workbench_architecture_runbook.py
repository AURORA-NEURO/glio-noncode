"""Operational runbook for D15 workbench architecture."""

from __future__ import annotations

from .workbench_architecture_contracts import WorkbenchArchitectureFixture
from .workbench_architecture_public_data import default_workbench_architecture_fixture


def workbench_architecture_runbook(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> tuple[dict[str, object], ...]:
    selected = fixture or default_workbench_architecture_fixture()
    return (
        ("load", "load the checked-in public aggregate workbench fixture", selected.fixture_id),
        (
            "audit",
            "audit four source registries, joins, contexts, and scenario balance",
            selected.fixture_id,
        ),
        ("plan", "compile sixteen dependency-safe workspace operations", selected.fixture_id),
        ("execute", "evaluate positive and control delegate records", selected.fixture_id),
        ("route", "route held and blocking states to review", selected.fixture_id),
        (
            "release",
            "publish only after replay, quality, and boundary closure",
            selected.fixture_id,
        ),
    )


def workbench_architecture_runbook_summary(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> dict[str, object]:
    selected = fixture or default_workbench_architecture_fixture()
    steps = workbench_architecture_runbook(selected)
    return {
        "fixture_id": selected.fixture_id,
        "step_count": len(steps),
        "step_names": [item[0] for item in steps],
    }


__all__ = ["workbench_architecture_runbook", "workbench_architecture_runbook_summary"]
