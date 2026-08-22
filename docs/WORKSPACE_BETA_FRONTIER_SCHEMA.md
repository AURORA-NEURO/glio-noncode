# Workspace beta frontier schema

## Operation schemas

### Topology viewport

Required fields are `context_key`, `nodes`, `edges`, `state`, `focus`, and
`warnings`. Loop, promoter-capture, contact-score, and activity-by-contact
records are input families. Nodes and edges retain source IDs and observation
receipts.

### Causal chain

Required fields are `context_key`, `results`, `state`,
`missing_mediator_kinds`, `alternative_edge_ids`, and `warnings`. Each edge
retains mediator kind, support, uncertainty, source IDs, source versions,
evidence IDs, and negative evidence IDs.

### Posterior decomposition

Required fields are `context_key`, `hypothesis_id`, `declared_prior`,
`evidence_support`, `components`, `residual`, `normalized_shares`, and
`calibration_status`. `evidence_support` is a required nullable field: the key
must be present even when the value is absent.

### Evidence table

Required fields are `context_key`, `workspace_id`, `filter`, `rows`,
`total_matches`, `facets`, and `warnings`. A row retains record type, state,
channel, tier, confidence, source IDs, tags, and fields.

## Shared requirements

- all context keys are exact strings
- all source IDs are stable strings
- all output objects are JSON serializable
- all package receipts use a `sha256:` prefix
- all bounded values are checked before execution
- all unresolved states remain representable
- all public aggregate boundaries remain explicit

## Schema evolution

Adding a field is compatible when it is optional or nullable and does not alter
state semantics. Removing a field, changing an enum, changing pagination
meaning, or changing residual tolerance requires a new package version and a
new fixture control.
