# Downloaded-data ingestion

The downloaded-data plane makes a local ZIP inspectable without turning the
package into executable configuration. It accepts a downloaded archive as
input, catalogs safe structured members, applies an explicit selection, parses
bounded records, records immutable lineage, audits the result, and persists an
offline runtime that can be loaded and queried again.

The ZIP is data. Repository source files, old repositories, generated code,
instructions, and prose are never used as a framework for this plane.

## Real ZIP demo

The checked-in demo accepts the product rebuild ZIP as downloaded input. It
selects the 17 data-bearing members and leaves the seven schema documents and
the OpenAPI YAML document outside the record set. This is intentional: schema
declarations describe a boundary, while the ingestion command operates on
selected data records.

```powershell
python examples/downloaded_data_ingestion_demo.py `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  artifacts/downloaded-data-ingestion-demo
```

The current ZIP produces 25 cataloged structured members, 17 selected
members, and 4,030 parsed records. The demo returns a 40-row inspection page,
while the persisted batch retains all 4,030 records. It reports the source,
content addresses, selection, record count, completion state, audit result,
release readiness, and five redacted record metadata samples. It does not print
the full values to the terminal.

The output layout is:

```text
artifacts/downloaded-data-ingestion-demo/
  summary.json
  runtime-audit.json
  runtime-audit.md
  runtime/
    manifest.json
    catalog.json
    selection.json
    batch.json
    audit.json
    query.json
    query-audit.json
    runtime.json
```

The `runtime` directory is an exact eight-file replay bundle. Every artifact
is content-addressed, and the manifest links the component addresses. The
runtime audit recomputes the component relationships and checks that the
replayed runtime is release-ready.

## Value-free structural profiling

After ingestion, the profile plane derives a second public projection from
the typed batch. It reports member and field counts, object/array/scalar
shapes, all seven JSON value-type counts, field presence and missingness,
serialized size ranges, and bounded distinct-value counts. It intentionally
does not copy source values into the profile, query, audit, or persisted
profile runtime.

Run the real downloaded ZIP through both replay planes:

```powershell
python examples/downloaded_data_profile_demo.py `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  artifacts/downloaded-data-profile-demo
```

The profile demo repeats the explicit 17-member data selection, retains all
4,030 records in the ingestion runtime, and emits a value-free structural
summary. The profile runtime is an exact six-file bundle:

```text
artifacts/downloaded-data-profile-demo/
  summary.json
  profile-runtime-audit.json
  profile-runtime-audit.md
  ingestion-runtime/
    manifest.json ... runtime.json
  profile-runtime/
    manifest.json
    profile.json
    audit.json
    query.json
    query-audit.json
    runtime.json
```

The profile runtime can be inspected and queried directly:

```powershell
glio-noncode downloaded-data-profile `
  artifacts/downloaded-data-profile-demo/ingestion-runtime `
  --format markdown --output profile.md

glio-noncode downloaded-data-profile-query `
  artifacts/downloaded-data-profile-demo/profile-runtime `
  --resource fields --field-name status --format csv --output fields.csv

glio-noncode downloaded-data-profile-audit `
  artifacts/downloaded-data-profile-demo/profile-runtime --format summary

glio-noncode downloaded-data-profile-runtime-audit `
  artifacts/downloaded-data-profile-demo/profile-runtime --format summary
```

Profile query resources are `summary`, `members`, `fields`, and `types`.
Filters support member name, data kind, field name, value type, text, offset,
and limit. A zero-count type row is retained as a canonical fact, so the
seven-type inventory remains stable even when a type is absent from the
download.

## Value-free schema contract

The contract plane turns profile observations into a stable data dictionary.
It adds required and optional fields, member-local field inventories, member
coverage, dominant types, type consistency, and explicit field states:
`empty`, `sparse`, `uniform`, `mixed`, and `complete`. A `sparse` field is
observed in only part of the record domain. A `mixed` field has more than one
observed JSON value type. The contract never carries a source value; it only
publishes bounded structural facts and content addresses.

