# Domain 12 cohort frontier evidence gate

This document defines the release boundary for the cohort convergence frontier.
It is intentionally narrower than a scientific conclusion. The implementation
can organize public aggregate evidence, expose control behavior, and make
replays reproducible. It cannot turn a bounded fixture into patient care,
diagnosis, prognosis, treatment selection, or an individual risk estimate.

## Scope

The gate covers four operations:

1. subgroup fairness stratification;
2. feature transportability review;
3. federated aggregate summary;
4. aggregate cohort discovery publication.

Each operation is exercised with one positive record and three control records.
The positive record demonstrates the intended path. The controls demonstrate a
specific boundary that must remain visible. A passing gate therefore means that
the implementation correctly distinguishes supported, review, invalid, and
published states. It does not mean that every record is supported.

## Evidence boundary

The fixture is public aggregate evidence. It carries five source receipts and
sixteen records. The record body contains declared counts, features, context,
and issue expectations. It does not contain a patient identifier, a raw sample,
a protected row, or a clinical outcome.

The exact context key is:

```text
GRCh38|glioma|adult|stem_like|core|unknown
```

The boundary token is:

```text
public_aggregate_non_patient
```

The boundary token is required in the fixture, release manifest, and exported
review surfaces. A caller that changes the token must fail the quality gate.

## Positive records

The positive records are:

| ID | Operation | Expected state | Purpose |
| --- | --- | --- | --- |
| C13-POS-001 | subgroup fairness | supported | balanced group rates |
| C14-POS-001 | transportability | supported | complete overlap and bounded shift |
| C15-POS-001 | federated summary | supported | site counts above privacy floor |
| C16-POS-001 | cohort discovery | published | aggregate feature manifest |

The positive records are not a claim that the methods are calibrated. They are
stable contract examples used to keep serialization, replay, and release logic
executable.

## Control records

The controls are deliberately non-accepted:

| ID | Boundary | Expected issue |
| --- | --- | --- |
| C13-CTRL-001 | high parity gap | parity_gap_high |
| C13-CTRL-002 | empty input | empty_fairness_input |
| C13-CTRL-003 | missing group field | invalid_fairness_input |
| C14-CTRL-001 | target feature gap | target_feature_gap |
| C14-CTRL-002 | distribution shift | distribution_shift_high |
| C14-CTRL-003 | empty input | empty_transportability_input |
| C15-CTRL-001 | privacy floor | privacy_floor_violation |
| C15-CTRL-002 | empty input | empty_federated_input |
| C15-CTRL-003 | malformed mean | invalid_federated_input |
| C16-CTRL-001 | context mismatch | invalid_cohort_discovery_input |
| C16-CTRL-002 | empty input | empty_cohort_discovery_input |
| C16-CTRL-003 | empty analysis set | invalid_cohort_discovery_input |

Controls must remain in the fixture. Removing them would make the release
surface less informative, because a positive-only test cannot show that a
review boundary is enforced.

## Gate sequence

The gate is evaluated after the following sequence:

1. load the fixture or the default public aggregate;
2. audit source receipts and record structure;
3. load the four operation contracts;
4. load the four operation schemas;
5. execute all sixteen records;
6. calculate metrics from the execution report;
7. apply the research-use policy;
8. construct source and fixture lineage;
9. reconcile expected and observed states;
10. evaluate twelve blocking checks;
11. assemble the release bundle;
12. replay the fixture and compare receipts;
13. construct the release manifest;
14. publish review rows and aggregate exports.

The runtime module implements the first ten steps and bundle assembly as ten
ordered stages. The release command adds replay and release-manifest checks.

## Blocking checks

The twelve checks are:

| Check | Required observation |
| --- | --- |
| data-audit | all source and fixture checks pass |
| evaluation | all expected checks pass |
| contract-coverage | four operations are declared |
| schema-coverage | four schemas are declared |
| lineage-acyclic | the graph has no cycle |
| lineage-terminals | every record has a terminal address |
| reconciliation | expected and observed receipts match |
| addresses | every execution has a content address |
| boundary | the public aggregate token is exact |
| positive-count | one positive record per operation |
| control-count | three controls per operation |
| issue-vocabulary | all issue codes are declared |

