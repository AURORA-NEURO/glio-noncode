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
