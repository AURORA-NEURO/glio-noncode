# Registry history release-certificate query

The release-certificate query boundary exposes bounded inspection over a package-audit certificate.  It supports summary, checks, passed, failed, holds, blocking, and evidence resources plus severity, check identity, public text, offset, and limit filters.  A raw three-file package can be audited, certified, and queried in one operation.

## Python

```python
from glio_noncode import query_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_directory

result = query_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_directory(
    "/path/to/package", resource="summary"
)
print(result.records)
```

## CLI

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-release-gate-package-audit-certificate-query \
  --input /path/to/package --resource failed --format markdown
```

## HTTP

Use `GET /v1/assurance-history-observatory/archive-registry/history/release-gate/package/audit/certificate/query?input=/path/to/package&resource=failed&format=json`.  The route exposes `/query-schema`, `/query-result-schema`, and `/query-capabilities` alongside the query path.
