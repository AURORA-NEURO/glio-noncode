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

For a portable execution handoff above a runtime-registry history diff, build a
runtime package. It seals the diff, its independent audit, its bounded query,
and its query audit into one value-free artifact. The runtime is `complete`
only when both nested audits pass, and it is release-ready only for an accepted
`improved` or `unchanged` direction. Persistence is an exact six-file package:
`manifest.json`, `diff.json`, `audit.json`, `query.json`, `query-audit.json`,
and `runtime.json`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime `
  runtime-registry-history-diff --runtime-id review-runtime-registry-history-diff-runtime `
  --resource summary --resource items --resource added --resource unchanged `
  --resource addresses --resource bounds --limit 100 `
  --destination runtime-registry-history-diff-runtime --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-audit `
  runtime-registry-history-diff-runtime --format summary
```

The runtime API routes append `/runtime-registry/history/diff/runtime` and
`/runtime-registry/history/diff/runtime/audit` to the history-diff route.
Discovery publishes manifest, runtime, and audit schemas and capabilities. The
independent runtime audit has 15 checks covering exact six-file closure,
nested diff/audit/query/query-audit linkage, aggregate replay, readiness
folding, address conservation, public-boundary enforcement, and mapping
round-trip. Real downloaded-ZIP evidence produces a complete, release-ready
runtime over the improved comparison.

For deterministic admission above those portable runtime handoffs, build a
runtime handoff registry. Each entry is derived from one complete runtime,
duplicate runtime identities are rejected, registry readiness folds across
all entries, and the package exposes bounded summary, entry, runtime, state,
readiness, address, and bounds resources. Persistence is an exact four-file
package: `manifest.json`, `registry.json`, `entries.json`, and `summary.json`.

```powershell
python examples/downloaded_data_quality_diff_demo.py `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  artifacts/downloaded-data-quality-diff-demo
python examples/downloaded_data_quality_diff_gate_demo.py `
  artifacts/downloaded-data-quality-diff-demo/diff.json `
  artifacts/downloaded-data-quality-diff-demo/gate
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-audit `
  artifacts/downloaded-data-quality-diff-demo/gate/remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry `
  --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-query `
  artifacts/downloaded-data-quality-diff-demo/gate/remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry `
  --resource summary --resource entries --resource runtimes --resource readiness --resource addresses --limit 100 --format json
```

The registry API routes append `/runtime-registry/history/diff/runtime-registry`,
`/audit`, `/query`, and `/query-audit` to the history-diff route. Discovery
publishes entry, entries, manifest, summary, registry, audit, query, and
query-audit schemas and capabilities. The independent registry audit has 16
checks; its query audit has 12 checks and replays resource ordering, filters,
pagination, row addresses, and registry linkage. The live ZIP demo builds two
complete runtime handoffs, admits both, emits 26 bounded query rows, and
persists the exact four-file registry without source paths, source records,
payload bytes, private metadata, agent attributes, or language attributes.

For append-only admission history above those runtime-handoff registries, build
an empty baseline registry and a ready candidate registry. The history records
the addressed registry snapshots, aggregate counts, ancestry, and deterministic
`initial`/`improved`/`regressed`/`unchanged`/`changed` transitions. Persistence is
an exact four-file package: `manifest.json`, `history.json`, `entries.json`, and
`summary.json`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history `
  empty-runtime-handoff-registry ready-runtime-handoff-registry `
  --history-id runtime-handoff-registry-history --destination runtime-handoff-registry-history `
  --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-audit `
  runtime-handoff-registry-history --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query `
  runtime-handoff-registry-history --resource summary --resource snapshots `
  --resource transitions --resource states --resource readiness --resource addresses `
  --resource bounds --limit 100 --format json --output runtime-handoff-registry-history-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query-audit `
  runtime-handoff-registry-history-query.json runtime-handoff-registry-history --format summary
```

The history API routes append `/runtime-registry/history/diff/runtime-registry/history`,
`/audit`, `/query`, and `/query-audit` to the history-diff route. Discovery
publishes entry, entries, manifest, summary, history, audit, query, and
query-audit schemas and capabilities. The independent history audit has 16
checks; the query audit has 12 checks and replays transition ordering, filters,
pagination, row addresses, and history linkage. The live downloaded ZIP demo
produces a ready two-entry history with `initial` then `improved` transitions,
40 bounded query rows, and the exact four-file history package.

For a release-facing comparison above those runtime-handoff histories, build a
baseline history and a candidate history with the same history identity. The
diff replays each ordinal snapshot, records added/removed/changed/unchanged
evidence, signs aggregate deltas, folds readiness into an `improved`,
`regressed`, `changed`, or `unchanged` direction, and rejects value-private
fields at construction and reload. Persistence is an exact four-file package:
`manifest.json`, `diff.json`, `items.json`, and `summary.json`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff `
  baseline-runtime-handoff-history candidate-runtime-handoff-history `
  --diff-id runtime-handoff-history-diff --destination runtime-handoff-history-diff `
  --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-audit `
  runtime-handoff-history-diff --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-query `
  runtime-handoff-history-diff --resource summary --resource items --resource added `
  --resource unchanged --resource addresses --resource bounds --limit 100 --format json
```

The API routes append `/runtime-registry/history/diff/runtime-registry/history/diff`,
`/audit`, `/query`, and `/query-audit` to the history route. Discovery publishes
item, items, manifest, summary, diff, audit, query, and query-audit schemas and
capabilities. The independent diff audit has 16 checks; the query audit has 13
checks and replays classification ordering, filters, pagination, row addresses,
and baseline/candidate linkage. On the supplied downloaded ZIP, the live demo
compares an empty baseline history to the ready candidate history and reports
`improved`, one added snapshot, one unchanged snapshot, 30 query rows, and
passing 16/16 and 13/13 audits.

For a portable execution handoff above that history diff, build a runtime
closure. It seals the diff, its independent audit, its bounded query, and its
query audit into one value-free artifact. The runtime is `complete` only when
both nested audits pass, and it is `release_ready` only for an accepted
`improved` or `unchanged` direction. Persistence is an exact six-file package:
`manifest.json`, `diff.json`, `audit.json`, `query.json`, `query-audit.json`,
and `runtime.json`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime `
  runtime-handoff-history-diff --runtime-id runtime-handoff-history-diff-runtime `
  --resource summary --resource items --resource added --resource removed `
  --resource changed --resource unchanged --resource addresses --resource bounds `
  --limit 100 --destination runtime-handoff-history-diff-runtime --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-audit `
  runtime-handoff-history-diff-runtime --format summary
```

The API routes append `/runtime` and `/runtime/audit` to the history-diff
route. Discovery publishes the runtime manifest, runtime schema, capabilities,
and the independent 15-check runtime audit surfaces. The live downloaded-ZIP
demo produces a complete, release-ready runtime over the improved history
comparison and reloads the exact six-file package.

For deterministic admission above portable history-diff runtimes, build a
runtime closure registry. It accepts one or more complete six-file runtime
closures, rejects duplicate runtime identity or address, folds entries into
`empty`, `ready`, or `blocked`, and exposes bounded summary, entry, runtime,
state, readiness, address, and bounds resources. Persistence is an exact
four-file package: `manifest.json`, `registry.json`, `entries.json`, and
`summary.json`.

```powershell
glio-noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry `
  runtime-handoff-history-diff-runtime-primary runtime-handoff-history-diff-runtime-secondary `
  --registry-id runtime-handoff-history-diff-runtime-registry `
  --destination runtime-handoff-history-diff-runtime-registry --overwrite --format summary
glio-noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-audit `
  runtime-handoff-history-diff-runtime-registry --format summary
glio-noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-query `
  runtime-handoff-history-diff-runtime-registry --resource summary --resource entries `
  --resource runtimes --resource states --resource readiness --resource addresses `
  --resource bounds --limit 100 --format json --output runtime-handoff-history-diff-runtime-registry-query.json
glio-noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-query-audit `
  runtime-handoff-history-diff-runtime-registry-query.json runtime-handoff-history-diff-runtime-registry --format summary
```

The API route appends `/runtime-registry` to the history-diff runtime route;
`/audit`, `/query`, and `/query-audit` provide independent verification and
bounded projections. Discovery publishes registry, entry, entries, manifest,
summary, audit, query, and query-audit schemas and capabilities. The registry
audit has 16 checks and the query audit has 12 checks. On the supplied
downloaded ZIP, the live demo admits two complete runtime closures, reports a
ready registry with two entries, returns 26 query rows without truncation, and
passes both audits.

For a release-facing comparison above the portable runtime-registry histories,
build a baseline history and a candidate history with the same history identity.
The diff aligns snapshots by ordinal, preserves the full public snapshot evidence,
classifies added/removed/changed/unchanged items, folds the latest quality state
into an improved/regressed/changed/unchanged direction, and rejects noncanonical
or private projections. Persistence is an exact four-file package:
`manifest.json`, `diff.json`, `items.json`, and `summary.json`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff `
  baseline-runtime-registry-history candidate-runtime-registry-history `
  --diff-id runtime-registry-history-d161-diff --destination runtime-registry-history-d161-diff `
  --overwrite --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-audit `
  runtime-registry-history-d161-diff --format summary
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-query `
  runtime-registry-history-d161-diff --resource summary --resource items --resource added `
  --resource removed --resource changed --resource unchanged --resource addresses `
  --resource bounds --limit 100 --format json --output runtime-registry-history-d161-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-query-audit `
  runtime-registry-history-d161-query.json runtime-registry-history-d161-diff --format summary
```

The API appends `/diff`, `/audit`, `/query`, and `/query-audit` to the
runtime-registry history route. Discovery publishes item, items, manifest,
summary, diff, audit, query, and query-audit schemas and capabilities. The
independent diff audit has 16 checks; the query audit has 13 checks and replays
classification ordering, filters, pagination, row addresses, and baseline/
candidate linkage. The live downloaded ZIP demo compares an empty baseline
history to the ready candidate history and reports `improved`, one added
snapshot, one unchanged snapshot, 30 query rows, and passing 16/16 and 13/13
audits through both the CLI and HTTP API.
For a release-facing runtime closure above the portable registry-history diff,
build a six-file package from the D161 diff. The closure carries the diff,
its independent audit, the bounded query, the query audit, and a runtime
summary with complete/incomplete state and release readiness. The persisted
package is exactly `manifest.json`, `diff.json`, `audit.json`, `query.json`,
`query-audit.json`, and `runtime.json`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime runtime-registry-history-d161-diff --runtime-id runtime-registry-history-d161-runtime --resource summary --resource items --resource added --resource removed --resource changed --resource unchanged --resource addresses --resource bounds --limit 100 --destination runtime-registry-history-d161-runtime --overwrite --format json --output runtime-registry-history-d161-runtime.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-audit runtime-registry-history-d161-runtime --format json --output runtime-registry-history-d161-runtime-audit.json
```

The API appends `/runtime` and `/runtime/audit` to the D161 diff route.
Discovery publishes runtime manifest, runtime schema, runtime capabilities, and
the independent runtime-audit schemas. The runtime audit has 15 checks. The
live downloaded ZIP demo completes with `state=complete`, `accepted=true`,
`release_ready=true`, and `direction=improved`; its D161 query remains
bounded and fully returned.
For deterministic admission above D162 runtime closures, build a registry from
one or more persisted runtime packages. The registry rejects duplicate runtime
identity or content addresses, folds readiness into a stable ready/blocked
state, and exposes bounded entry, runtime, state, readiness, address, and
bounds projections. Its exact four-file package is `manifest.json`,
`registry.json`, `entries.json`, and `summary.json`.

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry runtime-registry-history-d161-runtime runtime-registry-history-d161-api-runtime --registry-id runtime-registry-history-d163 --destination runtime-registry-history-d163 --overwrite --format json --output runtime-registry-history-d163.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-audit runtime-registry-history-d163 --format json --output runtime-registry-history-d163-audit.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-query runtime-registry-history-d163 --resource summary --resource entries --resource runtimes --resource states --resource readiness --resource addresses --resource bounds --limit 100 --format json --output runtime-registry-history-d163-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-query-audit runtime-registry-history-d163-query.json runtime-registry-history-d163 --format json --output runtime-registry-history-d163-query-audit.json
```

The API appends `/registry`, `/registry/audit`, `/registry/query`, and
`/registry/query-audit` to the D162 runtime route. Discovery publishes registry,
entry, entries, manifest, summary, query, and independent audit schemas. The
live downloaded ZIP demo admits two closures with `state=ready`,
`accepted=true`, 26/26 query rows, 16/16 registry-audit checks, and 12/12
query-audit checks through both CLI and HTTP API.
## D164 runtime-closure registry history

D164 adds append-only history over the D163 runtime-closure admission registry. It accepts one or more typed D163 registry packages, preserves stable registry identity and address lineage, rejects duplicate snapshots, and classifies each snapshot as `initial`, `improved`, `regressed`, `unchanged`, or `changed`. State, acceptance, ready/blocked counts, and latest-snapshot projections are recomputed from the ordered entries.

The history package is an exact four-file contract:

- `manifest.json`
- `history.json`
- `entries.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history REGISTRY_A REGISTRY_B --history-id quality-history-d164 --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-audit HISTORY_DIR --format json --output history-audit.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query HISTORY_DIR --resource summary --resource snapshots --resource transitions --resource states --resource readiness --resource addresses --resource bounds --limit 100 --format json --output history-query.json
python -m glio_noncode downloaded-data-quality-diff-gate-remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query-audit history-query.json HISTORY_DIR --format json --output history-query-audit.json
```

The HTTP surface is rooted at:

```
/v1/downloaded-data/quality/diff/gate/remediation/resolution/history/diff/policy/package/registry/history/diff/runtime-registry/history/diff/runtime-registry/history/diff/runtime-registry/history/diff/runtime/registry/history
/v1/downloaded-data/quality/diff/gate/remediation/resolution/history/diff/policy/package/registry/history/diff/runtime-registry/history/diff/runtime-registry/history/diff/runtime-registry/history/diff/runtime/registry/history/audit
/v1/downloaded-data/quality/diff/gate/remediation/resolution/history/diff/policy/package/registry/history/diff/runtime-registry/history/diff/runtime-registry/history/diff/runtime-registry/history/diff/runtime/registry/history/query
/v1/downloaded-data/quality/diff/gate/remediation/resolution/history/diff/policy/package/registry/history/diff/runtime-registry/history/diff/runtime-registry/history/diff/runtime-registry/history/diff/runtime/registry/history/query-audit
```

All projections are value-free and path-free. The history and query audits independently replay canonical addresses, counts, transitions, filters, pagination, and nested projections.


Live downloaded-ZIP evidence for D164 used the real D163 registry package at `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d161-registry-d163` plus an empty baseline with the same registry identity. The CLI and HTTP API both produced a ready two-snapshot history with `initial_count=1`, `improved_count=1`, `entry_count=2`, `40/40` query rows, a `16/16` history audit, and a `12/12` query audit. Persisted evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d161-registry-history-d164-v2.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d161-registry-history-d164-v2-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d161-registry-history-d164-v2-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d161-registry-history-d164-v2-query-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d161-registry-history-d164-api-v2`

## D165 downloaded-data quality runtime-history release gate

D165 turns a D164 history into a deterministic release decision. The gate accepts explicit policy limits for minimum history depth, allowed regressions, allowed latest blocked entries, latest readiness, latest acceptance, and unchanged transitions. It emits twelve fixed checks, addressable explanations, a ready or blocked state, and a release-ready boolean without exposing source paths or payload values.

The persisted gate is an exact four-file package:

- `manifest.json`
- `gate.json`
- `checks.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-gate HISTORY_DIR --gate-id quality-gate --destination GATE_DIR --overwrite --format json --output gate.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-gate-audit GATE_DIR HISTORY_DIR --format json --output gate-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-gate-query GATE_DIR --resource summary --resource policy --resource checks --resource readiness --resource counters --resource addresses --resource bounds --limit 64 --format json --output gate-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-gate-query-audit gate-query.json GATE_DIR --format json --output gate-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-gate`, with `/audit`, `/query`, and `/query-audit` suffixes.

Live downloaded-ZIP evidence for D165 used the persisted D164 history at `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d161-registry-history-d164-v2`. The CLI and HTTP API both produced `state=ready`, `release_ready=true`, and `12/12` release checks; the gate query returned `36/36` rows without truncation; and the independent gate and query audits each passed `12/12`. The empty-history negative case correctly produced `state=blocked`. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-gate-d165-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-gate-d165-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-gate-d165-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-gate-d165-live-query-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-gate-d165-api`

## D166 downloaded-data quality runtime-history release evidence

