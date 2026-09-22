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

Both Python demo wrappers also accept `--feature-annotation-file` for a
user-reviewed `source_feature_id,curated_feature_id` CSV. The source label stays
unchanged and the map is provenance metadata only; see
`docs/GEO_EXPRESSION_WORKFLOW.md` for its validation rules.

## What the demo exercises

The example streams the count matrix, checks its shape and integer counts,
computes per-sample library totals, and extracts the `EGFR` row. It treats the
input as raw counts and defaults to the simple `log2(CPM + 1)` calculation
before constructing normalized expression observations. To estimate TMM
composition factors first, add `--normalization-method tmm_log2_cpm` to either
demo wrapper. It then runs a symmetric leave-one-out comparison: each tumor
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

Before selecting a contrast, inspect the downloaded supplementary metadata and
confirm the grouping and pair columns without printing sample or patient keys:

```powershell
glio-noncode geo-count-metadata GSE141945 `
  --sample-key-column "" `
  --pair-key-column Patient `
  --metadata-file-name GSE141945_RNAseq.metadata.csv.gz
```

The same downloaded files can then drive a paired, feature-wide comparison by
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
  --top 25 `
  --track-feature-id 2-Sep `
  --track-feature-id AAGAB `
  --save-to-workspace `
  --data-root .glio
```

When run with `--save-to-workspace`, the completed aggregate report is retained
as a separately addressed GEO analysis record, without storing individual
sample or pair keys. Start `glio-noncode serve --host 127.0.0.1 --port 8765
--data-root .glio` and open `http://127.0.0.1:8765/` to inspect its provenance,
paired design, summary counts, top reported rows, and limitations alongside
case-run reviews. GEO study analyses remain distinct from case dossiers.

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
Date/month-shaped labels remain verbatim, but each emitted result now carries a
row-level `feature_label_review` flag; any flagged label needs annotation review
before it is interpreted as a gene identifier.
The input SHA-256 digests were
`50ed47d4a6d859f94dbe93e2bca16299d3f1d865c0bd5b4160ceb2c8f19b6f2b` for the
count matrix and `146583acadda31455842e9a9581156a4a847e27a0a7823717601b46053785cf0` for
metadata.

To run the same path through the example wrapper, use
`python examples/real_downloaded_glioma_paired_contrast_demo.py`; pass both
`--counts-file` and `--metadata-file` to reuse local downloads rather than
fetching the canonical GEO supplement paths again.

### TMM comparison on downloaded public data

On September 22, 2026, both GEO supplementary files were fetched over HTTPS
from the public NCBI record (3,653,658-byte count matrix and 489-byte metadata
table), then reused locally for four comparisons: single-feature outlier and
paired contrast, each with the default `log2_cpm` and optional
`tmm_log2_cpm` normalization.

The single-feature EGFR screen produced 4 descriptive outlier calls and 13
non-outlier comparisons under either normalization. TMM factors across all 81
matrix columns ranged from 0.7536 to 1.3978, with median 0.9999.

For the paired Tumor-versus-1wk screen, the same 17 complete patient pairs and
56,828 uniquely labeled tested rows were used in both runs. The default CPM
screen reported 10,726 BH-significant rows and 5,938 direction-only sign-test
rows at q <= 0.05. The TMM-adjusted screen reported 8,187 and 5,222,
respectively. These differences show the effect of changing the library-size
normalization on this dataset; they are not evidence that one result set is
biologically correct. This implementation performs paired rank/sign tests on
log-CPM values, not negative-binomial count-model differential expression.

The leading TMM-adjusted label was `2-Sep`, also marked by the output as a
date/month-shaped source label requiring annotation review. The program
preserves it verbatim and does not claim that it is a gene identifier. This is
an important example of the importer surfacing a data-quality hazard instead
of silently changing a row label.

The two saved runs can now be reviewed directly as a same-Series normalization
sensitivity comparison. In the downloaded-data run, the TMM report was the
left run and the simple CPM report was the right run. Comparing the 25 displayed
feature labels produced 14 stable directions, zero changed directions, and 11
labels not present in both bounded top-row projections; the FDR and sign-test
significance states were stable for the same 14 jointly reported labels. The
date-shaped `2-Sep` row was jointly reported and direction/significance-stable,
while its median paired effect changed by approximately `+0.2961` log2-CPM
from TMM (left) to CPM (right). These are transform-sensitivity observations,
not a pooled result or evidence that either normalization is biologically
correct. The saved artifact is exposed at
`/v1/geo-count-sensitivity/{comparison_id}` and its aggregate feature ledger at
`/v1/geo-count-sensitivity/{comparison_id}/features.csv`.

For a stricter rerun, adding `--track-feature-id 2-Sep --track-feature-id AAGAB`
to both normalization commands retains those exact source rows even if the
ranked top-25 lists change. This changes only report coverage: all 56,828
eligible rows remain in the BH and sign-test families, while the report records
which rows were ranked and which were explicitly retained.

That tracked-row path was exercised with `--top 1` on the downloaded files. The
TMM report `geo-cf1af3836345459b224f73453469a62e08c998a9b45169f67f07082f48a12f9e`
and CPM report
`geo-5049128ffc96687078eb58fe6ae7fd981346aab10846839f630345a8cb08f617` each
returned one ranked row plus one explicitly tracked row. Their saved sensitivity
comparison `geo-count-sensitivity-df5ccabdd18ad5c2faf1e4a7bd293601c2ecd8d4231a590b46349ef266f8628c`
reported stable direction, signed-rank FDR, and sign-test FDR states for both
`2-Sep` and `AAGAB`.

The GEO series describes RNA-seq of glioblastoma tumor and organoid samples.
The results above remain an exploratory re-analysis of a small public study;
they do not establish independent-patient replication, validated biology,
causality, diagnosis, or treatment guidance. See
`docs/GEO_EXPRESSION_WORKFLOW.md` for normalization assumptions and command
options.

These examples demonstrate downloaded-data handling, a single-gene descriptive
screen, and a paired feature-wide cohort screen. They do not construct a
non-coding variant or regulatory-element hypothesis, link expression to a
regulatory element, or run the complete case workflow. CPM is a simple
library-size normalization, not a replacement for a count-model or
precision-weighted RNA-seq workflow with appropriate design and nuisance-effect
handling. Optional TMM adjusts composition under a majority-stable-features
assumption, but does not remove the need for count-model inference or suitable
batch and covariate handling. This example is strictly for research software
demonstration and has no clinical use.
