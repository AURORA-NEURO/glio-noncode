# Assurance-history failure matrix

This matrix defines the expected fail-closed behavior of the longitudinal
assurance-history module. A failure is useful only when it identifies the
boundary that was crossed and gives the reviewer a safe next action.

The module distinguishes three outcomes:

1. A valid promotable history.
2. A valid held or blocked history.
3. An invalid or incompatible package.

Only the first outcome is promotable.

## 1. Outcome vocabulary

| Outcome | Meaning | Preserve package | Promotion |
| --- | --- | --- | --- |
| promote | Verified terminal gate is accepted and ready. | Yes | Allowed by this gate. |
| hold | Verified terminal gate is acceptable for review but not ready. | Yes | Not allowed. |
| block | Verified terminal gate is not accepted. | Yes | Not allowed. |
| invalid | Structural or semantic contract failed. | Yes, unchanged | Not allowed. |
| incompatible | Package belongs to another version or module. | Yes, unchanged | Not allowed. |

An invalid package is not an empty history.

An incompatible package is not a blocked gate.

A held gate is not an invalid package.

## 2. Input validation failures

| ID | Condition | Boundary | Safe action |
| --- | --- | --- | --- |
| IN-001 | No ledger input | CLI source selection | Supply at least one ledger. |
| IN-002 | No assurance-gate input | CLI source selection | Supply at least one gate. |
| IN-003 | Ledger and gate modes combined | Demo source mode | Choose one input mode. |
| IN-004 | Input path missing | Directory boundary | Check handoff path. |
| IN-005 | Input path is a file | Directory boundary | Point at package directory. |
| IN-006 | Input path is a symlink | Regular-file boundary | Use a verified regular directory. |
| IN-007 | Duplicate resolved input directory | Identity boundary | Remove duplicate argument. |
| IN-008 | Empty input sequence | Builder boundary | Provide one typed gate. |
| IN-009 | Non-typed gate object | Type boundary | Load or build the current typed gate. |
| IN-010 | Legacy gate mapping | Compatibility boundary | Rebuild with current producer. |
| IN-011 | Unsupported gate version | Version boundary | Use matching current module. |
| IN-012 | Gate contains forbidden public field | Public boundary | Remove from source projection. |
| IN-013 | Gate source not independently assured | Assurance boundary | Recompute assurance first. |
| IN-014 | Ledger loader rejects package | Upstream boundary | Repair upstream handoff. |
| IN-015 | Assurance loader rejects package | Assurance boundary | Repair assurance package. |
| IN-016 | Snapshot ID count differs | Alignment boundary | Pass one ID per gate. |
| IN-017 | Snapshot ID is empty | Identifier boundary | Supply a bounded non-empty ID. |
| IN-018 | Snapshot ID is oversized | Identifier boundary | Use bounded stable identity. |
| IN-019 | Snapshot IDs duplicate | Join boundary | Resolve identity before append. |
| IN-020 | History ID is empty | Identity boundary | Supply a bounded history ID. |
| IN-021 | History ID is oversized | Identity boundary | Use bounded history ID. |
| IN-022 | Destination is a file | Write boundary | Select a directory destination. |
| IN-023 | Baseline is missing | Diff boundary | Supply an existing history. |
| IN-024 | Baseline is not a history | Diff boundary | Use the exact history package. |
| IN-025 | Diff destination is a file | Write boundary | Select a directory destination. |

## 3. Typed entry failures

