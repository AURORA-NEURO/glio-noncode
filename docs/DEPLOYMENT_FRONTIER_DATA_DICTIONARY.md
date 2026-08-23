# Deployment frontier data dictionary

## Identity and context

| Field | Type | Required | Meaning | Boundary |
| --- | --- | ---: | --- | --- |
| `fixture_id` | string | yes | stable fixture identity | replay key |
| `fixture_version` | string | yes | contract version | migration key |
| `context_key` | string | yes | six-component exact join context | no implicit transport |
| `record_id` | string | yes | stable operation-row identity | duplicate-free |
| `operation` | enum | yes | one of C13–C16 operation families | typed dispatch |
| `role` | enum | yes | `positive` or `control` | expected-state boundary |
| `source_ids` | array[string] | yes | public source receipt links | provenance |
| `content_address` | SHA-256 string | yes | canonical content address | replay/integrity |

The deployment context is `GRCh38|diffuse_glioma|adult|aggregate|platform|research`.
The fields are intentionally narrower than a participant-level data model.

## Source receipts

| Field | Type | Meaning |
| --- | --- | --- |
| `source_id` | string | stable public portal identity |
| `title` | string | human-readable portal name |
| `uri` | HTTPS string | public provenance anchor |
| `scope` | string | declared aggregate or vocabulary scope |
| `version` | string | portal or receipt version label |
| `content_address` | SHA-256 string | receipt identity |

The checked-in fixture uses GDC, ENCODE, 4D Nucleome, DepMap, and GA4GH
receipts. The fixture does not download records during evaluation.

## C13 fields

| Field | Type | Meaning |
| --- | --- | --- |
| `requests` | array[object] | policy requests to evaluate |
| `request_id` | string | request identity |
| `subject_id` | string | declared operational principal label |
| `action` | string | requested action such as `read` |
| `roles` | array[string] | roles presented for the request |
| `required_role` | string, optional | role required by the request |
| `sensitive` | boolean, optional | whether the request crosses a sensitive boundary |
| `network` | boolean, optional | whether network access is requested |
| `retention_days` | integer | requested retention interval |
| `policies` | object | named policy rules |

The output retains decision IDs and reason classes. It does not copy principal
values into release summaries.

## C14 fields

| Field | Type | Meaning |
| --- | --- | --- |
| `bundle_id` | string | local bundle identity |
| `platform` | string | target platform label |
| `runtime_version` | string | required runtime |
| `offline` | boolean | offline-readiness boundary |
| `artifacts` | array[object] | files or package units |
| `artifact_id` | string | artifact identity |
| `version` | string | artifact version |
| `digest` | string | SHA-256-style artifact digest |
| `size_bytes` | integer | declared artifact size |
| `services` | array[object] | local service inventory |
| `service_id` | string | service identity |
| `depends_on` | array[string] | local dependency IDs |
| `environment_requirements` | object | non-secret runtime requirements |

An online-only bundle remains `hold`; the adapter is a manifest builder and
does not start services.

## C15 fields

| Field | Type | Meaning |
| --- | --- | --- |
| `plan_id` | string | coordination plan identity |
| `privacy_budget` | integer | maximum declared task cost |
| `minimum_site_count` | integer | minimum eligible sites per task |
| `tasks` | array[object] | aggregate task declarations |
| `task_id` | string | task identity |
| `privacy_cost` | integer | cost charged to the plan |
| `minimum_sample_count` | integer | aggregate minimum |
| `site_ids` | array[string], optional | locality constraint |
| `sites` | array[object] | site capability declarations |
| `site_id` | string | site identity |
| `available` | boolean | current availability declaration |
| `sample_count` | integer | aggregate count only |
| `supported_contexts` | array[string] | exact contexts supported |

Site outputs contain assignment state and reason only. They do not include raw
site rows or participant-level values.

## C16 fields

| Field | Type | Meaning |
| --- | --- | --- |
| `release_id` | string | transition identity |
| `current_version` | string | currently active version |
| `requested_version` | string | requested transition target |
| `action` | enum | `release` or `rollback` |
| `previous_version` | string, optional | required for rollback |
| `checks` | object[string,bool] | named release gate results |
| `required_checks` | array[string] | exact gate set |
| `failed_checks` | array[string] | retained failed gate names |

## Shared output rules

Every output includes a content address. Outputs may include IDs, state,
counts, issue codes, and references to other receipts. Outputs must not include
passwords, tokens, API keys, signing secrets, or participant-level data.

## State vocabulary

| State | Meaning |
| --- | --- |
| `ready` | positive operation passed its declared boundary |
| `hold` | operation is not releaseable but remains reviewable |
| `denied` | policy or release gate rejected the request |
| `released` | release checks passed |
| `rolled_back` | rollback checks passed |
| `review` | an evidence row remains for human inspection |