The contract is independently auditable. The audit recomputes field/type
conservation, member coverage, member-local required/optional/mixed counts,
nested addresses, exact public fields, and mapping round-trip behavior. The
contract query exposes `summary`, `types`, `members`, `fields`, and `issues`
resources. The `issues` resource turns sparse and mixed fields into a bounded
review queue without re-reading source data.

Run the end-to-end contract demo against the supplied downloaded ZIP:

```powershell
python examples/downloaded_data_contract_demo.py `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  artifacts/downloaded-data-contract-demo
```

The current archive produces a value-free contract over 4,030 records, 17
selected members, and 136 fields. The member-level selection excludes schema
and OpenAPI declaration files as data, while those files remain valid catalog
input. The contract reports 136 sparse fields across the multi-member record
domain, 0 globally required fields, 0 globally mixed fields, and 98 fields
whose dominant observed type is string. Member-local inventories still report
the fields required within each individual member. All 12 contract checks, all
10 query checks, and all 13 runtime-closure checks pass in the demo.

The contract runtime is an exact six-file replay bundle:

```text
artifacts/downloaded-data-contract-demo/
  summary.json
  runtime-audit.json
  runtime-audit.md
  contract-runtime/
    manifest.json
    contract.json
    audit.json
    query.json
    query-audit.json
    runtime.json
```

Inspect and query the persisted contract:

```powershell
glio-noncode downloaded-data-profile-contract `
  artifacts/downloaded-data-contract-demo/contract-runtime `
  --format markdown --output contract.md

glio-noncode downloaded-data-profile-contract-query `
  artifacts/downloaded-data-contract-demo/contract-runtime `
  --resource issues --state sparse --limit 25 `
  --format csv --output schema-issues.csv

glio-noncode downloaded-data-profile-contract-audit `
  artifacts/downloaded-data-contract-demo/contract-runtime --format summary

glio-noncode downloaded-data-profile-contract-runtime-audit `
  artifacts/downloaded-data-contract-demo/contract-runtime --format summary
```

The contract query supports member name, data kind, field name, dominant
value type, state, required, type-consistent, text, offset, and limit filters.
All query pages are content-addressed and retain stable resource ordering.
Unknown fields, altered nested addresses, and extra runtime files fail closed.

The contract HTTP routes mirror the CLI:

```text
GET /v1/downloaded-data/profile/contract?input=<profile-json-or-runtime-directory>
GET /v1/downloaded-data/profile/contract/audit?input=<contract-json-or-runtime-directory>
GET /v1/downloaded-data/profile/contract/query?input=<contract-json-or-runtime-directory>&resource=issues
GET /v1/downloaded-data/profile/contract/query-audit?input=<query-json-or-contract-runtime-directory>
GET /v1/downloaded-data/profile/contract/runtime?input=<ingestion-json-or-runtime-directory>
GET /v1/downloaded-data/profile/contract/runtime/audit?input=<contract-runtime-directory>
GET /v1/downloaded-data/profile/contract/schema
GET /v1/downloaded-data/profile/contract/query/schema
GET /v1/downloaded-data/profile/contract/runtime/schema
```

## Value-free schema evolution diff

The contract diff plane compares two inferred contracts without reading or
publishing source record values. It emits one deterministic transition for
each field, member, and canonical JSON type. A transition is `added`,
`removed`, `changed`, or `unchanged`; changed rows list only the structural
attributes that differ, such as coverage counts, type counts, member
coverage, or field-state metadata. The diff audit independently checks
transition conservation, nested addresses, public-boundary safety, and
mapping replay. The diff query adds bounded `summary`, `fields`, `members`,
and `types` resources with change, identity, attribute, text, offset, and
limit filters.

Run the real comparison against the supplied archive:

