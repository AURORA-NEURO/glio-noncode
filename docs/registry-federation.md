# Package-registry federation

This document describes the package-registry federation boundary in
`glio-noncode`. The boundary consumes already verified package registries. It
does not copy source repositories, infer missing package contents, or publish
local filesystem paths into a public receipt.

## What the boundary does

The federation layer turns one or more registry directories into a deterministic
replication receipt. Every input registry is loaded through the package
registry verifier before it is admitted as a peer. A peer contributes its
registry address, manifest address, package IDs, package addresses, entry
counters, and audit disposition. The federation then computes:

1. The union of package IDs observed across all peers.
2. Missing-package conflicts when a package is present on fewer peers than the
   federation expects.
3. Divergent-package conflicts when a package ID resolves to more than one
   package content address.
4. A quorum-aware federation state and release decision.
5. Address-linked review or blocking actions for every conflict and quorum
   deficiency.

The resulting receipt is public data. It contains no source path, agent field,
model field, programming-language field, author field, or process handle.

## Module boundaries

The family is intentionally split into narrow modules:

| Module | Responsibility |
| --- | --- |
| federation core | Peer receipts, conflicts, actions, reconciliation, five-file persistence |
| federation query | Bounded projections for summary, peers, packages, conflicts, actions, evidence |
| federation audit | Fourteen independent conservation checks |
| federation diff | Peer, package, conflict, and action transition items |
| diff audit | Independent validation of transition counters and item addresses |
| federation runtime | Build, audit, query, and optional atomic persistence composition |
| federation gate | Policy evaluation over state, decision, quorum, conflicts, actions, and audit |
| federation history | Append-only history of addressed federation release receipts |
| federation observatory | Cross-history timeline and bounded state/decision filters |
| federation matrix | Pairwise peer agreement, missing observations, and address divergence |
| matrix audit | Sixteen independent pair, ratio, state, evidence, and address checks |
| federation consensus | Quorum-safe package address candidates, explicit selection, and remediation actions |
| consensus audit | Independent selection, quorum, action, and replay checks |
| consensus query | Bounded package, candidate, action, and evidence projections |

The core is the only module that computes package-registry federation facts.
Queries and reports are projections. Audits recompute relationships from the
receipt fields. Diffs compare public receipts rather than private directories.
The runtime composes these boundaries without changing their source data.

## Pairwise agreement matrix

`registry_federation_matrix.py` derives an unordered comparison for every peer pair. It is useful when a federation has more than two downloaded registries and an aggregate conflict is not enough to explain the topology of the disagreement.

Each observation reports the peer pair and package union, common/matching/divergent/left-only/right-only counts, a bounded agreement ratio, a consistent or conflicted state, and address-linked evidence. For `n` peers, the matrix has exactly `n(n-1)/2` observations in lexicographic pair order. A one-peer federation is valid with zero pair observations and ratio `1.0`. A pair is conflicted whenever it has a divergent package address or a one-sided package observation; the matrix is conflicted if any pair is conflicted.

The independent matrix audit recomputes all sixteen invariants, including the pair set, package unions, state transitions, ratios, evidence ordering, mapping replay, and content addresses. Audit acceptance means the receipt is internally sound; it does not turn a conflicted matrix into an accepted release.

Build a matrix from three downloaded registries:

```text
python -m glio_noncode.cli registry-federation-matrix \
  --peer primary=C:\data\primary-registry \
  --peer replica=C:\data\replica-registry \
  --peer archive=C:\data\archive-registry \
  --federation-id downloaded-three-peer \
  --format markdown
```

Persisted matrix JSON can be filtered without rebuilding the federation:

```text
python -m glio_noncode.cli registry-federation-matrix-query \
  --input C:\data\matrix.json \
  --state conflicted \
  --format markdown
```

The HTTP equivalent is `GET /v1/registry/federation/matrix` with repeated `peer=ID=DIRECTORY` query values. Matrix schemas and capability responses are available below the same API surface. Matrix exports contain addresses and package IDs, not filesystem paths.

With the downloaded demonstration registries, two equivalent registries produce one consistent pair with ratio `1.0`; the ready-versus-held registries produce one conflicted pair with ratio `0.0`, while the independent audit still passes all `16/16` integrity checks.

## Quorum-safe consensus and remediation

The consensus boundary consumes a verified federation receipt and groups each package's observed content addresses into candidates. A candidate is selected only when it has at least the requested quorum and strictly more support than every other candidate. A tie, a below-quorum candidate, or an absent package remains unresolved. The source federation is never modified and dissenting addresses remain in the receipt.

The output carries one package row per union package, candidate rows with supporting peer IDs and support counts, and explicit actions. Divergent candidates create `inspect-divergence`; missing peer observations create `replicate-missing`; unresolved packages create `hold-package`. Blocking actions are retained even when the receipt is rejected, making the result useful as an operator work list rather than only as a boolean gate.

