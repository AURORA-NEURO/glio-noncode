# Domain 11 continuous integration contract

## Objective

The Domain 11 continuous integration surface proves that the public aggregate
fixture, contracts, evaluator, controls, release surfaces, and CLI remain
consistent on every supported Python version. It is a repository check, not a
scientific validation claim.

## Required checks

The CI job should run the following sequence:

1. compile all Domain 11 modules;
2. run targeted lint on the new modules and tests;
3. run public-data audit;
4. run fixture evaluation;
5. run replay;
6. run metrics;
7. run lineage;
8. run policy;
9. run quality gate;
10. run runtime;
11. run release manifest;
12. run depth audit;
13. run focused Domain 11 tests;
14. run the complete test suite.

## Matrix

The workflow uses a Python version matrix. Each version must produce the same
semantic receipt even if timing differs. The matrix catches differences in
typing, enum serialization, dataclass behavior, and JSON ordering.

## Commands

```powershell
python -m py_compile src/glio_noncode/causal_frontier_adapters.py
python -m py_compile src/glio_noncode/causal_frontier_artifacts.py
python -m py_compile src/glio_noncode/causal_frontier_checks.py
python -m py_compile src/glio_noncode/causal_frontier_contracts.py
python -m py_compile src/glio_noncode/causal_frontier_depth.py
python -m py_compile src/glio_noncode/causal_frontier_fixture_eval.py
python -m py_compile src/glio_noncode/causal_frontier_public_data.py
python -m py_compile src/glio_noncode/causal_frontier_quality_gate.py
python -m ruff check --ignore E501 src/glio_noncode/causal_frontier_*.py tests/test_causal_frontier_*.py
python -m glio_noncode causal-frontier-data-audit
python -m glio_noncode causal-frontier-contracts
python -m glio_noncode causal-frontier-schema
python -m glio_noncode causal-frontier-evaluate
python -m glio_noncode causal-frontier-replay
python -m glio_noncode causal-frontier-metrics
python -m glio_noncode causal-frontier-lineage
python -m glio_noncode causal-frontier-policy
python -m glio_noncode causal-frontier-quality-gate
python -m glio_noncode causal-frontier-runtime
python -m glio_noncode causal-frontier-release
python -m glio_noncode causal-frontier-depth-audit
python -m pytest -q tests/test_causal_frontier_evidence.py
python -m pytest -q tests/test_causal_frontier_depth.py
python -m pytest -q tests/test_causal_frontier_evidence_cli.py
python -m pytest -q tests/test_causal_frontier_surfaces.py
```

## Expected counts

| Surface | Expected |
| --- | ---: |
| source receipts | 5 |
| records | 16 |
| positive records | 4 |
| control records | 12 |
| operation contracts | 4 |
| operation schemas | 4 |
| evaluation checks | 120 |
| lineage edges | 36 |
| quality checks | 12 |
| runtime stages | 10 |
| metrics | 13 |
| depth checks | 18 |
| threshold profiles | 4 |
| threshold probes | 324 |
| artifact inventory entries | 7 |
| invariant entries | 10 |

Changing a count requires a deliberate module update and a test update. A
workflow that only checks exit status can miss a reduction in control coverage,
so the focused tests assert these counts.

## Artifact handling

JSON command output can be captured as a CI artifact for review. The preferred
artifact set is:

- data audit;
- evaluation;
- replay;
- quality gate;
- runtime;
- release;
- depth audit;
- review CSV.

Artifacts should be retained long enough to compare a changed run with the
previous successful run. The content addresses make comparison compact.

## Failure triage

### Compile failure

Inspect imports, enum names, and circular dependencies. Do not skip the module
from CI merely because the core evaluator still imports.

### Lint failure

Fix new code directly. Keep legacy unrelated warnings separate from the Domain
11 targeted lint result.

### Evaluation failure

Inspect the first failed check ID. Compare expected and observed state and issue
codes. This usually points to one adapter branch or fixture control.

### Quality-gate failure

Inspect `blocking_check_ids`. A quality failure should not be hidden by running
only the positive test.

### Depth failure

Inspect the observed and required values. A count failure often means a new
control or source was added without updating a release surface.

### CLI failure

Run the same command locally with no input path, then with a temporary fixture
path. Confirm both stdout and output-file modes.

## Source integrity check

The workflow also scans added lines for restricted metadata markers. New files
must contain implementation identity and boundary information through ordinary
module documentation and content addresses, not through generated metadata
fields. The scan is applied to staged added lines before a substantial commit.

## Test ownership

The focused test groups have distinct jobs:

| Test file | Focus |
| --- | --- |
| `test_causal_frontier_evidence.py` | operation behavior and release surfaces |
| `test_causal_frontier_depth.py` | depth counts and invariants |
| `test_causal_frontier_evidence_cli.py` | command parsing and output paths |
| `test_causal_frontier_surfaces.py` | reusable adapter and artifact APIs |

The full suite remains required because the package export surface and capability
registry are shared with the earlier domains.

## Release branch procedure

1. implement a coherent module slice;
2. run focused tests;
3. run full tests;
4. stage only intended files;
5. inspect staged diff and added-line metadata scan;
6. verify line count is substantial;
7. commit to main history as requested;
8. push the main branch;
9. wait for every matrix job;
10. record run URLs and result counts;
11. update the capability ledger;
12. begin the next domain only after the build is green.

## Reproducibility note

Wall-clock stage durations are expected to differ. Fixture, evaluation,
execution, check, metrics, lineage, bundle, and release addresses should remain
stable when inputs and code are stable. If only a timing field differs, that is
not address drift because timing belongs to the runtime stage receipt rather
than deterministic operation bodies.

## Security and privacy boundary

The fixture contains public aggregate references only. CI should not add private
case material, access tokens, local paths, or unreviewed external downloads to
the fixture. A new external source requires a public URI, scope statement,
release marker, and source receipt.

## CI completion statement

A green Domain 11 job means the repository can reproduce its declared public
aggregate evidence boundary, including positive and control behavior, under the
supported runtime matrix. It does not mean that any hypothesis is clinically
valid or causally established.
