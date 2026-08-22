# Domain 04 C13-C16 validation and evidence gate

## Required evidence counts

The accepted fixture is intentionally small but not shallow:

| Evidence family | Required count | Current count |
| --- | ---: | ---: |
| Public source receipts | 5 | 5 |
| Operation records | 16 | 16 |
| Positive records | 4 | 4 |
| Control records | 12 | 12 |
| Data audit checks | 23 | 23 |
| Execution checks | 48 | 48 |
| Replay checks | 12 | 12 |
| Quality checks | 25 | 25 |
| Policy rules | 12 | 12 |
| Lineage nodes | at least 100 | 111 |
| Lineage edges | at least 100 | 133 |
| Scenario rows | 16 | 16 |
| Threshold rows | 12 | 12 |
| Validation rows | 4 | 4 |
| Runbook steps | 14 | 14 |

The four operations are balanced at four records each. A positive record
demonstrates the accepted path; controls demonstrate missing, mismatched,
foreign, unavailable, drifted, or failed-check conditions.

## Execution assertions

Every record receives three execution assertions:

1. The observed state equals `expected_state`.
2. The sorted observed issue codes equal `expected_issue_codes`.
3. The execution receipt is content addressed.

The independent projection audit adds state vocabulary, raw-key redaction,
schema projection, receipt address, declared issue vocabulary, and acceptance
semantics for every execution. This keeps the fixture evaluator from being the
only source of evidence about its own output.

## Replay

Replay repeats the exact fixture with the same bounded adapters. It compares
fixture identity, execution tuples, check tuples, evaluation address, accepted
state, record count, check count, execution addresses, check addresses, record
order, and operation order. A replay report is accepted only when every
comparison passes.

## Scenario matrix

The scenario matrix has four rows per operation:

- C13: matched receipt, missing URI, checksum mismatch, missing license.
- C14: ignored receipt change, substantive field change, new identity, stable
  repeated identity.
- C15: available exact context, foreign context, unavailable row, missing
  identity.
- C16: all checks true, checksum false, context false, multiple checks false.

Each scenario retains an expected state, issue codes, and release risk. The
matrix itself is deterministic and independently addressable.

## Thresholds

Twelve thresholds enforce source count, record count, positive/control counts,
check count, operation count, lineage depth, sanitization, evaluation
acceptance, addressed execution count, and issue vocabulary. The threshold
report records observed value, operator, target, pass state, and address.

## Validation matrix

One validation row exists per capability ID `GNC-D04-C13` through
`GNC-D04-C16`. Each row maps the four fixture record IDs to the operation,
required test paths, and boundary assertions:

- public fixture;
- positive path;
- control path;
- replay;
- quality gate;
- CLI smoke;
- exact context;
- public aggregate boundary;
- content addressing;
- raw-row exclusion.

The matrix closes over all sixteen execution IDs and requires accepted runtime
evaluation before it can pass.

## Test commands

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_reference_release_frontier tests.test_reference_release_frontier_cli tests.test_capability_registry -v
ruff check src/glio_noncode/reference_release_frontier_*.py tests/test_reference_release_frontier*.py
python -m compileall -q src tests
```

The full repository command remains:

```powershell
python -m unittest discover -s tests -t . -v
```

The release package is promoted in the capability ledger only when the local
focused tests, complete suite, CLI checks, content-address checks, and staged
metadata scan all pass.
