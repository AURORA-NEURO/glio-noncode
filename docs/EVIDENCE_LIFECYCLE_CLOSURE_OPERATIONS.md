# D14 evidence lifecycle closure operations

The closure layer is an independent review and release surface over the
portable D14 evidence-lifecycle handoff. It consumes hydrated public aggregate
artifacts and emits deterministic projections. It does not require a service,
database, network access, private records, or mutable producer state.

## Release denominators

The source handoff contains 21 exact-byte artifacts, 5 HTTPS source receipts,
16 aggregate records, 4 operation families, 16 executions, 120 evaluation
checks, 36 lineage edges, 16 queue items, 16 review rows, 31 scenario rows, 26
source observability events, and 10 source runtime stages.

The closure layer adds:

| Projection | Contract |
| --- | --- |
| Boundary | Public aggregate key and filesystem audit with forbidden-key inventory |
| Indexes | Ten deterministic address-only indexes over artifacts, records, checks, sources, events, stages, edges, queue, and scenarios |
| Query | Bounded filtered views over thirteen closure resources |
| Reconciliation | 34 cross-projection denominator, join, policy, and address checks |
| Summary | Operation, state, queue, issue, and denominator counters |
| Certification | Eight domains and 48 evidence-linked checks; accepted only at 48/48 |
| Observability | 30 stage events, 32 record events, and 18 aggregate metrics |
| Graph | 356 nodes and 585 connected joins for the current public fixture |
| Failure controls | Ten named negative controls for boundary and join drift |
| Runtime | Twelve ordered stages ending in a deterministic release decision |
| Export | Twelve exact-byte JSON artifacts plus a manifest and verification receipt |

Every projection has a stable content address derived from canonical JSON. The
closure does not include operation payload text in query or export rows. It
retains identifiers, states, issue codes, addresses, counts, and bounded
review context so a reviewer can reproduce the release decision without
reconstructing private inputs.

## Boundary and privacy behavior

`audit_evidence_lifecycle_closure_boundary` first runs the source offline
boundary audit, then checks every hydrated artifact. It verifies that:

1. every artifact is present and JSON-decodable;
2. every artifact has an exact-byte address and a safe relative path;
3. artifact paths are unique and remain below the export root;
4. nested keys do not contain direct identity or attribution fields;
5. source receipts remain HTTPS addresses;
6. the declared public aggregate boundary is retained.

The key inventory is intentionally recursive. A forbidden key is reported by
its normalized terminal key, making the audit useful for nested fixtures as
well as top-level manifests. The release surface excludes agent, assistant,
author, email, language, model, patient, participant, sample, subject, and
similar direct identity fields.

## Indexes and query contract

The index builder emits address-only entries. Each entry includes the lookup
key, resource kind, target identity, source artifact, ordinal, and source
address. The index audit checks that every index is populated, addressed,
ordinal-bearing, target-bearing, and closed over its denominator.

The supported query resources are:

```text
artifacts records executions checks sources events stages edges queue reviews
scenarios operations states
```

Queries accept bounded pagination and the following filters where applicable:

```text
operation role state artifact_kind event_type disposition scenario_id text
offset limit
```

The default page size is 50 and the maximum is 500. CSV and Markdown exports
are generated from the same canonical row set as the JSON result, so a review
packet cannot silently change shape by output format.

## Reconciliation and summary

Reconciliation is deliberately independent from the source producer objects.
It reparses the public artifact payloads and compares fixture records with
record projections, execution identities, catalog identities, source URIs,
evaluation checks, lineage, review, queue, metrics, runtime, release, replay,
and privacy policy projections.

The current release is accepted when all 34 checks pass. The checks include:

- artifact, record, source, role, and operation conservation;
- catalog-to-fixture and execution-to-record joins;
- evaluation check and address conservation;
- lineage identity and edge conservation;
- release, replay, and source reconciliation acceptance;
- queue disposition conservation at 4 ready and 12 held;
- review and scenario conservation;
- contiguous source runtime stages and 26 source events;
- explicit policy exclusions, metric denominators, issue visibility, and row addresses.

The summary groups records by operation and exposes positive/control counts,
accepted and held counts, issue counts, check counts, passed checks, observed
states, and queue dispositions. Its audit confirms that four balanced
operations each contribute four records and 28 record-level evaluation checks.

## Certification domains

Certification produces six checks in each of eight domains:

1. manifest integrity;
2. fixture and source integrity;
3. evaluation and join integrity;
4. lineage integrity;
5. queue and review integrity;
6. runtime and replay integrity;
7. public boundary and index integrity;
8. release and summary integrity.

Each check includes the observed value, required value, human-readable detail,
and one or more evidence addresses. The report includes domain-level counts,
the global 48-check denominator, failed check identifiers, and a 100 percent
coverage value only when every check passes.

## Observability and graph

The closure observability projection is timestamp-free and deterministic. For
each source runtime stage it emits `stage_started`, `stage_completed`, and
`stage_reconciled`. For each aggregate record it emits `record_observed` and
`record_reconciled`. This produces 62 ordered events with linked input and
output addresses.

The 18 metrics expose artifact, record, source, execution, evaluation,
lineage, queue, review, scenario, operation, runtime, event, issue, and
acceptance denominators. Ratios are represented as bounded numeric values and
retain their unit.

The graph projection connects the root bundle to every artifact, artifact
projections to their row resources, records to executions/checks/queue/review,
and lineage edge nodes to their parent and child identifiers. The current
fixture produces 356 nodes and 585 edges in one connected component. Graph
edges use their own stable address and preserve the originating evidence
address in the deterministic construction input.

## Failure controls

The failure-control report covers ten drift modes:

```text
missing_payload duplicate_path forbidden_key record_join_gap
evaluation_check_drift non_https_source runtime_sequence_gap
queue_disposition_drift scenario_count_drift missing_reconciliation
```

Controls are described as injected and detected. The baseline report is
accepted only when all ten named detectors are present and the source boundary
remains accepted. Individual controls can be requested by identifier without
mutating the source bundle.

## Twelve-stage runtime

`run_evidence_lifecycle_closure_runtime` runs these ordered stages:

1. source bundle;
2. boundary;
3. indexes;
4. index audit;
5. reconciliation;
6. summary;
7. summary audit;
8. certification;
9. observability;
10. graph;
11. replay;
12. finalization.

The runtime rebuilds the source bundle twice with identical identifiers for the
replay stage. The final state is `ready` only when every projection and replay
receipt is accepted. Otherwise it is `blocked`; no partial result is promoted
as a release handoff.

## Exact-byte export

The export packet writes twelve canonical UTF-8 JSON files:

```text
boundary.json indexes.json index-audit.json reconciliation.json summary.json
summary-audit.json certification.json observability.json graph.json
failure-controls.json replay.json runtime.json
```

Each file ends with one newline, has an exact-byte hash, and is listed in the
packet manifest. `verify_evidence_lifecycle_closure_export` checks missing,
changed, and unexpected paths. The manifest itself is deterministic and is
written as `manifest.json`; it is not counted as one of the twelve projection
artifacts.

## CLI and API

The CLI exposes the complete closure surface:

```powershell
glio-noncode evidence-lifecycle-offline-bundle-closure-query <bundle> --resource records
glio-noncode evidence-lifecycle-offline-bundle-closure-boundary <bundle>
glio-noncode evidence-lifecycle-offline-bundle-closure-indexes <bundle>
glio-noncode evidence-lifecycle-offline-bundle-closure-reconciliation <bundle>
glio-noncode evidence-lifecycle-offline-bundle-closure-summary <bundle>
glio-noncode evidence-lifecycle-offline-bundle-closure-certification <bundle>
glio-noncode evidence-lifecycle-offline-bundle-closure-observability <bundle>
glio-noncode evidence-lifecycle-offline-bundle-closure-graph <bundle>
glio-noncode evidence-lifecycle-offline-bundle-closure-failures <bundle>
glio-noncode evidence-lifecycle-offline-bundle-closure-runtime
glio-noncode evidence-lifecycle-offline-bundle-closure-export --destination <dir>
glio-noncode evidence-lifecycle-offline-bundle-closure-export-verify <dir>
```

The HTTP API mirrors the read-only projections at
`/v1/evidence-lifecycle/bundle/closure-*`. The export writer remains an
explicit filesystem CLI operation so callers choose its destination.

## Verification expectations

The focused closure suite covers boundary, indexes, queries, reconciliation,
summary, certification, schema, observability, graph, failure controls,
runtime replay, exact-byte export, CLI handlers, and HTTP endpoints. The
neighboring D14 offline suite remains required because closure acceptance is
meaningful only when the source handoff itself is still exact and accepted.
