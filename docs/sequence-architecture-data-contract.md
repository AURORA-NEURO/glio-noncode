# D06 Public Data Contract

## Context

The D06 architecture key is:

```text
GRCh38|diffuse_glioma|adult|bulk_tumor|sequence|baseline
```

The fields are assembly, disease class, age band, tissue state, sequence territory, and treatment state. Family fixtures have narrower contexts; their original contexts remain inside family summaries, while the aggregate case boundary is fixed to the D06 key. Each case also carries a delegated context key so cross-family execution remains inspectable.

## Source rules

Sources require a public URI, release or version, family provenance, public aggregate scope, an explicit public aggregate marker, and a SHA-256 content address. Source identifiers are unique after family prefixing. Every operation and case must join at least one D06 source receipt.

## Sequence payload rules

Payloads are mappings owned by the family fixture. The aggregate requires a record ID for positive delegation and retains the family record mapping for replay. Payloads may contain sequence strings, motif rows, model output rows, regulatory windows, or frontier evidence rows from the public aggregate fixture. The D06 boundary does not add subject, patient, donor, or sample identity fields.

## State rules

`accepted` is reserved for a positive path whose family result is supported, accepted, or published and whose expected issue receipt matches. `review` is required for all controls. `blocked` is a runtime or release state, not a positive evidence result. `published` is only a release state after quality closure.

## Deterministic addressing

Canonical JSON content hashes address sources, operations, cases, receipts, ledger events, artifacts, releases, and runtime stages. Replaying a fixed fixture must reproduce evaluation receipt projections, check projections, and the evaluation content address.

## Required counts

| Entity | Count |
| --- | ---: |
| Public sources | 17 |
| Operations | 16 |
| Cases | 64 |
| Positive cases | 16 |
| Control cases | 48 |
| Receipts | 64 |
| Evaluation checks | 458 |
| Validation cells | 80 |
| Ledger events | 64 |
| Runtime stages | 24 |
| Release artifacts | 6 |
