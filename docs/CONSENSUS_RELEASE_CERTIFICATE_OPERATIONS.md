# Certificate operations and handoff runbook

This runbook covers the practical life of a certificate: evaluating downloaded
registry directories, inspecting an issued or withheld result, persisting the
handoff package, reviewing policy transitions, and diagnosing transport or
policy failures.

## Inputs

The command accepts directories written by the canonical package-registry
writer. A directory is not trusted because its name looks familiar. It is
trusted only after the registry loader checks its exact members, canonical JSON,
manifest, package addresses, and verification closure.

For a two-peer clean run:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-runtime `
  --peer primary=C:\downloads\primary-registry `
  --peer replica=C:\downloads\replica-registry `
  --federation-id downloaded-federation `
  --consensus-id downloaded-consensus `
  --runtime-id downloaded-certificate-runtime `
  --gate-id downloaded-release-gate `
  --certificate-id downloaded-release-certificate `
  --certificate-policy-id downloaded-certificate-policy `
  --quorum 2 `
  --limit 100 `
  --destination C:\handoffs\downloaded-certificate-package `
  --format json `
  --output C:\handoffs\downloaded-certificate-runtime.json
```

The `--limit 100` value is intentional. Issuance requires the internal gate
query to be complete. An operator can still request a smaller certificate query
page later with the query command.

## Clean result

The clean runtime should report:

| field | value |
| --- | --- |
| `certificate_state` | `issued` |
| `certificate_decision` | `promote` |
| `accepted` | `true` |
| `failed_count` | `0` |
| `certificate_audit.accepted` | `true` |
| `persisted` | `true` when `--destination` is supplied |
| `package_address` | a certificate-package address when persisted |

The certificate normally has 19 passed checks. The independent certificate
audit has 20 passed findings. The package audit has 18 passed findings. These
counts are part of the contract and are useful smoke-test assertions.

## Divergent result

Point one peer at a different downloaded registry:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-runtime `
  --peer primary=C:\downloads\primary-registry `
  --peer archive=C:\downloads\archive-registry `
  --federation-id downloaded-federation `
  --consensus-id downloaded-divergent-consensus `
  --runtime-id downloaded-divergent-certificate-runtime `
  --certificate-id downloaded-divergent-certificate `
  --limit 100 `
  --format summary `
  --output C:\handoffs\downloaded-divergent-certificate-summary.json
```

The expected decision is:

| field | value |
| --- | --- |
| `state` | `withheld` |
| `decision` | `hold` |
| `accepted` | `false` |
| `failed_count` | greater than zero |
| `certificate_audit.accepted` | normally `true` |

The command returns exit code 2 for this valid hold. Keep the receipt. It
contains the failed check IDs and the addresses needed to explain the
divergence. Do not replace it with a hand-written status string.

## Inspect a certificate

Render a full certificate as Markdown:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate `
  --input C:\handoffs\downloaded-certificate-runtime.json `
  --format markdown `
  --output C:\handoffs\downloaded-certificate.md
```

The command accepts a certificate runtime, a gate runtime, a certificate
package mapping, or a certificate mapping. A runtime is preferable because it
retains all nested sources. A package directory is inspected with the package
audit command.

## Inspect failures first

For a held certificate, start with the smallest useful projection:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-query `
  --input C:\handoffs\downloaded-divergent-certificate.json `
  --resource failures `
  --passed false `
  --limit 100 `
  --format markdown
```

Then request the supporting evidence addresses:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-query `
  --input C:\handoffs\downloaded-divergent-certificate.json `
  --resource evidence `
  --limit 100 `
  --format json `
  --output C:\handoffs\downloaded-divergent-evidence.json
```

The `failures` rows correspond exactly to `blocking_check_ids`. The query is a
projection of the certificate, not a second evaluation. Its content address
changes when its resources, filters, offset, or limit changes.

## Pagination procedure

When a result reports `truncated: true`:

