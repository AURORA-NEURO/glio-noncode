# Platform frontier data dictionary

The C01-C04 JSON and CSV projections share the following fields. The
dictionary keeps operational metadata stable across CLI, package, review, and
release surfaces.

## Identity fields

| Field | Type | Scope | Meaning |
| --- | --- | --- | --- |
| `fixture_id` | string | fixture | Stable fixture identity. |
| `fixture_version` | string | fixture | Contract version. |
| `context_key` | string | fixture/row | Exact platform context. |
| `evidence_boundary` | string | fixture/release | Limit of supported receipts. |
| `record_id` | string | row/execution | Stable positive or control row. |
| `operation` | enum | row/execution | One of C01, C02, C03, or C04. |
| `role` | enum | row/execution | `positive` or `control`. |
| `content_address` | SHA-256 | all | Address of the canonical body. |

## Planning fields

`mission_id`, `project_id`, `intended_use`, `requested_question`,
`claim_ceiling`, `allowed_source_ids`, `allowed_data_scopes`,
`allowed_mutations`, `requested_roles`, and `workflow_id` describe a bounded
mission request. The planner output retains `plan_id`, selected role IDs,
selected tool IDs, registry address, workflow ID, step IDs, and warnings.

An empty `requested_roles` array is a deliberate abstention input. It is not a
missing JSON field and must not cause the planner to insert default work.

## Workflow fields

Each step has `step_id`, `kind`, `depends_on`, `resource`, `optional`,
`deterministic`, `input_contract`, and `output_contract`. Resource fields are
`cpu`, `memory_gb`, `gpu_count`, `storage_gb`, `network_egress`, and
`max_seconds`.

The compiled projection adds `step_ids`, `step_count`, `total_cpu`,
`peak_memory_gb`, `total_storage_gb`, `max_seconds`, and `warnings`. A cycle or
missing dependency produces an explicit issue code; it does not produce a
partial topological order.

## Registry fields

The tool query uses `tool_id`, `expected_input_contract`,
`expected_output_contract`, `expected_tool_count`, and `kind`. The descriptor
projection uses `name`, `input_contract`, `output_contract`, `safety_class`,
`deterministic`, `network_egress`, `mutation_scope`, `tool_count`, and
`registry_address`.

## Sandbox fields

The invocation uses `request_id`, `role_id`, `tool_id`, `register_handler`,
`input_payload`, and `kind`. The safe run projection contains `state`,
`admitted`, `admission_reason`, `response_type`, `cached`, `event_ids`,
`warnings`, `result_state`, and `result_error_code`.

Raw sensitive values are never part of a platform execution projection. A
policy rejection may retain a field path or stable error code, but not the
field value.

## State and issue vocabulary

Planning uses `ready`, `abstained`, `rejected`, or `partial`. Workflow
compilation uses `ready`, `blocked`, or `partial`. Registry resolution uses
`compatible`, `incompatible`, or `rejected`. Sandbox admission uses
`admitted`, `denied`, or `rejected`.

The fixture issue vocabulary is:

- `no_roles_requested`;
- `unknown_role`;
- `claim_ceiling_exceeded`;
- `dependency_cycle`;
- `missing_dependency`;
- `network_or_nondeterminism`;
- `tool_not_registered`;
- `input_contract_mismatch`;
- `registry_cardinality_mismatch`;
- `handler_not_registered`;
- `network_egress_disabled`; and
- `direct_identifier`.

## Projection guarantees

JSON keys are sorted for content addressing. CSV columns have stable order.
Markdown uses the same row IDs and state values. Fixture loader round trips
reconstruct enums and tuples, then verifies the fixture address before
returning a typed object.
