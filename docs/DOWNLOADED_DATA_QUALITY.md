# Downloaded Data Quality

The downloaded-data quality boundary converts a structural profile into an
explicit, content-addressed decision. It is a structural gate, not a
scientific interpretation layer: it can say that a source satisfies declared
record, field, type, missingness, cardinality, and serialized-size constraints,
but it cannot say that the source is biologically correct.

## Pipeline

```text
ZIP -> catalog -> bounded ingestion -> value-free profile -> quality policy
                                                        -> findings
                                                        -> independent audit
                                                        -> bounded query
```

`downloaded_data_quality.py` provides `build_policy` and `build_quality`.
Policies are reusable and contain only bounded structural thresholds. A quality
result retains the profile address and the policy itself. Every finding records
its rule, scope, target, measured value, limit, detail, and evidence addresses.

The decision state is one of:

- `accepted`: all generated checks passed;
- `review`: at least one check failed and the policy requested review; or
- `blocked`: at least one check failed and the policy requested blocking.

Empty `allowed_value_types` means that the policy does not constrain field value
types. Ratios are represented as parts per million to avoid floating-point
policy drift. Missingness is measured against profile record count; nullness is
measured against observations of the field. A profile whose distinct-value
estimate was truncated fails a bounded distinct-value check, because the exact
cardinality is not known at that boundary.

## Independent verification

`downloaded_data_quality_audit.py` recomputes eighteen checks over the typed
result, including exact field shape, current version, policy and profile
linkage, content-address replay, finding ordinals, rule/scope/target shape,
decision state, and evidence retention.

`downloaded_data_quality_query.py` exposes two deterministic resources:
`summary` and `findings`. Queries support rule, scope, severity, text, offset,
and limit filters. `downloaded_data_quality_query_audit.py` independently
verifies twelve query checks, including filter shape and pagination.

`downloaded_data_quality_runtime.py` joins the policy, result, audits, and
query into a seven-file atomic runtime. `persist_runtime` writes a canonical
manifest and the five linked artifacts; `load_runtime` requires the exact file
set, replays every nested address, and rejects edits to any artifact.

The boundary rejects unknown fields, coercive numeric values, duplicate policy
names, non-finite source statistics inherited from a profile, unbounded text,
and public-surface fields that would identify private execution machinery.

## Real downloaded ZIP demonstration

Run:

```powershell
python examples/downloaded_data_quality_demo.py `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  artifacts/downloaded-data-quality-demo
```

The demo selects data-bearing catalog members, reuses the bounded ingestion
runtime, builds a value-free profile, evaluates a review policy, writes JSON and
Markdown projections, and reports the quality/audit/query addresses. The
source ZIP is never copied into the emitted quality artifacts.

## CLI and HTTP replay surface

The same typed result can be replayed without reopening the source ZIP. A
profile JSON or the persisted profile runtime is accepted by the focused CLI:

```powershell
python -m glio_noncode downloaded-data-quality artifacts/downloaded-data-profile-demo/profile-runtime --format summary
python -m glio_noncode downloaded-data-quality-runtime artifacts/downloaded-data-profile-demo/profile-runtime --destination artifacts/downloaded-data-quality-demo/quality-runtime --overwrite --format summary
python -m glio_noncode downloaded-data-quality-query artifacts/downloaded-data-quality-demo/quality-runtime --resource findings --severity blocked --limit 25 --format markdown
python -m glio_noncode downloaded-data-quality-runtime-audit artifacts/downloaded-data-quality-demo/quality-runtime --format json
```

The loopback API exposes the corresponding routes under
`/v1/downloaded-data/quality`: the root builds a result, `/audit` verifies a
result, `/query` applies bounded filters, `/query-audit` verifies a query,
`/runtime` builds and optionally persists the exact seven-file handoff, and
`/runtime/audit` verifies the runtime closure. `/schema`, `/capabilities`, and
the nested audit/query/runtime schema routes are available for machine clients.
All routes accept `input`, `policy`, `resource`, filter, pagination, format,
destination, and overwrite query parameters where applicable.

## Longitudinal quality comparison

Quality results can be compared without reopening the source data. The diff
joins findings by the stable `(rule, scope, member, field)` identity, classifies
added, removed, changed, and unchanged checks, and separately marks changed
checks as improved, regressed, or changed. It retains both endpoint quality and
policy addresses, conserves left/right finding totals, and never copies source
values.

```powershell
python -m glio_noncode downloaded-data-quality-diff `
  artifacts/downloaded-data-quality-demo/quality-runtime/quality.json `
  artifacts/downloaded-data-quality-demo/quality-runtime/quality.json `
  --format summary
python -m glio_noncode downloaded-data-quality-diff-runtime `
  artifacts/downloaded-data-quality-demo/quality-runtime/quality.json `
  artifacts/downloaded-data-quality-demo/quality-runtime/quality.json `
  --destination artifacts/downloaded-data-quality-demo/quality-diff-runtime `
  --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-query `
  artifacts/downloaded-data-quality-demo/quality-diff-runtime `
  --resource items --limit 25 --format markdown
python -m glio_noncode downloaded-data-quality-diff-runtime-audit `
  artifacts/downloaded-data-quality-demo/quality-diff-runtime --format summary
