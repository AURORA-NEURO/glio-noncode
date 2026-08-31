# Downloaded-data comparison-query snapshot registry history

This module adds a longitudinal, value-free history stream for persisted comparison-query snapshot registries. It accepts one or more registry handoffs that share a registry identity, verifies every nested snapshot/query/audit address, and records deterministic transitions between registry revisions.

## What it does

- admits only typed comparison-query snapshot registries with one shared `registry_id`;
- rejects duplicate registry content addresses and mixed registry identities;
- computes `initial`, `improved`, `regressed`, `unchanged`, or `changed` transitions from conserved registry quality counters;
- retains predecessor links, registry state, acceptance, and all registry count fields;
- exposes bounded summary, entry, transition, acceptance, readiness, and text-search query resources;
- emits JSON, CSV, and Markdown projections without source paths or private metadata.

The history package is exactly four canonical files:

| File | Purpose |
| --- | --- |
| `entries.json` | ordered registry revisions and transition evidence |
| `summary.json` | conserved totals and latest revision state |
| `manifest.json` | package identity, file list, and artifact addresses |
| `history.json` | complete public history document |

Persistence writes to a temporary sibling and promotes the completed directory atomically. Reload requires the exact file set, canonical JSON bytes, matching content addresses, and replayable nested registry documents. Any extra file, whitespace drift, altered address, or broken cross-link is rejected.

## Audits and queries

The independent history audit has 16 checks covering version and boundary, ordering, identity, unique addresses, predecessor links, transition replay, transition counters, latest replay, count conservation, query conservation, summary/entry/manifest replay, mapping replay, and the public boundary.

The history query has deterministic resource ordering and pagination. Its independent query audit has 12 checks covering resource order, filter shape, count conservation, pagination, row ordering, row addresses, linkage, resource semantics, mapping replay, and the public boundary.

## Python

```python
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history as history_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_audit as audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_query as query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_query_audit as query_audit_model

history = history_model.build_history((baseline_registry, candidate_registry), history_id="downloaded-history")
history_model.persist_history(history, "history-handoff")
audit = audit_model.audit_history(history)
query = query_model.query_history(history, resources=("summary", "improved", "accepted"), accepted=True, limit=64)
query_audit = query_audit_model.audit_query(query)
```

## CLI

Build and persist a history from registry directories:

```powershell
python -m glio_noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history baseline-registry candidate-registry --history-id downloaded-history --destination history-handoff --format summary
```

Audit, query, and audit the query result:

```powershell
python -m glio_noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-audit history-handoff --format summary
python -m glio_noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-query history-handoff --resource summary --resource improved --accepted --format json --output history-query.json
python -m glio_noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-query-audit history-query.json --format summary
```

Schema and capability commands are registered for every history, audit, query, and query-audit document. The local HTTP API mirrors the same operations below the existing downloaded-data compatibility path, with repeated `input` and `resource` query values and the same bounded filters.

## Real downloaded-archive demonstration

`examples/downloaded_data_contract_resolution_history_diff_policy_demo.py` builds the input registries from the supplied downloaded ZIP, persists the history package, reloads it, runs the 16-check history audit, queries accepted ready/improved rows, and runs the 12-check query audit. The demonstration summary reports member selection, record counts, registry counts, transition counts, audit counts, exact package files, and content addresses.
