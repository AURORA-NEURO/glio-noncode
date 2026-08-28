# Release-Registry Federation Gate Review Decision Ledger Assurance

This document specifies the independent assurance boundary for the current
release-registry federation gate review decision ledger. It is an operational
integrity layer for public, reproducible, content-addressed review records.
It does not rank scientific evidence, alter source findings, or turn operator
handling into a new source release decision.

The boundary was added after the release-registry federation gate review queue
and its append-only decision ledger. The ledger already verifies its own
construction contract. This module creates a separate projection that checks
the ledger as an untrusted snapshot and records the result in addressed
findings. A second gate then decides whether that assurance is promotable.

## Scope

The input is a current-format persisted decision ledger produced by the
release-registry federation gate review module.

The input must contain the exact four ledger documents:

1. `manifest.json`;
2. `ledger.json`;
3. `entries.json`; and
4. `replay.json`.

The assurance builder loads and verifies that package before it constructs an
assurance gate. The builder does not accept an older observatory packet,
federation package, or unrelated ledger by guessing field conversions.

The output is an independent assurance gate with two nested projections:

1. `assurance`, which contains fourteen recomputed findings; and
2. `gate`, which contains ten promote/hold/block checks.

The output is intentionally public and path-free. It contains bounded text,
fixed-vocabulary state values, identifiers, addresses, counters, and receipt
links. It does not expose local paths, users, agents, assistants, authors,
models, languages, private metadata, secrets, tokens, or credentials.

## Design principles

### Source authority is preserved

The source queue and source federation gate retain authority over acceptance
and release readiness. A reviewer can record an evidence-backed remediation,
acknowledgement, escalation, or permitted waiver. That action changes the
review replay state, not the source gate's original decision.

If the source gate was not release-ready, a cleanly handled review ledger can
still be accepted as an operational record, but the independent assurance
gate remains on hold. A new source gate and a new queue snapshot are required
to change source readiness.

### Independent recomputation

The assurance builder does not call the decision-ledger verifier as its
primary evidence. It independently checks content addresses, item identities,
entry ancestry, action counts, evidence policy, transition policy, replay
state, source authority, and public projection closure.

The independent verifier can therefore produce a failed finding when a
mutable in-memory object has been tampered with after construction, even if
the source constructor originally accepted that object.

### Fail closed

Required failed findings are blockers. Optional failed findings are warnings.
The assurance state is:

| Failed required findings | Failed optional findings | Assurance state | Assurance accepted | Assurance release-ready |
| ---: | ---: | --- | --- | --- |
| 0 | 0 | `passed` | `true` | `true` |
| 0 | 1 or more | `warning` | `true` | `false` |
| 1 or more | any | `blocked` | `false` | `false` |

The release gate applies its own check policy. A failed required check makes
the gate `block`. A failed optional check makes it `hold`. Only all-passed
checks make it `promote`.

### Canonical public receipts

Every finding and check has a content address derived from its canonical
public projection. The assurance, gate, bundle, and diff projections are also
addressed. Persisted JSON is canonical UTF-8, and each data document has a
byte receipt in its manifest.

## Data flow

```text
persisted review ledger
          |
          v
independent field and chain recomputation
          |
          +--> 14 addressed assurance findings
          |          |
          |          v
          |    assurance state
          |
          +--> 10 independent release checks
                     |
                     v
             promote / hold / block
                     |
                     v
       exact three-file assurance package
```

The builder uses only the current review ledger's public fields. The durable
assurance package does not embed the source ledger, which keeps the handoff
small and avoids duplicating a second mutable copy of the input. The ledger
address and queue address remain the linkage anchors.

## Contract identity

The implementation module is:

`src/glio_noncode/assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance.py`

The module exposes:

