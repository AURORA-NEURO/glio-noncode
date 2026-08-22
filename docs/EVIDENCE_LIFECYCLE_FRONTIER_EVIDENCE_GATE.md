# Evidence Lifecycle Frontier Evidence Gate

## Gate intent

This document defines the public aggregate gate for Domain 14 C01–C04.

The gate covers citation resolution.

The gate covers versioned graph construction.

The gate covers claim-edge validation.

The gate covers contradiction and disagreement tracking.

The gate keeps these operations separate.

The gate does not merge citation state with graph state.

The gate does not merge graph state with edge state.

The gate does not merge edge state with disagreement state.

The gate preserves the output of every operation.

The gate preserves the input record for every execution.

The gate preserves positive and control roles.

The gate preserves source receipts.

The gate preserves exact context.

The gate preserves issue codes.

The gate preserves content addresses.

The gate preserves replay behavior.

The gate preserves research-use limits.

## Evidence boundary

The fixture boundary is `public_aggregate_non_patient`.

The fixture context is `GRCh38|glioma|adult|stem_like|core|untreated`.

The fixture contains five HTTPS source receipts.

The fixture contains sixteen records.

The fixture contains four positive records.

The fixture contains twelve control records.

Each operation has one positive record.

Each operation has three control records.

The records do not contain patient identifiers.

The records do not contain specimen identifiers.

The records do not contain clinical decisions.

The records do not contain treatment instructions.

The records do not contain prognosis statements.

The records do not contain individual risk estimates.

The records do not contain a clinical validation claim.

The fixture is a public aggregate test surface.

The fixture is not a clinical evidence set.

The fixture is not an experiment result.

The fixture is not a regulatory submission.

## Source receipts

`src-citation` identifies the citation manifest boundary.

`src-graph` identifies the graph snapshot boundary.

`src-edge` identifies edge validation inputs.

`src-disagreement` identifies disagreement inputs.

`src-control` identifies negative control inputs.

Each receipt has a source ID.

Each receipt has a title.

Each receipt has an HTTPS URI.

Each receipt has an access note.

Each receipt has a content address.

The source ID is stable inside the fixture.

The URI is not treated as a content hash.

The receipt address covers the declared receipt fields.

A source receipt does not prove source quality.

A source receipt does not prove source agreement.

A source receipt only binds a public input boundary.

## Record identity

The record ID is unique within the fixture.

The record ID is retained through execution.

The record ID is retained through metrics.

The record ID is retained through reconciliation.

The record ID is retained through review views.

The record ID is retained through CSV export.

The record ID is retained through lineage.

The record ID is retained through the review queue.

The record address covers the operation.

The record address covers the role.

The record address covers the context.

The record address covers source IDs.

The record address covers payload.

The record address covers expected state.

The record address covers expected issue codes.

The record address covers the review note.

Changing a record payload changes its address.

Changing an expected issue changes its address.

Changing the role changes its address.

## C01 citation resolution

C01 uses `CitationResolver`.

C01 accepts TSV input.

C01 accepts CSV input.

C01 accepts JSON input.

C01 retains source version.

C01 retains raw input hash.

C01 retains raw row hash.

C01 retains retrieval time when supplied.

C01 retains unknown fields as attributes.

C01 retains malformed rows as issues.

C01 does not silently drop malformed rows.

The C01 positive has one valid row.

The C01 positive has one incomplete row.

The C01 positive is partial.

The C01 positive retains `missing_required_field`.

The first C01 control has malformed JSON.

The first C01 control is abstained.

The first C01 control retains `invalid_json`.

The second C01 control has duplicate IDs.

The second C01 control is partial.

The second C01 control retains `duplicate_citation_id`.

The third C01 control has no header.

The third C01 control is abstained.

The third C01 control retains `missing_header`.

The C01 evaluator compares state.

The C01 evaluator compares issue codes.

The C01 evaluator compares role.

The C01 evaluator compares operation.

The C01 evaluator checks content address.

The C01 evaluator checks output retention.

## C02 graph construction

C02 uses `VersionedEvidenceGraphConstructor`.

C02 accepts typed claims.

C02 accepts typed citations.

C02 checks unique claim IDs.

C02 checks unique citation IDs.

C02 checks graph context.

C02 checks parent claim IDs.

C02 checks supersession targets.

C02 checks source references.

C02 checks citation context.

C02 derives active claim IDs.

C02 derives superseded claim IDs.

C02 derives orphan claim IDs.

C02 derives contradictory edge IDs.

C02 retains graph warnings.

