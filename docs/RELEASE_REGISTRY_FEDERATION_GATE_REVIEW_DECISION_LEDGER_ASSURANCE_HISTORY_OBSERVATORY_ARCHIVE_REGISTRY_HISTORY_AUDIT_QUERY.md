# Assurance history observatory archive registry history audit query

The history-audit query boundary provides bounded, read-only inspection over a
thirteen-check registry-history audit. It preserves the audit decision and
does not expose source paths, mutable state, private attribution, ownership,
or language metadata. Every result page contains the source audit address, a
normalized query, a bounded record window, and a deterministic query address.

## Resources and filters

- `summary` — one aggregate audit summary;
- `checks` — all thirteen check records;
- `passed` — only checks with `passed=true`;
- `failed` — only checks with `passed=false`;
- `evidence` — check IDs, pass state, evidence addresses, and check addresses.

All resources support `check_id`, case-insensitive public `text`, `offset`, and
`limit`. The `passed` filter can further restrict checks and evidence. The
default page is 50 records, the maximum page is 256, and the maximum offset is
2,048.

## Python

```python
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit_query as query

value = history.load_history("./review-output/history")
report = audit.audit_history(value)
result = query.query_audit(report, resource="evidence", check_id="content-address")
print(result.to_dict())
```

Use `query.query_result_from_mapping` and `query.address_query` to rehydrate
and verify a public result page. Query objects and keyword filters are
mutually exclusive, keeping the recorded query unambiguous.

## CLI

Inspect evidence for the content-address check:

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-audit-query \
  --input ./review-output/history \
  --resource evidence \
  --check-id content-address \
  --passed \
  --format markdown
```

The schema commands are `-query-schema`, `-query-result-schema`, and
`-query-capabilities` on the history-audit command. An incomplete source audit
still returns its bounded records and uses exit code `2` to preserve the
underlying audit decision.

## HTTP

The query route is the `query` child of the history-audit route:

```text
/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/audit/query
```

Supply `input` or `history`, `resource`, and optional `passed`, `check_id`,
`q` or `text`, `offset`, `limit`, and `format=json|csv|markdown`. The child
routes `/query-schema`, `/query-result-schema`, and `/query-capabilities`
describe the contract.

## Downloaded-data demonstration

After creating a history from downloaded registry data, run:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit_query_demo.py \
  --input "$TEMP/glio-noncode-history-audit-demo/history" \
  --resource passed \
  --check-id content-address \
  --format json
```

The verified self-history produces one passing `content-address` record and a
replayable query content address.