1. store the current query result and its content address;
2. read `next_offset`;
3. issue the same query with that offset;
4. preserve the same resources and filters;
5. stop when `truncated` is false and `next_offset` is zero.

Changing the limit between pages is allowed but creates a different query
address and should be recorded as a new view. A page with zero returned rows
can still be valid when the offset is beyond the matched range.

## Package handoff

Create a package from a certificate runtime:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-package `
  --input C:\handoffs\downloaded-certificate-runtime.json `
  --package-id downloaded-certificate-handoff `
  --destination C:\handoffs\downloaded-certificate-package `
  --format summary
```

Audit it before transport:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-package-audit `
  --input C:\handoffs\downloaded-certificate-package `
  --format markdown
```

The destination must contain exactly:

```text
manifest.json
package.json
certificate.json
runtime.json
gate.json
gate-audit.json
gate-query.json
certificate-audit.json
certificate-query.json
```

Do not add notes, screenshots, temporary files, or alternate JSON projections
inside this directory. Put auxiliary material beside the package directory.

## Receiver procedure

The receiving process should perform the following sequence:

1. copy the package directory into a new destination;
2. run `load_package` or the package-audit CLI;
3. require an accepted package audit;
4. compare the loaded package address with the sender’s handoff record;
5. inspect `certificate.accepted`;
6. if false, route to hold triage and stop promotion;
7. if true, check the expected policy address;
8. optionally compare with the prior accepted certificate;
9. persist certificate, audit, and package addresses in the receiver record.

The receiver should not rebuild the value from source directories unless the
package itself is missing. Rebuilding may create a new address after a source
adapter, schema, or policy change.

## Strict package mode

Use `--require-package` when the certificate must not be issued unless the gate
runtime has a persisted package. The runtime command handles this by persisting
the underlying gate package before evaluating the certificate policy and then
writing the certificate package at the requested destination.

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-runtime `
  --peer primary=C:\downloads\primary-registry `
  --peer replica=C:\downloads\replica-registry `
  --require-package `
  --destination C:\handoffs\strict-certificate-package `
  --format json `
  --output C:\handoffs\strict-certificate-runtime.json
```

If the destination is omitted, a strict policy has no package address to
reference and the certificate is withheld. This is an intentional policy
failure, not a filesystem accident.

## Policy transition review

Compare a normal certificate with a stricter policy result:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-diff `
  --left C:\handoffs\normal-certificate.json `
  --right C:\handoffs\strict-certificate.json `
  --diff-id normal-to-strict `
  --format markdown `
  --output C:\handoffs\certificate-transition.md
```

Audit the serialized diff after saving a JSON projection:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-diff-audit `
  --input C:\handoffs\certificate-transition.json `
  --format summary
```

The expected direction for an accepted certificate becoming withheld is
`regressed`. The diff does not declare whether the strict policy is better; it
only makes the field-level transition inspectable.

## Triage table

| failed check | first action |
| --- | --- |
| `runtime-link` | inspect the nested gate runtime and consensus address |
| `gate-link` | verify the gate identity was not mixed with another runtime |
| `audit-link` | rerun the independent gate audit |
| `query-link` | rebuild the gate query with the correct gate value |
| `package-link` | persist the gate package or remove the strict requirement |
| `policy-link` | reconstruct the policy from its exact public fields |
| `state-allowed` | inspect federation conflicts and policy state set |
| `decision-allowed` | inspect gate decision and allowed decision set |
| `gate-accepted` | query the gate failures before certificate failures |
| `audit-accepted` | inspect gate audit findings and nested source links |
| `query-complete` | increase the internal limit or reduce source rows intentionally |
| `check-floor` | compare gate check counters with policy minimums |
| `counter-conservation` | treat the source gate as corrupted and reload it |
| `acceptance-conservation` | inspect all preceding failed certificate checks |
| `mapping-round-trip` | check serialization field names and tuple/list conversion |
| `path-free` | remove local paths from public detail or evidence values |

## Transport failure table

