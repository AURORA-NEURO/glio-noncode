# Domain 11 operations and replay guide

## Overview

The causal frontier is an operational module with four scientific-beta adapters
and a common evidence envelope. It is designed to make review state visible at
the point where a score would otherwise be over-interpreted.

The recommended operating order is:

```text
data audit -> contracts -> schema -> evaluation -> replay -> metrics
    -> policy -> lineage -> reconciliation -> quality gate
    -> runtime -> release -> review export
```

Each step can be run independently from the Python API or the command line.
The runtime composes the same steps in a fixed sequence.

## Starting a run

With no input path, the CLI uses the checked-in public aggregate fixture:

```powershell
glio-noncode causal-frontier-runtime --output runtime.json
```

The output includes ten stages and a release bundle. To use a caller fixture,
provide a JSON path:

```powershell
glio-noncode causal-frontier-runtime fixture.json --output runtime.json
```

The caller fixture is not trusted merely because it parses. The data audit and
quality gate still execute against it. A caller fixture with zero source rows,
missing controls, or an unknown issue code should produce a review or blocked
result.

## Data audit

The data audit is the first safe stop:

```powershell
glio-noncode causal-frontier-data-audit
```

Inspect:

- `accepted`;
- `failed_check_ids`;
- `fixture_version`;
- `evidence_boundary`;
- source and record counts;
- source-reference and HTTPS checks.

An audit can be accepted even when a later operation result is partial. The
audit describes fixture integrity, not biological support.

## Contracts and schema

Contracts:

```powershell
glio-noncode causal-frontier-contracts
```

Schema:

```powershell
glio-noncode causal-frontier-schema
```

Compare the contract content address and schema content address with the
release manifest. If either changes, inspect required fields, issue codes,
positive states, control states, and excluded-use language.

## Evaluation

Evaluation is the primary behavior check:

```powershell
glio-noncode causal-frontier-evaluate --output evaluation.json
```

The expected result is 16 executions and 120 checks. The positive path should
have four accepted executions: three supported results and one published
manifest. All twelve controls should remain non-accepted and carry issue codes.

A useful inspection pattern is:

```powershell
$result = Get-Content evaluation.json | ConvertFrom-Json
$result.executions | Select-Object record_id, operation, role, state, issue_codes
```

The evaluation output is intentionally verbose. It retains operation output so
reviewers can inspect posterior components, driver ranks, prediction thresholds,
abstentions, and dossier addresses without re-running a hidden calculation.

## C13 posterior decomposition

The positive C13 record contains two hypotheses. The adapter calculates a raw
component for each and normalizes them. The top hypothesis is a field in the
report. It is not a conclusion.

The controls prove three boundaries:

| Control | Expected result |
| --- | --- |
| zero component mass | partial plus zero mass issue |
| empty array | invalid plus empty input issue |
| prior above one | invalid plus typed input issue |

When reviewing C13, compare prior, likelihood, measurement, and dependence
penalty. A normalized posterior without these components is not sufficient for
review in this boundary.

## C14 regulatory driver posterior

The positive C14 record contains two driver hypotheses with separate evidence ID
lists. The adapter ranks them and retains support and prior. The low-support
control remains in the output and receives `low_driver_support`.

The driver ID is a stable row identity, not a claim that the driver regulates a
specific clinical outcome. Reviewers should follow evidence IDs and inspect the
source receipts before using the ranking for further research.

## C15 selective prediction

The positive C15 record has a high score and low uncertainty. The first control
has a weak score. The second control has high uncertainty despite a strong
score. The second control intentionally demonstrates two issue codes:

```text
prediction_uncertainty_high
selective_prediction_abstention
```

This matters because uncertainty can affect both the decision and the reason
for abstention. Consumers must not retain only one issue code.

The matrix command is available through the Python API and depth audit. It
crosses score, uncertainty, support, evidence count, and operation dimensions.
Threshold changes should be tested against the matrix before release.

## C16 dossier publication

The positive C16 record binds two hypotheses and two evidence addresses. The
publisher emits a dossier address and `published` state. The artifact is a
manifest of references. It has no field that asserts mechanism, diagnosis,
prognosis, pathogenicity, or treatment value.

The controls cover:

- a top hypothesis not in the declared hypothesis set;
- an empty dossier input;
- a missing evidence address.

Each condition is invalid and remains visible in the evaluation.

## Replay

Replay produces a compact receipt:

```powershell
glio-noncode causal-frontier-replay --output replay.json
```

The receipt includes fixture address, evaluation address, all execution
addresses, check count, passed check count, and acceptance. It is suitable for
CI artifact comparison.

