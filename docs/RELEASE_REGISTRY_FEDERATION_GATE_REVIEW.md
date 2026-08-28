# Release-registry federation gate review

## Purpose

This module is the operational review boundary after release-registry
federation assurance has produced a source gate. It answers a narrow question:
what should a reviewer do with each failed finding or failed release check,
and how can the resulting handling be transported, replayed, and compared
without changing the source decision?

The module deliberately separates three kinds of truth:

1. the source gate says what the verified federation currently means;
2. the review queue says which findings and checks require attention; and
3. the decision ledger says what a reviewer recorded about that attention.

The queue and ledger are therefore operational projections. They do not
rewrite a federation, a release registry, a series-release package, a policy,
an evaluation, an assurance finding, or a gate check. A new authoritative
source gate must be built from a new source package when evidence changes.

## Boundary and non-goals

The review boundary accepts only a persisted release-registry federation gate
in the current package shape. It does not infer a current gate from an older
packet format, guess a missing registry, or silently coerce a legacy package.
This is important for downloaded-data work: a directory can be real and still
be incompatible with this module's contract.

The public projection contains content addresses, stable IDs, bounded text,
state, severity, plane, requiredness, evidence references, and counts. It
does not contain local filesystem paths, usernames, machine names, emails,
sample identifiers, patient identifiers, model metadata, programming
language metadata, or agent metadata. Private inputs may be used by an
adapter before this boundary, but they must not cross into a queue, ledger,
query result, schema, manifest, or export.

The module does not provide a reviewer identity system, a notification
service, a work scheduler, a database, or a scientific remediation engine.
Those systems can consume the addressed packages. The package remains useful
offline and can be verified in a separate CI job.

## End-to-end flow

The operational flow is intentionally linear:

```text
persisted federation gate
          |
          v
  build_review_from_gate_directory
          |
          +--> queue: source findings + source checks
          |
          +--> verification: independent queue checks
          |
          v
       review package
          |
          v
  build_decision_ledger_from_directory
          |
          v
       empty ledger
          |
          +--> append decision with expected head
          |
          v
       replayed ledger
          |
          +--> query operational state
          |
          +--> compare two ledgers
          |
          v
    review decision diff
```

The source gate is read and verified before the queue is built. The queue is
verified before the ledger is built. The ledger is verified before a decision
is appended or a diff is calculated. Every edge in this flow is represented
by a content address in the public documents.

## Module surface

The implementation is in
`src/glio_noncode/assurance_history_series_release_registry_federation_gate_review.py`.
The package exports the typed classes, address functions, builders, mapping
loaders, persistence functions, query functions, renderers, schemas, and
capability projections through `glio_noncode`.

### Queue types

| Type | Role | Mutable? | Address basis |
| --- | --- | --- | --- |
| `FederationReviewItem` | one routed source finding or source check | no | item public projection |
| `FederationReviewQueue` | ordered item snapshot and readiness summary | no | queue summary |
| `ReviewVerificationFinding` | one independent queue check | no | finding public projection |
| `FederationReviewVerification` | verification check rollup | no | verification summary |
| `FederationReviewBundle` | queue plus verification | no | nested addresses |
| `ReviewQuery` | bounded request | no | request projection |
| `ReviewQueryResult` | bounded response | no | response projection |

### Ledger types

| Type | Role | Mutable? | Address basis |
| --- | --- | --- | --- |
| `FederationReviewDecision` | one append-only reviewer action | no | entry projection |
| `FederationReviewReplayItem` | one replayed item state | no | replay-item projection |
| `FederationReviewReplay` | derived item state and source authority | no | replay summary |
| `FederationReviewDecisionLedger` | queue snapshot plus decision chain | no | ledger summary |
| `DecisionQuery` | bounded ledger request | no | request projection |
| `DecisionQueryResult` | bounded ledger response | no | response projection |

### Diff types