The consensus state is `consistent` only when every package has a selection. An accepted consensus additionally requires the source federation to be accepted and to have no remediation actions. A three-peer majority can therefore expose a selected address while still returning `review` when the source federation contains dissent. This preserves the distinction between a mechanically reproducible selection and a release approval.

Build and persist a consensus receipt:

```text
python -m glio_noncode.cli registry-federation-consensus \
  --peer primary=C:\data\primary-registry \
  --peer replica=C:\data\replica-registry \
  --federation-id downloaded-federation \
  --consensus-id downloaded-consensus \
  --destination C:\data\consensus \
  --format markdown
```

Audit and query the persisted JSON receipt:

```text
python -m glio_noncode.cli registry-federation-consensus-audit \
  --input C:\data\consensus.json
python -m glio_noncode.cli registry-federation-consensus-query \
  --input C:\data\consensus.json \
  --resource actions \
  --severity blocking \
  --format markdown
```

The API mirrors this at `/v1/registry/federation/consensus`, `/consensus/audit`, and `/consensus/query`. The consensus persistence package contains exactly `manifest.json`, `consensus.json`, `packages.json`, and `actions.json`; all four are canonicalized and checked on reload.

## Consensus execution, transitions, and history

`registry_federation_consensus_runtime.py` is the end-to-end composition boundary. It loads the downloaded registries, builds the federation and quorum receipt, runs the independent audit, creates a bounded query result, and optionally persists the derived consensus package. Its runtime receipt links every child address and exposes one replayable content address:

```text
python -m glio_noncode.cli registry-federation-consensus-runtime \
  --peer primary=C:\data\primary-registry \
  --peer replica=C:\data\replica-registry \
  --destination C:\data\consensus \
  --format summary
```

`registry_federation_consensus_diff.py` compares two consensus receipts by package, candidate, remediation action, and receipt disposition. It keeps added, removed, and changed counts plus changed-field attribution and evidence addresses. `registry_federation_consensus_diff_audit.py` recomputes those counts and item addresses independently:

```text
python -m glio_noncode.cli registry-federation-consensus-diff \
  --left C:\data\consensus-before \
  --right C:\data\consensus-after \
  --format markdown
python -m glio_noncode.cli registry-federation-consensus-diff-audit \
  --input C:\data\consensus-diff.json
```

`registry_federation_consensus_history.py` records ordered consensus/audit pairs as a three-file atomic package. Repeated evaluations of the same logical consensus ID are allowed; each addressed receipt remains a separate history entry. `registry_federation_consensus_observatory.py` aggregates one or more histories and provides bounded state, decision, and acceptance filters:

```text
python -m glio_noncode.cli registry-federation-consensus-history \
  --input C:\data\consensus-before \
  --input C:\data\consensus-after \
  --destination C:\data\consensus-history
python -m glio_noncode.cli registry-federation-consensus-observatory \
  --input C:\data\consensus-history \
  --decision reject \
  --format markdown
```

The HTTP equivalents are `/consensus/runtime`, `/consensus/diff`, `/consensus/diff/audit`, `/consensus/history`, and `/consensus/observatory`; schema and capability resources are published beside each route. The real downloaded-data example exercises the complete chain, including a clean acceptance, a divergent rejection, a strict-quorum transition, audit replay, history counters, and observatory filtering.

## Consensus release-control plane

The consensus receipt answers whether package addresses can be selected under a
quorum. The release-control plane answers the follow-on operational question:
whether that verified execution is eligible for promotion under an explicit,
content-addressed policy. It is deliberately a separate boundary so a useful
consensus result never becomes an implicit approval.

`registry_federation_consensus_gate.py` evaluates a verified consensus runtime
against a policy with twenty ordered checks. The default policy requires a
consistent/accepted consensus, at least one peer and quorum, at least one
selected package, no unresolved packages, no blocking remediation, and all
three child audits. Query completeness is configurable. The output is one of
`eligible/promote`, `review/review`, or `blocked/hold`; only the first pair is
accepted. Every check retains supporting content addresses, and the policy,
check list, counters, disposition, and final address replay independently.

Build the gate directly from downloaded registries, with optional package
persistence:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-runtime \
  --peer primary=C:\data\primary-registry \
  --peer replica=C:\data\replica-registry \
  --federation-id downloaded-federation \
  --consensus-id downloaded-consensus \
  --quorum 2 \
  --destination C:\data\consensus-gate-package \
  --format json \
  --output C:\data\consensus-gate-runtime.json