| ID | Condition | Verification | Safe action |
| --- | --- | --- | --- |
| EN-001 | Entry history ID differs | Identity linkage | Rebuild the entry. |
| EN-002 | Entry version differs | Version linkage | Use the current producer. |
| EN-003 | Entry boundary differs | Public boundary | Reject the package. |
| EN-004 | Entry ordinal is negative | Ordinal bound | Reject the package. |
| EN-005 | Entry ordinal skips a value | Chain order | Rebuild ordered entries. |
| EN-006 | Entry snapshot ID is empty | Identity bound | Reject the package. |
| EN-007 | Entry gate address is malformed | Linkage type | Rebuild from gate. |
| EN-008 | Entry assurance address is malformed | Linkage type | Rebuild from assurance. |
| EN-009 | Entry ledger address is malformed | Linkage type | Rebuild from ledger. |
| EN-010 | Entry bundle address is malformed | Linkage type | Rebuild from bundle. |
| EN-011 | Entry state is unknown | Enum vocabulary | Reject the package. |
| EN-012 | Entry assurance state is unknown | Enum vocabulary | Reject the package. |
| EN-013 | Entry transition is unknown | Enum vocabulary | Reject the package. |
| EN-014 | Entry accepted is not boolean | Typed field | Reject the package. |
| EN-015 | Entry release-ready is not boolean | Typed field | Reject the package. |
| EN-016 | Finding count is negative | Count bound | Reject the package. |
| EN-017 | Check count is negative | Count bound | Reject the package. |
| EN-018 | Passed count exceeds total | Count conservation | Reject the package. |
| EN-019 | Warning count exceeds total | Count conservation | Reject the package. |
| EN-020 | Blocker count exceeds total | Count conservation | Reject the package. |
| EN-021 | Entry content address is pending on disk | Address finality | Reject the package. |
| EN-022 | Entry content address does not recompute | Address integrity | Rebuild the package. |
| EN-023 | Entry has unknown mapping key | Strict mapping | Reject the package. |
| EN-024 | Entry misses required mapping key | Strict mapping | Reject the package. |
| EN-025 | Entry contains private metadata | Public boundary | Reject before publishing. |

## 4. Chain failures

| ID | Condition | Verification | Safe action |
| --- | --- | --- | --- |
| CH-001 | First previous address is not initial head | Start proof | Rebuild first entry. |
| CH-002 | Later previous address skips prior entry | Ancestry proof | Rebuild from ordered gates. |
| CH-003 | Later previous address points forward | Ancestry proof | Reject cyclic chain. |
| CH-004 | Two entries have the same address | Identity proof | Reject ambiguous chain. |
| CH-005 | Ordinals are out of order | Order proof | Rebuild in explicit order. |
| CH-006 | Snapshot IDs repeat | Join proof | Resolve duplicate identity. |
| CH-007 | Head differs from terminal entry | Terminal proof | Rebuild summary. |
| CH-008 | Empty history has non-initial head | Empty proof | Rebuild empty history. |
| CH-009 | Empty history has latest snapshot | Empty proof | Reject inconsistent summary. |
| CH-010 | Empty history has latest gate | Empty proof | Reject inconsistent summary. |
| CH-011 | Empty history is accepted | Empty proof | Empty is not promotable. |
| CH-012 | Empty history is release-ready | Empty proof | Reject inconsistent summary. |
| CH-013 | Entry references missing upstream gate | Source proof | Restore source package. |
| CH-014 | Entry references mismatched gate | Source proof | Recompute from exact gate. |
| CH-015 | Entry chain is altered after signing | Byte proof | Preserve and investigate. |

## 5. History summary failures

| ID | Condition | Verification | Safe action |
| --- | --- | --- | --- |
| HS-001 | Entry count differs from tuple length | Count proof | Rebuild summary. |
| HS-002 | Initial count is wrong | Counter proof | Recompute counters. |
| HS-003 | Stable count is wrong | Counter proof | Recompute counters. |
| HS-004 | Improved count is wrong | Counter proof | Recompute counters. |
| HS-005 | Regressed count is wrong | Counter proof | Recompute counters. |
| HS-006 | Changed count is wrong | Counter proof | Recompute counters. |
| HS-007 | State counts do not conserve | Counter proof | Recompute counters. |
| HS-008 | State does not match terminal gate | Terminal proof | Inspect latest source. |
| HS-009 | Latest snapshot does not match terminal | Terminal proof | Inspect latest source. |
| HS-010 | Latest gate address does not match terminal | Terminal proof | Inspect latest source. |
| HS-011 | Accepted flag does not match terminal | Terminal proof | Recompute summary. |
| HS-012 | Release-ready flag does not match terminal | Terminal proof | Recompute summary. |
| HS-013 | Promote state has false accepted flag | Decision proof | Reject summary drift. |
| HS-014 | Promote state has false readiness | Decision proof | Reject summary drift. |
| HS-015 | Block state has true readiness | Decision proof | Reject summary drift. |
| HS-016 | History address includes itself | Address proof | Clear field before hashing. |
| HS-017 | History address does not recompute | Address proof | Rebuild package. |
| HS-018 | History includes private path | Public proof | Reject before publication. |
| HS-019 | History includes unbounded entries | Bound proof | Reject oversized package. |
| HS-020 | History version is not current | Version proof | Route to compatible loader. |

