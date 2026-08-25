# Local service surface

The local service exposes the certified product surfaces through a dependency-free
HTTP API. The service constructs one deterministic snapshot lazily and reuses it
for the lifetime of the server. Every projection carries the address of the
report or runtime from which it was derived.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | Cheap process health response |
| GET | `/v1/schema` | Existing case contract summary |
| GET | `/v1/search` | Replay-gated cross-run search over public dossier resources |
| GET | `/v1/search/closure` | Complete content-addressed cross-run search closure |
| GET | `/v1/batches` | Paginated catalog of persisted batch evaluations |
| GET | `/v1/batches/{batch_id}` | Reopen and verify one batch result |
| GET | `/v1/batches/{batch_id}/release` | Build a gated portable batch handoff bundle |
| GET | `/v1/status` | Compact capability, program, operational, and boundary status |
| GET | `/v1/capabilities` | Certified capability query |
| GET | `/v1/architecture/program` | Architecture receipt query |
| GET | `/v1/architecture/operational` | Full stage, artifact, and check handoff trace |
| GET | `/v1/architecture/diff` | Baseline comparison with a named control |
| GET | `/v1/runs` | Paginated catalog of persisted case runs |
| GET | `/v1/runs/{run_id}` | Bounded summary and integrity status for one run |
| GET | `/v1/runs/{run_id}/dossier` | Reopen the immutable stored dossier |
| GET | `/v1/runs/{run_id}/events` | Reopen the hash-chained event record |
| GET | `/v1/runs/{run_id}/replay` | Return replay verification evidence |
| GET | `/v1/runs/{run_id}/inspection` | Return the complete run inspection closure |
| GET | `/v1/runs/{run_id}/workspace` | Reopen a replay-verified case as a bounded workspace projection |
| GET | `/v1/runs/{run_id}/workspace/closure` | Return the complete content-addressed run workspace closure |
| GET | `/v1/runs/{run_id}/workspace/history` | Rebuild every verified dossier snapshot as a workspace timeline |
| GET | `/v1/runs/{run_id}/workspace/compare` | Compare two historical workspace snapshots by public record identity |
| GET | `/v1/runs/{run_id}/workspace/release` | Build a gated portable workspace handoff bundle |
| GET | `/v1/runs/{run_id}/history` | List content-addressed dossier snapshots for one run |
| GET | `/v1/runs/{run_id}/compare/{target_run_id}` | Compare current or selected snapshots from two runs |
| GET | `/v1/runs/{run_id}/compare/{target_run_id}/release` | Build a gated portable comparison handoff bundle |
| GET | `/v1/runs/{run_id}/summary` | Aggregate evidence, review, and validation counters |
| GET | `/v1/runs/{run_id}/query-closure` | Complete content-addressed dossier query projection |
| GET | `/v1/runs/{run_id}/hypotheses` | Filter bounded hypothesis projections |
| GET | `/v1/runs/{run_id}/evidence` | Filter bounded evidence-claim projections |
| GET | `/v1/runs/{run_id}/experiments` | Filter bounded validation-route projections |
| GET | `/v1/runs/{run_id}/lineage` | Join hypothesis edges to referenced claims |
| GET | `/v1/runs/{run_id}/release` | Build a gated, content-addressed portable dossier release bundle |
| POST | `/v1/runs/{run_id}/review` | Attach a typed human review and create a new dossier snapshot |
| GET | `/v1/review-queue` | Return a bounded deterministic priority queue for review operations |
| GET | `/v1/review-queue/closure` | Return the complete review queue with state and priority counters |
| GET | `/v1/review-operations` | Return an as-of SLA, aging, and reviewer workload projection |
| GET | `/v1/review-operations/closure` | Return the complete SLA and workload closure |
| POST | `/v1/runs/{run_id}/assignment` | Append a durable reviewer assignment and create a new dossier snapshot |
| POST | `/v1/evaluate` | Existing case evaluation endpoint |
| POST | `/v1/evaluate-batch` | Evaluate a manifest list with independent item outcomes |

