# Provenance-first review workspace

The review workspace is the dossier review read model for GLIO-NONCODE. It
complements the searchable run workspace by keeping the reasoning graph
visible: hypotheses, decomposed edges, evidence states, alternatives, source
provenance, human-review work items, and explicit cross-run deltas are returned
as separate collections.

It is a replay-gated research projection. A failed current run or baseline run
withholds details. The projection never publishes raw evidence payloads,
producer metadata, direct subject/sample/contact fields, or a single aggregate
decision score.

## Review collections

- `hypotheses` retains mechanism, context, status, support, uncertainty, edge
  IDs, evidence IDs, alternatives, provenance IDs, and missing/negative
  evidence declarations.
- `edges` retains source/target identifiers, typed edge kind, support,
  uncertainty, context fit, support level, claim IDs, source IDs, and evidence
  state counts.
- `evidence` retains source, channel, tier, state, score, confidence, context,
  summary, dependency IDs, and supersession links. Payloads are withheld.
- `alternatives` keeps each declared branch as a separate reviewable object;
  an alternative is not folded into the primary hypothesis.
- `provenance` groups evidence by source and retains edge/claim coverage,
  tiers, states, contexts, dependencies, supersession, and declared receipt
  IDs.
- `review_queue` gives a bounded priority band and reasons for human review.
  Priority is workflow triage, not biological ranking.
- `deltas` compare common or introduced/removed hypotheses, edges, and evidence
  between two verified runs. Numeric deltas are per dimension (support,
  uncertainty, context fit, score, or confidence); state and presence changes
  remain categorical.

## CLI

```powershell
glio-noncode review-workspace RUN_ID --data-root .glio --output review-workspace.json
glio-noncode review-workspace RUN_ID --data-root .glio --baseline-run-id BASELINE_RUN_ID --output review-deltas.json
glio-noncode review-workspace-schema --output review-workspace-schema.json
glio-noncode review-workspace-capabilities --output review-workspace-capabilities.json
glio-noncode review-workspace-export RUN_ID --data-root .glio --format markdown --output review-workspace.md
glio-noncode review-workspace-export RUN_ID --data-root .glio --format csv --collection edges --output edges.csv
glio-noncode review-workspace-release RUN_ID --data-root .glio --output review-release
glio-noncode review-workspace-release-verify review-release --output verification.json
glio-noncode review-workspace-index RUN_ID --data-root .glio --output review-index.json
glio-noncode review-workspace-query RUN_ID --collection evidence --state contradictory --limit 50 --data-root .glio --output review-query.json
glio-noncode review-workspace-query-schema --output review-query-schema.json
glio-noncode review-workspace-release-load review-release --output release-summary.json
glio-noncode review-workspace-release-index review-release --output release-index.json
glio-noncode review-workspace-plan RUN_ID --data-root .glio --output review-plan.json
glio-noncode review-workspace-plan-query RUN_ID --lane provenance --limit 50 --data-root .glio --output plan-query.json
glio-noncode review-workspace-plan-export RUN_ID --data-root .glio --format markdown --output review-plan.md
glio-noncode review-workspace-plan-schema --output review-plan-schema.json
glio-noncode review-workspace-plan-capabilities --output review-plan-capabilities.json
glio-noncode review-workspace-plan-execution RUN_ID --data-root .glio --output execution.json
glio-noncode review-workspace-plan-event RUN_ID --action-id ACTION_ID --kind start --event-id EVENT_ID --occurred-at 2026-09-01T12:00:00Z --data-root .glio --output execution.json
glio-noncode review-workspace-plan-execution-query RUN_ID --status open --data-root .glio --output execution-query.json
glio-noncode review-workspace-plan-execution-schema --output execution-schema.json
glio-noncode review-workspace-plan-execution-capabilities --output execution-capabilities.json
glio-noncode review-workspace-plan-execution-release RUN_ID --data-root .glio --output execution-release
glio-noncode review-workspace-plan-execution-release-verify execution-release --output execution-release-verification.json
glio-noncode review-workspace-plan-execution-release-load execution-release --include-report --output execution-release-report.json
glio-noncode review-workspace-plan-execution-release-query execution-release --status open --limit 50 --output execution-release-query.json
glio-noncode review-workspace-plan-execution-release-diff execution-release-a execution-release-b --output execution-release-diff.json
glio-noncode review-workspace-release-query review-release --collection evidence --limit 50 --output release-query.json
glio-noncode review-workspace-release-plan review-release --output release-plan.json
glio-noncode review-workspace-release-diff release-a release-b --output release-diff.json
```

The command exits successfully when the public projection is safe to consume,
including when its review state is `review`. `abstained` and `blocked` are
content states that remain inspectable when the run itself is valid; failed
replay verification returns no reasoning collections.

## Exports and portable release

