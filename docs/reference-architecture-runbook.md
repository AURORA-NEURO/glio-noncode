# D04 reference architecture runbook

This runbook describes the operational path from the checked-in public fixture to a publishable aggregate reference release.

## Preconditions

- The repository is on a reviewed branch with a clean fixture diff.
- Python dependencies used by the existing project are installed.
- The fixture path is readable and is the intended D04 public aggregate fixture.
- No upstream data copy is required; source receipts and public URIs are sufficient for this boundary.
- The expected context is GRCh38 diffuse glioma adult bulk-tumor reference baseline.

## Standard run

Run the following commands from the repository root:

```powershell
python -m glio_noncode reference-architecture-data-audit --input examples/reference-architecture-public-aggregate.json --output .\out\data-audit.json
python -m glio_noncode reference-architecture-plan --input examples/reference-architecture-public-aggregate.json --output .\out\plan.json
python -m glio_noncode evaluate-reference-architecture --input examples/reference-architecture-public-aggregate.json --output .\out\evaluation.json
python -m glio_noncode reference-architecture-validation --input examples/reference-architecture-public-aggregate.json --output .\out\validation.json
python -m glio_noncode reference-architecture-runtime --input examples/reference-architecture-public-aggregate.json --output .\out\runtime.json
python -m glio_noncode reference-architecture-quality --input examples/reference-architecture-public-aggregate.json --output .\out\quality.json
python -m glio_noncode reference-architecture-compliance --input examples/reference-architecture-public-aggregate.json --output .\out\compliance.json
python -m glio_noncode reference-architecture-report --input examples/reference-architecture-public-aggregate.json --output .\out\report.json
python -m glio_noncode reference-architecture-receipts-csv --input examples/reference-architecture-public-aggregate.json --output .\out\receipts.csv
python -m glio_noncode reference-architecture-review-csv --input examples/reference-architecture-public-aggregate.json --output .\out\review.csv
python -m glio_noncode replay-reference-architecture --input examples/reference-architecture-public-aggregate.json --output .\out\replay.json
python -m glio_noncode reference-architecture-bundle --input examples/reference-architecture-public-aggregate.json --output .\out\bundle
```

The output directory can be temporary. The bundle contains runtime, release, and fixture projections; its files are local inspection products, while the typed artifact inventory remains the release authority.

## Acceptance checklist

Confirm these values before publication:

| Check | Required |
| --- | ---: |
| source receipts | 20 |
| operations | 16 |
| cases | 64 |
| positive cases | 16 |
| held controls | 48 |
| evaluation checks | 458 |
| validation cells | 80 |
| lineage events | 64 |
| runtime stages | 24 |
| quality checks | 12 |
| result states | 6 |
| compliance checks | 8 |
| depth completion | 100.0% |
| release artifacts | 6 |
| release state | `published` |

Confirm that all controls appear in the review queue and that the policy issue set is exactly `context_mismatch`, `malformed_input`, and `identity_conflict`. Confirm that positive informative codes remain on their receipts and that their family result state is successful.

## Triage order

If the run is blocked, inspect in this order:

1. Data audit: version, boundary, source scope, context, and sensitive-field checks.
2. Plan: missing operation, dependency order, or source join.
3. Evaluation: the first failed case receipt and its seven checks.
4. Policy: a control dispatched unexpectedly or a positive held unexpectedly.
5. Lineage: missing case event, broken previous address, or mismatched output address.
6. Replay: changed receipt projection or content address.
7. Schema and access: missing field, media type, retention, or source address.
8. Compliance: public markers, delegated contexts, and forbidden-field paths.
9. Quality and release: aggregate summary after upstream correction.

Do not repair a failing address by editing only the expected value. Reconstruct the affected record from its source receipts, rerun the canonical fixture, and inspect the resulting diff.

## Control handling

Controls are expected review work. `foreign_context` proves that the exact context boundary is active. `malformed_input` proves that shape errors do not reach family adapters. `identity_conflict` proves that contradictory public reference identity is not silently resolved.

For a control finding, retain:

- case ID and operation ID;
- scenario and reason code;
- input and output addresses;
- review priority and next action;
- the release run ID that held the case.

The runtime may publish a release with controls present because publication means all declared controls were handled according to policy. It must not publish if a control receipt disagrees with its expected held outcome.

## Rollback

When a release check fails:

1. Mark the release blocked.
2. Retain all artifact addresses and the failed check IDs.
3. Restore the previous public manifest outside the current output directory.
4. Open or update review items for the failing cases and checks.

The `rollback_key` is derived from the fixture address. It is an audit join, not a destructive operation. No source file or fixture is deleted by the runtime.

## Escalation rules

Stop the run and request review when:

- scope or direct identity checks fail;
- replay or lineage addresses diverge;
- checksum, schema, license, or context evidence is missing.

The failure report classifies positive contract mismatches separately from control-policy mismatches. Positive mismatches block publication. Control-policy mismatches also block publication because they mean the boundary contract is not being enforced.

## CI expectations

CI runs the data audit, plan, evaluation, runtime, quality, depth, validation, replay, review, metrics, access, invariants, schema, failure classification, bundle, and focused D04 tests. A local run should use the same fixture path and commands so output differences can be compared directly.

## Safe change procedure

For a fixture or adapter change:

1. Make the smallest source or contract edit.
2. Run the focused D04 tests.
3. Run the full D04 CLI sequence.
4. Run the metadata boundary scan.
5. Inspect `git diff --check` and the staged diff.
6. Commit the complete build once the validation and release gates pass.

Keep generated output outside tracked paths unless a fixture or documentation update is intentional. Preserve public source receipts and content addresses in any committed fixture change.