The C02 positive has an original claim.

The C02 positive has a replacement claim.

The replacement supersedes the original.

The original remains in graph history.

The replacement remains active.

The positive graph is supported.

The first C02 control has a missing parent.

The first C02 control has a missing source.

The first C02 control is partial.

The first C02 control retains `orphan_claim`.

The second C02 control changes claim context.

The second C02 control is invalid.

The second C02 control retains `graph_context_mismatch`.

The third C02 control repeats a claim ID.

The third C02 control is invalid.

The third C02 control retains `duplicate_claim_id`.

The C02 gate never deletes superseded history.

The C02 gate never repairs missing sources silently.

## C03 claim-edge validation

C03 uses `ClaimEvidenceEdgeValidator`.

C03 selects one edge at a time.

C03 retains all claim IDs for that edge.

C03 retains active claim IDs.

C03 retains missing source IDs.

C03 retains source IDs.

C03 reports contradiction state.

C03 reports uncertainty as a descriptive value.

C03 reports warnings.

C03 checks an optional expected context.

The C03 positive has one supported claim.

The C03 positive has a resolved citation.

The C03 positive is supported.

The C03 positive has no issue code.

The first C03 control has a missing citation.

The first C03 control is partial.

The first C03 control retains `missing_source`.

The second C03 control requests another context.

The second C03 control is out of domain.

The second C03 control retains `edge_context_mismatch`.

The third C03 control requests an absent edge.

The third C03 control is abstained.

The third C03 control retains `edge_absent`.

C03 does not average claim support.

C03 does not convert uncertainty into probability.

C03 does not turn an absent edge into a negative result.

## C04 disagreement tracking

C04 uses `ContradictionDisagreementTracker`.

C04 selects explicit edge IDs.

C04 keeps positive claim IDs.

C04 keeps negative claim IDs.

C04 keeps declared value groups.

C04 keeps source IDs.

C04 marks unresolved records.

C04 reports contradictory edge IDs.

C04 reports incomplete edge IDs.

C04 reports out-of-domain edge IDs.

The C04 positive contains a supported claim.

The C04 positive contains a measured-negative claim.

The C04 positive contains two declared values.

The C04 positive is contradictory.

The C04 positive retains `contradiction_unresolved`.

The first C04 control has one supported observation.

The first C04 control is clear.

The first C04 control has no issue code.

The second C04 control has no claims.

The second C04 control is incomplete.

The second C04 control retains `incomplete_disagreement`.

The third C04 control has an out-of-domain claim.

The third C04 control is out of domain.

The third C04 control retains `disagreement_out_of_domain`.

C04 never averages values.

C04 never hides a negative observation.

C04 never treats a clear row as causal proof.

## Execution contract

Every record has one execution.

Every execution has one operation.

Every execution has one role.

Every execution has one state.

Every execution has an accepted flag.

Every execution has issue codes.

Every execution has an output object.

Every execution has a content address.

Execution order follows fixture order.

Execution order is not used for state inference.

Execution acceptance is role-aware.

Positive acceptance requires expected state.

Positive acceptance requires expected issue codes.

Control execution remains non-accepted.

An expected control is still a retained blocker.

An expected control is not a successful release path.

An unexpected positive result fails evaluation.

An unexpected control result fails evaluation.

An unknown issue code fails evaluation.

An empty output fails evaluation.

An absent content address fails evaluation.

## Evaluation checks

Each record receives a state check.

Each record receives an issue check.

Each record receives a role check.

Each record receives an operation check.

Each record receives an address check.

Each record receives a context check.

Each record receives an output check.

Sixteen records produce 112 record checks.

The evaluation adds a record-count check.

The evaluation adds a source-count check.

The evaluation adds an operation-count check.

The evaluation adds a positive-count check.

The evaluation adds a control-count check.

The evaluation adds an address check.

The evaluation adds a boundary check.

The evaluation adds a context check.

The total is 120 checks.

The accepted result requires all 120 checks.

The passed count is exposed in JSON.

The failed check IDs are exposed in JSON.

## Contract vocabulary

`invalid_lifecycle_input` describes malformed lifecycle input.

`invalid_graph_input` describes graph construction input failure.

`invalid_json` describes JSON decoding failure.

`missing_header` describes a table without a header.

`missing_required_field` describes an incomplete citation.

`duplicate_citation_id` describes a repeated citation ID.

`graph_context_mismatch` describes a claim crossing graph context.

`duplicate_claim_id` describes a repeated claim ID.

`orphan_claim` describes missing lineage or citation.