| Contract | Value or role |
| --- | --- |
| `VERSION` | current review-ledger assurance version derived from the current review version |
| `BOUNDARY` | `public_release_registry_federation_gate_review_decision_ledger_assurance` |
| `ASSURANCE_NAME` | `assurance.json` |
| `GATE_NAME` | `gate.json` |
| `FILES` | `manifest.json`, `assurance.json`, `gate.json` |
| `DIFF_NAME` | `diff.json` |
| `DIFF_FILES` | `manifest.json`, `diff.json` |
| `DEFAULT_ASSURANCE_ID` | stable default assurance identifier |
| `DEFAULT_GATE_ID` | stable default gate identifier |
| `DEFAULT_DIFF_ID` | stable default diff identifier |
| `MAX_FINDINGS` | 32 |
| `MAX_CHECKS` | 32 |
| `MAX_DIFF_ITEMS` | 64 |
| `MAX_QUERY_ITEMS` | 4,096 |

The observed build emits fourteen findings and ten checks. The extra capacity
in the bounded maxima is reserved for compatible future extensions without
accepting unbounded input.

## Finding model

Each finding has:

| Field | Meaning |
| --- | --- |
| `ordinal` | contiguous zero-based finding position |
| `finding_id` | stable ledger-scoped finding identifier |
| `plane` | one of the fixed assurance planes |
| `kind` | bounded machine-readable invariant name |
| `severity` | `pass`, `warning`, or `blocker` |
| `required` | whether failure blocks assurance acceptance |
| `passed` | recomputed outcome |
| `detail` | bounded explanation of the outcome |
| `remediation` | bounded operator-facing corrective action |
| `evidence_address` | addressed ledger snapshot used as evidence |
| `content_address` | addressed finding projection |

Passed findings always use `pass` severity. Failed required findings always
use `blocker` severity. Failed optional findings always use `warning` severity.
The constructor enforces this relationship so a serialized report cannot
claim that a blocker passed or that an optional warning is a required failure.

### Finding 0: ledger-address

This finding recomputes the ledger address from the ledger summary while
removing only the address field being checked. It catches direct edits to
identity-bearing summary fields, counters, state, readiness, and linkage.

Failure is required because an unauthenticated ledger cannot be used as the
subject of the remaining checks.

Recommended remediation is to rebuild the ledger with canonical content
addressing from the current verified queue snapshot.

### Finding 1: ledger-contract

This finding checks the review-ledger version and boundary and confirms that
the declared entry count equals the entry sequence length.

Failure is required because a ledger from another contract generation is not a
valid input to this assurance plane.

### Finding 2: queue-linkage

This finding checks that queue, source gate, source assurance, and replay
addresses exist and that replay retains the same queue and gate addresses as
the ledger. It also checks the entry sequence length used by the replay.

Failure is required because a ledger without a stable source relationship
cannot explain which review snapshot was handled.

### Finding 3: item-addresses

This finding independently recomputes every frozen queue item address and
checks item-ID and item-address uniqueness.

Failure is required. A modified item changes the meaning of every decision
that targets it, so the decision chain cannot be trusted after item drift.

### Finding 4: entry-chain

This finding checks all of the following for every entry:

1. the ordinal is contiguous;
2. the entry content address recomputes;
3. the first entry points to `none:review-head`;
4. later entries point to the preceding entry address; and
5. the ledger head equals the terminal entry address, or the initial head when
   the ledger has no entries.

Failure is required. The decision ledger is append-only, so an ancestry gap,
reordered entry, or forged head is a blocker.

### Finding 5: entry-item-linkage

This finding checks that each decision's item ID is present in the frozen item
set and that its item address equals the current address for that exact ID.

Failure is required. A decision with a valid-looking address but a different
item identity must not be replayed as if it handled the retained item.

### Finding 6: action-counters

This finding counts each action directly from the entries and compares those
counts with the ledger's acknowledge, remediate, waive, escalate, and reopen
counters. It also checks total entry conservation.

Failure is required. Counters are used by queue and gate queries and must not
be accepted when they disagree with the canonical entry sequence.

