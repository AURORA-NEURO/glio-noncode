# Workspace frontier data dictionary

## Scope

This dictionary describes the public aggregate data used to verify Domain 15
C01–C04. It is a contract reference for contributors, reviewers, and future
client implementations.

## Fixture constants

| Constant | Value | Use |
| --- | --- | --- |
| `WORKSPACE_FRONTIER_FIXTURE_VERSION` | `2026.08.d15-c01-c04.v1` | fixture revision |
| `WORKSPACE_FRONTIER_CONTEXT_KEY` | `GRCh38|glioma|adult|stem_like|core|untreated` | exact context |
| `WORKSPACE_FRONTIER_EVIDENCE_BOUNDARY` | `public_aggregate_non_patient` | data boundary |
| `WORKSPACE_FRONTIER_SOURCE_COUNT` | `5` | source receipt count |
| `WORKSPACE_FRONTIER_POSITIVE_COUNT` | `4` | positive record count |
| `WORKSPACE_FRONTIER_CONTROL_COUNT` | `12` | control record count |

## Operations

| Operation | Value | Positive record |
| --- | --- | --- |
| case workspace | `case_workspace` | `C01-POS-001` |
| cohort workspace | `cohort_workspace` | `C02-POS-001` |
| variant explorer | `variant_explorer` | `C03-POS-001` |
| regulatory track browser | `regulatory_track_browser` | `C04-POS-001` |

## Roles

| Role | Meaning | Acceptance |
| --- | --- | --- |
| `positive` | expected supported or explicitly partial path | may be accepted |
| `control` | expected boundary, absence, invalid, or parse path | never promoted |

## Source receipt dictionary

| Source ID | Display title | Scope |
| --- | --- | --- |
| `case-manifest` | Public case manifest receipt | aggregate manifest identity and versions |
| `cohort-public` | Public aggregate cohort receipt | pseudonymous aggregate record shape |
| `track-public` | Public regulatory interval receipt | annotation-only interval source |
| `workbench` | Research workbench contract | context and provenance vocabulary |
| `accessibility` | Public accessibility guidance receipt | labels, focus, keyboard, reading order |

## Case data

### Variant

The variant dictionary uses the repository `VariantIdentity` model.

| Field | Example | Meaning |
| --- | --- | --- |
| `variant_id` | `v-frontier-1` | stable fixture identity |
| `kind` | `snv` | typed variation kind |
| `chromosome` | `7` | source chromosome |
| `start` | `100` | one-based start |
| `end` | `100` | one-based end |
| `reference` | `A` | reference allele |
| `alternate` | `T` | alternate allele |
| `genome_build` | `GRCh38` | assembly |
| `origin` | `somatic` | declared origin category |
| `sample_id` | `aggregate-sample` | aggregate placeholder |

### Candidate element

| Field | Example | Meaning |
| --- | --- | --- |
| `element_id` | `element-frontier-1` | interval identity |
| `chromosome` | `7` | element chromosome |
| `start` | `90` | interval start |
| `end` | `125` | interval end |
| `element_type` | `candidate_enhancer` | annotation type |
| `source_id` | `track-public` | source receipt |
| `target_genes` | `GENE1` | declared candidate target |
| `state_ids` | `stem_like` | declared cell state |
| `features` | score map | descriptive feature values |

## Cohort data

| Field | Example | Meaning |
| --- | --- | --- |
| `record_id` | `cohort-r1` | stable row identity |
| `variant` | typed variant object | canonical variant |
| `context_key` | default context | exact applicability |
| `source_id` | `cohort-public` | source receipt |
| `sample_id` | `aggregate-cohort-r1` | aggregate placeholder |
| `callable` | `true` | selection eligibility |
| `sequence_context` | `ACGTACGT` | bounded sequence context |
| `chromatin_features` | score map | descriptive feature values |
| `annotations` | object | source annotations |

The positive path contains two callable rows. One control contains a single
non-callable row. One control contains no rows. One control contains a row in a
different context.

## Accessibility data

### Case metadata

