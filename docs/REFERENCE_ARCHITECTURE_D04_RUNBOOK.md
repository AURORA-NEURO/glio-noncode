# D04 deep execution runbook

This runbook is for a full local verification of the public aggregate reference architecture. It describes the artifact flow, expected closure values, and failure isolation points.

## Inputs and boundary

Use `examples/reference-architecture-public-aggregate.json` as the canonical fixture unless a reviewed replay fixture is explicitly supplied. The fixture must retain the exact GRCh38 diffuse glioma adult bulk-tumor reference context, HTTPS public source receipts, source scope `public_aggregate`, and bounded payloads.

The loader accepts legacy fixture rows that do not yet carry explicit public markers or delegated contexts by applying the closed defaults. Newly exported fixture JSON always carries both fields so the boundary is visible in persisted data.

## Full run

```powershell
$out = ".\\out\\d04"
python -m glio_noncode reference-architecture-fixture --output "$out\\fixture.json"
python -m glio_noncode reference-architecture-data-audit --input "$out\\fixture.json" --output "$out\\audit.json"
python -m glio_noncode reference-architecture-plan --input "$out\\fixture.json" --output "$out\\plan.json"
python -m glio_noncode evaluate-reference-architecture --input "$out\\fixture.json" --output "$out\\evaluation.json"
python -m glio_noncode reference-architecture-validation --input "$out\\fixture.json" --output "$out\\validation.json"
python -m glio_noncode reference-architecture-runtime --input "$out\\fixture.json" --output "$out\\runtime.json"
python -m glio_noncode reference-architecture-quality --input "$out\\fixture.json" --output "$out\\quality.json"
python -m glio_noncode reference-architecture-depth --input "$out\\fixture.json" --output "$out\\depth.json"
python -m glio_noncode reference-architecture-compliance --input "$out\\fixture.json" --output "$out\\compliance.json"
python -m glio_noncode reference-architecture-report --input "$out\\fixture.json" --output "$out\\report.json"
python -m glio_noncode reference-architecture-receipts-csv --input "$out\\fixture.json" --output "$out\\receipts.csv"
python -m glio_noncode reference-architecture-review-csv --input "$out\\fixture.json" --output "$out\\review.csv"
python -m glio_noncode reference-architecture-bundle --input "$out\\fixture.json" --output "$out\\bundle"
```

## Expected closure

The data audit returns 16 checks. Evaluation returns 64 receipts and 458 checks. The validation matrix returns 80 cells. The review queue and ledger contain 48 and 64 entries respectively. The runtime contains 24 ordered stages, six artifacts, a 12-check quality gate, an eight-check compliance report, and an accepted depth report.

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

The first 18 stages close intake, family preparation, evaluation, review, lineage, metrics, validation, schema, artifacts, access, and replay. The final six stages are:

19. `depth-accounted` — target counts and completion score are recorded.
20. `compliance-closed` — public marker, context, control, and forbidden-field checks pass.
21. `release-gated` — the release manifest is publishable.
22. `quality-gated` — all twelve quality checks pass.
23. `observability-closed` — the metrics and validation projection is addressed.
24. `runtime-finalized` — the run identity and stage count are addressed.

Every stage records its previous input address, output address, state, ordinal, and stage address. This makes a partial run easy to isolate without inspecting raw payloads.

## Failure isolation

If the run is blocked, inspect the first failed contract in this order:

1. Public data audit for source scope, context, markers, and joins.
2. Evaluation for the first case receipt and its seven checks.
3. Plan and policy for operation order or unexpected dispatch.
4. Validation and schema for missing plane cells or fields.
5. Review and lineage for held-control routing or broken address links.
6. Compliance for forbidden paths or context separation.
7. Depth for cardinality, family, state, or stage shortfalls.
8. Quality and release for the aggregate decision.

Do not edit an expected address by hand. Rebuild the affected declaration from its source rows, regenerate the canonical fixture, and rerun the full closure.

## Review semantics

All 48 controls are expected review work. A published runtime means each control matched its declared outcome and was routed into the review queue; it does not convert the control into a positive result. The three control issue codes are `context_mismatch`, `malformed_input`, and `identity_conflict`.

The report and CSV outputs preserve case ID, operation ID, scenario result, issue codes, priority, next action, and content addresses. They are intended for inspection and downstream comparison, not for mutating the fixture.

## Change procedure

For a D04 contract change:

1. Update the typed contract and canonical fixture projection.
2. Run the focused D04 unit tests.
3. Run the CLI matrix and bundle commands.
4. Scan new files for prohibited identity or attribution metadata.
5. Review `git diff --check` and staged line counts.
6. Commit the complete build to `main` after all gates pass.
