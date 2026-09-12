# Architecture

The first slice is organized as a deterministic pipeline:

```text
case manifest
    │
    ├── identity and contract checks
    ├── context comparison
    ├── candidate element and evidence readings
    ├── dependence-aware edge aggregation
    ├── decomposed hypotheses
    ├── validation-route planning
    ├── optional live reference bundles + Atlas replay-input/bundle pairs and claims
    ├── policy and release checks
    └── content-addressed dossier + hash-chained event log
```

## Canonical objects

`CaseManifest` is the immutable input boundary. `VariantIdentity` stores normalized coordinates, origin, clonality, and adapter annotations. `ReferenceContext` is required before evidence can be interpreted. `EvidenceClaim` is append-only and belongs to one edge. `HypothesisEdge` retains claim IDs, support, uncertainty, and context fit. `Hypothesis` keeps the complete variant-element-gene-state path visible. `Dossier` is the replayable output snapshot.

## Evidence aggregation

Evidence channels are grouped by shared assumptions before they are combined. The strongest claim in a channel group contributes more than repeated correlated claims, measured negatives reduce support without erasing positives, and missing or out-of-domain claims increase uncertainty. This is a conservative baseline, not a validated causal model.

## Context transport

The context matcher scores genome build, disease class, age group, cell state, territory, and treatment phase separately. A mismatch remains visible in the claim payload. A transferred reference is not represented as an exact match.

## Persistence

Callback-driven runtime, Atlas, and public-reference operations share one
process-local re-entrant isolation lock before taking any component instance lock.
This ordering serializes the package-wide semantic snapshots used by those surfaces,
so one operation cannot accept another callback's temporary module or class state as
its baseline. A runtime evaluation cannot nest another runtime evaluation on the same
thread, even when the second evaluation uses a different `CaseRuntime` instance or is
started inside a fresh `contextvars.Context`. Runtime instance shells are canonical at
capture time, and recovery restores
the exact classes and namespace identities of configured objects before restoring
their fields; a callback cannot leave method shadows or hostile setters installed.

This is an in-process integrity and rollback boundary for ordinary Python extension
callbacks, not a security sandbox. Code deliberately traversing private function
closures, manipulating interpreter internals, or using native memory access shares the
host process and is outside the guarantee; run such code in a separate process when it
must be treated as hostile.

Adapter discovery and execution deliberately use different registry views. The
discovery endpoint exposes the full configured projection and effective limits;
each run captures its selected-execution projection atomically, with every selected
adapter's complete addressed metadata embedded in the claim report. The adapter
objects selected in that same capture remain identity-pinned across all callbacks;
substitution fails the run and restores those selected registry slots while unrelated
registrations remain available. The adapter
event contains four ordered record roles: the base manifest, selected registry
snapshot, resolution report, and attributed claim-collection report. The global
dossier source list is first-use ordered and deduplicates an exact record reused by
another stage. Adapter source events must precede hypothesis construction in the
canonical lifecycle.

The optional source closure has two byte boundaries: 128 MiB for any one persisted
source object and 256 MiB across the unique RNA, reference, Atlas, and adapter records
retained by a run. Every variant contributes one ordered Atlas pair: an external,
detached `AtlasReplayInputs` record followed immediately by the `AtlasBundle` derived
from it. Either byte limit may be configured lower. The hard/default ceiling for the
ordered, unique source-address list remains 3,006: one RNA batch, one submitted
manifest, one reference bundle, one detached Atlas replay-input artifact, and one Atlas
bundle for each of at most 1,000 variants, plus four adapter roles.

Charging is progressive at runtime stage boundaries. The submitted manifest is
admitted before reference enrichment. The runtime cannot interrupt a source callback
already in flight; it checks each complete returned result before later runtime work.
RNA consequence iterators are detached and charged one canonical row at a time, so a
byte ceiling stops further consumption instead of first expanding the full batch.
Retained reference bundles are admitted before Atlas collection. Before each Atlas
callback, admission reserves the two source-address slots for its replay-input/bundle
pair. The returned replay input and bundle are detached and validated together, then
retained in that order; both must fit the object and aggregate byte limits before the
next variant callback. Adapter base and registry records, then the resolution report,
are admitted before the later adapter phases. The source-receipt
ceiling is 256,000 ordered reference and atlas occurrences. A hard/default 10,000
external-claim allowance is shared by linked atlas claims and adapter claims. Both
count ceilings may be configured lower.

Each limit blocks only later work that could consume it. Source byte/address capacity
gates all later source stages; receipt capacity, accumulated source-warning capacity,
and Atlas event-payload capacity gate later atlas calls; and external-claim capacity
gates later claim-producing atlas calls and adapter claim callbacks. Unpromoted atlas
observations consume no claim slot, and adapter resolution can run before claim
collection encounters a zero remainder. A failure still prevents publication of a
partial run.

