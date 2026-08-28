# Release-registry federation gate review decision-ledger assurance history

Status: implemented in the current repository build.

This document is the contract for the longitudinal assurance-history module.
It describes what is accepted, what is produced, how the address graph is
recomputed, how operators use the package, and how failures are expected to
appear. The contract is deliberately narrower than a general event store: it
records verified release-gate observations and nothing else.

## 1. Purpose

The release-registry federation pipeline already produces a review decision
ledger and an independently recomputed assurance gate. One assurance gate is a
point-in-time decision. Operational review needs a second dimension: the
ability to compare successive verified decisions without trusting timestamps,
filesystem names, or mutable annotations.

The history module supplies that second dimension.

It accepts a sequence of current-format assurance gates.

It assigns each gate a stable snapshot identity.

It records an immutable entry for each snapshot.

It links each entry to the previous entry by content address.

It recomputes a transition from the previous quality vector.

It projects the terminal entry into a history-level decision.

It persists the result as a small exact-file package.

It compares two verified histories through addressed diff items.

It exposes bounded API, CLI, schema, and capability surfaces.

It rejects shapes that belong to older modules instead of silently converting
them.

The result is useful for release review, regression triage, reproducibility
checks, and offline audit. It is not a scientific model, a clinical decision
system, or a substitute for review policy.

## 2. Scope and non-goals

### In scope

| Area | Contract |
| --- | --- |
| Inputs | Current-format persisted assurance gates or current-format decision ledgers that can be assured independently. |
| Ordering | Caller-supplied order is preserved; default snapshot identities are derived from gate content addresses. |
| Identity | Histories, entries, diff items, and query results have deterministic content addresses. |
| State | `empty`, `promote`, `hold`, and `block` are the history state vocabulary. |
| Transitions | `initial`, `stable`, `improved`, `regressed`, and `changed` are the entry transition vocabulary. |
| Persistence | Exact canonical JSON packages with manifest byte receipts and atomic writes. |
| Query | Bounded summary, entry, transition, state, text, and diff projections. |
| Verification | Structural, linkage, counter, transition, terminal, byte, and public-boundary checks. |
| Integration | Package exports, HTTP routes, CLI commands, public-surface inventory, and Actions checks. |

### Out of scope

| Area | Reason |
| --- | --- |
| Mutable history editing | An append-only record is easier to replay and review. |
| Automatic source discovery | Inputs must be explicit and already curated by an upstream boundary. |
| Repository cloning | The build is independent of prior repositories and frameworks. |
| Scientific inference | This module reports gate evidence; it does not infer disease biology. |
| Private identity | Public projections must not contain user, author, model, or machine identity. |
| Wall-clock ordering | Timestamps create nondeterministic addresses and are not needed for this contract. |
| Unlimited export | Every query and package collection has a fixed maximum. |
| Legacy conversion | A wrong package shape is an explicit compatibility failure. |

## 3. Upstream boundary

The direct upstream object is `DecisionLedgerAssuranceGate` from
`assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance`.
The history module does not trust an arbitrary mapping with similar keys. It
requires the typed object and verifies the object before making an entry.

When the caller starts with a decision ledger, the demo and integration layer
recompute an assurance gate first:

```text
persisted decision ledger
        |
        v
independent assurance findings
        |
        v
assurance release gate
        |
        v
history entry
```

The upstream assurance gate already contains:

| Link | Meaning |
| --- | --- |
| `ledger_address` | Address of the decision ledger that was assured. |
| `assurance.content_address` | Address of the independent findings projection. |
| `gate.content_address` | Address of the release-gate checks and decision. |
| `content_address` | Address of the combined assurance-gate bundle. |
| `gate.state` | `ready`, `held`, or `blocked` source outcome. |
| `gate.accepted` | Whether the source gate was acceptable for review. |
| `gate.release_ready` | Whether the source gate may be promoted. |
| `assurance.state` | Independent assurance result such as `passed`, `warning`, or `blocked`. |

The history entry copies only stable public projections of these fields. It
does not copy input directory names, local paths, environment variables, or
unbounded source records.

