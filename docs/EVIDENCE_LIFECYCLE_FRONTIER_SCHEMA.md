# Evidence Lifecycle Frontier Schema

## Schema contract

The schema describes the Domain 14 C01–C04 public aggregate interface.

The schema has four operation entries.

The schema version is `2026.08.d14.v1`.

The schema ID is `evidence-lifecycle-frontier-schema`.

The schema is content addressed.

Every field has a name.

Every field has a value type.

Every field has a required flag.

Every field has a nullable flag.

Every field has a detail string.

Every field has a content address.

## Shared record fields

`record_id` is a required string.

`record_id` is unique within a fixture.

`operation` is an enum value.

`role` is an enum value.

`context_key` is a required string.

`source_ids` is a required string array.

`payload` is a required object.

`expected_state` is a required string.

`expected_issue_codes` is a string array.

`notes` is a required string.

`content_address` is a required string.

The record context must equal fixture context.

The record source IDs must resolve to receipts.

The record payload is operation-specific.

The expected state is a fixture assertion.

The expected issue codes are a fixture assertion.

## Source receipt fields

`source_id` is a required string.

`title` is a required string.

`uri` is a required HTTPS string.

`access_note` is a required string.

`content_address` is a required string.

The URI must begin with `https://`.

The source ID must be unique.

The address covers all receipt fields.

## C01 input fields

`text` is required for citation resolution.

`source_id` is required for citation resolution.

`source_version` is required for citation resolution.

`input_format` is optional.

The format may be `tsv`.

The format may be `csv`.

The format may be `json`.

The resolver may infer JSON from the first character.

The resolver may infer TSV for other text.

The resolver rejects unsupported formats.

## C01 citation fields

`citation_id` is required after fallback.

`source_id` is required after fallback.

`source_uri` is required.

`title` is required.

`version` is required after fallback.

`raw_hash` is required after hashing.

`citation_text` is required.

`retrieved_at` is required after fallback.

`context_key` is nullable.

`source_checksum` is nullable.

`raw_record` is retained.

`attributes` retain unknown fields.

## C01 output fields

`source_id` identifies the input manifest.

`source_version` identifies the input version.

`input_hash` identifies raw input.

`citations` contains accepted rows.

`issues` contains quarantined rows.

`state` is derived from citations and issues.

`quarantined_count` counts quarantined rows.

`content_address` identifies the batch.

The batch is partial when citations and issues coexist.

The batch is abstained when no citations are accepted.

The batch is supported when citations exist without issues.

## C02 claim fields

`claim_id` is a required string.

`edge_id` is a required string.

`context_key` is a required string.

`state` is a lifecycle state.

`support` is nullable.

`confidence` is a number from zero to one.

`claim_type` is a required string.

`summary` is a required string.

`source_ids` is a required string array.

`source_versions` maps source IDs to versions.

`raw_hash` is a required string.

`parent_claim_ids` is a string array.

`supersedes` is nullable.

`attributes` is an object.

`created_at` is a required deterministic string in fixtures.

## C02 graph fields

`graph_id` is a required string.

`graph_version` is a positive integer.

`context_key` is a required string.

`claims` is a claim array.

`citations` is a citation array.

The graph rejects duplicate claim IDs.

The graph rejects duplicate citation IDs.

The graph rejects mismatched claim context.

The graph records orphan claims.

The graph records context mismatch claims.

The graph records superseded claims.

The graph records active claims.

The graph records contradictory edges.

The graph records warnings.

The graph records lifecycle state.

The graph records content address.

## C02 graph states

`supported` indicates resolved active claims without blockers.

`partial` indicates retained orphan conditions.

`out_of_domain` indicates context mismatch.

`contradictory` indicates conflicting active claims.

`abstained` indicates no usable claim.

`superseded` indicates no active claim remains.

`invalid` indicates input construction failure.

The state is descriptive.

The state is not a clinical conclusion.

## C03 edge fields

`edge_id` selects one graph edge.

`expected_context_key` is optional.

`claim_ids` lists all matching claims.

`active_claim_ids` lists active claims.

`orphan_claim_ids` lists unresolved claims.

`missing_source_ids` lists unresolved citations.

`source_ids` lists attached sources.

`contradiction` is a boolean.

`uncertainty` is descriptive.

`warnings` is a string array.

`state` is an edge lifecycle state.

`content_address` identifies the edge report.

## C04 disagreement fields

`edge_ids` selects edges for tracking.

`records` contains one record per selected edge.

`state` is a disagreement state.

`claim_ids` lists active claims.

`positive_claim_ids` lists supported claims.

`negative_claim_ids` lists measured-negative or absent claims.

`value_groups` maps declared values to claim IDs.

`source_ids` lists sources.

`unresolved` marks a review condition.

`rationale` describes the state.

`contradictory_edge_ids` lists conflicting edges.

`unresolved_edge_ids` lists all unresolved edges.

## State vocabulary

`supported` means the positive lifecycle state is resolved.

`partial` means some evidence or lineage remains incomplete.

`abstained` means the operation cannot support a state.

`out_of_domain` means context does not match.

`contradictory` means competing states remain.

`superseded` means an older claim is not active.

`absent` means all active claims are negative or absent.

`measured_negative` is a claim state.

`clear` is a disagreement state.

`incomplete` is a disagreement state.

`invalid` is an execution wrapper state.

## Contract fields

Each contract has one operation.

