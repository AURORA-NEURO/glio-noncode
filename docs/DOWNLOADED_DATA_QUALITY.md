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

The history can also be transferred as an exact six-file runtime package:
`manifest.json`, `history.json`, `audit.json`, `query.json`,
`query-audit.json`, and `runtime.json`. The runtime audit has nineteen checks,
replays manifest component addresses, verifies the latest decision projection,
and distinguishes structural acceptance from latest release readiness. A
blocked latest snapshot can therefore produce `accepted: true`,
`release_ready: false`, and `state: complete` when the history handoff itself
is intact.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-history-runtime `
  history.json --destination history-runtime --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-history-runtime-audit `
  history-runtime --format summary
```

For blocked or reviewable gates, a value-free remediation plan turns every
finding into an evidence-linked next action (`repair`, `investigate`,
`policy_review`, or `data_review`) with bounded priority and requiredness.
It never mutates the input gate or changes policy; it is safe to hand to a
review queue or downstream workflow.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation `
  gate.json --format markdown --output remediation.md
```

The API equivalent is `/v1/downloaded-data/quality/diff/gate/remediation`,
with action and plan schemas available through the quality schema discovery
surface.

For operational handoff, the remediation plan also supports an exact
six-file runtime package containing the plan, independent plan audit, bounded
query, query audit, manifest, and runtime projection. The runtime preserves
the gate lineage and distinguishes an intact but blocked plan from a release-
ready one.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-runtime `
  gate.json --destination remediation-runtime --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-runtime-audit `
  remediation-runtime --format summary
```

The plan has independent action and query audits. The query exposes summary,
all-action, required, blocked, review, and critical projections with bounded
identity, reason, outcome, priority, and text filters. The exact six-file
runtime handoff (`manifest.json`, `plan.json`, `audit.json`, `query.json`,
`query-audit.json`, and `runtime.json`) preserves the gate lineage, action
counters, audit receipts, and query completeness. A structurally complete
blocked plan is accepted as a valid handoff but remains `release_ready: false`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-audit `
  remediation.json --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-query `
  remediation.json --resource required --required-only --priority critical `
  --limit 25 --format markdown
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-runtime `
  gate.json --resource summary --resource blocked --limit 100 `
  --destination remediation-runtime --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-runtime-audit `
  remediation-runtime --format summary
```

The runtime and audit routes are nested under
`/v1/downloaded-data/quality/diff/gate/remediation/runtime`; manifest, runtime,
and runtime-audit schemas and capabilities are available through the same
quality schema discovery surface.

The next handoff records dispositions for the plan without executing repairs
or changing the gate. Every action receives a bounded status (`pending`,
`resolved`, `waived`, `rejected`, or `not_applicable`), rationale, and evidence
addresses. Required actions stay open until explicitly resolved; a waiver is
visible and does not count as a release-ready repair.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution `
  remediation.json --format markdown --output remediation-resolution.md
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-audit `
  remediation-resolution.json --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-query `
  remediation-resolution.json --resource pending --resource open --limit 100 `
  --format markdown
```

For a durable handoff, the resolution ledger has its own exact six-file
runtime package (`manifest.json`, `resolution.json`, `audit.json`, `query.json`,
`query-audit.json`, and `runtime.json`). Its structural runtime state can be
complete while release readiness remains false when required actions are still
pending, waived, or rejected.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-runtime `
  remediation-resolution.json --resource summary --resource pending --resource open `
  --limit 1000 --destination remediation-resolution-runtime --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-runtime-audit `
  remediation-resolution-runtime --format summary
```

The API equivalents are nested under
`/v1/downloaded-data/quality/diff/gate/remediation/resolution`, including
`/audit`, `/query`, `/query-audit`, `/runtime`, and `/runtime/audit`; all
schemas and capabilities are published through the quality discovery surface.