```powershell
python examples/downloaded_data_contract_diff_demo.py `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  artifacts/downloaded-data-contract-diff-demo
```

The demo compares all 17 selected structured members with a second selection
that omits two members. The current archive produces 4,030 versus 3,965
records, 136 versus 123 fields, 17 versus 15 members, and 160 value-free
transition items. The transition breakdown is 13 removed and 123 changed
fields, 2 removed members, and 4 changed plus 3 unchanged canonical type
rows. The query returns its first 25 rows with truncation enabled. The diff,
query, and runtime audits all pass, and the six-file diff runtime is release
ready.

The exact-file output is:

```text
artifacts/downloaded-data-contract-diff-demo/
  summary.json
  left-contract.json
  right-contract.json
  runtime-audit.json
  runtime-audit.md
  diff-runtime/
    manifest.json
    diff.json
    audit.json
    query.json
    query-audit.json
    runtime.json
```

Inspect, filter, and audit the persisted comparison:

```powershell
glio-noncode downloaded-data-profile-contract-diff `
  artifacts/downloaded-data-contract-diff-demo/left-contract.json `
  artifacts/downloaded-data-contract-diff-demo/right-contract.json `
  --format markdown --output diff.md

glio-noncode downloaded-data-profile-contract-diff-query `
  artifacts/downloaded-data-contract-diff-demo/diff-runtime `
  --resource fields --change removed --limit 25 `
  --format csv --output removed-fields.csv

glio-noncode downloaded-data-profile-contract-diff-audit `
  artifacts/downloaded-data-contract-diff-demo/diff-runtime --format summary

glio-noncode downloaded-data-profile-contract-diff-runtime-audit `
  artifacts/downloaded-data-contract-diff-demo/diff-runtime --format summary
```

The HTTP surface mirrors the CLI. A diff accepts `left_input` and
`right_input`; all other diff operations accept `input` as a JSON document or
the exact runtime directory:

```text
GET /v1/downloaded-data/profile/contract/diff?left_input=<left-contract>&right_input=<right-contract>
GET /v1/downloaded-data/profile/contract/diff/audit?input=<diff-or-runtime>
GET /v1/downloaded-data/profile/contract/diff/query?input=<diff-or-runtime>&resource=fields&change=removed
GET /v1/downloaded-data/profile/contract/diff/query-audit?input=<query-or-runtime>
GET /v1/downloaded-data/profile/contract/diff/runtime?left_input=<left-contract>&right_input=<right-contract>
GET /v1/downloaded-data/profile/contract/diff/runtime/audit?input=<diff-runtime>
GET /v1/downloaded-data/profile/contract/diff/schema
GET /v1/downloaded-data/profile/contract/diff/query/schema
GET /v1/downloaded-data/profile/contract/diff/runtime/schema
```

## Policy-governed history-diff release review

The policy plane turns a value-free history diff into an explicit release
decision. A policy records the allowed directions, candidate-readiness
requirement, added/removed/changed limits, transition-delta limits, and state
progression requirement. The evaluator emits ten addressed rules and maps
them to `eligible`/`promote`, `review`/`hold`, or `blocked`/`block`.

Run the policy review against the same downloaded archive:

```powershell
python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  artifacts/downloaded-data-contract-resolution-history-diff-policy-demo
```

The current archive's improved history diff passes all ten policy rules. The
independent policy audit passes 12 checks, the bounded policy query audit
passes 10 checks, and the runtime audit passes 16 checks. The runtime is
release-ready only when the policy evaluation, source diff audit, query audit,
and public-boundary checks all pass. Review thresholds can deliberately turn a
diff into a held or blocked decision without exposing source record values.

The exact policy runtime contains eight files:

```text
artifacts/downloaded-data-contract-resolution-history-diff-policy-demo/
  summary.json
  policy-audit.json
  policy-audit.md
  runtime-audit.json
  runtime-audit.md
  policy-runtime/
    manifest.json
    diff.json
    policy.json
    evaluation.json
    audit.json
    query.json
    query-audit.json
    runtime.json