## 4. Public data model

### 4.1 Entry

An `AssuranceHistoryEntry` is one verified observation.

| Field | Type | Invariant |
| --- | --- | --- |
| `history_id` | bounded string | Matches the containing history identity. |
| `version` | fixed string | Matches the module version. |
| `boundary` | fixed string | Matches the public boundary constant. |
| `ordinal` | non-negative integer | Starts at zero and increments by one. |
| `snapshot_id` | bounded string | Unique within one history. |
| `previous_address` | address string | `INITIAL_HEAD` for ordinal zero; prior entry address otherwise. |
| `gate_address` | address string | Exact upstream release-gate address. |
| `assurance_address` | address string | Exact upstream assurance address. |
| `ledger_address` | address string | Exact upstream decision-ledger address. |
| `bundle_address` | address string | Exact upstream assurance-gate bundle address. |
| `gate_state` | enum | `ready`, `held`, or `blocked`. |
| `assurance_state` | enum | Upstream assurance state vocabulary. |
| `accepted` | boolean | Copied from the upstream gate. |
| `release_ready` | boolean | Copied from the upstream gate. |
| `finding_count` | count | Matches the upstream assurance count. |
| `passed_finding_count` | count | Never exceeds `finding_count`. |
| `warning_finding_count` | count | Never exceeds `finding_count`. |
| `blocker_finding_count` | count | Never exceeds `finding_count`. |
| `check_count` | count | Matches the upstream gate check count. |
| `passed_check_count` | count | Never exceeds `check_count`. |
| `warning_check_count` | count | Never exceeds `check_count`. |
| `blocker_check_count` | count | Never exceeds `check_count`. |
| `transition` | enum | Determined from the preceding entry and current quality vector. |
| `content_address` | address string | Recomputed from all public entry fields with this field cleared. |

The entry intentionally contains counts rather than full findings and checks.
The source assurance and gate packages remain the authoritative detailed
records. History is the comparison index and terminal release projection.

### 4.2 History

An `AssuranceHistory` is an ordered tuple of entries plus a terminal summary.

| Field | Type | Invariant |
| --- | --- | --- |
| `history_id` | bounded string | Stable identity supplied by the caller. |
| `version` | fixed string | Current history version. |
| `boundary` | fixed string | Public boundary identifier. |
| `entry_count` | count | Equals `len(entries)`. |
| `head_address` | address string | `INITIAL_HEAD` when empty, terminal entry address otherwise. |
| `state` | enum | `empty` when empty, terminal `gate_state` otherwise. |
| `latest_snapshot_id` | nullable string | Terminal snapshot or null when empty. |
| `latest_gate_address` | nullable address | Terminal gate or null when empty. |
| `accepted` | boolean | False when empty; terminal acceptance otherwise. |
| `release_ready` | boolean | False when empty; terminal release decision otherwise. |
| `initial_count` | count | Conservation of entry transitions. |
| `stable_count` | count | Conservation of entry transitions. |
| `improved_count` | count | Conservation of entry transitions. |
| `regressed_count` | count | Conservation of entry transitions. |
| `changed_count` | count | Conservation of entry transitions. |
| `promote_count` | count | Conservation of terminal gate states. |
| `hold_count` | count | Conservation of terminal gate states. |
| `block_count` | count | Conservation of terminal gate states. |
| `entries` | bounded tuple | Contiguous, ordered, unique entry chain. |
| `content_address` | address string | Recomputed from the history projection with this field cleared. |

The summary is not independently authored. It is derived from the entries at
build time and checked again at load time.

### 4.3 Diff item

An `AssuranceHistoryDiffItem` joins baseline and candidate records by
`snapshot_id`.