Replay does not trust only the final manifest. It rehydrates the exact submitted
manifest and every per-variant reference bundle. Each reference bundle includes a
versioned address over every canonical `ReferenceContext` field, avoiding aliases from
its human-readable key. The Atlas event supplies equal-length, variant-ordered
`replay_input_addresses` and `bundle_addresses` arrays. Replay validates their shape,
order, uniqueness, and pairwise correspondence, then interleaves each replay-input
record immediately before its bundle in the declared source closure. It reconstructs
each `AtlasReplayInputs` artifact against the exact full `VariantIdentity`,
`ReferenceContext`, retained reference bundle, and `AtlasQuery` before accepting the
bundle's replay-input binding. Offline semantic replay then rederives sequence and motif
analysis, declared-track reports and observations, ENCODE projection or abstention,
receipt and warning closure, the
receipt-derived timestamp, out-of-domain and uncertainty outputs, and evidence claims;
all retained outputs and dossier claims must match. It also replays all four adapter
records, including the selected metadata snapshot and claim attribution. Receipt replay compares
the exact ordered occurrence sequence, with reference receipts before atlas receipts;
identical occurrences may repeat, but conflicting definitions for one request hash fail
validation. Reference events must contain all bundle warnings and keep every event
warning in the dossier,
although additional enrichment-level warnings cannot be reconstructed from bundles.
Atlas event warnings must exactly match the deduplicated bundle and claim-link warnings
and also remain in the dossier. Source-event order, identities, payload fields, and
derived counters are verified. Unverifiable legacy live-source closures and older
adapter report versions fail closed and should be recomputed from their original
inputs. Immutable offline runs remain readable when their current canonical, address,
event, and cross-link contracts verify.

JSON objects are written under SHA-256 addresses. The run index records the input,
event-log, and dossier addresses plus append-only event and dossier histories. Every new
review or assignment snapshot first appends a canonical predecessor-binding event that
authenticates both prior addresses; historical assessment therefore fails closed when
old history lacks a successor binding. The loader validates the entire retained modern
suffix, including exact event prefixes, paired dossier addresses, transition order, and
the latest typed review. A rollback of the complete mutable index is indistinguishable
from a legacy-normalized index without an external monotonic anchor, so deployments
needing rollback resistance must anchor run heads outside this store.

Optional live evaluation stores the submitted manifest, exact per-variant public
reference bundles, ordered Atlas replay-input/bundle pairs, source receipts, and source
warnings. Generic public
annotations remain reference-tier claims. A selected runtime evidence adapter retains
the base manifest, atomic selected-registry snapshot, resolution report, and attributed
claim-collection report before producing the effective manifest, so source identity
and claims remain replayable rather than being trusted from the in-memory adapter.

Runtime events form a chain so replay can detect order changes or altered payloads.
`storage-audit` checks canonical bytes, address drift, index pointers, replay state,
missing references, and orphan objects without repairing the store. `portfolio-release`
composes bounded multi-run dossier/workspace handoff closures while retaining per-run
gate evidence and blocked-member diagnostics; its filesystem verifier checks exact
UTF-8 bytes, namespaced paths, member closure, and public-boundary safety. The
repository-wide module-fabric runtime now has a separate 21-artifact offline bundle
with manifest-address reconstruction, byte-level verification, record/artifact queries,
deterministic observability, replay stages, and an independent cross-artifact audit. The
D13 validation-design runtime now has a deterministic 27-artifact offline bundle with
normalized timing receipts, byte verification, bounded queries, schema validation, and
cross-artifact reconciliation. The D14 evidence-lifecycle runtime now has a
deterministic 21-artifact offline bundle with fixture, evaluation, review, queue,
release, observability, and runtime closure; it preserves 16 records, 120 checks, 26
events, exact bytes, replay stability, and the public boundary. The D15
workbench-release runtime now has a deterministic 56-artifact offline bundle with all
49 runtime stages, 26 root closure checks, 80 evaluation checks, five source receipts,
operation and denominator indexes, public-key auditing, byte verification, bounded
queries, and independent reconciliation. The review-workspace execution runtime adds a
separate append-only plan ledger with dependency-aware replay, required-check completion
gates, bounded status queries, deterministic exports, and tamper-evident filesystem
manifests.
`public-surface-audit` closes the remaining projection boundary by checking the 99 named
service, schema, bundle, and closure outputs as one addressed inventory. The public
mission-plan receipt is a separate lossy projection over internal planning: it retains
dependency-safe workflow shape, resources, review state, aggregate counts, and content
addressing while excluding routing identifiers and raw request metadata. Its release
plane packages five exact-byte artifacts with independent manifest, receipt, check,
workflow, and resource verification; bounded offline queries, structural diffs, a
staged runtime, aggregate observability, addressed lineage, configurable policy gates,
multi-release catalogs, catalog diffs, semantic audits, aggregate catalog reports,
policy-gated catalog handoffs, timestamp-free gate runtime rehearsal, eight-artifact
gate packets, bounded gate-check queries, gate-to-gate structural diffs, aggregate gate
observability, and public conformance replay preserve the same boundary without
executing handlers. The storage layer is local and intentionally uncomplicated; a
future database adapter must preserve immutable addresses, history semantics, and event
ordering.

The public service-release registry now sits above the cached service snapshot.
It composes six accepted aggregate surfaces, 13 exact-byte artifacts, 15
dependencies, 24 gates, 78 events, 24 metrics, five reviewer views, eight
negative controls, and a fourteen-stage replayable runtime. The registry is
included in the repository-wide public-surface audit and preserves immutable
addresses at every child boundary.

Mission-plan release catalogs add a cross-release public inventory above the
single-release handoff. Catalog queries, evolution diffs, semantic audits, and
aggregate reports conserve release identities and counts while remaining
offline, content-addressed, and free of planner execution or private metadata.

## API

The deployment profile is the institutional boundary for the API: loopback is
the default, while non-loopback binds require API-key scopes, TLS intent,
rate limiting, declared principals, and a redacted audit ledger. The profile
and schema are included in the repository-wide public projection audit.

The dependency-free local HTTP API exposes health, schema, and evaluation endpoints. It is not an internet-facing service by itself. The deployment profile boundary now enforces API-key authentication, scoped authorization, rate limiting, and redacted audit export before a private or public bind is accepted; see [deployment profiles](DEPLOYMENT_PROFILES.md).