```

The runtime envelope contains the nested consensus runtime, gate, independent
gate audit, bounded gate query, persistence state, and one runtime address.
The standalone commands accept those JSON projections for re-evaluation:

```text
python -m glio_noncode.cli registry-federation-consensus-gate \
  --input C:\data\consensus-gate-runtime.json \
  --format markdown
python -m glio_noncode.cli registry-federation-consensus-gate-audit \
  --input C:\data\consensus-gate.json \
  --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-query \
  --input C:\data\consensus-gate.json \
  --resource failures \
  --passed false \
  --limit 50 \
  --format markdown
```

The bounded query exposes `summary`, `checks`, `failures`, and `evidence`
resources. It conserves filters, row ordinals, next offsets, and content
addresses, so a caller can inspect exactly why a release was held without
loading or rebuilding the source registries.

`registry_federation_consensus_gate_package.py` is the durable transport
boundary. It writes exactly six canonical JSON members:

| member | purpose |
| --- | --- |
| `manifest.json` | package identity, exact member list, and child addresses |
| `package.json` | package envelope and content address |
| `runtime.json` | complete consensus runtime used by the gate |
| `gate.json` | policy, checks, disposition, and acceptance |
| `audit.json` | independently recomputed gate audit |
| `query.json` | bounded operator projection |

Reload requires exact member vocabulary, canonical JSON bytes, manifest replay,
all child links, and package-address replay. The independent package audit
recomputes those conditions from the typed package. No local directory path is
included in the public package, and the public-boundary checks reject private
path or attribution metadata.

`registry_federation_consensus_gate_diff.py` compares two gate receipts by
policy, check, disposition, and receipt resources. Values are represented by
content fingerprints rather than raw duplicated payloads, while changed-field
attribution and evidence addresses explain the transition. Its independent
diff audit recomputes item addresses, counters, endpoints, and disposition
conservation. This is useful for showing a clean downloaded replica becoming a
review or hold result after a quorum policy change or registry divergence.

`registry_federation_consensus_gate_history.py` records ordered gate/audit pairs
as an exact three-file atomic package. `append_history` preserves every prior
entry and assigns the next ordinal; accepted, review, and blocked counters are
recomputed at construction and reload. The history audit checks ordering,
counter conservation, gate/audit links, evidence, mapping replay, and the
history address.

`registry_federation_consensus_gate_observatory.py` aggregates one or more
histories into a bounded timeline. It reports accepted, review, and blocked
counts and supports state, decision, acceptance, offset, and limit filters.
The independent observatory audit verifies history membership, observation
identity, aggregate counts, row/query replay, and the public boundary.

The HTTP equivalents are `/consensus/gate`, `/consensus/gate/runtime`,
`/consensus/gate/audit`, `/consensus/gate/query`, `/consensus/gate/package`,
`/consensus/gate/package/audit`, `/consensus/gate/diff`,
`/consensus/gate/diff/audit`, `/consensus/gate/history`,
`/consensus/gate/history/audit`, `/consensus/gate/observatory`, and
`/consensus/gate/observatory/audit`. Each route has adjacent schema and
capability resources. The downloaded-data demo runs this entire control plane,
then compares the normal gate with a stricter quorum policy, persists and
reloads the six-file package, audits the transition, and aggregates the
eligible/review observations.

## Consensus release certificate and handoff plane

The gate is the policy decision boundary. A certificate is the portable
handoff receipt produced from one verified gate runtime. It records whether the
gate was issued as `promote` or withheld as `hold`, retains the runtime, gate,
audit, query, policy, and evidence addresses, and preserves the failed check
IDs when promotion is withheld. A certificate never mutates the source
registry and never treats a passing audit as permission to promote.

`registry_federation_consensus_gate_certificate.py` defines a content-addressed
policy, a fixed 19-check issuance vocabulary, and the `issued/promote` or
`withheld/hold` state machine. The default policy requires an eligible gate,
the promote decision, gate acceptance, an accepted gate audit, a complete gate
query, and at least one gate check and passed check. `require_package=True`
adds a durable gate-package requirement. The policy address is included in
the certificate evidence set, so a policy change produces a new certificate
address and can be reviewed as a transition.

The certificate checks are ordered and fail closed:

| check group | purpose |
| --- | --- |
| `exact-fields`, `public-boundary` | keep the public certificate vocabulary fixed and path-free |
| `runtime-link`, `gate-link`, `audit-link`, `query-link`, `package-link` | connect the certificate to the exact execution evidence |
| `policy-link`, `state-allowed`, `decision-allowed` | replay policy bytes and compare gate disposition to policy |
| `gate-accepted`, `audit-accepted`, `query-complete` | require the child release-control values needed for handoff |
| `check-floor`, `counter-conservation`, `acceptance-conservation` | conserve counts and enforce fail-closed acceptance |
| `certificate-address`, `mapping-round-trip`, `path-free` | finalize deterministic identity and the boundary contract |

Build a certificate directly from a gate runtime JSON document:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate \
  --input C:\data\consensus-gate-runtime.json \
  --certificate-id downloaded-release-certificate \
  --format markdown
```

