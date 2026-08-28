# Assurance-history test catalog

This catalog maps the longitudinal assurance-history contract to focused
regression tests. The tests are intentionally deterministic and run without a
network connection. The catalog is a review aid; the executable test module is
the authority for exact assertions.

## 1. Test principles

Every positive test starts with typed current-format assurance gates.

Every persistence test reloads from bytes.

Every address test recomputes the expected address.

Every mapping test checks both round-trip and strict rejection.

Every collection test exercises a bounded result.

Every failure test asserts a typed validation error.

Every public-boundary test traverses nested values.

Every CLI test exercises the real parser and dispatcher.

Every older artifact test proves rejection rather than conversion.

The suite does not require an external dataset.

The downloaded-data demo is run separately against authorized current-format
persisted outputs.

## 2. Test fixture contract

| Fixture | Purpose |
| --- | --- |
| ready gate | Promotable terminal state and positive baseline. |
| held gate | Accepted but non-promotable state. |
| blocked gate | Non-accepted blocking state. |
| repeated ready gates | Stable transition. |
| held-to-ready pair | Improved transition. |
| ready-to-blocked pair | Regressed transition. |
| same-ID changed pair | Changed transition and diff item. |
| empty sequence | Explicit empty history. |
| current persisted gate directory | Exact loader and reload behavior. |
| old downloaded directory | Compatibility rejection. |

The fixture builder uses the existing decision-ledger review fixture and then
builds independent assurance gates. It does not fabricate a history mapping.

## 3. Construction coverage

| ID | Test intent | Expected proof |
| --- | --- | --- |
| H-001 | Empty history builds | Empty state, no latest snapshot, zero counters. |
| H-002 | Populated history builds | Entries and terminal projection are present. |
| H-003 | Default history ID | Stable default identity is applied. |
| H-004 | Custom history ID | Identity changes while gate projections remain stable. |
| H-005 | Default snapshot IDs | Repeated build produces identical entry IDs. |
| H-006 | Explicit snapshot IDs | Caller identities are retained in order. |
| H-007 | Mismatched ID count | Build rejects partial alignment. |
| H-008 | Duplicate snapshot IDs | Build rejects ambiguous joins. |
| H-009 | Entry ordinal sequence | Ordinals are zero-based and contiguous. |
| H-010 | Entry previous address | First entry uses initial head. |
| H-011 | Entry chain | Each later entry references the prior address. |
| H-012 | Terminal head | Head equals last entry address. |
| H-013 | History address | Address is recomputable from public projection. |
| H-014 | Public projection | No forbidden metadata appears recursively. |
| H-015 | Repeated build | Same inputs produce same complete mapping. |

## 4. Append coverage

| ID | Test intent | Expected proof |
| --- | --- | --- |
| A-001 | Append to empty | First append creates initial transition. |
| A-002 | Append ready after ready | Stable transition is assigned. |
| A-003 | Append ready after held | Improved transition is assigned. |
| A-004 | Append blocked after ready | Regressed transition is assigned. |
| A-005 | Append changed quality | Changed transition is assigned when incomparable. |
| A-006 | Append expected history address | Optimistic guard accepts current object. |
| A-007 | Append stale history address | Optimistic guard rejects stale writer. |
| A-008 | Append duplicate snapshot | Duplicate identity is rejected. |
| A-009 | Append preserves source links | Ledger, assurance, gate, and bundle links survive. |
| A-010 | Append immutability | Original history value is unchanged. |
| A-011 | Append counter conservation | State and transition totals remain valid. |
| A-012 | Append terminal projection | Latest fields match the new entry. |

## 5. Transition matrix

| Previous state | Current state | Quality movement | Expected transition |
| --- | --- | --- | --- |
| none | ready | not applicable | initial |
| none | held | not applicable | initial |
| none | blocked | not applicable | initial |
| ready | ready | equal | stable |
| held | held | equal | stable |
| blocked | blocked | equal | stable |
| held | ready | upward | improved |
| blocked | held | upward | improved |
| blocked | ready | upward | improved |
| ready | held | downward | regressed |
| held | blocked | downward | regressed |
| ready | blocked | downward | regressed |
| ready | ready | text or non-quality change | changed |
| held | ready | competing dimensions | changed |
| blocked | held | competing dimensions | changed |

The matrix is interpreted through the complete public quality vector, not by
state name alone. Tests that need a changed classification use a pair whose
quality dimensions move in competing directions.

## 6. Verification coverage

