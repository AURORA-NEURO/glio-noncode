# Domain 12 C01-C04 evidence depth

This document describes the public aggregate evidence boundary for the cohort
foundation frontier. It is a research-use contract for reproducibility and
review. It does not describe a patient-level workflow.

## Scope

The frontier covers four capability modules:

1. `CohortQueryBuilder` selects exact-context callable variant rows.
2. `LocalBackgroundMutationModel` estimates a descriptive callable-space rate.
3. `SequenceContextControlMatcher` constructs bounded sequence controls.
4. `ChromatinContextControlMatcher` constructs bounded chromatin controls.

The implementation wraps each primitive with the same evidence obligations:

- the input adapter declares required fields and rejects context mismatch;
- the operation contract records positive states, control states, issue codes,
  and prohibited claims;
- the field schema identifies typed inputs and context requirements;
- the evaluator executes both positive and negative-control rows;
- the metrics plane reports operation, state, role, source, and issue counts;
- the lineage graph joins sources, fixture rows, and execution receipts;
- the provenance graph retains versions, input addresses, output addresses,
  and the aggregate boundary;
- the policy plane maps supported output to descriptive publication and maps
  incomplete or foreign output to review or quarantine;
- reconciliation compares declared expected states with observed states;
- the quality gate blocks release when source, schema, evaluation, lineage,
  or reconciliation checks fail;
- replay proves that the same fixture produces the same execution addresses;
- release artifacts, package files, and exports remain content-addressed;
- diagnostics, invariants, traces, and observability expose silent failures;
- recovery, retention, change control, accessibility, and compatibility make
  the handoff operationally inspectable.

## Fixture boundary

The pinned fixture is `cohort-foundation-frontier-public-aggregate` at version
`2026.08.d12-c01-c04.v1`. Its target context is:

`GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment`

The fixture contains five public source receipts and sixteen pseudonymous
aggregate records. Each operation has one positive record and three controls.
The controls include incomplete callability, empty selection, absent matched
controls, missing callable denominators, and foreign-context inputs. The
foreign context is retained as a quarantine test and is never transported into
the target context.

The sources are metadata receipts for public portals. Checked-in values are
aggregate fixture values. The repository does not import patient identifiers,
raw specimens, clinical outcomes, or private access tokens.

## Control taxonomy

| State | Meaning | Publication action |
| --- | --- | --- |
| `supported` | Exact-context input met the declared operation contract | descriptive fields only |
| `partial` | Some requested rows or controls were unavailable | review |
| `absent` | No candidate met the declared selection boundary | review; not negative evidence |
| `abstained` | A required denominator or complete input was unavailable | review |
| `out_of_domain` | Input belonged to the foreign context | quarantine |

The state taxonomy is intentionally descriptive. No state is converted into a
diagnosis, prognosis, clinical risk estimate, significance claim, treatment
recommendation, or causal conclusion.

## Runtime contract

The ordered runtime has thirty-nine stages. The first stages audit data,
register sources, normalize adapters, validate contracts and schema, execute
records, and check integrity. The middle stages calculate metrics, control
coverage, lineage, provenance, policy, traces, reconciliation, invariants,
review, quality, replay, bundle, release, artifacts, package, and diagnostics.
The final stages construct review views, accessibility metadata, depth and
scenario matrices, validation and operational matrices, claim boundaries,
threshold probes, assurance, runbook, query, observability, and recovery.

Each stage has an ordinal, status, output address, and detail string. A runtime
is accepted only when every stage is accepted. A release is ready only when
the quality gate, reconciliation, replay, boundary, and package checks pass.

## Verification commands

```powershell
python -m unittest tests.test_cohort_foundation_frontier -q
python -m unittest tests.test_cohort_foundation_frontier_cli -q
python -m glio_noncode cohort-foundation-frontier-runtime
python -m glio_noncode cohort-foundation-frontier-failure-injections
python -m glio_noncode cohort-foundation-frontier-invariants
python -m glio_noncode cohort-foundation-frontier-summary
```

The focused test package checks fixture closure, adapter rejection,
contract/schema coverage, all sixteen state expectations, metrics, lineage,
provenance, policy, reconciliation, quality, replay, release, artifacts,
diagnostics, thresholds, failure injections, recovery, compatibility,
retention, reproducibility, and export formats.

The full repository test suite remains the authoritative regression gate. The
Actions workflow runs the same frontier commands on every supported Python
matrix entry after installation and compilation.
