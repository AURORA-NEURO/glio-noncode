# Workspace Gamma Frontier Release Notes

## Release unit

The C09–C12 release unit is `workspace-gamma-frontier-c09-c12`. It packages
four public research-workspace surfaces and their evidence. The package is
research-use only and is not a clinical release.

## Included modules

| Module | Responsibility |
| --- | --- |
| `public_data` | fixture rows, source receipts, data audit |
| `contracts` | operation inputs, outputs, states, issues, review questions |
| `schema` | field types, requiredness, allowed values, output order |
| `fixture_eval` | primitive execution and expected-state checks |
| `projection_assertions` | serialized shape and boundary assertions |
| `metrics` | transparent counts and ratios |
| `lineage` | source-to-output graph |
| `policy` | ordered release, review, and hold routing |
| `reconciliation` | expected-versus-observed comparison |
| `quality_gate` | blocking and advisory release checks |
| `replay` | stable repeated evaluation addresses |
| `runtime` | ordered runtime rehearsal |
| `observability` | stage and row events |
| `views` | sanitized review table and source matrix |
| `review_queue` | prioritized issue routing |
| `release` | release state and evidence address manifest |
| `bundle` | address-only research-use package |
| `artifacts` | kind, retention, and sensitivity inventory |
| `accessibility` | labels, state visibility, navigation checks |
| `compliance` | aggregate boundary and secret-surface checks |
| `checks` | cross-record invariants |
| `adapters` | mapping, JSON, and table transport declarations |
| `scenario_matrix` | twenty declared scenarios |
| `thresholds` | operational bound profiles and probes |
| `validation_matrix` | twenty-eight operation-by-axis cases |
| `runbook` | fourteen-step operational sequence |
| `exports` | canonical JSON, manifest, and CSV |
| `pipeline` | end-to-end integration |

## Versioning

Fixture and schema version: `2026.08.d15.c09-c12.v1`.

All content addresses are recalculated from canonical values. A change to an
operation input, output, source receipt, issue code, policy rule, or release
check is a compatibility event and should receive a new version.

## Release states

`ready` means all blocking checks pass and no advisory check remains unresolved.
`review` means required checks pass but an advisory review remains.
`blocked` means at least one blocking check failed.

The default fixture is expected to produce `ready`.

## Evidence address set

The pipeline exposes sixteen named addresses:

```text
runtime
replay
release
bundle
artifacts
review_view
review_queue
observability
accessibility
boundary
invariants
scenarios
thresholds
validation
runbook
adapters
```

The compact manifest additionally records fixture ID, metrics address, bundle
address, release address, release state, entry count, metric count, and public
boundary.

## Promotion procedure

1. Run `gamma-frontier-pipeline` on the default fixture.
2. Confirm the report is accepted.
3. Inspect the release check list.
4. Inspect the review queue and retained controls.
5. Export JSON and CSV from the same pipeline view.
6. Run focused tests.
7. Run the full repository test suite.
8. Run static checks and staged-line metadata scan.
9. Commit a substantial build.
10. Push the exact commit to `main` and verify Actions.

## Non-goals

This package does not:

- execute notebooks or SDK commands;
- issue credentials;
- establish public-key identity;
- infer missing permissions;
- convert a review state into scientific validation;
- expose secret values in compact outputs;
- treat a control row as an absent row;
- replace external institutional controls.

## Changelog entry

The C09–C12 build adds a fresh aggregate fixture, four primitive integrations,
twenty-eight supporting modules, a complete pipeline, a CLI family, focused
tests, and public operational documentation. The package is intentionally
separate from the earlier C01–C08 projection packages while sharing only the
repository's canonical serialization and bounded workspace primitives.
