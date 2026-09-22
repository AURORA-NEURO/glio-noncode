# Provenance-first review workspace

The review workspace is the dossier review read model for GLIO-NONCODE. It
complements the searchable run workspace by keeping the reasoning graph
visible: hypotheses, decomposed edges, evidence states, alternatives, source
provenance, human-review work items, and explicit cross-run deltas are returned
as separate collections.

It is a replay-gated research projection. A failed current run or baseline run
withholds details. The projection never publishes raw evidence payloads,
producer metadata, direct subject/sample/contact fields, or a single aggregate
decision score.

## Local browser workbench

Start the loopback API and open `http://127.0.0.1:8765/` in a browser:

```powershell
glio-noncode serve --host 127.0.0.1 --port 8765 --data-root .glio
```

The workbench is a read-only client of the existing run-catalog and review
workspace endpoints. It shows replay-checked runs, candidate paths, separate
support and uncertainty values, edge-level evidence states, alternatives,
source lineage, review-queue reasons, optional baseline deltas, and a Markdown
export. It does not calculate scores, promote a claim, or change a persisted
run. Assets are served from the installed package, use same-origin requests,
and do not fetch fonts, scripts, or styles from third parties. Keep the default
loopback bind for local use; non-loopback deployments must retain the existing
deployment-profile authentication, TLS, and audit requirements.

Completed paired GEO count contrasts can be saved separately as aggregate
study reports with `geo-count-contrast --save-to-workspace --data-root .glio`.
They appear in the workbench's GEO analyses rail and retain input digests,
comparison design, quality checks, result rows, and stated limitations. These
reports are not converted into case dossiers or causal hypotheses. The API
catalog is `GET /v1/geo-analyses?limit=20&offset=0`; one result page is
`GET /v1/geo-analyses/{analysis_id}?limit=25&offset=0`.
The verified complete report can be downloaded as JSON from
`GET /v1/geo-analyses/{analysis_id}/report.json`; the response is an attachment
named with its GEO accession and content-addressed analysis ID. The workbench
enables this export only after the selected report page has passed verification.

The GEO rail also exposes `Open archive health`. That panel reopens every
cataloged GEO analysis and comparison object through its content address and
shows a per-catalog ledger of records, verified objects, feature-row totals,
tested-row totals, FDR-significant totals, accession counts, and state. Its aggregate-only JSON export is
`GET /v1/geo-review/summary`; the CLI equivalent is
`glio-noncode geo-review-summary --data-root .glio`. These counts are catalog
summaries and are not deduplicated across studies or comparisons. The
row-level, aggregate-only health ledger is available as
`GET /v1/geo-review/summary.csv?verify_reports=true`. It contains one row per
saved analysis or comparison, the public GEO accession(s), bounded feature
counts, and verification state. The CSV never contains sample, subject, pair,
raw matrix, agent, or language metadata. The workbench exposes it as
`Download health ledger` after archive health has been opened. The same
projection is available from the CLI:
`glio-noncode geo-review-summary --csv --data-root .glio
--output geo-review-ledger.csv`.

Preparation preflights can also be retained before a final contrast is run.
The `geo-qc`, `geo-metadata`, `geo-design`, `geo-count-metadata`, and
`geo-count-design` commands accept `--save-to-workspace --data-root .glio`.
Their bounded catalog rows identify the preflight kind, GEO accession, source
digest, sample/feature counts, and selected design metrics; full reports remain
explicit exports from `GET /v1/geo-preflights/{preflight_id}/report.json`.
List them with `GET /v1/geo-preflights?kind=contrast_design&accession=GSE141945`.
Download the kind-aware aggregate ledger with
`glio-noncode geo-review-summary --preflights-csv` or
`GET /v1/geo-preflights.csv?verify_reports=true`; it includes report schema,
source receipt, dimensions, design state, and verification without sample or
pair identifiers.
The browser workbench renders these saved rows in a preparation rail, supports
accession/kind filters and bounded loading, and opens a verified aggregate
detail view; it keeps sample identifiers and pair-level detail outside the
browser projection.
The archive-health summary and CSV ledger verify these preflights alongside
the final analysis and cross-study comparison catalogs.

Feature pages accept bounded aggregate filters before pagination:
`feature_contains` performs case-insensitive source-label matching,
`effect_direction` accepts `case_higher`, `case_lower`, or
`no_mean_difference`, and `fdr_significant` and
`sign_test_fdr_significant` accept `true` or `false`. The optional
`min_abs_median_effect` threshold filters on the absolute median paired
difference in log2-CPM units. The response reports both
`total_results` after filtering and `unfiltered_result_count`, along with the
normalized `filters` object. These filters operate only on the immutable
feature-result rows; they never search or expose sample, patient, or pair keys.
For example:

```text
GET /v1/geo-analyses/{analysis_id}?feature_contains=EGFR&fdr_significant=true&limit=25
```

The same filters can be exported without pagination as a bounded, aggregate-only
CSV from `GET /v1/geo-analyses/{analysis_id}/results.csv`. Its columns contain
source feature labels, review flags, paired effect summaries, p/q values, and
significance flags; it does not contain sample, patient, or pair identifiers.
The workbench's `Download filtered CSV` control follows the active filters.

The GEO rail also includes a cross-study check. Select two or more saved
analyses, enter exact source feature IDs (one per line or separated by commas),
and compare the reports in a separate aggregate view. The view shows tested,
untestable, FDR-significant, sign-test-significant, and not-reported states per
Series. It does not merge curated aliases, pool effect sizes, combine p-values,
or expose individual sample or pair identifiers.

The paired-count rail also supports same-Series normalization sensitivity. Select
exactly two saved paired-count runs, enter source feature IDs, and choose
`Review normalization sensitivity`. The sensitivity contract requires the same
Series accession, count-matrix and metadata digests, case/reference filters,
pairing design, effect basis, test, and FDR settings; only the declared
normalization/expression scale may differ. It emits stable, changed,
insufficient, and not-reported states for direction, signed-rank FDR, and
direction-only sign-test FDR. It never pools statistics or treats a missing
bounded row as negative evidence.

For reproducible cross-normalization coverage, pass repeated
`--track-feature-id FEATURE_ID` options to each `geo-count-contrast` run. The
report retains the ranked `--top` rows plus those exact source IDs, records
`ranked_feature_count` and `additional_tracked_feature_count`, and rejects
duplicate or absent IDs. This keeps a requested row jointly reportable without
changing the multiple-testing family, ranking, or statistical calculations.

The sensitivity CLI accepts saved IDs or two portable report files:

```powershell
glio-noncode geo-count-sensitivity --data-root .glio `
  --analysis-id GEO_TMM_ID --analysis-id GEO_CPM_ID `
  --feature-id 2-Sep --feature-id EGFR --save-to-workspace
```

The immutable records are listed by `GET /v1/geo-count-sensitivity`, opened by
`GET /v1/geo-count-sensitivity/{comparison_id}`, and exported as aggregate CSV
from `GET /v1/geo-count-sensitivity/{comparison_id}/features.csv`. Archive
health includes the sensitivity catalog as
`paired_count_sensitivity_comparisons`.

Saved paired-count reports can also be compared across distinct GEO Series
without exposing their sample or pair keys. The focused CLI accepts either
portable report files or immutable store IDs:

```powershell
glio-noncode geo-count-consistency first.json second.json `
  --feature-id SIGNAL --feature-id INFLUENTIAL --output consistency.json
glio-noncode geo-count-consistency --data-root .glio `
  --analysis-id GEO_ID_A --analysis-id GEO_ID_B `
  --feature-id SIGNAL --output consistency.json
```

The same projection is available at
`GET /v1/geo-analyses/consistency?analysis_id=GEO_ID_A&analysis_id=GEO_ID_B&feature_id=SIGNAL`.
The comparison requires compatible case/reference filters, pairing design,
normalization, effect-direction basis, statistical test, and FDR settings.
It reports per-Series aggregate values and separately classifies tested,
untestable, FDR-significant, sign-test-significant, and not-reported rows.
Missing rows remain `not_reported_in_bounded_results`; they are never treated
as negative evidence. Effect sizes and p-values are never pooled or combined.

## Phased sequence and motif analysis

The focused `sequence-haplotype` command runs the sequence-inference module on
one bounded sequence window and an explicitly phased set of SNV/indel records.
It is intended for downloaded FASTA/VCF-derived slices after the caller has
resolved the reference interval, genome build, phase block, and motif catalog.
The command does not fetch remote data itself; the input records the retrieval
receipt that belongs to the already downloaded window.

The exact input contract is `glio-noncode.sequence-haplotype-input.v1`:

```powershell
glio-noncode sequence-haplotype examples/sequence-haplotype-input.json `
  --output sequence-haplotype-report.json
```

The `sequence` object contains the assembly, interval, bases, source identity,
source URL, source version, and retrieval timestamp. Every variant must carry
an explicit phase set and haplotype index. The parser rejects unphased blocks,
unsupported variant syntax, interval/sequence-length mismatches, duplicate
fields, and records over the module's bounded limits. Motifs are supplied as
named definitions with a source ID rather than being silently inferred from an
untracked database.