For an end-to-end directory-to-certificate runtime with a durable package:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-runtime \
  --peer primary=C:\data\primary-registry \
  --peer replica=C:\data\replica-registry \
  --federation-id downloaded-federation \
  --consensus-id downloaded-consensus \
  --quorum 2 \
  --certificate-policy-id downloaded-certificate-policy \
  --require-package \
  --destination C:\data\consensus-certificate-package \
  --format json \
  --output C:\data\consensus-certificate-runtime.json
```

The runtime wrapper retains the complete gate runtime, certificate, independent
certificate audit, bounded certificate query, optional package address,
persistence flag, and one runtime address. It is the recommended input to a
handoff service because a receiver can verify the complete nested chain from a
single document.

`registry_federation_consensus_gate_certificate_audit.py` independently
recomputes 20 certificate invariants. It checks the fixed field vocabulary,
policy address, every nested link, check ordering, counters, disposition,
evidence, mapping replay, and content-address replay. A withheld certificate
can therefore have an accepted audit: the audit means the rejection is
internally consistent, not that the release should proceed.

`registry_federation_consensus_gate_certificate_query.py` exposes five bounded
resources: `summary`, `checks`, `failures`, `evidence`, and `policy`. It
supports check ID, pass flag, state, decision, offset, and limit filters. Rows
carry resource identity, a stable row ID, the relevant check and evidence
addresses, and their own content addresses. The query result preserves total,
matched, returned, next-offset, and truncation counters. Use the failures
resource to explain a hold and the evidence resource to hand the addresses to
another verifier:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-query \
  --input C:\data\consensus-certificate.json \
  --resource failures \
  --passed false \
  --limit 50 \
  --format markdown
```

When a query is truncated, continue at `next_offset`. A page is a bounded
view, not a different certificate; the query address changes with resources,
filters, offset, and limit so the view itself is replayable.

`registry_federation_consensus_gate_certificate_query_audit.py` audits that
filtered view independently. It verifies the requested resources and filters,
page ordinals, next offset, nested row/query/result addresses, mapping replay,
and public boundary. Use `registry-federation-consensus-gate-certificate-query-audit`
or `/consensus/gate/certificate/query-audit` when a paginated result is being
handed to another review process.

`registry_federation_consensus_gate_certificate_package.py` is the durable
certificate transport boundary. It writes exactly nine canonical JSON members:

| member | purpose |
| --- | --- |
| `manifest.json` | version, exact member vocabulary, and every child address |
| `package.json` | package envelope and package content address |
| `certificate.json` | issued or withheld certificate |
| `runtime.json` | nested gate runtime used by certificate evaluation |
| `gate.json` | gate policy, checks, disposition, and acceptance |
| `gate-audit.json` | independent gate audit |
| `gate-query.json` | bounded gate projection |
| `certificate-audit.json` | independent certificate audit |
| `certificate-query.json` | bounded certificate projection |

The package writer stages members in a sibling directory and replaces the
destination only after every canonical member is ready. The loader rejects
missing or extra members, non-canonical JSON, broken manifest hashes, broken
nested links, and package-address drift. `package-audit` independently checks
18 invariants including both audit/query closures:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-package-audit \
  --input C:\data\consensus-certificate-package \
  --format markdown
```

`registry_federation_consensus_gate_certificate_diff.py` compares two
certificates field by field across policy, source links, disposition, checks,
counters, blockers, evidence, and acceptance. Values are rendered as bounded
fingerprints rather than duplicated payloads. The direction is `unchanged`,
`improved`, `regressed`, or `mixed`; it is derived from the left/right
acceptance values and does not declare which source is correct. The independent
diff audit recomputes 14 checks for item vocabulary, counters, item addresses,
endpoint conservation, direction, and mapping replay:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-diff \
  --left C:\data\certificate-before.json \
  --right C:\data\certificate-after.json \
  --format markdown \
  --output C:\data\certificate-transition.md
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-diff-audit \
  --input C:\data\certificate-transition.json \
  --format summary
```

The HTTP equivalents are `/consensus/gate/certificate`,
`/consensus/gate/certificate/runtime`, `/consensus/gate/certificate/audit`,
`/consensus/gate/certificate/query`,
`/consensus/gate/certificate/package`,
`/consensus/gate/certificate/package/audit`,
`/consensus/gate/certificate/diff`, and
`/consensus/gate/certificate/diff/audit`. Schema and capability resources are
published under the same prefix. A valid withheld certificate uses HTTP 422
for evaluation routes while its audit and query routes remain readable; this
keeps transport errors separate from an intentional release hold.

