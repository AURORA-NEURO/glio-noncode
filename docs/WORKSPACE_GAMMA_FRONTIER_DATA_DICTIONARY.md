# Workspace Gamma Frontier Data Dictionary

## Boundary fields

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `fixture_id` | string | yes | Stable package identifier |
| `fixture_version` | string | yes | Versioned fixture contract |
| `context_key` | string | yes | Exact genome, disease, age, state, territory, and treatment context |
| `evidence_boundary` | string | yes | Declared aggregate and non-patient boundary |
| `content_address` | string | yes | Canonical receipt address |

The default context is `GRCh38|glioma|adult|stem_like|core|untreated`.

## Source receipts

`GammaFrontierSourceReceipt` contains `source_id`, `title`, `uri`,
`access_note`, and `content_address`. URIs must use HTTPS. The five public
receipts cover workspace design, planning, runtime reproducibility, snapshot
sharing, and policy vocabulary. A receipt records provenance; it does not
prove that a source claim is true.

## Record fields

| Field | Type | Meaning |
| --- | --- | --- |
| `record_id` | string | Unique execution case |
| `operation` | enum | One of the four C09–C12 surfaces |
| `role` | enum | `positive` or `control` |
| `context_key` | string | Context declared by the case |
| `source_ids` | list[string] | Receipts supporting the case |
| `payload` | object | Operation-specific input |
| `expected_state` | string | Required state after execution |
| `expected_issue_codes` | list[string] | Required retained issue vocabulary |
| `notes` | string | Review explanation |

Record hashes include all of these fields. Changing a note, source receipt,
expected state, or control issue changes the record address.

## Experiment card fields

Cards use the base workspace card model. The important fields are:

- `experiment_id`: unique card identifier;
- `target_id`: aggregate target label;
- `title`: human-readable planning title;
- `assay_type`: declared readout family;
- `status`: backlog, ready, in progress, blocked, complete, or deferred;
- `priority`: one through five;
- `owner`: declared planning group;
- `dependencies`: other card IDs;
- `blockers`: visible blockers;
- `readout`: declared measurement;
- `notes`: review notes.

Dependencies are graph edges. Missing dependencies are not invented and are
not converted into successful completion.

## Launch request fields

Launch requests contain an artifact ID, runtime, mode, context, entrypoint,
parameters, resource profile, network declaration, and source IDs.

Supported runtime values are `python`, `r`, `julia`, `node`, and `sdk`.
Supported modes are `notebook` and `sdk`. Resource profiles are `small`,
`medium`, and `large`.

The parameter hash is computed from canonical parameters. The descriptor keeps
the hash while avoiding arbitrary source text. Network state is one of
`network_disabled` or `declared_network_review_required`.

## Snapshot fields

| Field | Meaning |
| --- | --- |
| `snapshot_id` | Envelope identifier |
| `snapshot_type` | Declared payload type |
| `payload` | Portable aggregate payload |
| `payload_hash` | Canonical payload address |
| `key_id` | External key reference |
| `signature` | HMAC signature |
| `algorithm` | `hmac-sha256` |
| `issued_at` | Envelope creation time |
| `expires_at` | Optional expiry time |
| `audience` | Declared sharing audience |
| `research_use_only` | Required true boundary |
| `limitations` | Integrity and scientific review notes |

The compact execution output retains verification booleans and the algorithm,
not the signature or secret.

## Collaboration fields

Members have an ID, display label, role, context, active flag, source ID, and
raw receipt hash. Requests have an ID, member ID, action, target ID, context,
and reason.

Roles are viewer, contributor, reviewer, data steward, and owner. Actions are
view, comment, edit, launch, share, and approve. The matrix is explicit and
deny-by-default. Each decision contains the role, state, allowed flag, reason,
policy receipt, and content address.

## Issue vocabulary

| Code | Surface | Meaning |
| --- | --- | --- |
| `context_mismatch` | board, launch, access | Case is outside the requested context |
| `invalid_experiment_card` | board | Card cannot satisfy card contract |
| `unknown_dependency` | board | Dependency is not present in accepted cards |
| `invalid_launch_request` | launch | Runtime or request shape is invalid |
| `resource_profile_not_allowed` | launch | Resource profile is outside bounds |
| `snapshot_context_mismatch` | snapshot | Envelope context differs from requested context |
| `snapshot_signature_invalid` | snapshot | HMAC verification failed |
| `snapshot_expired` | snapshot | Reference time is at or beyond expiry |
| `inactive_member` | access | Roster member is inactive |
| `unknown_member` | access | Request member is absent from roster |

Issue codes are sorted before address calculation. Consumers should treat the
set as evidence, not as a display-only annotation.

## State vocabulary

`ready_for_review` means a bounded result can be inspected. `review_required`
means an explicit review condition remains, such as requested network access.
`blocked` means a result cannot proceed. `out_of_domain` means context gating
excluded the case. `abstained` means no valid surface result was produced.
`allowed` and `denied` describe access decisions. `verified` and `expired`
describe snapshot verification.

## Address fields

Unprefixed addresses use the repository `sha256:` form. Some named report
families use a readable prefix such as `runtime:` or `review-row:` followed by
the canonical digest. Both forms are opaque receipts and must not be parsed as
business identifiers.