D166 packages one D165 release gate, its independent gate audit, the complete evidence query, and the independent query audit into one portable release-evidence contract. The summary records gate readiness, both audit decisions, query completeness, evidence readiness, checks, rows, and resource counts. Every nested artifact remains content-addressed and all cross-artifact identities and addresses replay before the package is accepted.

The persisted evidence package is an exact seven-file directory:

- `manifest.json`
- `evidence.json`
- `gate.json`
- `gate-audit.json`
- `query.json`
- `query-audit.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence GATE_DIR HISTORY_DIR --evidence-id quality-release-evidence --destination EVIDENCE_DIR --overwrite --format json --output evidence.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-audit EVIDENCE_DIR --format json --output evidence-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-query EVIDENCE_DIR --limit 128 --format json --output evidence-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-query-audit evidence-query.json EVIDENCE_DIR --format json --output evidence-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence`, with `/audit`, `/query`, and `/query-audit` suffixes.

Live downloaded-ZIP evidence for D166 used the persisted D165 gate and D164 history. The CLI and HTTP API both produced `evidence_ready=true`; the embedded D165 query was `36/36`, the evidence query returned `55/55` rows without truncation, and the independent evidence and query audits each passed `12/12`. Exact-file reload succeeded and summary tampering was rejected. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-d166-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-d166-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-d166-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-d166-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-d166-live-query-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-d166-api`

## D167 downloaded-data quality runtime-history release-evidence history

D167 adds an append-only history above D166 release evidence. Each snapshot records the evidence address, stable gate and source-history identities, readiness counters, predecessor address, and a deterministic transition. Appends require the current head when supplied, reject duplicate snapshot IDs and evidence addresses, and preserve the latest state and readiness projection.

The persisted history is an exact four-file directory:

- `manifest.json`
- `history.json`
- `entries.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history EVIDENCE_DIR --history-id quality-release-evidence-history --snapshot-id initial --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-append HISTORY_DIR EVIDENCE_DIR --snapshot-id candidate-2 --expected-head HEAD_ADDRESS --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-audit HISTORY_DIR --format json --output history-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-query HISTORY_DIR --limit 128 --format json --output history-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-query-audit history-query.json HISTORY_DIR --format json --output history-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history`, with `/append`, `/audit`, `/query`, and `/query-audit` suffixes.

Live downloaded-ZIP evidence for D167 used the persisted D166 release-evidence package. The CLI and HTTP API both produced a ready one-entry history; the history audit passed `16/16`, the query returned `27/27` rows without truncation, and the query audit passed `12/12`. A blocked-to-ready in-memory append separately produced `initial` followed by `improved`, with stale-head and duplicate protections covered by tests. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-history-d167-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-history-d167-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-history-d167-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-history-d167-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-history-d167-live-query-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-history-d167-api`

## D168 downloaded-data quality runtime-history release-evidence history runtime

D168 turns the append-only D167 evidence history into an explicit policy decision. The runtime evaluates minimum history depth, regression and blocked-snapshot budgets, latest state and evidence readiness, transition allowances, stable identity, canonical head/address namespaces, and the public boundary. It folds those checks into a deterministic `ready` or `blocked` release decision.

The persisted runtime is an exact four-file directory:

- `manifest.json`
- `runtime.json`
- `checks.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime HISTORY_DIR --runtime-id quality-release-evidence-runtime --minimum-entries 1 --maximum-regressed 0 --maximum-blocked 0 --destination RUNTIME_DIR --overwrite --format json --output runtime.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-audit RUNTIME_DIR --format json --output runtime-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-query RUNTIME_DIR --limit 128 --format json --output runtime-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-query-audit runtime-query.json RUNTIME_DIR --format json --output runtime-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime`, with `/audit`, `/query`, and `/query-audit` suffixes. Schemas and capabilities are exposed beneath the same API family.

Live downloaded-ZIP evidence for D168 used the persisted D167 history. The runtime produced `ready=true` with `14/14` policy checks; the independent runtime audit passed `14/14`; the bounded query returned `49/49` rows without truncation; and the independent query audit passed `12/12`. CLI and HTTP outputs were both generated, exact-file persistence and reload succeeded, and runtime tamper rejection is covered by the regression suite. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-history-runtime-d168-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-history-runtime-d168-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-history-runtime-d168-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-history-runtime-d168-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-history-release-evidence-history-runtime-d168-live-query-audit.json`

## D169 downloaded-data quality runtime-history release-evidence history runtime registry

D169 admits multiple D168 history-runtime decisions into one deterministic registry. Each registry entry preserves the runtime and history identities, content addresses, state, readiness, check counters, and history depth. The aggregate remains explicit: an empty registry is `empty`, a non-empty registry with only ready entries is `ready`, and any blocked entry produces `blocked`. Duplicate runtime IDs and runtime content addresses are rejected before admission.

The persisted registry is an exact four-file directory:

- `manifest.json`
- `registry.json`
- `entries.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry RUNTIME_DIR_1 RUNTIME_DIR_2 --registry-id quality-runtime-registry --destination REGISTRY_DIR --overwrite --format json --output registry.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-audit REGISTRY_DIR --format json --output registry-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-query REGISTRY_DIR --limit 128 --format json --output registry-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-query-audit registry-query.json REGISTRY_DIR --format json --output registry-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry`, with `/audit`, `/query`, and `/query-audit` suffixes. Entry, manifest, summary, registry, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP evidence for D169 admitted two independent D168 runtimes. The registry produced `state=ready`, `release_ready=true`, and `2/2` ready entries; the independent registry audit passed `16/16`; the registry query returned `24/24` rows without truncation; and the independent query audit passed `12/12`. Duplicate runtime admission was rejected, and a deliberately blocked runtime produced a blocked aggregate. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-d169-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-d169-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-d169-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-d169-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-d169-live-query-audit.json`

## D170 downloaded-data quality runtime-history release-evidence history runtime registry history

D170 adds append-only history above D169 runtime registries. Each snapshot records the stable registry identity, registry content address, aggregate state and readiness, entry counters, predecessor address, snapshot ID, and deterministic transition. Appends require the current head when supplied, reject duplicate snapshot IDs and registry addresses, and fold the latest state and readiness without importing source records or paths.

The persisted history is an exact four-file directory:

- `manifest.json`
- `history.json`
- `entries.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history REGISTRY_DIR --history-id quality-runtime-registry-history --snapshot-id initial --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-append HISTORY_DIR REGISTRY_DIR --snapshot-id ready --expected-head HEAD_ADDRESS --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-audit HISTORY_DIR --format json --output history-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-query HISTORY_DIR --limit 128 --format json --output history-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-query-audit history-query.json HISTORY_DIR --format json --output history-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history`, with `/append`, `/audit`, `/query`, and `/query-audit` suffixes. Entry, manifest, summary, history, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP evidence for D170 used a blocked D169 registry followed by a ready D169 registry with the same registry identity. The history produced `initial → improved`, `latest_state=ready`, and `latest_release_ready=true`; the independent history audit passed `16/16`; the history query returned `30/30` rows without truncation; and the independent query audit passed `12/12`. Duplicate registry append and stale/tampered persistence controls are covered by the regression suite. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d170-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d170-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d170-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d170-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d170-live-query-audit.json`

## D171 downloaded-data quality runtime-history release-evidence history runtime registry history diff

D171 compares two D170 runtime-registry histories that share the same registry identity. It matches snapshots by ordinal, retains both addressed snapshots, records the ordered entry fields that changed, classifies each ordinal as added, removed, changed, or unchanged, and folds the comparison into an improved, regressed, changed, or unchanged direction with an explicit state transition.

The persisted comparison is an exact four-file directory:

- `manifest.json`
- `diff.json`
- `items.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff BASELINE_HISTORY_DIR CANDIDATE_HISTORY_DIR --diff-id quality-runtime-registry-history-diff --destination DIFF_DIR --overwrite --format json --output diff.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-audit DIFF_DIR --format json --output diff-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-query DIFF_DIR --change added --limit 128 --format json --output diff-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-query-audit diff-query.json DIFF_DIR --format json --output diff-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff`, with `/audit`, `/query`, and `/query-audit` suffixes. Item, manifest, summary, diff, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP evidence compares a blocked one-snapshot baseline with the ready two-snapshot D170 candidate. The diff reports `blocked→ready`, `direction=improved`, one added item, one unchanged item, zero removed items, and zero changed items. The independent diff audit passes `16/16`; the bounded query returns `27/27` rows without truncation; and the independent query audit passes `12/12`. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-d171-baseline-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-d171-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-d171-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-d171-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-d171-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-d171-live-query-audit.json`

## D172 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime

D172 evaluates a D171 history comparison against an explicit release policy. The policy controls minimum comparison depth, added/removed/changed budgets, permitted directions, acceptance, state-transition shape, and unchanged-item handling. Fifteen deterministic checks produce a ready or blocked disposition while preserving the comparison address, direction, transition, and class counters.

The persisted runtime decision is an exact four-file directory:

- `manifest.json`
- `runtime.json`
- `checks.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime DIFF_DIR --runtime-id quality-runtime-registry-history-diff-runtime --maximum-added 128 --destination RUNTIME_DIR --overwrite --format json --output runtime.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-audit RUNTIME_DIR --format json --output runtime-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-query RUNTIME_DIR --limit 128 --format json --output runtime-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-query-audit runtime-query.json RUNTIME_DIR --format json --output runtime-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime`, with `/audit`, `/query`, and `/query-audit` suffixes. Policy, check, manifest, summary, runtime, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP evidence evaluates the D171 blocked-to-ready comparison. The default policy produces `state=ready`, `release_ready=true`, and `15/15` runtime checks. The runtime query returns `58/58` rows without truncation and its independent query audit passes `12/12`. A strict `maximum_added=0` policy produces the expected blocked disposition with `14/15` checks. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-d172-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-d172-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-d172-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-d172-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-d172-live-query-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-d172-blocked-live.json`

## D173 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry

D173 admits multiple D172 runtime decisions into one deterministic registry. It rejects duplicate runtime identities and duplicate runtime content addresses, preserves each runtime's addressed decision, folds empty/ready/blocked aggregate state and release readiness, and records accepted admission independently from release readiness.

The persisted registry is an exact four-file directory:

- `manifest.json`
- `registry.json`
- `entries.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry RUNTIME_DIR... --registry-id quality-runtime-registry-history-d173 --destination REGISTRY_DIR --overwrite --format json --output registry.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-audit REGISTRY_DIR --format json --output registry-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-query REGISTRY_DIR --limit 128 --format json --output registry-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-query-audit registry-query.json REGISTRY_DIR --format json --output registry-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry`, with `/audit`, `/query`, and `/query-audit` suffixes. Entry, runtime, manifest, summary, registry, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP evidence admits one ready and one blocked D172 runtime. The registry is accepted with `state=blocked`, `release_ready=false`, `entry_count=2`, `ready_count=1`, and `blocked_count=1`; the independent registry audit passes `16/16`; the bounded query returns `24/24` rows without truncation; and the independent query audit passes `12/12`. Duplicate identity, duplicate address, persistence tamper, CLI, HTTP, and schema controls are covered by the regression suite. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-d173-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-d173-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-d173-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-d173-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-d173-live-query-audit.json`

## D174 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history

D174 adds append-only history above D173 multi-runtime registries. Each snapshot preserves the stable registry identity, addressed registry state and counters, predecessor address, snapshot identity, and deterministic transition. Appends require the current head when supplied and reject duplicate snapshot IDs, duplicate registry addresses, identity changes, and stale heads. The latest state, readiness, and acceptance remain explicit projections.

The persisted history is an exact four-file directory:

- `manifest.json`
- `history.json`
- `entries.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history REGISTRY_DIR --history-id quality-runtime-registry-history-d174 --snapshot-id blocked --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-append HISTORY_DIR REGISTRY_DIR --snapshot-id ready --expected-head HEAD_ADDRESS --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-audit HISTORY_DIR --format json --output history-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-query HISTORY_DIR --limit 128 --format json --output history-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-query-audit history-query.json HISTORY_DIR --format json --output history-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history`, with `/append`, `/audit`, `/query`, and `/query-audit` suffixes. Entry, entries, manifest, summary, history, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP evidence appends a blocked D173 registry followed by a ready D173 registry with the same registry identity. The history reports `initial → improved`, `latest_state=ready`, and `latest_release_ready=true`; the independent history audit passes `16/16`; the bounded query returns `30/30` rows without truncation; and the independent query audit passes `12/12`. Duplicate address, stale-head, persistence tamper, CLI, HTTP, and schema controls are covered by the regression suite. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d174-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d174-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d174-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d174-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d174-live-query-audit.json`

## D175 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff

D175 compares two D174 diff-runtime registry histories with the same registry identity while preserving distinct left/right history identities and addressed roots. It matches snapshots by ordinal, records ordered field-level changes with both snapshot addresses, classifies each ordinal as added, removed, changed, or unchanged, and folds the result into an improved, regressed, changed, or unchanged direction with an explicit state transition.

The persisted comparison is an exact four-file directory:

- `manifest.json`
- `diff.json`
- `items.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff BASELINE_HISTORY_DIR CANDIDATE_HISTORY_DIR --diff-id quality-runtime-registry-history-diff-d175 --destination DIFF_DIR --overwrite --format json --output diff.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-audit DIFF_DIR --format json --output diff-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-query DIFF_DIR --change added --limit 128 --format json --output diff-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-query-audit diff-query.json DIFF_DIR --format json --output diff-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff`, with `/audit`, `/query`, and `/query-audit` suffixes. Item, items, manifest, summary, diff, audit, query, and capability schemas are exposed beneath the same API family.

The downloaded-data regression compares a blocked one-snapshot history with a ready two-snapshot history. It reports `blocked→ready`, `direction=improved`, one added item, one unchanged item, zero removed items, and zero changed items. The independent diff audit passes `16/16`; the bounded query returns `27/27` rows without truncation; and the independent query audit passes `12/12`. Same-registry and persistence-tamper rejection are covered by the regression suite. Live evidence is generated from the downloaded-data admission artifacts under:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-baseline-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-candidate-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-live-query-audit.json`

## D176 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime

D176 evaluates a D175 history comparison against an explicit release policy. The policy controls minimum comparison depth, added/removed/changed budgets, permitted directions, comparison acceptance, state-transition requirements, and unchanged-item handling. Fifteen deterministic checks produce a ready or blocked release disposition while preserving the comparison address, direction, transition, and change counters.

The persisted runtime decision is an exact four-file directory:

- `manifest.json`
- `runtime.json`
- `checks.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime DIFF_DIR --runtime-id quality-runtime-registry-history-d176-runtime --maximum-added 128 --destination RUNTIME_DIR --overwrite --format json --output runtime.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-audit RUNTIME_DIR --format json --output runtime-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-query RUNTIME_DIR --limit 128 --format json --output runtime-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-query-audit runtime-query.json RUNTIME_DIR --format json --output runtime-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime`, with `/audit`, `/query`, and `/query-audit` suffixes. Policy, check, manifest, summary, runtime, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP-derived evidence evaluates the D175 blocked-to-ready comparison. The default policy produces `state=ready`, `release_ready=true`, and `15/15` runtime checks. The runtime query returns `58/58` rows without truncation and its independent query audit passes `12/12`. A strict `maximum_added=0` policy produces the expected blocked disposition with `14/15` checks. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-diff-runtime-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-diff-runtime-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-diff-runtime-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-diff-runtime-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-diff-runtime-live-query-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-diff-runtime-d176-blocked-live.json`

## D177 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime registry

D177 admits multiple D176 policy runtimes into one deterministic registry. Each runtime becomes a value-only entry carrying its runtime and diff addresses, state, readiness, check counters, and item count. The registry rejects duplicate runtime identities or addresses and folds the entries into an empty, ready, or blocked aggregate disposition.

The persisted registry is an exact four-file directory:

- `manifest.json`
- `registry.json`
- `entries.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry READY_RUNTIME BLOCKED_RUNTIME --registry-id quality-runtime-registry-history-d177 --destination REGISTRY_DIR --overwrite --format json --output registry.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-audit REGISTRY_DIR --format json --output registry-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-query REGISTRY_DIR --limit 128 --format json --output registry-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-query-audit registry-query.json REGISTRY_DIR --format json --output registry-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry`, with `/audit`, `/query`, and `/query-audit` suffixes. Entry, entries, manifest, summary, registry, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP-derived evidence admits the D176 ready runtime and strict-budget blocked runtime. The aggregate is `state=blocked`, `release_ready=false`, with `2` entries, `1` ready entry, and `1` blocked entry. The independent registry audit passes `16/16`; the registry query returns `24/24` rows without truncation; and its independent query audit passes `12/12`. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-diff-runtime-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-d175-diff-runtime-d176-blocked-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-live-query-audit.json`

## D178 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime registry history

