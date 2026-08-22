# Workspace frontier schema

## Schema version

The current schema manifest is `2026.08.d15.v1`. It contains four operation
schemas and a shared state vocabulary. Every field specification has a content
address and a semantic role.

## Shared state vocabulary

```text
supported
partial
absent
abstained
out_of_domain
invalid
```

The values are descriptive display states. They do not represent clinical
classification and should not be converted into a risk score.

## Shared identity fields

| Field | Type | Required | Role |
| --- | --- | ---: | --- |
| `workspace_id` | string | yes | immutable workspace snapshot identity |
| `context_key` | context-key | yes | exact applicability boundary |
| `record_id` | string | yes | stable row identity |
| `source_ids` | array[string] | no | source receipt references |
| `state` | enum | yes | explicit research-display state |
| `content_address` | sha256 string | yes | deterministic payload address |

## Context-key grammar

The frontier uses six pipe-delimited parts:

```text
genome_build|disease_class|age_group|cell_state|territory|treatment_phase
```

The default value is:

```text
GRCh38|glioma|adult|stem_like|core|untreated
```

The key is compared as an exact string at workspace boundaries. A future
structured context validator may add normalized fields, but it must preserve
the exact key in serialized output.

## Case workspace fields

### Input

| Field | Type | Required | Notes |
| --- | --- | ---: | --- |
| `case_id` | string | yes | source case identity |
| `subject_id` | string | yes | aggregate placeholder in fixture |
| `context_key` | context-key | yes | exact case context |
| `variants` | array[variant] | yes | at least one typed variant |
| `candidate_elements` | array[element] | no | context-qualified intervals |
| `input_versions` | object | no | source version receipts |
| `accessibility` | object | yes in fixture | labels and navigation metadata |

### Output

| Field | Type | Required | Notes |
| --- | --- | ---: | --- |
| `workspace_id` | string | yes | `case:<case_id>` |
| `state` | enum | yes | may be partial without dossier |
| `section_ids` | array[string] | yes | five ordered sections |
| `record_ids` | array[string] | yes | variant and element identities |
| `page_total` | integer | yes | bounded search total |
| `facets` | object | yes | record, state, and source counts |
| `warnings` | array[string] | yes | limitations and missing sections |
| `input_address` | sha256 string | yes | manifest address |

The five standard sections are `variants`, `regulatory-elements`,
`hypotheses`, `evidence`, and `validation`. A section can exist even when no
records are available; its description explains the limitation.

## Cohort workspace fields

### Input

| Field | Type | Required | Notes |
| --- | --- | ---: | --- |
| `evidence_id` | string | yes | discovery envelope identity |
| `query_id` | string | yes | selection contract identity |
| `context_key` | context-key | yes | exact query context |
| `require_callable` | boolean | yes | callable-space selection policy |
| `records` | array[cohort-record] | yes | selected and candidate rows |
| `accessibility` | object | yes in fixture | row and section labels |

### Output

| Field | Type | Required | Notes |
| --- | --- | ---: | --- |
| `workspace_id` | string | yes | `cohort:<evidence_id>` |
| `query_record_count` | integer | yes | selected record count |
| `excluded_count` | integer | yes | exact-context exclusions |
| `excluded_reasons` | object | yes | reason-to-count map |
| `section_ids` | array[string] | yes | cohort, background, controls |
| `facets` | object | yes | record, state, source counts |
| `warnings` | array[string] | yes | research limitations |
| `input_address` | sha256 string | yes | query result address |

The three standard sections are `cohort-records`, `background`, and `controls`.
Control candidates are not merged into selected cohort rows.

## Variant detail fields

| Field | Type | Required | Nullable | Notes |
| --- | --- | ---: | ---: | --- |
| `workspace_id` | string | yes | no | containing snapshot |
| `variant_id` | string | yes | no | requested identity |
| `state` | enum | yes | no | supported or abstained |
| `variant_record_id` | string | no | yes | absent on abstention |
| `related_record_ids` | array[string] | yes | no | declared relationships only |
| `related_by_type` | object | yes | no | typed relationship groups |
| `warnings` | array[string] | yes | no | absence or boundary notes |
| `content_address` | sha256 string | yes | no | stable detail payload |

