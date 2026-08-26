# Storage maintenance planning

Storage maintenance is the review boundary after the local storage audit. It
turns findings into a deterministic action ledger without changing the data
root. A plan is addressed from its audit, policy, counters, and ordered
actions, so the same accepted storage state produces the same plan address.

## States

| State | Meaning |
| --- | --- |
| `clean` | The audit is accepted and the plan contains one `no-action` entry. |
| `review` | Only reversible quarantine or unexpected-entry review is proposed. |
| `blocked` | A reference, object, run index, or batch index needs recovery or repair, or the action bound overflowed. |

Every action is `review_only=true`. `safe_to_apply` is always false. The
planner does not delete files, rewrite indexes, restore objects, replay runs,
or quarantine entries. `approval_required` records the policy decision for an
external workflow; it is not an execution authorization.

## Action routing

- `quarantine-orphan`: a valid object is unreachable from persisted roots.
- `quarantine-unexpected`: a file is outside the recognized store layout.
- `restore-missing-object`: a referenced object is absent.
- `repair-invalid-object`: an object fails byte, JSON, or address checks.
- `replay-run`: a run index or replay check fails.
- `reopen-batch`: a batch index or result reopen check fails.
- `no-action`: the accepted audit has no findings.

The planner is bounded by `max_actions` and exports only aggregate metadata,
addresses, relative paths, reasons, and counts. It does not copy source
payloads into the plan.

## CLI

```text
glio-noncode storage-maintenance --data-root .glio --format markdown
glio-noncode storage-maintenance --kind repair-invalid-object --severity high
glio-noncode storage-maintenance-schema
glio-noncode storage-maintenance-capabilities
glio-noncode storage-maintenance-verify plan.json
glio-noncode storage-maintenance-diff before.json after.json
glio-noncode storage-maintenance-packet --data-root .glio --destination maintenance-packet
glio-noncode storage-maintenance-packet-verify maintenance-packet
glio-noncode storage-maintenance-packet-load maintenance-packet
```

Filtered output is a bounded JSON page. Unfiltered output may be JSON, CSV,
or Markdown. The verify and diff commands accept only strict contract objects
and reject content-address drift.

## HTTP

- `GET /v1/storage/maintenance` builds and pages a plan from the configured data root.
- `GET /v1/storage/maintenance/schema` returns the closed plan schema.
- `GET /v1/storage/maintenance/capabilities` describes supported projections.
- `POST /v1/storage/maintenance/verify` validates a saved plan.
- `POST /v1/storage/maintenance/query` pages actions from a supplied plan.
- `POST /v1/storage/maintenance/diff` compares two supplied plans.

All endpoints are read-only. Invalid contracts return a bounded client error;
the storage root is never mutated by this feature.

## Offline packet

`storage-maintenance-packet` writes seven fixed UTF-8 payloads and one manifest:
the strict plan, action CSV, aggregate summary, schema, capabilities,
observability, and review queue. Each
payload has byte, line, and content-address metadata. Verification rejects
missing, unexpected, unsafe, symlinked, duplicate, or tampered paths, checks
the plan address against the manifest, and scans JSON metadata at the public
boundary. `storage-maintenance-packet-load` hydrates the plan only after every
check passes.

The packet also includes the observability and review-queue projections.
Observability is a timestamp-free event ledger plus aggregate counts and byte
estimates. The review queue orders actions by blocked/recovery priority, then
exposes explicit `quarantine`, `repair`, `replay`, and `reopen` routes. Neither
projection contains assignment or execution state.

Additional CLI projections are available with
`storage-maintenance-observability` and `storage-maintenance-review`; each
supports deterministic JSON and tabular exports, while filtered output remains
bounded JSON.