| Field | Example |
| --- | --- |
| `keyboard_order` | ordered section IDs |
| `labels_present` | `true` |
| `focus_boundary` | `workspace-case-public` |
| `reading_order` | `section-order` |

### Cohort metadata

| Field | Example |
| --- | --- |
| `row_label` | `cohort record` |
| `summary_label` | `cohort summary` |
| `controls_label` | `matched controls` |

### Track metadata

| Field | Example |
| --- | --- |
| `interval_label` | `regulatory interval` |
| `coordinate_label` | `genomic coordinate` |
| `issue_label` | `parse issue` |

## Fixture record IDs

| Record range | Surface | Count |
| --- | --- | ---: |
| `C01-*` | case workspace | 4 |
| `C02-*` | cohort workspace | 4 |
| `C03-*` | variant explorer | 4 |
| `C04-*` | regulatory track browser | 4 |

The positive ID suffix is `POS-001`. Control IDs use `CTRL-001` through
`CTRL-003`. This convention makes the review queue and CSV export easy to
inspect without relying on array position.

## Metrics

The metrics report contains 13 descriptive metrics.

| Metric | Interpretation |
| --- | --- |
| `positive_acceptance_rate` | accepted positive rows divided by positives |
| `control_rejection_rate` | rejected controls divided by controls |
| `execution_check_pass_rate` | passed checks divided by checks |
| `context_preservation_rate` | passed context checks divided by context checks |
| `addressed_execution_rate` | addressed executions divided by executions |
| `case_surface_count` | case rows divided by total rows |
| `cohort_surface_count` | cohort rows divided by total rows |
| `variant_surface_count` | variant rows divided by total rows |
| `track_surface_count` | track rows divided by total rows |
| `review_state_rate` | non-supported rows divided by total rows |
| `source_boundary_check_rate` | boundary check result |
| `issue_visibility_rate` | issue/state agreement rate |
| `output_retention_rate` | non-empty outputs divided by executions |

These are fixture metrics, not population estimates or clinical probabilities.

## Artifact dictionary

| Artifact ID | Kind | Parent |
| --- | --- | --- |
| `workspace-artifact-fixture` | fixture | none |
| `workspace-artifact-evaluation` | evaluation | fixture |
| `workspace-artifact-metrics` | metrics | evaluation |
| `workspace-artifact-quality` | quality | evaluation |
| `workspace-artifact-runtime` | runtime | evaluation, metrics |
| `workspace-artifact-bundle` | bundle | fixture, evaluation, metrics |
| `workspace-artifact-release` | release | bundle, quality, runtime |

## Runtime dictionary

| Stage ID | Description |
| --- | --- |
| `fixture-load` | load bounded public aggregate fixture |
| `contract-load` | load four operation contracts |
| `surface-execution` | execute four workspace surfaces |
| `metric-measurement` | measure descriptive metrics |
| `lineage-build` | construct acyclic source lineage |
| `policy-review` | apply research-use decisions |
| `reconciliation` | compare expected and observed rows |
| `bundle-assembly` | assemble release inputs |

## Review queue dictionary

| Field | Meaning |
| --- | --- |
| `item_id` | queue item identity |
| `record_id` | fixture execution row |
| `operation` | workspace surface |
| `priority` | high, medium, or low |
| `disposition` | ready, hold, or withhold |
| `issue_codes` | unresolved issue set |
| `source_ids` | source receipts |
| `rationale` | human-readable review reason |
| `content_address` | stable queue row address |

## Export formats

JSON is intended for programmatic use. Canonical JSON is intended for stable
address comparison. Review CSV is intended for bounded inspection and contains
one header plus 16 rows. The manifest export contains the fixture ID, run ID,
boundary, release ID, acceptance state, and root addresses.

## Data handling rules

1. Keep aggregate labels aggregate.
2. Keep exact context on every record.
3. Keep source IDs and content addresses.
4. Keep parse and selection issues visible.
5. Keep positive and control roles separate.
6. Do not infer missing relationships.
7. Do not convert interval overlap into mechanism.
8. Do not use fixture metrics as population estimates.
9. Do not add individual-level rows without a new boundary review.
10. Do not alter fixture values without a fixture-version decision.