### Finding 7: evidence-policy

This finding applies the action evidence policy independently:

| Action | Evidence rule |
| --- | --- |
| `acknowledge` | must use the fixed no-evidence address |
| `remediate` | must carry a non-no-evidence address |
| `waive` | must carry a non-no-evidence address |
| `escalate` | must use the fixed no-evidence address |
| `reopen` | must use the fixed no-evidence address |

Failure is required. Evidence is not inspected as scientific content here;
the assurance layer checks that the decision carries the required addressed
receipt shape.

### Finding 8: transition-policy

This finding replays action transitions with an independent implementation of
the current review policy. It rejects illegal transitions such as:

1. acknowledging a clear item;
2. remediating an already resolved or waived item;
3. waiving a required blocker;
4. escalating an already closed item; or
5. reopening an item that was never handled.

Failure is required because an illegal action sequence invalidates the replay
state even if the individual entry addresses remain well formed.

### Finding 9: replay-projection

This finding rebuilds replay item states from the frozen queue and entry
sequence, then compares state counts, source fields, readiness, and queue/gate
linkage with the stored replay summary.

Failure is required. Stored replay is a convenience projection and must not
be trusted when it differs from the independent transition result.

### Finding 10: source-authority

This finding checks that ledger acceptance equals replay source acceptance and
that ledger readiness preserves replay source readiness. It prevents local
review handling from manufacturing source readiness.

Failure is required. A source gate that was held or blocked must remain held or
blocked at this boundary.

### Finding 11: closure-readiness

This finding checks the closure expression used by the ledger:

`release_ready == source_release_ready and state == clear`

It is optional at the assurance level because a valid ledger may be an
accepted, well-formed operational record that is still waiting for closure or
source readiness. The release gate applies this condition as an independent
optional hold check.

### Finding 12: public-boundary

This finding recursively checks the ledger's serialized public projection for
forbidden attribute keys and identity-bearing private metadata. It is required
and is also repeated at the gate boundary.

The check covers nested item, entry, and replay structures, not only the top
level summary.

### Finding 13: replay-addresses

This finding independently recomputes every replay-item address and the replay
snapshot address. It is distinct from replay state comparison so an address
drift cannot hide behind matching state counters.

Failure is required because downstream consumers use replay addresses as
stable receipt links.

## Gate model

Each gate check has:

| Field | Meaning |
| --- | --- |
| `ordinal` | contiguous check position |
| `check_id` | gate-scoped identifier |
| `plane` | assurance plane that owns the check |
| `kind` | bounded machine-readable check name |
| `required` | whether failure blocks acceptance |
| `passed` | check result |
| `detail` | bounded explanation |
| `evidence_address` | assurance or ledger address supporting the check |
| `content_address` | addressed check projection |

The independent gate emits ten checks.

### Check 0: assurance-accepted

Required. It passes only when no assurance finding is a required failure.

### Check 1: assurance-release-ready

Required. It passes only when the assurance report has no warnings or blockers.

### Check 2: source-accepted

Required. It passes only when the source replay reports source acceptance.

### Check 3: source-release-ready

Optional. A source hold creates a gate hold rather than a false promotion.

### Check 4: ledger-clear

Optional. A ledger with an active review state remains operationally valid but
is not promotable until it is clear.

### Check 5: no-open-items

Optional. Open or acknowledged items produce a hold. The check is deliberately
separate from the required no-blocked-items check so operators can distinguish
source blockers from incomplete handling.

### Check 6: no-blocked-items

Required. Required blocker items remaining in replay block the independent
gate.

### Check 7: no-escalated-items

Optional. Escalated items create a hold until the escalation is resolved or a
new source snapshot is supplied.

### Check 8: head-continuity

Required. The head must be the initial head for an empty ledger or the address
of the terminal entry for a non-empty ledger.

### Check 9: public-boundary

Required. Both ledger and assurance projections must remain public and
path-free.

