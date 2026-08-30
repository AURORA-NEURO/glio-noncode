# Reconciliation Runtime Operator Runbook

This runbook is the short operational companion to the resolution contract.
Use it when a team has one or more independently downloaded archive registries
and needs to decide whether they can be released together, held for review, or
preserved as blocked evidence.

The runtime is deliberately an analysis-only handoff. It does not fetch a
missing archive, write to a peer registry, or execute a replacement. Those are
separate actions that must consume the addressed plan and obtain their own
authorization.

## 1. Prepare downloaded inputs

Before federation, validate every registry independently. Each registry should
be an exact five-file handoff produced by the archive-registry runtime:

```text
manifest.json
runtime.json
registry.json
registry-audit.json
registry-query.json
```

The exact member names are enforced by the registry loader. A public registry
JSON file is also acceptable when the operator already has a verified file.
Keep the original download directories immutable during this run.

For each source, record outside the public runtime:

| Operator note | Why it matters |
| --- | --- |
| peer label | Stable identity for the independent source |
| registry label | Human-readable source identity |
| acquisition context | Operational trace kept outside public evidence |
| intended quorum | Policy input that changes every downstream address |
| destination | New directory for the reconciliation handoff |

Do not put filesystem paths, credentials, access tokens, or private notes into
the registry JSON. The runtime accepts paths only as loader arguments and
discards them after reading canonical bytes.

## 2. Check the source boundary

Run the source registry audit before invoking reconciliation:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-audit `
  --input C:\data\primary-registry --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-audit `
  --input C:\data\replica-registry --format summary
```

An audit failure means the input is not a valid registry handoff. Preserve the
failure output for diagnosis and repair the source boundary first. Do not use a
reconciliation result to mask malformed source evidence.

If a source is supplied as JSON, audit its public document before composing the
peer list. JSON and directory inputs are equivalent after canonical parsing.

## 3. Build a ready runtime

The normal two-peer invocation is:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-runtime `
  --input C:\data\primary-registry `
  --input C:\data\replica-registry `
  --peer-id primary `
  --peer-id replica `
  --quorum 2 `
  --runtime-id production-reconciliation-001 `
  --destination C:\data\reconciliation-runtime-001 `
  --format summary
```

The command reads both registries, creates one federation observation set,
calculates consensus, derives a resolution, expands the plan, audits each
nested component, and writes an atomic destination. The summary should include:

```text
state=ready
accepted=true
release_ready=true
source_count=2
peer_count=2
resolved_count=...
operation_count=peer_count × entry_count
```

A ready state means every observed entry has a quorum-backed selection and
every peer already matches that selection. If the operation count is nonzero,
that does not by itself indicate a problem; the no-op count should equal it.

## 4. Inspect the persisted closure

The runtime destination contains exactly nine files:

```powershell
Get-ChildItem C:\data\reconciliation-runtime-001 -File | Select-Object -ExpandProperty Name
```

The expected names are:

```text
manifest.json
runtime.json
federation.json
federation-audit.json
consensus.json
resolution.json
resolution-audit.json
plan.json
plan-audit.json
```

Inspect the runtime audit directly:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-runtime-audit `
  --input C:\data\reconciliation-runtime-001 `
  --format markdown
```

Directory input verifies manifest sizes and byte hashes before parsing. A
`runtime.json` input verifies the nested public closure but does not have the
raw-directory membership context. Prefer the directory for release handoff
verification.

## 5. Read resolution outcomes

Resolution JSON is the entry-level decision view:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-resolution-query `
  --input C:\data\reconciliation-runtime-001\resolution.json `
  --resource summary `
  --resource resolved `
  --resource review `
  --resource blocked `
  --format markdown
```

For each entry, read the fields in this order:

1. `state` tells whether the entry is resolved, review, or blocked.
2. `action` tells the next analysis disposition.
3. `selected_archive_address` is the only release candidate address.
4. `candidate_addresses` shows all observed alternatives.
5. `supporting_peer_ids` shows the quorum support.
6. `missing_peer_ids` shows peers with no observation.
7. `dissenting_peer_ids` shows peers that observed another address.
8. `rationale` explains why no selection or a selection exists.
9. `evidence_addresses` provides the replay links.

