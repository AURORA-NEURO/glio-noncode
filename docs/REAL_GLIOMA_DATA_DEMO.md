# Real glioblastoma expression-data demonstration

This runnable example fetches the processed count matrix and sample table for
NCBI GEO accession [GSE141945](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE141945),
then passes real values through GLIO-NONCODE's typed expression-evidence API.
GEO describes the series as RNA-sequencing of glioblastoma tumors and
corresponding organoids. The example restricts its comparisons to the matrix's
tumor-labeled samples.

Run from the repository root:

```powershell
python examples/real_downloaded_glioma_expression_demo.py
```

On first run it downloads two public GEO supplementary files into the ignored
`.glio-gse141945-demo/` directory. It prints SHA-256 digests and byte sizes so
the exact downloaded inputs are identifiable. Subsequent runs reuse those
local files. Delete that specific cache directory when you no longer need it.

## What the demo exercises

The example streams the count matrix, checks its shape and integer counts,
computes per-sample library totals, and extracts the `EGFR` row. It first sends
raw counts through the expression comparator; the API correctly rejects all
17 tumor-sample comparisons as out of domain because raw counts are not
cohort-comparable. It then applies the deliberately simple transform
`log2(CPM + 1)` and runs a symmetric leave-one-out comparison: each tumor
sample is compared with the other tumor-labeled samples using the current
median/MAD robust-outlier implementation. Sample keys and individual expression
values are not printed.

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
