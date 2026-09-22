# Public GEO expression comparison

This command reads one public GEO Series Matrix and performs one exploratory
feature comparison against samples selected by their recorded characteristics.
It is not matched-case evidence or clinical guidance.

## Example

GSE103227 is a public expression-array series with five glioblastoma and five
normal-brain samples on platform GPL16956. Its processing notes report quantile
normalization. Example invocation:

    glio-noncode geo-outlier GSE103227 --feature-id ASHGA5P000001 --target-sample GSM2758529 --reference-filter diagnosis=normal --scale normalized_intensity

The example run read 10 samples and 58,944 feature rows. The target value was
11.36248, the reference median was 12.71811, and the robust z-score was -2.9203.
The result was no_descriptive_outlier at the absolute threshold 3.5. It describes
one platform feature in one sample relative to the chosen references, not a
cohort-wide finding.

## Selecting data

Inspect the Series Matrix processing notes and sample characteristics before
choosing options. Repeat the reference-filter option for additional conditions;
all conditions must match. Characteristic keys and values are case-insensitive,
but the tool does not infer a reference group from titles or diagnoses. The
target sample is rejected if it also matches its reference filters.

The scale option is required. Choose it from the matrix processing metadata.
normalized_intensity is available for processed array intensities. Raw counts
are not cohort-comparable in the expression analyzer. The command does not
transform values or decide whether the declared scale is suitable.

For offline analysis or a non-canonical matrix filename, pass a local txt or
txt.gz file with matrix-file. Local inputs are bounded regular files and the
report includes the filename only, never the directory path.

## Report meaning and limits

The versioned JSON contains source and response provenance, a SHA-256 digest of
the compressed matrix, selected target/reference sample IDs, the platform
feature identifier, sample characteristics, processing notes, declared scale,
robust statistic, and missing-value counts. Results distinguish descriptive
outlier, no descriptive outlier, and unresolved comparisons.

No transcript or gene annotation is inferred from a platform probe ID. Only
one feature is analyzed; there is no multiple-testing correction, p-value, or
population-level test. The report states that the comparison is not matched to
a patient case. A no-outlier result is not evidence that expression is
unchanged. The command does not harmonize differences in platforms, tissue
handling, normalization, or cohort composition and is not clinical guidance.

The importer limits compressed input to 25 MB, decompressed text to 256 MB,
individual lines to 4 MB, samples to 2,000, and matrix cells to 5,000,000. It
validates gzip checksums, matrix dimensions, sample IDs, numeric values, and
the selected feature before returning a report.

## Supplementary integer count tables

Some GEO series publish a gene-by-sample integer count matrix and a separate
sample metadata table instead of a Series Matrix. Use `geo-count-outlier` for
the supported bounded table format. The command requires exact file names (or
local file paths), explicit comma/tab delimiters, a metadata sample-key column,
and one or more `FIELD=VALUE` cohort filters. It never guesses a group from
sample names or downloads arbitrary URLs; remote files are fetched only from
the validated NCBI GEO supplementary path for the requested GSE accession.

### Inspect supplementary-count metadata before selecting groups

Use `geo-count-metadata` to discover exact metadata headers, sample-level
category counts, and whether a proposed subject key is complete or repeated.
This lets you inspect a supplementary metadata file before writing the explicit
`FIELD=VALUE` filters required by `geo-count-outlier` and `geo-count-contrast`:

```console
glio-noncode geo-count-metadata GSE141945 \
  --sample-key-column "" \
  --pair-key-column Patient \
  --metadata-file-name GSE141945_RNAseq.metadata.csv.gz \
  --metadata-delimiter comma
```

The same report accepts a local file with `--metadata-file` instead of the GEO
filename. It validates UTF-8 and gzip integrity, rectangular rows, unique
case-insensitive headers, the exact sample-key column, unique sample keys, and
an optional pair-key column. It reports row/column coverage and category
frequencies (casefolded in the same way as the contrast filters), plus optional
pair-key missingness, nonblank coverage, unique-key count, repeated-key rows,
and maximum rows per key. Repeated samples per subject are summarized, not
treated as duplicate errors; the paired contrast applies its own per-group
one-sample-per-subject validation after filters are selected. Pair keys are
trimmed for this summary, matching the paired contrast's
join behavior. The report does not emit sample or pair-key values and does not
assign groups or validate that metadata keys match a count matrix; the count
analysis performs that exact cross-file join before testing.

At most 25 category values per field are listed. Higher-cardinality fields
report a distinct-value lower bound and suppress values. Sample-key, pair-key,
and identifier-like fields never list category labels. Long category values
are truncated at 1,024 characters, and the report marks whether each shown
value can be copied into a CLI filter without changing it. Matching is
case-insensitive but does not trim metadata values, so leading or trailing
whitespace can make a value non-round-trippable. Source filename, canonical
response URL when fetched, SHA-256, and byte sizes are included; local directory
paths are not.