| Field | Type | Invariant |
| --- | --- | --- |
| `ordinal` | non-negative integer | Stable sorted position in the diff. |
| `snapshot_id` | bounded string | Join key. |
| `action` | enum | `added`, `removed`, `unchanged`, or `changed`. |
| `direction` | enum | `unchanged`, `improved`, `regressed`, or `mixed`. |
| `baseline_entry_address` | nullable address | Present for candidate joins that existed in baseline. |
| `candidate_entry_address` | nullable address | Present for candidate joins that exist in candidate. |
| `baseline_gate_state` | nullable enum | Baseline state when present. |
| `candidate_gate_state` | nullable enum | Candidate state when present. |
| `baseline_release_ready` | nullable boolean | Baseline release projection when present. |
| `candidate_release_ready` | nullable boolean | Candidate release projection when present. |
| `detail` | bounded string | Deterministic human-readable difference summary. |
| `content_address` | address string | Recomputed from the item projection. |

The diff item stores both entry addresses so a reviewer can walk from a
comparison back to the exact history package without relying on a mutable
path.

### 4.4 Diff

An `AssuranceHistoryDiff` retains both history identities and addresses.

| Field | Meaning |
| --- | --- |
| `diff_id` | Stable caller-selected diff identity. |
| `baseline_history_id` | History identity on the left side. |
| `candidate_history_id` | History identity on the right side. |
| `baseline_address` | Address of the complete baseline history. |
| `candidate_address` | Address of the complete candidate history. |
| `item_count` | Number of joined snapshot records. |
| `added_count` | Candidate-only snapshots. |
| `removed_count` | Baseline-only snapshots. |
| `unchanged_count` | Same public entry projection. |
| `changed_count` | Same snapshot identity with changed projection. |
| `improved_count` | Items whose quality vector improved. |
| `regressed_count` | Items whose quality vector regressed. |
| `state` | Aggregate `unchanged`, `improved`, `regressed`, or `mixed`. |
| `items` | Bounded sorted item tuple. |
| `content_address` | Address of the complete diff projection. |

## 5. State and transition semantics

### 5.1 State mapping

History state follows the terminal gate state exactly.

| Gate state | History state | Accepted | Release-ready |
| --- | --- | --- | --- |
| `ready` | `promote` | true | true |
| `held` | `hold` | true | false |
| `blocked` | `block` | false | false |
| no entries | `empty` | false | false |

The history state is a release projection, not a score. A held entry remains a
valid record and is not silently downgraded to an input failure. A blocked
entry is retained so the reason for regression remains reviewable.

### 5.2 Quality vector

Transition classification uses a lexicographic quality vector derived from
public entry values. The vector is intentionally explicit and finite:

```text
(accepted,
 release_ready,
 -blocker_finding_count,
 -blocker_check_count,
 -warning_finding_count,
 -warning_check_count,
 passed_finding_count,
 passed_check_count)
```

Boolean values are ordered as false before true. Negative failure counts make
fewer blockers and warnings better. More passed findings and checks are better.
No timestamp, path, or arbitrary text participates in classification.

### 5.3 Transition table

| Previous | Current | Quality relation | Transition |
| --- | --- | --- | --- |
| none | any | not applicable | `initial` |
| present | identical public quality | equal | `stable` |
| present | strictly better and no worse field | greater | `improved` |
| present | strictly worse and no better field | lower | `regressed` |
| present | incomparable or changed outside the quality order | mixed | `changed` |

The exact quality vector is retained in the implementation rather than
serialized as an extra public field. That keeps the public format small while
making the verifier able to recompute every classification.

### 5.4 Counter conservation

For every non-empty history:

```text
initial_count
+ stable_count
+ improved_count
+ regressed_count
+ changed_count
= entry_count
```

The state counters satisfy:

```text
promote_count
+ hold_count
+ block_count
= entry_count
```

An empty history has all counters zero and `head_address == INITIAL_HEAD`.
These equations are checked in typed construction, mapping construction, and
directory loading.

## 6. Address graph

The address graph is the core reproducibility mechanism.

```text
decision ledger address
          |
          v
assurance address
          |
          v
gate address -----> bundle address
          |
          v
history entry address
          |
          v
history head address
          |
          v
history content address
```

Each arrow is a value link, not a filesystem link.

The first entry points to `INITIAL_HEAD`.

Every later entry points to the previous entry's `content_address`.

