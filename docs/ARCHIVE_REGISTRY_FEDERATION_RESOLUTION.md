# Archive Registry Federation Resolution and Reconciliation

This contract is the decision-preserving layer above independently downloaded
archive registries. It answers two separate questions:

1. What can be selected from the observations under a declared quorum?
2. What would each peer need to do to converge on that selection?

The answers are represented as immutable, content-addressed public documents.
They do not edit a source registry, choose a winner when a quorum is absent, or
silently remove a dissenting observation. A ready result is safe to release;
a review or blocked result is safe to inspect and route for a later decision.

## Boundary

The boundary name is:

```text
consensus-certificate-observatory-archive-registry-federation-resolution
```

The plan boundary extends it with:

```text
consensus-certificate-observatory-archive-registry-federation-resolution-reconciliation-plan
```

The persisted runtime extends it again with:

```text
consensus-certificate-observatory-archive-registry-federation-resolution-reconciliation-plan-runtime
```

Every document includes a version, boundary, stable identifier, and a
content address. The address is calculated from the canonical public mapping
with the address field removed. Canonical JSON uses sorted object keys and a
stable representation for sequences. Reordering peers, candidates, or input
paths therefore cannot create a different result when the evidence is the
same.

The boundary accepts only public data. It rejects local filesystem paths,
attribution fields, credentials, opaque secrets, and unbounded text. Paths are
accepted only as process inputs and are never copied into the resulting
documents.

## Evidence flow

```text
downloaded registry  ─┐
downloaded registry  ─┼─> federation observations ─> quorum consensus
downloaded registry  ─┘                              │
                                                     ├─> resolution
                                                     │     │
                                                     │     └─> resolution audit
                                                     │
                                                     └─> per-peer plan
                                                           │
                                                           ├─> plan audit
                                                           └─> exact runtime
                                                                 │
                                                                 └─> runtime audit
```

The source registry contract remains the authority for each individual
download. Federation compares registry entries by entry identity and preserves
the archive content addresses observed by each peer. Consensus groups the
addresses for an entry and records candidate support. Resolution projects each
decision into an explicit item. The reconciliation plan expands each item into
one operation for every peer/entry pair.

## Inputs

Each input can be one of the following:

| Input | Accepted form | Meaning |
| --- | --- | --- |
| Registry directory | exact archive-registry directory | Reloaded and verified by the registry runtime |
| Registry JSON | public registry document | Parsed and verified by the registry model |
| In-memory registry | typed registry object | Verified before federation |

The runtime rejects symlinks, malformed JSON, non-regular files, unknown
registry members, bad nested addresses, and registry documents whose canonical
bytes do not replay. The runtime accepts at most the federation peer bound.
Source registries remain untouched even when the result contains replacements,
requests, or manual review operations.

## Resolution model

The resolution has one item for every federation observation. Items are sorted
by entry identifier and receive one-based ordinals. Each item contains:

| Field | Purpose |
| --- | --- |
| `entry_id` | Stable identity of the registry entry |
| `package_id` | Public source package identity |
| `state` | `resolved`, `review`, or `blocked` |
| `action` | `retain-consensus`, `review-divergence`, or `request-missing` |
| `selected_archive_address` | Quorum-selected archive address, when one exists |
| `candidate_archive_addresses` | All observed candidate addresses |
| `supporting_peer_ids` | Peers supporting the selected address |
| `missing_peer_ids` | Peers with no observation for the entry |
| `dissenting_peer_ids` | Peers supporting another address |
| `peer_count` | Number of federation peers considered |
| `quorum` | Required support count |
| `evidence_addresses` | Federation and candidate addresses used to derive the item |
| `rationale` | Stable explanation for the state |
| `content_address` | Address of the resolution item |

The aggregate repeats conserved counts so downstream readers do not need to
recompute them. The following state rules are normative:

| Evidence | State | Action | Release effect |
| --- | --- | --- | --- |
| One candidate reaches quorum | `resolved` | `retain-consensus` | Eligible |
| Multiple candidates exist and none reaches quorum | `review` | `review-divergence` | Held for review |
| No candidate reaches quorum because the entry is absent | `blocked` | `request-missing` | Blocked |

