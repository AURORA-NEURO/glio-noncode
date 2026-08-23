# Evidence release frontier operations

This surface implements Domain 14 capabilities C13-C16 as a separate, deterministic
release boundary. It is designed for public aggregate evidence lifecycle work. It
does not ingest individual-level records and it does not convert a lifecycle receipt
into a clinical, causal, or efficacy claim.

## Transition map

| Capability | Operation | Successful state | Primary controls |
| --- | --- | --- | --- |
| C13 | evidence-tier reclassification | `reclassified` | exact context, score threshold, two reviewers, two source receipts |
| C14 | deprecation and supersession | `superseded` | target closure, self-link detection, cycle detection, context quarantine |
| C15 | audit reproducibility bundle | `bundled` | evidence/review/release sections, item addresses, duplicate identity checks |
| C16 | signed research dossier | `signed` then `verified` | audience, expiry, key ID, HMAC receipt, recomputation |

Each operation returns an immutable content address. A `review` state means the
input is structurally usable but a required human or evidence condition is not
closed. A `blocked` state is reserved for context quarantine or a cycle that must
not be transported into the release. A `rejected` state is malformed input.

## Runtime order

The local runtime starts with the public source and schema audits, evaluates all
sixteen rows, then builds metrics, lineage, reconciliation, quality, replay,
reproducibility, release, artifact, review, integrity, evidence, and operational
receipts. The final accepted value requires every blocking plane to pass. The runtime
does not require a network call: source receipts retain public HTTPS anchors and
scope; the fixture is an explicit aggregate contract.

## Safe dossier publication

Signing material is accepted as an operation argument and never included in the
result projection. The public fixture uses deterministic test material only so a
fresh checkout can verify its own receipt. A real deployment should inject its key
through a secret manager and publish only the key identifier and signature receipt.
The HMAC is a shared-secret receipt; it is not a public-key identity.

## Module ownership

The contracts module owns enums and immutable records.
The support module owns parsing and safe projection.
The operations module owns transition semantics.
The public-data module owns fixture construction and audit.
The schema module owns required-field validation.
The adapters module owns explicit dispatch.
The evaluator owns row-level comparison.
The runtime owns stage order and gate composition.
The lineage module owns source joins.
The reconciliation module owns expected-state comparison.
The review modules own queue and handoff projection.
The integrity modules own address checks.
The release modules own package and artifact receipts.
The documentation owns the declared boundary.
The tests own executable examples of positive and control behavior.

This separation makes a change reviewable: a change to a transition function can be
replayed against the same fixture, while a change to the fixture must update its
content address and pass data-boundary checks. A change to a schema requires a
version or migration receipt. A change to publication policy must rerun signature,
claim-boundary, and release checks. A change to a report projection must not change
the operation result address unless its serialized output changes.