The history `head_address` equals the terminal entry address.

The history address includes the complete ordered entry projection.

The diff address includes baseline and candidate addresses plus all diff items.

The query result address includes the query parameters and returned records.

Address recomputation always clears the address being recomputed before
canonical hashing. A pending address is permitted only transiently during
construction and cannot be loaded from disk.

## 7. Deterministic construction

### 7.1 Build inputs

`build_history` accepts a sequence of typed assurance gates.

The caller may provide `snapshot_ids`.

If no snapshot IDs are provided, the gate bundle address becomes the snapshot
identity.

If IDs are provided, their count must equal the gate count.

Each ID is bounded, non-empty, and unique within the build.

The caller-supplied gate order is preserved.

The same gates, IDs, and history ID always produce the same entry and history
addresses.

### 7.2 Append inputs

`append_history` accepts one typed gate, an optional snapshot ID, and an
optional expected history address.

The expected address is an optimistic concurrency guard. If it does not equal
the current history content address, append fails before any derived value is
returned.

The entry ancestry guard uses the current `head_address`, not the history
content address. This distinction is deliberate: a history content address
identifies the whole object, while an entry previous address identifies the
chain head.

Duplicate snapshot IDs are rejected even when their gates are byte-identical.

The original history object is never mutated.

### 7.3 Empty history

An empty history is a valid typed value.

It has no latest snapshot.

It has no latest gate.

It is not accepted.

It is not release-ready.

It has `state == empty`.

It has an addressed content projection.

This makes “no observations” distinct from “a blocked observation.”

## 8. Diff construction

`build_diff` first verifies both typed histories.

It joins entries by `snapshot_id`.

It sorts join keys deterministically.

It labels one-sided keys as `added` or `removed`.

It labels same-projection keys as `unchanged`.

It labels same-ID, changed-projection keys as `changed`.

It calculates direction from the baseline and candidate quality vectors.

One-sided additions use the candidate's quality against the baseline absence and
are treated as improvement.

One-sided removals are treated as regression because evidence disappeared.

The aggregate direction is:

| Observed directions | Diff state |
| --- | --- |
| none except unchanged | `unchanged` |
| improvement only | `improved` |
| regression only | `regressed` |
| both improvement and regression | `mixed` |

The verifier recomputes the join, action, direction, counters, aggregate
state, and final content address.

## 9. Exact persistence

### 9.1 History package

The history package contains exactly:

```text
manifest.json
history.json
entries.json
```

`history.json` contains the history summary without the repeated entry array.

`entries.json` contains the versioned ordered entry document.

`manifest.json` contains the package version, public boundary, history address,
file names, byte counts, byte addresses, and content addresses needed to verify
the two artifact files.

No other file is admitted.

### 9.2 Diff package

The diff package contains exactly:

```text
manifest.json
diff.json
```

The manifest records the diff identity, baseline and candidate history
addresses, and the exact byte receipt for `diff.json`.

### 9.3 Canonical bytes

JSON is encoded as UTF-8.

Objects use sorted keys.

Separators are compact and deterministic.

Trailing newline policy is fixed by the shared serialization helper.

A loader reads bytes before parsing.

It parses the value.

It reserializes the parsed value canonically.

It rejects any byte difference.

It recomputes the artifact byte address.

It compares the byte count and address with the manifest.

It then maps the typed value and verifies the content address.

### 9.4 Atomic writes

Writers create a short-lived temporary sibling.

Each artifact is written completely before replacement.

The destination is replaced only when `overwrite=True`.

Existing directories are not reused implicitly.

Temporary names do not contain source paths or private identifiers.

Directory entries must be regular files.

Symlinks are rejected on read and write paths.

## 10. Compatibility boundary

The module recognizes one current history version and one current diff version.

The following are explicit failures:

| Input | Failure |
| --- | --- |
| Older review history with `observations` | Legacy shape rejected. |
| Assurance gate manifest with unrelated artifact fields | Wrong manifest contract rejected. |
| Missing `entries.json` | Exact package failure. |
| Additional file | Exact package failure. |
| Symlinked artifact | Regular-file failure. |
| Non-canonical JSON | Canonical-byte failure. |
| Changed manifest receipt | Manifest linkage failure. |
| Unknown mapping key | Strict mapping failure. |
| Missing required key | Typed mapping failure. |
| Invalid enum string | Vocabulary failure. |
| Duplicate snapshot ID | History identity failure. |
| Wrong previous address | Chain continuity failure. |
| Wrong terminal summary | Projection failure. |
| Mismatched expected head | Optimistic concurrency failure. |

The failure is intentionally not converted into an empty history or a best-
effort import. Operators can then distinguish unsupported input from a valid
but held release.

## 11. Query contract

### 11.1 History resources

| Resource | Returned records |
| --- | --- |
| `summary` | One addressed history summary. |
| `entries` | All selected entry records. |
| `entries` | All selected entry records. |
| `transitions` | Entries whose transition is not `stable`. |
| `states` | Entries with a release gate state. |

Transition and gate-state filters select `initial`, `stable`, `improved`,
`regressed`, and `changed` records without expanding the resource vocabulary.

### 11.2 History filters

| Filter | Behavior |
| --- | --- |
| `transition` | Exact transition match. |
| `gate_state` | Exact source gate state match. |
| `assurance_state` | Exact independent assurance state match. |
| `accepted` | Exact boolean match. |
| `release_ready` | Exact boolean match. |
| `text` | Deterministic bounded search over public textual fields. |
| `offset` | Non-negative page start. |
| `limit` | Positive bounded page size. |

### 11.3 Diff resources

| Resource | Returned records |
| --- | --- |
| `summary` | One addressed diff summary. |
| `items` | All selected diff items. |
| `items` | All selected diff items. |
| `changes` | Items whose action is `changed`. |
| `directions` | Items whose direction is not `unchanged`. |

Action and direction filters select `added`, `removed`, `unchanged`, `changed`,
`improved`, or `regressed` records without expanding the resource vocabulary.

### 11.4 Query safety

The resource name is validated before filtering.

Offset and limit are bounded before slicing.

Query object and keyword filters cannot be supplied together.

Returned records are copied into a new immutable result.

Query results have their own content address.

The address changes when the query window changes.

Text filtering never searches local paths because paths are not in public
projections.

## 12. CLI contract

The canonical build command is:

```text
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history
```

The command accepts repeatable `--gate` directories.

It accepts repeatable `--snapshot-id` values.

It accepts `--history-id`.

It accepts `--destination` and `--allow-existing`.

It emits summary, JSON, CSV, or Markdown.

The build command returns status zero when the terminal history is promotable.

It returns status two when the history is valid but held or blocked.

It returns status one for invalid input or persistence failure.

The verify command loads one history package and performs the same checks.

The query command loads one history package and emits a bounded projection.

The `-schema` command emits a closed schema document.

The `-entry-schema` command emits the entry schema.

The `-query-schema` command emits query parameters and result fields.

The `-capabilities` command emits the fixed feature vocabulary.

The `-diff` command compares two history packages.

The `-diff-verify` command verifies one diff package.

The `-diff-query` command queries one diff package.

The `-diff-schema`, `-diff-item-schema`, `-diff-query-schema`, and
`-diff-capabilities` commands describe the diff surface.

## 13. HTTP contract

The history route is nested under the release-registry federation gate review
decision-ledger assurance route.

The route family mirrors the CLI.

| Operation | Input | Success | Valid hold/block |
| --- | --- | --- | --- |
| build | repeatable gate directory or assurance gate input | 200 | 422 |
| verify | history directory | 200 | 422 when terminal not promotable |
| query | history directory plus filters | 200 | 200 |
| diff | baseline and candidate history directories | 200 | 200 |
| diff verify | diff directory | 200 | 200 |
| diff query | diff directory plus filters | 200 | 200 |
| schema | none | 200 | not applicable |
| capabilities | none | 200 | not applicable |

Structural errors such as missing directories, wrong package versions, or
tampered bytes are client errors. A valid held gate is not a structural error.