The aggregate `accepted` flag is false when a blocked item exists, while a
review-only result remains accepted for planning. `release_ready` is true only
when every item is resolved. The independent resolution audit can still accept
the blocked mapping as an internally coherent evidence receipt, allowing an
operator to archive the explanation without treating it as release approval.

### Quorum

The declared quorum is bounded to the number of peers and is part of the
consensus address. Omitting it uses the consensus model default. Changing the
quorum creates a new consensus, resolution, plan, and runtime address even if
the registry inputs are unchanged.

A candidate is selected only when its support count is at least the quorum. A
tie at or above quorum is rejected by the consensus contract and cannot be
flattened by the resolution layer. Missing entries are retained separately
from divergent entries because a missing peer can be asked to retrieve the
selected archive while a divergent peer requires comparison.

## Reconciliation plan

The plan is a read-only operation matrix with exactly:

```text
operation_count = peer_count × entry_count
```

Operations are ordered first by entry identifier and then by peer identifier.
The operation content address includes the evidence addresses, so a changed
observation cannot reuse an old instruction.

| Source state | Observed peer address | Action | Status | Priority |
| --- | --- | --- | --- | --- |
| `resolved` | equals selected address | `no-op` | `no-op` | `none` |
| `resolved` | absent | `request-missing` | `planned` | `high` |
| `resolved` | different address | `replace-with-consensus` | `planned` | `high` |
| `review` | any | `manual-review` | `review` | `critical` |
| `blocked` | present | `manual-review` | `blocked` | `critical` |
| `blocked` | absent | `request-missing` | `blocked` | `critical` |

`desired_archive_address` is populated only when a safe target exists. A
blocked request deliberately has no desired address: there is no quorum-backed
archive to request. `requires_confirmation` is true for every mutation,
manual review, and blocked operation. No executor is included in this
boundary; the plan is a safe handoff for a separately governed process.

The plan aggregate has four useful outcomes:

| Plan state | Meaning |
| --- | --- |
| `ready` | Every peer/entry operation is a no-op |
| `review` | At least one operation needs human review, but none is structurally blocked |
| `blocked` | At least one operation cannot proceed without missing quorum evidence |

`accepted` means no operation is blocked. `release_ready` means every
operation is a no-op. Thus a plan can be accepted for planning while remaining
not release-ready because it contains planned replacements or requests.

## Audits

Resolution, plan, and runtime audits are independent typed contracts. Each
audit has a fixed check list, addressed checks, canonical replay, and a public
summary. Audits do not trust the producer's boolean flags; they recompute
links, counts, states, and address relationships.

### Resolution audit checks

The resolution audit validates:

1. federation and consensus linkage;
2. item count conservation;
3. item ordinal continuity;
4. state count conservation;
5. action/state compatibility;
6. selected-address support;
7. missing-peer conservation;
8. bounded peer evidence;
9. candidate-address linkage;
10. item address replay;
11. consensus address namespace;
12. public-field safety;
13. bounded input limits;
14. aggregate address replay.

### Plan audit checks

The plan audit validates:

1. plan linkage;
2. peer/entry matrix dimensions;
3. operation ordinal continuity;
4. action counter conservation;
5. blocked counter conservation;
6. unique peer/entry coverage;
7. confirmation policy;
8. operation content-address replay;
9. supported source states;
10. acceptance and readiness projection;
11. operation evidence;
12. nested address namespaces;
13. public-field safety;
14. plan content-address replay.

### Runtime audit checks

The runtime audit validates the complete nested closure:

1. runtime identity and boundary;
2. source-count/federation-peer conservation;
3. shared federation linkage;
4. consensus/resolution linkage;
5. resolution/plan linkage;
6. plan/federation linkage;
7. federation audit linkage;
8. consensus audit linkage;
9. resolution audit linkage;
10. plan audit linkage;
11. acceptance projection;
12. release-readiness/state projection;
13. public-field safety;
14. runtime content-address replay.

The runtime is accepted only if all nested audits are accepted. Release
readiness still follows the plan and therefore remains false for valid review
or blocked evidence.