The gate stores observed and required values for every row. This makes a failed
check useful for review and avoids a single undifferentiated boolean.

## State rules

` supported ` means the operation accepted the record under the declared
thresholds. ` review ` means the operation completed but a declared gap or shift
requires review. ` invalid ` means the payload cannot satisfy the operation
contract. ` published ` means an aggregate discovery manifest passed the bounded
publication checks.

No state is upgraded because a control is inconvenient. No control is omitted
from the review view because it is invalid. Invalid payloads are part of the
contract surface and must retain their issue code.

## Policy rules

The policy evaluates positive paths for release readiness. Controls remain in
the evaluation and review surfaces but do not poison a release candidate when
they match their expected issue. The four positive decisions are:

| Operation | Decision | Publication posture |
| --- | --- | --- |
| subgroup fairness | allow review | aggregate method review |
| transportability | allow review | aggregate method review |
| federated summary | allow review | privacy-bounded review |
| cohort discovery | allow publication | manifest-only publication |

`allow publication` refers to the aggregate manifest. It does not authorize a
clinical or operational use outside the excluded-use list.

## Release uses

The manifest may be used for:

- aggregate cohort review;
- method development;
- reproducibility testing;
- research triage.

The manifest excludes:

- patient care;
- diagnosis;
- prognosis;
- treatment selection;
- individual risk;
- clinical cohort claims.

The same allowed and excluded uses are retained in JSON, canonical JSON, and
the release manifest. A downstream consumer must not infer a broader use from
the word `published`.

## Review procedure

When the gate passes, review the following in order:

1. confirm the boundary token and exact context;
2. confirm all five source receipts are HTTPS and non-patient;
3. inspect the four positive execution rows;
4. inspect every control issue code;
5. inspect the policy decision for each operation;
6. inspect lineage terminals and content addresses;
7. compare the replay receipt;
8. verify the excluded-use list before distribution.

When the gate fails, retain the failed manifest and the failed check IDs. Do
not replace a failed result with a newly generated fixture without recording
the input change. A changed fixture is a new evidence version.

## CLI gate commands

```powershell
glio-noncode cohort-frontier-data-audit --output data-audit.json
glio-noncode cohort-frontier-evaluate --output evaluation.json
glio-noncode cohort-frontier-quality-gate --output quality.json
glio-noncode cohort-frontier-runtime --output runtime.json
glio-noncode cohort-frontier-release --output release.json
glio-noncode cohort-frontier-depth-audit --output depth.json
```

The commands use the deterministic public aggregate when no input path is
provided. A caller fixture can be supplied as the positional input. The loader
requires all source and record sections and validates their typed fields.

## Review checklist

- [ ] The fixture version is recorded.
- [ ] The context key is exact.
- [ ] The boundary token is exact.
- [ ] Five source receipts are present.
- [ ] Sixteen records are present.
- [ ] Four positive records are present.
- [ ] Twelve controls are present.
- [ ] The evaluation has 120 passing checks.
- [ ] The quality gate has 12 passing checks.
- [ ] The runtime has 10 ordered stages.
- [ ] Replay reports no drift.
- [ ] The release state is `ready`.
- [ ] Allowed uses and excluded uses are present.
- [ ] The review CSV has 17 lines including its header.

## Versioning

The fixture version, schema version, and release version are explicit strings.
Change any of them when record semantics, issue vocabulary, thresholds, or
output fields change. A code-only refactor that preserves canonical output may
reuse the version, but the replay test must prove that the addresses remain
stable.

## Non-goals

This gate does not estimate prevalence, establish causality, calibrate a risk
model, validate a clinical endpoint, or authorize access to restricted data. It
does not replace institutional review, data-use agreements, privacy review, or
domain adjudication. Its purpose is to make a narrow aggregate computation
reproducible and its limitations inspectable.
