# D06 Runtime Runbook

## Standard sequence

```powershell
python -m glio_noncode sequence-architecture-fixture --output .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-data-audit --input .artifacts/sequence-fixture.json --output .artifacts/data.json
python -m glio_noncode sequence-architecture-plan --input .artifacts/sequence-fixture.json --output .artifacts/plan.json
python -m glio_noncode evaluate-sequence-architecture --input .artifacts/sequence-fixture.json --output .artifacts/evaluation.json
python -m glio_noncode sequence-architecture-validation --input .artifacts/sequence-fixture.json --output .artifacts/validation.json
python -m glio_noncode sequence-architecture-runtime --input .artifacts/sequence-fixture.json --output .artifacts/runtime.json
python -m glio_noncode sequence-architecture-quality --input .artifacts/sequence-fixture.json --output .artifacts/quality.json
python -m glio_noncode sequence-architecture-dictionary --input .artifacts/sequence-fixture.json --output .artifacts/dictionary.json
python -m glio_noncode sequence-architecture-scenarios --input .artifacts/sequence-fixture.json --output .artifacts/scenarios.json
python -m glio_noncode sequence-architecture-report --input .artifacts/sequence-fixture.json --format markdown --output .artifacts/report.md
python -m glio_noncode sequence-architecture-bundle --input .artifacts/sequence-fixture.json --output .artifacts/sequence-bundle
python -m glio_noncode sequence-architecture-compliance --input .artifacts/sequence-fixture.json --output .artifacts/compliance.json
python -m glio_noncode sequence-architecture-sources --input .artifacts/sequence-fixture.json --output .artifacts/sources.json
```

## Triage

1. Audit failure: inspect source joins, URI, version, public scope, context, and content addresses.
2. Plan failure: inspect D06 operation order and dependency references.
3. Evaluation failure: inspect the named receipt, then the family summary and expected issue codes.
4. Validation failure: locate the plane/operation cell and confirm all four receipts pass.
5. Replay failure: compare receipt projections and first/second evaluation addresses.
6. Quality failure: inspect the eight quality checks; publication remains held until all pass.

## Control review

```powershell
python -m glio_noncode sequence-architecture-review --input .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-query --state review --input .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-invariants --input .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-failures --input .artifacts/sequence-fixture.json
```

Foreign sequence context, malformed payload, and identity conflict are expected held controls. They must not be promoted or removed from the receipt set. If a control is absent, the count and scenario-balance checks fail.

## Release checklist

- [ ] 17 public source receipts are joined and addressed.
- [ ] 16 operations have four cases each.
- [ ] 16 positives and 48 controls are present.
- [ ] 325 evaluation checks pass.
- [ ] 80 validation cells pass.
- [ ] all controls remain in review.
- [ ] 64 ledger events are hash-linked.
- [ ] six artifacts are addressed.
- [ ] replay, schema, access, and invariant checks pass.
- [ ] final release state is published.