| Type | Role | Mutable? | Address basis |
| --- | --- | --- | --- |
| `FederationReviewDiffItem` | one stable item comparison | no | diff-item projection |
| `FederationReviewDecisionDiff` | complete baseline/candidate comparison | no | diff summary |

The type names describe the persisted public contract. They do not imply a
database ORM or an implicit mutable session.

## Queue construction

`build_review_queue` first verifies the source
`FederationAssuranceGateBundle`. It projects every assurance finding before
every release-gate check in source order. The resulting item IDs are scoped by
record type:

```text
finding:<source-finding-id>
check:<source-check-id>
```

The source finding or check address is retained as `source_address`. The
review item has its own content address because the routing projection also
contains review state, priority, and a stable item ID.

The initial queue state is determined by failed items:

| Failed item set | `state` | `accepted` | `release_ready` |
| --- | --- | --- | --- |
| empty | `clear` | `true` | `true` |
| warning-only | `review` | `true` | `false` |
| one or more required failures | `blocked` | `false` | `false` |

The source gate's own `accepted` and `release_ready` values are authoritative
for the queue. The queue does not independently promote a warning, and it
does not turn a required source failure into an accepted release.

Every failed item receives an initial operational state and priority:

| Item | Initial state | Priority |
| --- | --- | --- |
| passed finding/check | `clear` | `none` |
| failed optional finding/check | `open` | `high` |
| failed required finding/check | `blocked` | `critical` |

This distinction is intentionally separate from the source gate's assurance
severity. A source warning is a required review action in an operational
queue, but it is not a source blocker.

## Independent queue verification

`build_review_verification` recomputes the queue contract from the queue and,
when available, from the source gate. It emits ten addressed checks:

| Check | Severity | Recomputed property |
| --- | --- | --- |
| `source-gate-verified` | blocker | source gate is present and linked |
| `source-linkage` | blocker | federation, runtime, and assurance links are conserved |
| `item-counts` | blocker | item and pass/fail totals are conserved |
| `finding-projection` | blocker | all source findings are routed exactly once |
| `check-projection` | blocker | all source checks are routed exactly once |
| `item-addresses` | blocker | item addresses recompute from public fields |
| `state-priority` | blocker | initial state and priority follow source state |
| `queue-public-boundary` | blocker | private fields do not cross the boundary |
| `gate-authoritative` | warning | queue readiness matches the source gate |
| `queue-address` | blocker | queue address recomputes from the summary |

Verification readiness is deliberately independent from queue release
readiness. A held queue can have ten passing verification checks: the queue is
healthy as a transport while the source gate still requires review.

## Exact queue package

The queue package is fixed to four files:

```text
manifest.json
queue.json
items.json
verification.json
```

`queue.json` is the top-level queue summary plus ordered items. `items.json`
is the split item projection used for byte-level conservation. The
verification document holds the independent findings. `manifest.json` records
the package version, boundary, source links, content addresses, exact file
names, and SHA-256-style byte receipts used by the repository's canonical
serialization layer.

The writer follows this sequence:

1. verify the typed bundle;
2. serialize each data document to canonical UTF-8 bytes;
3. compute document receipts;
4. build the manifest from those receipts;
5. create a private staging directory inside the destination parent;
6. write all files with exclusive creation;
7. atomically rename the staging directory into place; and
8. reject a pre-existing non-empty destination unless overwrite is explicit.

The staging prefix is intentionally short for Windows path portability. It is
not part of the public address namespace and is never written to an artifact.

The loader rejects all of the following:

- missing manifest;
- missing queue, item, or verification document;
- an extra file in the package directory;
- a directory where a regular file is required;
- a symlink in the artifact set;
- non-canonical JSON bytes;
- a manifest with a wrong version or boundary;
- a changed document byte receipt;
- a changed nested content address;
- queue/item split-projection drift;
- verification findings with non-contiguous ordinals; and
- any private or forbidden public key.

## Decision ledger semantics

`build_decision_ledger` freezes the queue item sequence and starts with the
sentinel head `INITIAL_HEAD`. An empty ledger is still a complete ledger: it
has a replay, a source link, a head, counts, and a content address.

