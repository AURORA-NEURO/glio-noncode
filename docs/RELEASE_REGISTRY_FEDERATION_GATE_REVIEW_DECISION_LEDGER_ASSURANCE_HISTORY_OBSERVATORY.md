# Release-registry federation gate review decision-ledger assurance-history observatory

The observatory is the cross-run review boundary for GLIO-NONCODE. It accepts
current-format assurance-history packages, preserves every history as a
source-scoped member, and computes a deterministic aggregate. It is designed
for downloaded release-registry evidence where several independent runs need
to be reviewed together without flattening their provenance.

The observatory is an operational review instrument. It is not a scientific
claim, a clinical decision, a substitute for a domain review, or an inference
that a missing package is safe. A promoted observatory means that the current
public contract is internally consistent and that every member is accepted and
release-ready according to its upstream history gate.

## Boundary contract

The public boundary is:

```text
public_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory
```

The version is derived from the verified decision-ledger assurance-history
version and ends in `-observatory-v1`. The boundary deliberately contains no
machine path, timestamp, username, email, agent field, language field, model
field, credential, or private identity. A source path is used only while
loading an input package and is never copied into a member or report.

An observatory has one stable identity and zero or more members. A member is
identified by an explicit public member ID or, when omitted, by its upstream
history ID. Members are sorted by member ID before the aggregate address is
computed. Duplicate member IDs, duplicate history addresses, and duplicate
member addresses are rejected.

## What is retained

Each member retains the following public facts from its verified history:

| Field | Meaning |
| --- | --- |
| `member_id` | Stable public identity assigned by the caller. |
| `history_id` | Upstream history identity. |
| `history_address` | Content address of the complete upstream history. |
| `head_address` | Address of the terminal history entry or the explicit initial head. |
| `entry_count` | Number of history observations. |
| `latest_snapshot_id` | Terminal snapshot identity, if the history is non-empty. |
| `latest_transition` | `initial`, `stable`, `improved`, `regressed`, or `changed`. |
| `state` | Upstream terminal `promote`, `hold`, `block`, or explicit `empty`. |
| `accepted` | Upstream history acceptance projection. |
| `release_ready` | Upstream terminal release-readiness projection. |
| transition counters | Counts of every history transition. |
| gate counters | Counts of promoted, held, and blocked history entries. |
| quality counters | Finding and check totals conserved across every entry. |
| `content_address` | Address recomputed from the complete member projection. |

The observatory does not retain the history entries themselves. The upstream
address remains the join key, so an operator can inspect the source package
when needed without creating a second authority for its contents.

## Aggregate state

The member state projection is deterministic:

| Member terminal condition | Member observatory state |
| --- | --- |
| no history entries | `empty` |
| blocked gate | `blocked` |
| held gate | `held` |
| accepted and release-ready promoted gate | `ready` |
| any other non-empty combination | `mixed` |

The aggregate projection is fail-closed:

1. No members produces `empty` and is not release-ready.
2. Any blocked member produces `blocked` and is not release-ready.
3. Otherwise any held member produces `held` and is not release-ready.
4. All members ready produces `ready` and is release-ready.
5. A mixture of empty, ready, or otherwise non-ready members produces `mixed`
   and is not release-ready.

`accepted` is true only when at least one member exists and every member is
accepted. `release_ready` is true only when at least one member exists, the
aggregate state is `ready`, and every member is release-ready. Adding a held,
blocked, empty, or mixed member therefore cannot accidentally promote a package
that was previously ready.

## Aggregate conservation

The builder recomputes rather than accepts caller-supplied aggregate counters.
The following equations are checked by the typed constructor and again by
the independent verifier:

```text
member_count = len(members)
entry_count = sum(member.entry_count)

initial_count + stable_count + improved_count + regressed_count + changed_count
    = entry_count

promote_count + hold_count + block_count = entry_count

passed_finding_count + warning_finding_count + blocker_finding_count
    = finding_count

passed_check_count + warning_check_count + blocker_check_count
    = check_count

empty_member_count + ready_member_count + held_member_count
    + blocked_member_count + mixed_member_count = member_count
```

Every aggregate field is also compared with a fresh sum over members. The
stored metrics document is a projection of those same values and is rejected
when it differs from a recomputation.