| symptom | likely cause | response |
| --- | --- | --- |
| missing member | incomplete copy or wrong package family | restore exact nine-file package |
| extra member | notes or temporary output in destination | remove from a new transport copy |
| non-canonical JSON | formatter rewrote a member | regenerate with the package writer |
| package address mismatch | member content changed | discard modified copy and request a new package |
| manifest mismatch | copied projections do not belong together | use the sender’s original package directory |
| audit address mismatch | audit was edited or from another certificate | rerun audit from the loaded certificate |
| query address mismatch | query filters or source certificate changed | regenerate the query projection |

Do not repair a package by editing one member in place. The old package address
is no longer meaningful after a member change. Rebuild the complete package so
all child and manifest addresses are recomputed together.

## HTTP operation examples

Build directly from downloaded peer directories:

```text
GET /v1/registry/federation/consensus/gate/certificate/runtime?peer=primary=C:\downloads\primary-registry&peer=replica=C:\downloads\replica-registry&quorum=2&format=json
```

Read a certificate query:

```text
GET /v1/registry/federation/consensus/gate/certificate/query?input=C:\handoffs\certificate.json&resource=failures&passed=false&limit=50&format=json
```

Read the package audit:

```text
GET /v1/registry/federation/consensus/gate/certificate/package/audit?input=C:\handoffs\certificate-package&format=json
```

Read a schema or capability descriptor:

```text
GET /v1/registry/federation/consensus/gate/certificate/schema
GET /v1/registry/federation/consensus/gate/certificate/package/capabilities
```

The runtime evaluation route returns HTTP 200 for an issued certificate and
HTTP 422 for a valid withheld certificate. The audit, query, and package-audit
routes return readable diagnostic projections. HTTP 400 indicates malformed
input, missing source data, invalid query parameters, or a broken package.

## Demo procedure

Run the real downloaded-data demonstration with two registry directories:

```powershell
python examples/registry_federation_real_downloaded_data_demo.py `
  --primary-registry C:\downloads\primary-registry `
  --replica-registry C:\downloads\replica-registry `
  --limit 5
```

The report includes the original federation and consensus layers, gate and
remediation layers, then the certificate layer:

| report key | demonstration |
| --- | --- |
| `consensus_gate_certificate_runtime` | end-to-end wrapper summary |
| `consensus_gate_certificate` | normal issuance decision |
| `consensus_gate_certificate_audit` | independent audit |
| `consensus_gate_certificate_query` | bounded operator page |
| `consensus_gate_certificate_strict` | policy-tightened hold |
| `consensus_gate_certificate_diff` | acceptance-aware transition |
| `consensus_gate_certificate_diff_audit` | independent diff audit |
| `consensus_gate_certificate_history` | append-only issued/withheld stream |
| `consensus_gate_certificate_history_audit` | independent 14-check history audit |
| `consensus_gate_certificate_history_disk_replay` | three-file write/load address equality |
| `consensus_gate_certificate_observatory` | cross-history certificate observations and counters |
| `consensus_gate_certificate_observatory_audit` | independent 16-check aggregate audit |
| `consensus_gate_certificate_observatory_query` | resource-filtered and paginated monitoring view |
| `consensus_gate_certificate_observatory_query_audit` | independent 13-check result audit |
| `consensus_gate_certificate_observatory_report` | deterministic health, trend, and alert report |
| `consensus_gate_certificate_observatory_report_audit` | independent 15-check report audit |
| `consensus_gate_certificate_observatory_package` | exact eight-file observatory handoff |
| `consensus_gate_certificate_observatory_package_audit` | independent 15-check package audit |
| `consensus_gate_certificate_package` | exact nine-file package |
| `consensus_gate_certificate_package_audit` | package invariant audit |
| `consensus_gate_certificate_package_disk_replay` | write/load address equality |

The demo uses the complete internal query for issuance and a five-row operator
query for visibility. This shows that correctness and presentation bounds can
be controlled independently. It also appends the normal issued decision and a
strict-policy withheld decision into one history, persists the three-file
history package, reloads it, and audits the reloaded value.

## Certificate observatory operations

After histories have been retained, aggregate them into a monitoring value and
review the derived health report:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory --input C:\data\history-issued --input C:\data\history-withheld --output C:\data\certificate-observatory.json --format json
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-audit --input C:\data\certificate-observatory.json --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-query --input C:\data\certificate-observatory.json --resource withheld --resource evidence --limit 25 --format markdown
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-query-audit --input C:\data\certificate-query.json --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-report --input C:\data\certificate-observatory.json --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-report-audit --input C:\data\certificate-report.json --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-package --input C:\data\certificate-observatory.json --destination C:\data\certificate-observatory-package --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-package-audit --input C:\data\certificate-observatory-package --format summary
```