D178 adds append-only history above D177 runtime registries. A history records the registry identity and a sequence of content-addressed snapshots. Appends require the current snapshot entry address as the optimistic expected head, reject duplicate snapshot IDs and registry addresses, and fold transitions as `initial`, `improved`, `regressed`, `unchanged`, or `changed` while exposing the latest state and readiness.

The persisted history is an exact four-file directory:

- `manifest.json`
- `history.json`
- `entries.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history REGISTRY_DIR --history-id quality-runtime-registry-history-d178 --snapshot-id blocked --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-append HISTORY_DIR READY_REGISTRY_DIR --snapshot-id ready --expected-head SNAPSHOT_ENTRY_ADDRESS --destination NEXT_HISTORY_DIR --overwrite --format json --output next-history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-audit HISTORY_DIR --format json --output history-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query HISTORY_DIR --limit 128 --format json --output history-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query-audit history-query.json HISTORY_DIR --format json --output history-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history`, with `/append`, `/audit`, `/query`, and `/query-audit` suffixes. Entry, entries, manifest, summary, history, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP-derived evidence starts with the blocked D177 registry and appends the ready D177 registry. The initial snapshot is blocked; the appended history is `latest_state=ready`, `latest_release_ready=true`, with `2` entries and transitions `initial,improved`. The independent history audit passes `16/16`; the history query returns `30/30` rows without truncation; and its independent query audit passes `12/12`. A stale history-document address was rejected by the expected-head guard; the successful append used the authoritative initial snapshot entry address. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-ready-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-live-initial`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-live-query-audit.json`

## D179 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime registry history diff

D179 compares two D178 registry histories while preserving explicit left/right history identity and address provenance. It classifies snapshots by ordinal as added, removed, changed, or unchanged, records ordered field-level deltas, and folds direction and state transition into `improved`, `regressed`, `changed`, or `unchanged` outcomes.

The persisted diff is an exact four-file directory:

- `manifest.json`
- `diff.json`
- `items.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff LEFT_HISTORY_DIR RIGHT_HISTORY_DIR --diff-id quality-runtime-registry-history-d179 --destination DIFF_DIR --overwrite --format json --output diff.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-audit DIFF_DIR --format json --output diff-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-query DIFF_DIR --limit 128 --format json --output diff-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-query-audit diff-query.json DIFF_DIR --format json --output diff-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff`, with `/audit`, `/query`, and `/query-audit` suffixes. Item, items, manifest, summary, diff, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP-derived evidence compares the blocked one-snapshot D178 history against the appended blocked-to-ready D178 history. The result is `direction=improved`, `state_transition=blocked->ready`, with `1` added snapshot, `0` removed, `0` changed, and `1` unchanged. The independent diff audit passes `16/16`; the diff query returns `27/27` rows without truncation; and its independent query audit passes `12/12`. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-live-initial`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-live-query-audit.json`

## D180 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime registry history diff runtime

D180 evaluates a D179 baseline/candidate diff against an explicit, value-only release policy. The policy controls minimum comparison depth, added/removed/changed budgets, allowed direction, source acceptance, required state changes, and whether unchanged snapshots are allowed. Fifteen deterministic checks fold into a `ready` or `blocked` runtime with failed-check evidence.

The persisted runtime is an exact four-file directory:

- `manifest.json`
- `runtime.json`
- `checks.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime DIFF_DIR --runtime-id quality-runtime-registry-history-d180 --maximum-added 1 --destination RUNTIME_DIR --overwrite --format json --output runtime.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-audit RUNTIME_DIR --format json --output runtime-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-query RUNTIME_DIR --limit 128 --format json --output runtime-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-query-audit runtime-query.json RUNTIME_DIR --format json --output runtime-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime`, with `/audit`, `/query`, and `/query-audit` suffixes. Policy, check, manifest, summary, runtime, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP-derived evidence evaluates the D179 improved blocked-to-ready diff. The permissive policy produces `state=ready`, `release_ready=true`, and `15/15` checks; the independent runtime audit passes `15/15`; the runtime query returns `58/58` rows without truncation; and its independent query audit passes `12/12`. A negative-control policy with `maximum_added=0` exits with code `2` and records `state=blocked`, `release_ready=false`, and `14/15` checks. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-live-query-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-live-blocked`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-live-blocked.json`

## D181 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime registry

D181 composes one or more D180 runtime decisions into an addressed admission registry. It rejects duplicate runtime identities and addresses, preserves each runtime entry, and folds the aggregate to `empty`, `ready`, or `blocked` while retaining separate ready and blocked counts.

The persisted registry is an exact four-file directory:

- `manifest.json`
- `registry.json`
- `entries.json`
- `summary.json`

The CLI surface is:

```powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry RUNTIME_DIR... --registry-id quality-runtime-registry-history-d181 --destination REGISTRY_DIR --overwrite --format json --output registry.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-audit REGISTRY_DIR --format json --output registry-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-query REGISTRY_DIR --limit 128 --format json --output registry-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-query-audit registry-query.json REGISTRY_DIR --format json --output registry-query-audit.json
```

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry`, with `/audit`, `/query`, and `/query-audit` suffixes. Entry, entries, manifest, summary, registry, audit, query, and capability schemas are exposed beneath the same API family.

Live downloaded-ZIP-derived evidence composes the D180 ready runtime and its strict-budget blocked control. The mixed registry records `2` entries, `1` ready and `1` blocked, and folds to `state=blocked` with `release_ready=false`; its independent registry audit passes `16/16`, the query returns `24/24` rows without truncation, and query audit passes `12/12`. A ready-only registry records `1` entry, folds to `state=ready`, passes `16/16` audit checks, returns `22/22` query rows, and passes `12/12` query-audit checks. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-live-query-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-ready-live`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-ready-live.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-ready-live-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-ready-live-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-quality-admission-registry-live-20260920-v5/runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-ready-live-query-audit.json`

## D182 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime registry history

D182 adds an append-only history above D181 admission registries. A history binds one stable registry identity to an ordered sequence of registry snapshots, requires an optimistic expected head for appends, rejects duplicate snapshot IDs and registry addresses, classifies `initial`, `improved`, `regressed`, `unchanged`, and `changed` transitions, and folds the latest registry state and readiness into the history summary.

The persisted history is an exact four-file directory:

- `manifest.json`
- `history.json`
- `entries.json`
- `summary.json`

The CLI surface is:

~~~powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history REGISTRY_DIR --history-id HISTORY_ID --snapshot-id SNAPSHOT_ID --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-append HISTORY_DIR REGISTRY_DIR --snapshot-id SNAPSHOT_ID --expected-head HEAD_ADDRESS --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-audit HISTORY_DIR --format json --output history-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query HISTORY_DIR --limit 128 --format json --output history-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query-audit history-query.json HISTORY_DIR --format json --output history-query-audit.json
~~~

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history`, with `/append`, `/audit`, `/query`, and `/query-audit` suffixes. Entry, entries, manifest, summary, history, audit, query, query-audit, and capability schemas are exposed beneath the same API family.

The downloaded-data regression replays the ZIP-derived profile through D181 mixed and ready registries, then verifies a blocked-to-ready history transition, duplicate and stale-head rejection, exact persistence, tamper rejection, CLI append/audit/query flows, HTTP append/audit/query flows, and the `RegistryHistory` schema. The authoritative run passed: `Ran 1 test in 413.342s`, `OK`.
## D183 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime registry history diff

D183 compares two D182 runtime-registry histories that share the same registry identity. It emits ordered added, removed, changed, and unchanged snapshot items, preserves both history and entry addresses, records field-level deltas, folds direction and latest-state transitions, and rejects cross-history identity mismatches.

The persisted diff is an exact four-file directory:

- `manifest.json`
- `diff.json`
- `items.json`
- `summary.json`

The CLI surface is:

~~~powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff BASELINE_HISTORY_DIR CANDIDATE_HISTORY_DIR --diff-id DIFF_ID --destination DIFF_DIR --overwrite --format json --output diff.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-audit DIFF_DIR --format json --output diff-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-query DIFF_DIR --limit 128 --format json --output diff-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-query-audit diff-query.json DIFF_DIR --format json --output diff-query-audit.json
~~~

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff`, with `/audit`, `/query`, and `/query-audit` suffixes. Item, items, manifest, summary, diff, audit, query, query-audit, and capability schemas are exposed beneath the same API family.

The focused replay verifies canonical round-trip, summary tamper rejection, same-registry identity enforcement, deterministic field-level change classification, bounded queries, independent 16/16 diff auditing, independent 12/12 query auditing, and the exact four-file artifact contract. The direct smoke uses the downloaded-data history model; the broader historical suite currently reports a pre-existing D174 registry-identity failure before reaching D183.

## D184 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime registry history diff runtime registry history diff runtime

D184 evaluates a D183 baseline/candidate history diff against an explicit, value-only release policy. The policy controls minimum comparison depth, added/removed/changed budgets, allowed direction, source acceptance, required state changes, and whether unchanged snapshots are allowed. Fifteen deterministic checks fold into a `ready` or `blocked` runtime with failed-check evidence and a `release_ready` projection.

The persisted runtime is an exact four-file directory:

- `manifest.json`
- `runtime.json`
- `checks.json`
- `summary.json`

The CLI surface is:

~~~powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime DIFF_DIR --runtime-id quality-history-diff-policy-d184 --maximum-added 1 --destination RUNTIME_DIR --overwrite --format json --output runtime.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-audit RUNTIME_DIR --format json --output runtime-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-query RUNTIME_DIR --limit 128 --format json --output runtime-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-query-audit runtime-query.json RUNTIME_DIR --format json --output runtime-query-audit.json
~~~

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime`, with `/audit`, `/query`, and `/query-audit` suffixes. Policy, check, manifest, summary, runtime, audit, query, and capability schemas are exposed beneath the same API family.

The focused replay builds a D183 diff from two downloaded-data history snapshots, evaluates the permissive policy, verifies `state=ready`, `release_ready=true`, and `15/15` runtime checks, replays all bounded query resources, and rejects a tampered persisted summary. A strict negative-control policy with `maximum_changed=0` can be used to force a blocked decision while preserving the same auditable artifact contract.

Live evidence from the supplied ZIP first reports `25` catalog members, `17` selected data members, `4,030` records, `136` profiled fields, and an accepted `563`-check quality result. The D184 replay derived its stable history identity from that source result, then produced a ready runtime with `15/15` checks, `58/58` query rows, and a `12/12` query audit. The `maximum_changed=0` negative control produced `state=blocked`, `release_ready=false`, and `14/15` checks. Artifacts are available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d184-diff`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d184`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d184-blocked`

## D185 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime registry history diff runtime registry history diff runtime registry

D185 admits one or more typed D184 policy runtimes into a deterministic addressed registry. Admission rejects duplicate runtime identities and duplicate runtime content addresses, preserves each runtime decision as an entry, and folds the aggregate to `empty`, `ready`, or `blocked` while retaining entry, ready, and blocked counts plus the aggregate `release_ready` projection. The registry is value-only: it carries runtime decisions, addresses, states, and audit evidence without exposing source paths or source records.

The persisted registry is an exact four-file directory:

- `manifest.json`
- `registry.json`
- `entries.json`
- `summary.json`

The CLI surface is:

~~~powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry RUNTIME_DIR... --registry-id quality-runtime-registry-d185 --destination REGISTRY_DIR --overwrite --format json --output registry.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-audit REGISTRY_DIR --format json --output registry-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-query REGISTRY_DIR --limit 128 --format json --output registry-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-query-audit registry-query.json REGISTRY_DIR --format json --output registry-query-audit.json
~~~

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry`, with `/audit`, `/query`, and `/query-audit` suffixes. Entry, entries, manifest, summary, registry, audit, query, query-audit, and capability schemas are exposed beneath the same API family. Query resources are bounded and independently auditable across summary, entries, diffs, state, readiness, addresses, and bounds projections.

The focused replay builds two D184 policy runtimes over the same downloaded-data history diff, admits both, verifies canonical round-trip and summary tamper rejection, rejects a duplicate runtime identity, and independently replays the registry and query contracts. The ready registry folds to `state=ready`, `release_ready=true`, and `2` ready entries; the registry audit passes `16/16`; the bounded query returns `22/22` rows; and the query audit passes `12/12`.

Live replay of `GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip` uses the persisted D184 runtime derived from the real source quality data. It produces a ready one-entry D185 registry with `entry_count=1`, `ready_count=1`, and `release_ready=true`; the registry audit passes `16/16`; the bounded query returns `22/22` rows without truncation; and the query audit passes `12/12`. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d185-registry`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d185-registry.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d185-registry-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d185-registry-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d185-registry-query-audit.json`

## D186 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime registry history diff runtime registry history diff runtime registry history

D186 records an append-only history of D185 admission registries. A history has one stable `registry_id`, retains each addressed registry snapshot, assigns a deterministic sequence, classifies transitions such as `initial`, `ready_to_ready`, `blocked_to_ready`, and `ready_to_blocked`, and folds the latest snapshot into the current `empty`, `ready`, or `blocked` state. Appends require an optional expected head address, so stale writers fail before they can fork the history. Duplicate snapshot identifiers and duplicate addresses are rejected, and snapshots from a different registry identity cannot be admitted.

The persisted history is an exact four-file directory:

- `manifest.json`
- `history.json`
- `entries.json`
- `summary.json`

The CLI surface is:

~~~powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history REGISTRY_DIR --history-id quality-registry-history-d186 --snapshot-id initial --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-append HISTORY_DIR REGISTRY_DIR --snapshot-id next --expected-head HISTORY_HEAD --format json --output history-next.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-audit HISTORY_DIR --format json --output history-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query HISTORY_DIR --limit 128 --format json --output history-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query-audit history-query.json HISTORY_DIR --format json --output history-query-audit.json
~~~

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history`, with `/append`, `/audit`, `/query`, and `/query-audit` suffixes. Entry, entries, manifest, summary, history, audit, query, query-audit, and capability schemas are exposed beneath the same API family. Query resources are bounded and independently auditable across summary, entries, transitions, state, readiness, addresses, and bounds projections.

The focused replay verifies the initial and appended snapshot sequence, stable registry identity, expected-head concurrency guard, duplicate snapshot/address rejection, foreign-registry rejection, deterministic transition classification, canonical reload, summary tamper rejection, independent 16/16 history auditing, bounded queries, and independent 12/12 query auditing.

Live replay of `GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip` starts from the persisted D185 registry derived from the real downloaded source quality data. It produces a one-entry D186 history with the real registry address, `state=ready`, `release_ready=true`, a `16/16` history audit, `29/29` bounded query rows, and a `12/12` query audit. The focused D186 test passes; the 30-test historical file reports 29 passing tests and one pre-existing D174 registry-identity failure outside this layer. Evidence is written under:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d186`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d186.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d186-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d186-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d186-query-audit.json`

## D187 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime registry history diff runtime registry history diff runtime registry history diff

D187 compares two D186 registry histories while preserving their separate history addresses. It aligns ordered snapshots by ordinal, classifies added, removed, changed, and unchanged entries, records field-level deltas for changed snapshots, and folds direction (`improved`, `regressed`, `changed`, or `unchanged`) together with the state transition. The comparison requires the same registry identity on both sides and remains value-only: no source paths, source records, or payload bytes enter the persisted result.

The persisted diff is an exact four-file directory:

- `manifest.json`
- `diff.json`
- `items.json`
- `summary.json`

The CLI surface is:

~~~powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff BASELINE_DIR CANDIDATE_DIR --diff-id quality-registry-history-diff-d187 --destination DIFF_DIR --overwrite --format json --output diff.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-audit DIFF_DIR --format json --output diff-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-query DIFF_DIR --limit 128 --format json --output diff-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-query-audit diff-query.json DIFF_DIR --format json --output diff-query-audit.json
~~~

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff`, with `/audit`, `/query`, and `/query-audit` suffixes. The root accepts either repeated `input` values or explicit `left`/`right` history paths. Item, items, manifest, summary, diff, audit, query, query-audit, and capability schemas are exposed beneath the same API family. Query resources are bounded and independently auditable across summary, items, added, removed, changed, unchanged, addresses, and bounds projections.

The focused replay verifies same-registry identity, ordinal classification, direction and transition folding, field-level change preservation, canonical reload, summary tamper rejection, independent `16/16` diff auditing, bounded queries, and independent `12/12` query auditing.

Live replay starts from real downloaded-data-derived D186 baseline and candidate histories. The candidate contains an initial empty registry snapshot followed by the ready registry admitted from `GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip`; the comparison reports `direction=changed`, `added_count=1`, `changed_count=1`, `removed_count=0`, and `unchanged_count=0`. The CLI and HTTP replays both return `16/16` diff-audit checks, `27/27` query rows without truncation, and `12/12` query-audit checks. Evidence is written under:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d187-baseline`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d187-candidate`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d187-diff`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d187-diff.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d187-diff-audit.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d187-diff-query.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-real-zip-demo-e74815f7edbc470bb5ba241444c84e3d/runtime-history-d187-diff-query-audit.json`

