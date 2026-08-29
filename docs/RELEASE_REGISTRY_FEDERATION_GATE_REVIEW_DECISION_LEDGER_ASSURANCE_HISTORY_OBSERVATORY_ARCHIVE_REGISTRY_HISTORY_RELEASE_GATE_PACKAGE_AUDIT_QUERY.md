# Registry history release-gate package-audit query

The package-audit query boundary exposes bounded inspection over the eleven checks produced by the independent package audit.  Resources are `summary`, `checks`, `passed`, `failed`, and `evidence`.  Filters support check identity, pass/fail state, case-insensitive public text, offset, and limit.  Every result is a public content-addressed projection.

## Python

```python
from glio_noncode import query_assurance_history_observatory_archive_registry_history_release_gate_package_audit_directory

result = query_assurance_history_observatory_archive_registry_history_release_gate_package_audit_directory(
    "/path/to/package", resource="failed", limit=20
)
print(result.total_count, result.returned_count)
```

## CLI

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-release-gate-package-audit-query \
  --input /path/to/package --resource failed --format markdown
```

## HTTP

Use `GET /v1/assurance-history-observatory/archive-registry/history/release-gate/package/audit/query?input=/path/to/package&resource=failed&format=json`.  The route also exposes `/query-schema`, `/query-result-schema`, and `/query-capabilities` next to the query path.  A damaged package returns the same bounded records with HTTP `422`, preserving the failed audit decision while allowing evidence inspection.
