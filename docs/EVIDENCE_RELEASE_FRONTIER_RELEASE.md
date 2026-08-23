# Evidence release frontier release note

This build adds a dedicated D14 C13-C16 release surface. It includes four
independent operation adapters, a 16-row public aggregate fixture, 5 source receipts,
81 deterministic evaluation checks, 53 ordered runtime stages, schema and data
audits, replay, content-addressed artifacts, review routing, and HMAC dossier
verification.

The fixture intentionally mixes positive and control rows. Controls remain part of
the release evidence: they prove that low scores, reviewer shortages, context
transport, missing targets, cycles, empty sections, duplicate sections, expiry,
and empty dossiers do not silently become successful releases.

This boundary is research-operational. It describes evidence lifecycle transitions
and publication receipts; it does not claim clinical performance, individual outcome,
or causal certainty.

The build is intentionally self-contained: public URLs are recorded as provenance
anchors, the fixture contains aggregate operational rows, and all derived artifacts
are content addressed. The runtime can be inspected offline after checkout. The
release boundary is open for the next module tranche; this commit closes only the
D14 C13-C16 evidence-release slice and does not declare the product finished.

The public aggregate fixture is intentionally inspectable.
The source receipts are intentionally linkable.
The row contracts are intentionally replayable.
The controls are intentionally retained.
The issue vocabulary is intentionally explicit.
The context boundary is intentionally exact.
The signatures are intentionally verifiable.
The key material is intentionally absent.
The artifacts are intentionally addressable.
The runtime stages are intentionally ordered.
The audit log is intentionally contiguous.
The handoff is intentionally bounded.
The claim wording is intentionally conservative.
The package is intentionally reproducible.
The next build can extend this surface without changing its fixture contract.
Every subsequent tranche should keep the same public-data boundary.
Every subsequent tranche should add positive and negative controls.
Every subsequent tranche should preserve deterministic replay.
Every subsequent tranche should document its stop conditions.
Every subsequent tranche should retain a clean metadata boundary.
Every subsequent tranche should keep public source scope explicit.
Every subsequent tranche should keep release decisions inspectable.
Every subsequent tranche should keep controls visible.
Every subsequent tranche should keep addresses stable.
Every subsequent tranche should keep tests executable.
Every subsequent tranche should keep CI commands explicit.
Every subsequent tranche should keep the project unfinished until its next audited build.