## D188 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history diff runtime

D188 evaluates a D187 registry-history diff against a content-addressed release policy. Policies bound the minimum comparison size, added/removed/changed budgets, allowed directions, acceptance requirement, state-transition requirement, and unchanged behavior. The runtime emits a ready or blocked release disposition with fifteen independently replayable checks while preserving the value-free D187 comparison.

The persisted runtime is an exact four-file directory:

- `manifest.json`
- `runtime.json`
- `checks.json`
- `summary.json`

The CLI surface is:

~~~powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime BASELINE_DIFF_DIR --runtime-id quality-registry-history-diff-runtime-d188 --maximum-added 1 --maximum-changed 1 --destination RUNTIME_DIR --overwrite --format json --output runtime.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-audit RUNTIME_DIR --format json --output runtime-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-query RUNTIME_DIR --limit 128 --format json --output runtime-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-query-audit runtime-query.json RUNTIME_DIR --format json --output runtime-query-audit.json
~~~

The repository example performs the same complete replay and writes a compact summary alongside the exact runtime package:

~~~powershell
python examples/downloaded_data_quality_history_diff_runtime_demo.py D187_DIFF_DIR D188_OUTPUT_DIR --runtime-id quality-registry-history-diff-runtime-d188 --maximum-added 1 --maximum-changed 1
~~~

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime`, with `/audit`, `/query`, and `/query-audit` suffixes. Policy, check, manifest, summary, runtime, audit, query, query-audit, schema, and capability projections are exposed beneath the same API family.

The focused replay verifies policy acceptance and blocking, exact-file persistence, canonical reload, summary tamper rejection, independent `15/15` runtime auditing, bounded query completeness, and independent `12/12` query auditing. The fresh replay of `GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip` first produced `25` catalog members, `17` selected members, `4,030` records, `136` fields, and an accepted `563`-check quality result. That accepted quality address seeded the downstream policy identity; the current D187 comparison reported `direction=improved` with one added snapshot, and D188 produced `state=ready`, `release_ready=true`, `15/15` checks, `58/58` query rows without truncation, and a `12/12` query audit. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/summary.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/quality-runtime`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d188-runtime`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d188-summary.json`

## D189 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry

D189 admits one or more typed D188 policy runtimes into a deterministic value-free registry. Admission rejects duplicate runtime identities and duplicate runtime content addresses, retains each runtime's diff identity and release disposition, and folds the aggregate to `empty`, `ready`, or `blocked` while preserving entry, ready, blocked, and release-readiness counters.

The persisted registry is an exact four-file directory:

- `manifest.json`
- `registry.json`
- `entries.json`
- `summary.json`

The CLI surface is:

~~~powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry RUNTIME_DIR... --registry-id quality-registry-history-diff-runtime-registry-d189 --destination REGISTRY_DIR --overwrite --format json --output registry.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-audit REGISTRY_DIR --format json --output registry-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-query REGISTRY_DIR --limit 128 --format json --output registry-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-query-audit registry-query.json REGISTRY_DIR --format json --output registry-query-audit.json
~~~

The repository example performs the same admission and writes a compact summary alongside the exact registry package:

~~~powershell
python examples/downloaded_data_quality_history_diff_runtime_registry_demo.py D188_READY_RUNTIME_DIR D188_BLOCKED_RUNTIME_DIR --registry-id quality-registry-history-diff-runtime-registry-d189 --destination D189_OUTPUT_DIR
~~~

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry`, with `/audit`, `/query`, and `/query-audit` suffixes. Entry, entries, manifest, summary, registry, audit, query, query-audit, schema, and capability projections are exposed beneath the same API family.

The focused replay verifies ready/blocked aggregate folding, duplicate identity rejection, exact-file persistence, canonical reload, summary tamper rejection, independent `16/16` registry auditing, bounded query completeness, and independent `12/12` query auditing. The fresh downloaded-ZIP-derived replay admitted one ready and one blocked D188 runtime, producing `state=blocked`, `release_ready=false`, `entry_count=2`, `ready_count=1`, `blocked_count=1`, `16/16` registry checks, `24/24` query rows without truncation, and a `12/12` query audit. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d189-registry/summary.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d189-registry/registry`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d189-blocked-runtime`

## D190 downloaded-data quality runtime-history release-evidence history runtime registry history diff runtime registry history

D190 records successive D189 runtime registries as an append-only, addressed history. Each snapshot preserves one stable registry identity, a monotonic ordinal, ancestry through the previous snapshot address, and a deterministic transition: `initial`, `improved`, `regressed`, `unchanged`, or `changed`. Appends support an optional expected-head guard so stale writers cannot fork the history; duplicate snapshot identifiers, duplicate registry addresses, and foreign registry identities are rejected.

The persisted history is an exact four-file directory:

- `manifest.json`
- `history.json`
- `entries.json`
- `summary.json`

The CLI surface is:

~~~powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history REGISTRY_DIR --history-id quality-registry-history-diff-runtime-registry-history-d190 --snapshot-id baseline --destination HISTORY_DIR --overwrite --format json --output history.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-append HISTORY_DIR REGISTRY_DIR --snapshot-id candidate --expected-head HEAD_ADDRESS --format json --output history-next.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-audit HISTORY_DIR --format json --output history-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query HISTORY_DIR --limit 128 --format json --output history-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-query-audit history-query.json HISTORY_DIR --format json --output history-query-audit.json
~~~

The repository example performs the same append and writes a compact summary alongside the exact history package:

~~~powershell
python examples/downloaded_data_quality_history_diff_runtime_registry_history_demo.py D189_BASELINE_REGISTRY_DIR D189_CANDIDATE_REGISTRY_DIR --history-id quality-registry-history-diff-runtime-registry-history-d190 --destination D190_OUTPUT_DIR
~~~

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history`, with `/append`, `/audit`, `/query`, and `/query-audit` suffixes. Entry, entries, manifest, summary, history, audit, query, query-audit, schema, and capability projections are exposed beneath the same API family.

The focused replay verifies blocked-to-ready transition folding, stable identity, expected-head and duplicate guards, exact-file persistence, canonical reload, summary tamper rejection, independent `16/16` history auditing, bounded query completeness, and independent `12/12` query auditing. The fresh downloaded-ZIP-derived replay records a blocked baseline followed by a ready candidate, producing `entry_count=2`, `initial_count=1`, `improved_count=1`, `latest_state=ready`, `latest_release_ready=true`, `16/16` history checks, `30/30` query rows without truncation, and a `12/12` query audit. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d190-history/summary.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d190-history/history`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d190-blocked-registry`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d190-ready-registry`

## D191 downloaded-data quality runtime-registry history diff

D191 compares two exact four-file D190 history directories. It preserves the
left and right history addresses, classifies each ordinal as `added`, `removed`,
`changed`, or `unchanged`, records ordered field-level snapshot deltas, and
folds the result into `improved`, `regressed`, `changed`, or `unchanged` with a
state transition such as `blocked->ready`.

The persisted diff is an exact four-file directory:

- `manifest.json`
- `diff.json`
- `items.json`
- `summary.json`

The CLI surface is:

~~~powershell
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff D190_LEFT_HISTORY_DIR D190_RIGHT_HISTORY_DIR --diff-id quality-registry-history-d190-diff --destination D191_DIFF_DIR --overwrite --format json --output diff.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-audit D191_DIFF_DIR --format json --output diff-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-query D191_DIFF_DIR --change changed --text state --limit 128 --format json --output diff-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-query-audit diff-query.json D191_DIFF_DIR --format json --output diff-query-audit.json
~~~

The repository example exposes the same comparison with bounded change, key,
text, offset, and limit filters:

~~~powershell
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_demo.py D190_LEFT_HISTORY_DIR D190_RIGHT_HISTORY_DIR --diff-id quality-registry-history-d190-diff --destination D191_OUTPUT_DIR
~~~

The HTTP surface is rooted at `/v1/downloaded-data/quality/diff/gate/runtime-history/release-evidence-history/runtime/registry/history/diff/runtime/registry/history/diff/runtime/registry/history/diff`, with `/audit`, `/query`, and `/query-audit` suffixes. Item, items, manifest, summary, diff, audit, query, query-audit, schema, and capability projections remain value-only and path-free.

The focused replay verifies added/unchanged and changed classifications,
registry identity rejection, field filtering, exact-file persistence, canonical
reload, summary tamper rejection, independent `16/16` diff auditing, bounded
query completeness, and independent `12/12` query auditing. The fresh
downloaded-ZIP-derived replay compares blocked and ready D190 histories and
produces `direction=improved`, `state_transition=blocked->ready`,
`item_count=1`, `changed_count=1`, `16/16` diff checks, `26/26` query rows
without truncation, and a `12/12` query audit. Evidence is available at:

- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d191-real-demo/summary.json`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d191-real-demo/diff`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d191-left-check`
- `C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d191-right-check`

## D192 history-diff runtime release evaluation

D192 evaluates an exact four-file D191 history diff against a bounded release
policy.  It keeps the comparison's direction, state transition, counts, and
canonical addresses linked into fifteen independent checks.  A failed budget
or disposition check produces a deterministic `blocked` runtime; a policy that
accepts the comparison produces `ready` evidence without exposing source paths,
records, payload bytes, or private metadata through the value model.

The CLI surface is:

```text
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime D191_DIFF_DIR --destination D192_RELEASE_DIR --overwrite --format json --output runtime.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-audit D192_RELEASE_DIR --format json --output runtime-audit.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-query D192_RELEASE_DIR --limit 128 --format json --output runtime-query.json
python -m glio_noncode downloaded-data-quality-runtime-history-release-evidence-history-runtime-registry-history-diff-runtime-registry-history-diff-runtime-registry-history-diff-runtime-query-audit runtime-query.json D192_RELEASE_DIR --format json --output runtime-query-audit.json
```

The focused demonstration evaluates both sides of the policy boundary and
persists `strict/`, `release/`, `strict-audit.json`, `release-audit.json`,
`release-query.json`, `release-query-audit.json`, and `summary.json`:

```text
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_demo.py D191_DIFF_DIR --destination D192_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run used the downloaded archive named above as the provenance source.
Its D191 comparison contained one accepted improved change across a
`blocked->ready` transition.  D192's default zero-change policy produced
`blocked` at 14/15 checks with only `changed_budget` failing.  The release
policy permitting one change produced `ready` at 15/15; its independent
runtime audit passed 15/15 and its query audit passed 12/12 with 58/58 rows
returned.  The rerun summary is stored outside the repository at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d192-real-demo/summary.json
```

## D193 history-diff runtime registry admission

D193 aggregates exact four-file D192 runtimes into a content-addressed release
registry.  Runtime identity and runtime-address duplicates are rejected, and
the aggregate remains `blocked` whenever any admitted runtime is blocked.  The
registry carries entry-level diff and readiness evidence while keeping source
paths, records, payload bytes, and private metadata outside the public value
boundary.

The focused demonstration keeps the strict and release D192 outputs together:

```text
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_registry_demo.py D192_STRICT_DIR D192_RELEASE_DIR --destination D193_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run admitted `glio-noncode-d192-strict-runtime` and
`glio-noncode-d192-release-runtime`.  It produced two entries, one ready and
one blocked, so the registry was correctly `blocked` and not release-ready.
The independent registry audit passed 16/16 checks; the blocked-state query
returned 22/22 rows without truncation, and its query audit passed 12/12.
Admitting the same runtime twice was rejected by the duplicate identity guard.
The rerun summary is stored outside the repository at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d192-example-real/d193-mixed/summary.json
```

## D194 runtime registry history

D194 records D193 registry snapshots in an append-only, content-addressed
history.  Each append requires the current head address, preserves stable
registry and history identity, rejects duplicate snapshots or registry
addresses, and folds the latest state and release readiness into the history
summary.  Transition labels make the movement from a blocked aggregate to a
ready aggregate directly queryable.

The focused demonstration appends a ready-only D193 registry after the mixed
blocked registry produced by D193:

```text
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_registry_history_demo.py D193_REGISTRY_DIR D192_RELEASE_RUNTIME_DIR --destination D194_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries, latest state `ready`, latest
release readiness `true`, and an `improved` transition.  The independent
history audit passed 16/16 checks; the readiness-filtered query returned 5/5
rows without truncation, and its query audit passed 12/12.  The rerun summary
is stored outside the repository at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d194-example-real/summary.json
```

## D195 runtime registry history diff

D195 compares two exact four-file D194 histories while preserving both history
addresses and classifying each ordinal as added, removed, changed, or
unchanged.  Direction and state-transition folding make the release movement
explicit, while the independent diff and query audits verify the persisted
evidence without trusting the producer projection.

The focused demonstration compares a blocked-only baseline with the
blocked-to-ready candidate:

```text
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_demo.py D194_BASELINE_DIR D194_CANDIDATE_DIR --destination D195_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run classified two history items as one added and one unchanged,
folded the direction to `improved`, and preserved the `blocked->ready` state
transition.  The independent diff audit passed 16/16 checks; the added-item
query returned 2/2 rows without truncation, and its query audit passed 12/12.
The rerun summary is stored outside the repository at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d195-example-real/summary.json
```

## D196 history diff runtime release evaluation

D196 evaluates an exact four-file D195 history diff against explicit release
budgets.  A strict zero-added policy blocks the real comparison, while a
one-added improved-transition policy produces ready evidence.  The runtime
links the diff identity, counts, direction, state transition, policy, check
addresses, summary, and manifest into a value-only four-file artifact.

The focused demonstration evaluates both policy outcomes:

```text
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_demo.py D195_DIFF_DIR --destination D196_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run contained one added item across an `improved` `blocked->ready`
transition.  The strict result was `blocked` at 14/15 checks with only
`added_budget` failing.  The release result was `ready` at 15/15; its runtime
audit passed 15/15 and its query audit passed 12/12 over 58/58 rows.  The
rerun summary is stored outside the repository at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d196-example-real/summary.json
```

## D197 history-diff runtime registry admission

D197 aggregates exact four-file D196 decisions into a content-addressed
registry.  The registry rejects duplicate runtime identity or address and
folds readiness conservatively: one blocked runtime keeps the aggregate
blocked even when another runtime is ready.

The focused demonstration admits the strict and release D196 outputs:

```text
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_demo.py D196_STRICT_DIR D196_RELEASE_DIR --destination D197_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
was `blocked` and not release-ready.  Its independent audit passed 16/16
checks, the blocked-only query returned 22/22 rows without truncation, and the
query audit passed 12/12.  Duplicate runtime admission was rejected.  The
rerun summary is stored outside the repository at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d197-example-real/summary.json
```

## D198 runtime registry history

D198 records D197 registry snapshots in an append-only, content-addressed
history.  The optimistic expected-head guard prevents stale writers, while
stable registry identity, duplicate snapshot/address rejection, transition
folding, and latest readiness make the release movement directly auditable.

The focused demonstration appends a ready-only registry after the mixed
blocked registry:

```text
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_demo.py D197_REGISTRY_DIR D196_RELEASE_RUNTIME_DIR --destination D198_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, latest state `ready`, latest release
readiness `true`, and an `improved` transition.  The independent history
audit passed 16/16 checks; the readiness-filtered query returned 5/5 rows
without truncation, and its query audit passed 12/12.  The rerun summary is
stored outside the repository at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d198-example-real/summary.json
```

## D199 runtime registry history diff

D199 compares exact four-file D198 histories while preserving both history
addresses and classifying each ordinal as added, removed, changed, or
unchanged.  Direction and state-transition folding preserve the release
movement, and independent diff/query audits verify the bounded projections.

The focused demonstration compares a blocked-only baseline with the
blocked-to-ready candidate:

```text
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_demo.py D198_BASELINE_DIR D198_CANDIDATE_DIR --destination D199_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run classified two history items as one added and one unchanged,
folded the direction to `improved`, and preserved `blocked->ready`.  The
independent diff audit passed 16/16 checks; the added-only query returned 2/2
rows without truncation, and its query audit passed 12/12.  The rerun summary
is stored outside the repository at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d199-example-real/summary.json
```

## D200 history-diff runtime release decision

D200 evaluates the exact four-file D199 history diff under two explicit
release policies. The strict policy permits no newly added history item and
therefore blocks the comparison; the release policy permits one added item
only when the folded direction is `improved` and the state changes.

The focused demonstration evaluates and persists both decisions, then audits
the release projection:

```text
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_demo.py D199_DIFF_DIR --destination D200_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run carried one added item across an `improved` `blocked->ready`
transition. The strict result was `blocked` at 14/15 checks with only
`added_budget` failing. The release result was `ready` at 15/15; its runtime
audit passed 15/15 and its query audit passed 12/12 over 58/58 rows. The
rerun summary is stored outside the repository at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d200-example-real/summary.json
```

## D201 runtime registry admission

D201 aggregates exact four-file D200 runtime decisions into a deterministic,
content-addressed registry. Duplicate runtime identity or address is rejected,
and aggregate readiness remains blocked while any admitted runtime is blocked.
The registry exposes independent sixteen-check admission audits and bounded
state-filtered queries with twelve-check query audits.

The focused demonstration admits the strict and release D200 outputs:

```text
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_demo.py D200_STRICT_DIR D200_RELEASE_DIR --destination D201_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
was blocked and not release-ready. Its registry audit passed 16/16 checks, the
blocked-only query returned 22/22 rows without truncation, and its query audit
passed 12/12. Duplicate runtime admission was rejected. The rerun summary is
stored outside the repository at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d201-example-real/summary.json
```

## D202 runtime registry history

D202 records D201 registry snapshots in an append-only, content-addressed
history. The optimistic expected-head guard prevents stale writers, while
stable registry and history identity, duplicate snapshot/address rejection,
transition folding, and latest readiness make release movement auditable.

The focused demonstration appends a ready-only registry after the mixed
blocked registry:

```text
python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_demo.py D201_REGISTRY_DIR D200_RELEASE_RUNTIME_DIR --destination D202_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, latest state `ready`, latest release
readiness `true`, and an `improved` transition. The independent history audit
passed 16/16 checks; the readiness-filtered query returned 5/5 rows without
truncation, and its query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d202-example-real/summary.json
```

## D203 registry history diff

D203 compares exact four-file D202 histories while preserving both history
addresses and classifying each ordinal as added, removed, changed, or
unchanged. Direction and state-transition folding preserve the release
movement, while independent diff and query audits verify the bounded output.
The module uses a compact portable stem because the fully descriptive chain
would exceed Windows path limits; its typed dependency remains the complete
D202 history contract.

The focused demonstration compares a blocked-only baseline with the
blocked-to-ready candidate:

```text
python examples/downloaded_data_quality_d203_history_diff_demo.py D202_BASELINE_DIR D202_CANDIDATE_DIR --destination D203_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run classified two history items as one added and one unchanged,
folded the direction to `improved`, and preserved `blocked->ready`. The
independent diff audit passed 16/16 checks; the added-only query returned 2/2
rows without truncation, and its query audit passed 12/12. The rerun summary
is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d203-example-real/summary.json
```

## D204 history diff runtime release decision

D204 evaluates the exact four-file D203 history diff under strict and release
policies. A zero-addition strict budget blocks the added snapshot, while a
one-addition policy permits only an `improved` transition with a required
state change. The compact module stem keeps the runtime surface portable on
Windows while retaining the full D203 diff dependency.

The focused demonstration evaluates and persists both decisions:

```text
python examples/downloaded_data_quality_d204_history_diff_runtime_demo.py D203_DIFF_DIR --destination D204_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run carried one added item across `improved` `blocked->ready`. The
strict result was `blocked` at 14/15 checks with only `added_budget` failing.
The release result was `ready` at 15/15; its runtime audit passed 15/15 and
its query audit passed 12/12 over 58/58 rows. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d204-example-real/summary.json
```

## D205 history-diff runtime registry admission

D205 aggregates exact four-file D204 strict and release runtimes into a
deterministic, content-addressed registry. Duplicate runtime identity or
address is rejected, and one blocked runtime conservatively keeps the
aggregate blocked. The compact module stem keeps the registry usable on
Windows while preserving independent registry and query audits.

The focused demonstration admits the D204 outputs:

```text
python examples/downloaded_data_quality_d205_runtime_registry_demo.py D204_STRICT_DIR D204_RELEASE_DIR --destination D205_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
was blocked and not release-ready. Its audit passed 16/16 checks, the
blocked-only query returned 22/22 rows without truncation, and its query audit
passed 12/12. Duplicate runtime admission was rejected. The rerun summary is
stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d205-example-real/summary.json
```

## D206 runtime registry history

D206 records D205 registry snapshots in an append-only, content-addressed
history. Optimistic expected-head checks prevent stale writers, duplicate
registry addresses are rejected, and transition folding exposes the latest
state and readiness. The compact module stem keeps this layer portable on
Windows with independent history and query audits.

The focused demonstration appends a ready-only registry after the mixed
blocked registry:

```text
python examples/downloaded_data_quality_d206_runtime_registry_history_demo.py D205_REGISTRY_DIR D204_RELEASE_RUNTIME_DIR --destination D206_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, latest state `ready`, latest release
readiness `true`, and an `improved` transition. The history audit passed 16/16
checks; the readiness-filtered query returned 5/5 rows without truncation, and
its query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d206-example-real/summary.json
```

## D207 registry history diff

D207 compares exact four-file D206 histories while preserving both history
addresses and classifying each ordinal as added, removed, changed, or
unchanged. Direction and state-transition folding preserve release movement,
and independent diff/query audits verify bounded projections.

The focused demonstration compares the blocked-only baseline with the
blocked-to-ready candidate:

```text
python examples/downloaded_data_quality_d207_history_diff_demo.py D206_BASELINE_DIR D206_CANDIDATE_DIR --destination D207_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run classified two history items as one added and one unchanged,
folded the direction to `improved`, and preserved `blocked->ready`. The
independent diff audit passed 16/16 checks; the added-only query returned 2/2
rows without truncation, and its query audit passed 12/12. The rerun summary
is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d207-example-real/summary.json
```

## D208 history diff runtime release decision

D208 evaluates the exact four-file D207 history diff under strict and release
policies. A zero-addition strict budget blocks the added snapshot, while a
one-addition policy permits only an `improved` transition with a required
state change.

The focused demonstration evaluates and persists both decisions:

```text
python examples/downloaded_data_quality_d208_history_diff_runtime_demo.py D207_DIFF_DIR --destination D208_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run carried one added item across `improved` `blocked->ready`. The
strict result was `blocked` at 14/15 checks with only `added_budget` failing.
The release result was `ready` at 15/15; its runtime audit passed 15/15 and
its query audit passed 12/12 over 58/58 rows. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d208-example-real/summary.json
```

## D209 history-diff runtime registry admission

D209 aggregates exact four-file D208 strict and release runtimes into a
deterministic content-addressed registry. Duplicate runtime identity or
address is rejected, and one blocked runtime conservatively keeps the
aggregate blocked. Independent registry and query audits verify the bounded
projections.

The focused demonstration admits the D208 outputs:

```text
python examples/downloaded_data_quality_d209_runtime_registry_demo.py D208_STRICT_DIR D208_RELEASE_DIR --destination D209_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
was blocked and not release-ready. Its audit passed 16/16 checks, the
blocked-only query returned 22/22 rows without truncation, and its query audit
passed 12/12. Duplicate runtime admission was rejected. The rerun summary is
stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d209-example-real/summary.json
```

## D210 runtime registry history

D210 records D209 registry snapshots in an append-only, content-addressed
history. Optimistic expected-head checks prevent stale writers, duplicate
registry addresses are rejected, and transition folding exposes latest state
and readiness through independently audited projections.

The focused demonstration appends a ready-only registry after the mixed
blocked registry:

```text
python examples/downloaded_data_quality_d210_runtime_registry_history_demo.py D209_REGISTRY_DIR D208_RELEASE_RUNTIME_DIR --destination D210_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, latest state `ready`, latest release
readiness `true`, and an `improved` transition. The history audit passed 16/16
checks; the readiness-filtered query returned 5/5 rows without truncation, and
its query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d210-example-real/summary.json
```

## D211 registry history diff

D211 compares exact four-file D210 histories while retaining both history
addresses. It classifies ordinal entries as added, removed, changed, or
unchanged, records field-level deltas, folds release direction and state
transitions, and exposes independently audited bounded projections.

The focused demonstration compares the blocked-only D210 baseline with the
blocked-to-ready D210 candidate:

```text
python examples/downloaded_data_quality_d211_history_diff_demo.py D210_BASELINE_DIR D210_CANDIDATE_DIR --destination D211_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real downloaded-ZIP-derived run produced two items, one added and one
unchanged, with direction `improved` and state transition `blocked->ready`.
The diff audit passed 16/16 checks; the added-filter query returned 2/2 rows
without truncation; and its query audit passed 12/12. The rerun summary is
stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d211-example-real/summary.json
```

## D212 history diff runtime release decision

D212 evaluates the exact four-file D211 history diff under strict and release
policies. Bounded policy checks cover comparison presence and acceptance,
added/removed/changed budgets, direction and state-transition controls,
unchanged handling, conservation, identity, address integrity, policy
integrity, release disposition, and public-boundary compliance.

The focused demonstration persists both decisions and their independent
runtime/query audits:

```text
python examples/downloaded_data_quality_d212_history_diff_runtime_demo.py D211_DIFF_DIR --destination D212_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run carried one added item across `improved` `blocked->ready`. The
strict result was `blocked` at 14/15 checks with only `added_budget` failing;
its integrity audit passed 15/15. The release result was `ready` at 15/15;
its runtime audit passed 15/15 and its query audit passed 12/12 over 58/58
rows. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d212-example-real/summary.json
```

## D214 runtime registry history

D214 records D213 registry snapshots in an append-only, content-addressed
history. Optimistic expected-head checks prevent stale writers, duplicate
snapshot and registry-address submissions are rejected, and transition folding
exposes the latest state and readiness through independently audited
projections.

The focused demonstration appends a ready-only D213 registry after the mixed
blocked registry:

```text
python examples/downloaded_data_quality_d214_runtime_registry_history_demo.py D213_REGISTRY_DIR D212_RELEASE_RUNTIME_DIR --destination D214_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, latest state `ready`, latest release
readiness `true`, and an `improved` transition. The history audit passed 16/16
checks; the readiness-filtered query returned 5/5 rows without truncation; and
its query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d214-example-real/summary.json
```

## D215 registry history diff

D215 compares exact four-file D214 histories while retaining both history
addresses. It classifies ordinal entries as added, removed, changed, or
unchanged, records field-level deltas, folds release direction and state
transitions, and exposes independently audited bounded projections.

The focused demonstration compares the blocked-only D214 baseline with the
blocked-to-ready D214 candidate:

```text
python examples/downloaded_data_quality_d215_history_diff_demo.py D214_BASELINE_DIR D214_CANDIDATE_DIR --destination D215_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real downloaded-ZIP-derived run produced two items, one added and one
unchanged, with direction `improved` and state transition `blocked->ready`.
The diff audit passed 16/16 checks; the added-filter query returned 2/2 rows
without truncation; and its query audit passed 12/12. The rerun summary is
stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d215-example-real/summary.json
```

## D216 history diff runtime release decision

D216 evaluates the exact four-file D215 history diff under strict and release
policies. Bounded policy checks cover comparison presence and acceptance,
added/removed/changed budgets, direction and state-transition controls,
unchanged handling, conservation, identity, address integrity, policy
integrity, release disposition, and public-boundary compliance.

The focused demonstration persists both decisions and their independent
runtime/query audits:

```text
python examples/downloaded_data_quality_d216_history_diff_runtime_demo.py D215_DIFF_DIR --destination D216_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run carried one added item across `improved` `blocked->ready`. The
strict result was `blocked` at 14/15 checks with only `added_budget` failing;
its integrity audit passed 15/15. The release result was `ready` at 15/15;
its runtime audit passed 15/15 and its query audit passed 12/12 over 58/58
rows. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d216-example-real/summary.json
```

## D217 history diff runtime registry admission

D217 aggregates exact four-file D216 strict and release runtimes into a
deterministic content-addressed registry. Runtime identity and address
duplicates are rejected, and any blocked admitted runtime conservatively keeps
the registry blocked until every entry is ready. The registry, entry, and
bounded query projections retain their upstream runtime and diff addresses.

The focused demonstration admits both D216 outputs:

```text
python examples/downloaded_data_quality_d217_runtime_registry_demo.py D216_STRICT_DIR D216_RELEASE_DIR --destination D217_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d217-example-real/summary.json
```

## D218 runtime registry history

D218 records D217 registry snapshots in an append-only, content-addressed
history. Optimistic expected-head checks prevent stale writers, duplicate
snapshot and registry-address submissions are rejected, and transition folding
exposes the latest state and readiness through independently audited
projections.

The focused demonstration appends a ready-only D217 registry after the mixed
blocked registry:

```text
python examples/downloaded_data_quality_d218_runtime_registry_history_demo.py D217_REGISTRY_DIR D216_RELEASE_RUNTIME_DIR --destination D218_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, latest state `ready`, latest release
readiness `true`, and an `improved` transition. The history audit passed 16/16
checks; the readiness-filtered query returned 5/5 rows without truncation; and
its query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d218-example-real/summary.json
```

## D219 registry history diff

D219 compares exact four-file D218 histories while retaining both history
addresses. It classifies ordinal entries as added, removed, changed, or
unchanged, records field-level deltas, folds release direction and state
transitions, and exposes independently audited bounded projections.

The focused demonstration compares the blocked-only D218 baseline with the
blocked-to-ready D218 candidate:

```text
python examples/downloaded_data_quality_d219_history_diff_demo.py D218_BASELINE_DIR D218_CANDIDATE_DIR --destination D219_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real downloaded-ZIP-derived run produced two items, one added and one
unchanged, with direction `improved` and state transition `blocked->ready`.
The diff audit passed 16/16 checks; the added-filter query returned 2/2 rows
without truncation; and its query audit passed 12/12. The rerun summary is
stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d219-example-real/summary.json
```

## D220 history diff runtime release decision

D220 evaluates the exact four-file D219 history diff under strict and release
policies. Bounded policy checks cover comparison presence and acceptance,
added/removed/changed budgets, direction and state-transition controls,
unchanged handling, conservation, identity, address integrity, policy
integrity, release disposition, and public-boundary compliance.

The focused demonstration persists both decisions and their independent
runtime/query audits:

```text
python examples/downloaded_data_quality_d220_history_diff_runtime_demo.py D219_DIFF_DIR --destination D220_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run carried one added item across `improved` `blocked->ready`. The
strict result was `blocked` at 14/15 checks with only `added_budget` failing;
its integrity audit passed 15/15. The release result was `ready` at 15/15;
its runtime audit passed 15/15 and its query audit passed 12/12 over 58/58
rows. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d220-example-real/summary.json
```

## D221 history diff runtime registry admission

D221 aggregates exact four-file D220 strict and release runtimes into a
deterministic content-addressed registry. Runtime identity and address
duplicates are rejected, and any blocked admitted runtime conservatively keeps
the registry blocked until every entry is ready. The registry, entry, and
bounded query projections retain their upstream runtime and diff addresses.

The focused demonstration admits both D220 outputs:

```text
python examples/downloaded_data_quality_d221_runtime_registry_demo.py D220_STRICT_DIR D220_RELEASE_DIR --destination D221_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d221-example-real/summary.json
```

## D222 runtime registry history

D222 records D221 registry snapshots in an append-only, content-addressed
history. Optimistic expected-head checks prevent stale writers, duplicate
snapshot and registry-address submissions are rejected, and transition folding
exposes the latest state and readiness through independently audited
projections.

The focused demonstration appends a ready-only D221 registry after the mixed
blocked registry:

```text
python examples/downloaded_data_quality_d222_runtime_registry_history_demo.py D221_REGISTRY_DIR D220_RELEASE_RUNTIME_DIR --destination D222_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, latest state `ready`, latest release
readiness `true`, and an `improved` transition. The history audit passed 16/16
checks; the readiness-filtered query returned 5/5 rows without truncation; and
its query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d222-example-real/summary.json
```

## D223 registry history diff

D223 compares exact four-file D222 histories while retaining both history
addresses. It classifies ordinal entries as added, removed, changed, or
unchanged, records field-level deltas, folds release direction and state
transitions, and exposes independently audited bounded projections.

The focused demonstration compares the blocked-only D222 baseline with the
blocked-to-ready D222 candidate:

```text
python examples/downloaded_data_quality_d223_history_diff_demo.py D222_BASELINE_DIR D222_CANDIDATE_DIR --destination D223_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real downloaded-ZIP-derived run produced two items, one added and one
unchanged, with direction `improved` and state transition `blocked->ready`.
The diff audit passed 16/16 checks; the added-filter query returned 2/2 rows
without truncation; and its query audit passed 12/12. The rerun summary is
stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d223-example-real/summary.json
```

## D224 history diff runtime release decision