Each append must identify exactly one queue item by item ID, item address, or
both. Supplying both is preferred because it detects an ID/address mismatch.
The caller must also provide the current head. The append fails if the
expected head differs from the loaded ledger head.

The action vocabulary is fixed:

| Action | Valid source state | Resulting state | Evidence |
| --- | --- | --- | --- |
| `acknowledge` | `open`, `blocked`, `escalated` | `acknowledged` | not allowed |
| `remediate` | `open`, `acknowledged`, `escalated` | `resolved` | required |
| `waive` | `open`, `acknowledged`, `escalated` | `waived` | required |
| `escalate` | `open`, `acknowledged` | `escalated` | not required |
| `reopen` | `resolved`, `waived` | `open` | not required |

Critical blocked items cannot be waived. A remediation of a critical item
records that the review item was handled, but it does not mutate the source
gate's `accepted` or `release_ready` value. This preserves a strong audit
property: operational handling cannot be confused with changed evidence.

The rationale is bounded text and is part of the addressed decision. Evidence
is represented by an address, not by an embedded payload. This keeps the
ledger portable and lets a separate evidence system control access to the
underlying material.

## Replay model

Replay starts one item at its initial state and applies entries in ordinal
order. Each entry must reference the exact queue item address and the
preceding entry head. The replay recomputes:

- the last action and decision address for every item;
- clear, open, blocked, acknowledged, resolved, waived, and escalated totals;
- the queue-level state;
- the source-authoritative accepted value; and
- the source-authoritative release-ready value constrained by unresolved
  operational states.

Replay state rules are fail-closed:

```text
source not accepted                 -> blocked
blocked replay item exists           -> blocked
source not release-ready             -> review
open/acknowledged/escalated exists   -> review
otherwise                            -> clear
```

The ledger's top-level `accepted` remains the source gate's accepted value.
The ledger's release-ready value is the source release-ready value only when
the replay has no blocking or open operational item. In particular, a
warning-only source gate remains not release-ready until the operational
queue is resolved or evidence-backed handling is recorded. A source blocker
can never be operationally waived into a promoted ledger.

## Exact ledger package

The ledger package is fixed to four files:

```text
manifest.json
ledger.json
entries.json
replay.json
```

`ledger.json` contains the frozen queue item list and ledger summary.
`entries.json` contains the append-only decision chain. `replay.json`
contains the derived state. The manifest binds all three documents and the
queue, gate, assurance, ledger, and replay addresses.

The loader reconstructs the ledger from the split documents, then verifies
the decision chain, replay, counts, nested addresses, and manifest bytes.
It does not accept only the top-level summary as proof of a valid chain.

## Decision diffs

`build_decision_diff` compares two verified ledgers. It keys rows by stable
queue item ID, not ordinal, so inserting an unrelated item does not produce
false changes for every subsequent row.

| Baseline row | Candidate row | Action |
| --- | --- | --- |
| absent | present | `added` |
| present | absent | `removed` |
| present with same state/head | present with same state/head | `unchanged` |
| present with different state/head | present with different state/head | `changed` |

For a row present in both snapshots, direction is derived from operational
state scores. Improvements and regressions are reported separately from the
top-level candidate release projection. A diff is analysis-only: it never
rewrites either source ledger.

The diff package is fixed to two files:

```text
manifest.json
diff.json
```

## Query contract

Queue query resources are:

```text
summary, items, findings, checks, open, blockers, warnings,
clear, passed, failed
```

Queue filters include record type, plane, severity, item state, priority,
passed, required, text, offset, and limit. Text matching is case-insensitive
and bounded. Results are deterministically ordered by source ordinal.

Ledger query resources are:

```text
summary, items, entries, decisions, open, resolved, waived, escalated
```

Ledger filters include item ID, action, replay state, text, offset, and limit.
Ledger item rows include the frozen item projection plus the replayed last
action and last state. Entry rows preserve the full decision ancestry.