## Certificate history and append-only handoff

`registry_federation_consensus_gate_certificate_history.py` records certificate
decisions as an ordered, append-only value. Each entry captures the certificate
ID and runtime ID, the certificate and independent-audit addresses, the issued
or withheld state, the promote or hold decision, acceptance, check counters,
and a bounded set of evidence addresses. Entries are numbered from one and the
history stores separate issued and withheld counters. The constructor rejects
an entry whose acceptance is inconsistent with its disposition or whose audit
does not refer to the certificate.

The history is intentionally a new addressed value when a decision is appended.
`append_history` verifies the existing history, verifies the incoming
certificate/audit pair, assigns the next ordinal, and recomputes the history
address. The previous history and its entries remain valid and unchanged. The
bounded 256-entry limit makes retention and replay costs explicit while still
supporting a long release stream through external rotation.

History persistence is a three-member exact package:

| member | purpose |
| --- | --- |
| `manifest.json` | version, file vocabulary, history address, and entry count |
| `history.json` | complete addressed history envelope |
| `entries.json` | canonical ordered entry projection |

The writer uses sibling staging and destination replacement. The loader checks
the exact member set, rejects symlinks and non-canonical JSON, replays the
history and entry addresses, and compares both projections to the envelope.
`verify_history_directory` is the strict read boundary for a received history.

The independent history audit recomputes 14 checks: exact fields, public
boundary, entry and ordinal conservation, issued/withheld counters, certificate
and audit address vocabularies, disposition and acceptance rules, entry
addresses, mapping round-trip, history address, content address, and path-free
output. It is separate from the history constructor so a receiver can audit a
loaded value without trusting the producer's summary.

Build a history from certificate runtime or package directories. Multiple
`--input` values preserve their command-line order:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-history \
  --input C:\data\certificate-package-issued \
  --input C:\data\certificate-package-withheld \
  --history-id downloaded-certificate-history \
  --destination C:\data\certificate-history \
  --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-history-audit \
  --input C:\data\certificate-history \
  --format markdown
```

The API equivalents are `/consensus/gate/certificate/history` and
`/consensus/gate/certificate/history/audit`. The build route accepts repeated
`input` parameters and can persist an exact history package with `destination`
and `overwrite`. The audit route accepts either a history directory or a
canonical history JSON document. Both routes keep local source paths outside
the returned public object.

For operational use, retain the certificate package address, history address,
history audit address, and the entry ordinal together. A withheld certificate
is not erased or converted into an error: it remains a first-class historical
decision with failed checks available through the certificate query. A later
issued certificate is appended as a new entry, allowing reviewers to explain
the complete transition from hold to promotion without mutating the original
record.

## Certificate history observatory and health report

`registry_federation_consensus_gate_certificate_observatory.py` projects one
or more verified certificate histories into a single bounded monitoring value.
The projection keeps every source history address, assigns a deterministic
global observation ordinal, and carries the entry, certificate, runtime, and
independent-audit addresses needed to trace a decision back to its source. It
also conserves issued, withheld, accepted, held, total-check, and failed-check
counters. The source histories are never modified by aggregation, so an
observatory can be rebuilt whenever a review needs a different set of streams.

The observatory query is a stable resource projection with seven resources:

| resource | rows |
| --- | --- |
| `summary` | one aggregate row linked to the observatory address |
| `observations` | every history entry in global ordinal order |
| `issued` | observations whose certificate state is `issued` |
| `withheld` | observations whose certificate state is `withheld` |
| `accepted` | observations accepted by the certificate policy |
| `held` | observations not accepted by the certificate policy |
| `evidence` | trace rows carrying certificate and audit evidence links |

Resources can be combined and filtered by `history_id`, `certificate_id`,
certificate `state`, certificate `decision`, and `accepted`. Filters are applied
before the bounded `offset`/`limit` page, and each page records total, matched,
returned, next-offset, truncation, query, row, and result addresses. The query
serializer has JSON, CSV, and Markdown forms; all public rows contain labels,
counts, decisions, and content addresses, never source filesystem paths.

`registry_federation_consensus_gate_certificate_observatory_audit.py` performs
an independent 16-check audit of the aggregate. It rechecks exact fields,
public-boundary safety, source-history and observation conservation, ordinals,
all disposition counters, source and nested address vocabularies, acceptance
semantics, mapping replay, content-address replay, and path-free output.
`registry_federation_consensus_gate_certificate_observatory_query_audit.py`
performs a separate 13-check audit after filtering and pagination. That second
audit proves that the view actually delivered to a reviewer still matches its
requested resources, filters, offsets, row addresses, and source links.

The deterministic health report in
`registry_federation_consensus_gate_certificate_observatory_report.py` turns
the same stream into operational metrics. It reports acceptance ratio, latest
disposition, consecutive withheld count, transitions, recoveries, total check
and failure density, and a `steady`, `mixed`, or `held` stream state. Alerts
identify withheld decisions, an active withheld streak, failed checks, and a
stream with no accepted observations. Alerts remain bounded and carry only
stable evidence addresses. The independent report audit recomputes 15 checks,
including the ratio, trend counters, alert identity, nested observatory link,
mapping replay, and report address.

For durable review handoff,
`registry_federation_consensus_gate_certificate_observatory_package.py` writes
an exact eight-file package:

| ordinal | member | purpose |
| ---: | --- | --- |
| 1 | `manifest.json` | version, fixed vocabulary, and child addresses |
| 2 | `package.json` | addressed package envelope |
| 3 | `observatory.json` | complete aggregate and observations |
| 4 | `query.json` | complete bounded resource projection |
| 5 | `report.json` | health metrics and alert projection |
| 6 | `observatory-audit.json` | independent aggregate audit |
| 7 | `query-audit.json` | independent result audit |
| 8 | `report-audit.json` | independent health-report audit |

The writer stages a canonical directory and refuses accidental replacement
unless `overwrite` is explicit. The loader rejects extra members, symlinks,
non-canonical JSON, address mismatches, and projection drift. The independent
package audit checks 15 invariants across the exact member vocabulary, all
nested links, manifest replay, package addressing, byte projections, mapping
round trips, and the public boundary.

Build the observatory from persisted history directories:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory \
  --input C:\data\certificate-history-issued \
  --input C:\data\certificate-history-withheld \
  --observatory-id release-certificate-observatory \
  --output C:\data\certificate-observatory.json \
  --format json
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-query \
  --input C:\data\certificate-observatory.json \
  --resource withheld --resource evidence --limit 25 \
  --format markdown
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-report \
  --input C:\data\certificate-observatory.json --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-package \
  --input C:\data\certificate-observatory.json \
  --destination C:\data\certificate-observatory-package \
  --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-package-audit \
  --input C:\data\certificate-observatory-package --format summary
```