| ID | Test intent | Expected proof |
| --- | --- | --- |
| V-001 | Typed history verifier | Valid value is returned unchanged. |
| V-002 | Wrong verifier type | Non-history input is rejected. |
| V-003 | Cross-snapshot sequence | Entry gate links are replayed and checked. |
| V-004 | Wrong ordinal | Contiguous ordinal invariant fails. |
| V-005 | Wrong previous address | Chain invariant fails. |
| V-006 | Wrong entry address | Content address invariant fails. |
| V-007 | Wrong head | Terminal head invariant fails. |
| V-008 | Wrong state counter | State conservation fails. |
| V-009 | Wrong transition counter | Transition conservation fails. |
| V-010 | Wrong latest snapshot | Terminal summary fails. |
| V-011 | Wrong release readiness | Terminal summary fails. |
| V-012 | Wrong history address | Address recomputation fails. |
| V-013 | Recompute against gates | Independent gate sequence is checked. |
| V-014 | Wrong gate sequence | Independent replay rejects projection drift. |

## 7. Mapping coverage

| ID | Test intent | Expected proof |
| --- | --- | --- |
| M-001 | Entry round trip | `entry_from_mapping(entry.to_dict())` is stable. |
| M-002 | History round trip | Nested entry mappings rehydrate exactly. |
| M-003 | Diff item round trip | Both nullable sides preserve. |
| M-004 | Diff round trip | Baseline and candidate links preserve. |
| M-005 | Unknown entry key | Strict field rejection. |
| M-006 | Unknown history key | Strict field rejection. |
| M-007 | Unknown diff key | Strict field rejection. |
| M-008 | Missing required field | Required field rejection. |
| M-009 | Invalid gate state | Enum rejection. |
| M-010 | Invalid assurance state | Enum rejection. |
| M-011 | Invalid transition | Enum rejection. |
| M-012 | Invalid boolean | Type rejection. |
| M-013 | Invalid count | Bound and type rejection. |
| M-014 | Oversized text | Bounded string rejection. |
| M-015 | Nested forbidden key | Public projection rejection. |

## 8. Counter coverage

| ID | Check |
| --- | --- |
| C-001 | Transition totals equal entry count. |
| C-002 | Promote, hold, and block totals equal entry count. |
| C-003 | Empty history has zero transition totals. |
| C-004 | Empty history has zero state totals. |
| C-005 | One entry has one initial transition. |
| C-006 | Stable append increments stable only. |
| C-007 | Improvement append increments improved only. |
| C-008 | Regression append increments regressed only. |
| C-009 | Changed append increments changed only. |
| C-010 | Diff action totals equal item count. |
| C-011 | Diff direction totals do not exceed item count. |
| C-012 | Mixed direction is present only with both movements. |

## 9. Diff coverage

| ID | Test intent | Expected proof |
| --- | --- | --- |
| D-001 | Same histories | Unchanged items and state. |
| D-002 | Added snapshot | Added action and improved direction. |
| D-003 | Removed snapshot | Removed action and regressed direction. |
| D-004 | Same ID same entry | Unchanged action. |
| D-005 | Same ID changed gate | Changed action. |
| D-006 | Held to ready | Improved direction. |
| D-007 | Ready to held | Regressed direction. |
| D-008 | Ready to blocked | Regressed direction. |
| D-009 | Mixed movements | Mixed aggregate state. |
| D-010 | Baseline address | Retained in diff summary and items. |
| D-011 | Candidate address | Retained in diff summary and items. |
| D-012 | Item address | Recomputable independently. |
| D-013 | Diff address | Recomputable from full projection. |
| D-014 | Diff typed verifier | Valid diff is returned unchanged. |
| D-015 | Diff history verifier | Items are recomputed against both histories. |

## 10. Diff action matrix

| Baseline snapshot | Candidate snapshot | Action | Direction |
| --- | --- | --- | --- |
| absent | present ready | added | improved |
| absent | present held | added | improved |
| absent | present blocked | added | improved |
| present ready | absent | removed | regressed |
| present held | absent | removed | regressed |
| present blocked | absent | removed | regressed |
| equal entry | equal entry | unchanged | unchanged |
| held entry | ready entry | changed | improved |
| ready entry | held entry | changed | regressed |
| ready entry | blocked entry | changed | regressed |

The addition/removal direction convention is intentionally conservative for
review: new evidence is an improvement relative to no evidence, while removed
evidence is a regression relative to its baseline.

## 11. Query coverage