Every query has a typed request and result address. A result cannot contain
more rows than its limit, and the returned rows are checked for public-boundary
closure before an address is assigned.

## CLI contract

The CLI uses the long-form module-workbench command family so the boundary is
discoverable beside the existing registry, federation, and gate commands.
The base review command is:

```text
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry-federation-gate-review
```

The following suffixes are available:

| Command suffix | Input | Output |
| --- | --- | --- |
| none | persisted source gate directory | review bundle |
| `-verify` | persisted review directory | verification summary |
| `-query` | persisted review directory | bounded query |
| `-schema` | none | review bundle schema |
| `-queue-schema` | none | queue schema |
| `-item-schema` | none | item schema |
| `-verification-schema` | none | verification schema |
| `-verification-finding-schema` | none | finding schema |
| `-query-schema` | none | queue query schema |
| `-manifest-schema` | none | manifest schema |
| `-capabilities` | none | capability projection |
| `-decision-ledger` | persisted review directory | empty ledger |
| `-decision-ledger-append` | persisted ledger directory | appended ledger |
| `-decision-ledger-verify` | persisted ledger directory | verification summary |
| `-decision-ledger-query` | persisted ledger directory | bounded query |
| `-decision-ledger-schema` | none | ledger schema |
| `-decision-ledger-decision-schema` | none | decision schema |
| `-decision-ledger-replay-schema` | none | replay schema |
| `-decision-ledger-query-schema` | none | ledger query schema |
| `-decision-ledger-capabilities` | none | ledger capabilities |
| `-decision-ledger-diff` | baseline and candidate ledgers | diff |
| `-decision-ledger-diff-verify` | persisted diff directory | verification summary |
| `-decision-ledger-diff-schema` | none | diff schema |
| `-decision-ledger-diff-item-schema` | none | diff-item schema |
| `-decision-ledger-diff-capabilities` | none | diff capabilities |

Build and verify a queue:

```text
python -m glio_noncode <review-command> \
  --input ./gate \
  --queue-id queue:downloaded-review \
  --destination ./review \
  --format summary

python -m glio_noncode <review-command>-verify \
  --input ./review

python -m glio_noncode <review-command>-query \
  --input ./review \
  --resource failed \
  --limit 50 \
  --format markdown
```

Build and append a ledger:

```text
python -m glio_noncode <review-command>-decision-ledger \
  --input ./review \
  --ledger-id ledger:downloaded-review \
  --destination ./ledger \
  --format summary

python -m glio_noncode <review-command>-decision-ledger-append \
  --input ./ledger \
  --item-id finding:source-release-ready \
  --action remediate \
  --rationale "validation evidence is attached for the next source run" \
  --evidence-address evidence:downloaded-review-1 \
  --expected-head initial:release-registry-federation-gate-review \
  --destination ./ledger-next \
  --format summary
```

The exact initial-head value is exposed by the ledger summary and should be
copied from that verified result. It is shown symbolically above to keep the
runbook independent of a particular content-address version.

Compare two snapshots:

```text
python -m glio_noncode <review-command>-decision-ledger-diff \
  --baseline ./ledger \
  --candidate ./ledger-next \
  --destination ./diff \
  --format markdown
```

The CLI returns status `0` for a release-ready build or verification and
status `2` for an accepted-but-held or blocked source state. The output is
still written in the latter cases; CI can therefore archive the review
package while failing the release step.

## HTTP contract

The HTTP family is rooted at the existing module-workbench release-registry
federation gate review path:

```text
/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review
```

GET routes include:

