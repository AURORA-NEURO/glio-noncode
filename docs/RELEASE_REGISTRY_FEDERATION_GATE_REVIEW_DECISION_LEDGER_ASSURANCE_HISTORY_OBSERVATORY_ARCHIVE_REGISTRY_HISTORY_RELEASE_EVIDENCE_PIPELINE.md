# Downloaded-history release evidence pipeline

The release evidence pipeline is the one-call orchestration boundary for a downloaded observatory history directory. It composes the independently verifiable stages already exposed by `glio-noncode`:

1. Load and validate the ordered history snapshots.
2. Evaluate the release gate and its policy checks.
3. Materialize the exact three-file gate package when a destination is supplied.
4. Run the independent package audit.
5. Issue the package-audit release certificate.
6. Return a path-free, content-addressed receipt that projects every stage and the final release decision.

The pipeline only returns `ready` when both the release gate and the release certificate are accepted. A blocked gate or certificate produces `blocked`; other non-accepted combinations produce `held`. The receipt is replayable with `pipeline_from_mapping`, and `address_pipeline` recomputes its public content address.

## Python

```python
from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_json,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline,
)

value = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline(
    "path/to/downloaded-history",
    "path/to/release-package",
)
print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_json(value))
```

Omit the destination to run the package and audit stages in memory. Supplying a destination writes `manifest.json`, `policy.json`, and `gate.json` using the existing atomic package writer; use `overwrite=True` only when replacing an existing package is intentional.

## CLI

The long-form command is:

```text
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-release-gate-release-evidence-pipeline
```

Example:

```text
python -m glio_noncode.cli <command> --input path/to/downloaded-history --destination path/to/release-package --format summary
```

The `-schema` and `-capabilities` suffixes expose the machine-readable contract. The HTTP route uses the same boundary at `/.../history/release-gate/release-evidence-pipeline` with `/schema` and `/capabilities` companions.

## Querying the receipt

The companion query module exposes four bounded resources: `summary`, `stages`, `decisions`, and `evidence`. Stage records carry their acceptance state and content address; decision records separate the gate, certificate, and final release decisions; evidence records provide the complete address chain. Filters support accepted/rejected state, stage identity, state, case-insensitive text matching, and deterministic pagination.

```python
from glio_noncode import query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_directory

result = query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_directory(
    "path/to/downloaded-history",
    resource="stages",
    stage="release-certificate",
)
print(result.records)
```

The query demo is [`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query_demo.py`](../examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query_demo.py). Its CLI and HTTP surfaces offer JSON, CSV, and Markdown projections plus replayable content addresses.

## Durable bundle

For a portable handoff, `build_bundle` and `write_bundle` persist five exact files: `manifest.json`, `pipeline.json`, `stages-query.json`, `decisions-query.json`, and `evidence-query.json`. The manifest records the pipeline address, all query-result addresses, byte sizes, and byte hashes. `load_bundle` rejects extra members, symlinks, non-canonical JSON, oversized artifacts, altered query views, or broken linkage, then reconstructs the same path-free bundle receipt.

```python
from glio_noncode import (
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline,
    write_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle,
)

pipeline = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline("path/to/downloaded-history")
write_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle(pipeline, "path/to/evidence-bundle")
```

The bundle is also available at the CLI `...release-evidence-pipeline-bundle` command and the HTTP `/.../release-evidence-pipeline/bundle` route, each with verify, manifest, schema, and capability companions.

## Independent bundle audit

The bundle audit reads the raw directory independently from `load_bundle`. It
checks exact members, canonical bytes, manifest semantics, artifact receipts,
pipeline and query linkage, all three query projections, the public boundary,
content-address reproduction, and mapping round trips. A damaged bundle
returns an `incomplete` report with one row for every check, allowing a review
workflow to see which evidence failed while preserving the report's own
content address. The report contains no source path or timestamps.

```python
from glio_noncode import (
    audit_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_directory,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_markdown,
)

audit = audit_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_directory("path/to/evidence-bundle")
print(audit.summary())
print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_markdown(audit))
```

Use the `...release-evidence-pipeline-bundle-audit` CLI command or the HTTP
`/.../release-evidence-pipeline/bundle/audit` route. Both support JSON,
Markdown, and summary output, plus `schema`, `check-schema`, and
`capabilities` companions. The runnable example is
[`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_demo.py`](../examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_demo.py).

The audit-query companion provides `summary`, `checks`, `passed`, `failed`,
and `evidence` resources with pass/fail and check-ID filters, bounded text
search, pagination, and JSON, CSV, or Markdown output. It can query a damaged
bundle and expose the failed rows without weakening the audit boundary:

```python
from glio_noncode import query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_directory

failed = query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_directory(
    "path/to/evidence-bundle",
    resource="failed",
)
print(failed.records)
```

The query is available at `...release-evidence-pipeline-bundle-audit-query`
and `/.../release-evidence-pipeline/bundle/audit/query`, with
`query-schema`, `query-result-schema`, and `query-capabilities` companions.
The runnable example is
[`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_query_demo.py`](../examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_query_demo.py).

