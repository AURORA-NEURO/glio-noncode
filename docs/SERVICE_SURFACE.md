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
| GET | `/v1/runs/{run_id}/summary` | Aggregate evidence, review, and validation counters |
| GET | `/v1/runs/{run_id}/query-closure` | Complete content-addressed dossier query projection |
| GET | `/v1/runs/{run_id}/hypotheses` | Filter bounded hypothesis projections |
| GET | `/v1/runs/{run_id}/evidence` | Filter bounded evidence-claim projections |
| GET | `/v1/runs/{run_id}/experiments` | Filter bounded validation-route projections |
| GET | `/v1/runs/{run_id}/lineage` | Join hypothesis edges to referenced claims |
| GET | `/v1/runs/{run_id}/release` | Build a gated, content-addressed portable dossier release bundle |
| POST | `/v1/runs/{run_id}/review` | Attach a typed human review and create a new dossier snapshot |
| POST | `/v1/evaluate` | Existing case evaluation endpoint |

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

Dossier-plane queries accept `offset`, `limit`, and resource-specific filters.
Evidence supports `state`, `tier`, `channel`, `source_id`, `edge_id`, and
`evidence_id`; hypotheses support `hypothesis_id`, `status`, `min_support`, and
`max_uncertainty`; experiments support `option_id` and `assay`. The lineage
projection accepts `hypothesis_id` and fails closed when an edge references a
missing claim.

## CLI and offline closure

Run the compact status projection:

```text
glio-noncode service-surface --output service-status.json
```

Run the detailed archival projection:

```text
glio-noncode service-surface --closure --output service-surface-closure.json
```

Inspect persisted case work:

```text
glio-noncode run-catalog --data-root .glio
glio-noncode run-catalog --data-root .glio --closure --output run-catalog-closure.json
glio-noncode run-inspect run-<run-id> --data-root .glio --output run-inspection.json
glio-noncode run-review run-<run-id> review.json --data-root .glio --output reviewed-dossier.json
glio-noncode run-query run-<run-id> summary --data-root .glio --output run-summary.json
glio-noncode run-query run-<run-id> lineage --data-root .glio --output run-lineage.json
glio-noncode run-query run-<run-id> closure --data-root .glio --output dossier-query-closure.json
glio-noncode run-release run-<run-id> --data-root .glio --output dossier-release
glio-noncode run-release-verify dossier-release --output release-verification.json
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