Use the withheld and held resources for incident review, the evidence resource
for trace-back, and the report's latest disposition and streak counters for a
release dashboard. Continue from `next_offset` when a query reports
`truncated`. Store the observatory, query, report, and audit addresses with the
review record. The eight-file package is the preferred transport when another
process must replay the reviewed state.

The equivalent HTTP suffixes are `/observatory`, `/observatory/audit`,
`/observatory/query`, `/observatory/query-audit`, `/observatory/report`,
`/observatory/report/audit`, `/observatory/package`, and
`/observatory/package/audit` below the certificate route. Schema and capability
resources are published beside each family. The workflow compiles every
observatory module, runs its contract suite, and checks the public inventory
alongside the existing certificate controls.

For before/after release review, compare snapshots by logical history-entry
key and inspect only changed or failure-bearing rows:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-diff --left C:\data\observatory-before.json --right C:\data\observatory-after.json --output C:\data\observatory-diff.json --format json
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-diff-audit --input C:\data\observatory-diff.json --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-diff-query --input C:\data\observatory-diff.json --resource changed --resource failures --limit 25 --format markdown
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-diff-query-audit --input C:\data\observatory-diff-query.json --format summary
```

The diff direction is derived from acceptance and failed-check deltas. Keep
the diff audit address with the transition record; a `regressed` direction is
an explicit review signal, not a transport failure. When a job should perform
the complete load-to-package lifecycle in one operation, use the runtime:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-runtime --input C:\data\history-issued --input C:\data\history-withheld --destination C:\data\observatory-package --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-runtime-audit --input C:\data\observatory-runtime.json --format markdown
```

The runtime retains the addresses of the aggregate, query, health report,
three independent audits, and optional package. It is the recommended CI
entry point when downstream systems need one replayable receipt.

Replay should be treated as a gate in deployment automation: stop on a
non-canonical member, address mismatch, byte mismatch, projection mismatch, or
failed nested audit. These outcomes identify a handoff-integrity problem and
should not be collapsed into an ordinary withheld release decision.
The replay address is stable across repeated reads of the same package.
Retain it alongside the package address for later reconciliation.

## CI expectations

The repository workflow compiles all certificate modules and runs core,
extended, validation, and contract test modules. A build is considered healthy
when:

- every certificate schema is a closed object;
- capability descriptors are serializable;
- clean fixtures issue certificates;
- divergent fixtures withhold certificates;
- package directories contain exactly nine members;
- package reloads replay the original address;
- independent audits pass for clean and withheld typed results;
- query pagination conserves offsets;
- diffs and diff audits replay;
- history append preserves old entry addresses and assigns contiguous ordinals;
- history persistence contains exactly three canonical members;
- independent history audits pass after disk reload;
- certificate observatories conserve histories, observations, dispositions, and counters;
- observatory queries conserve resources, filters, row ordering, and pagination;
- health reports and their alert/trend counters pass an independent audit;
- observatory packages contain exactly eight canonical members and replay their address;
- the public surface inventory remains at its declared count;
- CLI and HTTP certificate routes remain callable.

These checks are deliberately redundant because the certificate is intended to
cross process boundaries. A passing unit test for one constructor is not enough
to establish that the serialized handoff can be received and replayed.
