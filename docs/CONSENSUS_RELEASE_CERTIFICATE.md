# Consensus release certificate contract

This document specifies the certificate and handoff boundary for downloaded
package-registry evidence. It is intentionally operational: it explains what
is evaluated, what is preserved, what is transportable, and what a receiver
can verify without reopening the source directories.

## Boundary and purpose

A registry is a downloaded observation. A federation reconciles several
observations. A consensus receipt identifies the package addresses selected by
the reconciliation rule. A release gate evaluates that receipt under a gate
policy. A certificate freezes the gate result as a small, portable decision
receipt.

The certificate boundary exists because these values answer different
questions:

| value | question answered |
| --- | --- |
| registry | What did one downloaded directory contain? |
| federation | How do multiple registry observations agree or disagree? |
| consensus | Which package addresses are eligible under a quorum? |
| gate | Does the verified execution satisfy release-control policy? |
| certificate | Can this gate result be handed to another process as an issued or withheld receipt? |
| package | Can the full evidence spine be transported and replayed later? |

The certificate is not a new source of scientific or product truth. It does
not rewrite a registry, resolve dissent by choosing a peer silently, add a
clock value, or turn an audit result into an approval. It preserves the
decision that the gate made and the evidence needed to recompute it.

## State and decision model

Certificate state and decision are coupled:

| state | decision | accepted | meaning |
| --- | --- | --- | --- |
| `issued` | `promote` | `true` | Every certificate prerequisite passed. |
| `withheld` | `hold` | `false` | At least one prerequisite failed; blockers remain visible. |

There is no third certificate state. A receiver must not infer approval from a
well-formed withheld certificate. Conversely, a receiver must not infer that a
withheld certificate is corrupt merely because its independent audit passes.
The audit proves that the hold is internally consistent; the decision proves
that promotion was not granted.

The constructor enforces the conservation rule:

```text
accepted = (failed_count == 0)
state    = issued   when accepted else withheld
decision = promote  when accepted else hold
```

The `acceptance-conservation` check is also emitted in the certificate so the
rule remains inspectable in exported evidence.

## Policy contract

`RegistryFederationConsensusGateCertificatePolicy` contains the requirements
used to derive a certificate:

| field | role |
| --- | --- |
| `policy_id` | bounded human-selected policy label |
| `allowed_gate_states` | source gate states accepted for issuance |
| `allowed_gate_decisions` | source gate decisions accepted for issuance |
| `minimum_check_count` | minimum source gate checks required |
| `minimum_passed_count` | minimum source gate checks that must pass |
| `require_gate_acceptance` | require the source gate to accept |
| `require_gate_audit` | require its independent audit to accept |
| `require_query_complete` | require the gate query not to be truncated |
| `require_package` | require a persisted gate package address |
| `content_address` | deterministic identity for the policy bytes |

The default policy accepts an `eligible/promote` gate, requires gate and audit
acceptance, requires a complete gate query, and requires at least one source
check and passed check. It does not require a persisted package because an
operator may first inspect an in-memory certificate and choose a transport
boundary later. Set `require_package=True` when issuance and durable handoff
must happen in the same operation.

Policy addresses are computed after replacing the address field with a null
placeholder and hashing the canonical object. Reconstructing the policy from
the same public fields therefore returns the same address. A changed threshold,
allowed state, or package requirement necessarily creates a different policy
address and, in turn, a different certificate address.

## The 19 issuance checks

Checks are ordered, typed, content-addressed, and retained in the certificate.
Every check includes its ordinal, ID, boolean result, bounded detail, evidence
addresses, and check address.

