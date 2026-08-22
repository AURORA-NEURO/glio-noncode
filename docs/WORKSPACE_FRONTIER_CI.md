# Workspace frontier CI

## Workflow coverage

The standard CI workflow runs the workspace frontier commands in every Python
matrix lane. The commands use the default public aggregate fixture unless a
future checked-in input path is provided.

## Command matrix

| Command | Output | Gate |
| --- | --- | --- |
| `workspace-frontier-data-audit` | data audit | accepted |
| `workspace-frontier-contracts` | contract registry | four contracts |
| `workspace-frontier-schema` | schema manifest | four operations |
| `workspace-frontier-evaluate` | evaluation | 120 checks |
| `workspace-frontier-replay` | replay receipt | stable |
| `workspace-frontier-metrics` | metrics | 13 metrics |
| `workspace-frontier-lineage` | lineage graph | acyclic, 36 edges |
| `workspace-frontier-policy` | policy and decisions | 16 decisions |
| `workspace-frontier-quality-gate` | quality gate | 14 checks |
| `workspace-frontier-runtime` | runtime report | eight stages |
| `workspace-frontier-observability` | event report | 24 events |
| `workspace-frontier-artifacts` | artifact inventory | seven artifacts |
| `workspace-frontier-bundle` | release bundle | accepted |
| `workspace-frontier-release` | release manifest | ready |
| `workspace-frontier-review-queue` | review queue | 16 rows |
| `export-workspace-frontier-review-csv` | CSV review rows | 17 lines |
| `workspace-frontier-depth-audit` | depth audit | 21 checks |
| `workspace-frontier-adapters` | adapter registry | four adapters |
| `workspace-frontier-scenarios` | scenario matrix | 33 scenarios |
| `workspace-frontier-thresholds` | threshold report | 972 probes |
| `workspace-frontier-invariants` | invariant report | accepted |

## Matrix expectations

Every Python lane must pass the focused frontier tests and the full repository
suite. The commands are deliberately repeated in each lane so a serialization,
enum, parser, or path difference cannot hide behind one interpreter version.

The expected matrix is:

| Runtime | Unit suite | CLI matrix | Expected |
| --- | --- | --- | --- |
| Python 3.11 | pass | pass | green |
| Python 3.12 | pass | pass | green |
| Python 3.13 | pass | pass | green |

## Local CI reproduction

Run the focused command matrix with:

```powershell
$commands = @(
  "workspace-frontier-data-audit",
  "workspace-frontier-contracts",
  "workspace-frontier-schema",
  "workspace-frontier-evaluate",
  "workspace-frontier-replay",
  "workspace-frontier-metrics",
  "workspace-frontier-lineage",
  "workspace-frontier-policy",
  "workspace-frontier-quality-gate",
  "workspace-frontier-runtime",
  "workspace-frontier-observability",
  "workspace-frontier-artifacts",
  "workspace-frontier-bundle",
  "workspace-frontier-release",
  "workspace-frontier-review-queue",
  "workspace-frontier-depth-audit",
  "workspace-frontier-adapters",
  "workspace-frontier-scenarios",
  "workspace-frontier-thresholds",
  "workspace-frontier-invariants"
)
foreach ($command in $commands) {
  python -m glio_noncode $command --output "/tmp/$command.json"
}
```

On Windows, replace `/tmp` with a task-scoped temporary directory. The command
outputs are disposable verification artifacts and do not belong in the source
tree.

## Test commands

Focused tests:

```powershell
python -m pytest -q tests/test_workspace_frontier_evidence.py tests/test_workspace_frontier_depth.py tests/test_workspace_frontier_evidence_cli.py
```

Targeted lint:

```powershell
python -m ruff check --ignore E501 src/glio_noncode/workspace_frontier_*.py tests/test_workspace_frontier_*.py
```

CLI compile:

```powershell
python -m py_compile src/glio_noncode/cli.py
```

The repository has older lint findings outside this frontier. The targeted
command is the relevant new-code signal; full test execution remains required.

## Failure handling

If a matrix command exits nonzero:

1. capture the command and interpreter version;
2. inspect standard error;
3. run the corresponding focused test;
4. compare the generated JSON to the expected counts;
5. check content-address drift;
6. fix the smallest typed boundary;
7. rerun the matrix locally;
8. push only after the local full suite passes.

Do not mark a lane successful by skipping a command. Do not turn a control row
into a positive row to make a count pass.

## Artifact retention

CI output files are intentionally written to a temporary directory. The
release evidence retained in source control is the fixture, typed modules,
tests, registry entry, docs, and workflow command. A future artifact-upload
step may preserve JSON and CSV files for a run, but it must not change the
deterministic address inputs.

## Pull request evidence

A frontier build handoff should include:

- focused test count;
- full test count;
- warning count and whether warnings predate the build;
- lint command and scope;
- CLI compile result;
- data audit result;
- evaluation check count;
- quality gate count;
- runtime stage count;
- release state;
- exact commit ID;
- both Actions run URLs.

## Versioning

Changing the fixture payload requires a fixture version decision. Changing a
field contract requires a schema version decision. Changing only docs or CLI
help may keep the fixture version while still requiring the focused suite.

Changing an issue code, state value, context key, or deterministic ordering is
a compatibility change and must be called out in the release notes.