## State interpretation

| Source state | Ledger replay state | Assurance state | Independent gate |
| --- | --- | --- | --- |
| source accepted and release-ready, no active items | `clear` | `passed` | `promote` |
| source accepted but not release-ready | `review` or `clear` | `passed` when structurally sound | `hold` |
| source not accepted | `blocked` | `passed` or `blocked` depending on structure | `block` |
| source accepted, required blocker remains | `blocked` | `passed` when structure is sound | `block` |
| source accepted, optional handling remains | `review` | `passed` when structure is sound | `hold` |
| chain, address, policy, or public tampering | any | `blocked` | `block` |

The table separates structural assurance from source readiness. A held source
can be fully assured as a trustworthy held artifact; it cannot be promoted by
that fact alone.

## Durable assurance package

The assurance gate is persisted with exactly these files:

```text
manifest.json
assurance.json
gate.json
```

No extra files are accepted. Directory symlinks and child symlinks are
rejected. Non-empty destinations require explicit overwrite.

### `assurance.json`

This document contains the assurance summary and all fourteen findings. It is
canonical JSON and its bytes are addressed by the manifest.

### `gate.json`

This document contains the gate summary and all ten checks. It is canonical
JSON and its bytes are addressed by the manifest.

### `manifest.json`

The manifest records:

1. assurance version and boundary;
2. ledger ID and ledger address;
3. assurance and gate addresses;
4. exact file list;
5. artifact count;
6. bytes for each data document;
7. a hash address for each data document's bytes;
8. a file receipt derived from the name and byte address; and
9. a manifest address.

The manifest is written last into an atomic temporary directory. On reload,
the loader verifies canonical bytes, exact membership, every byte receipt,
manifest address, nested addresses, and cross-document linkage.

## Assurance diff package

An assurance diff compares two already verified assurance gates. It does not
re-read arbitrary directories or infer missing fields.

The exact diff package is:

```text
manifest.json
diff.json
```

Each finding and check is joined by a stable key:

```text
assurance:<plane>:<kind>
gate:<plane>:<kind>
```

The diff classifies each key as:

| Action | Meaning |
| --- | --- |
| `added` | only the candidate contains the record |
| `removed` | only the baseline contains the record |
| `unchanged` | semantic result fields match |
| `changed` | severity, requiredness, or pass result changed |

Outcome direction is computed independently from the action:

| Baseline score | Candidate score | Direction |
| ---: | ---: | --- |
| absent | pass | improved |
| absent | warning/blocker | regressed |
| blocker | absent | improved |
| pass/warning | absent | regressed |
| lower score | higher score | improved |
| higher score | lower score | regressed |
| equal score | equal score | none |

The aggregate diff state is `unchanged`, `improved`, `regressed`, or
`changed`. Removed/added records are retained rather than discarded so a
reviewer can see contract coverage changes.

## Query surfaces

### Assurance queries

The assurance query resources are:

| Resource | Returned records |
| --- | --- |
| `summary` | one assurance summary with gate state fields |
| `findings` | all fourteen finding records |
| `blockers` | failed required findings |
| `warnings` | failed optional findings |
| `checks` | all ten gate checks |
| `failed` | failed findings of either severity |

Filters are `severity`, `passed`, `required`, `plane`, and case-insensitive
text search. `offset` and `limit` are bounded, and the result carries its own
content address.

### Diff queries

The diff query resources are:

`summary`, `actions`, `added`, `removed`, `changed`, `unchanged`, `improved`,
and `regressed`.

Filters are `action`, `plane`, and case-insensitive text search. Diff results
also retain baseline and candidate addresses for every matched record.

### Output formats

The module provides deterministic:

1. canonical JSON;
2. CSV with fixed field ordering for assurance and gate records; and
3. Markdown with sorted summary keys and stable table fields.

## CLI surface

The command base is:

```text
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry-federation-gate-review-decision-ledger-assurance
```