D224 evaluates the exact four-file D223 history diff under strict and release
policies. Bounded policy checks cover comparison presence and acceptance,
added/removed/changed budgets, direction and state-transition controls,
unchanged handling, conservation, identity, address integrity, policy
integrity, release disposition, and public-boundary compliance.

The focused demonstration persists both decisions and their independent
runtime/query audits:

```text
python examples/downloaded_data_quality_d224_history_diff_runtime_demo.py D223_DIFF_DIR --destination D224_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run carried one added item across `improved` `blocked->ready`. The
strict result was `blocked` at 14/15 checks with only `added_budget` failing;
its integrity audit passed 15/15. The release result was `ready` at 15/15;
its runtime audit passed 15/15 and its query audit passed 12/12 over 58/58
rows. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d224-example-real/summary.json
```

## D225 history diff runtime registry admission

D225 aggregates exact four-file D224 strict and release runtimes into a
deterministic content-addressed registry. Runtime identity and address
duplicates are rejected, and any blocked admitted runtime conservatively keeps
the registry blocked until every entry is ready. The registry, entry, and
bounded query projections retain their upstream runtime and diff addresses.

The focused demonstration admits both D224 outputs:

```text
python examples/downloaded_data_quality_d225_runtime_registry_demo.py D224_STRICT_DIR D224_RELEASE_DIR --destination D225_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d225-example-real/summary.json
```

## D226 runtime registry history

D226 records D225 registry snapshots in an append-only, content-addressed
history. Optimistic expected-head checks prevent stale writers, duplicate
snapshot and registry-address submissions are rejected, and transition folding
exposes the latest state and readiness through independently audited
projections.

The focused demonstration appends a ready-only D225 registry after the mixed
blocked registry:

```text
python examples/downloaded_data_quality_d226_runtime_registry_history_demo.py D225_REGISTRY_DIR D224_RELEASE_RUNTIME_DIR --destination D226_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, latest state `ready`, latest release
readiness `true`, and an `improved` transition. The history audit passed 16/16
checks; the readiness-filtered query returned 5/5 rows without truncation; and
its query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d226-example-real/summary.json
```

## D227 registry history diff

D227 compares exact four-file D226 histories while retaining both history
addresses. It classifies ordinal entries as added, removed, changed, or
unchanged, records field-level deltas, folds release direction and state
transitions, and exposes independently audited bounded projections.

The focused demonstration compares the blocked-only D226 baseline with the
blocked-to-ready D226 candidate:

```text
python examples/downloaded_data_quality_d227_history_diff_demo.py D226_BASELINE_DIR D226_CANDIDATE_DIR --destination D227_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real downloaded-ZIP-derived run produced two items, one added and one
unchanged, with direction `improved` and state transition `blocked->ready`.
The diff audit passed 16/16 checks; the added-filter query returned 2/2 rows
without truncation; and its query audit passed 12/12. The rerun summary is
stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d227-example-real/summary.json
```

## D228 history diff runtime release decision

D228 evaluates the exact four-file D227 history diff under strict and release
policies. Bounded policy checks cover comparison presence and acceptance,
added/removed/changed budgets, direction and state-transition controls,
unchanged handling, conservation, identity, address integrity, policy
integrity, release disposition, and public-boundary compliance.

The focused demonstration persists both decisions and their independent
runtime/query audits:

```text
python examples/downloaded_data_quality_d228_history_diff_runtime_demo.py D227_DIFF_DIR --destination D228_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run carried one added item across `improved` `blocked->ready`. The
strict result was `blocked` at 14/15 checks with only `added_budget` failing;
its integrity audit passed 15/15. The release result was `ready` at 15/15;
its runtime audit passed 15/15 and its query audit passed 12/12 over 58/58
rows. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d228-example-real/summary.json
```

## D229 history diff runtime registry admission

D229 aggregates exact four-file D228 strict and release runtimes into a
deterministic content-addressed registry. Runtime identity and address
duplicates are rejected, and any blocked admitted runtime conservatively keeps
the registry blocked until every entry is ready. The registry, entry, and
bounded query projections retain their upstream runtime and diff addresses.

The focused demonstration admits both D228 outputs:

```text
python examples/downloaded_data_quality_d229_runtime_registry_demo.py D228_STRICT_DIR D228_RELEASE_DIR --destination D229_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d229-example-real/summary.json
```

## D230 runtime registry history

D230 records D229 registry snapshots in an append-only, content-addressed
history. Optimistic expected-head checks prevent stale writers, duplicate
snapshot and registry-address submissions are rejected, and transition folding
exposes the latest state and readiness through independently audited
projections.

The focused demonstration appends a ready-only D229 registry after the mixed
blocked registry:

```text
python examples/downloaded_data_quality_d230_runtime_registry_history_demo.py D229_REGISTRY_DIR D228_RELEASE_RUNTIME_DIR --destination D230_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, latest state `ready`, latest release
readiness `true`, and an `improved` transition. The history audit passed 16/16
checks; the readiness-filtered query returned 5/5 rows without truncation; and
its query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d230-example-real/summary.json
```

## D231 registry history diff

D231 compares exact four-file D230 histories while retaining both history
addresses. It classifies ordinal entries as added, removed, changed, or
unchanged, records field-level deltas, folds release direction and state
transitions, and exposes independently audited bounded projections.

The focused demonstration compares the blocked-only D230 baseline with the
blocked-to-ready D230 candidate:

```text
python examples/downloaded_data_quality_d231_history_diff_demo.py D230_BASELINE_DIR D230_CANDIDATE_DIR --destination D231_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real downloaded-ZIP-derived run produced two items, one added and one
unchanged, with direction `improved` and state transition `blocked->ready`.
The diff audit passed 16/16 checks; the added-filter query returned 2/2 rows
without truncation; and its query audit passed 12/12. The rerun summary is
stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d231-example-real/summary.json
```

## D232 history diff runtime release decision

D232 evaluates the exact four-file D231 history diff under strict and release
policies. Bounded policy checks cover comparison presence and acceptance,
added/removed/changed budgets, direction and state-transition controls,
unchanged handling, conservation, identity, address integrity, policy
integrity, release disposition, and public-boundary compliance.

The focused demonstration persists both decisions and their independent
runtime/query audits:

```text
python examples/downloaded_data_quality_d232_history_diff_runtime_demo.py D231_DIFF_DIR --destination D232_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run carried one added item across `improved` `blocked->ready`. The
strict result was `blocked` at 14/15 checks with only `added_budget` failing;
its integrity audit passed 15/15. The release result was `ready` at 15/15;
its runtime audit passed 15/15 and its query audit passed 12/12 over 58/58
rows. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d232-example-real/summary.json
```

## D233 history diff runtime registry admission

D233 aggregates exact four-file D232 strict and release runtimes into a
deterministic content-addressed registry. Runtime identity and address
duplicates are rejected, and any blocked admitted runtime conservatively keeps
the registry blocked until every entry is ready. The registry, entry, and
bounded query projections retain their upstream runtime and diff addresses.

The focused demonstration admits both D232 outputs:

```text
python examples/downloaded_data_quality_d233_runtime_registry_demo.py D232_STRICT_DIR D232_RELEASE_DIR --destination D233_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d233-example-real/summary.json
```

## D234 runtime registry history

D234 records D233 registry snapshots in an append-only, content-addressed
history. Optimistic expected-head checks prevent stale writers, duplicate
snapshot and registry-address submissions are rejected, and transition folding
exposes the latest state and readiness through independently audited
projections.

The focused demonstration appends a ready-only D233 registry after the mixed
blocked registry:

```text
python examples/downloaded_data_quality_d234_runtime_registry_history_demo.py D233_REGISTRY_DIR D232_RELEASE_RUNTIME_DIR --destination D234_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, latest state `ready`, latest release
readiness `true`, and an `improved` transition. The history audit passed 16/16
checks; the readiness-filtered query returned 5/5 rows without truncation; and
its query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d234-example-real/summary.json
```

## D235 registry history diff

D235 compares exact four-file D234 histories while retaining both history
addresses. It classifies ordinal entries as added, removed, changed, or
unchanged, records field-level deltas, folds release direction and state
transitions, and exposes independently audited bounded projections.

The focused demonstration compares the blocked-only D234 baseline with the
blocked-to-ready D234 candidate:

```text
python examples/downloaded_data_quality_d235_history_diff_demo.py D234_BASELINE_DIR D234_CANDIDATE_DIR --destination D235_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real downloaded-ZIP-derived run produced two items, one added and one
unchanged, with direction `improved` and state transition `blocked->ready`.
The diff audit passed 16/16 checks; the added-filter query returned 2/2 rows
without truncation; and its query audit passed 12/12. The rerun summary is
stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d235-example-real/summary.json
```

## D236 history diff runtime

D236 evaluates a D235 history diff under explicit release policies. It keeps
strict and release decisions separate, budgets added, removed, and changed
items, checks direction and state transitions, persists exact four-file
runtimes, and exposes independently audited runtime and bounded query
projections.

The focused demonstration evaluates the real D235 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d236_history_diff_runtime_demo.py D235_DIFF_DIR --destination D236_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced a strict blocked decision at 14/15 checks because its
zero-added budget rejected one added item. The release policy passed 15/15,
was release-ready, and produced the `blocked->ready` transition. Its runtime
audit passed 15/15; the complete release query returned 58/58 rows without
truncation; and its query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d236-example-real/summary.json
```

## D237 runtime registry admission

D237 admits typed D236 strict and release runtimes into a deterministic
content-addressed registry. Runtime identity and address duplicates are
rejected, aggregate state remains blocked while any admitted decision is
blocked, and registry, audit, and bounded query projections retain their
upstream runtime addresses.

The focused demonstration admits both real D236 runtime directories:

```text
python examples/downloaded_data_quality_d237_runtime_registry_demo.py D236_STRICT_DIR D236_RELEASE_DIR --destination D237_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run admitted two entries: one ready and one blocked. The aggregate
state was `blocked` with `release_ready=false`, and duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d237-example-real/summary.json
```

## D238 runtime registry history

D238 records D237 registry snapshots in an append-only, content-addressed
history. Stable registry and history identities, optimistic expected-head
checks, duplicate snapshot/address rejection, and deterministic transition
folding keep the timeline auditable while exposing latest state and readiness
through bounded projections.

The focused demonstration appends a ready-only D237 registry after the mixed
blocked registry:

```text
python examples/downloaded_data_quality_d238_runtime_registry_history_demo.py D237_REGISTRY_DIR D236_RELEASE_RUNTIME_DIR --destination D238_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real downloaded-ZIP-derived run produced two snapshots, latest state
`ready`, latest release readiness `true`, and an `improved` transition. The
history audit passed 16/16 checks; the readiness query returned 5/5 rows
without truncation; and its query audit passed 12/12. The rerun summary is
stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d238-example-real/summary.json
```

## D239 runtime registry history diff

D239 compares exact four-file D238 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections.

The focused demonstration compares the blocked-only D238 baseline with the
two-snapshot D238 candidate:

```text
python examples/downloaded_data_quality_d239_history_diff_demo.py D238_BASELINE_DIR D238_CANDIDATE_DIR --destination D239_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real downloaded-ZIP-derived run produced two items, one added and one
changed, with direction `improved` and state transition `blocked->ready`.
The diff audit passed 16/16 checks; the added-filter query returned 2/2 rows
without truncation; and its query audit passed 12/12. The rerun summary is
stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d239-example-real/summary.json
```

## D240 history diff runtime

D240 evaluates an exact four-file D239 history diff under explicit release
policies. It preserves independent strict and release decisions, budgets
added, removed, and changed snapshots separately, and records fifteen runtime
checks plus twelve query-audit checks. Persistence remains canonical and
tamper-detecting, while bounded queries expose the complete release decision
without truncation.

The focused demonstration evaluates the real D239 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d240_history_diff_runtime_demo.py D239_DIFF_DIR --destination D240_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one changed, with direction
`improved` and state transition `blocked->ready`. The strict policy remained
blocked at 13/15 checks because it allows neither addition nor change. The
release policy allowed one of each and became ready at 15/15. Its runtime
audit passed 15/15; the release query returned 58/58 rows without truncation;
and its query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d240-example-real/summary.json
```

## D241 runtime registry admission

D241 aggregates exact four-file D240 runtime decisions into a deterministic,
content-addressed registry. It retains the upstream runtime and diff
addresses for every entry, folds readiness conservatively so one blocked
decision keeps the registry blocked, rejects duplicate runtime identity, and
provides independent registry and bounded-query audits.

The focused demonstration admits the real D240 strict and release outputs:

```text
python examples/downloaded_data_quality_d241_runtime_registry_demo.py D240_STRICT_DIR D240_RELEASE_DIR --destination D241_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d241-example-real/summary.json
```

## D242 runtime registry history

D242 records D241 registry decisions in an append-only history with stable
history identity, optimistic expected-head appends, duplicate snapshot and
registry-address guards, and deterministic transition folding. It persists
exact four-file histories, retains the latest state and readiness projection,
and exposes independently audited bounded history queries.

The focused demonstration records the real D241 mixed registry and appends a
ready-only D241 registry built from the D240 release runtime:

```text
python examples/downloaded_data_quality_d242_runtime_registry_history_demo.py D241_REGISTRY_DIR D240_RELEASE_RUNTIME_DIR --destination D242_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with `latest_release_ready`
true. The history audit passed 16/16 checks; the ready query returned 5/5
rows without truncation; and its query audit passed 12/12. The rerun summary
is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d242-example-real/summary.json
```

## D243 runtime registry history diff

D243 compares exact four-file D242 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection.

The focused demonstration compares a blocked-only D242 baseline with the
two-entry D242 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d243_history_diff_demo.py D242_BASELINE_DIR D242_CANDIDATE_DIR --destination D243_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d243-example-real/summary.json
```

## D244 history diff runtime

D244 evaluates an exact four-file D243 history diff under explicit release
policies. It preserves independent strict and release decisions, budgets
added, removed, and changed snapshots separately, and records fifteen runtime
checks plus twelve query-audit checks. Persistence remains canonical and
tamper-detecting, while bounded queries expose the complete release decision
without truncation.

The focused demonstration evaluates the real D243 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d244_history_diff_runtime_demo.py D243_DIFF_DIR --destination D244_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The strict policy remained
blocked at 14/15 checks because it disallows additions. The release policy
allowed one addition and became ready at 15/15. Its runtime audit passed
15/15; the release query returned 58/58 rows without truncation; and its query
audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d244-example-real/summary.json
```

## D245 runtime registry admission

D245 aggregates exact four-file D244 runtime decisions into a deterministic,
content-addressed registry. It retains upstream runtime and diff addresses for
each entry, folds readiness conservatively so one blocked decision keeps the
registry blocked, rejects duplicate runtime identity, and provides independent
registry and bounded-query audits.

The focused demonstration admits the real D244 strict and release outputs:

```text
python examples/downloaded_data_quality_d245_runtime_registry_demo.py D244_STRICT_DIR D244_RELEASE_DIR --destination D245_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d245-example-real/summary.json
```

## D246 runtime registry history

D246 records D245 registry decisions in an append-only history with stable
history identity, optimistic expected-head appends, duplicate snapshot and
registry-address guards, and deterministic transition folding. It persists
exact four-file histories, retains the latest state and readiness projection,
and exposes independently audited bounded history queries.

The focused demonstration records the real D245 mixed registry and appends a
ready-only D245 registry built from the D244 release runtime:

```text
python examples/downloaded_data_quality_d246_runtime_registry_history_demo.py D245_REGISTRY_DIR D244_RELEASE_RUNTIME_DIR --destination D246_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with `latest_release_ready`
true. The history audit passed 16/16 checks; the ready query returned 5/5
rows without truncation; and its query audit passed 12/12. The rerun summary
is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d246-example-real/summary.json
```

## D247 runtime registry history diff

D247 compares exact four-file D246 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection.

The focused demonstration compares a blocked-only D246 baseline with the
two-entry D246 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d247_history_diff_demo.py D246_BASELINE_DIR D246_CANDIDATE_DIR --destination D247_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d247-example-real/summary.json
```

## D248 history diff runtime

D248 evaluates an exact four-file D247 history diff under explicit release
policies. It preserves independent strict and release decisions, budgets
added, removed, and changed snapshots separately, and records fifteen runtime
checks plus twelve query-audit checks. Persistence remains canonical and
tamper-detecting, while bounded queries expose the complete release decision
without truncation.

The focused demonstration evaluates the real D247 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d248_history_diff_runtime_demo.py D247_DIFF_DIR --destination D248_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The strict policy remained
blocked at 14/15 checks because it disallows additions. The release policy
allowed one addition and became ready at 15/15. Its runtime audit passed
15/15; the release query returned 58/58 rows without truncation; and its query
audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d248-example-real/summary.json
```

## D249 runtime registry admission