```

For a smaller handoff boundary, package the verified runtime into an exact
five-file policy-review package. It retains the runtime, independent policy
audit, independent runtime audit, derived summary, and a manifest of their
addresses. Package reloads verify canonical bytes, nested links, file names,
and the public value-free boundary before accepting the handoff. The current
downloaded archive produces a complete package, a 14-check package audit, and
a 10-check package-query audit.

```text
policy-package/
  manifest.json
  runtime.json
  policy-audit.json
  runtime-audit.json
  summary.json
```

Multiple package handoffs can be admitted to a deterministic registry. The
registry keeps package identities, policy/runtime receipt links, decisions,
acceptance, and release readiness while remaining free of source values. Its
state folds to `empty`, `ready`, `review`, or `blocked`; the real archive demo
admits two addressed promote packages and produces a 15-check registry audit.

```text
policy-package-registry/
  manifest.json
  registry.json
  entries.json
  summary.json
```

Inspect the persisted decision and its independent receipts:

```powershell
glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy `
  artifacts/downloaded-data-contract-resolution-history-diff-policy-demo/policy-runtime `
  --format markdown --output policy-evaluation.md

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-query `
  artifacts/downloaded-data-contract-resolution-history-diff-policy-demo/policy-runtime `
  --resource rules --rule-id removed-limit --format csv --output policy-rule.csv

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-audit `
  artifacts/downloaded-data-contract-resolution-history-diff-policy-demo/policy-runtime --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-runtime-audit `
  artifacts/downloaded-data-contract-resolution-history-diff-policy-demo/policy-runtime --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-audit `
  artifacts/downloaded-data-contract-resolution-history-diff-policy-demo/policy-package --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-query `
  artifacts/downloaded-data-contract-resolution-history-diff-policy-demo/policy-package `
  --resource policy-rules --text removed-limit --format markdown

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-audit `
  artifacts/downloaded-data-contract-resolution-history-diff-policy-demo/policy-package-registry --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-query `
  artifacts/downloaded-data-contract-resolution-history-diff-policy-demo/policy-package-registry `
  --resource entries --decision promote --format markdown
```

The policy HTTP routes mirror the CLI:

```text
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy?input=<diff-or-runtime>&allow_direction=improved&allow_direction=unchanged
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/audit?input=<evaluation-or-runtime>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/query?input=<evaluation-or-runtime>&resource=rules&rule_id=removed-limit
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/query-audit?input=<query-or-runtime>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/runtime?input=<diff-or-runtime>&destination=<directory>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/runtime/audit?input=<policy-runtime>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package?input=<policy-runtime>&destination=<directory>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/audit?input=<policy-package>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/query?input=<policy-package>&resource=policy-rules&text=removed-limit
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/query-audit?input=<policy-package-query>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry?input=<policy-package>&input=<second-policy-package>&destination=<directory>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/audit?input=<policy-package-registry>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/query?input=<policy-package-registry>&resource=entries&decision=promote
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/query-audit?input=<policy-package-registry-query>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/schema
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/evaluation-schema
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/runtime/schema
```

### Policy package registry history and diffs

Registry histories retain append-only, addressed snapshots of one logical
package registry. Each observation stores only package counts, readiness,
decisions, state, ancestry, and a deterministic `initial`, `improved`,
`regressed`, `unchanged`, or `changed` transition. The history is persisted as
an exact four-file value-free package:

```text
policy-package-registry-history/
  manifest.json
  history.json
  entries.json
  summary.json
```

Two histories can be compared by ordinal snapshot identity. The diff reports
`added`, `removed`, `changed`, and `unchanged` snapshots, signed transition
deltas, state transition, and an `improved`, `regressed`, `mixed`, or `unchanged`
direction. It is also an exact four-file package:

```text
policy-package-registry-history-diff/
  manifest.json
  diff.json
  items.json
  summary.json