| Route | Behavior |
| --- | --- |
| base | build a review from `gate` or `input` |
| `/queue` | return queue projection |
| `/verify` | load and verify a review package |
| `/query` | run a bounded queue query |
| `/schema` | review schema |
| `/queue-schema` | queue schema |
| `/item-schema` | item schema |
| `/verification-schema` | verification schema |
| `/verification-finding-schema` | verification finding schema |
| `/query-schema` | queue query schema |
| `/manifest-schema` | manifest schema |
| `/capabilities` | capability projection |
| `/decision-ledger` | build a ledger from `input` or `review_directory` |
| `/decision-ledger/verify` | verify a ledger directory |
| `/decision-ledger/query` | query a ledger directory |
| `/decision-ledger/schema` | ledger schema |
| `/decision-ledger/decision-schema` | decision schema |
| `/decision-ledger/replay-schema` | replay schema |
| `/decision-ledger/query-schema` | ledger query schema |
| `/decision-ledger/capabilities` | ledger capabilities |
| `/decision-ledger/diff` | compare `baseline` and `candidate` ledgers |
| `/decision-ledger/diff/verify` | verify a diff directory |
| `/decision-ledger/diff/schema` | diff schema |
| `/decision-ledger/diff/capabilities` | diff capabilities |

The append operation is POST-only at:

```text
<review-prefix>/decision-ledger/append
```

Its JSON body is:

```json
{
  "directory": "./ledger",
  "item_id": "finding:source-release-ready",
  "action": "remediate",
  "rationale": "validation evidence is attached for the next source run",
  "evidence_address": "evidence:downloaded-review-1",
  "expected_head": "<head from verified ledger>",
  "destination": "./ledger-next",
  "overwrite": false
}
```

`directory` and `expected_head` are required. `item_address` can be supplied
alongside `item_id`. If `destination` is omitted, the updated ledger is
returned without filesystem mutation. If `destination` is supplied, the same
exact package writer used by the CLI is invoked.

POST responses return `200` for release-ready state, `422` for accepted-but-
held or blocked state, `400` for malformed payloads, and `422` for typed
contract failures such as stale heads, invalid actions, missing evidence, or
forbidden waivers.

## Downloaded-data procedure

The review module consumes artifacts already verified by the preceding
release-registry and federation layers. It does not download data itself.
That keeps network access, license declarations, and source adapters outside
the operational decision boundary.

Use this procedure for a real download:

1. preserve the original download directory read-only;
2. inspect the directory shape without editing it;
3. load the current release-registry package with its module loader;
4. persist each verified registry package in a portable directory;
5. build and persist federation from those verified registries;
6. build and persist the independent federation gate;
7. build and persist this review queue from the gate;
8. verify the queue in a separate process;
9. build and persist the empty decision ledger;
10. append only decisions that have an expected head;
11. verify the resulting ledger after each transport; and
12. retain the queue, ledger, and diff packages as CI artifacts.

The boundary must reject older downloaded shapes with a clear validation
error. “Real downloaded data” means the input came from a download; it does
not mean an incompatible historical artifact should be converted without an
explicit adapter.

## Failure matrix

| Failure | Detection point | Expected behavior |
| --- | --- | --- |
| source gate directory absent | load | validation error |
| source gate contains extra file | load | validation error |
| source gate byte changed | source loader | validation error |
| queue item ID duplicated | build | validation error |
| queue item address changed | verify | failed verification |
| source gate link changed | verify | failed verification |
| queue counts changed | verify | failed verification |
| optional warning present | queue state | accepted, held, review |
| required failure present | queue state | blocked, not accepted |
| ledger item not found | append | validation error |
| item ID/address disagree | append | validation error |
| stale expected head | append | validation error |
| unknown action | append | validation error |
| acknowledge with evidence | append | validation error |
| remediate without evidence | append | validation error |
| waive without evidence | append | validation error |
| blocker waiver | append | validation error |
| invalid transition | append | validation error |
| entry predecessor changed | load | validation error |
| replay state changed | load | validation error |
| ledger file missing | load | validation error |
| ledger extra file | load | validation error |
| diff input unverified | diff | validation error |
| diff item address changed | diff load | validation error |
| query limit is zero | query | validation error |
| query offset is negative | query | validation error |
| query result exceeds limit | result verify | validation error |
| private key in projection | build or verify | validation error |
| symlink artifact | load | validation error |
| non-canonical JSON | load | validation error |
| non-empty destination | write | validation error unless overwrite |