`review-workspace-export` renders JSON, Markdown, or one named CSV collection.
The named collections are `hypotheses`, `edges`, `evidence`, `alternatives`,
`deltas`, `provenance`, and `review_queue`. Markdown includes coverage,
integrity, warnings, and all review collections; CSV uses stable headers,
sorted source views, JSON-encoded collection cells, and LF line endings.

`review-workspace-release` packages the JSON projection, Markdown report, and
all seven CSV collections into nine UTF-8 artifacts. `manifest.json` records
byte count, line count, media type, and a content address for each artifact.
`review-workspace-release-verify` independently checks the manifest address,
exact bytes, safe direct filenames, unexpected files, and the public boundary.
The API remains read-only: `GET /v1/runs/{run_id}/review-workspace/export`
supports `format=json|markdown|csv` and `collection` for CSV; filesystem
materialization is an explicit CLI operation.

## Query and facets

`review-workspace-index` computes reusable collection, state, source, context,
dimension, item-type, and priority facets. `review-workspace-query` applies
bounded filters over that same public index and returns a stable page plus
facets for the complete matched set. Supported filters include collection,
free-text over the aggregate projection, evidence/review state, source ID,
context key, item type, delta dimension, queue priority, offset, and limit.
Rows are sorted by collection order and public item identifier; pagination
cannot change the underlying content address. Use `limit=none` only through
the offline closure helper, where the report's collection ceilings remain the
upper bound.

## Triage plan

`review-workspace-plan` expands each explainable queue item into ordered,
descriptive work steps. The intake step is followed, when applicable, by
context-fit, source-provenance, alternative-comparison, and disposition-
preparation steps. A disposition-preparation step is a checklist boundary; it
does not store the disposition. Hypothesis inspection can depend on queued
evidence inspection, so a reviewer can see the intended order without treating
the dependency as a scientific relationship.

The plan reports five lanes (`intake`, `context`, `provenance`, `alternatives`,
and `disposition`), priority counts, estimate units, exact action addresses,
and structural checks for queue closure, dependency closure, topological order,
lane closure, public-boundary safety, and configured bounds.
`review-workspace-plan-query` provides bounded action filters for lane, action kind, queue item,
target, state, priority, text, offset, and limit with complete-match facets.
`review-workspace-plan-export` renders JSON, Markdown, and deterministic action,
lane, and check CSV files. A verified portable release can be reopened and
planned with `review-workspace-release-plan`; no live run store is required.

## Plan execution ledger

`review-workspace-plan-event` appends one explicit transition to the local
`review-plan-execution/<plan-address>/events.jsonl` ledger. Valid transitions
are `start`, `complete`, `block`, `skip`, and `reopen`. The event chain is
address-linked and the neighboring `manifest.json` records exact byte, line,
event-count, and event-file addresses. A completion event must name every
required public check for its action and every dependency must already be
completed; blocked, skipped, or completed actions can be reopened only with an
explicit reason.

`review-workspace-plan-execution` replays the ledger into action statuses,
readiness, dependency waits, next-action IDs, blocked-action IDs, counters, and
structural checks. The execution report can be queried by status, lane, action
kind, action ID, event kind, priority, or text, and exports deterministic JSON,
Markdown, action CSV, event CSV, and check CSV. The ledger is operational only:
it does not alter the dossier, evidence, plan, or scientific conclusion.

The same execution query surface accepts `view=events` (or the CLI
`--view events`) for a first-class ordered event timeline. Timeline rows carry
their zero-based ledger sequence, typed transition, predecessor address,
occurrence instant, check and reference addresses, and a row content address.
They support exact kind, action, event, check, and reference filters; bounded
text and occurrence-range filters; sequence windows; pagination; and complete-
match facets for kinds, actions, checks, and references. Timeline results are
derived only from the replay-verified report and never create a second ledger.

## Execution metrics

`review-workspace-plan-execution-query --view metrics` derives deterministic
operational metrics from the typed source plan and replay report. It reports
integer-basis-point completion, declared estimate units, action timing and
transition counts, lane aggregation, dependency waits, required-check
coverage, blocked work, and the estimated critical path. It can be rendered as
canonical JSON, Markdown, or CSV through the portable release and never acts as
a scientific score.

## Execution operations

`review-workspace-plan-execution-query --view operations` projects the replayed
plan into a deterministic attention queue. Completed actions are excluded;
remaining actions are ranked into blocked, ready, in-progress, dependency-wait,
skipped, or queued classes using attention rank, plan priority, plan sequence,
and action ID. Each row includes public action context, unresolved
dependencies, event count, bounded rationale, recommended transition, and a
content address. The projection is read-only and does not assign work, mutate
the append-only ledger, infer identity, or make a scientific decision.

The operations projection links to the metrics content address and exports
deterministic JSON, Markdown, and CSV. Its schema and capability metadata are
available from `review-workspace-plan-execution-operations-schema` and
`review-workspace-plan-execution-operations-capabilities`.

## Portable execution release

