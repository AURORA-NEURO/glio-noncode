# D01 variant identity and intake operations

This document defines the executable boundary for the first sixteen GLIO-
NONCODE capabilities. It is an intake and identity control surface. It is not
a clinical interpretation layer, a specimen authentication system, or a
substitute for institutional governance.

## Closed operation map

| Order | Capability | Operation | Input | Output | Held control |
| ---: | --- | --- | --- | --- | --- |
| 1 | GNC-D01-C01 | Case manifest ingestion | `case.manifest.input.v1` | `case.manifest.receipt.v1` | context or required-field mismatch |
| 2 | GNC-D01-C02 | VCF/BCF/gVCF parsing | `variant.bytes.input.v1` | `variant.parse.receipt.v1` | malformed or unsupported source |
| 3 | GNC-D01-C03 | Regulatory track parsing | `regulatory.track.input.v1` | `regulatory.track.receipt.v1` | invalid interval or header |
| 4 | GNC-D01-C04 | VRS normalization | `variant.identity.input.v1` | `vrs.normalization.receipt.v1` | ambiguous or unsupported structure |
| 5 | GNC-D01-C05 | Cat-VRS normalization | `categorical.variation.input.v1` | `catvrs.normalization.receipt.v1` | undeclared membership |
| 6 | GNC-D01-C06 | VA-Spec envelope | `annotation.statement.input.v1` | `va.spec.receipt.v1` | missing provenance |
| 7 | GNC-D01-C07 | Multi-allelic decomposition | `multiallelic.record.input.v1` | `allele.decomposition.receipt.v1` | symbolic allele or invalid genotype |
| 8 | GNC-D01-C08 | Repeat-aware normalization | `repeat.window.input.v1` | `repeat.normalization.receipt.v1` | reference mismatch or placement ambiguity |
| 9 | GNC-D01-C09 | Variant equivalence | `identity.query.input.v1` | `identity.match.receipt.v1` | absent, competing, or foreign identity |
| 10 | GNC-D01-C10 | Duplicate/alias reconciliation | `identity.batch.input.v1` | `identity.reconciliation.receipt.v1` | duplicate or colliding alias |
| 11 | GNC-D01-C11 | Batch/sample identity | `batch.identity.input.v1` | `batch.identity.receipt.v1` | missing or reused public batch key |
| 12 | GNC-D01-C12 | Chain of custody | `custody.receipt.input.v1` | `custody.ledger.receipt.v1` | broken predecessor or digest link |
| 13 | GNC-D01-C13 | Consent/data-use policy | `data.use.policy.input.v1` | `data.use.policy.receipt.v1` | missing or incompatible policy |
| 14 | GNC-D01-C14 | Input anomaly quarantine | `input.anomaly.input.v1` | `input.quarantine.receipt.v1` | invalid base, coordinate, or identity |
| 15 | GNC-D01-C15 | Completeness scoring | `completeness.input.v1` | `completeness.receipt.v1` | weighted required field missing |
| 16 | GNC-D01-C16 | Reproducible bundle export | `intake.bundle.input.v1` | `intake.bundle.receipt.v1` | blocked row or non-reproducible artifact |

The operation IDs are `INTAKE-D01-C01` through `INTAKE-D01-C16` and the
capability joins are `GNC-D01-C01` through `GNC-D01-C16`. The fixture supplies
one positive row and three controls for every operation: exact-context
positive, foreign-context, malformed-input, and duplicate-identity.

## Execution order

The plan is deliberately linear at the public boundary. Parsing produces
source-addressed counts. Normalization preserves candidate and warning counts.
Identity resolution is source-qualified and alias-aware. Policy and
completeness controls run before bundle materialization. Review routing and
the hash-linked ledger retain every held row. Release is admitted only when
all five offline artifacts and the rollback pointer are present.

```text
source receipt
    -> format parser
    -> canonical identity / normalization
    -> equivalence and duplicate reconciliation
    -> scope, anomaly, and completeness policy
    -> review queue
    -> hash-linked custody ledger
    -> offline bundle
    -> release and rollback gate
```

## Format behavior

`VariantIntake` remains the source parser of record. VCF and gVCF headers and
records are parsed with raw-line hashes and explicit issue codes. BCF is
decoded through `BcfReader` when binary data is supplied to the underlying
primitive. TSV and JSON preserve accepted-count and deferred-count receipts.
The D01 architecture only projects aggregate counts and addresses into its
runtime result.

Regulatory tracks use a bounded tab-delimited interval adapter. It requires
`chrom`, `start`, `end`, and `name`; invalid or non-increasing intervals remain
held. It does not infer regulatory function from an interval label.

## Normalization behavior

VRS normalization emits a VRS-shaped allele receipt but does not pretend that a
local assembly name is a RefGet digest. Literal multi-allelic records are
decomposed into indexed children with parent lineage. Repeat-aware normalization
replays literal edits inside a supplied window and returns every equivalent
placement when more than one exists. Unsupported symbolic, breakend, CNV, and
haplotype forms remain abstained or held by the underlying primitive.

Cat-VRS matching is explicit membership and alias matching against a declared
catalog. A category label alone never creates membership.

## Identity and provenance

Identity records retain source ID, source version, raw hash, public aliases,
build, context, batch key, and aggregate sample key. Equivalence resolution
groups normalized keys while preserving source records. Reconciliation never
selects a preferred source when duplicates or aliases collide. Custody events
are content-addressed and linked to the previous event. The D01 ledger has 64
events for the 64 fixture cases.

## Held controls

Controls are not silently dropped and are never promoted by the runtime. The
review queue includes all 48 non-positive cases, with deterministic priority:

1. foreign-context controls are highest priority because context transport is a
   hard boundary;
2. malformed-input controls are next because they require source correction;
3. duplicate-identity controls retain both identity projections until a review
   decision is recorded.

The review CSV is a sanitized projection containing case ID, operation ID,
priority, issue codes, route, and state. It does not include raw source text.

## Public data boundary

The checked-in fixture uses public source receipts for NCBI Variation, the NCBI
reference assembly, GA4GH VRS, Ensembl variation documentation, ENCODE, and the
repository control record. All source URIs are HTTPS and all rows are marked
`public_aggregate`. The fixture contains public identifiers and synthetic
control structure only. It contains no private subject keys or subject-level
measurements.