```

Build and inspect the history and diff with bounded queries and independent
audits:

```powershell
glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history `
  policy-package-registry policy-package-registry-next `
  --history-id policy-package-registry-history --destination policy-package-registry-history --format markdown

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-query `
  policy-package-registry-history --resource transitions --transition improved --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff `
  policy-package-registry-history-baseline policy-package-registry-history `
  --diff-id policy-package-registry-history-diff --destination policy-package-registry-history-diff --format markdown

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff-query `
  policy-package-registry-history-diff --resource added --change added --format summary
```

The HTTP equivalents are:

```text
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/history?input=<registry>&input=<next-registry>&destination=<directory>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/history/audit?input=<history>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/history/query?input=<history>&resource=transitions&transition=improved
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/history/query-audit?input=<history-query>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/history/diff?left=<baseline-history>&right=<candidate-history>&destination=<directory>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/history/diff/audit?input=<history-diff>
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/history/diff/query?input=<history-diff>&resource=added&change=added
GET /v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/history/diff/query-audit?input=<history-diff-query>
```

## CLI workflow

Catalog the ZIP first when you want to inspect available members:

```powershell
glio-noncode downloaded-data-catalog `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  --format markdown --output catalog.md
```

Run ingestion with explicit member names. Repeat `--member` for every member
you want to read. The command also supports repeatable `--suffix` and
`--data-kind` selectors.

```powershell
glio-noncode downloaded-data-ingest `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  --member GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20/03_CAPABILITIES/CORE_CAPABILITIES_256.csv `
  --member GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20/06_DATA_AND_EVIDENCE/DATA_SOURCE_REGISTRY.csv `
  --resource summary --resource records --resource lineage `
  --destination downloaded-data-runtime `
  --format summary
```

For a repeatable saved runtime, provide an output directory. Persistence is
atomic: the completed temporary directory is moved into place only after all
eight files have been written and validated.

```powershell
glio-noncode downloaded-data-ingest `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  --suffix .csv --record-limit 100000 `
  --destination downloaded-data-runtime --format json `
  --output downloaded-data-runtime.json
```

Use a smaller explicit `--record-limit` when an input may exceed the bounded
record budget. The default policy is `reject`, which prevents a partial
runtime from being mistaken for a complete result. `--overflow-policy
truncate` is available when partial inspection is desired; the resulting batch
is marked incomplete, retains `dropped_record_count`, and is not release-ready.

Audit, query, and inspect the persisted result:

```powershell
glio-noncode downloaded-data-ingest-audit downloaded-data-runtime `
  --format markdown --output ingestion-audit.md

glio-noncode downloaded-data-ingest-query downloaded-data-runtime `
  --resource records --data-kind delimited --limit 25 `
  --format csv --output records.csv

glio-noncode downloaded-data-ingest-query downloaded-data-runtime `
  --resource lineage --member-name DATA_SOURCE_REGISTRY.csv `
  --format markdown --output lineage.md

glio-noncode downloaded-data-ingest-runtime-audit downloaded-data-runtime `
  --format json --output runtime-audit.json
```

The query resources are `summary`, `records`, `lineage`, and `values`.
Filters include record ID, member name, data kind, shape, field name, and
bounded text search. Pagination is explicit through `--offset` and `--limit`.
The summary row is always useful even when a filter returns an empty page;
empty pages are valid and remain auditable.

## Comparing two ingestions

Ingest two downloaded snapshots with stable member selections, then compare
their record values by the deterministic key `member_name#source_row`:

```powershell
glio-noncode downloaded-data-ingest-diff `
  --left downloaded-data-runtime-left `
  --right downloaded-data-runtime-right `
  --format json --output downloaded-data-diff.json

glio-noncode downloaded-data-ingest-diff-query downloaded-data-diff.json `
  --resource changed --changed-field value `
  --format csv --output changed.csv