The metadata reader is bounded to 25 MB compressed, 256 MB decompressed, 4 MB
per line, 2,048 metadata rows, 2,000 samples, and 256 columns. This is a design
and data-inspection aid, not a statistical analysis or clinical report.

For a count matrix whose first metadata column has a blank header:

```console
glio-noncode geo-count-outlier GSE141945 \
  --feature-id EGFR \
  --sample-key-column "" \
  --sample-filter Timepoint=Tumor \
  --counts-file-name GSE141945_RNAseq.counts.csv.gz \
  --metadata-file-name GSE141945_RNAseq.metadata.csv.gz \
  --counts-delimiter comma \
  --metadata-delimiter comma
```

The importer validates a rectangular table of non-negative integer counts,
tracks every row in the per-sample library totals, and requires the requested
feature row to occur exactly once. Non-target duplicate row labels are
preserved and counted. By default, it computes `log2(CPM + 1)` using raw
library sizes from all matrix rows. Optional `--normalization-method
tmm_log2_cpm` estimates TMM factors across all samples, excludes duplicated
feature IDs from factor estimation, and uses effective library sizes; duplicated
rows still contribute to raw library totals. Both modes run a symmetric
leave-one-out median/MAD comparison within the explicitly selected metadata
cohort. Sample-level keys and values are not emitted in the aggregate report;
source names, hashes, byte sizes, filters, sample counts, outcomes, and an
addressed report are retained instead.

This route is limited to one exact matrix row per invocation. It is a
descriptive outlier screen, not a count-model differential-expression test,
multiple-testing-corrected finding, patient-matched result, or clinical
interpretation. Basic CPM does not correct for composition. Optional TMM uses
a trimmed, weighted log-ratio estimate and assumes most uniquely identified
features are not changing. Neither method corrects for batch, gene length, or
repeated-specimen dependence; TMM is not a count model. The count and metadata tables
must have exactly the same sample keys. Compressed files are limited to 25 MB,
decompressed text to 256 MB, individual lines to 4 MB, samples to 2,000, gene
rows to 1,000,000, and matrix cells to 5,000,000.

The single-feature command also accepts `--feature-annotation-file` using the
same exact two-column CSV format described below. The selected source label
stays in `matrix.feature_id`; its optional user-supplied curation is reported
separately in `matrix.feature_annotation`. Every mapping entry is checked
against the count matrix, including duplicate source rows, and the mapping hash
is included in the source provenance and `comparison.source_version`.

## Paired supplementary-count contrast

### Preflight the sample join and paired design

Run `geo-count-design` before a feature-wide paired screen when you want to
verify the count-table shape, exact sample-key join, explicit group selection,
and pair-key structure without calculating effects or p-values:

    glio-noncode geo-count-design GSE141945 --case-filter Timepoint=Tumor --reference-filter Timepoint=1wk --sample-key-column "" --pair-key-column Patient --counts-file-name GSE141945_RNAseq.counts.csv.gz --metadata-file-name GSE141945_RNAseq.metadata.csv.gz

The report marks the design `estimable` or `not_estimable`, lists aggregate
selected, overlapping, unmatched, blank-key, and duplicate-key counts, and
includes source hashes for reproducibility. Sample and pair IDs are never
emitted. The matrix is still fully scanned to validate its integer counts and
structure, but no expression vectors, effects, p-values, or q-values are
calculated. A structurally malformed input returns an invalid-input report. A
non-exact sample-key join instead returns a completed but `not_estimable`
diagnostic with aggregate counts of matrix keys missing from metadata, metadata
keys missing from the matrix, and the shared-key rows used for group summaries;
no mismatched key values are emitted.

The count preflight and paired screen also flag up to 25 distinct feature labels
that match a day/month-shaped pattern, along with the total number found. This
is a review hint for possible spreadsheet-coerced identifiers, not a gene
annotation or a claim that a label was corrupted. Source labels are preserved
verbatim and never normalized automatically. Each emitted contrast result now
also carries its own `feature_label_review` object, so a suspicious label stays
attached when a result is copied or filtered away from the matrix-level report.
The object records whether the label matches the pattern, whether manual
annotation review is recommended, and that the source label was preserved
without automatic normalization. `summary.reported_date_like_feature_label_count`
counts flagged rows among the limited results emitted by `--top`; the matrix
review count remains the count across the full input.

To attach analyst-reviewed identifiers without guessing corrections, provide
`--feature-annotation-file annotations.csv`. The UTF-8 CSV must use the exact
header `source_feature_id,curated_feature_id`; each source ID must resolve to
one unique row in the count matrix. For example:

```csv
source_feature_id,curated_feature_id
2-Sep,VERIFIED_TARGET_ID
```

