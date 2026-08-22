# Evidence Lifecycle Frontier Operations

## Operator scope

This runbook covers the Domain 14 C01–C04 public aggregate surface.

Use it for local review.

Use it for CI review.

Use it for release rehearsal.

Use it for replay comparison.

Use it for control inspection.

The runbook assumes a clean Python environment.

The runbook assumes the package is installed in editable mode.

The runbook assumes the repository root is current.

The runbook assumes no live source fetch is required.

The runbook uses deterministic aggregate inputs.

The runbook does not require patient data.

The runbook does not require private source files.

The runbook does not make a clinical decision.

## Quick start

Run the data audit first.

```powershell
python -m glio_noncode evidence-lifecycle-data-audit --output lifecycle-data.json
```

The command should return zero.

The output should contain `accepted: true`.

The output should contain twelve checks.

The output should contain five sources.

The output should contain sixteen records.

Run the evaluator next.

```powershell
python -m glio_noncode evidence-lifecycle-evaluate --output lifecycle-evaluation.json
```

The output should contain 120 checks.

The output should contain 120 passed checks.

The output should contain an empty failed-check list.

Run the runtime rehearsal.

```powershell
python -m glio_noncode evidence-lifecycle-runtime --output lifecycle-runtime.json
```

The runtime should contain ten stages.

The runtime should be accepted.

The bundle should be publishable for research review.

## Directory layout

The public fixture module contains source receipts.

The public fixture module contains records.

The fixture evaluator contains execution logic.

The contract module contains issue vocabulary.

The schema module contains field specifications.

The replay module contains deterministic receipts.

The scenario module contains boundary combinations.

The policy module contains allowed decisions.

The lineage module contains source edges.

The reconciliation module contains expected-state comparison.

The metrics module contains descriptive measures.

The bundle module contains release inputs.

The quality module contains blocking checks.

The runtime module contains ordered stages.

The release module contains release state.

The observability module contains structured events.

The views module contains review rows.

The exports module contains JSON and CSV boundaries.

The depth module contains a twenty-check audit.

The adapter module contains input declarations.

The threshold module contains 972 probes.

The artifact module contains seven nodes.

The invariant module contains ten invariants.

The queue module contains held and ready review rows.

## Operation order

Citation resolution is the first operation.

Graph construction follows citation resolution.

Edge validation follows graph construction.

Disagreement tracking follows graph construction.

Metrics follow evaluation.

Policy follows evaluation.

Lineage follows evaluation.

Reconciliation follows policy.

The quality gate follows lineage and reconciliation.

The bundle follows the quality gate.

The release follows the bundle.

The review view follows the release.

The review queue follows policy and evaluation.

The export follows the view.

## Data audit procedure

Load the default fixture.

Confirm the fixture ID.

Confirm the fixture version.

Confirm the context key.

Confirm the evidence boundary.

Count source receipts.

Count records.

Count positive records.

Count control records.

Check record ID uniqueness.

Check source binding.

Check operation coverage.

Check record context.

Check record addresses.

Check source addresses.

Check fixture version.

An audit failure is actionable.

An audit failure is not ignored.

An audit failure blocks the runtime.

## C01 operating procedure

Inspect the input format.

Inspect the source ID.

Inspect the source version.

Inspect citation rows.

Inspect required fields.

Inspect row hashes.

Inspect citation IDs.

Inspect quarantined rows.

Confirm the positive state.

Confirm the positive issue code.

Confirm the malformed JSON control.

Confirm the duplicate ID control.

Confirm the no-header control.

Do not discard the quarantine list.

Do not replace a missing field with an inferred value.

Do not treat a parsed citation as source agreement.

Do not treat a valid URI as a verified source.

## C02 operating procedure

Inspect graph ID.

Inspect graph version.

Inspect claim IDs.

Inspect citation IDs.

Inspect parent claim IDs.

Inspect supersession targets.

Inspect active claim IDs.

Inspect superseded claim IDs.

Inspect orphan claim IDs.

Inspect context mismatch IDs.

Inspect contradictory edge IDs.

Inspect graph warnings.

Confirm the positive replacement.

Confirm the original remains in history.

Confirm the missing-lineage control.

Confirm the context control.

