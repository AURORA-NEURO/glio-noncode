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
