# D03 deep execution runbook

This runbook covers a complete local verification of the public aggregate
specimen architecture, including all four typed families and all release
projections.

## Input and boundary

Use `examples/specimen-architecture-public-aggregate.json` as the canonical
fixture unless a reviewed replay fixture is supplied. The fixture must retain
the exact GRCh38 diffuse glioma adult malignant-oligodendrocyte-like tumor-core
pre-treatment context, HTTPS source receipts, public aggregate scope, bounded
payloads, and content addresses.

The loader applies closed defaults when a legacy fixture row lacks an explicit
public marker or delegated context. Newly exported fixture JSON always carries
both fields so the boundary remains visible in persisted data.

## Full run

```powershell
$out = ".\\out\\d03"
python -m glio_noncode specimen-architecture-fixture --output "$out\\fixture.json"
python -m glio_noncode specimen-architecture-data-audit --input "$out\\fixture.json" --output "$out\\audit.json"
python -m glio_noncode specimen-architecture-plan --input "$out\\fixture.json" --output "$out\\plan.json"
python -m glio_noncode evaluate-specimen-architecture --input "$out\\fixture.json" --output "$out\\evaluation.json"
python -m glio_noncode specimen-architecture-validation --input "$out\\fixture.json" --output "$out\\validation.json"
python -m glio_noncode specimen-architecture-runtime --input "$out\\fixture.json" --output "$out\\runtime.json"
python -m glio_noncode specimen-architecture-quality --input "$out\\fixture.json" --output "$out\\quality.json"
python -m glio_noncode specimen-architecture-depth --input "$out\\fixture.json" --output "$out\\depth.json"
python -m glio_noncode specimen-architecture-compliance --input "$out\\fixture.json" --output "$out\\compliance.json"
python -m glio_noncode specimen-architecture-report --input "$out\\fixture.json" --output "$out\\report.json"
python -m glio_noncode specimen-architecture-receipts-csv --input "$out\\fixture.json" --output "$out\\receipts.csv"
python -m glio_noncode specimen-architecture-review-csv --input "$out\\fixture.json" --output "$out\\review.csv"
python -m glio_noncode specimen-architecture-bundle --input "$out\\fixture.json" --output "$out\\bundle"
```

## Expected closure

The data audit returns 15 checks. Evaluation returns 64 receipts and 458
checks. The validation matrix returns 112 cells. The review queue and ledger
contain 48 and 64 entries. The runtime contains 24 ordered stages, six
artifacts, twelve quality checks, eight compliance checks, and an accepted
depth report.

The runtime must have:

```text
state = published
accepted = true
stage_count = 24
depth.check_count = 458
depth.accepted = true
quality.passed = true
compliance.accepted = true
release.published = true
```

## Stage inspection

The first 18 stages close intake, family preparation, evaluation, review,
lineage, metrics, validation, schema, artifacts, access, and replay. The final
six stages are:

19. `depth-accounted` — structural target counts and completion are recorded.
20. `compliance-closed` — source, context, control, and forbidden-field checks pass.
21. `release-gated` — the release manifest is publishable.
22. `quality-gated` — all twelve quality checks pass.
23. `observability-closed` — metrics and validation projections are addressed.
24. `runtime-finalized` — run identity and stage count are addressed.

Every stage records input address, output address, state, ordinal, and stage
address. A partial run can therefore be isolated without opening raw payloads.

## Failure isolation

If the runtime is blocked, inspect the first failed contract in this order:

1. Data audit for source scope, context, markers, and joins.
2. Evaluation for the first case receipt and its seven checks.
3. Plan and policy for operation order or unexpected dispatch.
4. Validation and schema for missing plane cells or fields.
5. Review and lineage for control routing or broken address links.
6. Compliance for forbidden paths or context separation.
7. Depth for cardinality, family, state, check, or stage shortfalls.
8. Quality and release for the aggregate decision.

Do not edit an expected address by hand. Rebuild the affected declaration from
its source rows, regenerate the canonical fixture, and rerun the full closure.

## Review semantics

All 48 controls are expected review work. A published runtime means each
control matched its declared outcome and entered the review queue; it does not
convert a control into a positive result. The control issue set is
`context_mismatch`, `malformed_input`, and `identity_conflict`.

Report and CSV projections retain case ID, operation ID, outcome, issue codes,
priority, next action, and content addresses. They are inspection projections,
not mutation surfaces.

## Change procedure

For a D03 contract change:

1. Update the typed contract and canonical fixture projection.
2. Run focused D03 unit tests, including reporting tests.
3. Run the CLI matrix and bundle command.
4. Scan new files for prohibited attribution and identity metadata.
5. Review `git diff --check` and staged line counts.
6. Commit the complete build to `main` after all gates pass.
