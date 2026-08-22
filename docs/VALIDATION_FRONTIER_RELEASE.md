# Domain 13 planning release guide

The release combines fixture, evaluation, policy, lineage, quality, replay,
and use boundaries into one manifest.

## Inputs

Release assembly uses a typed fixture, evaluation, metrics, lineage,
reconciliation, policy, quality gate, and replay receipt. The runtime produces
the connected bundle used by the release builder.

## Checks

The release has four checks:

1. bundle address exists;
2. quality gate passes;
3. replay passes;
4. bundle is publishable.

All four produce `ready`. A failed check produces `review`.

## Allowed uses

- assay planning review;
- method development;
- reproducibility testing;
- research triage.

## Excluded uses

- patient care;
- diagnosis;
- prognosis;
- treatment selection;
- individual risk;
- clinical validation claims.

## Handoff contents

Include data audit, contracts, schema, evaluation, replay, metrics, lineage,
policy, quality, runtime, artifacts, observability, bundle, release, review CSV,
depth audit, and boundary documentation.

## Release checklist

- [ ] Evaluation has 120 passing checks.
- [ ] Reconciliation has 16 matching items.
- [ ] Lineage has 36 acyclic edges.
- [ ] Quality gate has 12 passing checks.
- [ ] Runtime has ten stages.
- [ ] Replay has no drift.
- [ ] Bundle is publishable.
- [ ] State is ready.
- [ ] Controls are included.
- [ ] Use boundaries are attached.
