# Registry history release-gate query

The release-gate query is the bounded inspection surface for a policy decision
over an ordered registry history. It evaluates the persisted history through
the release gate, then returns only the requested page of public records.

## Resources

| Resource | Records |
| --- | --- |
| `summary` | one gate summary record |
| `checks` | all eleven policy and integrity checks |
| `passed` | checks whose assertions passed |
| `failed` | checks whose assertions failed |
| `holds` | policy checks with `hold` severity |
| `blocking` | integrity or boundary checks with `blocking` severity |

Filters can be combined:

- `passed=true` or `passed=false`;
- `severity=hold` or `severity=blocking`;
- one declared `check_id`;
- case-insensitive text matching against the public record;
- bounded `offset` and `limit` pagination.

Each result preserves the gate address, the exact query object, total and
returned counts, public records, and a deterministic query content address.
Rehydrating the result from its JSON projection reproduces that address.

## Python

```python
from glio_noncode import (
    AssuranceHistoryObservatoryArchiveRegistryHistoryReleaseGateQuery,
    evaluate_assurance_history_observatory_archive_registry_history_release_gate_from_directory,
    query_assurance_history_observatory_archive_registry_history_release_gate,
)

gate = evaluate_assurance_history_observatory_archive_registry_history_release_gate_from_directory(
    "./review-output/history"
)
request = AssuranceHistoryObservatoryArchiveRegistryHistoryReleaseGateQuery(
    resource="failed", passed=False, limit=25
)
page = query_assurance_history_observatory_archive_registry_history_release_gate(gate, request)
print(page.total_count, page.content_address)
```

## CLI

```powershell
python -m glio_noncode <history-command>-release-gate-query `
  --input .\review-output\history `
  --resource failed `
  --failed `
  --limit 25 `
  --format markdown

python -m glio_noncode <history-command>-release-gate-query-schema
python -m glio_noncode <history-command>-release-gate-query-result-schema
python -m glio_noncode <history-command>-release-gate-query-capabilities
```

The query command uses the default release policy and returns the same exit
status as its gate: `0` for `ready`, `2` for a valid `held` or `blocked`
decision. The result body is still emitted for inspection in the latter cases.

## HTTP

```text
GET /v1/.../history/release-gate/query?input=./review-output/history&resource=failed&passed=false
GET /v1/.../history/release-gate/query-schema
GET /v1/.../history/release-gate/query-result-schema
GET /v1/.../history/release-gate/query-capabilities
```

The route supports JSON, CSV, and Markdown output. It keeps filesystem paths
in the request only; returned records contain public content addresses and no
source paths or private metadata.

## Downloaded-data demo

```powershell
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_query_demo.py `
  --input .\review-output\history `
  --resource passed `
  --check-id content-address `
  --format json
```

For the downloaded two-snapshot history, this returns one passing
`content-address` record and a stable query address.