`citation_context_mismatch` describes a citation context mismatch.

`missing_source` describes an unresolved edge source.

`edge_context_mismatch` describes a requested edge context mismatch.

`edge_absent` describes an unknown edge.

`contradiction_unresolved` describes competing observations.

`incomplete_disagreement` describes an empty or incomplete edge.

`disagreement_out_of_domain` describes an out-of-domain claim.

Issue vocabulary is closed by the contract registry.

Issue vocabulary is sorted in summaries.

Issue vocabulary is not a severity score.

Issue vocabulary does not imply clinical risk.

## Lineage gate

Every source binding creates a source-to-execution edge.

Every record creates a fixture-to-execution edge.

The fixture has twenty source edges.

The fixture has sixteen fixture edges.

The graph has thirty-six edges.

The graph has sixteen terminal addresses.

The graph is marked acyclic.

The source edge relation is explicit.

The fixture edge relation is explicit.

The terminal address is the execution address.

Lineage does not infer causality.

Lineage does not rank sources.

Lineage does not replace a citation.

Lineage does not erase a control.

## Reconciliation gate

Reconciliation iterates fixture records.

Reconciliation looks up execution by record ID.

Reconciliation compares expected state.

Reconciliation compares sorted expected issues.

Reconciliation stores observed state.

Reconciliation stores observed issues.

Reconciliation stores a match flag.

Reconciliation stores a content address.

Reconciliation exposes mismatched record IDs.

The default fixture reconciles completely.

An incomplete reconciliation blocks release.

A policy decision count is retained.

Reconciliation does not change execution.

Reconciliation does not change the fixture.

## Policy gate

Policy decisions are operation-specific.

Policy decisions are derived from positive executions.

Policy decisions are not derived from controls.

Positive acceptance enables bounded review.

Graph construction enables replay review.

All other positive operations enable lifecycle review.

A missing positive blocks release.

An unexpected positive issue blocks release.

Controls remain visible in the evidence view.

Allowed uses are explicit.

Excluded uses are explicit.

The policy does not grant patient use.

The policy does not grant diagnosis use.

The policy does not grant prognosis use.

The policy does not grant treatment selection use.

## Quality gate

The quality gate has twelve checks.

The evaluation check covers all record checks.

The positive-count check covers operation balance.

The control-count check covers negative controls.

The contract check covers four contracts.

The schema check covers four schemas.

The lineage check covers acyclic terminals.

The reconciliation check covers expected state.

The address check covers executions.

The issue check covers contract vocabulary.

The boundary check covers public scope.

The source check covers HTTPS receipts.

The context check covers exact record context.

The gate passes only when all checks pass.

The gate does not mutate the bundle.

The gate does not promote a control.

## Runtime gate

Runtime stage one audits fixture data.

Runtime stage two loads contracts.

Runtime stage three loads schema.

Runtime stage four evaluates records.

Runtime stage five measures metrics.

Runtime stage six applies policy.

Runtime stage seven builds lineage.

Runtime stage eight reconciles state.

Runtime stage nine runs the quality gate.

Runtime stage ten assembles the bundle.

Every stage has a sequence.

Every stage has a duration.

Every stage has an output address.

Every stage has a detail string.

Every stage has a content address.

The runtime report exposes ten stage IDs.

Runtime acceptance requires audit acceptance.

Runtime acceptance requires gate acceptance.

Runtime acceptance requires reconciliation.

Runtime acceptance requires bundle publication.

## Release gate

The release manifest names the release.

The release manifest names the bundle.

The release manifest names the replay.

The release manifest includes four release checks.

The bundle check covers policy decisions.

The quality check covers gate acceptance.

The replay check covers replay acceptance.

The boundary check covers research scope.

The ready state requires all four checks.

The blocked state is explicit when a check fails.

Allowed uses are copied to the release.

Excluded uses are copied to the release.

The release is not an experimental result.

The release is not a clinical record.

## Review queue gate

The review queue has one item per execution.

The queue has sixteen items.

The queue has four ready items.

The queue has twelve held items.

Ready items are positive accepted executions.

Held items are controls or failed executions.

Citation work has citation priority.

Graph work has graph priority.

Edge work has edge priority.

Disagreement work has disagreement priority.

Controls have control priority.

The next item prefers held work.

The next item uses priority.

The next item uses item ID as a tie-break.

Queue acceptance checks coverage.

Queue acceptance checks positive readiness.

Queue acceptance checks control retention.

Queue acceptance checks unique IDs.

Queue acceptance checks operation coverage.

Queue acceptance checks fixture binding.