Build an assurance gate from a persisted current-format ledger:

```text
python -m glio_noncode <command> --input <ledger-directory> --destination <assurance-directory> --format summary
```

The build command returns:

| Status | Meaning |
| ---: | --- |
| 0 | gate promoted |
| 2 | gate held or blocked |
| nonzero other | invalid input or command failure |

Verify a persisted assurance gate:

```text
python -m glio_noncode <command>-verify --input <assurance-directory>
```

Query findings:

```text
python -m glio_noncode <command>-query --input <assurance-directory> --resource findings --format markdown
```

Build a diff:

```text
python -m glio_noncode <command>-diff --baseline <baseline-directory> --candidate <candidate-directory> --destination <diff-directory> --format summary
```

Query changed records:

```text
python -m glio_noncode <command>-diff-query --input <diff-directory> --resource changed
```

The command family also exposes bundle, assurance, finding, gate, check,
query, diff, diff-item, diff-query, and capabilities schemas.

## HTTP surface

The HTTP base is the current review decision-ledger route followed by
`/assurance`:

```text
/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance
```

The route supports:

| Suffix | Operation |
| --- | --- |
| `/` | build from a persisted ledger directory |
| `/verify` | verify a persisted assurance package |
| `/query` | query an assurance package |
| `/schema` | bundle schema |
| `/assurance-schema` | assurance schema |
| `/finding-schema` | finding schema |
| `/gate-schema` | gate schema |
| `/check-schema` | check schema |
| `/query-schema` | query schema |
| `/capabilities` | capability projection |
| `/diff` | compare two persisted assurance packages |
| `/diff/verify` | verify a diff package |
| `/diff/query` | query a diff package |
| `/diff/schema` | diff schema |
| `/diff/item-schema` | diff item schema |
| `/diff/query-schema` | diff query schema |

The base build and `/verify` route return HTTP 200 for promotion and HTTP
422 for a held or blocked release result. Structural input errors return a
client error rather than a false success.

## Tamper and failure matrix

| Mutation | Detection | Result |
| --- | --- | --- |
| ledger summary field changed | `ledger-address` | required failure; gate block |
| ledger version changed | `ledger-contract` | required failure; gate block |
| queue address changed | `queue-linkage` | required failure; gate block |
| item content address changed | `item-addresses` | required failure; gate block |
| entry address changed | `entry-chain` | required failure; gate block |
| entry points to another item | `entry-item-linkage` | required failure; gate block |
| action counter changed | `action-counters` | required failure; gate block |
| remediation evidence removed | `evidence-policy` | required failure; gate block |
| illegal transition inserted | `transition-policy` | required failure; gate block |
| replay state/count changed | `replay-projection` | required failure; gate block |
| source acceptance changed | `source-authority` | required failure; gate block |
| source readiness/closure changed | `closure-readiness` | optional failure; gate hold |
| forbidden serialized key added | `public-boundary` | required failure; gate block |
| replay address changed | `replay-addresses` | required failure; gate block |
| missing package document | loader file-set check | load rejected |
| extra package document | loader file-set check | load rejected |
| non-canonical JSON | canonical-byte check | load rejected |
| changed artifact bytes | manifest byte receipt | load rejected |
| changed manifest linkage | manifest address/link check | load rejected |
| destination already populated | atomic-write guard | write rejected unless overwrite |
| directory symlink | input safety check | load rejected |

## Real downloaded-data compatibility

The preserved downloaded replay artifact from the earlier product boundary is
useful for demonstrating strict compatibility behavior. It contains an older
observatory packet registry/federation/gate shape. It was successfully replayed
by the older reader as a `promote` result with all recorded findings and checks
passing.

It is not a current review decision ledger. The current assurance loader does
not reinterpret it. It rejects the package because its exact file set and
field contract do not match the current ledger boundary. This is intentional:

1. no old repository is used as a framework;
2. no old artifact is silently upgraded;
3. downloaded evidence remains permitted as input data; and
4. format migrations remain explicit future work.

For a current-format downloaded ledger, the demonstration path is:

1. load the exact four-file ledger package;
2. independently build fourteen findings and ten checks;
3. write the exact three-file assurance package;
4. reload and verify all byte receipts;
5. query the findings and checks; and
6. compare the package with a second snapshot through the exact two-file diff.

The test fixture models this downloaded-data path using current persisted
directories and covers ready, held, blocked, handled, and tampered states.

## Public-surface registration

The public surface audit includes the following additions:

1. assurance bundle schema;
2. assurance report schema;
3. finding schema;
4. gate schema;
5. check schema;
6. query schema;
7. diff schema;
8. diff item schema;
9. diff query schema; and
10. capability projection.

The closed inventory count increases from 513 to 523. The audit rejects
forbidden nested keys and path-like values in every registered projection.

## Verification commands

Run the focused assurance suite:

```text
python -m unittest tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance -v
```

Run the public surface audit:

```text
python -m unittest tests.test_public_surface_audit -v
```

Run static checks on the new boundary:

```text
ruff check src/glio_noncode/assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance.py
python -m py_compile src/glio_noncode/assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance.py
```

The GitHub Actions workflow runs both the focused suite and the capability
contract command. This keeps assurance behavior visible in the same public
CI path as the source review-ledger contracts.

## Operational checklist

Before accepting a package for downstream review:

1. verify that the input is a current-format four-file ledger;
2. record the ledger address and source queue address;
3. build the independent assurance gate;
4. inspect all required failures first;
5. inspect optional warnings separately from source readiness;
6. verify that the gate state is interpreted as promote, hold, or block;
7. persist the exact three-file package;
8. reload the package from a separate process when possible;
9. query blockers, warnings, and failed findings for reviewer handoff;
10. compare baseline and candidate assurance packages when changing a build;
11. retain the diff package with the release review; and
12. do not describe operator remediation as a source-gate change.

## Limitations

This boundary does not:

1. determine whether scientific evidence is valid;
2. inspect the semantic truth of an evidence address;
3. authorize external release actions;
4. merge old artifact formats;
5. store local paths or credentials;
6. replace source queue verification;
7. infer missing files; or
8. make a held source promotable merely because review items were handled.

Those limitations are part of the contract. They keep operational assurance
separate from source evidence and keep the public repository reproducible when
no private dataset is installed.

## Implementation map

| Area | Implementation |
| --- | --- |
| independent model | `DecisionLedgerAssurance`, `DecisionLedgerAssuranceFinding` |
| independent gate | `DecisionLedgerReleaseGate`, `DecisionLedgerGateCheck` |
| combined handoff | `DecisionLedgerAssuranceGate` |
| assurance construction | `build_assurance`, `build_assurance_gate` |
| address verification | `verify_assurance`, `verify_gate`, `verify_assurance_gate` |
| persistence | `write_assurance_gate`, `load_assurance_gate` |
| diff construction | `build_diff`, `write_diff`, `load_diff` |
| queries | `query_assurance`, `query_diff` |
| JSON/CSV/Markdown | `*_json`, `*_csv`, `render_*_markdown` functions |
| schemas | `assurance_schema`, `finding_schema`, `gate_schema`, `check_schema`, `query_schema`, `diff_schema`, `diff_item_schema`, `diff_query_schema` |
| CLI | long-form assurance and diff command families |
| HTTP | current review decision-ledger assurance route family |
| CI | focused tests and capability contract |
| public inventory | ten closed schema/capability entries |

## Acceptance statement

This module is accepted when code, tests, docs, public-surface inventory, and
Actions coverage agree on the same current-format contract. A successful
assurance build means that the ledger snapshot is structurally and
operationally consistent according to these checks. It does not mean that the
source federation gate has changed, that scientific evidence has been judged,
or that a release has been externally published.