glio-noncode downloaded-data-ingest-diff-audit downloaded-data-diff.json `
  --format summary
```

Diff items are classified as `added`, `removed`, `changed`, or `unchanged`.
Changed items include the exact field names that differ and both bounded values;
unchanged items do not duplicate values. Diff and diff-query contracts have
their own audits and content addresses, so comparison output is not an
unverified convenience view.

## Compatibility and release gating

To turn a structural contract diff into an explicit release decision, run the
compatibility plane. It evaluates field, member, and type changes using only
the value-free snapshots already present in the diff:

```powershell
glio-noncode downloaded-data-profile-contract-compatibility `
  downloaded-data-contract-diff.json --format markdown

glio-noncode downloaded-data-profile-contract-compatibility-runtime `
  downloaded-data-contract-diff.json --resource summary --resource findings `
  --limit 25 --destination compatibility-runtime --format summary

glio-noncode downloaded-data-profile-contract-compatibility-runtime-audit `
  compatibility-runtime --format summary
```

The default policy permits safe and review outcomes, permits any number of
review findings, and permits no breaking findings. Optional fields added to a
contract are safe; required fields added, required fields removed, type
changes, member removals, and member shape changes are breaking. Optional
field removals, coverage changes, member additions, and type-distribution
changes remain review items. The gate therefore reports `eligible/promote`,
`review/hold`, or `blocked/block` without ever looking at source values.

The compatibility runtime is an exact seven-file handoff:
`manifest.json`, `diff.json`, `gate.json`, `audit.json`, `query.json`,
`query-audit.json`, and `runtime.json`. Each nested artifact is independently
replayed and addressed; tampering, extra files, missing files, and mismatched
addresses fail closed. The runnable
[`downloaded_data_contract_compatibility_demo.py`](../examples/downloaded_data_contract_compatibility_demo.py)
applies the policy to the supplied GLIO-NONCODE ZIP as data only. Its current
selection intentionally produces a blocked decision while the independent
compatibility, query, and runtime audits remain inspectable and accepted.

The local API mirrors this plane at
`/v1/downloaded-data/profile/contract/compatibility`, `/audit`, `/query`,
`/query-audit`, `/runtime`, and `/runtime/audit`, with schemas and capabilities
under the corresponding `/profile/contract/compatibility/...` paths. All
query views are bounded and support outcome, resource, identity, reason, text,
offset, and limit filters.

### Compatibility remediation planning

The remediation plane converts every compatibility finding into a deterministic,
value-free action. Safe findings become low-priority `none` actions; removed
members become critical `restore` actions; requiredness changes become
`migrate`; type or shape changes become `repair`; resource or distribution
uncertainty becomes `investigate`; and other non-safe findings become `review`.
Every non-safe action is required, and any breaking finding blocks the plan.

```powershell
glio-noncode downloaded-data-profile-contract-compatibility-remediation `
  compatibility-gate.json --format markdown --output remediation.md

glio-noncode downloaded-data-profile-contract-compatibility-remediation-audit `
  remediation.json --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-query `
  remediation.json --resource actions --action restore --required --limit 25 --format json

glio-noncode downloaded-data-profile-contract-compatibility-remediation-runtime `
  compatibility-gate.json --resource summary --resource actions --limit 25 `
  --destination remediation-runtime --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-runtime-audit `
  remediation-runtime --format summary
```

The remediation runtime is an exact seven-file handoff:
`manifest.json`, `gate.json`, `plan.json`, `audit.json`, `query.json`,
`query-audit.json`, and `runtime.json`. The gate retains the structural diff
address, while the plan retains one addressed action and evidence set for
every finding. Independent plan, query, and runtime audits replay counts,
ordering, linkage, public-boundary rules, and canonical addresses. The runnable
[`downloaded_data_contract_remediation_demo.py`](../examples/downloaded_data_contract_remediation_demo.py)
performs the full flow on the supplied GLIO-NONCODE ZIP as data only.

