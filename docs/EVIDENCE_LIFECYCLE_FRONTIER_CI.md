# Evidence Lifecycle Frontier CI

## CI purpose

CI verifies the Domain 14 C01–C04 surface on every supported Python lane.

CI runs the same public aggregate fixture on each lane.

CI runs the full unit suite.

CI compiles the package.

CI executes the legacy lifecycle tests.

CI executes the frontier evaluator.

CI executes the frontier release rehearsal.

CI executes the frontier review queue.

CI executes the frontier CSV export.

CI executes the frontier depth audit.

CI does not require private inputs.

CI does not require live source access.

CI does not require patient data.

## Python matrix

The workflow includes Python 3.11.

The workflow includes Python 3.12.

The workflow includes Python 3.13.

Each lane installs the package.

Each lane compiles the package.

Each lane runs unit tests.

Each lane runs command checks.

## Command order

The data boundary audit runs first.

The contract command runs second.

The schema command runs third.

The evaluator runs fourth.

The replay command runs fifth.

The metrics command runs sixth.

The lineage command runs seventh.

The policy command runs eighth.

The quality gate runs ninth.

The runtime rehearsal runs tenth.

The observability command runs eleventh.

The artifact inventory runs twelfth.

The bundle command runs thirteenth.

The release command runs fourteenth.

The review queue runs fifteenth.

The CSV export runs sixteenth.

The depth audit runs seventeenth.

## Expected outputs

The data audit is accepted.

The contract count is four.

The schema count is four.

The evaluation count is 120.

The replay is accepted.

The metric count is thirteen.

The lineage edge count is thirty-six.

The policy decision count is four.

The quality check count is twelve.

The runtime stage count is ten.

The observability event count is twenty-six.

The artifact count is seven.

The bundle is publishable.

The release is ready.

The queue has four ready rows.

The queue has twelve held rows.

The CSV has seventeen lines.

The depth check count is twenty.

## Failure interpretation

A data audit failure indicates fixture drift.

A contract failure indicates issue vocabulary drift.

A schema failure indicates field drift.

An evaluator failure indicates expected-state drift.

A replay failure indicates nondeterminism.

A metrics failure indicates measurement drift.

A lineage failure indicates traceability drift.

A policy failure indicates release-boundary drift.

A quality failure indicates a blocking invariant.

A runtime failure indicates ordered-stage failure.

An observability failure indicates event loss.

An artifact failure indicates release inventory drift.

A bundle failure indicates release assembly drift.

A release failure indicates an unmet gate.

A queue failure indicates role or coverage drift.

A CSV failure indicates review-row loss.

A depth failure indicates shallow module coverage.

## Local CI reproduction

Run package compile.

```powershell
python -m compileall -q src
```

Run focused tests.

```powershell
python -m pytest -q tests/test_evidence_lifecycle_frontier_evidence.py tests/test_evidence_lifecycle_frontier_depth.py tests/test_evidence_lifecycle_frontier_evidence_cli.py
```

Run targeted lint.

```powershell
python -m ruff check --ignore E501 src/glio_noncode/evidence_lifecycle_frontier_*.py tests/test_evidence_lifecycle_frontier_*.py
```

Run the full suite.

```powershell
python -m pytest -q
```

## CI artifact handling

Command outputs use temporary paths.

Temporary outputs are not source fixtures.

Temporary outputs are not committed.

The JSON output remains machine-readable.

The CSV output remains review-readable.

The job log retains command names.

The job log retains exit status.

The job log retains failure text.

## Branch verification

The protected main path runs the quality workflow.

The build/foundation path runs the quality workflow.

Both runs use the same commit SHA.

Both runs use the same fixture.

Both runs use the same command list.

Both runs must pass before handoff.

## CI change procedure

Add a command to the CLI.

Add a focused command test.

Add the command to the workflow.

Add expected output documentation.

Run the command locally.

Run the focused test.

Run the full suite.

Stage the workflow change.

Run the staged scan.

Commit the complete build.

Push the exact SHA.

Wait for main.

Wait for build/foundation.

## CI boundary

CI verifies declared behavior.

CI verifies deterministic fixtures.

CI verifies output shape.

CI verifies control retention.

CI verifies release policy.

CI does not verify external source truth.

CI does not verify experimental effect.

CI does not verify patient outcome.

CI does not grant clinical use.

## Completion

The CI surface is complete when all commands run.

The CI surface is complete when all expected counts hold.

The CI surface is complete when all matrix lanes pass.

The CI surface is complete when main passes.

The CI surface is complete when build/foundation passes.

The CI surface is complete when the release remains research scoped.