## Exact persisted runtime

When `--destination` is provided, the runtime writes exactly nine files:

| File | Contents |
| --- | --- |
| `manifest.json` | File names, sizes, and byte hashes |
| `runtime.json` | Top-level runtime closure and outcome |
| `federation.json` | Independent peer observations |
| `federation-audit.json` | Federation audit |
| `consensus.json` | Candidate groups and decisions |
| `resolution.json` | Entry-level state/action projection |
| `resolution-audit.json` | Resolution audit |
| `plan.json` | Peer/entry reconciliation matrix |
| `plan-audit.json` | Plan audit |

The destination is materialized through a temporary sibling directory and
renamed into place. Existing destinations are refused unless `overwrite=True`
is explicitly supplied by the caller. Replay rejects missing files, extra
files, symlinks, non-canonical bytes, incorrect manifest sizes, incorrect byte
hashes, and nested documents with mismatched addresses.

The runtime JSON is also sufficient for a typed in-memory replay. The directory
loader additionally verifies all raw artifacts against the manifest before it
constructs the nested object graph. This makes a copied runtime independently
verifiable without access to the original source directories.

## Queries

### Resolution query

The resolution query exposes these resources:

```text
summary, items, resolved, review, blocked, supporting, missing, dissenting
```

Filters include entry ID, state, action, peer ID, package ID, and bounded text.
The query result records the original total, filtered count, returned count,
offset, limit, and next offset. Row ordinals are reissued after filtering so a
page is deterministic and easy to audit.

### Plan query

The plan query exposes:

```text
summary, operations, no-op, request-missing, replace-with-consensus,
manual-review, planned, review, blocked
```

Filters include peer ID, entry ID, source state, action, status, priority,
registry ID, package ID, and bounded text. Operations retain their stable
operation addresses in every projection.

Both query layers have separate query audits. A query audit verifies the query
address, result address, resource selection, original row order, page bounds,
row ordinals, filter replay, and public-field safety. A query is not considered
verified merely because it returns zero rows.

## CLI

Build and persist a reconciliation runtime from two downloaded registries:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-runtime `
  --input C:\data\primary-registry `
  --input C:\data\replica-registry `
  --peer-id primary --peer-id replica `
  --quorum 2 `
  --destination C:\data\reconciliation-runtime `
  --format summary
```

Inspect the persisted runtime or its nested plan:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-runtime-audit `
  --input C:\data\reconciliation-runtime\runtime.json --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-plan `
  --input C:\data\reconciliation-runtime\runtime.json --format markdown
```

Query the resolution and plan JSON documents:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-resolution-query `
  --input C:\data\reconciliation-runtime\resolution.json `
  --resource review --resource blocked --format markdown
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-plan-query `
  --input C:\data\reconciliation-runtime\plan.json `
  --resource replace-with-consensus --resource manual-review --format csv
```

The resolution command can also derive a resolution directly from a public
federation JSON document:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-resolution `
  --input C:\data\federation.json --quorum 2 --format markdown