## Independent verification

The verification artifact contains eight required checks:

| Check | Recomputed assertion |
| --- | --- |
| `member-identities` | Member IDs are unique and count-conserved. |
| `member-addresses` | Every member address is reproducible from its fields. |
| `counter-conservation` | Aggregate entry and quality totals equal member sums. |
| `state-projection` | Aggregate state equals the state fold over members. |
| `readiness-projection` | Readiness is the conjunctive all-members rule. |
| `history-addresses` | Source history addresses are distinct. |
| `public-boundary` | No forbidden key or local path crosses the boundary. |
| `content-address` | Aggregate content address is reproducible. |

Verification has its own content address. A package loader independently
rebuilds the verification from the loaded observatory and rejects a
verification document that has a valid JSON shape but different checks,
counters, state, or address. Verification check counts are derived from the
individual check records, so changing `passed_count` alone cannot pass.

The verification gate maps aggregate posture to operator status:

| Aggregate posture | Verification state | `release_ready` |
| --- | --- | --- |
| ready | `promote` | true |
| held, mixed, or empty | `hold` | false |
| blocked | `block` | false |

The state describes the observable review posture. It does not claim that the
underlying data is correct beyond the declared upstream contracts.

## Exact persistence

An observatory package contains exactly these regular files:

```text
manifest.json
observatory.json
members.json
verification.json
metrics.json
```

`observatory.json` is the aggregate summary. `members.json` is the complete
source-scoped member document. `verification.json` contains the independent
checks. `metrics.json` contains a separately addressed projection of state,
transition, gate, quality, acceptance, and readiness totals. The manifest
contains the version, boundary, identity links, exact file tuple, byte sizes,
artifact hashes, and manifest address.

The writer uses canonical UTF-8 JSON and an atomic directory replacement. An
existing destination requires explicit overwrite authorization and must
already be an exact compatible package. The loader rejects:

- extra or missing files;
- symlinks at the package or artifact boundary;
- non-regular files;
- non-canonical JSON bytes;
- artifact hash or byte-size drift;
- manifest address drift;
- summary/member/verification/metrics linkage drift;
- legacy package shapes; and
- any verification or metrics result that cannot be independently reproduced.

An observatory diff contains exactly `manifest.json` and `diff.json`. The same
atomic write and exact-file rules apply.

## Diff semantics

Diffs compare member IDs, not raw list positions. For each union member ID the
diff records one of:

| Action | Meaning |
| --- | --- |
| `added` | Member is absent from the baseline and present in the candidate. |
| `removed` | Member is present in the baseline and absent from the candidate. |
| `unchanged` | Complete member projections are equal. |
| `changed` | The member exists on both sides but a public field changed. |

Direction is computed with a stable quality vector over readiness, acceptance,
state, blocker counts, regressions, improvements, and entry coverage:

| Direction | Meaning |
| --- | --- |
| `unchanged` | Complete member projection was unchanged. |
| `improved` | Candidate quality vector is greater. |
| `regressed` | Candidate quality vector is lower, or a member was removed. |
| `mixed` | Public identity or details changed without a strict quality ordering. |

An added ready member is an improvement relative to no member. An added empty
or non-ready member is classified conservatively by the same quality vector.
The overall diff state reports the dominant direction and retains a mixed
state whenever incomparable changes coexist with strict changes.

## Query contract

Observatory queries are bounded by `MAX_QUERY_ITEMS = 4096` and expose:

```text
summary, members, empty, ready, held, blocked, mixed, accepted, rejected
```

Filters can constrain member state, latest transition, accepted projection,
release readiness, and a case-insensitive canonical-text search. Every result
retains the observatory address, typed query, total count, returned count,
records, and its own content address. Offset and limit are validated before
the slice is taken.

Diff queries are bounded and expose:

```text
summary, items, added, removed, unchanged, changed,
improved, regressed, mixed
```

They support action, direction, candidate/baseline state, and text filters.
The fixed-column CSV and Markdown renderers operate over the same query
records as JSON; format selection never changes selection semantics.

Verification queries are independently addressed views over `verification.json`
and expose:

```text
summary, checks, failed, required, optional
```

