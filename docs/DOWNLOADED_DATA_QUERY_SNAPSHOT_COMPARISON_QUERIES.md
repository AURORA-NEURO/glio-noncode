# Downloaded-data query snapshot comparison queries

The comparison-query boundary inspects one persisted longitudinal comparison
without reopening either source handoff or the downloaded archive. It is a
value-free review projection: rows retain public identities, source addresses,
change classes, and bounded metadata, but do not copy source record values or
filesystem paths.

## Query resources

The query emits rows in canonical resource order:

- `summary` — one row with comparison-level counts and direction;
- `items` — one row per stable comparison item;
- `added`, `removed`, `changed`, `unchanged` — action-specific item rows; and
- `field-changes` — one row for every changed semantic field on an item.

An item row is paired by the comparison's stable key and retains its source
resource, identity, left and right row addresses, item address, action, and
changed-field count. A field-change row sets `field` to the changed semantic
field while retaining the parent item's key and address.

## Filters

The bounded query supports exact filters for:

- one or more resources;
- action (`added`, `removed`, `changed`, or `unchanged`);
- source resource, stable key, identity, or semantic field;
- comparison direction or state transition;
- any retained item, row, source, or comparison address; and
- case-insensitive text across the public query row.

`offset` and `limit` provide deterministic pagination. Returned ordinals are
page ordinals, and every row and query has a content address that replays from
canonical JSON. Empty filter results remain valid accepted queries with zero
rows and a stable address.

## Python

```python
from pathlib import Path

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff as comparison_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query as query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_audit as audit_model

comparison = comparison_model.load_diff(Path("comparison"))
query = query_model.query_diff(
    comparison,
    resources=("field-changes",),
    change="changed",
    field="diff_id",
    limit=32,
)
audit = audit_model.audit_query(query)
assert audit.accepted
```

`query_json`, `query_csv`, and `render_query_markdown` provide stable output
projections. `query_from_mapping` and `verify_query` reject unknown fields,
invalid resource order, out-of-bound pagination, bad addresses, and tampered
content-addressed rows.

## CLI and HTTP

Query a persisted comparison from the CLI:

```powershell
python -m glio_noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query comparison --resource field-changes --change changed --field diff_id --format json --output comparison-query.json
python -m glio_noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-audit comparison-query.json --format summary
```

The loopback service exposes the corresponding route at:

```text
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query/audit
```

The query route accepts the same bounded filters as query parameters. The audit
route consumes the emitted query JSON. Schema and capability routes describe
the row, query, check, and audit contracts without requiring a source archive.

## Independent audit

The audit recomputes twelve fixed checks:

1. current version;
2. public boundary;
3. canonical resource order;
4. every declared filter on every returned row;
5. count and pagination conservation;
6. page ordinal order;
7. row content-address replay;
8. comparison and endpoint linkage;
9. action-class replay;
10. changed-field semantics;
11. public-boundary replay; and
12. mapping round-trip address stability.

The audit is accepted only when all checks pass. The demo
`examples/downloaded_data_contract_resolution_history_diff_policy_demo.py`
builds the comparison-query projection from the attached downloaded archive
and writes both JSON and Markdown review outputs.