Confirm the duplicate-ID control.

Do not delete superseded claims.

Do not repair an orphan by changing history.

Do not carry a claim across graph context.

## C03 operating procedure

Select an edge ID.

Select an expected context when needed.

Inspect all claim IDs.

Inspect active claim IDs.

Inspect missing source IDs.

Inspect source IDs.

Inspect contradiction flag.

Inspect uncertainty.

Inspect warnings.

Confirm the supported positive.

Confirm the missing-source control.

Confirm the context control.

Confirm the absent-edge control.

Do not interpret uncertainty as a probability.

Do not treat a missing source as a negative measurement.

Do not treat an absent edge as evidence of absence.

Do not collapse warning text into a generic state.

## C04 operating procedure

Select explicit edge IDs.

Inspect active claim IDs.

Inspect positive claim IDs.

Inspect negative claim IDs.

Inspect value groups.

Inspect source IDs.

Inspect unresolved flag.

Inspect contradictory edge IDs.

Inspect incomplete edge IDs.

Inspect out-of-domain edges.

Confirm the positive contradiction.

Confirm the clear control.

Confirm the incomplete control.

Confirm the out-of-domain control.

Do not average positive and negative claims.

Do not remove a negative claim from the report.

Do not call a clear record causal.

Do not turn an out-of-domain record into a local result.

## Fixture file workflow

Export the default fixture to JSON.

Preserve source content addresses.

Preserve record content addresses.

Preserve enum values as strings.

Preserve tuple fields as arrays.

Preserve payload objects.

Preserve expected issue codes.

Load the JSON file.

Run the data audit.

Run the evaluator.

Compare evaluation addresses.

The loader rejects missing source lists.

The loader rejects missing record lists.

The loader rejects incomplete fixture metadata.

The loader converts operation values back to typed values.

The loader converts role values back to typed values.

The loader converts source IDs to tuples.

The loader converts issue codes to tuples.

## Replay procedure

Run replay with a named replay ID.

Run replay with a second replay ID.

Compare evaluation addresses.

Compare execution addresses.

Compare accepted state.

Inspect drift fields.

An empty drift list is required.

The fixture uses fixed retrieval time.

The fixture uses fixed claim creation time.

The fixture does not use random numbers.

The fixture does not use current time.

The fixture does not use network responses.

## Policy procedure

Load the policy.

Inspect policy ID.

Inspect policy rules.

Inspect allowed uses.

Inspect excluded uses.

Evaluate positive records.

Confirm four policy decisions.

Confirm four publishable positive paths.

Confirm controls are not policy positives.

Confirm graph replay is allowed as review.

Confirm citation review is bounded.

Confirm diagnosis is excluded.

Confirm treatment selection is excluded.

Confirm individual risk is excluded.

## Lineage procedure

Build lineage after evaluation.

Count source-to-execution edges.

Count fixture-to-execution edges.

Confirm thirty-six total edges.

Confirm sixteen terminal addresses.

Confirm acyclic state.

Inspect a C01 source edge.

Inspect a C02 source edge.

Inspect a C03 source edge.

Inspect a C04 source edge.

Inspect a control source edge.

Lineage is a traceability surface.

Lineage is not a causal graph.

Lineage is not a source-quality score.

## Reconciliation procedure

Build reconciliation after policy.

Confirm sixteen reconciliation items.

Confirm zero mismatch IDs.

Confirm expected state fields.

Confirm observed state fields.

Confirm expected issue fields.

Confirm observed issue fields.

Confirm policy decision count.

A mismatch is a release blocker.

A mismatch remains visible in the report.

The reconciler does not mutate records.

The reconciler does not mutate executions.

## Quality procedure

Load contracts.

Load schema.

Build lineage.

Build reconciliation.

Run the quality gate.

Confirm twelve checks.

Confirm twelve passed checks.

Confirm issue vocabulary coverage.

Confirm HTTPS source coverage.

Confirm exact context.

Confirm boundary.

Confirm graph history remains represented.

## Runtime procedure

Start with data audit.

Capture stage one address.

Capture stage duration.

Load contracts.

Load schema.

Evaluate records.

Measure metrics.

Apply policy.

Build lineage.

Reconcile records.

Run quality gate.

Assemble bundle.