`review-workspace-plan-execution-release` packages seventeen exact-byte artifacts:
the typed execution report, human report, action CSV, event CSV, check CSV,
canonical `events.jsonl`, and five source-plan artifacts covering the typed plan,
plan Markdown, plan actions, plan lanes, and plan checks, plus metrics JSON,
Markdown, and CSV, plus operations JSON, Markdown, and CSV. The manifest carries
each artifact's byte count, line count, media type, and content address, plus
execution, plan, metrics, and operations addresses.
`review-workspace-plan-execution-release-verify` independently validates safe
paths, artifact closure, nested report/action/check addresses, event-stream
reconciliation, metrics and operations derivation, manifest bytes, and the
public boundary. A verified package can
be loaded, queried, and diffed without a local runtime or plan store.

`review-workspace-plan-execution-release-query` applies the live bounded action
filters to a verified package; pass `--view events` for the same offline event
timeline and its sequence-aware facets, or `--view metrics` for the verified
metrics projection, or `--view operations` for the verified attention queue.
`review-workspace-plan-execution-release-diff`
compares source-plan action, lane, and check changes in addition to event IDs,
action status/address changes, execution checks, and artifact addresses between
two verified packages. Its nested metrics diff reports right-minus-left
completion, timing, check, dependency-wait, status-count, event-kind, action,
lane, and critical-path deltas. Release operations are read-only at the API boundary;
filesystem materialization remains an explicit CLI action.

## API

`GET /v1/review-workspace/schema` and
`GET /v1/review-workspace/capabilities` expose the contract. Use
`GET /v1/review-workspace/query/schema` and
`GET /v1/review-workspace/query/capabilities` for the bounded query contract.
`GET /v1/runs/{run_id}/review-workspace` for the current run and add
`baseline_run_id` to request verified cross-run deltas. Both runs must belong
to the same case and pass replay verification.

`GET /v1/runs/{run_id}/review-workspace/query` accepts the same filters as the
CLI through query parameters. Repeated `state` and `source_id` parameters are
allowed; `collection`, `text`, `context_key`, `item_type`, `dimension`,
`priority`, `offset`, `limit`, and `baseline_run_id` are scalar parameters.

`GET /v1/review-workspace/plan/schema` and
`GET /v1/review-workspace/plan/capabilities` expose the triage-plan contract.
`GET /v1/runs/{run_id}/review-workspace/plan` returns the ordered plan and
accepts `baseline_run_id` plus an optional JSON `config` object. The nested
`/plan/query` route accepts `lane`, `action_kind`, `queue_item_id`, `target_id`,
`target_type`, `state`, repeated `priority`, `text`, `offset`, `limit`, and
`baseline_run_id` filters. API responses remain read-only and payload-free.

`GET /v1/review-workspace/plan/execution/schema` and
`GET /v1/review-workspace/plan/execution/capabilities` expose the append-only
execution contract. `GET /v1/runs/{run_id}/review-workspace/plan/execution`
replays the local ledger; `/execution/query` applies bounded action filters by
default and accepts `view=events`, `view=metrics`, or `view=operations`.
Timeline filters
include `kind`, `event_id`, `action_id`, `check_id`, `reference_address`,
`occurred_from`, `occurred_to`, `sequence_start`, `sequence_end`, `text`,
`offset`, and `limit`. Ledger writes remain an explicit CLI operation so the
HTTP service stays read-only.

`GET /v1/review-workspace/plan/execution-release/schema` and
`GET /v1/review-workspace/plan/execution-release/capabilities` expose the
portable handoff contract. `GET
/v1/runs/{run_id}/review-workspace/plan/execution-release` returns the current
release projection in memory, and `/execution-release/query` applies its
bounded filters. Add `view=events` to query the verified event timeline with
the same ordering and facets, `view=metrics` for derived operational metrics,
or `view=operations` for the verified attention queue. The HTTP release
projection is read-only and does not write a filesystem package.

## Offline release operations

`review-workspace-release-load` verifies and reopens the public JSON projection
without a local run store. `review-workspace-release-index` and
`review-workspace-release-query` run the same facet and pagination contract as
the live workspace. `review-workspace-release-diff` compares exact artifact
addresses and collection item addresses between two verified releases. Any
manifest, byte, path, or boundary failure blocks loading before report rows
are exposed. `review-workspace-release-plan` runs the same triage-plan
synthesis over the verified report, so live and offline action addresses can be
compared without rehydrating a runtime.

The API response contains independent content addresses for the complete
workspace and every review collection item. This allows a renderer or offline
handoff to verify exact receipts without trusting a summary score.

## Boundary and limitations

Review state indicates work to adjudicate, not truth. Evidence state remains
distinct from review state: supported, contradictory, measured-negative,
absent, out-of-domain, and abstained claims are not silently converted into a
positive or negative conclusion. Source IDs and receipt IDs are declarations;
they do not establish external validation or scientific reproducibility by
themselves.