Resolution snapshots can also be retained as an append-only trend history.
The history compares required-open counts and state ranks to classify each
snapshot as `initial`, `improved`, `regressed`, or `unchanged`. A promoted
history describes the recorded remediation dispositions only; it never
overrides the source quality gate decision.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history `
  remediation-resolution.json --format markdown --output resolution-history.md
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-audit `
  resolution-history.json --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-query `
  resolution-history.json --resource entries --resource improved --resource latest `
  --limit 100 --format markdown
```

The history runtime is an exact six-file package with canonical reload,
ancestry, query-completeness, and tamper checks. Its API routes are nested
under `/v1/downloaded-data/quality/diff/gate/remediation/resolution/history`.

To measure a handoff between two recorded histories, the history-diff layer
aligns snapshots by ordinal and reports added, removed, changed, and unchanged
resolution snapshots. It also computes the change in improved and regressed
transitions, the state transition, release-readiness direction, and a bounded
query over the comparison. This is a value-free comparison: it carries
resolution metadata and content addresses, never source payloads or secrets.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff `
  history-comparison.json --format markdown --output resolution-history-diff.md
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-audit `
  resolution-history-diff.json --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-query `
  resolution-history-diff.json --resource summary --resource items --change changed `
  --limit 100 --format markdown
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-runtime `
  resolution-history-diff.json --resource summary --resource items --limit 1000 `
  --destination resolution-history-diff-runtime --overwrite --format summary
```

The API equivalents are nested under
`/v1/downloaded-data/quality/diff/gate/remediation/resolution/history/diff`,
with `/audit`, `/query`, `/query-audit`, `/runtime`, and `/runtime/audit`
subroutes. Schema and capability discovery exposes the same comparison
contract, including its bounded item and audit limits.

The history-diff policy layer turns that measured comparison into an explicit
bounded disposition. Ten replayable rules cover allowed direction, candidate
readiness, added/removed/changed limits, improvement and regression deltas,
entry conservation, state progression, and the public boundary. The result is
`promote`/`eligible`, `hold`/`review`, or `block`/`blocked`; it does not rewrite
the source gate or claim that unresolved remediation is complete.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy `
  resolution-history-diff.json --allow-direction improved --max-added 1 `
  --max-removed 0 --max-changed 0 --max-improved-delta 1 --max-regressed-delta 0 `
  --require-candidate-ready --require-state-progression --format markdown `
  --output resolution-history-diff-policy.md
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-audit `
  resolution-history-diff-policy.json --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-query `
  resolution-history-diff-policy.json --resource summary --resource rules `
  --passed true --limit 100 --format markdown
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-runtime `
  resolution-history-diff.json --allow-direction improved --max-added 1 `
  --max-removed 0 --max-changed 0 --max-improved-delta 1 --max-regressed-delta 0 `
  --require-candidate-ready --require-state-progression --resource summary `
  --resource rules --limit 100 --destination resolution-history-diff-policy-runtime `
  --overwrite --format summary
```

The policy API routes are nested under
`/v1/downloaded-data/quality/diff/gate/remediation/resolution/history/diff/policy`,
with `/audit`, `/query`, `/query-audit`, `/runtime`, and `/runtime/audit`
subroutes. The policy runtime is an exact eight-file package containing the
diff, policy, evaluation, source diff audit, query, query audit, manifest, and
runtime receipt; its runtime audit requires all component links and readiness
aggregates to replay.

For transport or review handoff, seal the policy runtime into a portable
five-file package. The package carries the runtime, policy-evaluation audit,
runtime closure audit, a value-free summary, and a manifest that conserves all
artifact addresses. Package queries expose the summary, policy-audit checks,
policy rules, runtime closure checks, and the underlying history-diff checks.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package `
  resolution-history-diff-policy-runtime --package-id review-package `
  --destination resolution-history-diff-policy-package --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-audit `
  resolution-history-diff-policy-package --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-query `
  resolution-history-diff-policy-package --resource summary --resource policy-audit `
  --resource runtime-checks --limit 100 --format json --output package-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-query-audit `
  package-query.json --format summary
```