The source-matrix `feature_id` remains unchanged. In a paired contrast, each
result carries the user-supplied value in
`results[].feature_annotation.curated_feature_id`; in the single-feature
outlier report it is under `matrix.feature_annotation.curated_feature_id`.
The map's SHA-256 and entry count are recorded under
`source.feature_annotation_map`, and its hash participates in
`comparison.source_version`. Missing source IDs,
duplicate mapping keys, and mapping keys that point to repeated matrix rows are
rejected. Curated identifiers are not checked against an external authority;
multiple source rows may share a curated identifier and are never merged. The
map changes display/interpretation metadata only, not counts, tests, FDR family,
or effect estimates. `VERIFIED_TARGET_ID` is a placeholder: replace it only
after checking the intended identifier against a trusted annotation source.

When a supplementary matrix has a separate subject/pair key, use
`geo-count-contrast` to compare two explicitly filtered sample groups within
matched subjects. Each subject must contribute exactly one selected case and
one selected reference sample; subjects missing either group are excluded and
reported as aggregate counts. At least three complete pairs are required.
Pair keys are used only for the join and are not included in the output.

For the GSE141945 tumor and one-week organoid groups:

```console
glio-noncode geo-count-contrast GSE141945 \
  --case-filter Timepoint=Tumor \
  --reference-filter Timepoint=1wk \
  --sample-key-column "" \
  --pair-key-column Patient \
  --counts-file-name GSE141945_RNAseq.counts.csv.gz \
  --metadata-file-name GSE141945_RNAseq.metadata.csv.gz \
  --counts-delimiter comma \
  --metadata-delimiter comma \
  --normalization-method tmm_log2_cpm \
  --fdr-method bh \
  --top 1000
```

The workflow validates every count and metadata row, computes each sample's
library size from the entire matrix, and analyzes uniquely labeled rows on
`log2(CPM + 1)` by default. Pass `--normalization-method tmm_log2_cpm` to
estimate composition factors across all matrix samples and use effective
library sizes. The report records method assumptions and aggregate factor
range, not per-sample factors. It uses a two-sided paired Wilcoxon signed-rank test on
within-subject differences: the exact sign-assignment distribution is used for
up to 32 nonzero pairs per feature, with a continuity-corrected normal
approximation above that bound. The matched-pairs rank-biserial effect,
mean/median paired difference, p-value, and BH or BY adjusted q-value are
reported. The correction family is all uniquely identified tested feature rows,
not only the displayed `--top` subset.

For both supplementary-count reports, `comparison.source_version` fingerprints
the input count and metadata files (and an optional annotation-map file), while
`comparison.context_key` fingerprints the selected groups/design and
normalization method. Analyses of the same files using CPM and TMM therefore
retain the same source version but have different context keys. The report's
`content_address` additionally fingerprints the resulting report contents.

For compatibility with existing v1 reports, `effect_direction` remains the
sign of the mean paired difference. New consumers should use the explicit
`mean_effect_direction`, `median_effect_direction`, and
`rank_biserial_effect_direction` fields to match a direction to its estimate.
The last field is the sign of `matched_pairs_rank_biserial_correlation`, the
declared rank-based effect size. A skewed paired distribution can make the mean,
median, and rank-biserial directions disagree; zero effects use explicit
no-difference labels.

The direction-only paired sign test is reported as a sensitivity view. It
excludes zero differences, uses the exact binomial distribution through 128
nonzero pairs, and uses a continuity-corrected normal approximation above that
bound. Because it ignores difference magnitude, it helps show whether a ranked
result persists when only directional consistency is considered. Each feature
reports case-higher, case-lower, and tied pair counts; sign-test q-values are
adjusted separately from the primary test.

Each feature also includes `leave_one_pair_out_median_sensitivity`. It removes
each matched pair in turn and summarizes the range and direction counts of the
remaining median paired log2-CPM difference. The `direction_stable` flag is
true only when every omission has the same median direction as the full paired
set. The aggregate summary counts features, including FDR-significant features,
whose median direction changes after at least one omission. This is a
descriptive influence diagnostic: it does not refit a hypothesis test, create
another p-value family, or establish that any pair is erroneous. Sample and
pair identifiers remain omitted. The calculation sorts each feature's paired
differences once and evaluates omissions from order statistics.

Each feature also reports `median_paired_difference_confidence_interval_log2_cpm`,
a central exact sign/order-statistic interval for the median paired difference.
`--confidence-level` sets its requested coverage (default 0.95); the report
records the attained binomial coverage and order-statistic ranks. Tied
differences are retained. Because finite-sample coverage is discrete, a small
number of pairs may not support any finite interval at the requested level; in
that case bounds and attained coverage are null and the report gives the maximum
coverage available from finite endpoints. These are pointwise intervals, not
adjusted across the feature family. They do not change the Wilcoxon p-values,
FDR correction, or exploratory status of the workflow.

