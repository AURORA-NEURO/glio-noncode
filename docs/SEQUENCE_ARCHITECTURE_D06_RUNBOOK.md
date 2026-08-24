# D06 Sequence Architecture Runbook

## Purpose

This runbook describes a repeatable build and review loop for the public aggregate sequence surface. It is intended for local verification and continuous action execution. All commands operate on an explicit fixture path when a persisted artifact is being reviewed.

## Build loop

Create a clean artifact directory and materialize the public fixture:

```powershell
New-Item -ItemType Directory -Force .artifacts\d06 | Out-Null
python -m glio_noncode sequence-architecture-fixture --output .artifacts\d06\fixture.json
```

Run the structural and behavioral projections:

```powershell
python -m glio_noncode sequence-architecture-data-audit --input .artifacts\d06\fixture.json --output .artifacts\d06\audit.json
python -m glio_noncode sequence-architecture-plan --input .artifacts\d06\fixture.json --output .artifacts\d06\plan.json
python -m glio_noncode evaluate-sequence-architecture --input .artifacts\d06\fixture.json --output .artifacts\d06\evaluation.json
python -m glio_noncode sequence-architecture-validation --input .artifacts\d06\fixture.json --output .artifacts\d06\validation.json
python -m glio_noncode sequence-architecture-compliance --input .artifacts\d06\fixture.json --output .artifacts\d06\compliance.json
```

Close and package the runtime:

```powershell
python -m glio_noncode sequence-architecture-runtime --input .artifacts\d06\fixture.json --output .artifacts\d06\runtime.json
python -m glio_noncode sequence-architecture-quality --input .artifacts\d06\fixture.json --output .artifacts\d06\quality.json
python -m glio_noncode sequence-architecture-depth --input .artifacts\d06\fixture.json --output .artifacts\d06\depth.json
python -m glio_noncode sequence-architecture-report --input .artifacts\d06\fixture.json --format markdown --output .artifacts\d06\report.md
python -m glio_noncode sequence-architecture-bundle --input .artifacts\d06\fixture.json --output .artifacts\d06\bundle
```

## Expected closure

The following values must be present before a D06 build is accepted:

```text
audit checks: 16
evaluation checks: 458
validation cells: 80
controls: 48
ledger events: 64
runtime stages: 24
quality checks: 12
release artifacts: 6
depth completion: 100.0
runtime state: published
```

The bundle must contain:

```text
fixture.json
runtime.json
release.json
report.json
```

`runtime.json` is the complete typed projection. `release.json` is a compact handoff containing artifacts, release state, quality checks, depth accounting, and compliance. `report.json` provides summary measures and source, operation, control, and artifact sections.

## Review controls

Review the held controls by scenario:

```powershell
python -m glio_noncode sequence-architecture-query --state review --input .artifacts\d06\fixture.json
python -m glio_noncode sequence-architecture-scenarios --input .artifacts\d06\fixture.json
python -m glio_noncode sequence-architecture-review --input .artifacts\d06\fixture.json
```

The expected control distribution is sixteen foreign-context cases, sixteen malformed-input cases, and sixteen identity-conflict cases. Controls remain in review and must retain their issue code. A control becoming accepted is a contract failure even if the total receipt count remains unchanged.

## Failure triage

1. If the fixture audit fails, inspect version, boundary, context, public source markers, family coverage, joins, scenario balance, and content addresses.
2. If the plan fails, inspect operation ordinals, dependency IDs, and source joins.
3. If evaluation fails, inspect the named case receipt, its expected issue tuple, its observed counts, and its delegated context.
4. If compliance fails, inspect `forbidden_key_paths`, then inspect public markers, context keys, control states, and operation policies.
5. If validation fails, locate the plane and operation cell; every cell should reference four passing receipts.
6. If replay fails, compare first and second evaluation addresses and the receipt/check counts.
7. If quality fails, inspect all twelve quality checks. Release state must remain held until each check passes.
8. If depth fails, compare source, operation, case, family, and evaluation-check counts with the target matrix.

## Determinism checks

Run the fixture and runtime commands twice with the same input and compare canonical JSON output. The evaluation content address, receipt addresses, check addresses, ledger addresses, stage addresses, and report address must remain stable. A run identifier changes runtime-stage identity intentionally; the fixture and evaluation projections must not change.

## Public-scope review

Before handoff, confirm that source URIs are public, source scope is `public_aggregate`, every source carries the boolean public marker, and all case content is aggregate. The compliance report must be accepted and its forbidden path list must be empty.

## Release handoff

Attach the bundle directory, the Markdown report, and the depth report to the build record. Record the commit identifier, fixture content address, runtime content address, depth percentage, and release state. Do not hand off a bundle when any check is false, when any stage is blocked, or when a control has lost its expected hold state.
