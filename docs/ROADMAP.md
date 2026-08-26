# Build sequence

## Foundation delivered

- typed case, context, variation, evidence, hypothesis, validation, review, and dossier objects;
- deterministic baseline scoring with source-group dependence correction;
- event-sourced local persistence and content-addressed replay checks;
- a dependency-free CLI and loopback HTTP API;
- first-class structural-event paths, matched cohort controls, causal sensitivity, reclassification, workflow compilation, data controls, monitoring, and quality metrics;
- synthetic fixture coverage and an Actions quality matrix.

## Next implementation wave

1. Add a versioned reference manifest and adapter conformance tests. **Implemented:** addressed source receipts, access/license/context declarations, deterministic query/export projections, portable static-adapter probes, API/CLI surfaces, and fail-closed conformance states.
2. Add streaming VCF/BCF and bounded breakend import with explicit normalization reports. **Implemented:** line- and block-streamed source traversal, complete-source and header hashes, bounded row/issue retention, multiallelic and genotype policy controls, raw/BGZF BCF framing, deterministic row receipts, and explicit breakend mate-coordinate outcomes are available through the CLI and API. See [docs/STREAMING_VARIANT_IMPORT.md](STREAMING_VARIANT_IMPORT.md).
3. Add columnar interval indexes and context-lattice queries for public reference tracks. **Implemented:** bounded JSON/JSONL/CSV/TSV normalization, immutable parallel columns, block-level overlap pruning, deterministic row/index/query addresses, exact and assembly-safe lattice context matching, CLI/API surfaces, and public-boundary audit coverage. See [docs/REFERENCE_INTERVAL_INDEX.md](REFERENCE_INTERVAL_INDEX.md).
4. Replace fixture-only feature readings with adapters whose licenses and access modes are declared. **Implemented:** declared source metadata, license/access/coordinate/context contracts, columnar index-backed reads, unavailable and out-of-domain abstention states, deterministic conformance probes, manifest emission, CLI/API surfaces, public-boundary checks, and atlas integration. See [docs/REFERENCE_TRACK_ADAPTERS.md](REFERENCE_TRACK_ADAPTERS.md).
5. Add cohort split, leakage, calibration, selective-risk, and transport benchmarks. **Implemented:** deterministic aggregate-only cohort records, group/source/context/hash/temporal splits, cross-split leakage audits, held-out calibration and selective-risk reports, source-to-target transport comparisons, CLI/API/schema/capability surfaces, public-boundary checks, and regression coverage. See [docs/COHORT_BENCHMARKS.md](COHORT_BENCHMARKS.md).
6. Add a review workspace that renders evidence edges, alternatives, deltas, and provenance without reducing them to one score. **Implemented:** replay-gated provenance-first review read model, payload-free evidence views, typed edges, explicit alternatives, source-centric lineage, explainable review queue, cross-run per-dimension deltas, CLI/API/schema/capability surfaces, public-boundary checks, and regression coverage. See [docs/REVIEW_WORKSPACE.md](REVIEW_WORKSPACE.md).
7. Add authenticated deployment profiles and audit export for institutional operation. **Implemented:** explicit non-loopback policy, API-key scopes, rate limiting, redacted hash-chained request audit, profile schema, CLI handling, durable replay verification, retention controls, and API endpoints.
8. Add a repository-wide static module inventory for deep module-by-module review. **Implemented:** AST-only source discovery, line and symbol counts, local dependency graph, cycle and unresolved-edge visibility, bounded indexes and queries, explainable depth percentage, review queue, timestamp-free observability, public-boundary checks, and a ten-artifact exact-byte offline packet. See [docs/MODULE_INVENTORY.md](MODULE_INVENTORY.md).

Every wave should preserve the same contracts, add fixtures and failure cases, and distinguish implemented behavior from externally evaluated science.

## Change acceptance checklist

- input and output versions are recorded;
- unsupported paths abstain explicitly;
- negative controls are included where the task permits;
- privacy and license checks are documented;
- deterministic reruns produce the same addresses; and
- review-facing explanations retain edge-level provenance.

No roadmap item is a claim of completion until code, fixtures, tests, and review material exist together.

The public repository should remain useful with no private dataset installed.

Build waves should be reversible.
Persisted artifacts should be readable.
Benchmarks should include failures.
Adapters should declare limitations.
Review should remain accountable.
