# Workspace beta frontier release

## Release sequence

1. run the fixture audit
2. evaluate every positive and control row
3. measure package metrics
4. build source lineage
5. apply policy decisions
6. reconcile expected and observed state
7. run the quality gate
8. replay the fixture
9. assemble the bundle
10. build the release manifest

## Manifest checks

The manifest checks bundle acceptance, quality acceptance, replay determinism,
runtime acceptance, public boundary, stage count, and content-address format.
Blocking failures produce `held` state and a `hold_reasons` tuple.

## Versioning

The public package version is `2026.08.d15.c05-c08.v1`. Bumping the version
requires updating the fixture version, schema version, contract version, and
release documentation together.

## Promotion boundary

`ready` means the package satisfies its research-use contracts. It does not
mean that a topology edge is a mechanism, that a chain is a causal probability,
that a posterior proxy is calibrated, or that a table filter changes evidence.

## Reproducibility

The replay receipt compares the fixture address, evaluation address, and every
execution address. A release cannot be treated as reproducible if any of those
values change for the same fixture.

## Export checklist

- canonical JSON can be parsed by the repository serializer
- review CSV has stable columns
- all review rows retain source IDs
- issue codes are delimited without loss
- release manifest points to the bundle and runtime
- no row is silently dropped during pagination