The output is `glio-noncode.sequence-haplotype-analysis.v1` and is content
addressed. It keeps the source and response digests, interval, canonical
variant IDs, phase metadata, motif definitions, created/disrupted motif hits,
the inference state, and limitations. It deliberately omits raw bases and
sample IDs, so the report is an aggregate review artifact rather than a sample
export. A valid run can finish as `supported` or `abstained`; an abstained
state is still a complete, inspectable report with an explicit limitation.

The checked-in fixture is synthetic but follows the same shape as a downloaded
reference slice plus a VCF-derived phased call set. Replace its sequence and
variant records with locally downloaded data, retain the receipt fields, and
rerun the command to obtain a deterministic content address. The report can be
reviewed without granting the workbench access to the original FASTA or VCF.
The same bounded projection is available as a read-only HTTP operation:
`POST /v1/sequence-haplotype` with the exact input object as its JSON body.
Query parameters are rejected, and validation errors do not produce a partial
analysis.

For downloaded files, the adapter constructs that exact input contract from a
local FASTA window and a phased VCF sample. It accepts plain or gzip-compressed
files, requires a `GT` value with `|` separators, uses a record `PS` value (or
an explicit fallback), and selects only the requested haplotype. For example:

```powershell
glio-noncode sequence-files `
  --fasta downloads/GRCh38.fa.gz `
  --vcf downloads/sample.phased.vcf.gz `
  --sample-id SAMPLE_1 --genome-build GRCh38 --chromosome chr7 `
  --start 140453100 --end 140453300 `
  --source-id reference-download --source-url https://example.org/reference `
  --source-version 2026-08 --retrieved-at 2026-08-20T00:00:00Z `
  --motifs motifs.json --output sequence-report.json
```

The adapter rejects missing sample columns, unphased genotypes, no-call
alleles, malformed FASTA contigs, out-of-window requests, unsupported file
sizes, and missing phase provenance before motif analysis starts. The VCF and
FASTA are read locally; their bases, genotype strings, and sample IDs do not
cross into the persisted public report.

When several downloaded samples share the same reference window and motif
catalog, `sequence-batch` aggregates the individual reports without emitting
sample rows:

```powershell
glio-noncode sequence-batch batch-input.json --output batch-report.json
```

The batch projection reports supported versus abstained analyses and counts
how many reports created or disrupted each exact motif pattern. It requires a
single shared reference hash, interval, source receipt, and motif definition
set; mixed contexts are rejected. The equivalent read-only HTTP operation is
`POST /v1/sequence-haplotype/batch`.
To retain the aggregate result in the local catalog, send the same exact input
to `POST /v1/sequence-batches`; list saved batch summaries with
`GET /v1/sequence-batches` and export a verified report from
`GET /v1/sequence-batches/{batch_id}/report.json`.
The CLI can persist the same report with `--save-to-workspace --data-root
.glio`. A saved batch's aggregate changes are available at
`GET /v1/sequence-batches/{batch_id}?change=created|disrupted` and
`GET /v1/sequence-batches/{batch_id}/changes.csv`; both reopen and validate the
immutable batch object before returning rows.
Two compatible batch reports can be compared with
`glio-noncode sequence-batch-compare left.json right.json`; the result keeps
exact motif identity and reports prevalence deltas while treating a missing
row as `not_reported_in_one_batch`. The read-only API equivalent is
`POST /v1/sequence-haplotype/batch/compare` with `left` and `right` report
objects. Persist a comparison from two saved batch IDs with
`POST /v1/sequence-comparisons` and `{ "left_batch_id": "...", "right_batch_id": "..." }`;
the resulting catalog is listed at `GET /v1/sequence-comparisons` and its
verified changes are available through `/changes.csv`.

Saved single analyses and aggregate batches can be reviewed together without
opening raw reference windows in the catalog view:

```powershell
glio-noncode sequence-review summary --data-root .glio
glio-noncode sequence-review motifs --data-root .glio --motif-contains CTCF
glio-noncode sequence-review motifs --data-root .glio --change disrupted --csv --output motif-activity.csv
glio-noncode sequence-review verify --data-root .glio
```

The summary validates immutable catalog records and reports record counts,
state counts, source counts, and aggregate change counts. `verify` reopens every
content-addressed report object and emits a path-free integrity ledger. The
motif projection groups exact change direction, motif ID, matched string,
strand, and source ID across single reports and batches; batch fractions remain
separate from single-analysis counts. The HTTP equivalents are
`GET /v1/sequence-review/summary`, `GET /v1/sequence-review/motifs`,
`GET /v1/sequence-review/motifs.csv`, and `GET /v1/sequence-review/verify`.
These endpoints omit raw bases, genotype strings, sample identifiers, and
subject identifiers. A passed integrity check does not make sequence-only
evidence causal or clinical.