The package API routes append `/package`, `/package/audit`, `/package/query`,
and `/package/query-audit` to the policy route. Package discovery publishes
manifest, summary, package, audit, query, and query-audit schemas and
capabilities.

When several independent policy handoffs must be admitted together, register
the portable packages in a deterministic registry. Registry admission is
identity-safe: package IDs and package addresses must be unique, entries are
ordered canonically, and the registry remains `ready` only when every package
is accepted and release-ready. `review`, `blocked`, and `empty` states remain
explicit, so a registry cannot hide a failed package behind a successful
neighbor. The registry is an exact four-file package containing
`manifest.json`, `registry.json`, `entries.json`, and `summary.json`; it stores
public package receipts and never imports source paths or source records.

Registry queries provide the summary, ordered entries, release-ready entries,
and decision projections, with package, decision, state, acceptance, release
readiness, text, and pagination filters. A separate 15-check registry audit
replays identity uniqueness, counts, ordering, nested package addresses, and
the exact file boundary. A separate 10-check query audit replays filters,
pagination, row addresses, resource semantics, and the public boundary.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry `
  resolution-history-diff-policy-package-a resolution-history-diff-policy-package-b `
  --registry-id review-registry --destination policy-package-registry --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-audit `
  policy-package-registry --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-query `
  policy-package-registry --resource summary --resource entries --resource ready --resource decisions `
  --release-ready true --limit 100 --format json --output registry-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-query-audit `
  registry-query.json --format summary
```

The registry API routes append `/package/registry`, `/package/registry/audit`,
`/package/registry/query`, and `/package/registry/query-audit` to the policy
route. Repeat the `input` query parameter for each package when building a
registry. Registry discovery publishes manifest, entry, summary, registry,
audit, query, and query-audit schemas and capabilities.

For longitudinal review, append registry snapshots to a registry history. The
history accepts only one logical registry identity, rejects repeated snapshot
addresses, links each snapshot to the previous address, and folds the latest
snapshot into the current disposition. Transitions are deterministic:
`initial`, `improved`, `regressed`, `unchanged`, or `changed`. It is an exact
four-file package containing `manifest.json`, `history.json`, `entries.json`,
and `summary.json`. The history audit independently checks ancestry, transition
replay, latest linkage, disposition folding, address uniqueness, manifest
closure, and public-boundary integrity.

History queries expose summary, entries, release-ready snapshots, decisions,
and transitions with registry, state, decision, acceptance, readiness,
transition, text, and pagination filters. A separate 10-check query audit
replays ordering, filters, counts, row addresses, row semantics, and the
value-free boundary.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history `
  policy-package-registry-baseline policy-package-registry-candidate `
  --history-id review-registry-history --destination policy-package-registry-history `
  --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-audit `
  policy-package-registry-history --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-query `
  policy-package-registry-history --resource summary --resource entries --resource ready `
  --resource decisions --resource transitions --transition improved --limit 100 `
  --format json --output registry-history-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-query-audit `
  registry-history-query.json --format summary
```

The history API routes append `/package/registry/history`, `/package/registry/history/audit`,
`/package/registry/history/query`, and `/package/registry/history/query-audit`
to the policy route. Repeat `input` for each registry snapshot. History
discovery publishes entry, entries, manifest, summary, history, audit, query,
and query-audit schemas and capabilities.