They support severity, pass-state, case-insensitive check-text, offset, and
limit filters. `summary` returns the verification summary; the other resources
return check records. The query result retains the verification address and a
content address, so a filtered export can be referenced without copying the
source package or exposing its input path.

## Python API

The core API is available from the module named:

```text
glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory
```

Typical in-memory use:

```python
from glio_noncode import (
    build_assurance_history_observatory,
    build_assurance_history_observatory_verification,
    query_assurance_history_observatory,
    write_assurance_history_observatory,
)

observatory = build_assurance_history_observatory(
    (history_one, history_two),
    observatory_id="review-observatory:2026-08-27",
    member_ids=("download:one", "download:two"),
)
verification = build_assurance_history_observatory_verification(observatory)
write_assurance_history_observatory(observatory, output_directory)
members = query_assurance_history_observatory(observatory, resource="members")
```

Inspect only failed verification checks:

```python
from glio_noncode import query_assurance_history_observatory_verification

failed = query_assurance_history_observatory_verification(
    verification,
    resource="failed",
    limit=100,
)
```

Directory-oriented use is deliberately explicit:

```python
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory import (
    build_observatory_from_directories,
    load_observatory,
    verify_observatory_directory,
)

value = build_observatory_from_directories(
    ("run-one/history", "run-two/history"),
    observatory_id="review-observatory:downloaded-runs",
)
verify_observatory_directory("observatory-output")
reloaded = load_observatory("observatory-output")
```

The path-oriented helpers operate only at the process boundary. Their returned
objects remain path-free.

## CLI contract

The long-form CLI command is:

```text
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory
```

Build a package from downloaded-data histories:

```text
python -m glio_noncode.cli \
  <command> \
  --history-directory ./downloaded/run-one/history \
  --history-directory ./downloaded/run-two/history \
  --member-id download:one \
  --member-id download:two \
  --destination ./review-output/observatory \
  --format summary
```

Related operations are suffixed with:

```text
-verify
-query
-schema
-member-schema
-check-schema
-verification-schema
-verification-query
-verification-query-schema
-metrics-schema
-package-schema
-query-schema
-capabilities
-diff
-diff-verify
-diff-query
-diff-schema
-diff-item-schema
-diff-query-schema
-diff-capabilities
```

Build and verify return status `0` only for a promoted observatory. Held,
mixed, blocked, and empty packages still emit structured output but return
status `2`. Input, type, persistence, and contract errors return status `1`.
This lets Actions preserve a review artifact for a hold while distinguishing
it from a malformed input.

## HTTP contract

The HTTP family is appended to the existing release-registry federation gate
review decision-ledger assurance-history route:

```text
.../decision-ledger/assurance-history/observatory
```

Supported routes are:

| Route | Operation |
| --- | --- |
| `/observatory` | Build from repeated `history_directory`, `history`, or `input` values. |
| `/observatory/verify` | Verify an exact persisted package. |
| `/observatory/query` | Query a persisted package. |
| `/observatory/capabilities` | Return limits, resources, files, and features. |
| `/observatory/schema` | Return the summary schema. |
| `/observatory/member-schema` | Return the member schema. |
| `/observatory/check-schema` | Return the check schema. |
| `/observatory/verification-schema` | Return the verification schema. |
| `/observatory/verification-query` | Query verification summary or check records. |
| `/observatory/verification-query-schema` | Return the verification query schema. |
| `/observatory/metrics-schema` | Return the metrics schema. |
| `/observatory/package-schema` | Return the package schema. |
| `/observatory/query-schema` | Return the query schema. |
| `/observatory/diff` | Compare `baseline` and `candidate` packages. |
| `/observatory/diff/verify` | Verify a diff package. |
| `/observatory/diff/query` | Query a diff package. |
| `/observatory/diff/schema` | Return the diff schema. |
| `/observatory/diff/item-schema` | Return the diff item schema. |
| `/observatory/diff/query-schema` | Return the diff query schema. |
| `/observatory/diff/capabilities` | Return the same capability contract. |

`format=json` is the default. `format=csv` and `format=markdown` return the
deterministic renderer output with the appropriate content type. A promoted
build returns `200`; a non-promoted but structurally valid build returns
`422`; malformed input returns `400`.

