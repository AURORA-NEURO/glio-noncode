# Domain 13 planning review playbook

Use this playbook to review one run, compare two versions, or prepare a
planning bundle for aggregate research review.

## Establish identity

Capture fixture ID, fixture version, schema version, context key, boundary token,
run ID, release ID, and content addresses. If context or fixture version differs,
do not compare the reports as one run.

## Verify sources

The default fixture has five public HTTPS receipts. Confirm each source has an
ID, title, URI, access note, and address. Confirm that every source is referenced
by at least one record. Source receipts identify provenance and do not imply
restricted data access.

## Verify record balance

Confirm sixteen records: one positive and three controls for each operation.
Controls must be present before evaluation. A positive-only report cannot show
that blockers are enforced.

## Review C01

1. Read the two positive gaps.
2. Confirm missing measurement and uncertainty are separate.
3. Inspect priority order.
4. Confirm context mismatch becomes invalid.
5. Confirm missing hypothesis becomes invalid.
6. Confirm complete snapshot control remains labeled.

The gap report is a planning inventory. It does not prove that adding one of the
listed channels will resolve the hypothesis.

## Review C02

1. Confirm the positive model system matches.
2. Confirm insert bounds are satisfied.
3. Confirm both required controls are satisfied.
4. Confirm both readouts are satisfied.
5. Inspect the model mismatch blocker.
6. Inspect missing control and missing readout issues separately.
7. Confirm empty inventory abstains.

Feasibility is a declared inventory value. It is not a calibrated probability of
assay success.

## Review C03 and C04

For each reporter package:

- confirm assay identity;
- confirm exact context;
- confirm target and variant IDs;
- confirm reference allele sequence identity;
- confirm alternate sequence;
- confirm two constructs on the positive path;
- confirm controls and readouts;
- confirm limitations;
- inspect context, length, budget, and empty-target controls.

Do not infer endogenous regulatory effect from a reporter construct.

## Read metrics with denominators

The positive acceptance rate is based on four positive records. The control
rejection rate is based on twelve controls. Operation acceptance rates have a
denominator of four. State-rate values describe fixture composition and should
not be presented as population frequencies.

## Inspect policy

Policy decisions should contain one decision per operation. Positive records are
publishable as planning review artifacts when accepted. Controls remain in the
evaluation and are not removed to satisfy policy.

## Inspect lineage

The default graph contains 36 edges: 20 source-to-execution and 16
fixture-to-execution. Trace at least one positive and one control for each
operation. Every record, including an invalid or blocked control, must have a
terminal address.

## Inspect reconciliation

Reconciliation has sixteen items and no mismatches. Compare expected and
observed state and the complete sorted issue tuple. A state match with a wrong
issue code is still a failed reconciliation.

## Inspect runtime and release

Runtime stages are ordered:

1. data audit;
2. contracts;
3. schema;
4. fixture replay;
5. metrics;
6. policy;
7. lineage;
8. reconciliation;
9. quality gate;
10. release bundle.

The release manifest has four checks: bundle address, quality gate, replay, and
bundle publishability. All four must pass for `ready`.

## Replay review

Run replay twice with different replay IDs. Compare fixture ID, evaluation
address, check count, passed count, and acceptance. Replay IDs may differ; stable
evaluation addresses should not.

## Scenario and threshold review

The scenario matrix has 31 rows: 27 design combinations and four operation
rows. Threshold probing has 972 probes across four profiles. These surfaces
exercise edges but do not calibrate a planner or prove external validity.

## Output review

The review CSV must contain one header and sixteen data rows. The JSON release
manifest must retain allowed and excluded uses. Canonical JSON should be used
when comparing addresses.

## Version comparison

Compare versions in this order:

1. fixture and schema version;
2. source receipt addresses;
3. record addresses;
4. execution states and issues;
5. metrics;
6. policy decisions;
7. release state and use lists.

Classify differences as expected, structural, computational, provenance, or
policy. Every non-expected difference needs a review note.

## Final checklist

- [ ] Identity captured.
- [ ] Sources verified.
- [ ] Four positive paths accepted.
- [ ] Twelve controls retained.
- [ ] C01 gaps reviewed.
- [ ] C02 blockers reviewed.
- [ ] C03 and C04 constructs reviewed.
- [ ] Metrics denominators understood.
- [ ] Policy decisions reviewed.
- [ ] Lineage complete.
- [ ] Reconciliation exact.
- [ ] Twelve gate checks pass.
- [ ] Replay has no drift.
- [ ] Excluded uses attached.
