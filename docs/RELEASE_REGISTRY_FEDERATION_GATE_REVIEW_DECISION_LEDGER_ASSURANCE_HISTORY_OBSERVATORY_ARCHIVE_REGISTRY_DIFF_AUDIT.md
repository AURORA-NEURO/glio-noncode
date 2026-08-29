# Assurance history observatory archive registry diff audit

The registry-diff audit is an independent diagnostic boundary for a public
registry comparison. The strict diff builder accepts only two typed,
verified `ObservatoryArchiveRegistry` values. The audit accepts the resulting
public mapping and evaluates it through a fixed twelve-check contract, so a
damaged or tampered comparison can produce a useful incomplete report rather
than losing every diagnostic behind the first parsing exception.

## Checks

The checks run in stable order:

1. `exact-fields` — the diff has only its declared public fields.
2. `public-boundary` — no private, path, or attribution metadata is present.
3. `source-addresses` — registry and verification addresses use public namespaces.
4. `item-identities` — item ordinals, entry keys, and nested addresses are ordered and unique.
5. `action-sides` — added, removed, changed, and unchanged actions have valid sides.
6. `field-conservation` — changed fields are derived from entry projections.
7. `count-conservation` — action counts equal the item set.
8. `registry-change-fields` — aggregate fields are derived from registry projections.
9. `aggregate-state` — the diff state reflects posture and detected changes.
10. `item-addresses` — each nested item address can be replayed.
11. `content-address` — the top-level diff address can be replayed.
12. `mapping-round-trip` — the public mapping rehydrates without projection drift.

An accepted report is `complete`, has twelve passing checks, and is itself
content-addressed. An incomplete report retains the same stable check set and
uses safe public fallback addresses; it never exposes the input directory.

## CLI

Build and audit two exact five-file registry packages:

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-diff-audit \
  --baseline ./baseline-registry \
  --candidate ./candidate-registry \
  --format markdown
```

The command exits `0` for an accepted audit and `2` for an incomplete audit.
Use the `-schema`, `-check-schema`, and `-capabilities` suffix commands to
inspect the machine-readable contract.

## HTTP

The API exposes the same operation at the registry diff audit route:

```text
/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/diff/audit
```

Supply `baseline`, `candidate`, and optional `format=json|markdown|summary`.
The schema and capability routes are `/schema`, `/check-schema`, and
`/capabilities`.

## Downloaded-data demonstration

The audit can verify a self-diff of the downloaded observatory registry built
by the archive demo:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_audit_demo.py \
  --baseline "$TEMP/glio-noncode-history-observatory-demo-current/registry-v1" \
  --candidate "$TEMP/glio-noncode-history-observatory-demo-current/registry-v1"
```

For identical real registry directories the expected result is one unchanged
item, zero failed checks, and a stable audit content address.