The matrix is part of the test design, not just documentation. Each critical
row has a focused regression or is exercised by the shared persistence
failure helpers.

## Test coverage

The focused test module is
`tests/test_assurance_history_series_release_registry_federation_gate_review.py`.
It covers the following layers:

| Layer | Coverage |
| --- | --- |
| construction | ready, held, blocked, findings, checks, stable IDs |
| verification | source linkage, counts, priorities, addresses, public boundary |
| persistence | exact files, byte receipts, reload, overwrite, tamper, symlink |
| queue query | resources, filters, text, pagination, invalid bounds |
| ledger construction | initial head, replay, source authority, counts |
| ledger actions | acknowledge, remediate, waive, escalate, reopen |
| ledger policy | evidence, blocker waiver, stale head, invalid transition |
| ledger persistence | split files, receipts, ancestry, replay, tamper |
| ledger query | summary, items, entries, state partitions, exports |
| diff | unchanged, changed, added, removed, improved, regressed |
| CLI | build, verify, query, append, diff, schema, capabilities |
| HTTP | build, queue query, ledger query, schema, capabilities, append |
| public surface | forbidden keys, path leakage, mapping strictness |

The test fixture constructs current-format source gate bundles through the
repository's existing federation gate fixture. It does not clone an older
repository or use an older repository as a framework. For external data, the
same assertions run after the upstream persisted package has been verified.

## Performance and scaling

The module is bounded by design. Maximum queue items, verification findings,
decisions, and query rows are enforced before allocation grows beyond the
contract. Source item projection is linear in the number of assurance
findings plus gate checks. Replay is linear in queue items plus decision
entries. A diff builds two maps and sorts the union of stable item IDs.

Canonical serialization happens once per document during a write. The writer
does not serialize through a platform-default text encoding. Query renderers
operate on bounded results, so Markdown and CSV output cannot expand without
limit validation.

The main optimization boundary is persistence: queue items and ledger entries
are split into independently addressed documents so a transport verifier can
check exact bytes without re-reading unrelated source payloads. This also
makes CI artifact inspection predictable.

The module avoids caching values whose source address could become stale. A
caller that needs a cache can key it by the verified source gate address and
queue address. The ledger head is an explicit cache-busting token for append
operations.

## Public-boundary rules

The forbidden-key set is shared with the surrounding release layers. Review
objects are checked recursively. The check covers mappings, sequences,
dataclasses, and the values returned by schemas and capabilities. The
following values are especially important to keep out of this layer:

- local path strings;
- host and user names;
- email and phone values;
- medical or participant identifiers;
- sample and subject identifiers;
- model and model-version strings;
- assistant and agent fields;
- programming-language fields; and
- free-form payloads copied from a private source.

Evidence addresses are references, not evidence payloads. Rationale text is
reviewer-facing but bounded and should describe an action, not embed private
records.

## CI integration

Actions should run the focused review test module, schema commands, and a
tamper path. A representative job sequence is:

```text
python -m unittest tests.test_assurance_history_series_release_registry_federation_gate_review -v
python -m glio_noncode <review-command>-schema
python -m glio_noncode <review-command>-decision-ledger-schema
python -m glio_noncode <review-command>-decision-ledger-diff-item-schema
```

The focused test job must remain independent from any private data mount.
Downloaded-data verification can run as a separate artifact job when a
current-format package is available. The public CI path should still prove
construction, exact-byte transport, query determinism, and failure closure.

## Operational checklist

Before accepting a review package:

- confirm the source gate directory was verified;
- record the source gate address;
- verify the queue package in a clean process;
- inspect blockers and warnings separately;
- confirm the queue state matches the source gate;
- initialize the ledger from the queue snapshot;
- copy the exact current head before an append;
- require an evidence address for remediation and waiver;
- reject waiver attempts for critical blockers;
- persist the updated ledger to a new destination when possible;
- verify the updated ledger and replay; and
- compare the previous and current ledger with a diff package.

