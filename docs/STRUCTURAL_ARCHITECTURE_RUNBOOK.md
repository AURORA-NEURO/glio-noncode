# Structural architecture runbook

Run from the repository root with the checked-in public aggregate fixture.
The commands below are deterministic and write only to the requested output
paths.

## Preflight

```text
python -m compileall -q src/glio_noncode
python -m glio_noncode structural-architecture-data-audit --output /tmp/d02-data.json
python -m glio_noncode structural-architecture-plan --output /tmp/d02-plan.json
```

Stop if the data audit is not accepted or the plan is not executable.

## Execution and release

```text
python -m glio_noncode evaluate-structural-architecture --output /tmp/d02-evaluation.json
python -m glio_noncode structural-architecture-runtime --output /tmp/d02-runtime.json
python -m glio_noncode structural-architecture-quality --output /tmp/d02-quality.json
python -m glio_noncode structural-architecture-depth --output /tmp/d02-depth.json
python -m glio_noncode replay-structural-architecture --output /tmp/d02-replay.json
python -m glio_noncode structural-architecture-bundle --output /tmp/d02-bundle
```

The runtime and quality commands must return zero. The bundle directory must
contain the six expected files and a `published` release state.

## Review and diagnostics

```text
python -m glio_noncode structural-architecture-review-csv --output /tmp/d02-review.csv
python -m glio_noncode structural-architecture-query --state review --output /tmp/d02-held.json
python -m glio_noncode structural-architecture-failures --output /tmp/d02-failures.json
python -m glio_noncode structural-architecture-invariants --output /tmp/d02-invariants.json
```

Controls are expected to appear in review. Do not edit a published receipt to
remove a control. Repair the input or source/context declaration, then replay
the same fixture and compare content addresses.

## Focused verification

```text
python -m unittest tests.test_structural_architecture tests.test_structural_architecture_cli -q
```

The test suite verifies source scope, operation cardinality, adapter dispatch,
control holding, review routing, lineage conservation, six artifact output,
runtime ordering, replay determinism, quality gating, query filtering, and
CLI exit status.