The `quality_control` section summarizes matched case and reference samples
without emitting their identifiers. It reports library-size distributions,
the number of uniquely identified feature rows detected at raw counts of at
least 1, 5, and 10, top-one/top-ten feature count shares of the full library,
and the paired library-size imbalance distribution. Library sizes use every
input row; feature detection and top-feature shares exclude duplicated feature
IDs, and unmatched selected samples are not included in the group summaries.
These are descriptive checks only: they do not remove samples, filter tested
features, or modify the normalization or inference.

Repeated exact feature identifiers are excluded from the hypothesis-testing
family so a duplicated source label cannot be counted as two tests; all source
rows, including duplicates, still contribute to library totals. The report
records duplicate and unmatched counts, source hashes and byte sizes, exact
selection filters, method counts, and a content address. It omits sample IDs,
pair IDs, and individual expression values.

This is a paired exploratory log2-CPM screen, not a negative-binomial count
model or a voom/precision-weighted analysis. Inference assumes independent
pairs; the primary test uses exchangeable signs of ranked differences, while
the sign-test sensitivity uses exchangeable signs among nonzero differences.
Leave-one-pair-out direction stability is descriptive and does not relax the
independence assumption.
Basic library-size normalization does not model composition. Optional TMM adjusts
composition under a majority-stable-features assumption, but neither path models
gene-specific mean/variance, batch, purity, or other nuisance effects. FDR-screened rows remain research
associations—not validated biology, causal variant evidence, or clinical
guidance. The feature-row limit is 100,000; compressed/decompressed byte,
sample, line, and cell limits are shared with the supplementary-count importer.

## Sample and matrix quality summary

Run `geo-qc` before a contrast to review coverage and per-sample expression
distributions:

    glio-noncode geo-qc GSE103227 --scale normalized_intensity

For an existing download, add `--matrix-file GSE103227_series_matrix.txt.gz`.
The scale is a declaration from the Series Matrix processing notes; the report
does not transform, normalize, or otherwise rescale values. One platform is
required so sample-level statistics do not mix unlike feature measurements.

The versioned report contains full matrix provenance, a content address, the
observed and missing measurement counts, overall missing fraction, the number
of complete and partially observed features, and a histogram of features by
number of samples with missing values. Each sample row includes observed and
missing feature counts, missing fraction, arithmetic mean, sample standard
deviation, minimum, and maximum. Mean and standard deviation use all observed
features in that sample; standard deviation is null when fewer than two values
are observed or when the result cannot be represented as a finite number.
Statistics for a sample with no observed values are null.

Each sample row also reports `exact_profile_group_size`: the number of samples
whose parsed values and missingness positions match that sample across every
feature row. A value of 1 means no exact duplicate was found; larger values
identify exact repeated profiles. Samples with no observed values receive null
and are excluded from profile matching. The summary counts repeated groups by
size. SHA-256 profile fingerprints are used internally but are never emitted;
near-duplicates are not detected. This is a review signal only and does not
exclude or classify samples.

The quality calculation consumes each validated feature row once and does not
materialize the full feature-by-sample matrix. It retains per-sample running
statistics, one streaming profile digest per sample, the missingness histogram,
and a bounded set of feature IDs for duplicate detection; the compressed source
and unique-feature count are also bounded. Only the current decoded row is
processed at a time.

This is descriptive QC, not an automated quality decision. Samples are never
removed or ranked, and no threshold is applied. These summaries do not infer
why values are missing, correct batch effects, or guarantee that a sample is
suitable for downstream analysis. Distribution statistics are scale-dependent
and may be sensitive to extreme features; inspect the source matrix and study
design before deciding how to proceed.

## Sample-characteristic inventory

Before writing `--case-filter`, `--reference-filter`, or `--covariate` options,
inspect the annotations actually supplied by GEO:

    glio-noncode geo-metadata GSE103227

For a previously downloaded matrix, pass
`--matrix-file GSE103227_series_matrix.txt.gz`. The report inventories sample
accessions, titles, source names, and platform IDs, then lists each
characteristic field with its sample coverage, missing-sample count,
multi-valued-sample count, distinct-value count, and category counts. This makes
the available values visible without interpreting sample titles as design
labels. Field names and values are grouped with case-insensitive Unicode
casefolding; the first observed spelling is preserved for display. Repeated
field/value annotations that match case-insensitively within one sample count
once in category membership and are also reported as duplicate entries. Blank
characteristic cells are counted as missing; a literal value such as `NA` is
kept as submitter-provided text rather than reinterpreted as missing.

At most 100 category values per characteristic field are listed. If a field
exceeds that limit, the report explicitly records how many categories and
sample memberships are omitted. Parsing enforces the Series Matrix byte,
sample, line, metadata-row, and matrix-cell bounds. Unlike the expression QC
command, this path validates numeric matrix cells but does not retain expression
feature vectors, so metadata inspection has memory cost proportional to sample
annotations rather than the full feature-by-sample matrix.

The report is an inventory, not a cohort-design recommendation: it does not
assign clinical meanings, decide which values are cases or controls, infer
matched or repeated measurements, or automatically construct model covariates.
After reviewing the reported values, select group filters explicitly and use
`geo-contrast`; the contrast report then records the resulting sample IDs and
model diagnostics. GEO annotations are submitter supplied and may be missing,
inconsistent, or ambiguous.