The response body is always a public projection. It does not include local
input paths, temporary names, or hidden runtime context.

## 14. Real downloaded-data demonstration

The demonstration script is:

```text
examples/release_registry_federation_gate_review_decision_ledger_assurance_history_demo.py
```

It supports two input modes.

### Decision-ledger mode

Use this mode when the downloaded-data pipeline has already produced current
decision-ledger packages:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_demo.py \
  --ledger ./downloaded/run-one/ledger \
  --ledger ./downloaded/run-two/ledger \
  --snapshot-id downloaded-run-one \
  --snapshot-id downloaded-run-two \
  --destination ./out/history \
  --format summary
```

For each ledger, the script loads the exact package, recomputes the assurance
gate, verifies the gate against the ledger, and only then calls `build_history`.

### Assurance-gate mode

Use this mode when current assurance-gate packages already exist:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_demo.py \
  --assurance-gate ./downloaded/run-one/assurance-gate \
  --assurance-gate ./downloaded/run-two/assurance-gate \
  --destination ./out/history \
  --format markdown
```

The two modes are mutually exclusive.

### Comparing two downloaded histories

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_demo.py \
  --ledger ./downloaded/run-three/ledger \
  --snapshot-id downloaded-run-three \
  --destination ./out/candidate-history \
  --baseline ./out/history \
  --diff-destination ./out/history-diff \
  --format markdown