The HTTP routes mirror these operations below the certificate prefix:
`/consensus/gate/certificate/observatory`, `/audit`, `/query`,
`/query-audit`, `/report`, `/report/audit`, `/package`, and `/package/audit`.
Their schema and capability resources are also published. A receiving system
can therefore validate the aggregate, inspect the exact filtered page, read
the health report, and replay the eight-file handoff without access to the
source registry directories.

## Observatory transition diff and runtime

`registry_federation_consensus_gate_certificate_observatory_diff.py` compares
two addressed observatories by the stable logical key
`history_id:entry_ordinal`. It distinguishes `added`, `removed`, `changed`,
and `unchanged` observations even when global observation ordinals move because
histories were reordered. Every item retains both observation addresses,
certificate disposition, acceptance change, failed-check delta, and trace
evidence. The diff summary conserves item action counts, left/right population
counts, acceptance and withheld deltas, and failure totals. Its direction is
`unchanged`, `improved`, `regressed`, or `mixed` and is derived from those
conserved changes.

Diff queries expose `summary`, `items`, `added`, `removed`, `changed`,
`unchanged`, `accepted-gain`, `accepted-loss`, and `failures`. They accept a
logical observation-key filter, action filter, acceptance-change filter, and
bounded pagination. `registry_federation_consensus_gate_certificate_observatory_diff_audit.py`
recomputes 16 independent diff invariants. A separate
`registry_federation_consensus_gate_certificate_observatory_diff_query_audit.py`
recomputes 13 result invariants, including requested resources, filters,
pagination, row addresses, and mapping replay.

The diff makes a release transition explicit without requiring source registry
access:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-diff \
  --left C:\data\certificate-observatory-before.json \
  --right C:\data\certificate-observatory-after.json \
  --format markdown
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-diff-audit \
  --input C:\data\certificate-observatory-diff.json --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-diff-query \
  --input C:\data\certificate-observatory-diff.json \
  --resource changed --resource failures --limit 25 --format markdown
```

`registry_federation_consensus_gate_certificate_observatory_runtime.py`
orchestrates the complete lifecycle from history directories or public history
JSON: load, aggregate, independently audit, query, independently audit the
query, report health, independently audit the report, and optionally persist
the exact eight-file package. Its addressed runtime envelope makes each nested
stage and the optional package address explicit. The runtime audit recomputes
13 checks for stage links, acceptance, persistence state, mapping replay,
content addressing, and the public boundary.

Use the runtime when a CI job should produce one self-describing result:

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-runtime \
  --input C:\data\certificate-history-issued \
  --input C:\data\certificate-history-withheld \
  --destination C:\data\certificate-observatory-package \
  --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-runtime-audit \
  --input C:\data\certificate-observatory-runtime.json --format markdown
```