## Two-group, all-feature screen

`geo-contrast` compares two disjoint sample groups selected by explicit
characteristic filters. At least two samples must match each group, and the
Series Matrix must describe exactly one platform. Repeating a filter adds an
AND condition; sample titles are never interpreted as group labels.

    glio-noncode geo-contrast GSE103227 --case-filter diagnosis=glioblastoma --reference-filter diagnosis=normal --scale normalized_intensity --fdr 0.05 --top 1000

The analysis retains the matrix's platform feature IDs and screens every
eligible feature. It uses a two-sided Mann–Whitney U statistic, exact label
permutations when the bounded assignment budget permits, and a tie-corrected
normal approximation otherwise. By default, Benjamini–Hochberg adjusted
p-values cover all features with at least two non-missing observations in each
group. For dependent feature tests, `--fdr-method by` selects the more
conservative Benjamini–Yekutieli adjustment, which controls false discovery
rate under arbitrary dependence among valid per-feature p-values. This does not
repair invalid feature-level tests, confounding, or post-selection. The default
`--fdr-method bh` retains Benjamini–Hochberg. The chosen method is recorded in
`comparison.fdr_method` and `comparison.multiple_testing_adjustment`; q-values
and significance counts use that method. The BY procedure multiplies the ranked
BH adjustment by the harmonic-number factor for the full test family.
The procedure is described in Benjamini and Yekutieli, *The Annals of
Statistics* 29(4), 1165–1188 (2001), doi:10.1214/aos/1013699998.

`--top` limits only how many ranked rows are serialized; it does not change the
tested family or the significant-feature summary. The full screen is bounded
to 100,000 retained features in addition to the compressed/decompressed byte,
sample, line, and matrix-cell limits above.

`geo-contrast` scans the already buffered matrix twice: the first pass validates
metadata and establishes the feature count, and the second streams one feature
row at a time into the analysis. It does not retain a complete
feature-by-sample expression table, though it retains per-feature result rows
for FDR correction and ranking and keeps the bounded source payload available.
This trades an extra parse pass for lower peak memory. The report records
`analysis_limits.matrix_scan_passes=2` and
`analysis_limits.retains_feature_vectors=false`.

Each reported row includes group counts, means/medians differences, a
rank-biserial effect size, raw p-value, adjusted q-value, and test method.
Missing features remain visible as untestable rows and do not enter the
multiple-testing family. The report includes its matrix digest, sample IDs,
filter context, analysis limits, and content address.

For an unadjusted contrast, each feature row also reports
`leave_one_sample_out_median_sensitivity`. It recomputes the case-minus-reference
median direction after omitting each eligible observed sample in turn, while
retaining at least two observations in both groups. `complete` means both
groups had eligible omissions; `partial` means only one group did; `unavailable`
means no deletion was eligible or the feature was not testable. The report gives
omission counts, coverage, direction counts, whether every eligible deletion
matches the full-data median direction, and the range of deleted-sample median
differences when representable. It emits aggregate counts, not sample identities.
This is a descriptive influence check on unadjusted medians: it does not refit
the Mann–Whitney test, change p- or q-values, or automatically reject a feature.
For covariate-adjusted OLS contrasts, the per-feature status is
`not_calculated`; raw median sensitivity is not a sensitivity analysis of the
adjusted model coefficient.

When exact label permutations are used, `comparison.finite_sample_resolution`
reports the number of exact-tested features, the range of label-assignment
counts, the corresponding no-tie lower-bound range for attainable two-sided
p-values, the smallest observed exact p-value, and how many features share it.
The assignment count is computed per feature from its non-missing case and
reference observations, so missing values can change the resolution across
features. The lower bound is `2 / choose(n_case + n_reference, n_case)`; ties
can make the observed p-value support coarser. This diagnostic makes finite
sample granularity visible but does not establish that a cohort is adequately
powered or that exchangeability assumptions hold. For example, five observed
samples in each group provide 252 possible label assignments and a no-tie
two-sided p-value lower bound of 2/252 (about 0.00794).

## Contrast design preflight

Before scanning every feature, use `geo-design` to verify explicit sample
selection and model encodability using only GEO metadata:

    glio-noncode geo-design GSE103227 --case-filter diagnosis=glioblastoma --reference-filter diagnosis=normal

For a previously downloaded Series Matrix, add
`--matrix-file GSE103227_series_matrix.txt.gz`. Add each proposed adjustment
with an explicit type, for example `--covariate age=continuous` or
`--covariate batch=categorical`; group labels are never inferred from titles,
clinical vocabulary, or expression values.

