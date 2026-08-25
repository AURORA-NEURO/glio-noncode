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

JSON objects are written under SHA-256 addresses. The run index records the input, event-log, and dossier addresses plus append-only event and dossier histories. Optional live evaluation also stores public reference and atlas bundles, source receipts, and their warnings; generic public annotations remain reference-tier claims. Runtime events form a chain so replay can detect order changes or altered payloads. `storage-audit` checks canonical bytes, address drift, index pointers, replay state, missing references, and orphan objects without repairing the store. The storage layer is local and intentionally uncomplicated; a future database adapter must preserve immutable addresses, history semantics, and event ordering.

## API

The dependency-free local HTTP API exposes health, schema, and evaluation endpoints. It is not an internet-facing service by itself. Authentication, authorization, rate limiting, and audit export belong at the deployment boundary before binding to a non-loopback interface.