D249 aggregates exact four-file D248 runtime decisions into a deterministic,
content-addressed registry. It retains upstream runtime and diff addresses for
each entry, folds readiness conservatively so one blocked decision keeps the
registry blocked, rejects duplicate runtime identity, and provides independent
registry and bounded-query audits.

The focused demonstration admits the real D248 strict and release outputs:

```text
python examples/downloaded_data_quality_d249_runtime_registry_demo.py D248_STRICT_DIR D248_RELEASE_DIR --destination D249_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d249-example-real/summary.json
```

## D250 runtime registry history

D250 records D249 registry decisions in an append-only history with stable
history identity, optimistic expected-head appends, duplicate snapshot and
registry-address guards, and deterministic transition folding. It persists
exact four-file histories, retains the latest state and readiness projection,
and exposes independently audited bounded history queries.

The focused demonstration records the real D249 mixed registry and appends a
ready-only D249 registry built from the D248 release runtime:

```text
python examples/downloaded_data_quality_d250_runtime_registry_history_demo.py D249_REGISTRY_DIR D248_RELEASE_RUNTIME_DIR --destination D250_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with `latest_release_ready`
true. The history audit passed 16/16 checks; the ready query returned 5/5
rows without truncation; and its query audit passed 12/12. The rerun summary
is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d250-example-real/summary.json
```

## D251 runtime registry history diff

D251 compares exact four-file D250 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. It also publishes a compact version and boundary
namespace so deep compatibility chains remain within bounded public text
contracts.

The focused demonstration compares a blocked-only D250 baseline with the
two-entry D250 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d251_history_diff_demo.py D250_BASELINE_DIR D250_CANDIDATE_DIR --destination D251_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d251-example-real/summary.json
```

## D252 history diff runtime

D252 evaluates an exact four-file D251 history diff under explicit release
policies. It preserves independent strict and release decisions, budgets
added, removed, and changed snapshots separately, and records fifteen runtime
checks plus twelve query-audit checks. The compact D251 namespace remains
bounded through the runtime layer, while persistence and tamper detection stay
canonical.

The focused demonstration evaluates the real D251 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d252_history_diff_runtime_demo.py D251_DIFF_DIR --destination D252_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The strict policy remained
blocked at 14/15 checks because it disallows additions. The release policy
allowed one addition and became ready at 15/15. Its runtime audit passed
15/15; the release query returned 58/58 rows without truncation; and its query
audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d252-example-real/summary.json
```

## D253 runtime registry admission

D253 aggregates exact four-file D252 runtime decisions into a deterministic,
content-addressed registry. It retains upstream runtime and diff addresses for
each entry, folds readiness conservatively so one blocked decision keeps the
registry blocked, rejects duplicate runtime identity, and provides independent
registry and bounded-query audits.

The focused demonstration admits the real D252 strict and release outputs:

```text
python examples/downloaded_data_quality_d253_runtime_registry_demo.py D252_STRICT_DIR D252_RELEASE_DIR --destination D253_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d253-example-real/summary.json
```

## D254 runtime registry history

D254 records D253 registry decisions in an append-only history with stable
history identity, optimistic expected-head appends, duplicate snapshot and
registry-address guards, and deterministic transition folding. It persists
exact four-file histories, retains the latest state and readiness projection,
and exposes independently audited bounded history queries.

The focused demonstration records the real D253 mixed registry and appends a
ready-only D253 registry built from the D252 release runtime:

```text
python examples/downloaded_data_quality_d254_runtime_registry_history_demo.py D253_REGISTRY_DIR D252_RELEASE_RUNTIME_DIR --destination D254_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with `latest_release_ready`
true. The history audit passed 16/16 checks; the ready query returned 5/5
rows without truncation; and its query audit passed 12/12. The rerun summary
is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d254-example-real/summary.json
```

## D255 runtime registry history diff

D255 compares exact four-file D254 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. It preserves compact version and boundary namespaces so
deep compatibility chains remain within bounded public text contracts.

The focused demonstration compares a blocked-only D254 baseline with the
two-entry D254 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d255_history_diff_demo.py D254_BASELINE_DIR D254_CANDIDATE_DIR --destination D255_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d255-example-real/summary.json
```

## D256 history diff runtime

D256 evaluates an exact four-file D255 history diff under explicit release
policies. It preserves independent strict and release decisions, budgets
added, removed, and changed snapshots separately, and records fifteen runtime
checks plus twelve query-audit checks. The compact D255 namespace remains
bounded through the runtime layer, while persistence and tamper detection stay
canonical.

The focused demonstration evaluates the real D255 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d256_history_diff_runtime_demo.py D255_DIFF_DIR --destination D256_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The strict policy remained
blocked at 14/15 checks because it disallows additions. The release policy
allowed one addition and became ready at 15/15. Its runtime audit passed
15/15; the release query returned 58/58 rows without truncation; and its query
audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d256-example-real/summary.json
```

## D257 runtime registry admission

D257 aggregates exact four-file D256 runtime decisions into a deterministic,
content-addressed registry. It retains upstream runtime and diff addresses for
each entry, folds readiness conservatively so one blocked decision keeps the
registry blocked, rejects duplicate runtime identity, and provides independent
registry and bounded-query audits.

The focused demonstration admits the real D256 strict and release outputs:

```text
python examples/downloaded_data_quality_d257_runtime_registry_demo.py D256_STRICT_DIR D256_RELEASE_DIR --destination D257_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d257-example-real/summary.json
```

## D258 runtime registry history

D258 records D257 registry decisions in an append-only history with stable
history identity, optimistic expected-head appends, duplicate snapshot and
registry-address guards, and deterministic transition folding. It persists
exact four-file histories, retains the latest state and readiness projection,
and exposes independently audited bounded history queries.

The focused demonstration records the real D257 mixed registry and appends a
ready-only D257 registry built from the D256 release runtime:

```text
python examples/downloaded_data_quality_d258_runtime_registry_history_demo.py D257_REGISTRY_DIR D256_RELEASE_RUNTIME_DIR --destination D258_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with `latest_release_ready`
true. The history audit passed 16/16 checks; the ready query returned 5/5
rows without truncation; and its query audit passed 12/12. The rerun summary
is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d258-example-real/summary.json
```

## D259 runtime registry history diff

D259 compares exact four-file D258 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. It preserves compact version and boundary namespaces so
deep compatibility chains remain within bounded public text contracts.

The focused demonstration compares a blocked-only D258 baseline with the
two-entry D258 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d259_history_diff_demo.py D258_BASELINE_DIR D258_CANDIDATE_DIR --destination D259_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d259-example-real/summary.json
```

## D260 history diff runtime

D260 evaluates an exact four-file D259 history diff under explicit release
policies. It preserves independent strict and release decisions, budgets
added, removed, and changed snapshots separately, and records fifteen runtime
checks plus twelve query-audit checks. The compact D259 namespace remains
bounded through the runtime layer, while persistence and tamper detection stay
canonical.

The focused demonstration evaluates the real D259 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d260_history_diff_runtime_demo.py D259_DIFF_DIR --destination D260_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The strict policy remained
blocked at 14/15 checks because it disallows additions. The release policy
allowed one addition and became ready at 15/15. Its runtime audit passed
15/15; the release query returned 58/58 rows without truncation; and its query
audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d260-example-real/summary.json
```

## D261 runtime registry admission

D261 aggregates exact four-file D260 runtime decisions into a deterministic,
content-addressed registry. It retains upstream runtime and diff addresses for
each entry, folds readiness conservatively so one blocked decision keeps the
registry blocked, rejects duplicate runtime identity, and provides independent
registry and bounded-query audits.

The focused demonstration admits the real D260 strict and release outputs:

```text
python examples/downloaded_data_quality_d261_runtime_registry_demo.py D260_STRICT_DIR D260_RELEASE_DIR --destination D261_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d261-example-real/summary.json
```

## D262 runtime registry history

D262 records D261 registry decisions in an append-only history with stable
history identity, optimistic expected-head appends, duplicate snapshot and
registry-address guards, and deterministic transition folding. It persists
exact four-file histories, retains the latest state and readiness projection,
and exposes independently audited bounded history queries.

The focused demonstration records the real D261 mixed registry and appends a
ready-only D261 registry built from the D260 release runtime:

```text
python examples/downloaded_data_quality_d262_runtime_registry_history_demo.py D261_REGISTRY_DIR D260_RELEASE_RUNTIME_DIR --destination D262_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with `latest_release_ready`
true. The history audit passed 16/16 checks; the ready query returned 5/5
rows without truncation; and its query audit passed 12/12. The rerun summary
is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d262-example-real/summary.json
```

## D263 runtime registry history diff

D263 compares exact four-file D262 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. It preserves compact version and boundary namespaces so
deep compatibility chains remain within bounded public text contracts.

The focused demonstration compares a blocked-only D262 baseline with the
two-entry D262 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d263_history_diff_demo.py D262_BASELINE_DIR D262_CANDIDATE_DIR --destination D263_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d263-example-real/summary.json
```

## D264 history diff runtime

D264 evaluates an exact four-file D263 history diff under independent strict
and release policies. It preserves fifteen bounded policy checks, separate
added/removed/changed budgets, direction and transition controls, canonical
four-file persistence, runtime audits, and complete bounded release queries.

The focused demonstration evaluates the real D263 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d264_history_diff_runtime_demo.py D263_DIFF_DIR --destination D264_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run retained two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The strict policy rejected
the added-item budget at 14/15 checks while its independent runtime audit
passed 15/15. The release policy accepted the same diff at 15/15; its runtime
audit passed 15/15, and the release query returned 58/58 rows without
truncation with a 12/12 query audit. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d264-example-real/summary.json
```

## D265 runtime registry

D265 aggregates exact four-file D264 strict and release runtimes into a
deterministic content-addressed registry. It retains each upstream runtime
and diff address, rejects duplicate runtime identities and addresses, and
folds readiness conservatively so any blocked runtime keeps the registry
blocked. Independent registry and bounded-query audits protect the aggregate
and its persisted projections.

The focused demonstration admits both D264 outputs derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d265_runtime_registry_demo.py D264_STRICT_DIR D264_RELEASE_DIR --destination D265_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one blocked and one ready, so the registry
state was `blocked` and `release_ready` was false. Duplicate runtime admission
was rejected. The registry audit passed 16/16 checks; the blocked query
returned 22/22 rows without truncation; and its query audit passed 12/12. The
rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d265-example-real/summary.json
```

## D266 runtime registry history

D266 records D265 registry decisions in an append-only history with stable
history and registry identity, optimistic expected-head appends, duplicate
snapshot and registry-address guards, and deterministic transition folding.
It persists exact four-file histories and exposes independently audited
history and readiness projections while retaining the latest state and
release-readiness result.

The focused demonstration records the real D265 mixed registry and appends a
ready-only registry built from the D264 release runtime:

```text
python examples/downloaded_data_quality_d266_runtime_registry_history_demo.py D265_REGISTRY_DIR D264_RELEASE_RUNTIME_DIR --destination D266_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with
`latest_release_ready` true. The history audit passed 16/16 checks; the ready
query returned 5/5 rows without truncation; and its query audit passed 12/12.
The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d266-example-real/summary.json
```

## D267 runtime registry history diff

D267 compares exact four-file D266 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. Its compact version and boundary namespace keeps the
deep compatibility chain within bounded public text contracts.

The focused demonstration compares a blocked-only D266 baseline with the
blocked-to-ready D266 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d267_history_diff_demo.py D266_BASELINE_DIR D266_CANDIDATE_DIR --destination D267_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d267-example-real/summary.json
```

## D268 history diff runtime

D268 evaluates an exact four-file D267 history diff under independent strict
and release policies. It preserves fifteen bounded policy checks, separate
added/removed/changed budgets, direction and transition controls, canonical
four-file persistence, runtime audits, and complete bounded release queries.

The focused demonstration evaluates the real D267 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d268_history_diff_runtime_demo.py D267_DIFF_DIR --destination D268_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run retained two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The strict policy rejected
the added-item budget at 14/15 checks while its independent runtime audit
passed 15/15. The release policy accepted the same diff at 15/15; its runtime
audit passed 15/15, and the release query returned 58/58 rows without
truncation with a 12/12 query audit. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d268-example-real/summary.json
```

## D269 runtime registry

D269 aggregates exact four-file D268 strict and release runtimes into a
deterministic content-addressed registry. It retains each upstream runtime
and diff address, rejects duplicate runtime identities and addresses, and
folds readiness conservatively so any blocked runtime keeps the registry
blocked. Independent registry and bounded-query audits protect the aggregate
and its persisted projections.

The focused demonstration admits both D268 outputs derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d269_runtime_registry_demo.py D268_STRICT_DIR D268_RELEASE_DIR --destination D269_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one blocked and one ready, so the registry
state was `blocked` and `release_ready` was false. Duplicate runtime admission
was rejected. The registry audit passed 16/16 checks; the blocked query
returned 22/22 rows without truncation; and its query audit passed 12/12. The
rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d269-example-real/summary.json
```

## D270 runtime registry history

D270 records D269 registry decisions in an append-only history with stable
history and registry identity, optimistic expected-head appends, duplicate
snapshot and registry-address guards, and deterministic transition folding.
It persists exact four-file histories and exposes independently audited
history and readiness projections while retaining the latest state and
release-readiness result.

The focused demonstration records the real D269 mixed registry and appends a
ready-only registry built from the D268 release runtime:

```text
python examples/downloaded_data_quality_d270_runtime_registry_history_demo.py D269_REGISTRY_DIR D268_RELEASE_RUNTIME_DIR --destination D270_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with
`latest_release_ready` true. The history audit passed 16/16 checks; the ready
query returned 5/5 rows without truncation; and its query audit passed 12/12.
The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d270-example-real/summary.json
```

## D271 runtime registry history diff

D271 compares exact four-file D270 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. Its compact version and boundary namespace keeps the
deep compatibility chain within bounded public text contracts.

The focused demonstration compares a blocked-only D270 baseline with the
blocked-to-ready D270 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d271_history_diff_demo.py D270_BASELINE_DIR D270_CANDIDATE_DIR --destination D271_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d271-example-real/summary.json
```

## D272 history diff runtime

D272 evaluates an exact four-file D271 history diff under independent strict
and release policies. It preserves fifteen bounded policy checks, separate
added/removed/changed budgets, direction and transition controls, canonical
four-file persistence, runtime audits, and complete bounded release queries.

The focused demonstration evaluates the real D271 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d272_history_diff_runtime_demo.py D271_DIFF_DIR --destination D272_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run retained two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The strict policy rejected
the added-item budget at 14/15 checks while its independent runtime audit
passed 15/15. The release policy accepted the same diff at 15/15; its runtime
audit passed 15/15, and the release query returned 58/58 rows without
truncation with a 12/12 query audit. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d272-example-real/summary.json
```

## D273 runtime registry

D273 aggregates exact four-file D272 strict and release runtimes into a
deterministic content-addressed registry. It retains each upstream runtime
and diff address, rejects duplicate runtime identities and addresses, and
folds readiness conservatively so any blocked runtime keeps the registry
blocked. Independent registry and bounded-query audits protect the aggregate
and its persisted projections.

The focused demonstration admits both D272 outputs derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d273_runtime_registry_demo.py D272_STRICT_DIR D272_RELEASE_DIR --destination D273_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one blocked and one ready, so the registry
state was `blocked` and `release_ready` was false. Duplicate runtime admission
was rejected. The registry audit passed 16/16 checks; the blocked query
returned 22/22 rows without truncation; and its query audit passed 12/12. The
rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d273-example-real/summary.json
```

## D274 runtime registry history

D274 records D273 registry decisions in an append-only history with stable
history and registry identity, optimistic expected-head appends, duplicate
snapshot and registry-address guards, and deterministic transition folding.
It persists exact four-file histories and exposes independently audited
history and readiness projections while retaining the latest state and
release-readiness result.

The focused demonstration records the real D273 mixed registry and appends a
ready-only registry built from the D272 release runtime:

```text
python examples/downloaded_data_quality_d274_runtime_registry_history_demo.py D273_REGISTRY_DIR D272_RELEASE_RUNTIME_DIR --destination D274_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with
`latest_release_ready` true. The history audit passed 16/16 checks; the ready
query returned 5/5 rows without truncation; and its query audit passed 12/12.
The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d274-example-real/summary.json
```

## D275 runtime registry history diff

D275 compares exact four-file D274 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. Its compact version and boundary namespace keeps the
deep compatibility chain within bounded public text contracts.

The focused demonstration compares a blocked-only D274 baseline with the
blocked-to-ready D274 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d275_history_diff_demo.py D274_BASELINE_DIR D274_CANDIDATE_DIR --destination D275_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d275-example-real/summary.json
```

## D276 history diff runtime

