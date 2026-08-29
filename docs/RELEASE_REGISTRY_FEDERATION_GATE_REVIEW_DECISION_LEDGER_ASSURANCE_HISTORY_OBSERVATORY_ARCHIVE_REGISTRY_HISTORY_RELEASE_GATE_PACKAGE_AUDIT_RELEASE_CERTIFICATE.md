# Registry history release-gate package-audit release certificate

The release certificate is a separate decision boundary over an independently generated package audit.  It verifies the audit's fixed check denominator, completion and acceptance state, address namespaces, public projection, and content-address replay under an explicit certificate policy.  It reports `ready`, `held`, or `blocked` without changing the underlying audit.

## Python

```python
from glio_noncode import (
    audit_assurance_history_observatory_archive_registry_history_release_gate_package_directory,
    evaluate_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate,
)

audit = audit_assurance_history_observatory_archive_registry_history_release_gate_package_directory("/path/to/package")
certificate = evaluate_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate(audit)
print(certificate.state, certificate.accepted)
```

## CLI

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-release-gate-package-audit-certificate \
  --input /path/to/package --format markdown
```

## HTTP

Use `GET /v1/assurance-history-observatory/archive-registry/history/release-gate/package/audit/certificate?input=/path/to/package&format=json`.  The route also exposes `/schema`, `/policy-schema`, `/check-schema`, and `/capabilities`.