`related_record_ids` may be empty. Empty is different from a missing field and
means the containing workspace declared no related rows.

## Regulatory track fields

### Input

| Field | Type | Required | Notes |
| --- | --- | ---: | --- |
| `source_id` | string | yes | track receipt identity |
| `genome_build` | string | yes | coordinate assembly |
| `text` | string | yes | BED, narrowPeak, GFF3, or JSON |
| `context_key` | context-key | yes | exact track context |
| `accessibility` | object | yes in fixture | interval and issue labels |

### Output

| Field | Type | Required | Notes |
| --- | --- | ---: | --- |
| `workspace_id` | string | yes | source and input hash identity |
| `feature_count` | integer | yes | successfully parsed features |
| `issue_count` | integer | yes | parser issue count |
| `record_ids` | array[string] | yes | feature IDs |
| `coordinate_labels` | array[string] | yes | normalized closed intervals |
| `page_total` | integer | yes | bounded search total |
| `facets` | object | yes | source and state counts |
| `warnings` | array[string] | yes | annotation-only and parse notes |
| `input_address` | sha256 string | yes | batch address |

Coordinates are normalized by the existing track parser. The public fixture
expects `chr7:100-120` and `chr7:181-230` after normalization.

## Source receipt fields

| Field | Type | Required | Constraint |
| --- | --- | ---: | --- |
| `source_id` | string | yes | unique within fixture |
| `title` | string | yes | non-empty display title |
| `uri` | HTTPS URI | yes | must start with `https://` |
| `access_note` | string | yes | scope and access boundary |
| `content_address` | sha256 string | yes | receipt address |

Source receipts are not citations for scientific conclusions. They document
the public aggregate boundary used by the fixture.

## Issue vocabulary

| Code | Surface | Meaning |
| --- | --- | --- |
| `missing_dossier` | case | optional dossier snapshot not supplied |
| `context_mismatch` | all | requested context differs from fixture |
| `invalid_workspace_input` | case, cohort, variant | typed workspace input invalid |
| `duplicate_variant_id` | case | duplicate identity rejected |
| `no_matching_records` | cohort | no row satisfies selection |
| `variant_absent` | variant | exact requested identity absent |
| `track_parse_issue` | track | feature batch retains parse issue |
| `invalid_track_input` | track | parser input is empty or malformed |

Issue codes are sorted before execution addressing. Adding a new code requires
updates to contracts, fixture controls, evaluation checks, docs, and CLI tests.

## Addressing rules

Content addresses are calculated from canonical typed payloads. Runtime IDs and
human-readable run IDs are not used as inputs to deterministic fixture
execution addresses. Records and execution outputs are addressed separately.

An address must:

1. start with `sha256:`;
2. be stable across two replays;
3. change when declared payload content changes;
4. remain available in the exported JSON;
5. be referenced by lineage or artifact inventory when it is a release input.

## Serialization rules

JSON exports use sorted keys, two-space indentation, and a trailing newline.
Canonical exports use the repository canonical JSON helper. Enums serialize to
their stable string values. Tuples serialize as arrays. Mapping keys remain
strings. A fixture round trip must recreate enum types before execution.

## Accessibility metadata

The fixture carries:

- keyboard order;
- labels for rows and sections;
- focus boundary;
- reading order;
- interval coordinate label;
- parse issue label.

The metadata documents what a renderer must preserve. It is not a substitute
for browser-level or screen-reader conformance testing.

## Compatibility promise

New fields may be added with an explicit schema revision. Existing state values,
issue codes, context keys, and content-address rules must not be silently
changed. A breaking change requires a new fixture version and updated replay
expectations.