```

The summary reports source kind, source count, history and head addresses,
terminal state, readiness, transition totals, and optional diff address. It
does not report source paths.

## 15. Review workflow

The recommended offline review sequence is:

1. Verify the upstream decision-ledger package.
2. Recompute its independent assurance gate.
3. Verify the gate against the ledger.
4. Add the gate to the history in chronological input order.
5. Verify the written history package after reload.
6. Query entries by transition and gate state.
7. Compare candidate and baseline histories.
8. Inspect every regressed diff item.
9. Preserve the exact packages and public summary.
10. Promote only when the terminal history state is `promote`.

The history is evidence for a decision review. It does not make an approval
decision on behalf of the reviewer.

## 16. Failure triage

### Unsupported package

Symptom: loader reports wrong version, unknown manifest fields, or missing
exact files.

Action: route the input back to the producing module. Do not rename files or
remove fields to force a load.

### Canonical-byte failure

Symptom: parsed JSON appears valid but byte verification fails.

Action: preserve the original package for forensic review. Rebuild from the
typed source rather than reformatting the artifact in place.

### Chain failure

Symptom: an entry previous address does not equal the prior entry address.

Action: identify the first divergent ordinal. Compare its public entry mapping
with the producing history and discard any hand-edited replacement.

### Counter failure

Symptom: transition or state totals do not equal the entry count.

Action: treat the package as invalid. Counters are derived fields and must not
be manually patched.

### Terminal projection failure

Symptom: history state, latest snapshot, or release-ready flag disagrees with
the final entry.

Action: rebuild or reject. A terminal mismatch can hide a later blocked entry.

### Regression

Symptom: diff direction is `regressed` or aggregate state is `mixed`.

Action: query `regressed`, inspect baseline and candidate entry addresses, then
inspect the source assurance and gate packages at those addresses.

### Valid hold

Symptom: command returns status two with a complete history package.

Action: retain the package and route to review. Status two means a valid
non-promotable result, not a parser failure.

## 17. Privacy and public boundary

The public boundary is checked recursively.

Forbidden keys include identity, authorship, model, language, private, secret,
token, email, and user-style fields.

Filesystem paths are never copied into a public entry.

Report formatting is path-free by construction.

Source package names are not treated as public evidence.

Temporary write paths are not serialized.

The content address is not a privacy exemption. Addresses are computed only
from the allowed public projection.

The boundary test traverses mappings, tuples, lists, dataclasses, and nested
typed values.

## 18. Performance and boundedness

The common operation is append, which is linear in history length because the
current typed history is rebuilt immutably.

The persistence writer serializes three small documents.

Diff construction sorts the union of baseline and candidate snapshot IDs.

Query operations filter a bounded tuple and slice the result.

All collection sizes have explicit maxima.

Addressing uses canonical serialization once per derived object.

No network access is required by the module.

No repository discovery is performed by the module.

The current implementation favors reproducibility and review clarity over a
mutable index. A future index can be added only if it preserves the same
content-addressed projections and exact verification rules.

## 19. CI contract

`.github/workflows/assurance-history.yml` checks the focused surface.

It compiles the history module, API, and CLI.

It runs the 55 focused history tests.

It runs the upstream assurance and public-surface tests.

It invokes the capability command.

The workflow has read-only repository permissions.

The workflow does not download external data.

The workflow does not use a private dataset.

The workflow treats a valid held result as a test fixture rather than a CI
failure; only assertion or structural errors fail the job.

## 20. Verification matrix

| Category | Verified behavior |
| --- | --- |
| Construction | Empty and populated histories build deterministically. |
| Identity | Default and custom history IDs behave predictably. |
| Chain | Entry previous addresses form a contiguous chain. |
| Append | Expected head, duplicate snapshot, and terminal transition rules are enforced. |
| Mapping | Round trips work; unknown and missing fields fail closed. |
| Boundary | Recursive public projection contains no forbidden metadata. |
| Schema | Objects are closed and arrays are bounded. |
| Diff | Added, removed, unchanged, changed, improved, regressed, and mixed cases are covered. |
| Query | Resource, state, transition, text, boolean, offset, and limit filters are covered. |
| Persistence | Exact files, reload, overwrite, canonical bytes, manifest receipts, extra files, and symlinks are covered. |
| Compatibility | Older downloaded artifacts are rejected as incompatible. |
| CLI | Build, verify, query, diff, schema, and capability commands are covered. |
| API | Build, verify, query, diff, schema, and capability routes are covered. |
| Real data | Current-format persisted downloaded-data outputs are loaded and re-assured. |

## 21. Acceptance checklist

- [x] Input type is explicit.
- [x] Input version is checked.
- [x] Gate assurance is independently recomputed when starting from a ledger.
- [x] Snapshot IDs are bounded and unique.
- [x] Entry ancestry is content-addressed.
- [x] Optimistic head protection is available.
- [x] Transition classification is deterministic.
- [x] Readiness and state counters are conserved.
- [x] Terminal history projection is verified.
- [x] History and diff addresses are recomputed.
- [x] History persistence has exactly three files.
- [x] Diff persistence has exactly two files.
- [x] Canonical bytes are enforced.
- [x] Manifest byte receipts are enforced.
- [x] Extra files and symlinks are rejected.
- [x] Legacy package shapes are rejected.
- [x] Query windows are bounded.
- [x] JSON, CSV, and Markdown outputs are deterministic.
- [x] HTTP and CLI surfaces are integrated.
- [x] Public-surface inventory is updated.
- [x] Actions coverage is present.
- [x] Real downloaded-data demonstration is present.
- [x] Focused regression tests pass.

## 22. Implementation map

| Artifact | Responsibility |
| --- | --- |
| `src/glio_noncode/assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history.py` | Typed model, builders, verifiers, address graph, query, serializers, schemas, and persistence. |
| `src/glio_noncode/api.py` | HTTP route family and response status mapping. |
| `src/glio_noncode/cli.py` | Long-form command registration and dispatch. |
| `src/glio_noncode/public_surface_audit.py` | Public API/CLI inventory closure. |
| `examples/release_registry_federation_gate_review_decision_ledger_assurance_history_demo.py` | Real downloaded-data demonstration. |
| `tests/test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history.py` | Focused behavioral and failure coverage. |
| `.github/workflows/assurance-history.yml` | Actions compile, regression, public-boundary, and capability contract. |

## 23. Closing principle

Every history record must answer four questions without consulting a mutable
database:

1. Which verified decision was observed?
2. What was the prior verified decision?
3. What changed in the release-quality projection?
4. Can another reader recompute the answer from the package bytes?

If any answer is unavailable, the package is not a promotable history.