The runtime is path-free after loading. Input paths affect only the local
read, while its output contains labels, counters, decisions, alert values, and
content addresses. All diff, query, and runtime schema/capability resources are
available through both the CLI and the local HTTP API.

`registry_federation_consensus_gate_certificate_observatory_replay.py` closes
the transport loop for a written snapshot. It reloads the package, reads the
exact eight expected members, compares every canonical byte projection,
rechecks the nested package audit, and emits a path-free replay receipt with
the observatory, query, report, and audit addresses. The independent replay
audit recomputes 13 checks for member vocabulary, byte equality, projection
equality, nested audit acceptance, mapping replay, and the replay address.

```text
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-replay \
  --input C:\data\certificate-observatory-package --format markdown
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-replay-audit \
  --input C:\data\certificate-observatory-replay.json --format summary
```

The replay operation is also available at `/consensus/gate/certificate/observatory/replay`
and `/consensus/gate/certificate/observatory/replay/audit`, with schema and
capability routes beside them. A successful receipt proves that the package
received by the downstream process is the same addressed artifact that was
written by the producing process.

Replay acceptance checklist:

1. Confirm the package contains exactly the eight declared members.
2. Confirm every member is a regular file and parses as canonical JSON.
3. Confirm the envelope and manifest agree on the package address.
4. Confirm the observatory, query, report, and audit addresses are nested
   consistently across all projections.
5. Confirm the package audit is accepted before using the report operationally.
6. Confirm the replay receipt reports byte equality and projection equality.
7. Confirm the replay audit is accepted and retain its address with the handoff.
8. Compare the receipt address when the same package crosses another process
   boundary; a changed address means the receipt itself changed.

## Remediation plan and operator query

`registry_federation_consensus_remediation.py` converts every consensus action into a required or recommended non-mutating step. Each step retains its action ID, package, peer scope, instruction, and evidence addresses. `ready` is true only when there are no blocking steps; it does not authorize an edit. The independent remediation audit recomputes step identity, severity counters, readiness, and nested addresses. The query projection provides `summary`, `steps`, `required`, `recommended`, and `evidence` resources with bounded package, kind, severity, status, and pagination filters:

```text
python -m glio_noncode.cli registry-federation-consensus-remediation \
  --input C:\data\consensus.json \
  --format markdown
python -m glio_noncode.cli registry-federation-consensus-remediation-query \
  --input C:\data\remediation.json \
  --resource required \
  --status required \
  --format markdown
```

The runtime receipt embeds the remediation plan, its independent audit, and its query result so a caller can consume one addressed execution value. HTTP routes are `/consensus/remediation`, `/consensus/remediation/audit`, and `/consensus/remediation/query`, with schemas and capabilities beside them. Divergent downloaded registries therefore produce visible `inspect-divergence` and `hold-package` steps rather than an implicit repair.

`registry_federation_consensus_remediation_package.py` provides the durable handoff. It writes exactly `manifest.json`, `package.json`, `remediation.json`, and `audit.json` using sibling staging and canonical reload verification. The package includes the independently recomputed audit and rejects any manifest, step projection, audit, or member-set tampering. Use `registry-federation-consensus-remediation-package` or `GET /consensus/remediation/package` when the plan must be transported as a verified artifact.

`registry_federation_consensus_remediation_query_audit.py` independently checks the filtered view after projection. It verifies that returned rows belong to requested resources, satisfy every filter, preserve page ordinals and next offsets, and replay their query/row/result addresses. Its report is available through `registry-federation-consensus-remediation-query-audit` and `/consensus/remediation/query-audit`.

## State model

The reconciliation state is determined in this order:

| Condition | State | Decision | Accepted |
| --- | --- | --- | --- |
| No conflicts and healthy peers meet quorum | `consistent` | `accept` | true |
| Missing packages or healthy peers below quorum | `degraded` | `review` | false |
| Any divergent package | `conflicted` | `reject` | false |

The default quorum is the ceiling of half the peer count. A caller may declare
a stricter positive quorum, up to the configured peer limit. A divergence is
always blocking because selecting one address would silently discard another
peer's evidence. Missing content is review severity because it may represent a
stale replica rather than incompatible content.

## Canonical persistence

The federation core writes exactly these members:

| File | Content |
| --- | --- |
| `manifest.json` | version, boundary, federation identity, projection addresses |
| `federation.json` | complete typed federation receipt |
| `peers.json` | peer projection document |
| `reconciliation.json` | conflict and disposition projection |
| `actions.json` | deterministic operator actions |

