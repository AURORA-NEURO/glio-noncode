# Real glioblastoma expression-data demonstration

This runnable example fetches the processed count matrix and sample table for
NCBI GEO accession [GSE141945](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE141945),
then passes real values through GLIO-NONCODE's typed expression-evidence API.
GEO describes the series as RNA-sequencing of glioblastoma tumors and
corresponding organoids. The example restricts its comparisons to the matrix's
tumor-labeled samples.

Run from the repository root:

```powershell
$env:PYTHONPATH = "src"
python examples/real_downloaded_glioma_expression_demo.py
```

The example uses the reusable GEO supplementary-count API. It fetches the two
public source files over bounded HTTPS in memory and prints SHA-256 digests and
byte sizes so the exact inputs are identifiable. It does not write the data
files to the repository. To use files you already downloaded, pass both
`--counts-file` and `--metadata-file`.

The same operation is available as a CLI command:

```powershell
glio-noncode geo-count-outlier GSE141945 `
  --feature-id EGFR `
  --sample-key-column "" `
  --sample-filter Timepoint=Tumor `
  --counts-file-name GSE141945_RNAseq.counts.csv.gz `
  --metadata-file-name GSE141945_RNAseq.metadata.csv.gz `
  --counts-delimiter comma `
  --metadata-delimiter comma
```

## What the demo exercises

The example streams the count matrix, checks its shape and integer counts,
computes per-sample library totals, and extracts the `EGFR` row. It treats the
input as raw counts and explicitly transforms them with the deliberately simple
`log2(CPM + 1)` calculation before constructing normalized expression
observations. It then runs a symmetric leave-one-out comparison: each tumor
sample is compared with the other tumor-labeled samples using the current
median/MAD robust-outlier implementation. Raw counts are never passed to the
cohort comparator. Sample keys and individual expression values are not
printed.

With the downloaded files inspected for this demonstration, the matrix contains
56,832 gene rows and 81 samples, of which 17 are labeled `Tumor`. The current
run detects four downward EGFR outliers and records 13 measured comparisons
without an outlier. These are exploratory heuristic outcomes over one small
study matrix—not p-values or proof of biological differences. The metadata has
multiple time points and sampled specimens; the 17 columns must not be assumed
to represent 17 statistically independent patients.

The count matrix contains two repeated feature labels. The example retains all
rows when computing library totals and requires the requested `EGFR` row to be
unique before analyzing it.

## Matched tumor-versus-organoid screen

The same downloaded files can drive a paired, feature-wide comparison by
matching each tumor to its subject's one-week organoid:

```powershell
glio-noncode geo-count-contrast GSE141945 `
  --case-filter Timepoint=Tumor `
  --reference-filter Timepoint=1wk `
  --sample-key-column "" `
  --pair-key-column Patient `
  --counts-file-name GSE141945_RNAseq.counts.csv.gz `
  --metadata-file-name GSE141945_RNAseq.metadata.csv.gz `
  --fdr-method bh `
  --top 25
```

For the locally downloaded files used in the reproducible run, the matrix had
81 sample columns and 56,832 feature rows. The metadata produced 17 complete
Tumor/1wk pairs with no unmatched selected samples. Two duplicated feature IDs
(four source rows) were excluded from testing but remained in library totals;
56,828 uniquely labeled features were tested, and 10,726 had BH-adjusted
`q <= 0.05` in this run. These are exploratory paired log2-CPM signed-rank
screen results, not validated differential-expression findings or causal
evidence. The workflow assumes independent subjects and exchangeable within-pair
signs, does not fit a count model or precision weights, and does not infer gene
identity beyond the source row label. Sample and patient keys are not written
into its aggregate report. The direction-only sign-test sensitivity reported
5,938 features with BH-adjusted q <= 0.05, compared with 10,726 from the
signed-rank primary test. The top displayed labels each had 17 of 17 nonzero
pairs in the same direction; this is cohort-level consistency, not validation.
The input SHA-256 digests were
`50ed47d4a6d859f94dbe93e2bca16299d3f1d865c0bd5b4160ceb2c8f19b6f2b` for the
count matrix and `146583acadda31455842e9a9581156a4a847e27a0a7823717601b46053785cf0` for
metadata.

To run the same path through the example wrapper, use
`python examples/real_downloaded_glioma_paired_contrast_demo.py`; pass both
`--counts-file` and `--metadata-file` to reuse local downloads rather than
fetching the canonical GEO supplement paths again.

These examples demonstrate downloaded-data handling, a single-gene descriptive
screen, and a paired feature-wide cohort screen. They do not construct a
non-coding variant or regulatory-element hypothesis, link expression to a
regulatory element, or run the complete case workflow. CPM is a simple
library-size normalization, not a replacement for a count-model or
precision-weighted RNA-seq workflow with appropriate design and nuisance-effect
handling. This example is strictly for research software demonstration and has
no clinical use.
