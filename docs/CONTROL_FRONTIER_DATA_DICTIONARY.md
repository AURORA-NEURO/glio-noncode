# Control frontier data dictionary

The dictionary below defines the stable fields used by the Domain 16 C05-C12
aggregate runtime. Field names are shared by fixture JSON, evaluation JSON,
review CSV, metrics CSV, and the Markdown report wherever the projection
supports them.

## Identity and boundary fields

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `fixture_id` | string | yes | Stable name of the aggregate fixture. |
| `fixture_version` | string | yes | Versioned contract label for the fixture. |
| `context_key` | string | yes | Exact context tuple used for closure checks. |
| `evidence_boundary` | string | yes | Declared limit of what the receipts support. |
| `record_id` | string | yes | Stable row ID such as `C05-POS-001`. |
| `operation` | enum | yes | One of the eight C05-C12 operation names. |
| `role` | enum | yes | `positive` or `control`. |
| `content_address` | string | yes | SHA-256 address of the object body. |

The context key is not parsed into a new scientific taxonomy by this package.
It is compared exactly and retained as a single boundary value. A context
mismatch is a routing issue, not evidence about the underlying domain.

## Source receipt fields

| Field | Type | Meaning |
| --- | --- | --- |
| `source_id` | string | Stable source key referenced by rows. |
| `title` | string | Human-readable aggregate receipt title. |
| `uri` | HTTPS string | Public source location or placeholder receipt. |
| `access_note` | string | Scope and access explanation. |
| `content_address` | string | Address of the source receipt body. |

Source receipts are operational references. The fixture uses public HTTPS
placeholder locations and aggregate descriptions. No row-level private data is
stored in the fixture or produced by the runtime.

## Record fields

| Field | Type | Meaning |
| --- | --- | --- |
| `source_ids` | tuple[string] | Receipts supporting the row payload. |
| `payload` | object | Operation-specific typed input projection. |
| `expected_state` | enum | State the row is designed to exercise. |
| `expected_issue_codes` | tuple[string] | Ordered issue vocabulary for controls. |
| `notes` | string | Boundary explanation for the row. |

Expected values are fixture declarations. Evaluation compares them with the
observed operation result and never treats an expected value as an observed
fact.

## Evaluation fields

| Field | Type | Meaning |
| --- | --- | --- |
| `state` | enum | Observed operation state. |
| `accepted` | boolean | Positive row passed its declared acceptance rule. |
| `issue_codes` | tuple[string] | Observed, ordered issue vocabulary. |
| `output` | object | Structured operation receipt. |
| `check_id` | string | Stable assertion key. |
| `passed` | boolean | Whether the assertion passed. |
| `observed` | any | Projection of the observed value. |
| `required` | any | Projection of the required value. |
| `detail` | string | Human-readable assertion boundary. |

The five row assertions are state equality, issue equality, role separation,
content addressing, and structured output. A check may expose a boolean,
number, string, or bounded list, but it does not include raw sensitive values.

## Operation payload fields

### Policy and claim gate

`request_id`, `context_key`, `claim_ceiling`, `source_ids`, `mutation_scope`,
`sensitive_paths`, `network_sources`, and `declared_data_scope` describe the
admission request. Control rows vary one boundary at a time.

### Budget and resource scheduler

`work_items`, `dependencies`, `cpu`, `memory`, `gpu`, `storage`, `network`,
`seconds`, `cost`, and `budgets` describe a deterministic schedule request.
The adapter returns selected, deferred, rejected, cycle, and resource totals.

### Deterministic fallback

`failure`, `candidates`, `required_inputs`, `output_contract`, `network_allowed`,
and `remaining_cost` describe route selection. Candidate receipts retain
rejection reasons in priority order.

### Human review router

`items`, `max_items`, `default_role`, `source_ids`, and `context_key` describe
queue construction. Queue items retain priority, reason, role, source IDs,
and omission state.

### Execution ledger

`execution_id`, `context_key`, and `events` describe event replay. Each event
has `event_id`, `kind`, and `message`; contextual events may also carry an
explicit `context_key`.

### Model registry

`records` contain `model_id`, `version`, `model_family`, `artifact_digest`,
`input_contract`, `output_contract`, `supported_contexts`, `status`,
`source_ids`, `license_id`, and `evaluation_receipt`. `query` selects the
requested model, context, and contracts.

### Data/reference registry

`records` contain `dataset_id`, `version`, `reference_kind`, `source_uri`,
`checksum`, `format`, `schema_hash`, `supported_contexts`, `coordinate_system`,
`license_id`, `status`, `source_ids`, and `retrieval_receipt`. `query` selects
the exact dataset, context, coordinate, and license.

### Drift and OOD monitor

`observations` contain `observation_id`, `monitor_id`, `feature_id`,
`context_key`, `metric`, `reference_value`, `current_value`, `watch_threshold`,
`drift_threshold`, `in_domain`, `support_score`, `source_ids`, and `raw_hash`.
The monitor returns a declared state and an issue tuple.

## Projection guarantees

JSON serialization sorts keys for hashing and converts enums to their string
values. CSV serialization keeps stable column order. Markdown rendering uses
the same fixture ID, context key, counts, and state distribution as JSON.
Loader round trips verify the fixture address after reconstructing typed rows.