## Comparing bundle revisions

The bundle diff compares two directories only after each has passed the strict
five-file loader. It reports pipeline state and acceptance transitions,
manifest and query-address transitions, aggregate changed fields, and a
fixed row for every bundle file with byte sizes, hashes, and changed-field
details. The aggregate state is deterministically `unchanged`, `improved`,
`regressed`, or `mixed`; source paths never enter the diff.

```python
from glio_noncode import (
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_markdown,
)

diff = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff(
    "path/to/baseline-bundle",
    "path/to/candidate-bundle",
)
print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_markdown(diff))
```

The diff is available at `...release-evidence-pipeline-bundle-diff` and
`/.../release-evidence-pipeline/bundle/diff`, with JSON, CSV, Markdown, and
summary projections plus `schema`, `item-schema`, and `capabilities`
companions. The runnable example is
[`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_demo.py`](../examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_demo.py).

## Querying bundle revisions

The diff-query companion provides bounded projections over the verified diff.
The `fields` resource exposes semantic baseline/candidate transitions, while
`files`, `changed`, and `unchanged` expose the five artifact rows. The
`evidence` resource adds hashes, byte sizes, changed fields, and item content
addresses. Every resource supports action, file-name, changed-field, and
case-insensitive text filters with deterministic offset/limit pagination.

```python
from glio_noncode import query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_directories

changed_files = query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_directories(
    "path/to/baseline-bundle",
    "path/to/candidate-bundle",
    resource="changed",
    limit=10,
)
print(changed_files.records)
```

The query is available at `...release-evidence-pipeline-bundle-diff-query`
and `/.../release-evidence-pipeline/bundle/diff/query`, with JSON, CSV, and
Markdown output plus `query-schema`, `query-result-schema`, and
`query-capabilities` companions. The runnable example is
[`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_query_demo.py`](../examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_query_demo.py).

## Auditing bundle revisions

The diff-audit companion independently replays a public diff mapping through a
fixed twelve-check contract. It checks exact fields, public-boundary safety,
all bundle/manifest/pipeline/query namespaces, file identities and actions,
semantic field derivation, changed/unchanged count conservation, artifact and
query counts, aggregate state, nested item addresses, the diff content address,
and typed mapping round-trip. A malformed mapping becomes an `incomplete`
report with addressed failed checks instead of an unstructured exception.

```python
from glio_noncode import (
    audit_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff,
)

diff = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff(
    "path/to/baseline-bundle",
    "path/to/candidate-bundle",
)
report = audit_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff(diff)
print(report.summary())
```

The audit is available at `...release-evidence-pipeline-bundle-diff-audit`
and `/.../release-evidence-pipeline/bundle/diff/audit`, with `schema`,
`check-schema`, and `capabilities` companions. The runnable example is
[`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_demo.py`](../examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_demo.py).

The diff-audit query companion provides `summary`, `checks`, `passed`,
`failed`, and `evidence` resources over that twelve-check report. It supports
check-ID and pass/fail filters, bounded case-insensitive text search,
pagination, and JSON, CSV, or Markdown output. The query is available at
`...release-evidence-pipeline-bundle-diff-audit-query` and
`/.../release-evidence-pipeline/bundle/diff/audit/query`, with
`query-schema`, `query-result-schema`, and `query-capabilities` companions.

## Observability

The observability projection turns the same receipt into six ordered events
and twelve denominator metrics. Five events cover the evaluated stages and a
sixth records the final release decision. Each event links an input address to
an output address; metrics cover snapshot and stage counts, accepted and
rejected stage/decision counts, package files, query views, readiness, and the
public-boundary count. No timestamps, local paths, user metadata, or mutable
process identifiers enter this projection.

```python
from glio_noncode import (
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability,
)

pipeline = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline("path/to/downloaded-history")
observability = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability(pipeline)
print(observability.summary())
```

The CLI and HTTP observability surfaces support JSON, CSV, and Markdown plus
event, metric, and aggregate schemas. A valid held or blocked pipeline still
produces an accepted observability projection; `pipeline_accepted` preserves
the release decision separately from observability-contract validity.

## Querying observability

The observability query boundary turns the six events and twelve metrics into
bounded resources: `summary`, `events`, `metrics`, `accepted`, and `rejected`.
Queries can filter stage, state, event type, metric name, metric plane, or
case-insensitive public text, then apply deterministic offset/limit pagination.
The result stores the exact query and a content address, so a dashboard page
can be replayed from its JSON without reopening the downloaded directory.

```python
from glio_noncode import (
    query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_directory,
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_query_json,
)

result = query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_directory(
    "path/to/downloaded-history",
    resource="events",
    event_type="stage_evaluated",
    accepted=True,
    limit=3,
)
print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_query_json(result))
```

The CLI command is `...release-evidence-pipeline-observability-query`; the
HTTP route is `/v1/.../release-evidence-pipeline/observability/query`. Both
provide query schema, query-result schema, capabilities, JSON, CSV, and
Markdown output. The runnable example is
`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_query_demo.py`.