```

Schema and capability commands are available for every object, audit, query,
and runtime contract. They are included in the public-surface inventory and
are served under the corresponding HTTP namespace.

## HTTP

The API root is:

```text
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/federation
```

The new operation paths are:

| Path | Operation |
| --- | --- |
| `/resolution` | Build a resolution from a federation input |
| `/resolution/audit` | Audit a resolution JSON or runtime directory |
| `/resolution/query` | Query a resolution JSON |
| `/resolution/query-audit` | Audit a resolution query |
| `/reconciliation-plan` | Read a plan from a runtime input |
| `/reconciliation-plan/audit` | Audit a plan JSON or runtime directory |
| `/reconciliation-plan/query` | Query a plan JSON |
| `/reconciliation-plan/query-audit` | Audit a plan query |
| `/reconciliation-runtime` | Build and optionally persist a runtime |
| `/reconciliation-runtime/audit` | Audit a runtime JSON or directory |

The build routes accept `format=json`, `format=csv`, `format=markdown`, or
`format=summary`. Repeated `input`, `peer_id`, and `resource` query parameters
are preserved. HTTP errors are fail-closed: malformed documents and failed
validation are returned as contract errors rather than partial results.

Schema paths mirror the operation hierarchy. For example:

```text
/resolution/schema
/resolution/audit/schema
/resolution/query/result-schema
/reconciliation-plan/schema
/reconciliation-plan/query-audit/schema
/reconciliation-runtime/manifest-schema
/reconciliation-runtime/audit/schema
```

## Failure semantics

Failure handling is deliberately split into structural rejection and valid
held evidence.

### Structural rejection

The parser rejects unknown fields, missing fields, invalid labels, unbounded
arrays, invalid addresses, malformed nested documents, bad counters, and
content-address mismatches. A rejected mapping is not converted into a
synthetic blocked resolution because its evidence cannot be trusted.

### Valid review

Conflicting candidates can form a valid federation and a valid resolution with
`state=review`. The selected address remains empty and all candidates remain
visible. The plan marks every peer/entry operation as `manual-review` with
critical priority and `status=review`.

### Valid blocked evidence

Missing entries or quorum-unavailable candidates can form a valid blocked
resolution. The plan marks the relevant operations as `blocked`; its
`accepted` value remains true only when the plan has no blocked operations.
The runtime can still be archived for investigation, but
`release_ready=false`.

### Safe mutation boundary

No method in this boundary edits a registry. `replace-with-consensus` is a
description of a possible future change and includes `requires_confirmation`.
An executor, credentials, network transport, and write authorization belong to
a later separately governed module.

## Verification matrix

The focused contract suite covers the following matrix:

| Area | Ready case | Held case | Corruption case |
| --- | --- | --- | --- |
| Resolution | quorum-selected entries | missing/divergent entries | altered address or counter |
| Plan | all no-op operations | requests, replacements, review | altered operation or matrix |
| Query | resources, filters, pagination | review/blocked rows | altered ordinal or address |
| Runtime | exact nine-file replay | blocked but auditable handoff | missing/extra/tampered member |
| CLI | build, audit, query, schema | nonzero release result | invalid input rejection |
| HTTP | build and schemas | held state response | validation error |
| Public surface | closed schemas and inventory | public blocked summaries | forbidden-field scan |

The downloaded-input demo runs the same flow outside the test fixture. It
accepts only operator-provided registry downloads or public registry JSON; it
does not use the planning archive as production evidence and does not embed
local input paths in its output.

## Operational checklist

Before releasing a runtime:

1. Verify each source registry independently.
2. Assign stable peer IDs and record the intended quorum.
3. Build the runtime into a new destination.
4. Run the runtime audit against `runtime.json`.
5. Inspect resolution rows with `review` and `blocked` resources.
6. Inspect plan rows with `manual-review`, `request-missing`, and
   `replace-with-consensus` resources.
7. Confirm `accepted=true`, `release_ready=true`, and `state=ready`.
8. Preserve the runtime directory as the evidence handoff.

If any release condition is false, preserve the handoff and route the stated
evidence addresses to review. Do not infer that a failed release check means
the source registries are invalid; it may only mean that quorum evidence is
insufficient for a safe convergence decision.

## Determinism notes

The implementation sorts peer IDs, entry IDs, candidate addresses, evidence
addresses, and operation keys before constructing public mappings. It avoids
timestamps and process-local identifiers in addressed output. The optional
runtime ID and federation ID are explicit caller inputs, so two independent
operators can reproduce one address when they use the same public inputs and
identifiers.

The source path is used only to load bytes. Once loaded, the source path is
discarded. This keeps JSON, CSV, Markdown, query rows, audit evidence, and
runtime manifests portable across machines.

## Extension boundary

Future work may add a separately authorized executor, remote retrieval, or
signature verification. Such features must consume the plan as evidence and
must not change the meaning of the current states. In particular:

- an executor must require confirmation for every non-no-op operation;
- a missing selected address must remain a blocked request;
- a manual-review operation must never be auto-promoted;
- the original federation and resolution addresses must remain attached;
- the resulting registry must be a new addressed snapshot;
- the source runtime must remain immutable and replayable.

This keeps reconciliation explainable even as the surrounding product grows.
