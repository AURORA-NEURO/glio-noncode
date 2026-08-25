# D14 Evidence Lifecycle Offline Handoff

This build adds a portable release boundary for the public aggregate evidence
lifecycle surface. It is a research-operational handoff for citation
resolution, graph construction, edge validation, and disagreement tracking.
It is not a clinical conclusion, diagnostic result, treatment recommendation,
patient-level output, or individual risk estimate.

## Closed artifact set

The handoff contains 21 exact-byte artifacts plus the root `bundle.json`
manifest:

1. `fixture.json` and `catalog.json` preserve the 16 public aggregate records,
   five HTTPS source receipts, four operation families, and the balanced
   positive/control layout.
2. `data-audit.json`, `contracts.json`, and `schema.json` preserve the input
   boundary and typed operation contract.
3. `evaluation.json`, `metrics.json`, `policy.json`, `lineage.json`,
   `reconciliation.json`, and `quality.json` preserve execution and gate
   evidence.
4. `bundle.json.payload`, `replay.json`, and `release.json` preserve release
   state, replay address, allowed uses, and excluded uses.
5. `review.json`, `review-queue.json`, `artifacts.json`, and
   `scenario-matrix.json` preserve human review and lineage projections.
6. `observability.json`, `review.csv`, and `runtime.json` preserve 26
   structured events, a 16-row tabular projection, and the normalized ten-stage
   runtime trace.

Every artifact has a media type, safe relative path, UTF-8 byte count, line
count, and exact-byte content address. Runtime wall-clock durations are
normalized before publication, so the root bundle address is stable across
replay and host timing.

## Verification and audit

`evidence-lifecycle-offline-bundle-verify` checks canonical manifest bytes,
manifest address reconstruction, safe paths, artifact bytes, hashes, counts,
and public-key closure. `evidence-lifecycle-offline-bundle-audit` independently
reconciles fixture, evaluation, runtime, observability, release, replay,
review, queue, and artifact-inventory projections. It rejects denominator drift
for the 16 records, 120 evaluation checks, 26 events, and 10 runtime stages.

The `records`, `checks`, `sources`, `events`, and `artifacts` query resources
are bounded and deterministic. Query results can be exported to stable CSV.
The service API exposes the same schema, query, audit, observability, runtime,
and bundle projections under `/v1/evidence-lifecycle/bundle`. Additional
offline-only projections provide address-only indexes, explicit public-boundary
findings, denominator reconciliation, and a compact reviewer summary:

```powershell
glio-noncode evidence-lifecycle-offline-bundle-indexes lifecycle-bundle --output lifecycle-indexes.json
glio-noncode evidence-lifecycle-offline-bundle-boundary lifecycle-bundle --output lifecycle-boundary.json
glio-noncode evidence-lifecycle-offline-bundle-reconciliation lifecycle-bundle --output lifecycle-reconciliation.json
glio-noncode evidence-lifecycle-offline-bundle-summary lifecycle-bundle --format markdown --output lifecycle-summary.md
```

Indexes store only public identifiers, artifact locations, and addresses; they
never copy operation payloads. Boundary findings separately check public keys,
safe paths, symlink and hidden-file shape, extra-file closure, and review CSV
headers. Reconciliation joins fixture, catalog, evaluation, metrics, lineage,
release, replay, review, queue, observability, and runtime artifacts.

The public projection removes and rejects agent, assistant, author, model,
language, contact, subject, patient, sample, participant, and medical-record
keys. Data permitted by this boundary is aggregate research evidence only.
