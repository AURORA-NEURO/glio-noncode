# Decision-Ledger Assurance Runbook

This runbook is for the operator who receives a persisted release-registry
federation review decision ledger and needs a reproducible answer about its
integrity and promotion state.

The runbook assumes that the input directory was obtained as data. It does not
assume a source repository, a local framework, or an installed private data
bundle. Every command can be run against an exact persisted package.

## Fast path

1. Identify the current-format ledger directory.
2. Run the assurance command with a new destination.
3. Read the structured result.
4. Inspect required failures.
5. Inspect optional holds.
6. Verify the written package.
7. Query the package for reviewer handoff.
8. Compare it with a baseline when the build changed.

The fast path preserves a held or blocked result as a structured artifact. A
nonzero process status is not a reason to delete the result.

## Input acceptance

| Question | Expected answer |
| --- | --- |
| Is the input a directory? | yes |
| Is the directory itself not a symlink? | yes |
| Are all children regular non-symlink files? | yes |
| Are the children exactly four files? | yes |
| Are the files canonical UTF-8 JSON? | yes |
| Does the ledger version match the current review boundary? | yes |
| Does the manifest address match its canonical body? | yes |
| Do all byte receipts match? | yes |
| Do ledger, queue, gate, assurance, and replay links agree? | yes |

If any answer is no, stop at input verification. Do not copy fields into a
new ledger by hand. Do not rename an older artifact and call it current.

## Output acceptance

| Question | Expected answer |
| --- | --- |
| Is the assurance package exactly three files? | yes |
| Is the diff package exactly two files? | when a diff is requested |
| Are assurance and gate addresses stable on reload? | yes |
| Are all finding addresses reproducible? | yes |
| Are all check addresses reproducible? | yes |
| Is the public projection free of forbidden keys? | yes |
| Does the gate state match the failed-check policy? | yes |
| Does the gate preserve source readiness? | yes |

## Command recipes

Set the command once in a shell to make the recipes readable:

```text
ASSURANCE_COMMAND=module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry-federation-gate-review-decision-ledger-assurance
```

The Windows PowerShell equivalent is:

```text
$ASSURANCE_COMMAND = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry-federation-gate-review-decision-ledger-assurance"
```

Build a JSON result:

```text
python -m glio_noncode $ASSURANCE_COMMAND --input LEDGER --destination ASSURANCE --format json
```

Build a human-readable result:

```text
python -m glio_noncode $ASSURANCE_COMMAND --input LEDGER --destination ASSURANCE --format markdown
```

Verify the durable package:

```text
python -m glio_noncode $ASSURANCE_COMMAND-verify --input ASSURANCE
```

Query every finding:

```text
python -m glio_noncode $ASSURANCE_COMMAND-query --input ASSURANCE --resource findings --limit 50
```

Query only required findings:

```text
python -m glio_noncode $ASSURANCE_COMMAND-query --input ASSURANCE --resource findings --required --limit 50
```

Query blockers:

```text
python -m glio_noncode $ASSURANCE_COMMAND-query --input ASSURANCE --resource blockers --limit 50
```

Query gate checks:

```text
python -m glio_noncode $ASSURANCE_COMMAND-query --input ASSURANCE --resource checks --limit 50
```

Query replay findings:

```text
python -m glio_noncode $ASSURANCE_COMMAND-query --input ASSURANCE --resource findings --plane replay --limit 50
```

Query public-boundary findings:

```text
python -m glio_noncode $ASSURANCE_COMMAND-query --input ASSURANCE --resource findings --text public --limit 50
```

Build a baseline/candidate diff:

```text
python -m glio_noncode $ASSURANCE_COMMAND-diff --baseline BASELINE --candidate ASSURANCE --destination DIFF --format summary
```

Query changed diff records:

```text
python -m glio_noncode $ASSURANCE_COMMAND-diff-query --input DIFF --resource changed --limit 50
```

The command names are deliberately long because the path is a public module
identity. Use shell variables or a checked-in wrapper when invoking it often.

## Reading a result

Start with these fields:

| Field | Interpretation |
| --- | --- |
| `ledger_address` | exact input ledger identity |
| `assurance_address` | independent finding report identity |
| `gate_address` | independent gate identity |
| `assurance_state` | `passed`, `warning`, or `blocked` |
| `gate_state` | `promote`, `hold`, or `block` |
| `accepted` | required failures are absent |
| `release_ready` | all required and optional gate checks pass |
| `source_accepted` | source gate accepted the input |
| `source_release_ready` | source gate allowed release |
| `blocker_finding_count` | required assurance failures |
| `warning_check_count` | optional gate failures |

