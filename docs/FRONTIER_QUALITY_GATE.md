# Frontier quality gate

This document defines the repository-level evidence boundary for the checked-in
frontier slice. The gate is intentionally deterministic and local-first. It
does not claim clinical validity, biological effect, treatment response, or
transportability. It proves that the declared software contracts execute,
retain context and source accounting, and expose review boundaries when a
control fails.

## Scope

The current fixture is `examples/frontier-glioma-case.json`. It is a public
aggregate fixture with reproducibility measurements and no patient-level rows.
The fixture exercises domains D13 through D16:

1. Validation planning and experiment-package controls.
2. Evidence lifecycle, supersession, reproducibility, and signed dossier
   controls.
3. Review workbench, export, search, accessibility, and human-factors
   controls.
4. Privacy, local deployment, federated coordination, and release controls.

The fixture contains four accepted pipeline payloads, ten accepted hardening
operations, and four review-boundary controls. A passing result means the
software returned the expected state for each declared input. It does not mean
that an external reference, institutional policy, wet-lab experiment, or
clinical workflow has been validated.

## Commands

Run the individual receipts when debugging a failure:

```powershell
python -m glio_noncode evaluate-frontier-fixture examples/frontier-glioma-case.json
python -m glio_noncode audit-frontier-data examples/frontier-glioma-case.json
python -m glio_noncode replay-frontier-fixtures examples/frontier-glioma-case.json `
  --required-context-key "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
python -m glio_noncode frontier-contracts
python -m glio_noncode evaluate-frontier-scenarios examples/frontier-glioma-case.json
```

Run the combined gate used by CI:

```powershell
python -m glio_noncode frontier-quality-gate `
  examples/frontier-glioma-case.json `
  --output frontier-quality-report.json