Each contract has required input fields.

Each contract has required output fields.

Each contract has issue codes.

Each contract has state values.

Each contract has a review boundary.

Each contract has a content address.

The registry has a version.

The registry has a registry ID.

The registry exposes issue-code union.

## Schema validation rules

Every operation must have one schema.

Every operation must have one contract.

Every record operation must be declared.

Every issue code must be declared.

Every expected state must be supported.

Every source URI must be HTTPS.

Every record context must match fixture context.

Every record address must begin with `sha256:`.

Every source address must begin with `sha256:`.

Every execution address must begin with `sha256:`.

## Queue fields

`queue_id` identifies a review queue.

`fixture_id` binds queue to fixture.

`items` contains one item per execution.

`checks` contains structural queue checks.

`accepted` summarizes queue checks.

`ready_count` counts ready items.

`blocked_count` counts held items.

`next_item_id` identifies the next item.

`issue_codes` contains sorted issue union.

Queue item `item_id` is stable.

Queue item `record_id` binds to fixture.

Queue item `operation` preserves operation.

Queue item `role` preserves role.

Queue item `disposition` preserves readiness.

Queue item `priority` supports deterministic ordering.

Queue item `state` preserves observed state.

Queue item `issue_codes` preserves blockers.

Queue item `rationale` explains the disposition.

Queue item `next_action` explains the next step.

## Runtime fields

`run_id` identifies a runtime rehearsal.

`stages` contains ten ordered stages.

`bundle` contains the release bundle.

`accepted` summarizes the runtime.

Each stage has a sequence.

Each stage has a state.

Each stage has a duration.

Each stage has an output address.

Each stage has a detail string.

Each stage has a content address.

## Release fields

`release_id` identifies a manifest.

`bundle_id` binds it to a bundle.

`state` is ready or blocked.

`checks` contains four release checks.

`replay_id` binds it to replay.

`allowed_uses` states permitted research uses.

`excluded_uses` states prohibited use classes.

`accepted` summarizes release checks.

`content_address` identifies the manifest.

## Metrics fields

`metric_id` is stable.

`value` is a descriptive decimal.

`numerator` is an integer count.

`denominator` is an integer count.

`detail` describes the metric.

`content_address` identifies the metric.

The report binds to evaluation address.

The report contains thirteen metrics.

## Artifact fields

`artifact_id` is stable.

`kind` identifies fixture, evaluation, metric, quality, runtime, release, or bundle.

`content_address` binds artifact content.

`parent_ids` binds artifact lineage.

`accepted` exposes artifact state.

The inventory has seven artifacts.

The release artifact is the inventory root.

## Observability fields

`event_id` is stable within a run.

`event_type` identifies stage or execution.

`subject_id` identifies the source subject.

`state` copies source state.

`sequence` is explicit.

`detail` preserves issue or address context.

`content_address` identifies the event.

The report has ten stage events.

The report has sixteen execution events.

## Serialization rules

Enum values serialize as strings.

Tuples serialize as arrays.

Mappings serialize as objects.

Addresses serialize as strings.

JSON export uses two-space indentation.

JSON export uses sorted keys.

JSON export ends with a newline.

Canonical export has no formatting whitespace.

CSV export has deterministic field order.

CSV export preserves empty issue fields.

## Fixture loading rules

The loader requires a source list.

The loader requires a record list.

The loader requires fixture metadata.

The loader reconstructs typed source receipts.

The loader reconstructs typed records.

The loader reconstructs typed operations.

The loader reconstructs typed roles.

The loader reconstructs tuple source IDs.

The loader reconstructs tuple issue codes.

The loader preserves addresses.

The loader rejects empty sources.

The loader rejects empty records.

## Context rules

The fixture context is exact.

Record context must equal fixture context.

Claim context must equal graph context.

Expected edge context may differ for a control.

Citation context may be nullable.

Non-null citation context must match graph context.

Disagreement claim context must remain exact.

Context mismatch becomes an explicit state.

Context mismatch becomes an explicit issue when mapped.

Context mismatch is not repaired by coercion.

## Address rules

Source addresses use SHA-256 content addresses.

Record addresses use SHA-256 content addresses.

Execution addresses use SHA-256 content addresses.

Check addresses use SHA-256 content addresses.

Metric addresses use SHA-256 content addresses.

Stage addresses use SHA-256 content addresses.

Release addresses use SHA-256 content addresses.

Address presence is required.

Address equality supports replay.

Address equality does not prove external truth.

## Schema change procedure

Add a field specification.

Add a contract field.

Add a fixture field.

Add evaluator extraction.

Add a serialization assertion.

Add a replay assertion.

Add a CLI assertion.

Add a CI command if the field is operational.

Add a migration note.

Run focused tests.

Run full tests.

Run staged scan.

## Schema non-goals

The schema does not encode a patient record.

The schema does not encode treatment choice.

The schema does not encode a clinical cutoff.

The schema does not encode experimental success.

The schema does not encode causal certainty.

The schema does not encode a source-quality score.

The schema does not erase uncertainty.

The schema does not erase disagreement.

## Schema completion

The schema is complete when four operations are present.

The schema is complete when all required fields are declared.

The schema is complete when output fields are declared.

The schema is complete when contracts and schema agree.

The schema is complete when fixture records validate.

The schema is complete when JSON round-trip passes.

The schema is complete when CLI output passes.

The schema is complete when replay remains stable.
