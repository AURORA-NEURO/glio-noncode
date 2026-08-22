# Domain 12 CI and release verification

Continuous integration treats the cohort frontier as a vertical release
surface. The checks run against the default public aggregate and do not require
restricted inputs or external service credentials.

## Local baseline

Run focused compilation and tests first:

```powershell
python -m py_compile src/glio_noncode/cohort_frontier_*.py
python -m pytest -q tests/test_cohort_frontier_evidence.py tests/test_cohort_frontier_depth.py tests/test_cohort_frontier_evidence_cli.py
```

Then run the complete suite:

```powershell
python -m pytest -q
```

The focused suite covers public data, evaluation, contracts, schema, policy,
lineage, metrics, quality, runtime, replay, exports, depth, and CLI behavior.

## Static checks

The new modules and tests are checked with the targeted Ruff command:

```powershell
python -m ruff check --ignore E501 src/glio_noncode/cohort_frontier_*.py tests/test_cohort_frontier_*.py
```

The repository has older files with their own lint history. The Domain 12
surface is checked directly so unrelated formatting changes do not obscure a
new regression.

## Workflow commands

The CI workflow runs these commands in order:

1. data boundary audit;
2. operation contracts;
3. schema manifest;
4. fixture evaluation;
5. replay integrity;
6. metrics;
7. lineage;
8. policy;
9. quality gate;
10. runtime rehearsal;
11. release bundle;
12. release manifest;
13. review CSV;
14. depth audit.

Each command writes to a temporary output path. The command must return zero and
the output must be serializable. The workflow is intentionally explicit so a
failed surface is easy to identify in the run log.

## Expected CI values

| Surface | Expected |
| --- | ---: |
| source receipts | 5 |
| fixture records | 16 |
| positive records | 4 |
| control records | 12 |
| evaluation checks | 120 |
| lineage edges | 36 |
| metrics | 11 |
| quality checks | 12 |
| runtime stages | 10 |
| scenarios | 33 |
| threshold probes | 972 |
| depth checks | 19 |

The values are regression anchors for the public fixture, not universal limits
for future caller fixtures.

## Test layering

The evidence test module validates semantic output. The depth module validates
counts and cross-surface relationships. The CLI module validates command names,
serialization, output paths, and input loading. A release is not considered
complete if only one layer passes.

## Workflow failure response

When CI fails:

1. identify the first failed command;
2. reproduce it locally with the same arguments;
3. inspect the output file or stderr;
4. run the focused test for that surface;
5. preserve the failure while applying the smallest fix;
6. rerun the focused suite and full suite;
7. rerun every release command;
8. inspect the staged diff before commit.

Do not skip a release command because a later command can reproduce a similar
result. Each command is a declared delivery surface.

## Output validation

JSON outputs should have:

- an object root;
- an explicit content address where the report supports one;
- enum values represented as strings;
- no omitted controls;
- no restricted payloads;
- a stable schema shape.

The CSV output should have one header, sixteen data rows, and the fixed column
order documented in the data dictionary.

## Determinism check

The replay command and depth audit verify deterministic behavior. If runtime
durations change, that is expected. If fixture, execution, lineage, or release
addresses change without an input or code-semantic change, treat it as a
regression.

## Commit gate

Before a substantial build is committed:

- [ ] all intended paths are staged explicitly;
- [ ] unrelated worktree changes remain unstaged;
- [ ] `git diff --cached --check` is clean;
- [ ] added lines contain no authorship or language metadata attributes;
- [ ] focused tests pass;
- [ ] full tests pass;
- [ ] static checks pass for new files;
- [ ] staged insertions meet the build threshold;
- [ ] commit message describes the verified surface.

The public branch is updated only after the local staged review is complete.

## Branch verification

The build branch is pushed for traceability and the same commit is pushed to
`main` so the public repository exercises the Actions workflow. After pushing,
inspect both workflow runs and record their URLs in the handoff.

## Reproducible command set

```powershell
python -m glio_noncode cohort-frontier-data-audit --output d12-data.json
python -m glio_noncode cohort-frontier-contracts --output d12-contracts.json
python -m glio_noncode cohort-frontier-schema --output d12-schema.json
python -m glio_noncode cohort-frontier-evaluate --output d12-evaluation.json
python -m glio_noncode cohort-frontier-replay --output d12-replay.json
python -m glio_noncode cohort-frontier-metrics --output d12-metrics.json
python -m glio_noncode cohort-frontier-lineage --output d12-lineage.json
python -m glio_noncode cohort-frontier-policy --output d12-policy.json
python -m glio_noncode cohort-frontier-quality-gate --output d12-quality.json
python -m glio_noncode cohort-frontier-runtime --output d12-runtime.json
python -m glio_noncode cohort-frontier-bundle --output d12-bundle.json
python -m glio_noncode cohort-frontier-release --output d12-release.json
python -m glio_noncode export-cohort-frontier-review-csv --output d12-review.csv
python -m glio_noncode cohort-frontier-depth-audit --output d12-depth.json
```

The generated files are local verification artifacts. They should not be added
to the repository unless a future fixture policy explicitly requires them.

## CI non-goals

CI does not fetch restricted records, does not make clinical decisions, does not
claim external calibration, and does not replace institutional review. It proves
that the checked-in aggregate boundary remains executable and reproducible.
