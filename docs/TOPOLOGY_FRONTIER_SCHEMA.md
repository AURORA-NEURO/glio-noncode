# Domain 09 topology frontier schema

## Root fixture

```json
{
  "fixture_id": "topology-frontier-public-aggregate",
  "fixture_version": "2026.08.d09-c13-c16.v1",
  "context_key": "GRCh38|glioma|adult|stem_like|tumor|unknown",
  "evidence_boundary": "public_aggregate_non_patient",
  "sources": [],
  "records": [],
  "content_address": "sha256:..."
}
```

The source and record arrays are non-empty. Source IDs are unique. Record IDs
are unique. Every record operation belongs to the four-operation registry.

## Source receipt

| Field | Type | Rule |
| --- | --- | --- |
| `source_id` | string | non-empty, unique in fixture |
| `title` | string | non-empty display title |
| `uri` | string | HTTPS locator |
| `source_kind` | string | public archive or reference scope |
| `release` | string | explicit source release |
| `scope` | string | aggregate or reference purpose |
| `content_address` | string | `sha256:` prefix |

## Record receipt

| Field | Type | Rule |
| --- | --- | --- |
| `record_id` | string | unique, operation-prefixed |
| `operation` | enum | one of four Domain 09 operations |
| `role` | enum | `positive` or `control` |
| `context_key` | string | exact fixture context |
| `source_ids` | array | non-empty and source-closed |
| `payload` | object | contains serialized `input_text` |
| `expected_state` | enum | `supported`, `partial`, `out_of_domain`, `invalid` |
| `expected_issue_codes` | array | issue floor for controls |
| `description` | string | non-empty review explanation |
| `content_address` | string | `sha256:` prefix |

## Operation payloads

### C13

Required keys are `input_text`, `minimum_contact_score`, and
`minimum_sources`. Input rows contain amplicon, element, gene, score, source,
and context fields.

### C14

Required keys are `input_text` and `switch_threshold`. Input rows contain
region, previous score, current score, and context fields.

### C15

Required keys are `input_text` and `minimum_effective_signal`. Input rows contain
path, node, edge uncertainty, signal, and context fields.

### C16

Required keys are `input_text`, `bundle_id`, and `assay_ids`. Input rows contain
path and context fields. A publication bundle cannot be accepted without assay
receipts.

## Receipt summary

Receipt summaries are sanitized. They may include counts, states, identifiers,
bounded values, issue codes, and nested content addresses. They must not include
the raw `input_text` or the complete record payload.

## Schema checks

Each operation schema produces five checks:

1. schema is present;
2. four records are covered;
3. states use the declared vocabulary;
4. issues use the declared vocabulary;
5. schema content address is present.

Four schemas therefore produce 20 checks. A schema failure blocks the quality
gate even when the current fixture evaluation happens to pass.

## Address rules

Addresses are computed from normalized structured values. The following values
must be stable before hashing:

- enum values are serialized by their string value;
- tuples preserve declared order;
- sets are sorted before inclusion;
- dictionaries use stable key ordering;
- numeric transforms are rounded at their operation boundary;
- omitted fields are not silently replaced by arbitrary defaults in reports.

## Export fields

Receipt CSV fields are record ID, operation, role, context, adapter state, two
counts, issue codes, expected state, and content address. Review CSV fields are
record ID, operation, role, state, priority, action, issue codes, context, and
content address. Metric CSV adds operation totals and its address.

Markdown is a human-readable projection over the review queue. It does not
change state, issue, source, or address values.