For a reusable local catalog, use `--save-to-workspace`:

```powershell
glio-noncode sequence-haplotype downloaded-slice.json `
  --save-to-workspace --data-root .glio
```

Saved reports are listed at `GET /v1/sequence-analyses` and opened through
`GET /v1/sequence-analyses/{analysis_id}/report.json`. The aggregate motif
delta page is `GET /v1/sequence-analyses/{analysis_id}` with optional
`change=created|disrupted` and `motif_contains=...` filters; the same bounded
rows can be downloaded from `/changes.csv`. The persistence layer reopens and
revalidates the report address, source hashes, interval, analysis state, motif
hit shapes, and public-key boundary before returning any row.
The browser workbench shows saved sequence analyses in a separate rail and
renders their phase block, interval, hashes, motif changes, and limitations.
It keeps sequence reports separate from both patient-specific case dossiers
and cohort-level GEO contrasts.

The sequence workflow is intentionally split into reviewable boundaries:

| Boundary | Input | Public output | Persistence |
| --- | --- | --- | --- |
| `sequence-haplotype` | One bounded reference window and phased calls | One deterministic motif-delta report | Optional `sequence-analyses` record |
| `sequence-files` | Local plain/gzip FASTA plus phased VCF | The same motif-delta report | Optional `sequence-analyses` record |
| `sequence-batch` | Several compatible haplotype inputs | Aggregate state and exact motif prevalence | Optional `sequence-batches` record through HTTP |
| `sequence-batch-compare` | Two completed batch reports | Exact prevalence deltas | Portable JSON comparison |
| persisted comparison | Two saved batch IDs | Immutable exact prevalence comparison | `sequence-comparisons` catalog |
| `sequence-review` | Saved sequence catalogs | Integrity ledger and exact motif activity | Read-only archive projections |

Every boundary preserves the same safety properties: bounded input, explicit
source receipt, deterministic content address, no automatic phase inference,
and no private sample keys in the public projection. A report may be useful for
review while remaining `abstained`; that state is distinct from malformed
input, unavailable source data, or a failed persistence verification.

For operational triage, start with the catalog summary, then open the verified
report, then inspect motif rows or CSV only after the report address matches.
When comparing batches, inspect the shared reference hashes first; a missing
row means that the motif was not reported in that bounded result set. These
steps keep provenance, analysis state, and interpretation limits visible at
the same time rather than collapsing them into a single score.
The browser follows this ordering for saved sequence and GEO studies.
This makes a saved result auditable without exposing the downloaded source
files to the review client.

## Review collections

- `hypotheses` retains mechanism, context, status, support, uncertainty, edge
  IDs, evidence IDs, alternatives, provenance IDs, and missing/negative
  evidence declarations.
- `edges` retains source/target identifiers, typed edge kind, support,
  uncertainty, context fit, support level, claim IDs, source IDs, and evidence
  state counts.
- `evidence` retains source, channel, tier, state, score, confidence, context,
  summary, dependency IDs, and supersession links. Payloads are withheld.
- `alternatives` keeps each declared branch as a separate reviewable object;
  an alternative is not folded into the primary hypothesis.
- `provenance` groups evidence by source and retains edge/claim coverage,
  tiers, states, contexts, dependencies, supersession, and declared receipt
  IDs.
- `review_queue` gives a bounded priority band and reasons for human review.
  Priority is workflow triage, not biological ranking.
- `deltas` compare common or introduced/removed hypotheses, edges, and evidence
  between two verified runs. Numeric deltas are per dimension (support,
  uncertainty, context fit, score, or confidence); state and presence changes
  remain categorical.

## CLI

```powershell
glio-noncode review-workspace RUN_ID --data-root .glio --output review-workspace.json
glio-noncode review-workspace RUN_ID --data-root .glio --baseline-run-id BASELINE_RUN_ID --output review-deltas.json
glio-noncode review-workspace-schema --output review-workspace-schema.json
glio-noncode review-workspace-capabilities --output review-workspace-capabilities.json
glio-noncode review-workspace-export RUN_ID --data-root .glio --format markdown --output review-workspace.md
glio-noncode review-workspace-export RUN_ID --data-root .glio --format csv --collection edges --output edges.csv
glio-noncode review-workspace-release RUN_ID --data-root .glio --output review-release
glio-noncode review-workspace-release-verify review-release --output verification.json
glio-noncode review-workspace-index RUN_ID --data-root .glio --output review-index.json
glio-noncode review-workspace-query RUN_ID --collection evidence --state contradictory --limit 50 --data-root .glio --output review-query.json
glio-noncode review-workspace-query-schema --output review-query-schema.json
glio-noncode review-workspace-release-load review-release --output release-summary.json
glio-noncode review-workspace-release-index review-release --output release-index.json
glio-noncode review-workspace-plan RUN_ID --data-root .glio --output review-plan.json
glio-noncode review-workspace-plan-query RUN_ID --lane provenance --limit 50 --data-root .glio --output plan-query.json
glio-noncode review-workspace-plan-export RUN_ID --data-root .glio --format markdown --output review-plan.md
glio-noncode review-workspace-plan-schema --output review-plan-schema.json
glio-noncode review-workspace-plan-capabilities --output review-plan-capabilities.json
glio-noncode review-workspace-plan-execution RUN_ID --data-root .glio --output execution.json
glio-noncode review-workspace-plan-event RUN_ID --action-id ACTION_ID --kind start --event-id EVENT_ID --occurred-at 2026-09-01T12:00:00Z --data-root .glio --output execution.json
glio-noncode review-workspace-plan-execution-query RUN_ID --status open --data-root .glio --output execution-query.json
glio-noncode review-workspace-plan-execution-schema --output execution-schema.json
glio-noncode review-workspace-plan-execution-capabilities --output execution-capabilities.json
glio-noncode review-workspace-plan-execution-release RUN_ID --data-root .glio --output execution-release
glio-noncode review-workspace-plan-execution-release-verify execution-release --output execution-release-verification.json
glio-noncode review-workspace-plan-execution-release-load execution-release --include-report --output execution-release-report.json
glio-noncode review-workspace-plan-execution-release-query execution-release --status open --limit 50 --output execution-release-query.json
glio-noncode review-workspace-plan-execution-release-diff execution-release-a execution-release-b --output execution-release-diff.json
glio-noncode review-workspace-release-query review-release --collection evidence --limit 50 --output release-query.json
glio-noncode review-workspace-release-plan review-release --output release-plan.json
glio-noncode review-workspace-release-diff release-a release-b --output release-diff.json
```

The command exits successfully when the public projection is safe to consume,
including when its review state is `review`. `abstained` and `blocked` are
content states that remain inspectable when the run itself is valid; failed
replay verification returns no reasoning collections.

## Exports and portable release

`review-workspace-export` renders JSON, Markdown, or one named CSV collection.
The named collections are `hypotheses`, `edges`, `evidence`, `alternatives`,
`deltas`, `provenance`, and `review_queue`. Markdown includes coverage,
integrity, warnings, and all review collections; CSV uses stable headers,
sorted source views, JSON-encoded collection cells, and LF line endings.

`review-workspace-release` packages the JSON projection, Markdown report, and
all seven CSV collections into nine UTF-8 artifacts. `manifest.json` records
byte count, line count, media type, and a content address for each artifact.
`review-workspace-release-verify` independently checks the manifest address,
exact bytes, safe direct filenames, unexpected files, and the public boundary.
The API remains read-only: `GET /v1/runs/{run_id}/review-workspace/export`
supports `format=json|markdown|csv` and `collection` for CSV; filesystem
materialization is an explicit CLI operation.

## Query and facets

`review-workspace-index` computes reusable collection, state, source, context,
dimension, item-type, and priority facets. `review-workspace-query` applies
bounded filters over that same public index and returns a stable page plus
facets for the complete matched set. Supported filters include collection,
free-text over the aggregate projection, evidence/review state, source ID,
context key, item type, delta dimension, queue priority, offset, and limit.
Rows are sorted by collection order and public item identifier; pagination
cannot change the underlying content address. Use `limit=none` only through
the offline closure helper, where the report's collection ceilings remain the
upper bound.

## Triage plan

`review-workspace-plan` expands each explainable queue item into ordered,
descriptive work steps. The intake step is followed, when applicable, by
context-fit, source-provenance, alternative-comparison, and disposition-
preparation steps. A disposition-preparation step is a checklist boundary; it
does not store the disposition. Hypothesis inspection can depend on queued
evidence inspection, so a reviewer can see the intended order without treating
the dependency as a scientific relationship.

The plan reports five lanes (`intake`, `context`, `provenance`, `alternatives`,
and `disposition`), priority counts, estimate units, exact action addresses,
and structural checks for queue closure, dependency closure, topological order,
lane closure, public-boundary safety, and configured bounds.
`review-workspace-plan-query` provides bounded action filters for lane, action kind, queue item,
target, state, priority, text, offset, and limit with complete-match facets.
`review-workspace-plan-export` renders JSON, Markdown, and deterministic action,
lane, and check CSV files. A verified portable release can be reopened and
planned with `review-workspace-release-plan`; no live run store is required.

## Plan execution ledger

`review-workspace-plan-event` appends one explicit transition to the local
`review-plan-execution/<plan-address>/events.jsonl` ledger. Valid transitions
are `start`, `complete`, `block`, `skip`, and `reopen`. The event chain is
address-linked and the neighboring `manifest.json` records exact byte, line,
event-count, and event-file addresses. A completion event must name every
required public check for its action and every dependency must already be
completed; blocked, skipped, or completed actions can be reopened only with an
explicit reason.

`review-workspace-plan-execution` replays the ledger into action statuses,
readiness, dependency waits, next-action IDs, blocked-action IDs, counters, and
structural checks. The execution report can be queried by status, lane, action
kind, action ID, event kind, priority, or text, and exports deterministic JSON,
Markdown, action CSV, event CSV, and check CSV. The ledger is operational only:
it does not alter the dossier, evidence, plan, or scientific conclusion.

The same execution query surface accepts `view=events` (or the CLI
`--view events`) for a first-class ordered event timeline. Timeline rows carry
their zero-based ledger sequence, typed transition, predecessor address,
occurrence instant, check and reference addresses, and a row content address.
They support exact kind, action, event, check, and reference filters; bounded
text and occurrence-range filters; sequence windows; pagination; and complete-
match facets for kinds, actions, checks, and references. Timeline results are
derived only from the replay-verified report and never create a second ledger.

## Execution metrics

`review-workspace-plan-execution-query --view metrics` derives deterministic
operational metrics from the typed source plan and replay report. It reports
integer-basis-point completion, declared estimate units, action timing and
transition counts, lane aggregation, dependency waits, required-check
coverage, blocked work, and the estimated critical path. It can be rendered as
canonical JSON, Markdown, or CSV through the portable release and never acts as
a scientific score.

## Execution operations

`review-workspace-plan-execution-query --view operations` projects the replayed
plan into a deterministic attention queue. Completed actions are excluded;
remaining actions are ranked into blocked, ready, in-progress, dependency-wait,
skipped, or queued classes using attention rank, plan priority, plan sequence,
and action ID. Each row includes public action context, unresolved
dependencies, event count, bounded rationale, recommended transition, and a
content address. The projection is read-only and does not assign work, mutate
the append-only ledger, infer identity, or make a scientific decision.

The operations projection links to the metrics content address and exports
deterministic JSON, Markdown, and CSV. Its schema and capability metadata are
available from `review-workspace-plan-execution-operations-schema` and
`review-workspace-plan-execution-operations-capabilities`.

Operations queries accept `--attention-kind`, `--status`, `--lane`,
`--action-kind`, `--action-id`, `--priority`, `--ready`,
`--dependency-action-id`, `--text`, `--offset`, and `--limit`. Results preserve
queue rank, expose complete-match facets for attention kinds, statuses, lanes,
action kinds, priorities, and dependencies, and include `has_more` plus the
first and last returned ranks.

## Execution transition frontier

`review-workspace-plan-execution-query --view transitions` expands every
planned action into the five explicit ledger transition kinds: start, complete,
block, skip, and reopen. Each option states whether the current state permits
it, whether it is executable without more input, and whether it is waiting on
dependencies, required public checks, or a bounded reason. It also carries the
last event ID and predecessor address so an explicit append can be preflighted
without trusting an unverified summary.

The transition frontier exports deterministic JSON, Markdown, and CSV. Queries
support `--action-id`, `--kind`, `--disposition`, `--status`, `--lane`,
`--action-kind`, `--priority`, `--executable`, `--permitted`, `--text`,
`--offset`, and `--limit`, with complete-match facets. Its schema and
capabilities are available from
`review-workspace-plan-execution-transitions-schema` and
`review-workspace-plan-execution-transitions-capabilities`; the transition-diff
schema and capabilities expose deterministic cross-snapshot changes.

## Execution simulation

`review-workspace-plan-execution-simulate` evaluates a bounded JSON array of
proposed transitions entirely in memory. Proposals use `action_id`, `kind`,
`event_id`, and `occurred_at`, with optional `reason`, `check_ids`,
`reference_addresses`, and `expected_previous_event_address`. The simulator
automatically links accepted proposals to the current hypothetical predecessor,
replays each proposal through the same state machine and completion gates as the
ledger, and stops at the first failure. Later proposals are returned as
`not_evaluated`; the persisted `events.jsonl` file is not opened for writing.

```text
glio-noncode review-workspace-plan-execution-simulate RUN_ID --data-root .glio --proposals proposals.json --include-report --output simulation.json
glio-noncode review-workspace-plan-execution-simulation-schema --output simulation-schema.json
glio-noncode review-workspace-plan-execution-simulation-capabilities --output simulation-capabilities.json
glio-noncode review-workspace-plan-execution-batch RUN_ID --data-root .glio --proposals proposals.json --include-simulation --output batch.json
glio-noncode review-workspace-plan-execution-batch-schema --output batch-schema.json
glio-noncode review-workspace-plan-execution-batch-capabilities --output batch-capabilities.json
glio-noncode review-workspace-plan-execution-audit RUN_ID --data-root .glio --include-report --output audit.json
glio-noncode review-workspace-plan-execution-audit-schema --output audit-schema.json
glio-noncode review-workspace-plan-execution-audit-capabilities --output audit-capabilities.json
```

The result includes the baseline and projected execution addresses, accepted
event IDs, per-proposal preflight dispositions, projected metrics, operations,
and transition-frontier addresses. The same read-only operation is available as
`GET /v1/runs/RUN_ID/review-workspace/plan/execution/simulate?proposals=<url-encoded-json-array>`;
add `include_report=true` when the projected replay report is needed. Simulation
reports export deterministic JSON, Markdown, and CSV from the Python API and
remain ephemeral rather than becoming release artifacts.

## Atomic execution batches

`review-workspace-plan-execution-batch` takes the same proposal array as the
simulator, captures the current execution address and event count, and appends
the accepted hypothetical events with one manifest refresh. Callers may supply
`--expected-execution-address`, `--expected-event-count`, and
`--expected-last-event-address` to reject stale writers deterministically. A
failed simulation or stale base returns a structured receipt and leaves the
ledger unchanged; a successful batch returns committed event IDs and the new
replay address. The CLI operation is the explicit write path. The HTTP write
surface is `POST /v1/runs/RUN_ID/review-workspace/plan/execution/batch` with a
JSON body containing `proposals` and optional expected-base fields; set
`include_simulation` or `include_report` to request expanded receipts.

## Independent execution-ledger audit

`review-workspace-plan-execution-audit` is a read-only integrity inspection
that opens the persisted ledger files directly and produces bounded findings.
It verifies the safe ledger directory, allowed filenames, regular-file and
UTF-8 requirements, JSONL parsing, canonical event bytes, manifest fields and
manifest address, typed replay, and the public-key boundary. An absent ledger
is reported as a valid empty replay with a warning; malformed or partial
ledgers fail closed with the specific filesystem, event, manifest, replay, or
boundary checks that failed. JSON, Markdown, and CSV output are deterministic,
and the optional report is available only in JSON output.

The same contract is exposed by
`GET /v1/runs/RUN_ID/review-workspace/plan/execution/audit`, with
`include_report=true`, `baseline_run_id`, and the same optional plan `config`
query parameters. Schema and capability endpoints are available at
`/v1/review-workspace/plan/execution/audit/schema` and
`/v1/review-workspace/plan/execution/audit/capabilities`.

## Portable execution release

`review-workspace-plan-execution-release` packages twenty exact-byte artifacts:
the typed execution report, human report, action CSV, event CSV, check CSV,
canonical `events.jsonl`, and five source-plan artifacts covering the typed plan,
plan Markdown, plan actions, plan lanes, and plan checks, plus metrics JSON,
Markdown, and CSV, plus operations JSON, Markdown, and CSV, plus transition-
frontier JSON, Markdown, and CSV. The manifest carries
each artifact's byte count, line count, media type, and content address, plus
execution, plan, metrics, operations, and transitions addresses.
`review-workspace-plan-execution-release-verify` independently validates safe
paths, artifact closure, nested report/action/check addresses, event-stream
reconciliation, metrics and operations derivation, transition-frontier
reconciliation, manifest bytes, and the public boundary. A verified package can
be loaded, queried, and diffed without a local runtime or plan store.

`review-workspace-plan-execution-release-query` applies the live bounded action
filters to a verified package; pass `--view events` for the same offline event
timeline and its sequence-aware facets, or `--view metrics` for the verified
metrics projection, `--view operations` for the verified attention queue, or
`--view transitions` for the verified transition preflight and its bounded
facets.
`review-workspace-plan-execution-release-diff`
compares source-plan action, lane, and check changes in addition to event IDs,
action status/address changes, execution checks, and artifact addresses between
two verified packages. Its nested metrics diff reports right-minus-left
completion, timing, check, dependency-wait, status-count, event-kind, action,
lane, and critical-path deltas. Its nested operations diff reports queue-count
and completion deltas, added/removed queue actions, rank movement, attention
class/status/lane changes, class and lane count deltas, and recommendation
changes. Its nested transition diff reports added, removed, changed, and
unchanged transition options, per-action recommendation movement, and
right-minus-left frontier count deltas. Release operations are read-only at the API boundary; filesystem
materialization remains an explicit CLI action.

## API

`GET /v1/review-workspace/schema` and
`GET /v1/review-workspace/capabilities` expose the contract. Use
`GET /v1/review-workspace/query/schema` and
`GET /v1/review-workspace/query/capabilities` for the bounded query contract.
`GET /v1/runs/{run_id}/review-workspace` for the current run and add
`baseline_run_id` to request verified cross-run deltas. Both runs must belong
to the same case and pass replay verification.

`GET /v1/runs/{run_id}/review-workspace/query` accepts the same filters as the
CLI through query parameters. Repeated `state` and `source_id` parameters are
allowed; `collection`, `text`, `context_key`, `item_type`, `dimension`,
`priority`, `offset`, `limit`, and `baseline_run_id` are scalar parameters.

`GET /v1/review-workspace/plan/schema` and
`GET /v1/review-workspace/plan/capabilities` expose the triage-plan contract.
`GET /v1/runs/{run_id}/review-workspace/plan` returns the ordered plan and
accepts `baseline_run_id` plus an optional JSON `config` object. The nested
`/plan/query` route accepts `lane`, `action_kind`, `queue_item_id`, `target_id`,
`target_type`, `state`, repeated `priority`, `text`, `offset`, `limit`, and
`baseline_run_id` filters. API responses remain read-only and payload-free.

`GET /v1/review-workspace/plan/execution/schema` and
`GET /v1/review-workspace/plan/execution/capabilities` expose the append-only
execution contract. `GET /v1/runs/{run_id}/review-workspace/plan/execution`
replays the local ledger; `/execution/query` applies bounded action filters by
default and accepts `view=events`, `view=metrics`, or `view=operations`.
It also accepts `view=transitions` for a complete transition preflight.
Transition query parameters include `kind`, `disposition`, `status`, `lane`,
`action_kind`, `action_id`, `priority`, `executable`, `permitted`, `text`,
`offset`, and `limit`.
Operations query parameters include `attention_kind`, `status`, `lane`,
`action_kind`, `action_id`, `priority`, `ready`, `dependency_action_id`,
`text`, `offset`, and `limit`.
Timeline filters
include `kind`, `event_id`, `action_id`, `check_id`, `reference_address`,
`occurred_from`, `occurred_to`, `sequence_start`, `sequence_end`, `text`,
`offset`, and `limit`. Ledger writes remain an explicit CLI operation so the
HTTP service stays read-only.

`GET /v1/review-workspace/plan/execution-release/schema` and
`GET /v1/review-workspace/plan/execution-release/capabilities` expose the
portable handoff contract. `GET
/v1/runs/{run_id}/review-workspace/plan/execution-release` returns the current
release projection in memory, and `/execution-release/query` applies its
bounded filters. Add `view=events` to query the verified event timeline with
the same ordering and facets, `view=metrics` for derived operational metrics,
or `view=operations` for the verified attention queue, or `view=transitions`
for the verified transition preflight. The HTTP release
projection is read-only and does not write a filesystem package; operations
filters use the same names as the live query.

## Offline release operations

`review-workspace-release-load` verifies and reopens the public JSON projection
without a local run store. `review-workspace-release-index` and
`review-workspace-release-query` run the same facet and pagination contract as
the live workspace. `review-workspace-release-diff` compares exact artifact
addresses and collection item addresses between two verified releases. Any
manifest, byte, path, or boundary failure blocks loading before report rows
are exposed. `review-workspace-release-plan` runs the same triage-plan
synthesis over the verified report, so live and offline action addresses can be
compared without rehydrating a runtime.

The API response contains independent content addresses for the complete
workspace and every review collection item. This allows a renderer or offline
handoff to verify exact receipts without trusting a summary score.

## Boundary and limitations

Review state indicates work to adjudicate, not truth. Evidence state remains
distinct from review state: supported, contradictory, measured-negative,
absent, out-of-domain, and abstained claims are not silently converted into a
positive or negative conclusion. Source IDs and receipt IDs are declarations;
they do not establish external validation or scientific reproducibility by
themselves.
