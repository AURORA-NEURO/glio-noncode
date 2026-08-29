# Assurance history observatory archive registry history query

The registry-history query boundary provides bounded, read-only inspection of
an exact four-file history package. It does not rebuild source registries,
change the history acceptance decision, or expose input paths and private
metadata. Every typed result records the source history address, normalized
query, bounded page, and deterministic query content address.

## Resources

- `summary` — one aggregate history summary record;
- `snapshots` — all ordered snapshot projections;
- `transitions` — all adjacent transition projections;
- `state-changes` — transitions whose state is not `unchanged`;
- `accepted` — snapshots with `accepted=true`;
- `release-ready` — snapshots with `release_ready=true`.

The `state` filter accepts both registry snapshot states (`empty`, `ready`,
`held`, `blocked`, `mixed`) and transition states (`unchanged`, `improved`,
`regressed`, `mixed`). `accepted`, `release_ready`, `ordinal`, and
case-insensitive public `text` filters can be combined with any resource. The
default page is 50 records, the maximum page is 256 records, and the maximum
offset is 2,048.

## Python

```python
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_query as query

value = history.load_history("./review-output/history")
result = query.query_history(value, resource="transitions", state="unchanged")
print(result.to_dict())
```

Use `query.query_result_from_mapping` and `query.address_query` to replay and
verify a public result page. Query objects and keyword filters are mutually
exclusive, so the normalized query included in the result is unambiguous.

## CLI

Inspect accepted snapshots in ordinal order:

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-query \
  --input ./review-output/history \
  --resource snapshots \
  --state ready \
  --accepted \
  --format markdown
```

The schema commands are `-query-schema`, `-query-result-schema`, and
`-query-capabilities` on the history command. Output can be JSON, CSV, or
Markdown. Pagination and all filters are validated before a page is produced.

## HTTP

The query route is the `query` child of the registry-history route:

```text
/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/query
```

Supply `input` or `history`, `resource`, and optional `state`, `accepted`,
`release_ready`, `ordinal`, `q` or `text`, `offset`, `limit`, and
`format=json|csv|markdown`. The child routes `/query-schema`,
`/query-result-schema`, and `/query-capabilities` expose the contract.

## Downloaded-data demonstration

The standalone demo can inspect the history package created from the real
downloaded registry demonstration:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_query_demo.py \
  --input "$TEMP/glio-noncode-history-audit-demo/history" \
  --resource transitions \
  --state unchanged \
  --format markdown
```

For the two-snapshot self-history, the result contains one unchanged
transition and a deterministic query content address.