Repeated query values are parsed as ordered arrays. `member_id` values must
align with `history_directory` values. The HTTP adapter never treats a local
path as public data.

## Downloaded-data demo

The runnable demonstration is:

```text
examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_demo.py
```

It accepts current-format history directories produced by the preceding
downloaded-data assurance-history demo. This makes the input boundary
observable without introducing a fixture-only shortcut:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_demo.py \
  --history ./downloaded/run-one/history \
  --destination ./demo-output/observatory \
  --format summary
```

The demo reloads its own exact package before producing a report. With
`--baseline`, it also writes an exact two-file member diff. Summary output
contains only public aggregate addresses, counters, and state. The test suite
also exercises the current persisted downloaded-data package when it is
available in the local environment.

## Actions contract

`.github/workflows/assurance-history-observatory.yml` compiles the new module,
API, and CLI, runs the focused observatory suite, runs the upstream history and
public-surface suites, and invokes the capability command. It uses read-only
repository permissions. The workflow does not download private data or encode
developer identity into artifacts.

## Failure behavior

The implementation intentionally fails closed for:

- a plain mapping supplied where a typed history is required;
- empty or mismatched member-ID arrays;
- duplicate history or member identities;
- an empty member carrying a terminal snapshot or non-initial head;
- a non-empty member carrying the `empty` state;
- any non-conserved transition, gate, finding, or check counter;
- an aggregate state that does not match member projections;
- an aggregate address that does not reproduce;
- tampered verification check counts or check addresses;
- non-canonical JSON, manifest drift, or artifact hash drift;
- a symlink or extra package file;
- unsupported query resources or out-of-range windows; and
- legacy packages that do not have the exact current file set.

No error is converted to a promotable empty observatory. A caller can catch
`ValidationError` for typed contract failures and `GlioError` at the CLI/demo
boundary.

## Review and science limitations

The observatory verifies software contracts and public release posture. It
does not evaluate tumor biology, variant pathogenicity, assay validity,
clinical utility, cohort representativeness, or any other scientific question.
The transition direction is a deterministic operational comparison of stored
review counters and readiness fields. It must not be read as a scientific
improvement or regression without an appropriate domain review.

Downloaded files remain subject to their original license, privacy, and
provenance obligations. The public observatory package contains only the
declared path-free projections and addresses. Operators should keep source
data in an access-controlled location and publish only the exact artifacts
that have passed their applicable review.

## Verification checklist

Before accepting an observatory package, a reviewer should confirm:

1. every source history is current-format and independently verified;
2. member IDs are stable and meaningful to the review context;
3. the aggregate state matches the member state table;
4. the readiness projection is conjunctive and not overridden manually;
5. transition, gate, finding, and check counters conserve;
6. verification contains eight passing required checks;
7. the exact five-file package has no extra files or symlinks;
8. a reload produces the same content addresses;
9. a diff is interpreted as operational review evidence, not science; and
10. privacy and license restrictions for the source downloads remain in force.

This checklist is intentionally separate from the code's typed verification:
it gives a human reviewer a compact handoff procedure while the implementation
enforces machine-checkable invariants.

## Archive and chunk transport

The exact five-file directory can be written as a deterministic ZIP archive and
then transported as bounded content-addressed chunks. The archive manifest
records the five `observatory/` payload files and their byte receipts. The
archive-transfer manifest records the archive address, fixed chunk policy,
contiguous ranges, and one hash per chunk. Reassembly verifies both layers and
must reproduce the original archive address.

```powershell
python -m glio_noncode <observatory-command>-archive --input review-output/observatory --destination review-output/observatory.zip --format summary
python -m glio_noncode <observatory-command>-archive-transfer --input review-output/observatory.zip --destination review-output/transfer --chunk-size 65536 --format summary
python -m glio_noncode <observatory-command>-archive-transfer-verify --input review-output/transfer
python -m glio_noncode <observatory-command>-archive-transfer-query --input review-output/transfer --resource chunks --limit 50
```

The transfer surface is path-free in its public projections, rejects missing,
extra, symlinked, non-canonical, and tampered members, and supports manifest
inspection before byte reassembly. See [the archive-transfer contract](RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER.md).
