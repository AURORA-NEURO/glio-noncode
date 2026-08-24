# D05 Atlas Architecture Runbook

## Build sequence

Create a local artifact directory and materialize the canonical public fixture:

```powershell
New-Item -ItemType Directory -Force .artifacts\d05 | Out-Null
python -m glio_noncode atlas-architecture-fixture --output .artifacts\d05\fixture.json
```

Run each closure surface:

```powershell
python -m glio_noncode atlas-architecture-data-audit --input .artifacts\d05\fixture.json --output .artifacts\d05\audit.json
python -m glio_noncode atlas-architecture-plan --input .artifacts\d05\fixture.json --output .artifacts\d05\plan.json
python -m glio_noncode evaluate-atlas-architecture --input .artifacts\d05\fixture.json --output .artifacts\d05\evaluation.json
python -m glio_noncode atlas-architecture-validation --input .artifacts\d05\fixture.json --output .artifacts\d05\validation.json
python -m glio_noncode atlas-architecture-compliance --input .artifacts\d05\fixture.json --output .artifacts\d05\compliance.json
python -m glio_noncode atlas-architecture-runtime --input .artifacts\d05\fixture.json --output .artifacts\d05\runtime.json
python -m glio_noncode atlas-architecture-quality --input .artifacts\d05\fixture.json --output .artifacts\d05\quality.json
python -m glio_noncode atlas-architecture-depth --input .artifacts\d05\fixture.json --output .artifacts\d05\depth.json
```

Package the release review surfaces:

```powershell
python -m glio_noncode atlas-architecture-report --input .artifacts\d05\fixture.json --format markdown --output .artifacts\d05\report.md
python -m glio_noncode atlas-architecture-bundle --input .artifacts\d05\fixture.json --output .artifacts\d05\bundle
python -m glio_noncode atlas-architecture-receipts-csv --input .artifacts\d05\fixture.json --output .artifacts\d05\receipts.csv
python -m glio_noncode atlas-architecture-review-csv --input .artifacts\d05\fixture.json --output .artifacts\d05\reviews.csv
```

## Expected values

```text
audit checks: 16
evaluation checks: 458
validation cells: 80
review controls: 48
ledger events: 64
runtime stages: 24
quality checks: 12
release artifacts: 6
depth completion: 100.0
runtime state: published
```

The bundle must contain `fixture.json`, `runtime.json`, `release.json`, and `report.json`.

## Control review

Inspect the held boundary by scenario:

```powershell
python -m glio_noncode atlas-architecture-query --state review --input .artifacts\d05\fixture.json
python -m glio_noncode atlas-architecture-scenarios --input .artifacts\d05\fixture.json
python -m glio_noncode atlas-architecture-review --input .artifacts\d05\fixture.json
```

The expected distribution is sixteen foreign-context cases, sixteen malformed-input cases, and sixteen identity-conflict cases. All 48 remain in review. Each foreign case must retain `context_mismatch`, and each case must retain a delegated context key.

## Triage

1. Audit failures: inspect source count, public markers, context, family coverage, joins, scenario balance, and declaration addresses.
2. Plan failures: inspect ordinal order, dependency IDs, and operation source joins.
3. Evaluation failures: inspect the named case, the expected issue tuple, the count map, and the delegated context.
4. Compliance failures: inspect `forbidden_key_paths`, source markers, context keys, control state, and declaration addresses.
5. Validation failures: locate the plane and operation cell; all four case receipts should pass.
6. Replay failures: compare first and second evaluation addresses and projections.
7. Quality failures: inspect all twelve checks; publication stays held until all pass.
8. Depth failures: compare source, operation, case, family, and evaluation-check counts with the target matrix.

## Determinism

Run the fixture and evaluation projections twice with the same input. Fixture, receipt, check, ledger, stage, and report addresses must remain stable. A different run identifier changes runtime-stage identity by design; it must not change fixture or evaluation identity.

## Handoff

Attach the bundle, report, depth report, compliance report, and commit identifier to the build record. Record fixture and runtime addresses, depth percentage, release state, and the number of held controls. Do not hand off a bundle with a failed check, blocked stage, missing public marker, empty delegated context, or promoted control.
