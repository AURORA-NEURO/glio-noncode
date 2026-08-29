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

## Real downloaded-data demonstration

The runnable example is [`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_demo.py`](../examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_demo.py). It accepts the downloaded history directory used by the local assurance demos and can optionally persist the package. A successful run exposes the history address, release-gate address, package manifest address, package-audit address, certificate address, snapshot count, three-file package count, and final `ready` decision in one result.