The local API mirrors this plane at
`/v1/downloaded-data/profile/contract/compatibility/remediation`, `/audit`,
`/query`, `/query-audit`, `/runtime`, and `/runtime/audit`, with action, plan,
query-row, runtime, audit, and capability schemas under the matching
`/profile/contract/compatibility/remediation/...` paths.

### Remediation resolution and closure

After a remediation plan is reviewed, the resolution plane records only
addressed action references, bounded statuses, evidence addresses, and a
rationale. It never records source values or operator identity. By default,
required actions are `pending` and safe `none` actions are `not_applicable`:

```powershell
glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution `
  remediation-plan.json --status-update <action-address>=resolved `
  --format markdown --output resolution.md

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-query `
  resolution.json --resource entries --status pending --required --limit 25

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-runtime `
  remediation-plan.json --status-update <action-address>=resolved `
  --destination resolution-runtime --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-runtime-audit `
  resolution-runtime --format summary
```

The ledger derives `clear/promote` only when every required action is resolved;
pending or waived actions produce `review/hold`, and any rejected action
produces `blocked/block`. The resolution runtime is an exact seven-file
handoff: `manifest.json`, `plan.json`, `resolution.json`, `audit.json`,
`query.json`, `query-audit.json`, and `runtime.json`. The runnable
[`downloaded_data_contract_resolution_demo.py`](../examples/downloaded_data_contract_resolution_demo.py)
shows the default pending state on the supplied ZIP. The API exposes the same
behavior at `/v1/downloaded-data/profile/contract/compatibility/remediation/resolution`
and its `/audit`, `/query`, `/query-audit`, `/runtime`, and `/runtime/audit`
children.

### Longitudinal resolution history

When a plan is revisited after review, the history plane appends a new
value-free resolution snapshot instead of replacing the prior disposition. It
retains only resolution and plan addresses, bounded counts, state, decision,
release readiness, and a transition of `initial`, `improved`, `regressed`, or
`unchanged`. A lower required-open count is improved; a higher count is
regressed; equal counts use the clear/review/blocked state order.

The history can be built from a JSON document containing a `resolutions` array,
or from one existing resolution/runtime document:

```powershell
glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history `
  resolutions.json --history-id glio-noncode-resolution-history --format markdown

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-query `
  history.json --resource entries --transition improved --limit 25

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-runtime `
  history.json --destination history-runtime --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-runtime-audit `
  history-runtime --format summary
```

The history runtime is an exact six-file handoff: `manifest.json`,
`history.json`, `audit.json`, `query.json`, `query-audit.json`, and
`runtime.json`. It is independently audited, rejects extra or missing files,
and preserves the latest folded state: `clear/promote` only when the latest
snapshot is closed and every audit accepts. The runnable
[`downloaded_data_contract_resolution_history_demo.py`](../examples/downloaded_data_contract_resolution_history_demo.py)
demonstrates a pending-to-closed improvement on the supplied ZIP without
retaining source record values or operator metadata. The API exposes the same
surfaces below
`/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history`.

### Resolution-history diffs

Two value-free resolution histories can be compared without exposing source
record values or operator metadata. The diff matches entries by stable ordinal,
retains only baseline/candidate addresses and bounded snapshot facts, and
classifies each item as `added`, `removed`, `changed`, or `unchanged`. It also
reports transition-counter deltas and an `improved`, `regressed`, `mixed`, or
`unchanged` direction based on required-open counts and release readiness.

The diff input is a JSON object with `left` and `right` history objects:

```json
{
  "left": {"history_id": "baseline", "entries": []},
  "right": {"history_id": "candidate", "entries": []}
}
```

The CLI exposes the complete diff lifecycle:

```powershell
glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff `
  left-right.json --format markdown

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-query `
  diff.json --change added --limit 25

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-runtime `
  diff.json --destination diff-runtime --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-runtime-audit `
  diff-runtime --format summary
```