All JSON is canonicalized. Writes use a sibling staging directory and a final
directory replacement. Reloading checks the exact member set, canonical bytes,
manifest links, projection links, and byte-for-byte package replay. The core
does not accept a partially shaped destination as an overwrite target.

History uses the same approach with `manifest.json`, `history.json`, and
`entries.json`. History entries retain receipt addresses rather than copying
the complete federation payload into every timeline row.

## CLI

Build and persist a federation from registry directories:

```text
python -m glio_noncode.cli registry-federation \
  --peer primary=C:\data\primary-registry \
  --peer replica=C:\data\replica-registry \
  --federation-id release-federation \
  --destination C:\data\federation \
  --format json
```

The command returns exit code `0` for an accepted federation and `2` for a
review or rejection disposition while still emitting the receipt. This makes
it suitable for a GitHub Actions gate that uploads the JSON as an artifact.

Query a persisted receipt:

```text
python -m glio_noncode.cli registry-federation-query C:\data\federation \
  --resource conflicts \
  --severity blocking \
  --format markdown
```

Audit, gate, and compare receipts:

```text
python -m glio_noncode.cli registry-federation-audit C:\data\federation
python -m glio_noncode.cli registry-federation-gate C:\data\federation
python -m glio_noncode.cli registry-federation-diff C:\data\left C:\data\right
```

History and observatory commands consume persisted federation/history
directories:

```text
python -m glio_noncode.cli registry-federation-history \
  --input C:\data\left \
  --input C:\data\right \
  --destination C:\data\history
python -m glio_noncode.cli registry-federation-observatory \
  --input C:\data\history \
  --format csv
```

Every boundary has schema and capability commands. The capability responses
describe the supported resources, limits, prefixes, and output formats without
requiring a private implementation import.

## HTTP API

The local API exposes the same surface under `/v1/registry/federation`:

| Path | Purpose |
| --- | --- |
| `/v1/registry/federation` | Build from repeated `peer=ID=DIRECTORY` values |
| `/v1/registry/federation/query` | Query a persisted federation using `input` |
| `/v1/registry/federation/audit` | Run the fourteen-check audit |
| `/v1/registry/federation/gate` | Evaluate the default release policy |
| `/v1/registry/federation/diff` | Compare `left` and `right` persisted receipts |
| `/v1/registry/federation/history` | Build history from repeated `input` values |
| `/v1/registry/federation/observatory` | Aggregate repeated history inputs |
| `/v1/registry/federation/matrix` | Compare every peer pair from repeated `peer` values |
| `/v1/registry/federation/matrix/audit` | Independently audit a serialized matrix |
| `/v1/registry/federation/matrix/query` | Filter and page a serialized matrix |

Each endpoint supports JSON responses and the projection endpoints also support
CSV or Markdown where their CLI equivalent does. `/schema` and
`/capabilities` routes are available at each module boundary.

## Real-data demonstration

The tested demonstration used two downloaded package-registry directories from
the product handoff. Feeding the same downloaded registry as two replica peers
produced:

```text
state=consistent decision=accept accepted=True
peers=2 packages=1 conflicts=0 actions=0
audit=14/14
```

Feeding the downloaded ready registry beside a downloaded held registry with
the same package ID produced:

```text
state=conflicted decision=reject accepted=False
peers=2 packages=1 conflicts=1 actions=1
conflict=divergent severity=blocking
audit=14/14
```

The query layer returned the expected summary, peer, package, conflict, and
action rows with deterministic offsets. Mapping replay and five-member disk
replay both reproduced the original content address. The runtime composed the
same federation, audit, query, and persistence result into one runtime receipt.

## Integrity and public-boundary rules

Addresses are hashes over canonical public mappings with the content-address
field removed before hashing. Typed objects reject unknown fields, duplicate
IDs, unsupported states, malformed addresses, unbounded sequences, and
filesystem separators in public address lists. Loaders reject non-canonical
JSON and missing or extra files.

The public-surface audit includes every federation schema and capability
projection. The repository-wide inventory count increases when a new public
schema is added, so an accidental omission or an undocumented surface change
causes CI to fail. The Actions workflow compiles all federation modules and
runs the focused federation contract test alongside the existing regression
suite.

## Extension guidance

New federation projections should follow these rules:

- Accept typed verified federation values, not unverified paths, at the
  projection boundary.
- Derive rows from existing addressed fields instead of recalculating package
  semantics in a second location.
- Give every new public row an exact field set and a replayable address.
- Keep pagination bounded and deterministic.
- Add a schema, capability response, focused tests, CLI route, HTTP route, and
  public-surface inventory entry together.
- Add a downloaded-data demonstration when the projection depends on a new
  persistence or reconciliation relationship.