```

The command exits with status zero only when every required check passes. A
failed contract is serialized to the output path before the command exits with
status two, so local triage can inspect the exact failed IDs.

## Fixture contract

The top-level fixture must contain:

| Field | Requirement |
| --- | --- |
| `fixture_id` | Stable non-empty identity for replay and duplicate detection. |
| `fixture_version` | `frontier-fixture-v1`. |
| `provenance` | Source class, license, evidence boundary, data-scope flags, and numeric-value declaration. |
| `source_receipts` | At least one public source receipt with an identifier and context. |
| `context` | Six exact dimensions: genome build, disease class, age group, cell state, territory, and treatment phase. |
| `pipelines` | Validation, evidence, workbench, and deployment payloads. |
| `hardening` | Every operation in the ten-operation hardening inventory. |
| `negative_controls` | Review cases with expected state and blocked-stage IDs. |

The context dimensions are joined into one context key. The key is carried into
every operation call and receipt. A changed cell state or treatment phase is a
different evidence context, even if all other fields match.

## Component receipts

The quality gate composes five receipts. Each component remains available in
the report so a failure is attributable to a concrete boundary.

### Fixture evaluation

The fixture evaluator runs the four pipelines, all release operation adapters,
all hardening operations, and all negative controls. The current evidence floor
is 49 checks. The evaluator records accepted and review states, stage IDs,
operation outputs, and a content address. Signing material is consumed by the
operation but is not copied into the serialized result.

### Public-data audit

The public-data boundary indexes declared aggregate records and source
receipts. It checks duplicate record IDs, unknown source IDs, context mismatch,
patient-level flags, sensitive field paths, and empty catalogs. The report
retains paths and issue codes, never raw sensitive values.

### Replay integrity

Replay verifies the fixture ID, exact context key, source set, accepted state,
and minimum check count. Batch replay additionally rejects duplicate fixture
identities and mixed contexts unless a caller explicitly allows a mixed batch.
This prevents a locally passing case from being replaced by a different case
with the same filename.

### Scenario matrix

The scenario matrix derives four positive scenarios from the pipeline payloads
and one review scenario from each negative control. Positive scenarios must be
accepted with no blocked stages. Review scenarios must remain in review and
must include every declared blocked stage. The result makes state transitions
visible independently from the aggregate fixture check list.

### Operation registry

The declarative registry contains 79 operation contracts:

| Family | Count | Contract role |
| --- | ---: | --- |
| Data | 16 | Record normalization and intake boundaries. |
| Context | 16 | Context-aware interpretation boundaries. |
| Inference | 16 | Evidence and relationship boundaries. |
| Release | 17 | D13-D16 executable release operations. |
| Hardening | 10 | Safety, privacy, and deployment checks. |
| End-to-end | 4 | Pipeline orchestration contracts. |

The release family has 17 operations and 16 capability IDs because signed
dossier publication and verification are separate operations in one lifecycle
capability. The registry is an inventory and contract surface; its presence
does not promote untested capabilities to verified status.

## Required gate checks

The combined report currently has twelve checks:

1. Fixture evaluation is accepted.
2. The fixture retains at least 49 checks.
3. Public-data audit is accepted.
4. Replay has no identity, context, source, or state issues.
5. The scenario matrix is accepted.
6. Exactly four review scenarios remain visible.
7. The operation registry has 79 contracts.
8. The registry maps 16 release capability IDs.
9. Fixture, data, replay, and scenario receipts share one context key.
10. Fixture, data, and replay receipts share one source set.
11. Repeated evaluation produces the same content address.
12. Serialized evaluation output contains no signing secret.

The count is deliberately explicit. Adding or removing a gate requires a test,
an updated runbook, and a change to the quality-gate implementation so the
evidence boundary cannot drift silently.

## Failure triage

Start with the failed check IDs, then run the corresponding component command.

| Failed ID | First diagnostic |
| --- | --- |
| `fixture-evaluation` | Inspect the evaluator `failed_check_ids` and pipeline stage receipts. |
| `fixture-check-floor` | Confirm no pipeline, hardening operation, or negative control was removed. |
| `public-data-audit` | Inspect `issues`, `context_mismatch_ids`, and `sensitive_paths`. |
| `replay-integrity` | Run replay with the fixture context key and compare source IDs. |
| `scenario-matrix` | Inspect the failed scenario and its observed blocked stages. |
| `scenario-review-floor` | Confirm all four negative controls are declared and still review. |
| `contract-count` | Run `frontier-contracts` and inspect family counts. |
| `capability-count` | Check release capability mapping in the registry. |
| `context-consistency` | Compare the six fixture dimensions and every component context key. |
| `source-consistency` | Compare source receipt IDs and ordering across reports. |
| `deterministic-evaluation` | Check for unordered iteration, timestamps, or non-addressed output. |
| `secret-output-boundary` | Inspect operation serializers and remove input-only secret fields from output. |

Do not repair a failed review control by changing its expected state to
accepted. A review control is part of the contract and should fail loudly if a
stage that should block execution no longer blocks it.

## CI procedure

GitHub Actions installs the package without optional dependencies, compiles the
source and tests, runs the complete unittest suite, and executes each frontier
command. The combined quality report is written to the runner temporary
directory. A pull request or push is not considered green if a component command
passes while the combined gate fails.

For a local reproduction of the CI order:

```powershell
python -m compileall -q src tests
python -m unittest discover -s tests -t . -q
python -m glio_noncode evaluate-frontier-fixture examples/frontier-glioma-case.json
python -m glio_noncode audit-frontier-data examples/frontier-glioma-case.json
python -m glio_noncode replay-frontier-fixtures examples/frontier-glioma-case.json
python -m glio_noncode frontier-contracts
python -m glio_noncode evaluate-frontier-scenarios examples/frontier-glioma-case.json
python -m glio_noncode frontier-quality-gate examples/frontier-glioma-case.json
```

## Promotion rule

A capability is promoted to `verified` only when its executable path, targeted
tests, fixture receipt, and CI command all agree. The current ledger therefore
reports 19 verified capabilities and 237 partial capabilities out of 256
started capabilities. The 19 verified entries are a bounded software-evidence
slice, not a claim that the whole product is complete.

Future fixture additions should preserve the same rules: public or aggregate
data only, explicit source receipts, exact context, deterministic output,
negative controls, and a written evidence boundary. New external datasets may
extend coverage, but they must not be substituted for the repository's own
contract and replay checks.