## 6. Transition failures

| ID | Condition | Verification | Safe action |
| --- | --- | --- | --- |
| TR-001 | First entry is not initial | Transition replay | Rebuild first entry. |
| TR-002 | Equal quality classified improved | Quality replay | Recompute transition. |
| TR-003 | Equal quality classified regressed | Quality replay | Recompute transition. |
| TR-004 | Upward quality classified regressed | Quality replay | Recompute transition. |
| TR-005 | Downward quality classified improved | Quality replay | Recompute transition. |
| TR-006 | Mixed quality classified stable | Quality replay | Recompute transition. |
| TR-007 | Unknown transition string | Enum validation | Reject package. |
| TR-008 | Transition counter omits entry | Counter replay | Reject package. |
| TR-009 | Transition comparison uses path | Determinism proof | Rebuild without path. |
| TR-010 | Transition comparison uses timestamp | Determinism proof | Rebuild without time. |
| TR-011 | Transition comparison uses hidden field | Public proof | Reject non-public source. |
| TR-012 | Quality vector has wrong sign | Algorithm proof | Use current implementation. |
| TR-013 | Blocker reduction is treated as worse | Algorithm proof | Recompute vector. |
| TR-014 | Warning reduction is treated as worse | Algorithm proof | Recompute vector. |
| TR-015 | Additional passed check is ignored | Algorithm proof | Recompute vector. |

## 7. Append concurrency failures

| ID | Condition | Verification | Safe action |
| --- | --- | --- | --- |
| CO-001 | Expected address omitted | Allowed append | Proceed only when no guard is required. |
| CO-002 | Expected address equals current | Guard success | Append and verify. |
| CO-003 | Expected address is stale | Guard failure | Reload latest history. |
| CO-004 | Expected address is malformed | Guard type | Reject caller input. |
| CO-005 | Expected address is a gate address | Guard semantic | Reject mismatched object. |
| CO-006 | Append mutates original history | Immutability proof | Treat as implementation failure. |
| CO-007 | Append writes before guard | Safety proof | Reject behavior and fix implementation. |
| CO-008 | Append accepts duplicate ID | Identity proof | Reject behavior and fix implementation. |
| CO-009 | Append changes prior entries | Ancestry proof | Reject behavior and fix implementation. |
| CO-010 | Append drops prior counters | Conservation proof | Reject behavior and fix implementation. |

## 8. Diff failures