Do not infer a selection from the first row, first peer, or most recent source.
The selected address must appear in the candidate set and its support must meet
the declared quorum. The resolution model rejects a selected address that does
not satisfy those conditions.

## 6. Handle missing peers

When an entry is present in fewer peers than the quorum allows, it becomes a
blocked resolution item. Inspect the missing rows:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-resolution-query `
  --input C:\data\reconciliation-runtime-001\resolution.json `
  --resource blocked `
  --state blocked `
  --format csv
```

The resolution keeps the missing peer IDs. The plan then emits one operation
per peer for the blocked entry:

- a missing peer gets `request-missing` with no desired address;
- a present peer gets `manual-review` because quorum is unavailable;
- both operations are `blocked` with critical priority;
- both operations require confirmation.

The empty desired address is intentional. There is no quorum-backed target to
request. A later retrieval process may add a new registry snapshot, after
which a new federation and new addresses must be built.

## 7. Handle divergent peers

When multiple candidate addresses exist but none reaches quorum, the resolution
state is `review`:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-resolution-query `
  --input C:\data\reconciliation-runtime-001\resolution.json `
  --resource review `
  --action review-divergence `
  --format markdown
```

The plan exposes the review work:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-plan-query `
  --input C:\data\reconciliation-runtime-001\plan.json `
  --resource manual-review `
  --status review `
  --priority critical `
  --format markdown
```

Every peer/entry cell receives a manual-review operation. This is useful even
when only one entry diverges because the matrix makes the peer scope explicit.
The plan remains structurally accepted when it contains review rows, but it is
not release-ready.

## 8. Understand the plan matrix

The complete plan can be exported as CSV for a controlled review queue:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-plan-query `
  --input C:\data\reconciliation-runtime-001\plan.json `
  --resource operations `
  --limit 500 `
  --format csv `
  --output C:\data\reconciliation-runtime-001\plan-operations.csv
```

Use the following interpretation:

| Operation | Meaning | Safe automatic effect |
| --- | --- | --- |
| `no-op` | Peer already equals selected address | No change |
| `request-missing` | Peer lacks a selected quorum-backed entry | None; request requires a later process |
| `replace-with-consensus` | Peer differs from selected address | None; replacement requires confirmation |
| `manual-review` | Evidence cannot be safely selected | None; human decision required |

The plan is not an executor queue. It is a content-addressed description of
what a governed executor could consider. A consumer must preserve
`evidence_addresses`, inspect `requires_confirmation`, and create a new
registry snapshot after any authorized change.

## 9. Audit each derived document

Resolution audit:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-resolution-audit `
  --input C:\data\reconciliation-runtime-001\resolution.json --format summary
```

Plan audit:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-plan-audit `
  --input C:\data\reconciliation-runtime-001\plan.json --format summary
```

Query audit:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-resolution-query-audit `
  --input C:\data\resolution-query.json --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-plan-query-audit `
  --input C:\data\plan-query.json --format summary
```

An audit with `accepted=true` proves that the public document and its nested
addresses replay. It does not promote a review or blocked outcome to ready.
Always read the audited object's `state` and `release_ready` fields alongside
the audit result.

## 10. Re-run deterministically

To reproduce one handoff, use the same registry bytes, peer IDs, federation ID,
quorum, and runtime ID. The resulting nested addresses and runtime address
should match exactly. The following compares a loaded handoff to its runtime
JSON projection:

```powershell
python -c "import json; from pathlib import Path; from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_runtime as m; p=Path(r'C:\data\reconciliation-runtime-001'); v=m.load_runtime(p); raw=json.loads((p / 'runtime.json').read_text()); assert m.runtime_from_mapping(raw).to_dict() == v.to_dict(); print(v.content_address)"
```

Do not add a timestamp, machine name, or path to a public mapping when trying
to distinguish two runs. Use an explicit runtime ID or preserve the operator
context outside the addressed contract.

## 11. Repair and retry

If directory replay reports a missing or extra member:

1. Stop release processing.
2. Preserve the failed directory as received.
3. Compare the member set to the exact nine-file list.
4. Re-obtain the runtime from its original public inputs.
5. Write the retry to a new destination.
6. Audit the new destination.

If replay reports a non-canonical byte, do not normalize the file in place.
Normalization changes the evidence boundary and can invalidate the manifest.
Rebuild the handoff from the typed public mapping instead.

If an audit reports an address mismatch, retain the failing JSON and its audit
summary. The address identifies the public mapping that no longer replays. A
new runtime should be assigned a new destination, not overwrite the failed
evidence.

## 12. Release decision table

Use this table as the final gate:

| Runtime state | Runtime accepted | Release ready | Decision |
| --- | ---: | ---: | --- |
| `ready` | true | true | Release may proceed to the next governed boundary |
| `review` | true | false | Hold for manual divergence review |
| `blocked` | true | false | Hold for missing/quorum evidence |
| any | false | any | Reject the handoff as structurally unverified |

The runtime can be structurally accepted with `state=blocked` because the
blocked evidence is still valuable and auditable. That does not authorize
release. The release flag is the semantic boundary; it must be true before a
downstream release process proceeds.

## 13. Query design for large registries

Queries are bounded and deterministic. Prefer narrow resources and filters:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-plan-query `
  --input C:\data\reconciliation-runtime-001\plan.json `
  --resource replace-with-consensus `
  --peer-id replica `
  --limit 100 `
  --format csv
