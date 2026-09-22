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

The quality calculation consumes each validated feature row once and does not
materialize the full feature-by-sample matrix. It retains per-sample running
statistics, the missingness histogram, and a bounded set of feature IDs for
duplicate detection; the compressed source and unique-feature count are also
bounded. Only the current decoded row is processed at a time.

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

Each reported row includes group counts, means/medians differences, a
rank-biserial effect size, raw p-value, adjusted q-value, and test method.
Missing features remain visible as untestable rows and do not enter the
multiple-testing family. The report includes its matrix digest, sample IDs,
filter context, analysis limits, and content address.

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
`geo-contrast`, model parameter count, and residual degrees of freedom. Samples
missing a declared covariate are listed with the exact missing fields. Overlap,
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