Two replay IDs can differ while their content addresses remain identical. This
is expected. The replay ID identifies the run; the content address identifies
the deterministic result.

## Metrics

```powershell
glio-noncode causal-frontier-metrics --output metrics.json
```

The current report has 13 metrics:

1. overall check pass rate;
2. positive acceptance rate;
3. control rejection rate;
4. four operation acceptance rates;
5. four operation issue-free rates;
6. issue-free execution rate;
7. inverse issue-density score.

These metrics describe fixture and operation behavior. They should not be
plotted as patient outcomes or used as evidence of treatment effect.

## Policy and reconciliation

Policy:

```powershell
glio-noncode causal-frontier-policy --output policy.json
```

Reconciliation is included in the quality gate and runtime, but the Python API
can inspect it directly. Policy decisions use positive operation paths for
release disposition while controls remain part of the quality evidence.

Reconciliation compares exact sorted issue code tuples. If an implementation
adds an issue code to a control, reconciliation fails until the fixture and
contract are intentionally updated.

## Lineage

```powershell
glio-noncode causal-frontier-lineage --output lineage.json
```

The lineage graph contains source-to-execution and fixture-to-execution edges.
The fixture currently has 36 edges. The graph must be acyclic, and every
execution must appear as a terminal address.

Reviewers should use the edge explanation and operation field to distinguish a
source receipt from a transformed operation output. A source URI is not the
same thing as a result address.

## Quality gate

```powershell
glio-noncode causal-frontier-quality-gate --output quality.json
```

The quality gate is the preferred pre-release stop. It has 12 blocking checks.
The `blocking_check_ids` field should be empty. A failure should be investigated
at the narrowest layer possible:

| Failure | First inspection |
| --- | --- |
| data-audit | fixture and source receipt manifest |
| evaluation | record state and issue checks |
| contract-coverage | operation enum and contracts |
| schema-coverage | schema operation map |
| lineage-acyclic | edge parent/child relationships |
| reconciliation | expected vs observed record |
| issue-vocabulary | contract issue sets |

## Runtime and release

```powershell
glio-noncode causal-frontier-runtime --output runtime.json
glio-noncode causal-frontier-release --output release.json
```

The runtime bundle is the input to the release manifest. The release manifest
has four checks and a state. `ready` means all checks pass. `review` means the
artifact is useful for diagnosis but is not a ready release.

## Review CSV

```powershell
glio-noncode export-causal-frontier-review-csv --output review.csv
```

The CSV has one row per fixture record and retains role, state, acceptance,
source count, issue codes, and content address. It is intended for a review
queue or spreadsheet inspection. It is not a replacement for the JSON receipt;
the JSON retains nested operation output and full lineage references.

## Python API sequence

```python
from glio_noncode.causal_frontier_contracts import default_causal_frontier_contracts
from glio_noncode.causal_frontier_fixture_eval import evaluate_causal_frontier_fixture
from glio_noncode.causal_frontier_public_data import default_causal_frontier_fixture
from glio_noncode.causal_frontier_quality_gate import evaluate_causal_frontier_quality
from glio_noncode.causal_frontier_schema import default_causal_frontier_schema

fixture = default_causal_frontier_fixture()
contracts = default_causal_frontier_contracts()
schema = default_causal_frontier_schema()
evaluation = evaluate_causal_frontier_fixture(fixture)
```

The remaining layers accept these immutable values and return new immutable
receipts. A caller can therefore retain each intermediate artifact for audit.

## Failure handling

Validation failures are converted into typed invalid execution receipts during
fixture evaluation. Direct adapter calls still raise `ValidationError` for
malformed input. This distinction lets a replay continue across negative
controls while preserving direct API strictness.

Do not catch an invalid receipt and turn it into an empty positive result. Keep
the record ID, issue code, error string, and content address together.

## Performance notes

The fixture is intentionally deterministic and small. Operations use in-memory
tuples and canonical hashing. Runtime stage duration is observable but not part
of the content address of deterministic operation outputs. A slow run should be
investigated as an environment or scaling issue without changing the scientific
receipt.

## Extension checklist

To add a new operation:

1. add an enum member;
2. add a public fixture positive and three controls;
3. add a contract;
4. add schema fields;
5. add evaluator dispatch;
6. add policy behavior;
7. add lineage and metrics coverage;
8. add CLI command;
9. add tests and docs;
10. update depth counts and release evidence.

The same checklist applies when the operation already exists but a new issue
code, state, source, or threshold is introduced.
