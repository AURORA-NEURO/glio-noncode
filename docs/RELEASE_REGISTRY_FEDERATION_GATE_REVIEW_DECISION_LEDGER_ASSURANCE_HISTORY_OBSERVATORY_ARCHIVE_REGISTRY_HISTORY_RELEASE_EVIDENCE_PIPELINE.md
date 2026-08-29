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

## Real downloaded-data demonstration

The runnable example is [`release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_demo.py`](../examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_demo.py). It accepts the downloaded history directory used by the local assurance demos and can optionally persist the package. A successful run exposes the history address, release-gate address, package manifest address, package-audit address, certificate address, snapshot count, three-file package count, and final `ready` decision in one result.