The most important non-equivalence is:

```text
accepted != release_ready
```

An accepted result may be held. A structurally valid held source is useful
review evidence but is not a promotable release.

## Handling a promote

When the gate is `promote`:

1. retain the input ledger package;
2. retain the assurance package;
3. record all three addresses in the review handoff;
4. verify the package from a separate process if practical;
5. compare against a baseline for changes; and
6. let the downstream release process decide whether to publish.

`promote` means this boundary found no failed required or optional check. It
does not authorize publication by itself.

## Handling a hold

When the gate is `hold`:

1. retain the assurance package;
2. query `warnings` and failed checks;
3. identify whether the hold is source readiness, active review, or escalation;
4. decide whether an operator action is appropriate;
5. attach evidence only to remediation or waiver actions; and
6. do not rewrite source readiness locally.

Common hold causes:

| Failed check | Meaning |
| --- | --- |
| `source-release-ready` | source gate remains held |
| `ledger-clear` | replay still has an active state |
| `no-open-items` | review work is incomplete |
| `no-escalated-items` | a routed issue remains escalated |

The source gate and queue must be rebuilt from new evidence before source
readiness changes.

## Handling a block

When the gate is `block`:

1. do not treat the package as promotable;
2. query `blockers` and `failed`;
3. record the exact finding/check addresses;
4. inspect the ledger, replay, and manifest independently;
5. repair the source data or reject the ledger; and
6. rerun from a new clean snapshot.

Common blocker causes:

| Failed finding/check | First inspection |
| --- | --- |
| `ledger-address` | summary and content-address construction |
| `ledger-contract` | version, boundary, entry count |
| `queue-linkage` | queue, gate, assurance, replay addresses |
| `item-addresses` | frozen item snapshot |
| `entry-chain` | predecessor and terminal head |
| `entry-item-linkage` | decision item ID/address |
| `action-counters` | action counts versus entries |
| `evidence-policy` | remediation/waiver evidence address |
| `transition-policy` | action order and prior state |
| `replay-projection` | state counts and readiness |
| `source-authority` | source acceptance/readiness |
| `public-boundary` | nested serialized keys |
| `replay-addresses` | replay item and replay snapshot hashes |
| `assurance-accepted` | required assurance findings |
| `head-continuity` | ledger terminal head |

## Finding investigation sequence

Use this order because it moves from identity to policy:

1. ledger identity;
2. source linkage;
3. frozen item addresses;
4. entry ancestry;
5. item targeting;
6. action counts;
7. evidence shape;
8. transition legality;
9. replay state;
10. source authority;
11. readiness;
12. public projection; and
13. replay receipts.

Do not start with a human summary if the ledger identity is already invalid.
The summary may be stale or forged; the addressed finding explains which
identity boundary failed.

## Entry-chain investigation

For each decision entry, confirm:

1. ordinal begins at zero;
2. ordinal increments by one;
3. decision ID is unique;
4. item ID is present in the frozen queue;
5. item address is the frozen item address;
6. action is in the fixed action vocabulary;
7. rationale is bounded and non-empty;
8. evidence follows action policy;
9. previous address is the initial head for the first entry;
10. previous address is the prior entry address afterward; and
11. content address recomputes from the public entry projection.

The terminal ledger head must equal the final entry address. An empty ledger
must use `none:review-head`.

## Replay investigation

Replay is derived in this order:

1. copy each frozen item identity and initial state;
2. resolve each entry to one item ID;
3. verify the item address;
4. apply the independent action transition;
5. record last action and last decision address;
6. count every replay state;
7. derive queue state;
8. preserve source acceptance;
9. preserve source release readiness; and
10. derive release readiness from source readiness and clear state.

If the stored replay differs at any step, the `replay-projection` finding
fails. If replay addresses differ while states match, `replay-addresses`
fails. Both are required checks.

## Evidence investigation

The evidence rule is narrow and mechanical:

| Action | Expected evidence |
| --- | --- |
| acknowledge | `none:review-evidence` |
| remediate | any valid non-no-evidence address |
| waive | any valid non-no-evidence address |
| escalate | `none:review-evidence` |
| reopen | `none:review-evidence` |

Evidence addresses are not scientific claims. They are links to separately
managed evidence records. Do not put a filesystem path into an evidence
address.