D276 evaluates an exact four-file D275 history diff under independent strict
and release policies. It preserves fifteen bounded policy checks, separate
added/removed/changed budgets, direction and transition controls, canonical
four-file persistence, runtime audits, and complete bounded release queries.

The focused demonstration evaluates the real D275 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d276_history_diff_runtime_demo.py D275_DIFF_DIR --destination D276_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run retained two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The strict policy rejected
the added-item budget at 14/15 checks while its independent runtime audit
passed 15/15. The release policy accepted the same diff at 15/15; its runtime
audit passed 15/15, and the release query returned 58/58 rows without
truncation with a 12/12 query audit. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d276-example-real/summary.json
```

## D277 runtime registry

D277 aggregates exact four-file D276 strict and release runtimes into a
deterministic content-addressed registry. It retains each upstream runtime
and diff address, rejects duplicate runtime identities and addresses, and
folds readiness conservatively so any blocked runtime keeps the registry
blocked. Independent registry and bounded-query audits protect the aggregate
and its persisted projections.

The focused demonstration admits both D276 outputs derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d277_runtime_registry_demo.py D276_STRICT_DIR D276_RELEASE_DIR --destination D277_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one blocked and one ready, so the registry
state was `blocked` and `release_ready` was false. Duplicate runtime admission
was rejected. The registry audit passed 16/16 checks; the blocked query
returned 22/22 rows without truncation; and its query audit passed 12/12. The
rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d277-example-real/summary.json
```

## D278 runtime registry history

D278 records D277 registry decisions in an append-only history with stable
history and registry identity, optimistic expected-head appends, duplicate
snapshot and registry-address guards, and deterministic transition folding.
It persists exact four-file histories and exposes independently audited
history and readiness projections while retaining the latest state and
release-readiness result.

The focused demonstration records the real D277 mixed registry and appends a
ready-only registry built from the D276 release runtime:

```text
python examples/downloaded_data_quality_d278_runtime_registry_history_demo.py D277_REGISTRY_DIR D276_RELEASE_RUNTIME_DIR --destination D278_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with
`latest_release_ready` true. The history audit passed 16/16 checks; the ready
query returned 5/5 rows without truncation; and its query audit passed 12/12.
The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d278-example-real/summary.json
```

## D279 runtime registry history diff

D279 compares exact four-file D278 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. Its compact version and boundary namespace keeps the
deep compatibility chain within bounded public text contracts.

The focused demonstration compares a blocked-only D278 baseline with the
blocked-to-ready D278 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d279_history_diff_demo.py D278_BASELINE_DIR D278_CANDIDATE_DIR --destination D279_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d279-example-real/summary.json
```

## D280 history diff runtime

D280 evaluates an exact four-file D279 history diff under independent strict
and release policies. It preserves fifteen bounded policy checks, separate
added/removed/changed budgets, direction and transition controls, canonical
four-file persistence, runtime audits, and complete bounded release queries.

The focused demonstration evaluates the real D279 diff derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d280_history_diff_runtime_demo.py D279_DIFF_DIR --destination D280_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run retained two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The strict policy rejected
the added-item budget at 14/15 checks while its independent runtime audit
passed 15/15. The release policy accepted the same diff at 15/15; its runtime
audit passed 15/15, and the release query returned 58/58 rows without
truncation with a 12/12 query audit. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d280-example-real/summary.json
```

## D281 runtime registry

D281 aggregates exact four-file D280 strict and release runtimes into a
deterministic content-addressed registry. It retains each upstream runtime
and diff address, rejects duplicate runtime identities and addresses, and
folds readiness conservatively so any blocked runtime keeps the registry
blocked. Independent registry and bounded-query audits protect the aggregate
and its persisted projections.

The focused demonstration admits both D280 outputs derived from the
downloaded source archive:

```text
python examples/downloaded_data_quality_d281_runtime_registry_demo.py D280_STRICT_DIR D280_RELEASE_DIR --destination D281_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one blocked and one ready, so the registry
state was `blocked` and `release_ready` was false. Duplicate runtime admission
was rejected. The registry audit passed 16/16 checks; the blocked query
returned 22/22 rows without truncation; and its query audit passed 12/12. The
rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d281-example-real/summary.json
```

## D282 runtime registry history

D282 records D281 registry decisions in an append-only history with stable
history and registry identity, optimistic expected-head appends, duplicate
snapshot and registry-address guards, and deterministic transition folding.
It persists exact four-file histories and exposes independently audited
history and readiness projections while retaining the latest state and
release-readiness result.

The focused demonstration records the real D281 mixed registry and appends a
ready-only registry built from the D280 release runtime:

```text
python examples/downloaded_data_quality_d282_runtime_registry_history_demo.py D281_REGISTRY_DIR D280_RELEASE_RUNTIME_DIR --destination D282_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with
`latest_release_ready` true. The history audit passed 16/16 checks; the ready
query returned 5/5 rows without truncation; and its query audit passed 12/12.
The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d282-example-real/summary.json
```

## D283 runtime registry history diff

D283 compares exact four-file D282 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. Its compact version and boundary namespace keeps the
deep compatibility chain within bounded public text contracts.

The focused demonstration compares a blocked-only D282 baseline with the
blocked-to-ready D282 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d283_history_diff_demo.py D282_BASELINE_DIR D282_CANDIDATE_DIR --destination D283_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d283-example-real/summary.json
```

## D284 history diff runtime evaluation

D284 evaluates a D283 history diff under independent strict and release
policies. It enforces bounded added, removed, and changed budgets, direction,
acceptance, state-transition, and unchanged-item controls, then emits a
deterministic `ready` or `blocked` runtime with fifteen checks. Runtime,
audit, query, and query-audit artifacts retain their upstream diff address,
support canonical reload, and reject tampering.

The focused demonstration runs both policies against the real D283 diff:

```text
python examples/downloaded_data_quality_d284_history_diff_runtime_demo.py D283_DIFF_DIR --destination D284_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run intentionally blocked strict admission on the one-added-item
budget while release admission was ready. Both runtime audits passed 15/15;
the release projection returned 58/58 rows without truncation; and its query
audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d284-example-real/summary.json
```

## D285 runtime registry admission

D285 aggregates multiple D284 runtimes into a deterministic content-addressed
registry. It rejects duplicate runtime identities and content addresses,
folds `ready` and `blocked` entries conservatively, and retains each runtime
address in bounded registry projections. Exact four-file persistence,
sixteen-check registry audits, twelve-check query audits, canonical reload,
and tamper rejection are included.

The focused demonstration admits the real strict and release D284 runtimes:

```text
python examples/downloaded_data_quality_d285_runtime_registry_demo.py D284_STRICT_DIR D284_RELEASE_DIR --destination D285_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real registry contained two entries: one ready and one blocked. The
aggregate was conservatively `blocked`, duplicate-runtime admission was
rejected, the registry audit passed 16/16 checks, the blocked query returned
22/22 rows without truncation, and its query audit passed 12/12. The rerun
summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d285-example-real/summary.json
```

## D286 runtime registry history

D286 records D285 registry decisions in an append-only history with stable
history and registry identity, optimistic expected-head appends, duplicate
snapshot and registry-address guards, and deterministic transition folding.
It persists exact four-file histories and exposes independently audited
history and readiness projections while retaining the latest state and
release-readiness result.

The focused demonstration records the real D285 mixed registry and appends a
ready-only registry built from the D284 release runtime:

```text
python examples/downloaded_data_quality_d286_runtime_registry_history_demo.py D285_REGISTRY_DIR D284_RELEASE_RUNTIME_DIR --destination D286_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with
`latest_release_ready` true. The history audit passed 16/16 checks; the ready
query returned 5/5 rows without truncation; and its query audit passed 12/12.
The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d286-example-real/summary.json
```

## D287 runtime registry history diff

D287 compares exact four-file D286 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. Its compact version and boundary namespace keeps the
deep compatibility chain within bounded public text contracts.

The focused demonstration compares a blocked-only D286 baseline with the
blocked-to-ready D286 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d287_history_diff_demo.py D286_BASELINE_DIR D286_CANDIDATE_DIR --destination D287_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d287-example-real/summary.json
```

## D288 history diff runtime evaluation

D288 evaluates a D287 history diff under independent strict and release
policies. It enforces bounded added, removed, and changed budgets, direction,
acceptance, state-transition, and unchanged-item controls, then emits a
deterministic `ready` or `blocked` runtime with fifteen checks. Runtime,
audit, query, and query-audit artifacts retain their upstream diff address,
support canonical reload, and reject tampering.

The focused demonstration runs both policies against the real D287 diff:

```text
python examples/downloaded_data_quality_d288_history_diff_runtime_demo.py D287_DIFF_DIR --destination D288_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run intentionally blocked strict admission on the one-added-item
budget while release admission was ready. Both runtime audits passed 15/15;
the release projection returned 58/58 rows without truncation; and its query
audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d288-example-real/summary.json
```

## D289 runtime registry admission

D289 aggregates multiple D288 runtimes into a deterministic content-addressed
registry. It rejects duplicate runtime identities and content addresses,
folds `ready` and `blocked` entries conservatively, and retains each runtime
address in bounded registry projections. Exact four-file persistence,
sixteen-check registry audits, twelve-check query audits, canonical reload,
and tamper rejection are included.

The focused demonstration admits the real strict and release D288 runtimes:

```text
python examples/downloaded_data_quality_d289_runtime_registry_demo.py D288_STRICT_DIR D288_RELEASE_DIR --destination D289_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real registry contained two entries: one ready and one blocked. The
aggregate was conservatively `blocked`, duplicate-runtime admission was
rejected, the registry audit passed 16/16 checks, the blocked query returned
22/22 rows without truncation, and its query audit passed 12/12. The rerun
summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d289-example-real/summary.json
```

## D290 runtime registry history

D290 records D289 registry decisions in an append-only history with stable
history and registry identity, optimistic expected-head appends, duplicate
snapshot and registry-address guards, and deterministic transition folding.
It persists exact four-file histories and exposes independently audited
history and readiness projections while retaining the latest state and
release-readiness result.

The focused demonstration records the real D289 mixed registry and appends a
ready-only registry built from the D288 release runtime:

```text
python examples/downloaded_data_quality_d290_runtime_registry_history_demo.py D289_REGISTRY_DIR D288_RELEASE_RUNTIME_DIR --destination D290_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with
`latest_release_ready` true. The history audit passed 16/16 checks; the ready
query returned 5/5 rows without truncation; and its query audit passed 12/12.
The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d290-example-real/summary.json
```

## D291 runtime registry history diff

D291 compares exact four-file D290 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. Its compact version and boundary namespace keeps the
deep compatibility chain within bounded public text contracts.

The focused demonstration compares a blocked-only D290 baseline with the
blocked-to-ready D290 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d291_history_diff_demo.py D290_BASELINE_DIR D290_CANDIDATE_DIR --destination D291_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d291-example-real/summary.json
```

## D292 history diff runtime evaluation

D292 evaluates a D291 history diff under independent strict and release
policies. It enforces bounded added, removed, and changed budgets, direction,
acceptance, state-transition, and unchanged-item controls, then emits a
deterministic `ready` or `blocked` runtime with fifteen checks. Runtime,
audit, query, and query-audit artifacts retain their upstream diff address,
support canonical reload, and reject tampering.

The focused demonstration runs both policies against the real D291 diff:

```text
python examples/downloaded_data_quality_d292_history_diff_runtime_demo.py D291_DIFF_DIR --destination D292_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run intentionally blocked strict admission on the one-added-item
budget while release admission was ready. Both runtime audits passed 15/15;
the release projection returned 58/58 rows without truncation; and its query
audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d292-example-real/summary.json
```

## D293 runtime registry admission

D293 aggregates multiple D292 runtimes into a deterministic content-addressed
registry. It rejects duplicate runtime identities and content addresses,
folds `ready` and `blocked` entries conservatively, and retains each runtime
address in bounded registry projections. Exact four-file persistence,
sixteen-check registry audits, twelve-check query audits, canonical reload,
and tamper rejection are included.

The focused demonstration admits the real strict and release D292 runtimes:

```text
python examples/downloaded_data_quality_d293_runtime_registry_demo.py D292_STRICT_DIR D292_RELEASE_DIR --destination D293_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real registry contained two entries: one ready and one blocked. The
aggregate was conservatively `blocked`, duplicate-runtime admission was
rejected, the registry audit passed 16/16 checks, the blocked query returned
22/22 rows without truncation, and its query audit passed 12/12. The rerun
summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d293-example-real/summary.json
```

## D294 runtime registry history

D294 records D293 registry decisions in an append-only history with stable
history and registry identity, optimistic expected-head appends, duplicate
snapshot and registry-address guards, and deterministic transition folding.
It persists exact four-file histories and exposes independently audited
history and readiness projections while retaining the latest state and
release-readiness result.

The focused demonstration records the real D293 mixed registry and appends a
ready-only registry built from the D292 release runtime:

```text
python examples/downloaded_data_quality_d294_runtime_registry_history_demo.py D293_REGISTRY_DIR D292_RELEASE_RUNTIME_DIR --destination D294_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two history entries and an `improved` transition from
blocked to ready. The latest state was `ready` with
`latest_release_ready` true. The history audit passed 16/16 checks; the ready
query returned 5/5 rows without truncation; and its query audit passed 12/12.
The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d294-example-real/summary.json
```

## D295 runtime registry history diff

D295 compares exact four-file D294 histories while retaining both history
addresses. It classifies ordinal snapshots as added, removed, changed, or
unchanged, records field-level deltas, folds direction and state transitions,
and exposes independently audited bounded projections with canonical reload
and tamper rejection. Its compact version and boundary namespace keeps the
deep compatibility chain within bounded public text contracts.

The focused demonstration compares a blocked-only D294 baseline with the
blocked-to-ready D294 candidate derived from the downloaded source archive:

```text
python examples/downloaded_data_quality_d295_history_diff_demo.py D294_BASELINE_DIR D294_CANDIDATE_DIR --destination D295_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two items, one added and one unchanged, with direction
`improved` and state transition `blocked->ready`. The diff audit passed 16/16
checks; the added-filter query returned 2/2 rows without truncation; and its
query audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d295-example-real/summary.json
```

## D296 history diff runtime evaluation

D296 evaluates a D295 history diff under independent strict and release
policies. It enforces bounded added, removed, and changed budgets, direction,
acceptance, state-transition, and unchanged-item controls, then emits a
deterministic `ready` or `blocked` runtime with fifteen checks. Runtime,
audit, query, and query-audit artifacts retain their upstream diff address,
support canonical reload, and reject tampering.

The focused demonstration runs both policies against the real D295 diff:

```text
python examples/downloaded_data_quality_d296_history_diff_runtime_demo.py D295_DIFF_DIR --destination D296_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run intentionally blocked strict admission on the one-added-item
budget while release admission was ready. Both runtime audits passed 15/15;
the release projection returned 58/58 rows without truncation; and its query
audit passed 12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d296-example-real/summary.json
```

## D297 runtime registry admission

D297 aggregates multiple D296 runtimes into a deterministic content-addressed
registry. It rejects duplicate runtime identities and content addresses,
folds `ready` and `blocked` entries conservatively, and retains each runtime
address in bounded registry projections. Exact four-file persistence,
sixteen-check registry audits, twelve-check query audits, canonical reload,
and tamper rejection are included.

The focused demonstration admits the real strict and release D296 runtimes:

```text
python examples/downloaded_data_quality_d297_runtime_registry_demo.py D296_STRICT_DIR D296_RELEASE_DIR --destination D297_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real registry contained two entries: one ready and one blocked. The
aggregate was conservatively `blocked`, duplicate-runtime admission was
rejected, the registry audit passed 16/16 checks, the blocked query returned
22/22 rows without truncation, and its query audit passed 12/12. The rerun
summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d297-example-real/summary.json
```

## D213 history diff runtime registry admission

D213 aggregates exact four-file D212 strict and release runtimes into a
deterministic content-addressed registry. Runtime identity and address
duplicates are rejected, and any blocked admitted runtime conservatively keeps
the registry blocked until every entry is ready. The registry, entry, and
bounded query projections each retain their upstream runtime and diff
addresses.

The focused demonstration admits both D212 outputs:

```text
python examples/downloaded_data_quality_d213_runtime_registry_demo.py D212_STRICT_DIR D212_RELEASE_DIR --destination D213_OUTPUT_DIR --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
```

The real run produced two entries, one ready and one blocked, so the registry
state was `blocked` and `release_ready` was `false`. Duplicate runtime
admission was rejected. The registry audit passed 16/16 checks; the blocked
query returned 22/22 rows without truncation; and its query audit passed
12/12. The rerun summary is stored at:

```text
C:/Users/murar/AppData/Local/Temp/glio-noncode-d188-real-demo-20260921/d213-example-real/summary.json
```