| ID | Test intent | Expected proof |
| --- | --- | --- |
| Q-001 | Summary resource | One addressed summary result. |
| Q-002 | Entries resource | Ordered entry records. |
| Q-003 | Initial resource | Initial entries only. |
| Q-004 | Stable resource | Stable entries only. |
| Q-005 | Improved resource | Improved entries only. |
| Q-006 | Regressed resource | Regressed entries only. |
| Q-007 | Changed resource | Changed entries only. |
| Q-008 | Gate-state filter | Exact gate-state match. |
| Q-009 | Assurance-state filter | Exact assurance-state match. |
| Q-010 | Accepted filter | Exact boolean match. |
| Q-011 | Release-ready filter | Exact boolean match. |
| Q-012 | Text filter | Bounded public text search. |
| Q-013 | Offset | Non-negative page start. |
| Q-014 | Limit | Positive bounded page size. |
| Q-015 | Offset past end | Empty page with valid result. |
| Q-016 | Bad resource | Resource rejection. |
| Q-017 | Bad window | Window rejection. |
| Q-018 | Query object and kwargs | Mutual-exclusion rejection. |
| Q-019 | Query address | Address changes with window. |
| Q-020 | Query serialization | JSON, CSV, and Markdown stable. |

## 12. Diff query coverage

| ID | Test intent | Expected proof |
| --- | --- | --- |
| QD-001 | Summary resource | One addressed diff summary. |
| QD-002 | Items resource | Ordered item records. |
| QD-003 | Added filter | `items` plus `action=added`. |
| QD-004 | Removed filter | `items` plus `action=removed`. |
| QD-005 | Unchanged filter | `items` plus `action=unchanged`. |
| QD-006 | Changed resource | `changes` returns changed-action items. |
| QD-007 | Improved filter | `items` plus `direction=improved`. |
| QD-008 | Regressed filter | `items` plus `direction=regressed`. |
| QD-009 | Gate-state filter | Candidate gate state match. |
| QD-010 | Text filter | Bounded item text search. |
| QD-011 | Pagination | Offset and limit are enforced. |
| QD-012 | Bad action | Enum rejection. |
| QD-013 | Bad direction | Enum rejection. |
| QD-014 | Bad window | Window rejection. |
| QD-015 | Query serialization | JSON, CSV, and Markdown stable. |

## 13. Persistence coverage

| ID | Test intent | Expected proof |
| --- | --- | --- |
| P-001 | History exact files | Exactly manifest, history, entries. |
| P-002 | History reload | Loaded mapping equals original. |
| P-003 | History manifest | Version and boundary are linked. |
| P-004 | History artifact bytes | Byte count and address match. |
| P-005 | History canonical JSON | Noncanonical bytes fail. |
| P-006 | History manifest tamper | Receipt drift fails. |
| P-007 | History extra file | Package shape fails. |
| P-008 | History symlink | Regular-file contract fails. |
| P-009 | History overwrite | Existing destination requires flag. |
| P-010 | Diff exact files | Exactly manifest and diff. |
| P-011 | Diff reload | Loaded mapping equals original. |
| P-012 | Diff extra file | Package shape fails. |
| P-013 | Diff canonical JSON | Noncanonical bytes fail. |
| P-014 | Diff manifest tamper | Receipt drift fails. |
| P-015 | Diff overwrite | Existing destination requires flag. |

## 14. Byte tamper matrix

| Mutation | Expected failure boundary |
| --- | --- |
| Add whitespace to history JSON | Canonical-byte check. |
| Reorder keys in entries JSON | Canonical-byte check. |
| Change a byte in entries JSON | Byte address check. |
| Change history artifact byte count | Manifest receipt check. |
| Change history artifact byte address | Manifest receipt check. |
| Change history content address | Typed verifier check. |
| Change terminal state | Terminal projection check. |
| Change previous entry address | Chain check. |
| Add an unknown entry field | Strict mapping check. |
| Add an extra package file | Exact-file check. |
| Replace artifact with symlink | Regular-file check. |

## 15. Compatibility coverage

| ID | Legacy input | Expected result |
| --- | --- | --- |
| K-001 | Older downloaded registry directory | Not a history. |
| K-002 | Older review history manifest | Rejected. |
| K-003 | Older observatory history | Rejected. |
| K-004 | Assurance gate with wrong manifest fields | Rejected by assurance loader. |
| K-005 | History with `observations` instead of `entries` | Rejected. |
| K-006 | History with extra artifact | Rejected. |
| K-007 | History with missing manifest | Rejected. |
| K-008 | History with unsupported version | Rejected. |

No compatibility test permits “best effort” conversion.

## 16. CLI coverage