Two histories with the same logical registry identity can also be compared as
a value-free diff. The comparison classifies snapshot ordinals as `added`,
`removed`, `changed`, or `unchanged`, replays signed transition deltas, and
folds a deterministic `improved`, `regressed`, `mixed`, or `unchanged`
direction plus a state transition. Its exact four-file handoff contains
`manifest.json`, `diff.json`, `items.json`, and `summary.json`. The diff has an
independent 14-check audit and a 10-check query audit.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff `
  policy-package-registry-history-baseline policy-package-registry-history-candidate `
  --diff-id review-registry-history-diff --destination policy-package-registry-history-diff `
  --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-audit `
  policy-package-registry-history-diff --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-query `
  policy-package-registry-history-diff --resource summary --resource items --resource added `
  --change added --limit 100 --format json --output registry-history-diff-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-query-audit `
  registry-history-diff-query.json --format summary
```

The diff API routes append `/package/registry/history/diff`, `/diff/audit`,
`/diff/query`, and `/diff/query-audit` to the policy route. Diff discovery
publishes item, items, manifest, summary, diff, audit, query, and query-audit
schemas and capabilities.

For reusable execution handoff, seal a registry-history diff into a runtime.
The runtime composes the diff, its independent audit, bounded query, and query
audit into an exact six-file package: `manifest.json`, `diff.json`,
`audit.json`, `query.json`, `query-audit.json`, and `runtime.json`. It folds
component acceptance into `complete` or `incomplete` state and only reports
`release_ready` for accepted `improved` or `unchanged` comparisons. A separate
15-check runtime audit replays manifest closure, component linkage, aggregate
counts, readiness, addresses, and the public boundary.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime `
  policy-package-registry-history-diff --runtime-id review-registry-history-diff-runtime `
  --resource summary --resource items --resource added --limit 100 `
  --destination policy-package-registry-history-diff-runtime --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-audit `
  policy-package-registry-history-diff-runtime --format summary
```

The runtime API routes append `/package/registry/history/diff/runtime` and
`/runtime/audit` to the diff route. Runtime discovery publishes manifest,
runtime, audit, and capability contracts.

To admit multiple runtime packages as one deterministic unit, build a runtime
registry. It accepts only typed six-file runtime packages, sorts entries by
runtime identity and address, rejects duplicate identities, folds `empty`,
`ready`, and `blocked` states, and preserves the runtime's public addresses
without copying source data. The registry itself is an exact four-file package:
`manifest.json`, `registry.json`, `entries.json`, and `summary.json`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry `
  policy-package-registry-history-diff-runtime-a policy-package-registry-history-diff-runtime-b `
  --registry-id review-runtime-registry --destination policy-runtime-registry `
  --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-audit `
  policy-runtime-registry --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-query `
  policy-runtime-registry --resource summary --resource entries --resource runtimes `
  --resource states --resource readiness --resource addresses --resource bounds `
  --limit 100 --format json --output runtime-registry-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-query-audit `
  policy-runtime-registry --format summary
```

The runtime-registry API routes append `/runtime-registry`,
`/runtime-registry/audit`, `/runtime-registry/query`, and
`/runtime-registry/query-audit` to the history-diff route. Registry discovery
publishes entry, entries, manifest, summary, registry, audit, query, and
query-audit schemas and capabilities. The registry audit independently
replays all runtime links, entry ordering, state/count conservation, manifest
closure, and the public boundary; the query audit replays filters,
pagination, row addresses, resource semantics, and registry linkage.

For longitudinal tracking above runtime-registry snapshots, build append-only
runtime-registry history. Every snapshot must use one registry identity;
entries preserve the admitted registry address and aggregate counts, reject
duplicate addresses, and record deterministic `initial`, `improved`,
`regressed`, `unchanged`, or `changed` transitions. The latest snapshot folds
the history state and acceptance without exposing source paths, records, or
payload bytes. Persistence is an exact four-file package:
`manifest.json`, `history.json`, `entries.json`, and `summary.json`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history `
  policy-runtime-registry policy-runtime-registry --history-id review-runtime-registry-history `
  --destination policy-runtime-registry-history --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-audit `
  policy-runtime-registry-history --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-query `
  policy-runtime-registry-history --resource summary --resource snapshots --resource transitions `
  --resource states --resource readiness --resource addresses --resource bounds `
  --limit 100 --format json --output runtime-registry-history-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-query-audit `
  policy-runtime-registry-history --format summary
```

