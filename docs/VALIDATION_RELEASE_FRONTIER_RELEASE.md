# Validation-release frontier release controls

## Release contents

The local release manifest closes:

- the fixture and source receipt address;
- the 16-row, 80-check evaluation;
- the adapter and schema addresses;
- source-to-record-to-execution lineage;
- reconciliation and quality-gate addresses;
- deterministic replay receipt;
- six required artifact records;
- review queue, SLA, and handoff projections;
- depth, integrity, compatibility, and release-check receipts; and
- package, bundle, transcript, audit-log, and observability outputs.

The runtime currently emits 50 ordered stages. Release acceptance requires all
required stage outputs to be present, content-addressed, and consistent with
the declared state boundaries. The release is a research planning artifact;
it does not authorize experimental execution.

## Quality gates

The quality gate requires a passing public-data audit, a passing five-check
evaluation for every row, 16 records, 80 checks, four registered adapters, a
content-addressed schema, and expected/observed-state reconciliation. The
independent release checks additionally require quality, integrity, and
contract/runtime compatibility.

## Rollback and recovery

Every non-ready record receives a bounded operational action. Context issues
route to context verification, malformed inputs route to repair-and-replay,
and other controls route to domain review. A rollback plan identifies the
previous release address and remains reversible. The audit log is append-only
and sequence-checked; the transcript gives a readable ordered projection.

## Replay

Replay loads the checked-in fixture, does not fetch the source portals, and
recomputes the operation outputs. The replay receipt compares the original and
second evaluation addresses. A changed address is a release review event, not
a hidden update.

## Public boundary

Public source links are retained as provenance anchors. The checked-in data is
aggregate planning data with synthetic operational values. The release must
not be described as evidence of off-target absence, assay efficacy, causal
regulation, treatment response, patient benefit, or clinical safety.

## Regression evidence

The benchmark repeats the full fixture evaluation and compares deterministic
evaluation addresses while reporting elapsed local time separately. Contract
migration receipts identify the source and target schema versions, operation
families, and reversibility. Threshold probes exercise the C13 review and
blocking edges, the C14 no-selection edge, and the exact-context edge. These
receipts make performance, migration, and boundary changes reviewable without
turning a timing measurement into a scientific result.
