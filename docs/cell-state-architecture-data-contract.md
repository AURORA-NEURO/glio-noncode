# D08 Data Contract

## Required fixture object

```json
{
  "fixture_id": "d08-cell-state-architecture-public-aggregate",
  "version": "2026.08.d08-cell-state-architecture.v1",
  "boundary": "public_aggregate_cell_state_disease_territory",
  "context_key": "GRCh38|glioma|adult|stem_like|tumor|unknown",
  "sources": [],
  "operations": [],
  "cases": [],
  "content_address": "sha256:..."
}
```

The typed fixture requires exactly 18 sources, 16 operations, and 64 cases. Source, operation, case, receipt, execution, artifact, stage, ledger, and release objects each carry a content address. Addresses are derived from deterministic serialized bodies and are checked during mapping loads and runtime construction.

## Source fields

Sources contain `source_id`, family, title, HTTP(S) URI, version, aggregate scope, public-source license text, and a content address. The scope must be `public_aggregate`; a source that does not satisfy this boundary cannot enter the fixture.

## Operation fields

Operations contain an ordered ID, capability ID, enum operation, family, plane, input contract, output contract, dependencies, source IDs, control policy, and content address. Ordinals are contiguous from 1 through 16. Dependencies form a linear ready plan in this build and are checked before execution.

## Case fields

Cases contain operation and capability IDs, operation/family/plane enums, scenario, context key, source IDs, an object payload, expected state, expected result state, expected issue codes, expected counts, description, and content address. Positive cases must be accepted; controls must be review-held.

## Review-safe projection

Reports and views omit raw payload fields such as `payload`, `input_text`, `track_text`, `raw_text`, and `records_text`. This preserves the fact that a receipt was evaluated without copying raw family records into every reporting surface. The full fixture remains available through the explicit fixture export.

## Cardinality rules

The expected scenario vector is:

```text
positive: 16
foreign_context: 16
malformed_input: 16
identity_conflict: 16
```

The evaluation produces six checks for each of 64 cases and eight global checks, for 392 checks total. Source joins cover all 16 operation specifications and all 64 cases. The release contains six artifacts and 22 accepted stages.

## Cell-state payloads

C13 requires `sample_id`, `state_id`, `count`, and `total_cells` records plus an interval multiplier. C14 requires `cell_id` and reference scores plus score and margin thresholds. C15 requires cell ID, distance, support score, and support boundary plus OOD thresholds. C16 requires an envelope ID, exact context, non-empty cell IDs, and the three upstream content addresses.
