# D05 Runtime Runbook

## Standard build

Run the following sequence from the repository root:

```powershell
python -m glio_noncode atlas-architecture-fixture --output .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-data-audit --input .artifacts/atlas-fixture.json --output .artifacts/audit.json
python -m glio_noncode atlas-architecture-plan --input .artifacts/atlas-fixture.json --output .artifacts/plan.json
python -m glio_noncode evaluate-atlas-architecture --input .artifacts/atlas-fixture.json --output .artifacts/evaluation.json
python -m glio_noncode atlas-architecture-validation --input .artifacts/atlas-fixture.json --output .artifacts/validation.json
python -m glio_noncode atlas-architecture-runtime --input .artifacts/atlas-fixture.json --output .artifacts/runtime.json
python -m glio_noncode atlas-architecture-quality --input .artifacts/atlas-fixture.json --output .artifacts/quality.json
python -m glio_noncode atlas-architecture-bundle --input .artifacts/atlas-fixture.json --output .artifacts/atlas-bundle
python -m glio_noncode atlas-architecture-dictionary --input .artifacts/atlas-fixture.json --output .artifacts/dictionary.json
python -m glio_noncode atlas-architecture-scenarios --input .artifacts/atlas-fixture.json --output .artifacts/scenarios.json
python -m glio_noncode atlas-architecture-sources --input .artifacts/atlas-fixture.json --output .artifacts/sources.json
python -m glio_noncode atlas-architecture-report --input .artifacts/atlas-fixture.json --format markdown --output .artifacts/report.md
python -m glio_noncode atlas-architecture-receipts-csv --input .artifacts/atlas-fixture.json --output .artifacts/receipts.csv
```

The normal result is exit code zero, `accepted: true` for data, evaluation, validation, runtime, and depth surfaces, and `passed: true` for quality.

## Triage order

1. If data audit fails, inspect source receipts, context keys, source joins, and content addresses.
2. If plan compilation fails, inspect operation ordering and declared dependencies.
3. If evaluation fails, inspect the named case receipt first, then its scenario policy.
4. If validation fails, locate the plane/operation cell that contains the failing case.
5. If replay fails, compare the first and second fixture or receipt addresses.
6. If quality fails, inspect the quality checks in order; release remains held until every check passes.

Use focused commands to inspect the boundary:

```powershell
python -m glio_noncode atlas-architecture-review --input .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-query --state review --input .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-failures --input .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-invariants --input .artifacts/atlas-fixture.json
```

## Rollback and retention

The runtime is deterministic and does not mutate source records. Discard only the local `.artifacts/atlas-bundle` directory when a run is superseded, then rerun the fixture command. Retain the fixture, evaluation, validation, runtime, and release JSON together when a release receipt is published so the content addresses remain auditable.

Never promote a bundle with a held review queue, a failed validation cell, a replay mismatch, or a release state other than `published`.

## Release checklist

- [ ] 20 public source receipts are present and addressed.
- [ ] 16 operations have four cases each.
- [ ] 16 positive cases and 48 controls are present.
- [ ] all 325 evaluation checks pass.
- [ ] all 80 validation cells pass.
- [ ] all 48 controls remain in review.
- [ ] the 64-event ledger is hash-linked.
- [ ] six artifacts are materialized.
- [ ] access checks, schema checks, invariants, and replay checks pass.
- [ ] the final quality state is published.