## Public-boundary investigation

The public projection must not contain keys or nested values that expose:

1. agent;
2. assistant;
3. author;
4. email;
5. generated-by metadata;
6. language;
7. model;
8. private metadata;
9. secret;
10. token; or
11. user identity.

The assurance module applies this check recursively. A public-safe top-level
summary does not excuse a forbidden nested key in an entry or replay item.

Local paths are also excluded from the data projection. Paths may be supplied
to a loader or CLI, but they are not emitted in the addressed report.

## Persistence investigation

For an assurance package:

1. list children and compare with `manifest.json`, `assurance.json`, and
   `gate.json`;
2. parse every document as UTF-8 JSON;
3. compare raw bytes with canonical bytes;
4. compare byte lengths with manifest values;
5. compare byte hashes with manifest values;
6. compare file receipt addresses;
7. recompute manifest address;
8. load nested assurance and gate projections;
9. verify nested content addresses; and
10. verify cross-document ledger and assurance linkage.

For a diff package, repeat the same sequence for `manifest.json` and
`diff.json`.

## Diff investigation

Diffs answer what changed between two assurance gates. They do not silently
drop records that exist on one side only.

Inspect in this order:

1. baseline and candidate bundle addresses;
2. baseline and candidate ledger addresses;
3. baseline and candidate assurance states;
4. added records;
5. removed records;
6. changed records;
7. improved records; and
8. regressed records.

An unchanged semantic record may still have different package addresses when
its enclosing snapshot identity changed. The diff retains both record
addresses so that distinction is visible.

## Downloaded-data procedure

When the ledger came from a download:

1. preserve the original downloaded directory;
2. do not clone an old code repository;
3. do not use a similarly named repository as a framework;
4. verify exact file membership;
5. run the current-format loader;
6. record any explicit compatibility rejection;
7. build assurance into a new sibling directory;
8. avoid printing the local path into the public result;
9. verify the new package; and
10. retain the source and output addresses.

An older observatory artifact is not a current ledger. A rejection with an
explicit shape/version error is the correct result. Silent field conversion
would hide uncertainty and make the address meaningless.

## CI procedure

The focused suite should be run before a commit:

```text
python -m unittest tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance -v
```

Then run the public surface audit:

```text
python -m unittest tests.test_public_surface_audit -v
```

Then run static checks:

```text
ruff check src/glio_noncode/assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance.py
ruff check tests/test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance.py
python -m py_compile src/glio_noncode/assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance.py
```

Actions repeats the focused suite and the capability command. A local pass is
not a substitute for the public CI pass because the workflow also checks the
command registration path.

## Review handoff template

Use this field order in a handoff:

```text
ledger_address: <address>
queue_address: <address>
assurance_address: <address>
gate_address: <address>
bundle_address: <address>
assurance_state: <state>
gate_state: <state>
accepted: <true|false>
release_ready: <true|false>
source_accepted: <true|false>
source_release_ready: <true|false>
finding_count: <integer>
blocker_finding_count: <integer>
warning_finding_count: <integer>
check_count: <integer>
blocker_check_count: <integer>
warning_check_count: <integer>
```

Attach the exact package files separately. Never replace an address with a
filesystem path in the handoff.

## Stop conditions

Stop and request a new source snapshot when:

1. source acceptance is false;
2. source readiness is false and the desired outcome is promotion;
3. a required assurance finding fails;
4. an evidence address is missing for remediation or waiver;
5. a decision targets a different frozen item;
6. the entry chain is discontinuous;
7. replay cannot be reproduced;
8. the public projection contains forbidden metadata;
9. a package manifest or byte receipt fails; or
10. the artifact is an unsupported older format.

Do not “fix” these by editing the output package. Re-run the producing
boundary from valid input.

## Completion checklist

| Step | Done |
| --- | :---: |
| current-format ledger loaded | [ ] |
| source package preserved | [ ] |
| assurance findings inspected | [ ] |
| required failures reviewed | [ ] |
| optional holds reviewed | [ ] |
| source authority checked | [ ] |
| exact assurance package written | [ ] |
| package reloaded and verified | [ ] |
| findings queried | [ ] |
| checks queried | [ ] |
| baseline/candidate diff built if needed | [ ] |
| public-boundary result recorded | [ ] |
| downstream release decision kept separate | [ ] |

The runbook is complete when each checked box maps to an addressable record,
a deterministic command result, or a retained exact package.
