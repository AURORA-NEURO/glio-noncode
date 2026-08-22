# Workspace beta frontier data dictionary

## Context

`context_key` is the exact six-part key:

```text
genome_build|disease_class|age_group|cell_state|territory|treatment_phase
```

The fixture context is:

```text
GRCh38|glioma|adult|stem_like|core|untreated
```

The boundary value is `public_aggregate_non_patient`.

## Topology fields

| Field | Meaning |
| --- | --- |
| `feature_id` | stable loop feature identifier |
| `chromosome_a`, `start_a`, `end_a` | first interval |
| `chromosome_b`, `start_b`, `end_b` | second interval |
| `signal` | non-negative descriptive signal |
| `source_id`, `source_version` | source receipt fields |
| `raw_hash` | input content receipt |
| `resolution` | optional coordinate resolution |
| `focus_*` | bounded viewport focus |
| `max_nodes`, `max_edges` | output bounds |

Promoter-capture contacts use promoter and target element IDs plus one interval
for each endpoint. Contact scores and activity-by-contact results preserve
component values rather than hiding the underlying measurements.

## Causal fields

| Field | Meaning |
| --- | --- |
| `mediator_kind` | sequence-to-element, element-to-gene, or gene-to-state |
| `source_node`, `target_node` | directed chain endpoints |
| `state` | supported, partial, abstained, out-of-domain, or contradictory |
| `support` | bounded descriptive support when present |
| `uncertainty` | bounded descriptive uncertainty |
| `sensitivity` | optional sensitivity summary |
| `evidence_ids` | supporting receipt identifiers |
| `negative_evidence_ids` | against-direction or negative-control identifiers |
| `source_versions` | source version receipts |

## Posterior fields

| Field | Meaning |
| --- | --- |
| `hypothesis_id` | declared hypothesis identifier |
| `declared_prior` | declared prior proxy |
| `evidence_support` | declared support, nullable when absent |
| `posterior_proxy` | descriptive posterior proxy |
| `calibration_status` | calibration declaration |
| `component_id` | stable contribution ID |
| `contribution` | signed component contribution |
| `residual` | declared support minus exact-context component total |
| `normalized_shares` | absolute component shares |

## Table fields

| Field | Meaning |
| --- | --- |
| `record_id` | stable workspace record identifier |
| `record_type` | typed workspace row role |
| `channel` | dimension extracted from fields or tags |
| `tier` | declared evidence tier |
| `confidence` | bounded descriptive confidence |
| `source_ids` | source receipt identifiers |
| `facets` | pre-pagination dimension counts |
| `offset`, `limit` | bounded page selection |

## State rules

`supported` means the projection found exact-context inputs sufficient for its
own declared summary. `partial` means visible inputs remain unresolved or do
not reconcile. `absent` means no matching rows were found. `abstained` means an
essential input was not declared. `out_of_domain` means the requested context
does not match. `contradictory` retains mutually inconsistent evidence.
