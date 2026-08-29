# Assurance history observatory archive registry history audit

The registry-history audit boundary independently checks an ordered history
document. It is intentionally separate from the strict typed history loader:
valid histories produce a complete accepted report, while malformed public
mappings produce an addressable incomplete report with every fixed check
preserved for diagnosis.

The audit never adds source paths, timestamps, private attribution, ownership,
or language metadata to its public output.

## Checks

Every report contains the same thirteen checks in this order:

1. `exact-fields` — the history mapping has exactly the declared public fields.
2. `public-boundary` — no private or attribution metadata is present.
3. `source-addresses` — registry, verification, and diff addresses use public
   namespaces.
4. `snapshot-identities` — snapshot ordinals and snapshot addresses are
   ordered and unique.
5. `transition-identities` — transition ordinals and diff addresses are
   ordered and unique.
6. `adjacency` — each transition joins neighboring snapshots and the sequence
   has one fewer transition than snapshots.
7. `endpoint-linkage` — history endpoints and transition endpoints link to
   their snapshots.
8. `state-conservation` — state counts equal the transition sequence.
9. `count-conservation` — every transition's action counts equal its item
   count.
10. `registry-field-order` — aggregate changed fields use the canonical order.
11. `nested-addresses` — snapshot and transition addresses replay.
12. `content-address` — the history address replays from its public projection.
13. `mapping-round-trip` — the typed public mapping rehydrates without drift.

The report state is `complete` only when all checks pass. `accepted` follows
the report state; failed audits remain useful but are not accepted release
inputs.

## Python

Audit a typed history:

```python
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit as audit

value = history.load_history("./review-output/history")
report = audit.audit_history(value)
print(report.summary())
```

To preserve diagnostics from an untrusted public mapping, use
`audit.audit_from_mapping(mapping)`. It does not require the mapping to be
valid before producing the fixed check report.

## CLI

Audit an exact four-file history directory:

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-audit \
  --input ./review-output/history \
  --format markdown
```

The sibling commands `-schema`, `-check-schema`, and `-capabilities` expose
the report schema, check schema, and fixed audit contract. A complete audit
returns exit code `0`; an incomplete audit returns exit code `2` while still
printing the report.

## HTTP

The audit route is the `audit` child of the registry-history route:

```text
/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/audit
```

Supply `input` or `history` with an exact four-file history directory and
optional `format=json|markdown`. The `/schema`, `/check-schema`, and
`/capabilities` child routes describe the public contract.

## Downloaded-data demonstration

After building a history from downloaded registry packages, run:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit_demo.py \
  --input "$TEMP/glio-noncode-history-demo/history" \
  --format summary
```

For a verified two-snapshot self-history, all thirteen checks pass and the
report is content-addressed. The demo also supports `--mapping` to audit a
public JSON history mapping directly, retaining an incomplete report when the
mapping contains unknown or forged fields.