The report lists selected case, reference, overlapping, and unassigned sample
accessions. For adjusted designs it also reports covariate-complete samples,
per-group covariate summaries, the same deterministic encoding used by
`geo-contrast`, model parameter count, and residual degrees of freedom. Numeric
covariates include a descriptive case-minus-reference standardized mean
difference using the pooled within-group sample standard deviation, plus an
observed-range overlap indicator and intersection. Categorical covariates show
per-level group fractions, absolute fraction gaps, shared levels, and the
largest level gap. These summaries are descriptive only: range overlap is not a
distribution-overlap test, and no balance threshold or adjustment decision is
applied. Samples missing a declared covariate are listed with the exact missing
fields. Overlap,
insufficient group size, missing/invalid covariates, rank deficiency, or an
unsupported multi-platform matrix produce `not_estimable` with a reason; the
command does not repair the design or silently change group membership.

This is a metadata-only preflight in the sense that it retains no feature rows
or computes a group effect, statistic, p-value, or FDR value. It still reads
and validates the complete bounded Series Matrix, including the numeric matrix
cells, source digest, and feature count. Successful output is content-addressed
and records only the local source filename, not its directory. A successful
preflight does not guarantee that each feature will have enough observed values
for a later analysis, nor does covariate balance establish causal exchangeability.

### Reproducible local-data walkthrough

On the downloaded `GSE103227_series_matrix.txt.gz` used for this walkthrough,
the metadata report exposes five `diagnosis=glioblastoma` and five
`diagnosis=normal` samples. Streamed QC validated 58,944 features and 589,440
measurements, with no missing matrix values. Replay those checks without a new
network fetch:

    glio-noncode geo-metadata GSE103227 --matrix-file GSE103227_series_matrix.txt.gz
    glio-noncode geo-qc GSE103227 --scale normalized_intensity --matrix-file GSE103227_series_matrix.txt.gz

Then preflight the explicit contrast before calculating effects:

    glio-noncode geo-design GSE103227 --case-filter diagnosis=glioblastoma --reference-filter diagnosis=normal --matrix-file GSE103227_series_matrix.txt.gz

That preflight selected GSM2758529–GSM2758533 as cases and GSM2758524–GSM2758528
as references. The unadjusted two-group design was estimable with two
parameters and eight residual degrees of freedom. It retained no expression
vectors and calculated no effect sizes or p-values.

Replay the matching exploratory feature screen and retain only the top ten
rows in the output report:

    glio-noncode geo-contrast GSE103227 --case-filter diagnosis=glioblastoma --reference-filter diagnosis=normal --scale normalized_intensity --fdr 0.05 --top 10 --matrix-file GSE103227_series_matrix.txt.gz --output GSE103227-contrast.json

The exact-label permutation screen tested all 58,944 features. The top reported
feature was ASHGA5P000002 (median difference -2.9241, case lower, rank-biserial
correlation -1, raw p=0.00794, BH q=0.01876). The full FDR family contained
26,699 features at q≤0.05 (13,463 higher and 13,236 lower in the case group).
This is a small exploratory cohort result—not evidence of causality,
replication, diagnosis, or treatment response. Platform IDs are not mapped to
genes unless an explicit matching platform annotation file is supplied.

### Save and review the contrast locally

For a downloaded matrix that should remain available in the local review
workbench, persist the completed report in the content-addressed expression
catalog while still writing the full JSON report to disk:

    glio-noncode geo-contrast GSE103227 --case-filter diagnosis=glioblastoma --reference-filter diagnosis=normal --scale normalized_intensity --matrix-file GSE103227_series_matrix.txt.gz --top 1000 --save-to-workspace --data-root .glio --output GSE103227-contrast.json

The catalog stores the full report as a verified private object and creates a
deterministic `geo-expression-*` record. `GET /v1/geo-expression-analyses`
returns only bounded cohort and feature-count summaries. A detail page at
`/v1/geo-expression-analyses/{analysis_id}` returns paged feature effects,
directions, p-values, q-values, and provenance without selected GSM accessions.
Filtered aggregate CSV is available at
`/v1/geo-expression-analyses/{analysis_id}/results.csv`; the explicit
`report.json` export is the reproducibility artifact and includes the exact
sample selections needed to audit cohort assignment.

The local workbench presents saved expression contrasts beside paired-count
GEO analyses. It verifies the content address before rendering, supports
feature, direction, and FDR filters, and keeps expression contrast metrics
separate from the paired-count and sequence review surfaces.

## Compare exact feature directions across Series

When reviewing a candidate platform feature in multiple Series, retain it
explicitly even if it falls outside the ranked `--top` output. Repeat
`--track-feature-id` for each feature of interest, then compare two to eight
completed contrast reports:

