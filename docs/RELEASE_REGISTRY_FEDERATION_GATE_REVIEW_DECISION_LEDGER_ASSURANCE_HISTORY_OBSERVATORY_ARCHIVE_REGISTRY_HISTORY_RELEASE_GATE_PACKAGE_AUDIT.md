# Registry history release-gate package audit

The release-gate package audit independently checks a persisted three-file handoff.  It does not call the package loader, and it retains a public incomplete report when the directory is damaged.

Checks are fixed and addressed: exact members, canonical UTF-8 JSON, manifest contract, byte receipts, gate linkage, policy linkage, nested gate-check identities, decision projection, public boundary, package content addresses, and mapping round-trip.

## Python

```python
from glio_noncode import audit_assurance_history_observatory_archive_registry_history_release_gate_package_directory

report = audit_assurance_history_observatory_archive_registry_history_release_gate_package_directory("/path/to/package")
print(report.state, report.passed_count, report.failed_count)
```

## CLI

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-release-gate-package-audit \
  --input /path/to/package --format markdown
```

The command returns exit code `0` for a complete package and `2` for a diagnostic with one or more failed checks.  Reports contain addresses and check evidence only; input paths and process metadata are excluded.

## HTTP

Use `GET /v1/assurance-history-observatory/archive-registry/history/release-gate/package/audit?input=/path/to/package&format=json`.  The same route exposes `format=markdown` and `format=summary`; `/schema`, `/check-schema`, and `/capabilities` are available under the audit route.