```

The query records:

- the source plan address;
- the selected resource vocabulary;
- every explicit filter;
- the original row total;
- the filtered match count;
- the returned page count;
- the offset, limit, next offset, and truncation bit;
- each row's content address.

For a review queue, persist the query JSON and its query audit next to the
runtime. A later consumer can replay the exact page without rebuilding the
source plan.

## 14. Public handoff rules

Public runtime documents may contain labels, counts, states, addresses, and
bounded explanations. They must not contain:

- local paths;
- private keys;
- credentials;
- secrets or access tokens;
- process attribution fields;
- machine-specific environment values;
- unbounded free-form notes.

The source loader may need a path to open a directory, but that path is not
evidence. Keep it at the command boundary. If a consumer needs provenance,
store a separately governed record outside this public content-addressed
closure.

## 15. Extension rules

An executor added later must preserve these invariants:

1. It consumes a verified plan, never a raw source registry.
2. It refuses a plan with a failed audit.
3. It requires confirmation for every non-no-op operation.
4. It never invents a desired address for a blocked request.
5. It never auto-promotes manual review.
6. It writes a new registry snapshot after authorized changes.
7. It records the source plan address in the new snapshot's evidence.
8. It leaves the source runtime immutable.
9. It produces a new content address after every semantic change.
10. It provides a separate audit and replay boundary.

These rules keep the analysis layer stable while retrieval, approval, and
storage systems evolve around it.

## 16. Final checklist

Before handing off a ready runtime, confirm:

- every source registry audit passed;
- peer IDs are stable and unique;
- the quorum is recorded outside and inside the derived addresses;
- the destination contains exactly nine members;
- directory replay passed;
- runtime audit passed all fourteen checks;
- resolution audit passed all fourteen checks;
- plan audit passed all fourteen checks;
- review and blocked queries return no rows;
- every plan operation is a no-op;
- `accepted=true`;
- `release_ready=true`;
- `state=ready`;
- the runtime directory is preserved as the handoff.

If any item is false, stop at the appropriate hold or rejection state and
preserve the addressed evidence for the next review cycle.

## 17. Stable audit identifiers

The fixed identifiers make automated triage stable across export formats:

```text
resolution:
  resolution-linkage
  item-count
  item-order
  state-conservation
  action-state
  selected-replay
  missing-replay
  peer-evidence
  candidate-evidence
  address-links
  consensus-link
  public-boundary
  bounded-input
  resolution-address
plan:
  plan-linkage
  operation-count
  operation-order
  action-conservation
  status-conservation
  matrix-coverage
  confirmation
  address-replay
  source-states
  accepted-state
  evidence
  nested-links
  public-boundary
  plan-address
runtime:
  runtime-linkage
  source-count
  federation-link
  consensus-link
  resolution-link
  plan-link
  federation-audit
  consensus-audit
  resolution-audit
  plan-audit
  outcome-replay
  state-replay
  public-boundary
  runtime-address
```

When an audit check fails, use its evidence addresses first, then inspect the
source JSON that produced them. Check IDs are part of the addressed audit
mapping; changing a detail or evidence list creates a different audit address.