| ID | Condition | Verification | Safe action |
| --- | --- | --- | --- |
| DF-001 | Baseline is not typed history | Input proof | Load exact baseline. |
| DF-002 | Candidate is not typed history | Input proof | Load exact candidate. |
| DF-003 | Baseline history fails verification | Input proof | Preserve invalid baseline. |
| DF-004 | Candidate history fails verification | Input proof | Preserve invalid candidate. |
| DF-005 | Join key is missing | Join proof | Reject malformed history. |
| DF-006 | Join key is duplicated | Join proof | Reject malformed history. |
| DF-007 | Action is inconsistent with sides | Diff replay | Recompute action. |
| DF-008 | Added item has baseline side | Diff replay | Reject item. |
| DF-009 | Removed item has candidate side | Diff replay | Reject item. |
| DF-010 | Unchanged item projections differ | Diff replay | Recompute item. |
| DF-011 | Changed item projections equal | Diff replay | Recompute item. |
| DF-012 | Direction omits quality movement | Diff replay | Recompute direction. |
| DF-013 | Added direction is regressed | Diff policy | Reject item. |
| DF-014 | Removed direction is improved | Diff policy | Reject item. |
| DF-015 | Aggregate state omits improvement | Diff counter | Recompute aggregate. |
| DF-016 | Aggregate state omits regression | Diff counter | Recompute aggregate. |
| DF-017 | Mixed state has one direction | Diff counter | Recompute aggregate. |
| DF-018 | Baseline address is wrong | Address proof | Rebuild diff. |
| DF-019 | Candidate address is wrong | Address proof | Rebuild diff. |
| DF-020 | Diff item address is wrong | Address proof | Rebuild item. |
| DF-021 | Diff address is wrong | Address proof | Rebuild diff. |
| DF-022 | Diff contains private path | Public proof | Reject before publication. |
| DF-023 | Diff item contains unknown key | Strict mapping | Reject package. |
| DF-024 | Diff item contains missing side fields | Typed mapping | Reject package. |
| DF-025 | Diff version is unsupported | Version proof | Use compatible loader. |

## 9. Query failures

| ID | Condition | Verification | Safe action |
| --- | --- | --- | --- |
| QU-001 | Unknown history resource | Resource vocabulary | Use declared resource. |
| QU-002 | Unknown diff resource | Resource vocabulary | Use declared resource. |
| QU-003 | Invalid history transition | Enum vocabulary | Use declared transition. |
| QU-004 | Invalid gate state | Enum vocabulary | Use declared state. |
| QU-005 | Invalid assurance state | Enum vocabulary | Use declared state. |
| QU-006 | Invalid diff action | Enum vocabulary | Use declared action. |
| QU-007 | Invalid diff direction | Enum vocabulary | Use declared direction. |
| QU-008 | Negative offset | Window bound | Use zero or positive offset. |
| QU-009 | Zero limit | Window bound | Use positive limit. |
| QU-010 | Oversized limit | Window bound | Use bounded limit. |
| QU-011 | Oversized text | Filter bound | Shorten filter. |
| QU-012 | Query object plus kwargs | API contract | Choose one form. |
| QU-013 | Accepted filter is not boolean | Typed filter | Use boolean. |
| QU-014 | Ready filter is not boolean | Typed filter | Use boolean. |
| QU-015 | Query result leaks source path | Public proof | Reject implementation. |
| QU-016 | Query result is not addressed | Address proof | Rebuild result. |
| QU-017 | Query address ignores window | Determinism proof | Include query window. |
| QU-018 | Query returns unbounded rows | Resource bound | Apply limit. |
| QU-019 | Query sort varies by machine | Determinism proof | Use stable order. |
| QU-020 | Query text searches hidden fields | Public proof | Search allowed projection only. |

## 10. Persistence failures

| ID | Condition | Verification | Safe action |
| --- | --- | --- | --- |
| FS-001 | History manifest missing | Exact-file check | Reject package. |
| FS-002 | History summary missing | Exact-file check | Reject package. |
| FS-003 | History entries missing | Exact-file check | Reject package. |
| FS-004 | History extra file | Exact-file check | Preserve and inspect. |
| FS-005 | Diff manifest missing | Exact-file check | Reject package. |
| FS-006 | Diff document missing | Exact-file check | Reject package. |
| FS-007 | Diff extra file | Exact-file check | Preserve and inspect. |
| FS-008 | Artifact is symlink | File-kind check | Replace with verified regular file. |
| FS-009 | Destination already exists | Write safety | Pass explicit overwrite. |
| FS-010 | Destination is a file | Write safety | Choose directory. |
| FS-011 | Parent cannot be created | Filesystem error | Fix authorized permissions. |
| FS-012 | Temporary replacement fails | Atomic write | Retry in safe destination. |
| FS-013 | History byte count differs | Manifest check | Rebuild, do not patch. |
| FS-014 | History byte address differs | Manifest check | Rebuild, do not patch. |
| FS-015 | Diff byte count differs | Manifest check | Rebuild, do not patch. |
| FS-016 | Diff byte address differs | Manifest check | Rebuild, do not patch. |
| FS-017 | JSON has noncanonical whitespace | Canonical check | Rebuild canonical bytes. |
| FS-018 | JSON key order differs | Canonical check | Rebuild canonical bytes. |
| FS-019 | JSON encoding differs | Canonical check | Rebuild UTF-8 bytes. |
| FS-020 | Manifest fields are unknown | Strict manifest | Reject package. |

