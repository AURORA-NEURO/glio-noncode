# Assurance-history observatory verification-query contract

This contract describes the bounded verification-check view for a persisted
cross-run assurance-history observatory. It is an operator surface for
answering questions such as:

- Did the package's independent checks pass?
- Which required check failed?
- Are warnings present while blockers are absent?
- Which check detail, expected value, or observed value matches a search term?
- Which bounded window should be exported for review?

The query is evaluated only after the exact observatory package has been
loaded. Loading verifies the five-file package, canonical JSON bytes, manifest
receipts, member linkage, metrics, and the independently recomputed
verification. A query never turns malformed or unverified input into a valid
result.

## Public result

The result is a typed, content-addressed value with these fields:

| Field | Meaning |
| --- | --- |
| `verification_address` | Address of the verification being queried. |
| `query` | The normalized resource, filters, offset, and limit. |
| `total_count` | Number of matching records before pagination. |
| `returned_count` | Number of records in the selected window. |
| `records` | Verification summary or check projections. |
| `content_address` | Address of the exact filtered result. |

The query result is path-free. Source directories are process-boundary inputs
and are never serialized into the verification, query, or report.

## Resource vocabulary

| Resource | Record type | Selection rule |
| --- | --- | --- |
| `summary` | one verification summary | Always returns one summary record. |
| `checks` | check | All checks after optional filters. |
| `failed` | check | Only checks with `passed == false`. |
| `required` | check | Only checks with `severity == required`. |
| `optional` | check | Only checks with `severity == optional`. |

Resources are exact values. An unknown resource is a contract error and does
not produce an empty response. Empty matches are valid and return
`total_count: 0`, `returned_count: 0`, and an addressable empty window.

## Filters

Filters are applied before pagination and are deterministic:

| Filter | Values | Behavior |
| --- | --- | --- |
| `severity` | `required`, `optional` | Limits checks by severity. |
| `passed` | boolean | Limits checks by pass state. |
| `text` | bounded string | Case-insensitive search over canonical check text. |
| `offset` | 0 through 4096 | Skips matching records. |
| `limit` | 1 through 4096 | Bounds the returned window. |

The implementation applies both a resource predicate and supplied filters.
For example, `resource=required&passed=true` returns only passing required
checks. A query with `resource=failed&passed=true` is valid but returns zero
records because the predicates are contradictory.

The default limit is 50. Limits are deliberately finite even when the source
package has fewer checks. This keeps exports safe if a future version adds
more verification detail or a malformed caller attempts an unbounded window.

## Addressing and reproducibility

The query address is computed from:

1. the verification content address;
2. the normalized typed query;
3. the total and returned counts; and
4. the exact selected records.

The address is computed once with a pending marker removed and then validated
by the typed result constructor. Two equal verification packages and equal
query values therefore produce equal query addresses. Changing any filter,
window, check record, or source verification address changes the result
address.

This address is a receipt for the public projection. It is not a replacement
for the verification address or the upstream history addresses.

## Python API

The canonical module is:

```text
glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory
```

Example:

```python
from glio_noncode import (
    load_assurance_history_observatory_verification,
    query_assurance_history_observatory_verification,
)

verification = load_assurance_history_observatory_verification(
    "review-output/observatory"
)
failed = query_assurance_history_observatory_verification(
    verification,
    resource="failed",
    limit=100,
)
```

The typed class can be used when a query is composed before execution:

```python
from glio_noncode import VerificationQuery

query = VerificationQuery(
    resource="checks",
    severity="required",
    passed=True,
    text="address",
    offset=0,
    limit=25,
)
result = query_assurance_history_observatory_verification(
    verification,
    query=query,
)
```

The result can be rendered as canonical JSON, fixed-column CSV, or Markdown:

```python
from glio_noncode import (
    assurance_history_observatory_verification_query_csv,
    assurance_history_observatory_verification_query_json,
    render_assurance_history_observatory_verification_query_markdown,
)

json_text = assurance_history_observatory_verification_query_json(result)
csv_text = assurance_history_observatory_verification_query_csv(result)
markdown_text = render_assurance_history_observatory_verification_query_markdown(result)
```

All three renderers select from the same typed result. Formatting does not
change resource selection or pagination.

## CLI

The long-form command is the observatory command with
`-verification-query` appended. The package input is verified before querying:

```text
python -c "from glio_noncode.cli import main; raise SystemExit(main([
  '<observatory-command>-verification-query',
  '--input', 'review-output/observatory',
  '--resource', 'failed',
  '--format', 'markdown'
]))"
```

Required passing checks in a bounded window:

```text
<observatory-command>-verification-query \
  --input review-output/observatory \
  --resource checks \
  --severity required \
  --passed \
  --offset 0 \
  --limit 50 \
  --format json
```

The standalone demonstration is:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_verification_query_demo.py \
  --input review-output/observatory \
  --resource checks \
  --severity required \
  --passed \
  --format markdown
```

The demonstration returns status zero for a valid query, including a valid
empty result. Input, package, and contract errors return status one.

## HTTP

The HTTP route is nested below the observatory route:

```text
.../decision-ledger/assurance-history/observatory/verification/query
```

Example query:

```text
GET /.../observatory/verification/query?input=review-output/observatory&resource=failed&limit=50
```

The schema is available at:

```text
GET /.../observatory/verification/query-schema
```

The equivalent top-level observatory schema route is:

```text
GET /.../observatory/verification-query-schema
```

`format=json` is the default. `format=csv` returns `text/csv` and
`format=markdown` returns `text/markdown`. Query success is `200`, including
valid empty windows. Bad paths, malformed packages, unknown resources, and
invalid windows are client errors.

## Failure behavior

| Failure | Result |
| --- | --- |
| Unknown resource | `ValidationError` / client error. |
| Severity outside enum | `ValidationError` / client error. |
| Zero or negative limit | `ValidationError` / client error. |
| Offset above bound | `ValidationError` / client error. |
| Plain mapping in place of typed verification | `ValidationError`. |
| Tampered verification package | Package loader rejects before query. |
| Non-canonical package bytes | Package loader rejects before query. |
| Extra package file or symlink | Exact-file loader rejects before query. |
| No matching checks | Addressed empty result, not an error. |

## Review procedure

1. Verify or load the exact observatory package.
2. Query `summary` to capture the verification address and gate state.
3. Query `failed` to identify blockers and optional warnings.
4. Query `required` with `passed=true` to confirm the successful required set.
5. Export only the bounded records needed for the review packet.
6. Preserve the query content address alongside the verification address.
7. Return to the source observatory and upstream history package for any
   domain interpretation.

The query reports contract posture. It does not infer scientific validity,
clinical meaning, or safety from a passing check.

## Coverage

The focused suite covers every resource, severity and pass filter, canonical
text matching, pagination, typed validation, query addressing, JSON/CSV/
Markdown rendering, CLI schema and execution, HTTP schema and execution, and
current downloaded-data execution. Public-surface inventory includes the
verification-query schema and the root package exports.
