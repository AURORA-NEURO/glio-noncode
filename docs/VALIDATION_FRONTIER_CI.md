# Domain 13 planning CI

CI verifies the public aggregate planning boundary on Python 3.11, 3.12, and
3.13. It does not require restricted inputs or external credentials.

## Local commands

```powershell
python -m pytest -q tests/test_validation_frontier_evidence.py tests/test_validation_frontier_depth.py tests/test_validation_frontier_evidence_cli.py
python -m pytest -q
python -m ruff check --ignore E501 src/glio_noncode/validation_frontier_*.py tests/test_validation_frontier_*.py
```

## CI command order

1. data boundary audit;
2. contracts;
3. schema;
4. evaluation;
5. replay;
6. metrics;
7. lineage;
8. policy;
9. quality gate;
10. runtime;
11. observability;
12. artifacts;
13. bundle;
14. release;
15. review CSV;
16. depth audit.

Each step writes to a temporary output and must return zero.

## Expected anchors

| Surface | Expected |
| --- | ---: |
| source receipts | 5 |
| fixture records | 16 |
| positives | 4 |
| controls | 12 |
| evaluation checks | 120 |
| lineage edges | 36 |
| metrics | 13 |
| quality checks | 12 |
| runtime stages | 10 |
| scenarios | 31 |
| threshold probes | 972 |
| observability events | 26 |
| artifacts | 7 |
| depth checks | 20 |

These values are regression anchors for the checked-in fixture.

## Failure response

Identify the first failed command, reproduce it locally, inspect its output,
run the focused test, preserve the failed artifact, apply the smallest fix, and
rerun all release commands. Do not skip an earlier failed surface because a
later command still emits JSON.

## Commit gate

- [ ] Focused tests pass.
- [ ] Full suite passes.
- [ ] Targeted Ruff is clean.
- [ ] Staged diff check is clean.
- [ ] Added-line metadata scan is clean.
- [ ] Staged insertions exceed the build threshold.
- [ ] Only intended paths are staged.
- [ ] Main and build branch point to the same commit.
- [ ] Both Actions runs are green.

## Non-goals

CI proves that the bounded planning implementation remains executable. It does
not prove assay efficacy, safety, statistical power, external validity, or
clinical utility.