Inspect ten stage IDs.

Inspect runtime accepted state.

## Release procedure

Build the runtime bundle.

Build the replay receipt.

Build the quality gate.

Build the release manifest.

Inspect four release checks.

Inspect ready state.

Inspect allowed uses.

Inspect excluded uses.

Inspect content address.

The ready state is review readiness.

The ready state is not assay success.

The ready state is not a clinical state.

## Review queue procedure

Build the queue from fixture and evaluation.

Pass policy decisions to the builder.

Confirm sixteen queue items.

Confirm four ready items.

Confirm twelve held items.

Confirm six queue checks.

Inspect next item.

Inspect issue codes.

Inspect priority.

Inspect next action.

Resolve a held issue in a new fixture revision.

Replay the revised fixture.

Build a new queue.

Compare queue addresses.

Keep the old control row for comparison.

Do not manually promote a held row.

## Export procedure

Export JSON for machine review.

Export canonical JSON for content comparison.

Export manifest for release tracking.

Export CSV for tabular review.

Confirm CSV header.

Confirm sixteen data rows.

Confirm issue code separators.

Confirm source ID separators.

Confirm role column.

Confirm release-state column.

## Failure triage

If data audit fails, inspect fixture structure.

If citation state fails, inspect input text.

If graph state fails, inspect claim lineage.

If edge state fails, inspect source references.

If disagreement state fails, inspect active claims.

If replay drifts, inspect time fields.

If lineage count fails, inspect source bindings.

If reconciliation fails, inspect expected issue codes.

If quality fails, inspect the first failed check.

If runtime fails, inspect the failed stage.

If release blocks, inspect release checks.

If queue fails, inspect role separation.

If CSV fails, inspect review view rows.

## Local test commands

Run the legacy lifecycle tests.

```powershell
python -m pytest -q tests/test_evidence_lifecycle.py
```

Run the deep frontier tests.

```powershell
python -m pytest -q tests/test_evidence_lifecycle_frontier_evidence.py
python -m pytest -q tests/test_evidence_lifecycle_frontier_depth.py
python -m pytest -q tests/test_evidence_lifecycle_frontier_evidence_cli.py
```

Run the registry test.

```powershell
python -m pytest -q tests/test_capability_registry.py
```

Run targeted Ruff.

```powershell
python -m ruff check --ignore E501 src/glio_noncode/evidence_lifecycle_frontier_*.py
python -m ruff check --ignore E501 tests/test_evidence_lifecycle_frontier_*.py
```

Run the full suite before commit.

```powershell
python -m pytest -q
```

## CI procedure

CI runs all lifecycle commands.

CI runs the evaluator on every Python lane.

CI runs the runtime rehearsal on every Python lane.

CI runs the review queue on every Python lane.

CI runs the CSV export on every Python lane.

CI runs the depth audit on every Python lane.

CI stores command failures in the job log.

CI does not fetch private inputs.

CI does not require live source access.

## Handoff checklist

Record the commit ID.

Record the main run URL.

Record the build branch run URL.

Record local full-suite result.

Record focused test result.

Record targeted lint result.

Record staged scan result.

Record evaluation count.

Record quality count.

Record depth count.

Record queue counts.

Record release state.

Record remaining partial capabilities.

## Safe changes

Add a control with an explicit issue code.

Add a source receipt with an HTTPS URI.

Add a fixed timestamp to a deterministic row.

Add a check with observed and required values.

Add a test for a new failure mode.

Add a schema field with a contract update.

Add a CLI command with a smoke test.

Add a release note for a boundary change.

Run the full suite after structural changes.

## Unsafe changes

Do not remove a control row.

Do not hide an issue code.

Do not average contradiction values.

Do not erase superseded history.

Do not change context silently.

Do not use current time in fixture payloads.

Do not add private source material.

Do not add patient-level material.

Do not change excluded uses without review.

Do not mark a partial capability verified without evidence.

## Completion state

The operation is complete when the focused suite passes.

The operation is complete when the full suite passes.

The operation is complete when CI passes on main.

The operation is complete when CI passes on build/foundation.

The operation is complete when the commit is on main.

The operation is complete when the staged scan is clean.

The operation is complete when the release remains research scoped.