Before publishing any review artifact:

- inspect the manifest file set;
- verify canonical bytes;
- verify every nested address;
- scan the public projection for forbidden keys;
- ensure no source path appears in JSON, CSV, or Markdown;
- ensure CI preserves the exact package directory; and
- retain the failure result if the source is held or blocked.

## Troubleshooting

### “download root contains no exact release-registry packages”

The input is not the current release-registry package shape. Preserve the
download and run the upstream adapter or loader that creates a verified
current package. Do not rename files until the package contract is understood.

### “review verification linkage is invalid”

The queue and independent verification refer to different queue or gate
addresses. Rebuild the review from one verified source gate, or inspect the
exact bytes for tampering.

### “decision ledger expected head does not match”

Another append has produced a newer head, or the caller copied a head from a
different ledger. Reload and verify the current ledger, then retry with its
exact head. Do not disable the guard.

### “decision evidence address is required”

Remediation and waiver are evidence-bearing transitions. Supply a stable
address to an external evidence record. Do not place private evidence in the
ledger.

### “critical blocker cannot be waived”

This is an intentional fail-closed rule. Use acknowledge, remediate with
evidence, or escalate. If the underlying source evidence changes, build a new
source gate and a new queue snapshot.

### “destination is not empty”

The package writer is append-safe by default. Use a new destination for a new
snapshot. Explicit overwrite is available for controlled local regeneration,
but the resulting package must still be reloaded and verified.

## Design invariants

The following invariants are expected to remain true as the module evolves:

1. source gate acceptance is never inferred from a reviewer action;
2. source gate release readiness is never promoted by a ledger waiver;
3. every queue item is linked to exactly one source finding or check;
4. every ledger entry links to exactly one frozen queue item;
5. every entry predecessor is the previous head;
6. every replay is reproducible from queue plus entries;
7. every persisted byte receipt is checked on load;
8. every public address is recomputable from public fields;
9. every query is bounded and deterministically ordered;
10. every diff is analysis-only over verified inputs;
11. every blocker waiver attempt fails closed; and
12. no path, agent, model, or language metadata crosses the boundary.

Changes that violate one of these invariants require a versioned contract
change, an updated schema, an updated capability projection, a migration or
explicit rejection rule, a failure test, and a roadmap entry.

## Extension points

Future operational integrations can build on the existing contracts without
embedding private infrastructure:

- a reviewer assignment projection keyed by item address;
- a notification projection keyed by ledger head;
- a signed external evidence receipt keyed by evidence address;
- a batch append planner that still checks one expected head;
- a release-board view over queue and ledger query results;
- a retention index for immutable review packages; and
- an audit export that records API request hashes outside the package.

Each extension should keep its own package and address namespace. It should
not add private fields to the current queue or ledger documents. It should
also preserve the distinction between source authority and operational
handling.

## Completion definition

This module is considered implemented only when all of the following remain
true together:

- source gate loading is strict;
- queue construction is deterministic;
- independent queue verification is available;
- exact queue persistence reloads successfully;
- queue queries and exports are bounded;
- ledger construction starts at a known head;
- all action transitions are validated;
- evidence rules and blocker waiver rules are enforced;
- optimistic concurrency is enforced;
- replay is independently checked;
- exact ledger persistence reloads successfully;
- ledger queries and exports are bounded;
- decision diffs compare stable keys;
- CLI and HTTP surfaces expose the public contracts;
- schemas and capabilities enumerate the boundary;
- public-surface audit counts the new contracts;
- CI runs focused regression coverage; and
- at least one current-format downloaded-data package can be verified
  without exposing private source metadata.

The final condition is intentionally phrased as a package verification
requirement. It does not claim that every downloaded artifact found in the
wild is compatible with the current contract.

The detailed maintenance matrix is in
[RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_MATRIX.md](RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_MATRIX.md).