The diff runtime is an exact six-file handoff: `manifest.json`, `diff.json`,
`audit.json`, `query.json`, `query-audit.json`, and `runtime.json`. Loading
requires exactly those files and replays every nested content address. The
independent diff, query, and runtime audits fail closed on changed addresses,
missing rows, reordered items, malformed counts, extra files, and forbidden
public metadata. The runnable
[`downloaded_data_contract_resolution_history_diff_demo.py`](../examples/downloaded_data_contract_resolution_history_diff_demo.py)
demonstrates the baseline-to-candidate improvement on the supplied ZIP.
The API mirrors these surfaces under
`/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff`.

## Boundary and safety behavior

The ingestion boundary is deliberately strict:

- only regular ZIP members with supported `.json`, `.jsonl`, `.ndjson`,
  `.csv`, `.tsv`, or `.yaml`/`.yml` suffixes are eligible;
- absolute paths, traversal paths, duplicate names, encrypted members, and
  mismatched member digests are rejected;
- UTF-8 decoding is required;
- JSON non-finite constants are rejected;
- JSON/YAML depth, collection size, string size, member size, and record count
  are bounded;
- CSV and TSV headers must be unique, non-empty, and valid public field names;
- YAML support is intentionally conservative and accepts scalar, mapping,
  sequence, and block-scalar structures needed for bounded data inspection;
- unknown contract fields are rejected during replay;
- content addresses are recomputed from canonical values;
- public projections reject attribution and runtime-identity keys such as
  `agent`, `assistant`, `author`, `language`, and `model`;
- schema and OpenAPI files are not silently interpreted as application data
  by the demo selection policy.

Input values remain data and are never executed. A value with a prohibited
public key fails closed rather than being silently rewritten. The source ZIP
used in the demo is a product/planning package, not a clinical measurement
dataset; its records are suitable for exercising ingestion, lineage, query,
replay, and diff behavior only.

## HTTP surface

The same operations are available from the local service:

```text
GET /v1/downloaded-data/catalog?input=<zip-path>
GET /v1/downloaded-data/ingest?input=<zip-path>&member=<member-name>
GET /v1/downloaded-data/ingest/query?input=<runtime-or-batch-json>&resource=records
GET /v1/downloaded-data/ingest/diff?left=<runtime-or-batch-json>&right=<runtime-or-batch-json>
GET /v1/downloaded-data/ingest/runtime/audit?input=<runtime-directory>
GET /v1/downloaded-data/ingest/schema
GET /v1/downloaded-data/ingest/capabilities
GET /v1/downloaded-data/profile?input=<runtime-or-batch-json>
GET /v1/downloaded-data/profile/runtime?input=<runtime-or-batch-json>
GET /v1/downloaded-data/profile/query?input=<profile-json-or-runtime-directory>&resource=fields
GET /v1/downloaded-data/profile/audit?input=<profile-json-or-runtime-directory>
GET /v1/downloaded-data/profile/schema
GET /v1/downloaded-data/profile/runtime/schema
```

Paths and query values must be URL-encoded by clients. The HTTP surface uses
the same parser, limits, content-address checks, and fail-closed errors as the
CLI. It is an offline inspection surface; it does not fetch remote sources or
execute archive content.

## Contract inventory

The public surface includes schemas and capabilities for selection, lineage,
records, batches, audits, queries, diff items, diff queries, runtime manifests,
runtime audits, structural profiles, profile audits, profile queries, profile
query audits, and profile runtimes. The repository-wide surface audit counts
these contracts and fails if one is omitted. Focused coverage is in
`tests/test_downloaded_data_ingestion.py` and
`tests/test_downloaded_data_profile.py`, including all supported fixture
formats, truncation, empty queries, zero-count type facts, exact-file replay,
diff classification, tamper rejection, and public-schema checks.
