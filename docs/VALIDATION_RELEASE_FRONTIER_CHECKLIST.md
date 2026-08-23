# Validation-release frontier release checklist

## Data boundary

- [x] Five HTTPS public source receipts are declared.
- [x] Six-part exact context is attached to every row.
- [x] Sixteen records contain four positive paths and twelve controls.
- [x] No patient-level payload or secret marker is present.
- [x] The checked-in JSON fixture round-trips to its declared address.

## C13 risk

- [x] Weighted and maximum candidate burden are calculated.
- [x] Review and blocking thresholds are tested at boundaries.
- [x] Foreign context is blocked.
- [x] Malformed score input is rejected.

## C14 planning

- [x] Cost, information, risk, and prerequisites are retained.
- [x] Dependency-safe selection is budget bounded.
- [x] Missing prerequisites and cycles are explicit.
- [x] Foreign context is blocked.

## C15 package

- [x] Experiment, control, and protocol IDs are retained.
- [x] Per-file content addresses are emitted.
- [x] Empty experiments are rejected.
- [x] Cross-file ID collisions remain reviewable.

## C16 updates

- [x] Only known claims can update.
- [x] Result and claim contexts must match exactly.
- [x] Evidence receipt presence is checked.
- [x] Unknown claim, missing receipt, and context controls remain visible.

## Release and operations

- [x] Five checks execute for every row.
- [x] Scenario, validation, and evidence matrices close.
- [x] Lineage, reconciliation, quality, replay, and integrity close.
- [x] Review queue, SLA, protocol, handoff, and recovery are emitted.
- [x] Failure injection covers representative controls.
- [x] Fifty runtime stages are ordered and accepted.
- [x] Package, bundle, audit log, transcript, and observability receipts close.
- [x] Threshold, migration, benchmark, and wording-boundary receipts are inspectable.
- [x] Selected regression tests and compile checks pass.

The checklist is a software-boundary record. It is not an assertion that the
underlying biological measurements, experiments, or clinical interpretations
are correct.
