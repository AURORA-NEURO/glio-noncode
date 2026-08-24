# D07 chromatin architecture

The D07 aggregate closes the chromatin, accessibility, and methylation boundary
as one inspectable public-data module. It composes four source tranches while
keeping each tranche's own adapter receipts, context, source joins, uncertainty,
and refusal behavior visible:

| Tranche | Capabilities | Plane | Aggregate operations |
| --- | ---: | --- | ---: |
| Accessibility context | C01-C04 | accessibility | 4 |
| Methylation context | C05-C08 | methylation | 4 |
| Chromatin state | C09-C12 | chromatin_state | 4 |
| Cross-assay release | C13-C16 | cross_assay | 4 |

The aggregate fixture contains 19 public source receipts, 16 typed operation
contracts, 64 cases, 458 execution checks, six artifacts, and a 24-stage
runtime. Every operation has one positive case and three explicit controls:
foreign context, malformed input, and identity conflict. There are 16 positive
receipts and 48 review-held control receipts. Every source carries an explicit
public aggregate marker and every case retains its delegated context key.

## Context boundary

The aggregate context is:

`GRCh38|glioma|adult|stem_like|tumor|unknown`

All aggregate source receipts are public and use HTTPS. The methylation family
retains its source tranche context in the embedded family record while the
aggregate normalizes the operation boundary to the D07 context. This preserves
the provenance distinction between an input tranche and the cross-tranche
release view.

## Functional coverage

The first twelve operations delegate to their family fixture evaluators:

- C01-C04 execute ATAC/DNase and histone context retrieval and delta paths.
- C05-C08 execute methylation retrieval, CpG creation/loss, sensitive motif,
  and IDH panel context paths.
- C09-C12 execute state segmentation, allele-specific comparison, bounded
  epigenomic mixture estimation, and batch/composition correction.

C13-C16 call the typed cross-assay primitives directly:

- context imputation records observed values separately from declared priors
  and retains prior confidence;
- assay coverage requires declared support before interpretation;
- concordance reports direction agreement and the number of observations;
- publication requires exact context and declared assay IDs before creating a
  published evidence bundle.

No signal is converted into a clinical, causal, enhancer-truth, or treatment
conclusion. Every such boundary is retained in the release limitations.

## Runtime

`run_chromatin_architecture` executes 24 stages:

1. load and audit the fixture;
2. compile the dependency plan;
3. close each of the four family joins;
4. execute cases and route controls;
5. close lineage, ledger, metrics, schema, invariants, and replay;
6. materialize six artifacts and account for source, operation, case, family,
   state, issue, and check depth;
7. close policy, quality, release, access, compliance, observability, and
   finalization.

The runtime is accepted only when every stage, receipt, quality check, lineage
link, replay address, compliance check, and release artifact is closed. The
quality gate contains 14 direct checks and the depth report reaches 100.0%
when all five fixed targets are met.

## Commands

```text
glio-noncode chromatin-architecture-fixture --output fixture.json
glio-noncode chromatin-architecture-data-audit --input fixture.json
glio-noncode chromatin-architecture-plan --input fixture.json
glio-noncode evaluate-chromatin-architecture --input fixture.json
glio-noncode chromatin-architecture-runtime --input fixture.json
glio-noncode chromatin-architecture-quality --input fixture.json
glio-noncode chromatin-architecture-depth --input fixture.json
glio-noncode chromatin-architecture-compliance --input fixture.json
glio-noncode chromatin-architecture-validation --input fixture.json
glio-noncode chromatin-architecture-report --format markdown --input fixture.json
glio-noncode chromatin-architecture-receipts-csv --input fixture.json --output receipts.csv
glio-noncode chromatin-architecture-review-csv --input fixture.json --output review.csv
glio-noncode chromatin-architecture-bundle --input fixture.json --output bundle
```

The JSON fixture is deterministic and content-addressed. It can be regenerated
from the checked-in public source receipts without network access.