The history API routes append `/runtime-registry/history`,
`/runtime-registry/history/audit`, `/runtime-registry/history/query`, and
`/runtime-registry/history/query-audit` to the history-diff route. History
discovery publishes entry, entries, manifest, summary, history, audit, query,
and query-audit schemas and capabilities. The independent history audit has
16 checks; the query audit has 12 checks and replays resource selection,
filters, pagination, row addresses, and history linkage. Empty-to-ready real
downloaded-ZIP evidence is represented as an initial-to-improved transition.

Compare two runtime-registry histories with the history-diff surface. The
comparison is value-free and requires one history identity; it aligns snapshot
ordinals, preserves both addressed histories, emits signed count deltas, and
folds item changes into `improved`, `regressed`, `mixed`, or `unchanged`.
Added, removed, changed, and unchanged items retain their left/right snapshot
addresses and changed fields. Persistence is an exact four-file package:
`manifest.json`, `diff.json`, `items.json`, and `summary.json`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff `
  baseline-runtime-registry-history candidate-runtime-registry-history `
  --diff-id review-runtime-registry-history-diff --destination runtime-registry-history-diff `
  --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-audit `
  runtime-registry-history-diff --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-query `
  runtime-registry-history-diff --resource summary --resource items --resource added `
  --resource removed --resource changed --resource unchanged --resource addresses `
  --resource bounds --limit 100 --format json --output runtime-registry-history-diff-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-query-audit `
  runtime-registry-history-diff-query.json --format summary
```

The history-diff API routes append `/runtime-registry/history/diff`,
`/runtime-registry/history/diff/audit`, `/runtime-registry/history/diff/query`,
and `/runtime-registry/history/diff/query-audit`. Discovery publishes item,
items, manifest, summary, diff, audit, query, and query-audit schemas and
capabilities. The independent diff audit has 14 checks; the query audit has
10 checks and replays item membership, change filters, pagination, row
addresses, and diff linkage. The real downloaded-ZIP demonstration compares an
empty baseline to a ready candidate and records an improved transition.

For direct baseline/candidate comparison above runtime-registry histories, use
the runtime-registry history diff. Both histories must carry the same registry
identity. Snapshots are aligned by ordinal and classified as `added`,
`removed`, `changed`, or `unchanged`; changed snapshots retain field-level
evidence and the diff folds the result into `improved`, `regressed`, `changed`,
or `unchanged` direction plus an explicit state transition. The public model
contains no source paths or payload values. Persistence is an exact four-file
package: `manifest.json`, `diff.json`, `items.json`, and `summary.json`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff `
  baseline-runtime-registry-history candidate-runtime-registry-history `
  --diff-id review-runtime-registry-history-diff `
  --destination runtime-registry-history-diff --overwrite --format json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-audit `
  runtime-registry-history-diff --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-query `
  runtime-registry-history-diff --resource summary --resource items --resource added `
  --resource removed --resource changed --resource unchanged --resource addresses `
  --resource bounds --limit 100 --format json --output runtime-registry-history-diff-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-query-audit `
  runtime-registry-history-diff-query.json runtime-registry-history-diff --format summary
```

The diff API routes append `/runtime-registry/history/diff`,
`/runtime-registry/history/diff/audit`, `/runtime-registry/history/diff/query`,
and `/runtime-registry/history/diff/query-audit` to the history-diff route.
Discovery publishes item, items, manifest, summary, diff, audit, query, and
query-audit schemas and capabilities. The independent diff audit has 16
checks; the query audit has 13 checks and replays resource selection, change
filters, pagination, row addresses, and diff linkage. Real downloaded-ZIP
evidence compares an empty registry snapshot with an admitted runtime-registry
snapshot and reports one added plus one unchanged snapshot with improved
direction.