The consistency command accepts two to eight reports and up to 500 requested
feature IDs per run. A tracked ID must be present in that Series Matrix or the
contrast fails rather than silently dropping the requested feature.

    glio-noncode geo-contrast GSE_A --case-filter diagnosis=glioblastoma --reference-filter diagnosis=normal --scale normalized_intensity --track-feature-id EXACT_PLATFORM_ID --output GSE_A.json
    glio-noncode geo-contrast GSE_B --case-filter diagnosis=glioblastoma --reference-filter diagnosis=normal --scale normalized_intensity --track-feature-id EXACT_PLATFORM_ID --output GSE_B.json
    glio-noncode geo-consistency GSE_A.json GSE_B.json --feature-id EXACT_PLATFORM_ID

Tracked rows outside the ranked result limit are stored separately from the
top-ranked rows and remain part of the same full-matrix multiple-testing
correction; tracking does not change the test family. `geo-consistency` accepts
only reports from the same GPL platform and requires equal expression scale,
FDR method and threshold, and covariate specification. Feature IDs are exact
and case-sensitive, with no alias or cross-platform gene mapping. A feature not
present in either the ranked rows or explicitly tracked rows is `not reported`,
not a null result. The report compares tested effect directions, separately
summarizes agreement among FDR-significant reports, and copies each source
report's effect estimates and per-feature sample counts into the corresponding
study row: unadjusted rows retain their mean difference, median difference,
and rank-biserial correlation; adjusted rows retain the covariate-adjusted mean
difference and its confidence interval when available. It does not pool effect
sizes, p-values, q-values, or confidence intervals. A non-significant report is
not counted as evidence for the opposite direction; at least two
FDR-significant reports are required to call significant-direction agreement
or disagreement.
It can identify repeated GSM sample IDs and conflicting case/reference roles,
but distinct accessions and source hashes do not prove cohort independence.
These exploratory comparisons are not clinical evidence.

The declared case and reference filter sets must also match between reports,
including their group roles. Filter fields and values follow the GEO matcher’s
case-insensitive semantics, and the order of AND filters does not matter. A
mismatch returns `incompatible_contrast_reports` with a path-free explanation.
Matching filter definitions still do not prove that labels have the same
biological meaning in different studies; assess cohort and assay context
before treating directional agreement as replication.

Completed saved expression analyses can be compared by catalog identifier and
retained as a separate consistency record. The API accepts two or more saved
analysis IDs and exact source feature IDs:

    curl -X POST http://127.0.0.1:8786/v1/geo-expression-consistency \
      -H "Content-Type: application/json" \
      -d '{"analysis_ids":["geo-expression-...","geo-expression-..."],"feature_ids":["EXACT_PLATFORM_ID"]}'

The resulting `geo-consistency-*` record is immutable and can be listed at
`/v1/geo-expression-consistency`, paged at
`/v1/geo-expression-consistency/{comparison_id}`, or exported through
`features.csv`. Its public rows retain per-study direction and effect
estimates, but never emit GSM, subject, or pair identifiers. It does not pool
effects or p-values, resolve aliases, or treat an omitted bounded row as a
negative result. The workbench comparison page exposes exact-feature, tested
direction, and FDR-consistency filters; the filtered state is reused for the
CSV export.

## Persist paired-count consistency comparisons

The paired integer-count workflow has the same durable comparison boundary.
After saving completed paired-count analyses into the local GEO workspace, use
their catalog IDs to create a content-addressed comparison:

    glio-noncode geo-count-consistency --data-root .glio \
      --analysis-id geo-analysis-... --analysis-id geo-analysis-... \
      --feature-id EXACT_COUNT_FEATURE --save-to-workspace

The API equivalent is:

    curl -X POST http://127.0.0.1:8786/v1/geo-count-consistency \
      -H "Content-Type: application/json" \
      -d '{"analysis_ids":["geo-analysis-...","geo-analysis-..."],"feature_ids":["EXACT_COUNT_FEATURE"]}'

The resulting `geo-count-consistency-*` record is immutable and can be listed
at `/v1/geo-count-consistency`, paged at
`/v1/geo-count-consistency/{comparison_id}`, or exported through
`features.csv`. It preserves each study's paired design, normalization, and
aggregate direction state without pooling effects or p-values. Missing bounded
rows remain `not_reported_in_bounded_results`, and sample, subject, pair, and
analysis identifiers are withheld from the public comparison projection.
The workbench exposes exact-feature, tested-direction, signed-rank FDR, and
sign-test FDR filters, and applies those filters to the CSV export.

## Covariate-adjusted mode

The rank-based comparison above is the default and remains unchanged when no
covariates are supplied. To fit an additive ordinary least squares model, pass
each covariate with an explicit type:

    glio-noncode geo-contrast GSE103227 --case-filter diagnosis=glioblastoma --reference-filter diagnosis=normal --scale normalized_intensity --covariate age=continuous --covariate batch=categorical --fdr 0.05 --top 1000

The model estimates the case-minus-reference group coefficient while adjusting
for the declared fields. Continuous fields are centered and scaled by their
population standard deviation; this does not change the group coefficient.
Categorical fields use treatment coding with a deterministic, case-insensitive
sorted reference level. The report records the encoding, levels, parameter
names, and continuous-field center and scale. Covariates must come from sample
characteristics, must not also define the case/reference groups, and are never
inferred automatically.

