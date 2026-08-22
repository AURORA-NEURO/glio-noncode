# Chromatin frontier evidence gate

## Purpose

This gate defines the bounded evidence boundary for Domain 07 C13-C16. It
exercises four chromatin adapters against a deterministic public aggregate
fixture. The fixture is not a subject-level cohort and does not establish
clinical, causal, enhancer, or treatment conclusions. Public references are
represented by release-aware source receipts and content addresses.

The four operations are:

| Capability | Operation | Positive state | Control states |
| --- | --- | --- | --- |
| C13 | `chromatin_segmentation` | `supported` | `ambiguous`, `out_of_domain`, `partial` |
| C14 | `allele_specific_chromatin` | `supported` | `ambiguous`, `out_of_domain`, `partial` |
| C15 | `epigenomic_purity` | `supported` | `partial`, `out_of_domain`, `partial` |
| C16 | `batch_composition_correction` | `supported` | `partial`, `out_of_domain`, `partial` |

There are 16 records: one positive and three controls for each operation. The
evaluator produces 120 checks: seven per record and eight fixture-wide checks.
Controls remain visible even when they contain useful observations. Review is a
state transition, not an error to be hidden or converted into support.

## Source receipts

The fixture records five public aggregate boundaries:

- ENCODE for open-chromatin and replicate assay context;
- Roadmap Epigenomics for reference chromatin states;
- IHEC for epigenome metadata and assay provenance;
- NCBI GEO for public assay submission context;
- UCSC Genome Browser for assembly and coordinate context.

Each receipt contains source ID, title, HTTPS URI, source kind, release, scope,
and a content address. Evaluation is offline and resolves every record source ID
against this receipt map. A missing source is a failed boundary check, not an
implicit fetch.

## Adapter boundaries

### C13 segmentation

The segmentation adapter normalizes intervals, splits overlaps at every observed
boundary, computes signal summaries, retains samples and replicates, and assigns
open/intermediate/closed labels. Conflicting declared states are ambiguous.
Invalid coordinates and negative signals are quarantined with row-level issue
codes. Context mismatch produces an out-of-domain report with no reused segments.

### C14 allele-specific signal

The allele adapter groups observations by variant and assay, computes each
alternate-minus-reference replicate delta, summarizes median/minimum/maximum and
spread, and retains direction. Mixed positive and negative directions or spread
above the declared tolerance remain ambiguous. A delta is a descriptive assay
comparison, not causal evidence.

### C15 purity estimate

The purity adapter computes a one-dimensional mixture proportion from observed,
tumor-reference, and normal-reference marker signals. Marker raw values,
bounded values, denominators, assay, and source hashes remain visible. Values
outside the unit interval are clipped only for aggregate display and keep a
partial marker state. A zero denominator cannot support an estimate.

### C16 correction

The correction adapter retains raw signal, batch offset, composition coefficients,
target composition, batch adjustment, composition adjustment, and corrected
signal. Missing offsets and invalid proportions remain partial or quarantined.
The correction output is a transparent normalization record, not a causal
effect or a replacement for assay validation.

## Gate sequence

The quality gate composes these stages:

1. fixture context, source closure, cardinality, and sanitization audit;
2. typed operation contract resolution;
3. adapter execution for all 16 records;
4. expected state and issue-floor checks;
5. policy and interpretation checks;
6. schema shape and issue-vocabulary checks;
7. deterministic replay;
8. source-to-receipt lineage;
9. expected-versus-observed reconciliation;
10. metrics, bundle, and release readiness.

The quality report emits 12 checks and exposes failed check IDs. A ready release
requires data audit, evaluation, replay, scenarios, policy, schema, lineage,
reconciliation, cardinality, and content-address checks to pass. Runtime
`--fail-on-review` can impose a stricter batch boundary while retaining the full
diagnostic bundle.

## Non-claims

This gate does not infer chromatin occupancy, enhancer truth, gene regulation,
causality, clinical purity, prognosis, treatment response, or calibrated
probability. It records the declared adapter result, uncertainty, scope,
provenance, and review action needed for further work.