## Independent observability audit

The observability audit replays the public projection with thirteen fixed
checks. It verifies exact fields and namespace safety, the complete event
sequence, stage and event-type projection, input/output transition linkage,
event and metric content addresses, denominator conservation, final decision
conservation, mapping replay, and the projection address. Damaged mappings
produce an incomplete report with failed checks instead of an exception, so a
reviewer can see which invariant failed without losing the rest of the
diagnostic evidence.

```python
from glio_noncode import audit_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_directory

audit = audit_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_directory(
    "path/to/downloaded-history"
)
print(audit.summary())
```

The CLI command is `...release-evidence-pipeline-observability-audit`; the
HTTP route is `/v1/.../release-evidence-pipeline/observability/audit`. Both
support summary, JSON, and Markdown output plus `schema`, `check-schema`, and
`capabilities` companions. The runnable example is
`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_demo.py`.

The audit-query companion exposes `summary`, `checks`, `passed`, `failed`,
and `evidence` resources over the thirteen checks. It supports check identity,
pass/fail, and public text filters with deterministic pagination, and it keeps
the audit address and query address in every result. Use
`...release-evidence-pipeline-observability-audit-query` or
`/.../release-evidence-pipeline/observability/audit/query` for JSON, CSV, or
Markdown output; `query-schema`, `query-result-schema`, and
`query-capabilities` are available beside the command and route. The runnable
example is
`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_query_demo.py`.

## Durable observability handoff bundle

The observability bundle provides an offline handoff for operators who need
the operational projection and its independent assurance evidence together.
It writes exactly nine canonical JSON members: the pipeline receipt,
observability projection, events, metrics, accepted and rejected event query
views, the thirteen-check audit, the audit-check query view, and a manifest
with byte receipts. Reloading verifies every projection, query address,
content address, and artifact byte before returning the path-free receipt.

```python
from glio_noncode import (
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline,
    write_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle,
    verify_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle,
)

pipeline = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline("path/to/downloaded-history")
write_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle(
    pipeline,
    "path/to/observability-handoff",
)
handoff = verify_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle(
    "path/to/observability-handoff"
)
print(handoff.summary())
```

The CLI command is `...release-evidence-pipeline-observability-bundle`; its
`-verify`, `-manifest`, `-schema`, `-manifest-schema`, and `-capabilities`
companions expose the same contract. The HTTP surface is
`/.../release-evidence-pipeline/observability/bundle`, with matching
`/verify`, `/manifest`, `/schema`, `/manifest-schema`, and `/capabilities`
routes. The runnable example is
`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_demo.py`.

### Persisted observability bundle queries

Once a handoff directory exists, the persisted-bundle query boundary reads
only its verified canonical members. It exposes `summary`, `observability`,
`events`, `metrics`, `accepted`, `rejected`, `checks`, `passed`, `failed`, and
`evidence` resources, with stage/state/event/metric/plane/check filters,
case-insensitive text search, bounded pagination, replay addresses, and JSON,
CSV, or Markdown output. This lets an operator inspect a copied handoff
without rebuilding the downloaded history or trusting an unverified file.

The CLI command is `...release-evidence-pipeline-observability-bundle-query`
with `-query-schema`, `-query-result-schema`, and `-query-capabilities`
companions. The HTTP route is
`/.../release-evidence-pipeline/observability/bundle/query`, with the same
schema and capability routes. The runnable example is
`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_query_demo.py`.

### Persisted observability bundle comparisons

Two independently verified handoff directories can be compared without
rebuilding the downloaded history. The comparison covers all nine canonical
members, exact byte sizes and hashes, semantic receipt fields, nested query
addresses, artifact counts, and a deterministic aggregate transition of
`unchanged`, `improved`, `regressed`, or `mixed`. Changed and unchanged files
remain individually addressed so a release operator can see both the semantic
and byte-level reason for a handoff revision.

The CLI command is
`...release-evidence-pipeline-observability-bundle-diff`, with `-schema`,
`-item-schema`, and `-capabilities` companions. The HTTP route is
`/.../release-evidence-pipeline/observability/bundle/diff`, with matching
`/schema`, `/item-schema`, and `/capabilities` routes. The runnable example is
`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_demo.py`.

The diff has an independent twelve-check audit covering public-boundary
namespace safety, semantic and byte-action conservation, artifact/query count
conservation, nested addresses, aggregate-state agreement, content-address
replay, and mapping round trips. Its `/audit` surface returns addressed checks
and a release-safe status; `/audit/query` exposes bounded `summary`, `checks`,
`passed`, `failed`, and `evidence` resources with check-id/text filters,
pagination, replay addresses, and JSON/CSV/Markdown output. The audit-query
example is
`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_audit_query_demo.py`.

## Real downloaded-data demonstration

The runnable example is [`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_demo.py`](../examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_demo.py). It accepts the downloaded history directory used by the local assurance demos and can optionally persist the package. A successful run exposes the history address, release-gate address, package manifest address, package-audit address, certificate address, snapshot count, three-file package count, and final `ready` decision in one result.