Samples missing any declared covariate are excluded listwise and their GEO
sample IDs are reported separately from the originally selected groups. The
model requires at least two complete samples per group and at least three
residual degrees of freedom. Rank-deficient, collinear, constant-covariate, or
ill-conditioned designs are rejected. The model is bounded to 16 covariates
and 24 total parameters. An expression feature is untestable if any covariate-
complete model sample lacks its expression value; this fixed-sample rule avoids
silently fitting different designs feature by feature. Untestable features do
not enter the Benjamini-Hochberg family.

Adjusted rows retain descriptive group means and medians, but report the model's
adjusted group coefficient separately, along with its t statistic, residual
degrees of freedom, central 95% t confidence interval, residual standard error,
adjusted R-squared, p-value, and q-value. The interval uses the same residual
standard error and degrees of freedom as the reported t test. Adjusted
R-squared compares residual and total mean squares, accounting for the fitted
parameter count; it is a descriptive fit diagnostic, not evidence that the
covariate model is correctly specified. A fit diagnostic is null when the
response has no estimable total variance or the value is not representable.
Classical t inference assumes
independent samples and approximately normal, homoscedastic errors; continuous
covariate effects are linear and no interactions, nonlinear terms, paired or
repeated-measures structure are fitted. Adjustment covers only the covariates
the user supplies, so omitted batch effects and residual confounding remain
possible. The adjusted analysis is still exploratory and is not clinical
evidence.

### Join an explicit GEO platform annotation file

Series Matrix feature IDs can be joined to the corresponding local GPL SOFT
platform table without changing the statistical analysis. Supply the platform
file and select the exact data-table columns to retain:

    glio-noncode geo-contrast GSE103227 --case-filter diagnosis=glioblastoma --reference-filter diagnosis=normal --scale normalized_intensity --matrix-file GSE103227_series_matrix.txt.gz --platform-annotation-file GPL16956_family.soft.gz --annotation-column TRANSCRIPT_TYPE --annotation-column BUILD --annotation-column SPOT_ID --top 1000

The SOFT file must contain a `!Platform_geo_accession` matching the single
platform used by the Series Matrix; the `^PLATFORM` entity label itself may be
a different local identifier. If the SOFT file concatenates other entity
records, only the matching GPL table is joined while the hash still covers the
complete source. The ID column defaults to `ID`; override it with
`--annotation-id-column` only when the platform table uses another header.
Column labels are matched case-insensitively and the original header spelling is
retained in result objects. Feature identifiers are joined by exact,
case-sensitive text equality. Duplicate platform feature IDs, missing selected
columns, malformed rows, or a platform mismatch fail the command rather than
silently choosing a mapping.

Only the selected annotation fields are included in result rows. Values are
kept verbatim: delimiters inside a cell are not split, aliases are not resolved,
and a field is not automatically treated as a gene or transcript identity.
Rows without a match remain in the result with `platform_annotation_status` set
to `not_found`. The report records the platform accession, annotation filename,
full-source SHA-256, selected columns, source byte counts, and matched and
unmatched feature counts for the complete matrix. Local directory paths are not
written into the report. This makes annotation joins auditable while preserving
the annotation submitter's meaning and ambiguity.

The reader streams plain or gzip-compressed SOFT files and bounds compressed
and decompressed bytes, line length, row count, selected-field count, value
length, and retained annotation bytes. A quick or otherwise partial platform
table is permitted; its limited join coverage is visible in the report and
must not be mistaken for complete platform annotation. NCBI describes GPL
records as platform definitions with tab-delimited feature tables; platform
columns and identifiers vary by submitter, so inspect the table before
selecting fields.

## Reproducible run on GSE103227

Running the command above on the downloaded 2,609,899-byte Series Matrix with
SHA-256
`446cca696272bf16085aa1bf82717a1bfa2f4c81e44aeef41292ee79afdb0e14` selected
five glioblastoma and five normal samples. All 58,944 features were testable;
the bounded exact permutation test was used for each, and 26,699 rows had
`q <= 0.05` in this run. The top-ranked row was platform feature
`ASHGA5P000002` (median difference -2.9241, rank-biserial correlation -1.0,
raw p-value 0.00794, adjusted q-value 0.01876). These figures demonstrate the
workflow and are not independently validated biological findings.

This is an exploratory public-cohort comparison, not matched-case RNA
evidence. It does not model batch, purity, age, sex, repeated measures, or
other covariates, and the exchangeability assumption may not fit a given
series. A small cohort can have insufficient resolution for FDR significance.
Platform IDs are not gene annotations, and the report does not imply causal,
population-generalizable, diagnostic, or treatment conclusions. Raw-count
scales are rejected; inspect processing metadata and declare the scale
explicitly. Use `--matrix-file` for a previously downloaded local Series Matrix.
