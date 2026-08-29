# Consensus release control

This document is the operator-facing contract for the consensus release-control
plane. It is intentionally separate from reconciliation and from package
selection. A consensus receipt can be valuable while still being unsuitable
for promotion; the gate makes that distinction explicit.

## Design boundary

The release-control plane consumes a verified
`RegistryFederationConsensusRuntime`. That runtime already contains the
downloaded federation, quorum consensus, independent consensus audit,
non-mutating remediation plan, remediation audit, bounded consensus query,
remediation query, and remediation-query audit. The gate does not reopen
directories or infer facts from filenames. It evaluates only the addressed
runtime graph.

The flow is:

```text
downloaded registry directories
        |
        v
federation -> consensus -> remediation + queries
        |          |              |
        +----------+--------------+
                   v
          twenty-check gate policy
                   |
       +-----------+-----------+
       |                       |
 eligible/promote       review/review or blocked/hold
       |                       |
 six-file handoff       inspectable failed checks
```

The source directories are read-only inputs. No command in this plane edits a
registry or silently chooses one dissenting package address.

## Policy contract

`RegistryFederationConsensusGatePolicy` is content-addressed and public. Its
fields are:

| field | meaning |
| --- | --- |
| `allowed_states` | consensus states accepted by policy, normally `consistent` |
| `allowed_decisions` | consensus decisions accepted by policy, normally `accept` |
| `minimum_peer_count` | minimum number of source registries |
| `minimum_quorum` | minimum address support required by consensus |
| `minimum_selected_packages` | minimum selected package count |
| `maximum_unresolved_packages` | unresolved package tolerance |
| `maximum_blocking_steps` | blocking remediation tolerance |
| `require_consensus_audit` | require the independent consensus audit |
| `require_remediation_audit` | require the independent remediation audit |
| `require_remediation_query_audit` | require the independent remediation query audit |
| `require_complete_queries` | reject truncated query projections when enabled |

The default policy is conservative: it permits only a consistent accepted
consensus, requires all child audits, permits no unresolved packages or
blocking remediation steps, and keeps query completeness optional for bounded
interactive inspection. A deployment can construct a stricter policy by
raising the quorum or requiring complete projections. Policy addresses are
recomputed on load; a changed limit is a different policy.

## Gate checks

The twenty checks are ordered and conserved in every JSON projection:

1. `runtime-accepted`
2. `consensus-audit`
3. `remediation-audit`
4. `remediation-query-audit`
5. `state-allowed`
6. `decision-allowed`
7. `minimum-peers`
8. `minimum-quorum`
9. `selected-packages`
10. `unresolved-packages`
11. `blocking-remediation`
12. `remediation-ready`
13. `consensus-query-complete`
14. `remediation-query-complete`
15. `address-links`
16. `policy-address`
17. `check-conservation`
18. `content-address`
19. `mapping-round-trip`
20. `path-free`

Each check includes a boolean result, bounded detail, and supporting content
addresses. The gate is accepted only when every check passes. A failed
runtime/state/decision/remediation check produces `blocked/hold`; other policy
failures produce `review/review`. The distinction lets operators tell a hard
safety stop from a policy review without interpreting free-form text.

## Durable handoff

The gate package contains exactly six files. The package writer stages sibling
files and replaces the destination atomically after all canonical bytes have
been generated:

| file | checked content |
| --- | --- |
| `manifest.json` | version, boundary, exact files, and child addresses |
| `package.json` | package identity and content address |
| `runtime.json` | nested consensus execution receipt |
| `gate.json` | policy, checks, counters, and disposition |
| `audit.json` | independent gate audit |
| `query.json` | bounded check/failure/evidence projection |

Reload rejects extra files, missing files, non-canonical JSON, manifest drift,
projection drift, child-address substitution, and package-address mismatch.
`package_bytes` exposes the exact canonical byte map for transport adapters.

The package audit is independent of the package constructor. It recomputes the
member vocabulary, runtime/gate/audit/query links, nested addresses, mapping
round trip, content address, and public boundary. This means a caller can
verify a package received from another process without trusting the process
that produced its audit.

## Transitions and monitoring

Gate diffs compare policy, check, disposition, and receipt resources. Raw gate
payloads are not copied into a diff; changed values are represented by
content fingerprints and the diff retains changed-field attribution and
evidence links. The independent diff audit recomputes resource counts,
change categories, item addresses, endpoint dispositions, and the diff address.

