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

This demonstrates only the downloaded-data, normalization-boundary, and
single-gene expression-evidence portion of the project. It does not construct
a non-coding variant or regulatory-element hypothesis, link EGFR expression to
a regulatory element, or run the complete case workflow. CPM is a minimal
illustrative library-size normalization, not a replacement for a validated
RNA-seq differential-expression workflow with appropriate design, covariates,
and batch handling. This example is strictly for research software
demonstration and has no clinical use.
