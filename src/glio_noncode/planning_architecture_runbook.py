"""Operational command runbook for the D13 public aggregate."""

# ruff: noqa: E501

PLANNING_ARCHITECTURE_RUNBOOK = """# D13 Planning Architecture Runbook

The D13 surface joins four public aggregate planning families:

1. validation design, C01-C04;
2. editing design, C05-C08;
3. planning, C09-C12; and
4. validation release, C13-C16.

The checked-in fixture contains twenty public source receipts, sixteen
operations, and sixty-four cases. Each operation has one positive row and
three controls. The evaluator preserves delegate states and issue codes,
including context mismatch, review, blocked, rejected, and abstained paths.

## Rehearsal

```powershell
python -m glio_noncode planning-architecture-fixture --output .runtime/planning-architecture-fixture.json
python -m glio_noncode planning-architecture-data-audit --input .runtime/planning-architecture-fixture.json --output .runtime/planning-architecture-audit.json
python -m glio_noncode planning-architecture-plan --input .runtime/planning-architecture-fixture.json --output .runtime/planning-architecture-plan.json
python -m glio_noncode evaluate-planning-architecture --input .runtime/planning-architecture-fixture.json --output .runtime/planning-architecture-evaluation.json
python -m glio_noncode planning-architecture-runtime --input .runtime/planning-architecture-fixture.json --output .runtime/planning-architecture-runtime.json
python -m glio_noncode planning-architecture-quality --input .runtime/planning-architecture-fixture.json --output .runtime/planning-architecture-quality.json
python -m glio_noncode planning-architecture-depth --input .runtime/planning-architecture-fixture.json --output .runtime/planning-architecture-depth.json
python -m glio_noncode replay-planning-architecture --input .runtime/planning-architecture-fixture.json --output .runtime/planning-architecture-replay.json
python -m glio_noncode planning-architecture-report --input .runtime/planning-architecture-fixture.json --output .runtime/planning-architecture-report.json
python -m glio_noncode planning-architecture-bundle --input .runtime/planning-architecture-fixture.json --output .runtime/planning-architecture-bundle
```

## Query

```powershell
python -m glio_noncode planning-architecture-query --input data/planning-architecture-public-aggregate.json --operation D13-C14 --output .runtime/d13-c14.json
python -m glio_noncode planning-architecture-query --input data/planning-architecture-public-aggregate.json --family planning_frontier --scenario control_c --output .runtime/d13-planning-control-c.json
```

Queries are projections. They do not infer missing evidence or convert a held
planning state into a biological conclusion. The public boundary excludes
participant rows, private credentials, unsupported clinical decisions, and
unaddressed external state.
"""


def planning_architecture_runbook_summary() -> dict[str, object]:
    return {
        "module": "D13",
        "operation_count": 16,
        "case_count": 64,
        "source_count": 20,
        "command_count": 14,
        "boundary": "public_aggregate_non_patient",
    }


__all__ = ["PLANNING_ARCHITECTURE_RUNBOOK", "planning_architecture_runbook_summary"]
