# Domain 13 planning operation handbook

This handbook describes the four operations from typed input to review output.
The implementation keeps the underlying planning objects intact and adds
fixture-level state, issue, lineage, policy, and release surfaces.

## Shared execution path

Every record follows the same path:

1. identify operation and role;
2. verify record context;
3. validate operation payload;
4. build the typed planning object;
5. invoke the existing planning primitive;
6. normalize state and issue codes;
7. calculate an execution address;
8. compare expected and observed values;
9. include the row in release surfaces.

The fixture is read-only. The execution object is separate from the expected
record so reconciliation can expose a regression.

## C01 evidence-gap analysis

### Purpose

Evidence-gap analysis turns declared missing evidence, contradiction, and high
uncertainty into ranked planning gaps. It does not invent evidence or convert a
proxy score into a posterior.

### Positive path

`C01-POS-001` has one missing measurement channel and uncertainty of 0.8. The
result is `partial` and retains two gaps. The missing measurement has an impact
of 0.85. The uncertainty gap retains measurement and negative-control channels.
Priority order is sorted by impact and stable gap ID.

### Context control

`C01-CTRL-001` contains a hypothesis whose context differs from the fixture.
The wrapper emits `context_mismatch` and sets state `invalid`. A context that is
close in wording is still out of the declared planning scope.

### Typed-input control

`C01-CTRL-002` has no hypothesis object. It emits
`invalid_evidence_gap_input`. The evaluator does not create an empty hypothesis
to keep the pipeline moving.

### Complete-snapshot control

`C01-CTRL-003` has a supported hypothesis with no missing evidence and low
uncertainty. The primitive returns `ready_for_review`; the fixture marks this as
`complete_hypothesis_control` because it is a control for the gap boundary. A
complete snapshot is useful as a control even though it has no gap.

### Review questions

- Are missing channels named?
- Are impacts retained?
- Is uncertainty distinct from missing evidence?
- Are available channels sorted and visible?
- Is the exact context preserved?
- Is the limitation that this is planning output visible?

## C02 assay eligibility

### Purpose

Eligibility routing compares declared constraints to an assay inventory. It
reports routes and blockers rather than guessing a suitable model.

### Positive path

`C02-POS-001` matches `neural_model`, insert bounds 4–12, two controls, and two
readouts. The route is `ready_for_review` and retains all four satisfied
constraints. Feasibility remains the inventory value of 0.8.

### Model control

`C02-CTRL-001` supplies an inventory with `other_model`. The route is blocked
and emits `model_system_not_available`. Alternatives and sensitivity remain in
the output.

### Control and readout control

`C02-CTRL-002` supplies only a negative control and barcode readout. It emits
both `missing_controls` and `missing_readouts`. These issues remain separate so
the route reviewer knows which inventory dimensions are incomplete.

### Empty inventory control

`C02-CTRL-003` requests STARR-seq with an empty inventory. The router abstains
and emits `assay_not_present_in_inventory`. Abstention is not a claim that the
assay is unsuitable in general.

### Review questions

- Is model support declared rather than inferred?
- Do insert bounds overlap the requested range?
- Are controls and readouts checked independently?
- Are alternatives retained?
- Does empty inventory abstain?

## C03 MPRA planning

### Purpose

MPRA planning creates bounded reference and alternate constructs for a target
under context, insert, and construct limits.

### Positive path

`C03-POS-001` has an eight-base target, reference allele G, and alternate T.
The package is `ready_for_review` and has exactly two constructs. Both constructs
retain target ID, assay, context, source ID, and allele label.

### Context control

`C03-CTRL-001` supplies a pediatric target to an adult context constraint. The
planner retains the target ID in the blocker and emits `context_mismatch`.

### Budget control

`C03-CTRL-002` allows one construct while the paired-allele requirement creates
two. The package is blocked with `max_constructs_exceeded`. The pair is retained
for review rather than truncated silently.

### Empty-target control

`C03-CTRL-003` has no targets and emits `no_validation_targets`. An empty package
is not a ready experiment.

### Review questions

- Is the reference allele checked against the sequence?
- Is the alternate sequence retained?
- Are both allele constructs paired?
- Is the construct budget visible?
- Are controls and readouts present?
- Are synthesis and efficacy limitations visible?

## C04 STARR-seq planning

### Purpose

STARR-seq planning shares the allele-aware target contract while retaining its
assay identity. It produces a review package, not an expression claim.

### Positive path

`C04-POS-001` produces two constructs with `starr_seq` assay identity. The
package retains controls, readouts, limitations, and exact context.

### Context control

`C04-CTRL-001` supplies a pediatric target and is blocked with
`context_mismatch`. The mismatch is not normalized away.

### Insert control

`C04-CTRL-002` sets a maximum insert length of six for an eight-base target. It
is blocked with `insert_length`. The target remains in the package target list
and the blocker names the target.

### Empty-target control

`C04-CTRL-003` emits `no_validation_targets`. The package cannot be ready without
a target.

### Review questions

- Is assay identity STARR-seq?
- Are target and construct sequences retained?
- Is insert length checked before construct creation?
- Are controls and readouts visible?
- Is the package marked as planning only?

## Cross-operation accounting

| Operation | Positive | Controls | Total |
| --- | ---: | ---: | ---: |
| evidence gap | 1 | 3 | 4 |
| assay eligibility | 1 | 3 | 4 |
| MPRA planning | 1 | 3 | 4 |
| STARR-seq planning | 1 | 3 | 4 |

The evaluator produces seven checks per record and eight global checks:

```text
16 records × 7 checks = 112 record checks
112 record checks + 8 global checks = 120 checks
```

## State and issue accounting

Positive records must have no issue codes and accepted true. Controls must have
their expected sorted issue codes and accepted false. A control can be a valid
primitive result while still being a negative fixture because its role is part
of the contract.

## Metrics

The default report has 13 rows covering overall checks, positive acceptance,
control rejection, accepted execution rate, state rates, issue visibility, and
one row for each operation. Metrics describe the fixture and pipeline. They are
not population estimates or assay performance claims.

## Lineage

The default graph has 20 source-to-execution edges and 16 fixture-to-execution
edges. Positive rows cite two sources and controls cite one, giving 36 edges.
All sixteen execution addresses are terminals, including blocked and invalid
rows.

## Release order

Use this command order for handoff:

1. data audit;
2. contracts;
3. schema;
4. evaluation;
5. replay;
6. metrics;
7. lineage;
8. policy;
9. quality gate;
10. runtime;
11. bundle;
12. artifacts;
13. observability;
14. release;
15. review CSV;
16. depth audit.

The release manifest is suitable for the allowed planning uses only after all
control rows and excluded uses have been inspected.

## Maintainer checklist

- [ ] C01 has missing, mismatch, invalid, and complete controls.
- [ ] C02 has model, control, readout, and inventory controls.
- [ ] C03 has context, budget, and empty-target controls.
- [ ] C04 has context, insert, and empty-target controls.
- [ ] Every issue is declared.
- [ ] Every record has an address.
- [ ] Every record has lineage.
- [ ] Every control appears in CSV.
- [ ] Every package retains limitations.