Capability queries accept `capability_id`, `domain_id`, `mvp_only`, `state`, and
`text`. Architecture queries accept `domain_id`, `accepted_only`, and `text`.
Boolean values accept `true`, `false`, `1`, `0`, `yes`, and `no`. Diff controls
are `none`, `missing-fixture`, and `missing-runtime`. Invalid query values return
HTTP 400 with the `invalid_query` error code.

Run catalog queries accept `case_id`, `status`, `text`, `offset`, and `limit`.
The limit is bounded to 100 rows. Run identifiers are validated before they are
used as filesystem paths. Missing runs return HTTP 404; an existing run can be
accepted only when its input object, event chain, dossier address, and stored
object links all verify.

Cross-run search accepts `q` or its `text` alias, `resource` (`all`, `runs`,
`hypotheses`, `evidence`, `experiments`, or `reviews`), `case_id`, `status`,
`reviewer`, `review_state`, `state`, `tier`, `channel`, `min_support`,
`max_uncertainty`, `assay`, `accepted_only`, `offset`, and `limit`. Search
reopens and verifies every persisted run before emitting scientific records.
Corrupt or incomplete runs contribute only a bounded blocked-run record for
`all` or `runs`; they never contribute hypotheses, claims, experiments, or
reviews. Results use deterministic token matching, ranking, pagination, and
content addresses. `/v1/search/closure` disables pagination and returns the
complete replay-gated projection for offline handoff.

Batch catalog queries accept `text`, `offset`, and `limit`. Batch identifiers are
derived from the canonical batch input address, so repeating an identical batch
request reopens the existing result instead of creating a competing record.
Batch evaluation accepts an object with `manifests`, optional `batch_id` or
`label`, `live_reference`, `window_bp`, and `max_items`, or a bare JSON manifest
list in offline CLI use; a single case manifest is also accepted as a one-item
batch. Every item is evaluated independently. A failed item
retains its index, case identifier, input address, stable error category, and
error message beside successful run and dossier addresses. The batch is accepted
only when every requested item succeeds; partial results remain inspectable but
are never promoted as an accepted batch.

Dossier-plane queries accept `offset`, `limit`, and resource-specific filters.
Evidence supports `state`, `tier`, `channel`, `source_id`, `edge_id`, and
`evidence_id`; hypotheses support `hypothesis_id`, `status`, `min_support`, and
`max_uncertainty`; experiments support `option_id` and `assay`. The lineage
projection accepts `hypothesis_id` and fails closed when an edge references a
missing claim.

Review queue queries accept `scope` (`open`, `all`, `assigned`, `unassigned`,
`completed`, or `blocked`), `case_id`, `status`, `reviewer`, `queue_id`,
`priority_band`, `text`, `offset`, and `limit`. Queue priority is deterministic:
integrity blocks, returned or pending reviews, missing reviews, runtime warnings,
uncertainty, abstained evidence, and missing assignments contribute explicit
priority reasons. The queue remains a projection over replay-verified runs and
fails closed when any persisted run is corrupted.

Review operations accepts the same scope plus `reviewer`, `queue_id`,
`due_state`, `priority_band`, `text`, `offset`, `limit`, `as_of`, and
`due_soon_hours`. Due states are `completed`, `overdue`, `due_soon`,
`scheduled`, `undated`, and `invalid`. Every report includes the normalized UTC
clock, age in seconds, remaining seconds when a due time exists, an explicit
operational action, deterministic reviewer/queue workloads, and content
addresses. Supplying `as_of` is recommended for reproducible exports; omitting
it uses the current UTC instant for interactive use.

