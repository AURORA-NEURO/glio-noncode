# Evidence release frontier schema

The fixture version is `2026.08.d14-c13-c16.v1`. The supported context is an exact
ordered key:

`GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment`

Every record has an operation, role, context, source IDs, payload, expected state,
expected issue codes, notes, and a SHA-256 content address. Every source receipt has
a source ID, public HTTPS URI, scope, version declaration, and content address.

## Payload contracts

Reclassification requires `evidence_id`, `context_key`, `previous_tier`,
`proposed_tier`, `evidence_score`, `reviewer_ids`, and `source_ids`.

Supersession requires `context_key` and a `records` list. Each record carries an
identity, status, optional superseded target, and exact context.

Reproducibility bundling requires `bundle_id`, `context_key`, and `sections`. The
required section kinds are `evidence`, `review`, and `release`; every item carries
a content address.

Signed dossiers require `dossier_id`, `context_key`, `audience`, `expires_at`, and
an object payload. A key ID is public metadata. The signing material is not part of
the fixture and is excluded from safe output.

## State rules

`reclassified`, `superseded`, `bundled`, and `signed` are terminal operation results.
`verified` is emitted by the explicit verification helper. `review` preserves a
repairable or adjudication-required input. `blocked` quarantines foreign context or
cycle state. `rejected` identifies malformed shape or a failed signature.
