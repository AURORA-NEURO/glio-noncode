# Domain 13 validation-planning evidence gate

This document defines the bounded release gate for evidence-gap and reporter
assay planning. The surface organizes typed planning inputs, identifies blockers,
and preserves controls. It does not assert assay efficacy, safety, causality,
clinical validity, or suitability for an individual.

## Scope

The gate covers four operations:

1. evidence-gap analysis for a regulatory hypothesis;
2. assay eligibility routing against an inventory;
3. MPRA reference and alternate construct planning;
4. STARR-seq reference and alternate construct planning.

Each operation has one positive record and three controls. The positive record
shows the intended planning path. Controls exercise context mismatch, missing
typed input, absent inventory, missing controls, insert bounds, construct
budget, and empty targets.

## Public boundary

The fixture is public aggregate planning evidence. It has five HTTPS source
receipts and sixteen typed records. It has no patient-level input, no restricted
sample row, and no clinical outcome.

The exact context key is:

```text
GRCh38|glioma|adult|stem_like|core|unknown
```

The evidence boundary token is:

```text
public_aggregate_non_patient
```

The token is required in fixture, gate, bundle, release, and export surfaces.
Changing it is a boundary change and requires a new fixture version.

## Positive records

| ID | Operation | Expected state | Evidence |
| --- | --- | --- | --- |
| C01-POS-001 | evidence gap | partial | missing measurement and high uncertainty |
| C02-POS-001 | assay eligibility | ready_for_review | model, bounds, controls, readouts |
| C03-POS-001 | MPRA planning | ready_for_review | paired allele constructs |
| C04-POS-001 | STARR-seq planning | ready_for_review | paired allele constructs |

The partial state for C01 is intentional. A gap analysis that accurately
retains missing evidence is an accepted planning result even though the
hypothesis is not complete.

## Control records

| ID | Boundary | Expected issue |
| --- | --- | --- |
| C01-CTRL-001 | hypothesis context mismatch | context_mismatch |
| C01-CTRL-002 | missing hypothesis | invalid_evidence_gap_input |
| C01-CTRL-003 | complete snapshot control | complete_hypothesis_control |
| C02-CTRL-001 | model mismatch | model_system_not_available |
| C02-CTRL-002 | missing controls and readouts | missing_controls, missing_readouts |
| C02-CTRL-003 | empty inventory | assay_not_present_in_inventory |
| C03-CTRL-001 | target context mismatch | context_mismatch |
| C03-CTRL-002 | construct budget | max_constructs_exceeded |
| C03-CTRL-003 | empty target list | no_validation_targets |
| C04-CTRL-001 | target context mismatch | context_mismatch |
| C04-CTRL-002 | insert bound | insert_length |
| C04-CTRL-003 | empty target list | no_validation_targets |

Controls remain visible in evaluation, reconciliation, lineage, observability,
and review CSV output. They are not discarded because they are blocked.

## State semantics

`partial` means a gap analysis retained unresolved requirements. `ready_for_review`
means the route or package satisfied the declared planning constraints.
`blocked` means a required planning constraint was not met. `abstained` means
the operation could not identify a route from the supplied inventory.
`invalid` means the typed input could not be evaluated under the operation
contract.

None of these states means that an experiment will succeed. A ready package is
a review artifact with controls and limitations.

## Gate sequence

The release sequence is:

1. load the public fixture;
2. audit sources, records, operations, and contexts;
3. load four operation contracts;
4. load four operation schemas;
5. execute all sixteen records;
6. calculate descriptive metrics;
7. apply policy to positive planning paths;
8. build source and fixture lineage;
9. reconcile expected and observed states;
10. evaluate twelve blocking checks;
11. assemble a release bundle;
12. replay the evaluation;
13. build the release manifest;
14. export the complete review view.

The runtime implements the first ten stages and bundle assembly as ten ordered
stages. Replay and release checks are added by the release command.

## Blocking checks

The quality gate contains twelve blocking checks:

| Check | Required result |
| --- | --- |
| data-audit | source and fixture audit accepted |
| evaluation | all 120 evaluation checks pass |
| contract-coverage | four contracts present |
| schema-coverage | four schemas present |
| lineage-acyclic | no lineage cycle |
| lineage-terminals | sixteen record terminals |
| reconciliation | no mismatched records |
| addresses | every execution addressed |
| boundary | exact public boundary token |
| positive-count | four positive records |
| control-count | twelve controls |
| issue-vocabulary | all issues declared |

Every check retains observed, required, and rationale fields. A failed check is
therefore a review object rather than an opaque release boolean.

## Planning policy

Positive planning paths may be released for review when their execution is
accepted. C01 uses an allow-planning-review decision. C02 uses an allow-route-
review decision. C03 and C04 use allow-planning-review decisions. Controls do
not become positive because their issues are expected; their negative role is
part of the evidence boundary.

The allowed uses are:

- assay planning review;
- method development;
- reproducibility testing;
- research triage.

The excluded uses are:

- patient care;
- diagnosis;
- prognosis;
- treatment selection;
- individual risk;
- clinical validation claims.

## Construct boundary

MPRA and STARR-seq packages retain reference and alternate constructs. The
construct pair is not a prediction of expression, effect, or clinical response.
Sequence identity, synthesis, cloning, cell model, readout, randomization, and
batch controls require review beyond this repository.

## Review procedure

When the gate passes:

1. verify the exact context and boundary token;
2. inspect the five source receipts;
3. inspect the C01 gaps and priority order;
4. inspect C02 satisfied constraints and alternatives;
5. inspect the C03 and C04 construct pairs;
6. inspect every control issue;
7. inspect policy and excluded uses;
8. compare replay addresses;
9. retain the depth audit with the release.

When the gate fails, retain the failed output and check IDs. Do not replace a
failed fixture with a new default run without versioning the change.

## CLI commands

```powershell
glio-noncode validation-frontier-data-audit --output data.json
glio-noncode validation-frontier-contracts --output contracts.json
glio-noncode validation-frontier-schema --output schema.json
glio-noncode validation-frontier-evaluate --output evaluation.json
glio-noncode validation-frontier-replay --output replay.json
glio-noncode validation-frontier-quality-gate --output quality.json
glio-noncode validation-frontier-runtime --output runtime.json
glio-noncode validation-frontier-release --output release.json
glio-noncode validation-frontier-depth-audit --output depth.json
```

## Review checklist

- [ ] Five public source receipts are present.
- [ ] Sixteen records are present.
- [ ] Four positive records are present.
- [ ] Twelve controls are present.
- [ ] C01 retains two gaps.
- [ ] C02 retains satisfied constraints or blockers.
- [ ] C03 retains two allele constructs.
- [ ] C04 retains two allele constructs.
- [ ] Evaluation has 120 passing checks.
- [ ] Quality gate has 12 passing checks.
- [ ] Runtime has 10 ordered stages.
- [ ] Replay has no drift.
- [ ] Release state is ready.
- [ ] Allowed and excluded uses are visible.
- [ ] Review CSV has 17 lines.

## Non-goals

The gate is not a laboratory protocol, a statistical power guarantee, an
efficacy estimate, a safety determination, a causal conclusion, or a clinical
validation decision. It is a reproducible planning boundary for public
aggregate evidence.
