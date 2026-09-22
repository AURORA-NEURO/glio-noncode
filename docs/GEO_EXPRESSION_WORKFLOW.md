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

## Two-group, all-feature screen

`geo-contrast` compares two disjoint sample groups selected by explicit
characteristic filters. At least two samples must match each group, and the
Series Matrix must describe exactly one platform. Repeating a filter adds an
AND condition; sample titles are never interpreted as group labels.

    glio-noncode geo-contrast GSE103227 --case-filter diagnosis=glioblastoma --reference-filter diagnosis=normal --scale normalized_intensity --fdr 0.05 --top 1000

The analysis retains the matrix's platform feature IDs and screens every
eligible feature. It uses a two-sided Mann–Whitney U statistic, exact label
permutations when the bounded assignment budget permits, and a tie-corrected
normal approximation otherwise. Benjamini–Hochberg adjusted p-values cover all
features with at least two non-missing observations in each group. `--top`
limits only how many ranked rows are serialized; it does not change the tested
family or the significant-feature summary. The full screen is bounded to
100,000 retained features in addition to the compressed/decompressed byte,
sample, line, and matrix-cell limits above.

Each reported row includes group counts, means/medians differences, a
rank-biserial effect size, raw p-value, adjusted q-value, and test method.
Missing features remain visible as untestable rows and do not enter the
multiple-testing family. The report includes its matrix digest, sample IDs,
filter context, analysis limits, and content address.

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
degrees of freedom, p-value, and q-value. Classical t inference assumes
independent samples and approximately normal, homoscedastic errors; continuous
covariate effects are linear and no interactions, nonlinear terms, paired or
repeated-measures structure are fitted. Adjustment covers only the covariates
the user supplies, so omitted batch effects and residual confounding remain
possible. The adjusted analysis is still exploratory and is not clinical
evidence.

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