| ID | Command surface | Expected proof |
| --- | --- | --- |
| CLI-001 | History build | Parses repeatable gates and writes package. |
| CLI-002 | History verify | Loads and verifies package. |
| CLI-003 | History query | Emits bounded entries. |
| CLI-004 | History schema | Emits closed schema. |
| CLI-005 | History entry schema | Emits entry schema. |
| CLI-006 | History query schema | Emits query schema. |
| CLI-007 | History capabilities | Emits capabilities. |
| CLI-008 | History diff | Writes diff package. |
| CLI-009 | History diff verify | Loads and verifies diff. |
| CLI-010 | History diff query | Filters diff items. |
| CLI-011 | Diff schema | Emits closed diff schema. |
| CLI-012 | Diff item schema | Emits item schema. |
| CLI-013 | Diff query schema | Emits query schema. |
| CLI-014 | Diff capabilities | Emits capabilities. |
| CLI-015 | Held return code | Valid held result returns two. |
| CLI-016 | Invalid input return code | Structural failure returns one. |

The parser registration is checked independently of dispatch so an accidental
duplicate or missing command is caught before a build operation runs.

## 17. API coverage

| ID | Route surface | Expected proof |
| --- | --- | --- |
| API-001 | History schema | Closed schema response. |
| API-002 | History entry schema | Entry schema response. |
| API-003 | History diff schema | Diff schema response. |
| API-004 | History diff item schema | Item schema response. |
| API-005 | History query schema | Query schema response. |
| API-006 | History diff query schema | Diff query schema response. |
| API-007 | History capabilities | Capability response. |
| API-008 | History build | Gate directories produce a response. |
| API-009 | History verify | Persisted history verifies. |
| API-010 | History query | Entries are returned. |
| API-011 | History diff | Baseline/candidate comparison works. |
| API-012 | Diff verify | Persisted diff verifies. |
| API-013 | Diff query | Diff item filtering works. |
| API-014 | Held build | Valid hold returns 422. |
| API-015 | Missing input | Client error is structured. |

## 18. Public-surface coverage

| ID | Surface | Expected proof |
| --- | --- | --- |
| PS-001 | Module exports | Typed models are importable. |
| PS-002 | Builder aliases | History and diff builders are public. |
| PS-003 | Verifier aliases | History and diff verifiers are public. |
| PS-004 | Serializer aliases | JSON, CSV, Markdown are public. |
| PS-005 | Schema aliases | Schemas are public. |
| PS-006 | Capability alias | Capabilities are public. |
| PS-007 | CLI inventory | Canonical command names are registered. |
| PS-008 | Recursive boundary | No forbidden fields are exported. |
| PS-009 | Count closure | Inventory expected count matches. |

## 19. Real-data demonstration checks

The local demonstration is intentionally separate from unit tests because its
inputs are persisted outputs from the downloaded-data pipeline.

| Check | Expected result |
| --- | --- |
| Load current decision ledger | Passes the review loader. |
| Recompute assurance gate | Produces a typed independent gate. |
| Verify gate against ledger | No projection drift. |
| Build one-entry history | Initial transition is present. |
| Persist history | Exact three files are written. |
| Reload history | Address and summary are preserved. |
| Emit path-free summary | No local path appears. |
| Load older raw downloaded directory as history | Rejected as incompatible. |

## 20. Test execution

Focused history suite:

```text
python -m unittest tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history -v
```

Upstream assurance and public inventory:

```text
python -m unittest \
  tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance \
  tests.test_public_surface_audit -v
```

Compile check:

```text
python -m py_compile \
  src/glio_noncode/assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history.py \
  src/glio_noncode/api.py \
  src/glio_noncode/cli.py
```

The Actions workflow runs the same contract without external data. The current
focused module contains 55 tests, including three executable demonstration
integration checks.

## 21. Evidence interpretation

Passing a construction test proves a typed value can be built.

Passing a verifier test proves a tampered value is rejected.

Passing a persistence test proves exact bytes can be rehydrated.

Passing a CLI test proves the command surface is wired.

Passing an API test proves the HTTP route is wired.

Passing a public-surface test proves the expected boundary is closed.

Passing a real-data demonstration proves current-format integration with the
authorized persisted input used for that run.

None of these tests claims external scientific validity.

## 22. Coverage gaps kept explicit

The suite does not benchmark very large histories.

The suite does not simulate concurrent filesystem writers beyond the expected
head guard.

The suite does not infer chronology.

The suite does not validate the scientific source of a gate.

The suite does not transform legacy data.

The suite does not publish a private dataset.

These gaps are deliberate boundaries, not hidden assumptions.

## 23. Catalog sign-off