The queue does not remove controls.

The queue does not change evaluation state.

The queue does not assert evidence truth.

## Replay gate

Replay evaluates the same fixture.

Replay stores evaluation address.

Replay stores execution addresses.

Replay stores accepted state.

Replay IDs may differ.

Replay content addresses ignore replay ID differences.

Replay comparison reports drift fields.

Replay comparison reports left address.

Replay comparison reports right address.

The default fixture has no replay drift.

The citation records provide fixed retrieval times.

The graph records provide fixed creation times.

The replay does not use wall-clock state.

The replay does not use random state.

## Metric gate

The metric report has thirteen metrics.

Positive acceptance rate is one.

Control rejection rate is one.

Execution acceptance rate is role-aware.

Address coverage counts execution addresses.

Issue row rate counts visible issue rows.

Citation positive rate covers C01.

Graph positive rate covers C02.

Edge positive rate covers C03.

Disagreement positive rate covers C04.

Supported state rate describes observed states.

Review state rate describes review work.

Issue diversity describes vocabulary breadth.

Check pass rate describes evaluator checks.

Metrics are descriptive.

Metrics do not estimate clinical risk.

Metrics do not estimate effect size.

Metrics do not replace source review.

## Artifact gate

The artifact inventory contains seven nodes.

The fixture node is the root input.

The evaluation node depends on the fixture.

The metrics node depends on evaluation.

The quality node depends on evaluation.

The runtime node depends on quality.

The release node depends on runtime.

The bundle node depends on release.

Each node has a kind.

Each node has an address.

Each node has parent IDs.

Each node has an accepted flag.

The release node is the inventory root.

Artifact inventory does not infer missing evidence.

## Observability gate

Runtime stages produce ten events.

Executions produce sixteen events.

The report has twenty-six events.

The report has a stage counter.

The report has an execution counter.

The report has an accepted counter.

The report has positive and control counters.

The report has issue count.

The report has contradictory count.

The report has out-of-domain count.

Event IDs are stable for a run.

Event state is copied from the source object.

Event sequence is explicit.

Event detail retains issue or address context.

Events do not contain hidden personal data.

## Export gate

JSON export ends with a newline.

Canonical export uses sorted keys.

Manifest export names the boundary.

CSV export has one header row.

CSV export has sixteen data rows.

CSV export retains role.

CSV export retains operation.

CSV export retains state.

CSV export retains issue codes.

CSV export retains source IDs.

CSV export retains release state.

CSV export does not omit controls.

CSV export does not collapse issue codes.

## Threshold gate

There are four threshold profiles.

Each operation has one profile.

Each profile has 243 probes.

The report has 972 probes.

Each probe has a profile ID.

Each probe has a value.

Each probe has a state.

Each probe has an acceptance flag.

Accepted probes use the declared floor.

Review probes remain visible.

Threshold probes are calibration scaffolding.

Threshold probes are not probability estimates.

Threshold probes are not clinical cutoffs.

## Invariant gate

There are ten default invariants.

Context preservation is required.

Role separation is required.

Citation issues are required to remain visible.

Graph history is required to remain visible.

Edge validation must not average.

Disagreement must remain visible.

Source receipts must be addressed.

Executions must be addressed.

Replay must be stable.

Research boundary must be explicit.

An invariant report contains one result per invariant.

An invariant report is accepted only when all results pass.

## Verification checklist

Run the data audit.

Run the contract command.

Run the schema command.

Run the evaluator.

Run the replay command.

Run the metrics command.

Run the lineage command.

Run the policy command.

Run the quality gate.

Run the runtime rehearsal.

Run the observability command.

Run the artifact command.

Run the bundle command.

Run the release command.

Run the review queue command.

Run the CSV export.

Run the depth audit.

Run focused tests.

Run the full suite.

Run targeted lint.

Run the staged restricted-metadata scan.

## Completion rule

The fixture is complete when all source receipts resolve.

The fixture is complete when all records have addresses.

The evaluator is complete when 120 checks pass.

The replay is complete when drift is empty.

The lineage is complete when 36 edges are present.

The quality gate is complete when 12 checks pass.

The runtime is complete when 10 stages pass.

The observability report is complete when 26 events are present.

The artifact inventory is complete when seven nodes are present.

The depth audit is complete when 20 checks pass.

The queue is complete when four ready and twelve held rows are present.

The public boundary is complete when excluded uses remain visible.

The build is complete when all focused tests pass.

The build is complete when the full suite passes.

The build is complete when the staged scan has zero restricted hits.