| ordinal | check ID | rule |
| ---: | --- | --- |
| 1 | `exact-fields` | Certificate fields match the fixed public vocabulary. |
| 2 | `public-boundary` | Runtime and policy projections remain public and path-free. |
| 3 | `runtime-link` | Gate runtime links to the nested consensus runtime. |
| 4 | `gate-link` | Gate address and gate ID are retained. |
| 5 | `audit-link` | Independent gate audit links to the selected gate. |
| 6 | `query-link` | Bounded gate query links to the selected gate. |
| 7 | `package-link` | A package address exists when policy requires one. |
| 8 | `policy-link` | Policy content address recomputes exactly. |
| 9 | `state-allowed` | Gate state belongs to the policy’s allowed state set. |
| 10 | `decision-allowed` | Gate decision belongs to the policy’s allowed decision set. |
| 11 | `gate-accepted` | Gate acceptance is required when configured. |
| 12 | `audit-accepted` | Gate audit acceptance is required when configured. |
| 13 | `query-complete` | Gate query is complete when configured. |
| 14 | `check-floor` | Gate check and passed-check floors are met. |
| 15 | `counter-conservation` | Gate counters equal the actual check results. |
| 16 | `acceptance-conservation` | All certificate prerequisites pass. |
| 17 | `certificate-address` | Certificate identity can be assigned after checks. |
| 18 | `mapping-round-trip` | Public mapping reconstructs the same certificate. |
| 19 | `path-free` | Evidence values contain no local path material. |

The check list is deliberately redundant. Link checks protect graph shape;
policy checks protect the decision boundary; counters protect completeness;
address checks protect replay; and the public check protects the transport
boundary. A caller can use `blocking_check_ids` for a compact explanation and
then query the full check rows for detail.

## Independent certificate audit

`registry_federation_consensus_gate_certificate_audit.py` is a separate
recomputation boundary. It does not trust the certificate’s own check result
as evidence of its correctness. It checks:

1. exact certificate fields;
2. public and path-free projection shape;
3. runtime-to-gate address linkage;
4. gate-to-audit linkage;
5. gate-to-query linkage;
6. package requirement conservation;
7. policy address replay;
8. ordered check IDs and ordinals;
9. per-check address replay;
10. check count and pass/fail counters;
11. blocker list conservation;
12. evidence set conservation;
13. issued/withheld state conservation;
14. promote/hold decision conservation;
15. acceptance conservation;
16. certificate address replay;
17. mapping round-trip;
18. nested address completeness;
19. audit address replay;
20. final public-boundary replay.

The audit result has its own address and its own finding list. An audit finding
never edits the certificate. If the certificate is changed, the audit must be
run again and will obtain a different address.

## Runtime wrapper

The runtime wrapper is the simplest value for a service boundary. It contains:

| field | contents |
| --- | --- |
| `runtime_id` | wrapper label |
| `gate_runtime` | consensus runtime, gate, gate audit, and gate query |
| `certificate` | issuance decision and 19 checks |
| `certificate_audit` | independent 20-check audit |
| `certificate_query` | bounded certificate projection |
| `package_address` | optional durable certificate package address |
| `persisted` | whether the package was written |
| `content_address` | wrapper identity |

`run_certificate_runtime` performs the following deterministic sequence:

1. load every peer registry using the canonical registry loader;
2. build federation and consensus evidence;
3. evaluate the gate;
4. audit the gate;
5. build a complete certificate query for issuance;
6. evaluate the certificate policy;
7. audit the certificate independently;
8. build the requested bounded certificate query;
9. optionally write the exact nine-file certificate package;
10. construct and verify the final wrapper address.

The complete internal query and the caller-facing bounded query are separate
on purpose. Issuance can require query completeness while an operator receives
a small page for a terminal or review panel.

## Query resources

Certificate queries expose these deterministic resources:

| resource | rows |
| --- | --- |
| `summary` | One row with acceptance, state, decision, and check counts. |
| `checks` | One row for every ordered certificate check. |
| `failures` | One row for each failed check. |
| `evidence` | One row for each unique supporting content address. |
| `policy` | One row describing the policy thresholds and package requirement. |

Filters are applied before pagination:

| filter | behavior |
| --- | --- |
| `check_id` | Select one check row by fixed ID. |
| `passed` | Select passing or failing rows. |
| `state` | Select the certificate state. |
| `decision` | Select the certificate decision. |
| `offset` | Skip a bounded number of matched rows. |
| `limit` | Return at most the configured bounded page size. |

Every row retains the resource, row ID, check ID, pass value, detail, evidence
addresses, and row address. The result retains total, matched, returned,
next-offset, and truncation counters. A receiver should continue at
`next_offset` whenever `truncated` is true and should preserve the query
address with the page in a review record.

## Independent query-result audit

`registry_federation_consensus_gate_certificate_query_audit.py` closes the
last-mile review gap: it audits the exact filtered view after the certificate
query has been built. Its 11 findings verify the result field vocabulary,
public boundary, certificate link, requested resources, active filters, row
ordinals, pagination state, row/query/result addresses, result address,
mapping replay, and path-free output.

Run it against a saved query projection:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-query-audit \
  --input C:\data\certificate-query.json \
  --format markdown
```

This audit does not re-run the source federation and does not issue a new
certificate. It proves that the view being reviewed is the view requested and
that its rows remain attached to the certificate. It can accept both a complete
query and a truncated page; truncation is valid when its next offset is
conserved.

## Exact nine-file package

The certificate package is a directory transport format, not a loose set of
JSON files. The exact member set is:

| ordinal | file | source |
| ---: | --- | --- |
| 1 | `manifest.json` | manifest with member list and child addresses |
| 2 | `package.json` | typed package envelope |
| 3 | `certificate.json` | certificate value |
| 4 | `runtime.json` | nested gate runtime |
| 5 | `gate.json` | gate value |
| 6 | `gate-audit.json` | gate audit value |
| 7 | `gate-query.json` | gate query result |
| 8 | `certificate-audit.json` | certificate audit value |
| 9 | `certificate-query.json` | certificate query result |

The package envelope carries the certificate, gate runtime, gate, both audit
values, both query values, package ID, and package address. The manifest repeats
the exact member vocabulary and all child addresses. These repetitions are
intentional: they let a receiver diagnose which projection is inconsistent.

### Write sequence

The writer uses a sibling staging directory:

1. reject a non-empty destination unless overwrite is explicit;
2. serialize each member with canonical JSON;
3. create the manifest from the typed package;
4. verify the package address before writing;
5. write all nine members to staging;
6. replace the destination with staging;
7. remove only the staging directory after success.

An interrupted write leaves the previous destination intact when a previous
destination exists. A receiver should still run the loader and package audit;
filesystem atomicity does not replace content-address verification.

### Load sequence

The loader checks:

1. directory existence and directory type;
2. exact file-name equality;
3. canonical JSON bytes for every member;
4. package envelope field vocabulary;
5. typed certificate and runtime reconstruction;
6. gate, audit, and query reconstruction;
7. certificate audit and certificate query reconstruction;
8. manifest address and member-set replay;
9. every nested address link;
10. package content-address replay.

Changing one byte in any member changes a downstream address or fails canonical
reload. Adding an unlisted file is also a failure; extra material must travel
outside the package directory.

## Transition diffs

Certificate diffs compare two typed certificates across a fixed field set. Each
item reports:

| field | meaning |
| --- | --- |
| `ordinal` | stable position in the comparison vocabulary |
| `field` | compared certificate field |
| `action` | `added`, `removed`, `changed`, or `unchanged` |
| `left_value` | bounded fingerprint of the left value |
| `right_value` | bounded fingerprint of the right value |
| `changed` | whether the field differs |
| `detail` | bounded comparison explanation |
| `content_address` | item identity |

The direction is computed from endpoint acceptance:

| left | right | direction |
| --- | --- | --- |
| false | false | `mixed` when fields change, otherwise `unchanged` |
| false | true | `improved` |
| true | false | `regressed` |
| true | true | `mixed` when fields change, otherwise `unchanged` |

The direction is an operator hint, not a correctness claim. A policy change
from permissive to strict can be a deliberate regression in acceptance and a
useful safety improvement at the same time. The diff audit checks endpoint
addresses, item vocabulary, counters, item addresses, direction, and mapping
replay.

## Public boundary

All certificate projections use bounded labels and bounded text. Public output
contains labels, dispositions, counts, details, evidence addresses, and content
addresses. It excludes local source directories and private attribution
metadata. The boundary is recursive: nested maps, tuples, rows, audit findings,
manifests, and capability payloads are checked before a typed value is accepted.

The strict mapping constructors reject unknown fields. This is important for
forward compatibility discipline: adding a field requires a deliberate schema
revision and a new contract test instead of silently changing the meaning of
an old package.

## Performance considerations

The certificate layer is intentionally bounded:

- certificate checks are fixed at 19;
- evidence addresses are capped;
- query resources are a fixed vocabulary;
- query rows and page limits are bounded;
- package members are fixed at nine;
- audit findings and diff items have fixed upper bounds;
- content addresses use canonical serialization with no filesystem traversal;
- child values are verified once and then reused by the wrapper.

For large downloaded collections, keep source federation construction outside a
request loop and use the runtime wrapper as the cacheable boundary. For a
review panel, request `failures` first, then retrieve `checks` or `evidence`
pages only when needed. For transport, persist the package once and reload it
at the receiver rather than rebuilding from source directories.

## Example receiver algorithm

The following is the intended receiver logic in plain language:

1. Load the nine-file directory with `load_package`.
2. Run `audit_package` and require `accepted`.
3. Inspect `package.certificate.accepted`.
4. If false, query `failures` and stop the promotion path.
5. If true, compare the certificate policy address to the expected policy.
6. Compare the package address to the transport manifest or handoff record.
7. Optionally run the certificate diff against the previous accepted receipt.
8. Retain the package and audit addresses in the downstream record.

The algorithm is deliberately non-mutating. If a receiver needs a new policy,
it evaluates a new certificate and creates a new package; it does not edit the
old certificate in place.

## CLI surface

The certificate commands are:

| command | output |
| --- | --- |
| `registry-federation-consensus-gate-certificate` | issue or re-render one certificate |
| `registry-federation-consensus-gate-certificate-runtime` | build the end-to-end wrapper |
| `registry-federation-consensus-gate-certificate-audit` | independently audit a certificate |
| `registry-federation-consensus-gate-certificate-query` | return bounded certificate rows |
| `registry-federation-consensus-gate-certificate-package` | persist a nine-file package |
| `registry-federation-consensus-gate-certificate-package-audit` | audit a package directory |
| `registry-federation-consensus-gate-certificate-diff` | compare two certificates |
| `registry-federation-consensus-gate-certificate-diff-audit` | audit a transition diff |

Every structured command supports a public JSON projection; certificate,
audit, query, and diff values additionally support CSV or Markdown where the
projection is useful for a human review. Evaluation commands return zero for
accepted results and two for valid but withheld results. Malformed input
remains a validation error.

## HTTP surface

The local API mirrors the CLI under `/v1/registry/federation/consensus/gate`:

| route | operation |
| --- | --- |
| `/certificate` | read or evaluate a certificate |
| `/certificate/runtime` | build a runtime from repeated peer directories |
| `/certificate/audit` | audit a certificate |
| `/certificate/query` | query a certificate |
| `/certificate/package` | write and return a package |
| `/certificate/package/audit` | audit a package directory |
| `/certificate/diff` | compare left and right certificate inputs |
| `/certificate/diff/audit` | audit a serialized diff |

Schema and capability routes sit beside each operation. A valid withheld
evaluation returns HTTP 422 while audit and query routes remain available for
diagnosis. A malformed input, missing directory, broken address, or invalid
package member returns HTTP 400.

## Verification checklist

Before calling a certificate handoff complete, verify:

- the gate runtime is loaded from canonical registry data;
- the gate query is complete for issuance;
- the certificate audit is accepted;
- the certificate decision matches the state;
- failed checks are empty for `issued/promote`;
- the package directory has exactly nine members;
- package reload returns the same package address;
- the package audit is accepted;
- the certificate query can return failures and evidence;
- the diff audit is accepted when a transition is produced;
- the final public projection contains no local paths or private metadata;
- the receiving process stores the package and audit addresses.

The downloaded-data example in
`examples/registry_federation_real_downloaded_data_demo.py` exercises these
checks on canonical registry directories and emits a JSON report suitable for
manual inspection or a CI smoke test.

## Append-only decision history

The certificate boundary also includes a compact history layer for retaining
multiple decisions over time. The history accepts `(certificate, audit)` pairs,
not unverified summaries. It verifies each certificate and independent audit,
checks the audit-to-certificate link, assigns a contiguous ordinal, and records
the disposition and evidence addresses required for later review.

The history model has these fields:

| field | meaning |
| --- | --- |
| `history_id` | bounded public stream identifier |
| `entries` | ordered immutable certificate decisions |
| `entry_count` | number of retained entries |
| `issued_count` | entries with state `issued` |
| `withheld_count` | entries with state `withheld` |
| `content_address` | replayable history identity |

Each entry carries `certificate_id`, `runtime_id`, certificate and audit
addresses, state, decision, acceptance, check counters, evidence addresses,
and its own content address. The acceptance equation is fail-closed: an entry
is accepted only for the `issued/promote` disposition with zero failed checks.
This retains held decisions without treating them as malformed data.

`append_history` is the only supported extension operation. It validates the
prior history and new pair, refuses an entry beyond the 256-entry bound, and
returns a new addressed history. The old history remains replayable. This
supports immutable release records, deterministic transition review, and
external rotation when a stream reaches its retention bound.

The durable history package contains exactly three canonical JSON files:
`manifest.json`, `history.json`, and `entries.json`. `load_history` checks the
member set, canonical bytes, envelope address, manifest address, and entry
projection before returning a typed value. A separate history audit recomputes
14 checks and emits an addressable audit with JSON, CSV, Markdown, schema, and
capability projections. The CLI and HTTP routes accept package directories and
public JSON documents, so a downstream operator can build, persist, reload,
and audit a history without access to the original registry inputs.

The observatory and replay layers extend this same handoff discipline across
history collections, derived reports, and transport bytes.
The same address can be checked repeatedly without changing the source.

## Cross-history observatory and health report

The certificate observatory aggregates one or more verified histories into a
bounded monitoring projection. It retains source history, entry, certificate,
runtime, and audit addresses while assigning deterministic global observation
ordinals. Issued, withheld, accepted, held, total-check, and failed-check
counters are recomputed from observations and rejected when they drift.

Its query surface provides `summary`, `observations`, `issued`, `withheld`,
`accepted`, `held`, and `evidence` resources. History, certificate, state,
decision, and acceptance filters are applied before offset/limit pagination.
Every page records its query address, row addresses, total and matched counts,
next offset, and truncation state. The query can be rendered as JSON, CSV, or
Markdown for a review queue.

The aggregate has an independent 16-check audit, and the filtered result has a
separate 13-check audit. Together they verify public field closure, source and
counter conservation, address vocabularies, requested resources, active
filters, row ordering, pagination, mapping replay, and content-address replay.
The report layer derives acceptance ratio, latest disposition, withheld streak,
transition and recovery counts, failure density, stream state, and bounded
alerts. A 15-check report audit independently validates those derived values.

The durable observatory handoff has exactly eight members: `manifest.json`,
`package.json`, `observatory.json`, `query.json`, `report.json`,
`observatory-audit.json`, `query-audit.json`, and `report-audit.json`. The
loader checks exact membership, canonical bytes, nested addresses, and every
projection. Its independent package audit has 15 checks. This lets a receiver
inspect certificate health and replay the reviewed page without the source
history directories.
