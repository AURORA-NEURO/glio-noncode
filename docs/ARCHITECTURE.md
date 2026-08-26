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
    ├── optional live public reference + atlas bundles and reference-tier claims
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

JSON objects are written under SHA-256 addresses. The run index records the input, event-log, and dossier addresses plus append-only event and dossier histories. Optional live evaluation also stores public reference and atlas bundles, source receipts, and their warnings; generic public annotations remain reference-tier claims. Runtime events form a chain so replay can detect order changes or altered payloads. `storage-audit` checks canonical bytes, address drift, index pointers, replay state, missing references, and orphan objects without repairing the store. `portfolio-release` composes bounded multi-run dossier/workspace handoff closures while retaining per-run gate evidence and blocked-member diagnostics; its filesystem verifier checks exact UTF-8 bytes, namespaced paths, member closure, and public-boundary safety. The repository-wide module-fabric runtime now has a separate 21-artifact offline bundle with manifest-address reconstruction, byte-level verification, record/artifact queries, deterministic observability, replay stages, and an independent cross-artifact audit. The D13 validation-design runtime now has a deterministic 27-artifact offline bundle with normalized timing receipts, byte verification, bounded queries, schema validation, and cross-artifact reconciliation. The D14 evidence-lifecycle runtime now has a deterministic 21-artifact offline bundle with fixture, evaluation, review, queue, release, observability, and runtime closure; it preserves 16 records, 120 checks, 26 events, exact bytes, replay stability, and the public boundary. The D15 workbench-release runtime now has a deterministic 56-artifact offline bundle with all 49 runtime stages, 26 root closure checks, 80 evaluation checks, five source receipts, operation and denominator indexes, public-key auditing, byte verification, bounded queries, and independent reconciliation. The review-workspace execution runtime adds a separate append-only plan ledger with dependency-aware replay, required-check completion gates, bounded status queries, deterministic exports, and tamper-evident filesystem manifests. `public-surface-audit` closes the remaining projection boundary by checking the 73 named service, schema, bundle, and closure outputs as one addressed inventory. The public mission-plan receipt is a separate lossy projection over internal planning: it retains dependency-safe workflow shape, resources, review state, aggregate counts, and content addressing while excluding routing identifiers and raw request metadata. Its release plane packages five exact-byte artifacts with independent manifest, receipt, check, workflow, and resource verification; bounded offline queries, structural diffs, a staged runtime, aggregate observability, addressed lineage, and configurable policy gates preserve the same boundary without executing handlers. The storage layer is local and intentionally uncomplicated; a future database adapter must preserve immutable addresses, history semantics, and event ordering.

The public service-release registry now sits above the cached service snapshot.
It composes six accepted aggregate surfaces, 13 exact-byte artifacts, 15
dependencies, 24 gates, 78 events, 24 metrics, five reviewer views, eight
negative controls, and a fourteen-stage replayable runtime. The registry is
included in the repository-wide public-surface audit and preserves immutable
addresses at every child boundary.

## API

The deployment profile is the institutional boundary for the API: loopback is
the default, while non-loopback binds require API-key scopes, TLS intent,
rate limiting, declared principals, and a redacted audit ledger. The profile
and schema are included in the repository-wide public projection audit.

The dependency-free local HTTP API exposes health, schema, and evaluation endpoints. It is not an internet-facing service by itself. The deployment profile boundary now enforces API-key authentication, scoped authorization, rate limiting, and redacted audit export before a private or public bind is accepted; see [deployment profiles](DEPLOYMENT_PROFILES.md).