- [x] Construction behavior is cataloged.
- [x] Append behavior is cataloged.
- [x] Transition behavior is cataloged.
- [x] Verification behavior is cataloged.
- [x] Mapping behavior is cataloged.
- [x] Counter behavior is cataloged.
- [x] Diff behavior is cataloged.
- [x] Query behavior is cataloged.
- [x] Persistence behavior is cataloged.
- [x] Compatibility behavior is cataloged.
- [x] CLI behavior is cataloged.
- [x] API behavior is cataloged.
- [x] Public-surface behavior is cataloged.
- [x] Real-data demonstration behavior is cataloged.
- [x] Coverage gaps are explicit.

## 24. Operational invariants

The following invariants are repeated here because they are the fastest review
checks when a package is handed between systems.

| ID | Invariant | Why it matters |
| --- | --- | --- |
| OI-001 | Every entry has one snapshot ID | Diff joins remain deterministic. |
| OI-002 | Every snapshot ID is unique | A reviewer can identify one observation. |
| OI-003 | Every entry has one bundle address | Source evidence remains traceable. |
| OI-004 | Every entry has one prior address | Ancestry can be replayed. |
| OI-005 | The first prior address is fixed | Histories have a common start. |
| OI-006 | The terminal head is explicit | The latest observation is unambiguous. |
| OI-007 | State is terminally derived | Summary cannot hide a later block. |
| OI-008 | Readiness is terminally derived | Promotion follows current evidence. |
| OI-009 | Transition totals conserve | No entry disappears from rollups. |
| OI-010 | State totals conserve | No state disappears from rollups. |
| OI-011 | Entry addresses are content-derived | Renames do not change identity. |
| OI-012 | History address includes order | Reordering cannot be hidden. |
| OI-013 | Diff keeps both addresses | Review can navigate both sides. |
| OI-014 | Diff items have one action | Join interpretation is total. |
| OI-015 | Diff directions are bounded | Review vocabulary stays closed. |
| OI-016 | Query results are bounded | Export cannot grow without limit. |
| OI-017 | Query results are addressed | Filtered evidence is reproducible. |
| OI-018 | Canonical bytes are checked | Formatting edits cannot hide changes. |
| OI-019 | Manifest receipts are checked | Partial writes are detected. |
| OI-020 | Extra files are rejected | Hidden side channels are excluded. |
| OI-021 | Symlinks are rejected | Package contents remain local and explicit. |
| OI-022 | Overwrite is explicit | Prior evidence is not silently replaced. |
| OI-023 | Legacy shapes are rejected | Version boundaries remain meaningful. |
| OI-024 | Paths are not public fields | Reports are portable. |
| OI-025 | Identity fields are not public fields | Reports avoid private metadata. |
| OI-026 | API status maps state | Clients can route holds safely. |
| OI-027 | CLI status maps state | Automation can distinguish hold from error. |
| OI-028 | Schema objects are closed | Unknown fields fail early. |
| OI-029 | Capabilities are fixed | Clients can negotiate deliberately. |
| OI-030 | Real data uses persisted inputs | Demonstrations reflect the pipeline. |

## 25. Maintainer change gates

Any change to entry fields requires a schema review.

Any change to address input requires a determinism test.

Any change to transition ordering requires a matrix update.

Any change to state mapping requires CLI status review.

Any new persisted file requires exact-file contract review.

Any new manifest field requires compatibility review.

Any new public export requires inventory review.

Any new query resource requires boundedness review.

Any new filter requires typed input review.

Any route change requires status and error review.

Any demo input change requires current-format verification.

Any private-looking field requires public-boundary review.

Any writer change requires reload verification.

Any loader change requires tamper coverage.

Any legacy support proposal requires an explicit migration module.

No history field should be added only for convenience.

No verification should depend on a mutable path.

No test should assert only a printed success string.

No held fixture should be erased because it returns status two.

No regression fixture should be hidden by a changed expected value.

## 26. Release review sequence

Run compile checks.

Run focused history tests.

Run upstream assurance tests.

Run public-surface tests.

Run the real-data demo.

Reload the produced history.

Inspect the history summary.

Inspect transition counts.

Inspect terminal state.

Inspect release readiness.

If a baseline exists, build a diff.

Verify the diff.

Query regressed items.

Query changed items.

Preserve addresses.

Review the staged file set.

Review the staged insertion count.

Commit the complete wave.

Push the intended main branch.

Verify the remote head.

Record the commit in the delivery note.

## 27. Catalog conclusion

The catalog is complete when an operator can map each package failure to a
specific test, a specific boundary, and a safe remediation. A large number of
tests is not sufficient if the tests cannot explain why promotion is allowed.
The history contract therefore keeps construction, verification, persistence,
query, public-surface, and real-data checks visible as separate concerns.
