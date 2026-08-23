# Lifecycle Beta Frontier Operations

## Scope

This runbook covers Domain 14 capabilities C05 through C12. It is a
deterministic public aggregate rehearsal. It does not read patient files, does
not fetch live evidence, and does not produce a clinical or treatment result.

The fixture has eight operations, nine HTTPS source receipts, 32 records, one
positive record per operation, and three controls per operation. Every row
uses the exact context:

GRCh38|glioma|adult|stem_like|core|untreated

## Quick start

Run the pipeline:

~~~powershell
python -m glio_noncode lifecycle-beta-frontier-pipeline --output lifecycle-beta-runtime.json
~~~

The accepted result has 25 stages. The JSON projection includes:

- 32 execution records and 166 checks;
- 8 operation metrics and 24 control records;
- 40 five-position threshold probes;
- 32 validation cells across six evidence planes;
- deterministic replay and release addresses;
- a 32-row review queue and explicit excluded uses.

## Operation sequence

1. Data audit checks source bindings, record counts, roles, context, and
   content addresses.
2. Contracts and schema establish input/output vocabulary for each operation.
3. Fixture evaluation executes each positive and control payload.
4. Metrics count states and issue codes without collapsing controls.
5. Policy, lineage, and reconciliation expose the review boundary.
6. Quality checks block release when a receipt, schema, lineage, or expected
   state is missing.
7. Scenario, threshold, and validation matrices exercise edge cases.
8. Replay checks content-address stability.
9. Release, artifact, handoff, queue, depth, and observability surfaces close
   the package.

## Control interpretation

supported, ready_for_review, and adjudicated are descriptive research states.
approved is only an explicit research-release record. partial,
contradictory, out_of_domain, abstained, review_required, split_decision, and
rejected remain visible and are not upgraded by averaging or by the existence
of a positive row.

The C05 controls include directional tier conflict, context mismatch, and
unclassified evidence. C06 controls include missing parents, foreign lineage,
and empty graphs. C07 controls include foreign dimensions, empty ledgers, and
out-of-range values. C08 controls include foreign claims, empty queues, and
required-role review.

The C09 controls include split verdicts, missing decisions, and foreign cases.
C10 controls include duplicate IDs, foreign comments, and empty logs. C11
controls include blocking gates, explicit rejection, and gate context
mismatch. C12 controls include stable snapshots, context change, and empty
snapshots.

## Review and release

Use the validation matrix to inspect every row across the data, contract,
execution, control, lineage, and policy planes. Use the handoff manifest to
transfer the fixture and its exact source set. Use the replay report to detect
content-address drift before review.

The release manifest is research-use-only. It is publishable only when the
quality gate, replay, depth audit, artifact inventory, and handoff all pass.
The excluded-use list remains part of the release receipt:

- patient-level inference;
- clinical diagnosis;
- treatment selection;
- causal authorization;
- automatic publication.

## Export commands

~~~powershell
python -m glio_noncode lifecycle-beta-frontier-data-audit --output lifecycle-beta-data.json
python -m glio_noncode lifecycle-beta-frontier-evaluate --output lifecycle-beta-evaluation.json
python -m glio_noncode lifecycle-beta-frontier-thresholds --output lifecycle-beta-thresholds.json
python -m glio_noncode lifecycle-beta-frontier-validation-matrix --output lifecycle-beta-matrix.json
python -m glio_noncode lifecycle-beta-frontier-handoff --output lifecycle-beta-handoff.json
~~~

The Python API exposes the same surfaces through
run_lifecycle_beta_frontier_runtime, measure_lifecycle_beta_frontier,
build_lifecycle_beta_frontier_lineage, reconcile_lifecycle_beta_frontier,
and build_lifecycle_beta_frontier_review_queue.

## Failure handling

If a stage fails, retain all earlier stage addresses and restart from the
failed stage. Do not rewrite a fixture row to make a control pass. Re-run the
data audit, evaluation, reconciliation, and replay after any fixture or schema
change. A changed address requires a new review record and a new release
manifest.
