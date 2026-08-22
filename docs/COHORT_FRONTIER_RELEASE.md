# Domain 12 release assembly guide

The release surface combines the public fixture, computation, policy, lineage,
quality, replay, and use boundary into one manifest. This guide describes the
assembly order and the fields a downstream reader should expect.

## Assembly inputs

Release assembly requires:

- a typed public aggregate fixture;
- a complete evaluation;
- a metrics report;
- an acyclic lineage graph;
- a reconciled report;
- a policy with four decisions;
- a quality gate;
- a replay receipt.

The runtime produces the first seven operational surfaces and the release
command adds replay and manifest checks. Callers should use the runtime bundle
when possible so addresses are connected to one rehearsal.

## Bundle contents

The bundle carries:

| Field | Purpose |
| --- | --- |
| bundle_id | release rehearsal identity |
| fixture_id | source fixture identity |
| fixture_address | fixture receipt |
| evaluation_address | execution receipt |
| metrics_address | metric receipt |
| lineage_address | graph receipt |
| reconciliation_address | expectation receipt |
| policy_id | decision policy identity |
| policy_address | policy receipt |
| policy_decisions | four operation decisions |
| release_notes | boundary and limitation notes |
| content_address | bundle receipt |

The bundle is publishable only when every policy decision is publishable. The
default policy permits the four positive paths while retaining controls in the
underlying reports.

## Release checks

The release manifest has four checks:

1. bundle address exists;
2. quality gate is accepted;
3. replay is accepted;
4. bundle is publishable.

All four must pass for state `ready`. A failed check yields `review`. The state
is not a presentation label; it is calculated from the check set.

## Use boundary

The release manifest includes four allowed uses and six excluded uses. A
consumer must display these lists when presenting a release outside the local
package. The manifest is appropriate for aggregate review and method work. It
does not authorize patient care or individual decisions.

## Rehearsal sequence

```text
fixture -> audit -> contracts -> schema -> evaluation -> metrics
        -> policy -> lineage -> reconciliation -> quality
        -> bundle -> replay -> release
```

Every arrow represents a typed surface with a content address. The sequence is
also represented by runtime stage numbers for operational inspection.

## Release commands

```powershell
glio-noncode cohort-frontier-runtime --output runtime.json
glio-noncode cohort-frontier-bundle --output bundle.json
glio-noncode cohort-frontier-release --output release.json
glio-noncode export-cohort-frontier-review-csv --output review.csv
```

The default command path uses the public aggregate fixture. A positional JSON
path may be supplied for a caller fixture that satisfies the same schema.

## Manifest review

Before distributing a ready manifest:

- compare fixture and evaluation addresses;
- confirm the gate address is the gate reviewed by the release owner;
- compare the replay address with the current fixture;
- confirm all four checks are true;
- confirm `ready` state;
- confirm allowed and excluded uses;
- attach the review CSV;
- retain the depth audit.

## Version changes

Change the release version when output semantics, policy rules, issue codes, or
thresholds change. A changed note that changes only explanatory prose may be
handled as a metadata revision, but the release address must still be allowed
to change if the note participates in the hashed body.

## Distribution package

A complete handoff contains:

1. source audit JSON;
2. contract manifest;
3. schema manifest;
4. evaluation JSON;
5. replay JSON;
6. metrics JSON;
7. lineage JSON;
8. policy JSON;
9. quality gate JSON;
10. runtime JSON;
11. bundle JSON;
12. release JSON;
13. review CSV;
14. depth audit JSON;
15. this boundary documentation.

The package may be compressed for transfer, but individual files should retain
their content addresses in the manifest or their parent report.

## Blocked release handling

When state is `review`, preserve the manifest and publish the failed check IDs
to the review queue. A blocked release should not be rewritten as ready by a
consumer. Fix the upstream surface, rerun the complete sequence, and create a
new receipt.

## Release checklist

- [ ] Fixture audit accepted.
- [ ] Four contracts present.
- [ ] Four schemas present.
- [ ] Evaluation has 120 passing checks.
- [ ] Metrics has 11 rows.
- [ ] Lineage has 36 acyclic edges.
- [ ] Reconciliation has 16 matching items.
- [ ] Quality gate has 12 passing checks.
- [ ] Runtime has ten completed stages.
- [ ] Replay has no drift.
- [ ] Bundle is publishable.
- [ ] Release has four passing checks.
- [ ] State is ready.
- [ ] Use boundaries are visible.
- [ ] Review CSV contains all controls.