## 11. API and CLI failures

| ID | Condition | Expected response | Safe action |
| --- | --- | --- | --- |
| SV-001 | Missing build gate | Client error | Supply input. |
| SV-002 | Missing history input | Client error | Supply package. |
| SV-003 | Missing diff baseline | Client error | Supply baseline. |
| SV-004 | Missing diff candidate | Client error | Supply candidate. |
| SV-005 | Malformed JSON body | Client error | Correct request. |
| SV-006 | Wrong route resource | Client error | Use declared route. |
| SV-007 | Valid held build | HTTP 422 / CLI 2 | Route to review. |
| SV-008 | Valid blocked build | HTTP 422 / CLI 2 | Route to review. |
| SV-009 | Invalid package | HTTP client error / CLI 1 | Preserve evidence. |
| SV-010 | Capability request | HTTP 200 / CLI 0 | Inspect fixed vocabulary. |
| SV-011 | Schema request | HTTP 200 / CLI 0 | Inspect closed schema. |
| SV-012 | Unknown command collision | Parser failure | Fix registration before release. |
| SV-013 | Missing command registration | Parser failure | Add public inventory entry. |
| SV-014 | CLI emits local path | Public failure | Reject implementation. |
| SV-015 | API emits local path | Public failure | Reject implementation. |

## 12. Compatibility failures

| ID | Legacy shape | Required behavior |
| --- | --- | --- |
| CP-001 | Older registry package | Reject as wrong package. |
| CP-002 | Older federation package | Reject as wrong package. |
| CP-003 | Older gate package | Reject as wrong package. |
| CP-004 | Older review package | Reject as wrong package. |
| CP-005 | Older decision ledger | Reject unless upstream loader accepts current shape. |
| CP-006 | Older assurance package | Reject as wrong package. |
| CP-007 | Older review history | Reject as incompatible history. |
| CP-008 | Older observatory history | Reject as incompatible history. |
| CP-009 | Hand-edited current package | Reject byte or semantic drift. |
| CP-010 | Renamed legacy file set | Reject exact-file mismatch. |

The correct response to a compatibility failure is to use the original
producer to create a current package. The history loader must not become a
general migration layer.

## 13. Remediation rules

Never patch a content address by hand.

Never patch a manifest receipt by hand.

Never delete a failing artifact before preserving it.

Never convert an old shape by renaming files.

Never classify a malformed package as blocked.

Never classify a held package as malformed.

Never bypass an expected-head mismatch with implicit overwrite.

Never use a local path as a snapshot identity.

Never include private identity in a public report.

Always reload after a write.

Always verify the copied package.

Always retain baseline and candidate addresses for a diff.

Always query regressions before promotion.

## 14. Review evidence record

For each failure, retain:

the package content address when available;

the failing boundary name;

the command or route used;

the public error class or message;

the original package bytes;

the remediation decision;

the replacement package address if rebuilt;

the verification result after remediation.

Do not retain local paths in a public evidence record.

## 15. Matrix sign-off

- [x] Input failures are defined.
- [x] Typed entry failures are defined.
- [x] Chain failures are defined.
- [x] Summary failures are defined.
- [x] Transition failures are defined.
- [x] Concurrency failures are defined.
- [x] Diff failures are defined.
- [x] Query failures are defined.
- [x] Persistence failures are defined.
- [x] API and CLI failures are defined.
- [x] Compatibility failures are defined.
- [x] Remediation rules are explicit.
- [x] Public evidence rules are explicit.