Gate histories preserve ordered gate/audit pairs. `append_history` does not
rewrite or merge prior entries; it assigns the next ordinal and recomputes all
state counters. The history audit checks ordering, entry identity, gate/audit
links, evidence, counters, and content-address replay.

The observatory aggregates histories without flattening away provenance. Each
observation retains the history ID, history address, entry ordinal, gate ID,
gate address, state, decision, acceptance, and failed-check count. Queries can
filter state, decision, and acceptance with bounded offset/limit pagination.
The observatory audit independently recomputes membership, identity,
aggregate counters, query replay, and the public boundary.

## CLI workflow

Build a runtime from two downloaded registries and persist the handoff:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-runtime `
  --peer primary=C:\data\primary `
  --peer replica=C:\data\replica `
  --quorum 2 `
  --destination C:\data\gate-package `
  --format json `
  --output C:\data\gate-runtime.json
```

Inspect the gate and its bounded failures:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate `
  --input C:\data\gate-runtime.json --format markdown
python -m glio_noncode.cli registry-federation-consensus-gate-audit `
  --input C:\data\gate.json --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-query `
  --input C:\data\gate.json --resource failures --passed false --format json
```

Create a history from persisted gate packages and inspect it:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-history `
  --input C:\data\gate-package-before `
  --input C:\data\gate-package-after `
  --destination C:\data\gate-history
python -m glio_noncode.cli registry-federation-consensus-gate-observatory `
  --input C:\data\gate-history --accepted false --format markdown
```

The CLI returns exit code `0` for accepted gate/runtime audits and `2` for a
valid but rejected gate. It still writes the rejected JSON, which is important
for remediation and forensic review. Malformed input is reported as an error
and never becomes a synthetic accepted result.

## HTTP workflow

The local API mirrors the CLI under `/v1/registry/federation`:

| route | input |
| --- | --- |
| `/consensus/gate/runtime` | repeated `peer=ID=DIRECTORY` values |
| `/consensus/gate` | serialized consensus or gate-runtime JSON |
| `/consensus/gate/audit` | serialized gate JSON |
| `/consensus/gate/query` | serialized gate JSON and filters |
| `/consensus/gate/package` | serialized gate-runtime JSON |
| `/consensus/gate/package/audit` | serialized package JSON |
| `/consensus/gate/diff` | `left` and `right` gate JSON |
| `/consensus/gate/diff/audit` | serialized diff JSON |
| `/consensus/gate/history` | repeated persisted package directories |
| `/consensus/gate/history/audit` | serialized history JSON |
| `/consensus/gate/observatory` | repeated persisted history directories |
| `/consensus/gate/observatory/audit` | serialized observatory JSON |

Schema and capability resources sit beside each route. Summary responses use
HTTP `422` for a valid non-accepted gate/runtime and `400` for malformed input.
JSON, CSV, and Markdown outputs preserve the same typed verification boundary.

## Downloaded-data demonstration

`examples/registry_federation_real_downloaded_data_demo.py` runs the source
federation, ordinary gate, consensus, remediation, release gate, audits,
queries, strict-policy transition diff, history, observatory, and six-file
package replay. With equivalent downloaded registries it reports
`eligible/promote`, twenty passing gate checks, zero failed checks, and a true
package replay. With a ready registry paired with a held or divergent registry
it reports the dissenting consensus, `blocked/hold`, retained failed checks,
and an independently valid audit. The strict-policy comparison always provides
a deterministic review transition for a clean pair, making the demo useful
even when both downloaded registries are identical.

The demo is intentionally read-only with respect to its input directories. Its
temporary verification directory is discarded after canonical reload checks,
and the returned report contains addresses, IDs, counters, and rows rather
than local filesystem paths.

## Verification checklist

Before treating a release gate as transport-ready, a caller should verify:

- the source runtime address and nested consensus address are trusted;
- the gate is accepted and its decision is `promote`;
- the gate audit, package audit, diff audit, history audit, and observatory
  audit are accepted where those projections are used;
- every package directory contains the exact documented file set;
- query pagination is understood when `truncated` is true;
- a rejected result is retained for inspection instead of retried as an
  implicit repair;
- no source registry directory is modified by the workflow.

This contract is implemented in the `registry_federation_consensus_gate*`
modules, compiled by the assurance workflow, covered by focused CLI/HTTP and
adversarial mapping tests, and included in the repository public-surface
inventory.