Run workspaces reopen the persisted manifest and current dossier only after the
run's input object, event chain, and dossier address pass replay verification.
The projection accepts `q` or `text`, `context_key`, repeated or
comma-separated `record_type`, `state`, `source_id`, and `tag` filters, plus
`chromosome`, `start`, `end`, `variant_id`, `offset`, and `limit`. It returns
the exact-context records, sections, facets, state, and variant relationships
used by the typed workspace builders. Direct subject/sample keys and agent,
model, author, attribution, and language metadata are removed before the
public content address is calculated. A failed run remains visible as a
blocked projection with integrity evidence; its workspace records are
withheld. The `/workspace/closure` route pages through every matching record
and marks the page complete for offline consumers.

Workspace history rebuilds every accepted dossier snapshot against the original
manifest, retains the snapshot and review-state metadata, and compares adjacent
public records by stable `record_id`. Each transition reports additions,
removals, field-level changes, unchanged records, truncation state, and review
metadata changes. The history route accepts `change_limit`; the compare route
requires `source_snapshot` and `target_snapshot` and accepts the same limit.
History fails closed when any indexed dossier snapshot or its run replay is
invalid, while retaining blocked snapshot warnings for inspection.

Workspace releases package the replay-gated history into eight portable public
artifacts: current and historical JSON projections, a summary, snapshot/record/
transition CSVs, gate evidence, and a Markdown report. `release.json` addresses
the exact artifact bytes and the verifier rejects missing, extra, unsafe,
duplicate, tampered, non-UTF-8, and public-boundary-violating files. A blocked
history can be exported for inspection, but its release remains unaccepted.

## CLI and offline closure

Run the compact status projection:

```text
glio-noncode service-surface --output service-status.json
```

Run the detailed archival projection:

```text
glio-noncode service-surface --closure --output service-surface-closure.json
```

Evaluate and reopen a durable batch:

```text
glio-noncode evaluate-batch batch.json --data-root .glio --output batch-result.json
glio-noncode batch-inspect batch-<content-digest> --data-root .glio --output batch-inspection.json
glio-noncode batch-catalog --data-root .glio --output batch-catalog.json
glio-noncode batch-release batch-<content-digest> --data-root .glio --output batch-release
glio-noncode batch-release-verify batch-release --output batch-release-verification.json
```

Batch releases contain `release.json`, a private-key-filtered batch input
projection plus result JSON, summary and gate JSON, item/failure/run CSV
projections, and a Markdown report. The original input remains bound by its
content address in the gate evidence. Every artifact carries its byte count,
line count, and byte content address.
`batch-release-verify` reopens the directory, rejects unsafe or duplicate paths,
detects byte and manifest-address tampering, and preserves blocked partial
bundles as inspectable evidence.

Search the persisted corpus across runs:

```text
glio-noncode run-search --data-root .glio --query enhancer --resource hypotheses --output search.json
glio-noncode run-search --data-root .glio --resource evidence --state supported --closure --output evidence-search-closure.json
```

The search command is the offline equivalent of the two search endpoints. It
keeps the public dossier boundary, records scanned and blocked run counts, and
returns an explicit `accepted` flag so filtered results cannot conceal a
corrupted persisted run.

Inspect persisted case work:

```text
glio-noncode run-catalog --data-root .glio
glio-noncode run-catalog --data-root .glio --closure --output run-catalog-closure.json
glio-noncode run-inspect run-<run-id> --data-root .glio --output run-inspection.json
glio-noncode run-workspace run-<run-id> --data-root .glio --record-type evidence --state supported --output run-workspace.json
glio-noncode run-workspace run-<run-id> --data-root .glio --variant-id variant-1 --closure --output run-workspace-closure.json
glio-noncode run-workspace-history run-<run-id> --data-root .glio --output run-workspace-history.json
glio-noncode run-workspace-compare run-<run-id> 0 1 --data-root .glio --output workspace-transition.json
glio-noncode run-workspace-release run-<run-id> --data-root .glio --output workspace-release
glio-noncode run-workspace-release-verify workspace-release --output workspace-release-verification.json
glio-noncode run-review run-<run-id> review.json --data-root .glio --output reviewed-dossier.json
glio-noncode run-query run-<run-id> summary --data-root .glio --output run-summary.json
glio-noncode run-query run-<run-id> lineage --data-root .glio --output run-lineage.json
glio-noncode run-query run-<run-id> closure --data-root .glio --output dossier-query-closure.json
glio-noncode run-history run-<run-id> --data-root .glio --output run-history.json
glio-noncode run-compare run-<source-id> run-<target-id> --data-root .glio --output run-comparison.json
glio-noncode run-compare run-<run-id> run-<run-id> --source-snapshot 0 --target-snapshot 1 --data-root .glio --output review-transition.json
glio-noncode run-compare-release run-<run-id> run-<run-id> --source-snapshot 0 --target-snapshot 1 --data-root .glio --output comparison-release
glio-noncode run-compare-release-verify comparison-release --output comparison-verification.json
glio-noncode run-release run-<run-id> --data-root .glio --output dossier-release
glio-noncode run-release-verify dossier-release --output release-verification.json
glio-noncode review-queue --data-root .glio --scope open --output review-queue.json
glio-noncode review-queue --data-root .glio --closure --output review-queue-closure.json
glio-noncode review-operations --data-root .glio --as-of 2026-09-01T12:00:00Z --output review-operations.json
glio-noncode review-operations --data-root .glio --closure --as-of 2026-09-01T12:00:00Z --output review-operations-closure.json
glio-noncode review-assign run-<run-id> assignment.json --data-root .glio --output assignment-result.json
```

Review input uses the public `ReviewDecision` fields: `review_id`, `case_id`,
`reviewer`, `state`, `reviewed_hypothesis_ids`, `rationale`, and
`checked_claim_ids`. Accepted reviews produce a new `released_research` dossier
snapshot while retaining the research-use-only policy boundary and prior
content-addressed objects.

Review continuation is append-only: when a persisted run is reopened, the
existing verified event record is hydrated before the new `review_recorded`
event is appended. If the chain is invalid, the review is rejected rather than
silently replacing the history with a new chain.

Every persisted run now retains an ordered `dossier_history` of immutable
snapshot addresses. `run-history` verifies each snapshot independently and
reports the current index, review state, counts, and any missing or mismatched
object. `run-compare` and the compare route can select historical indexes and
return semantic additions, removals, and field-level changes for metadata,
hypotheses, evidence, and experiments. Comparisons require replay integrity,
matching case identity, a complete bounded projection, and the public boundary;
failed checks remain visible in the returned evidence.

Comparison handoffs are portable ten-artifact bundles containing canonical JSON,
summary/check JSON, Markdown, source and target history closures, and separate
metadata, hypothesis, evidence, and experiment CSV deltas. The release route and
`run-compare-release` command retain blocked comparisons as inspectable bundles;
`run-compare-release-verify` reopens the directory and verifies every byte,
manifest address, size, line count, and safe artifact path.

Review assignments are append-only `review_assigned` events. An assignment
records the public assignment identifier, reviewer, queue, optional due time and
note, and its content address. The runtime re-addresses the dossier with the
new event head, so assignment history is retained in `run-history`, semantic
comparisons, and subsequent release gates. Reassignments use a new assignment
identifier and never overwrite prior events.

The release route and CLI export ten portable artifacts: canonical dossier JSON,
Markdown, summary and query-closure JSON, replay events, release-gate evidence,
review JSON, and evidence/hypothesis/experiment CSV projections. Release is
accepted only when replay integrity, accepted human review, structural policy,
byte addressing, and the public boundary all pass. Filesystem bundles can be
reopened with `run-release-verify`; tampering, unsafe paths, missing files, and
manifest-address changes are reported as verification failures.

The closure includes the complete 256-row capability certification report, the
sixteen-domain architecture runtime, the twelve-stage operational trace, and
the common query projections. The closure is rejected if its public projection
contains a private-key field.