```

The comparison API is under `/v1/downloaded-data/quality/diff` with root,
`/audit`, `/query`, `/query-audit`, `/runtime`, and `/runtime/audit` routes.
Nested schema and capability discovery is available for the diff, query,
audits, runtime, and runtime audit. A diff runtime is an exact six-file
handoff: manifest, diff, audit, query, query-audit, and runtime.

## Policy-governed release gate

`downloaded_data_quality_diff_gate.py` turns a longitudinal diff into an
explicit release disposition. The default policy allows unchanged, improved,
changed, added, and removed checks, while treating every regression as a
blocked release. Policies are content-addressed and expose thresholds for
regressions, changed checks, additions, removals, audit receipts, and query
completeness.

The gate produces one bounded finding per diff item and conserves the safe,
review, and blocked counts. Its dispositions are `promote`/`eligible`,
`hold`/`review`, or `block`/`blocked`. The independent gate audit verifies
policy linkage, finding order, threshold replay, audit receipts, nested
addresses, public-boundary compliance, and canonical round-trip behavior.
The gate query exposes summary, findings, safe, review, blocked, allowed, and
disallowed resources with outcome, direction, identity, text, and pagination
filters. Its twelve-check audit verifies the query shape and row conservation.

After generating the real diff above, run the gate demo:

```powershell
python examples/downloaded_data_quality_diff_gate_demo.py `
  artifacts/downloaded-data-quality-diff-demo/diff.json `
  artifacts/downloaded-data-quality-diff-demo/gate
```

On the checked-in real downloaded ZIP, the default gate reports 563 findings,
72 blocked regressions, and decision `block`; the gate audit and blocked-query
audit pass. The same diff is also evaluated with a deliberately permissive
policy to demonstrate the `eligible`/`promote` branch without changing the
default fail-closed result.

The focused CLI commands are:

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate `
  artifacts/downloaded-data-quality-diff-demo/diff.json --format markdown
python -m glio_noncode downloaded-data-quality-diff-gate-audit `
  artifacts/downloaded-data-quality-diff-demo/gate/gate.json --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-query `
  artifacts/downloaded-data-quality-diff-demo/gate/gate.json `
  --resource blocked --outcome blocked --limit 25 --format markdown
python -m glio_noncode downloaded-data-quality-diff-gate-query-audit `
  artifacts/downloaded-data-quality-diff-demo/gate/blocked-query.json --format summary
```

The HTTP routes are nested under
`/v1/downloaded-data/quality/diff/gate`: root, `/audit`, `/query`, and
`/query-audit`, `/runtime`, and `/runtime/audit`, with schema and capability
discovery under the existing `/v1/downloaded-data/schema` surface. The gate
runtime is an exact six-file package: manifest, gate, audit, query,
query-audit, and runtime. Its independent 19-check closure audit distinguishes
a valid blocked release from a corrupt or incomplete handoff. A blocked gate
therefore remains auditable and transferable while correctly reporting
`release_ready: false`.

## Longitudinal gate history

`downloaded_data_quality_diff_gate_history.py` records successive gate runtime
snapshots in an append-only, ancestry-linked history. Each entry retains the
gate/runtime/policy addresses, decision counts, readiness, previous-head
address, and one of `initial`, `improved`, `regressed`, `unchanged`, or
`changed` transitions. Duplicate snapshot IDs and stale expected heads are
rejected. The independent history audit verifies sixteen replay checks.

The history query exposes summary, entries, decision, and transition
resources with deterministic filters and pagination; its independent query
audit verifies twelve shape and address checks. The real demo records a
default-policy `blocked` snapshot followed by a permissive-policy
`eligible`/`promote` snapshot, yielding an `improved` transition while
preserving both decisions.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-history `
  artifacts/downloaded-data-quality-diff-demo/gate/gate-runtime `
  --snapshot-id default-policy --format json --output history.json
python -m glio_noncode downloaded-data-quality-diff-gate-history-audit `
  history.json --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-history-query `
  history.json --resource entries --transition improved --format markdown
python -m glio_noncode downloaded-data-quality-diff-gate-history-query-audit `
  history-query.json --format summary
```
