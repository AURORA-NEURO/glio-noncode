# Decision-Ledger Assurance Matrix

This matrix is the operational companion to
[the assurance contract](RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE.md).
It is written for reviewers who need to answer three questions quickly:

1. what assertion was recomputed;
2. what evidence address supports it; and
3. whether a failure should block, hold, or remain source-controlled.

## Boundary inventory

| Boundary | Input | Output | Exact files | Promotion effect |
| --- | --- | --- | --- | --- |
| source federation gate | persisted federation | source assurance and gate | six source files | source authority |
| review queue | source gate | operational queue and verification | four queue files | routes work |
| decision ledger | review queue | append-only entries and replay | four ledger files | records handling |
| ledger assurance | decision ledger | independent assurance and gate | three assurance files | validates handling |
| assurance diff | two assurance gates | semantic comparison | two diff files | explains change |

The assurance boundary never treats a review entry as replacement evidence for
the source federation gate. It records whether handling is structurally valid
and whether the source decision still allows promotion.

## Finding matrix

| # | Kind | Plane | Required | Input fields | Recomputed relation | Failure class | Evidence |
| ---: | --- | --- | :---: | --- | --- | --- | --- |
| 0 | ledger-address | ledger | yes | summary, address | `address_ledger(ledger) == content_address` | identity drift | ledger address |
| 1 | ledger-contract | ledger | yes | version, boundary, entries | current contract and entry count | unsupported shape | ledger address |
| 2 | queue-linkage | queue | yes | queue, gate, assurance, replay | source links are conserved | orphaned snapshot | ledger address |
| 3 | item-addresses | queue | yes | items | every item address recomputes and is unique | item drift | ledger address |
| 4 | entry-chain | entries | yes | entries, head | ordinals and predecessor heads are continuous | fork or reorder | ledger address |
| 5 | entry-item-linkage | entries | yes | entries, items | ID and address resolve to one frozen item | wrong target | ledger address |
| 6 | action-counters | ledger | yes | counters, entries | counters equal entry action counts | summary drift | ledger address |
| 7 | evidence-policy | policy | yes | action, evidence | only remediation/waiver carry evidence | policy violation | ledger address |
| 8 | transition-policy | policy | yes | item state, action | each action is legal from prior state | illegal transition | ledger address |
| 9 | replay-projection | replay | yes | replay, entries, items | independent replay equals stored replay | stale projection | ledger address |
| 10 | source-authority | source | yes | accepted, ready, source flags | local state preserves source state | false promotion | ledger address |
| 11 | closure-readiness | policy | no | release-ready, source-ready, state | readiness equals source-ready and clear | incomplete closure | ledger address |
| 12 | public-boundary | public | yes | serialized ledger | no forbidden keys or path values | privacy boundary | ledger address |
| 13 | replay-addresses | replay | yes | replay items, replay | all replay addresses recompute | receipt drift | ledger address |

## Gate matrix

| # | Kind | Plane | Required | Pass condition | Failed result | Evidence address |
| ---: | --- | --- | :---: | --- | --- | --- |
| 0 | assurance-accepted | ledger | yes | no required assurance failures | block | assurance address |
| 1 | assurance-release-ready | ledger | yes | no assurance warnings | block | assurance address |
| 2 | source-accepted | source | yes | source replay accepted | block | ledger address |
| 3 | source-release-ready | source | no | source replay release-ready | hold | ledger address |
| 4 | ledger-clear | replay | no | ledger replay is clear | hold | replay address |
| 5 | no-open-items | replay | no | no open or acknowledged item | hold | replay address |
| 6 | no-blocked-items | replay | yes | no blocked item | block | replay address |
| 7 | no-escalated-items | replay | no | no escalated item | hold | replay address |
| 8 | head-continuity | entries | yes | head is initial or terminal | block | ledger address |
| 9 | public-boundary | public | yes | ledger and assurance are public | block | assurance address |

## Review item state matrix

The source review item has a fixed initial state. Decisions create replay
states; they do not mutate the frozen source item.

| Initial source result | Required | Initial state | Initial priority | Typical handling |
| --- | :---: | --- | --- | --- |
| passed finding/check | no or yes by source severity | `clear` | `none` | no action |
| failed warning | no | `open` | `high` | acknowledge, remediate, waive, escalate |
| failed blocker | yes | `blocked` | `critical` | acknowledge, remediate, escalate |

| Current state | Acknowledge | Remediate | Waive | Escalate | Reopen |
| --- | :---: | :---: | :---: | :---: | :---: |
| `clear` | reject | reject | reject | reject | reject |
| `open` | allow | allow with evidence | allow with evidence if optional | allow | reject |
| `blocked` | allow | allow with evidence | reject | allow | reject |
| `acknowledged` | allow | allow with evidence | allow with evidence if optional | allow | reject |
| `resolved` | reject | reject | reject | reject | allow |
| `waived` | reject | reject | reject | reject | allow |
| `escalated` | allow | allow with evidence | allow with evidence if optional | allow | allow |

The action transition table is independently reimplemented by the assurance
module. If an entry sequence cannot be replayed by that table, the assurance
result is blocked even when an entry's content address is otherwise valid.

## Evidence matrix

| Action | Fixed no-evidence address allowed | Non-empty evidence required | Why |
| --- | :---: | :---: | --- |
| acknowledge | yes | no | records that a reviewer saw the item |
| remediate | no | yes | claims handling evidence exists |
| waive | no | yes | records an evidence-backed exception |
| escalate | yes | no | routes the item without closing it |
| reopen | yes | no | returns a handled item to active review |

An evidence address is only a receipt-shaped address at this boundary. The
assurance module does not inspect the scientific meaning behind that address.
Evidence content remains the responsibility of the source process and its
applicable review controls.

## Source-authority matrix

| Source acceptance | Source readiness | Local item state | Assurance | Independent gate |
| :---: | :---: | --- | --- | --- |
| false | false | `blocked` | may pass structurally | `block` |
| false | true | `blocked` | source finding may fail | `block` |
| true | false | `review` | may pass structurally | `hold` |
| true | false | `clear` | may pass structurally | `hold` |
| true | true | `review` | may pass structurally | `hold` |
| true | true | `clear` | may pass structurally | `promote` |

The matrix intentionally has no row in which local remediation makes a
source-not-ready input promote. New source evidence must create a new source
gate and queue snapshot.

## Persistence matrix

| Package | Required file | Canonical | Addressed | Byte receipt | Extra files rejected |
| --- | --- | :---: | :---: | :---: | :---: |
| assurance gate | `manifest.json` | yes | yes | n/a | yes |
| assurance gate | `assurance.json` | yes | yes | yes | yes |
| assurance gate | `gate.json` | yes | yes | yes | yes |
| assurance diff | `manifest.json` | yes | yes | n/a | yes |
| assurance diff | `diff.json` | yes | yes | yes | yes |

| Loader check | Assurance gate | Assurance diff | Failure behavior |
| --- | :---: | :---: | --- |
| input is a regular directory | yes | yes | reject |
| directory is not a symlink | yes | yes | reject |
| child files are not symlinks | yes | yes | reject |
| exact file membership | yes | yes | reject |
| UTF-8 JSON | yes | yes | reject |
| canonical JSON bytes | yes | yes | reject |
| manifest address | yes | yes | reject |
| artifact byte hash | yes | yes | reject |
| nested content addresses | yes | yes | reject |
| cross-document linkage | yes | yes | reject |

## Diff join matrix

| Record family | Stable join key | Compared semantic fields | Address retained |
| --- | --- | --- | --- |
| assurance finding | `assurance:<plane>:<kind>` | severity, required, passed | baseline and candidate |
| gate check | `gate:<plane>:<kind>` | severity, required, passed | baseline and candidate |

| Baseline | Candidate | Action | Direction when candidate is better |
| --- | --- | --- | --- |
| absent | present | `added` | improved if pass, regressed otherwise |
| present | absent | `removed` | improved if baseline was blocker |
| present | present, same | `unchanged` | none |
| present | present, changed | `changed` | compare outcome score |

| Outcome | Score |
| --- | ---: |
| failed required or blocker | 0 |
| failed optional or warning | 1 |
| passed | 2 |

Diff state is `unchanged` when every record is unchanged, `improved` when only
improvements exist, `regressed` when only regressions exist, and `changed` for
mixed or non-directional changes.

## Query matrix

| Query surface | Resources | Filters | Maximum window |
| --- | --- | --- | ---: |
| assurance | summary, findings, blockers, warnings, checks, failed | severity, passed, required, plane, text | 4,096 |
| diff | summary, actions, added, removed, changed, unchanged, improved, regressed | action, plane, text | 4,096 |

| Query input | Valid boundary | Invalid boundary |
| --- | --- | --- |
| resource | fixed resource vocabulary | reject |
| severity | `pass`, `warning`, `blocker` | reject |
| plane | fixed assurance planes | reject |
| action | `added`, `removed`, `unchanged`, `changed` | reject |
| offset | non-negative bounded integer | reject |
| limit | positive bounded integer | reject |
| text | bounded case-insensitive string | reject |

Query result addresses include the query, returned rows, total count, and
source package address. A result is therefore safe to cache and compare in a
review handoff.

## Output matrix

| Output | Intended consumer | Ordering rule | Source of truth |
| --- | --- | --- | --- |
| canonical JSON | machine integration | canonical serializer | typed projection |
| CSV | spreadsheet and audit import | fixed columns | typed projection |
| Markdown | human review | sorted summary and fields | typed projection |

No output mode adds a local path or runtime attribution. The JSON and CSV
formats retain all addresses needed to locate the related package without
embedding machine-specific directory names.

## Tamper matrix

| Tamper operation | Finding/check | Package loader | Expected operator action |
| --- | --- | --- | --- |
| edit ledger summary | ledger-address | may load source ledger if re-written | rebuild source ledger |
| edit item address | item-addresses | nested address check | restore queue snapshot |
| edit entry predecessor | entry-chain | entry address/manifest | restore append order |
| edit entry item address | entry-item-linkage | nested address check | target frozen item |
| edit action counter | action-counters | ledger address | recompute counters |
| delete remediation receipt | evidence-policy | nested contract | attach evidence |
| add illegal action | transition-policy | nested contract | discard invalid entry |
| edit replay count | replay-projection | replay address | regenerate replay |
| edit source readiness | source-authority | ledger address | use a new source gate |
| add forbidden key | public-boundary | strict mapping | remove private attribute |
| edit replay address | replay-addresses | nested address check | regenerate replay receipts |
| edit assurance JSON | artifact byte receipt | reject | restore package bytes |
| edit gate JSON | artifact byte receipt | reject | restore package bytes |
| edit manifest | manifest address | reject | restore manifest |
| add file | exact membership | reject | remove extra file |

## Demonstration matrix

| Demonstration | Source | Expected result | What it proves |
| --- | --- | --- | --- |
| ready ledger build | current four-file ledger | 14/14 findings, promote | clean current contract |
| held ledger build | current four-file ledger | 14/14 findings, hold | source authority |
| blocked ledger build | current four-file ledger | gate block | required source failure |
| entry tamper | in-memory mutation | entry-chain failure | independent recomputation |
| persistence reload | three-file assurance package | same address | durable receipt integrity |
| diff ready versus held | two assurance packages | source check changed | release comparison |
| old downloaded artifact | prior package shape | explicit rejection | no silent migration |

## CI matrix

| CI surface | Command family | Coverage |
| --- | --- | --- |
| focused tests | `tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance` | build, tamper, persistence, query, CLI, HTTP |
| public inventory | `tests.test_public_surface_audit` | schema and capability closure |
| capability command | long-form CLI `...-decision-ledger-assurance-capabilities` | public command registration |
| static analysis | `ruff check` | new module and focused tests |
| bytecode check | `python -m py_compile` | syntax and import compilation |

## Reviewer decision template

Use the following compact record in an operational review:

```text
ledger_address: <content address>
assurance_address: <content address>
gate_address: <content address>
assurance_state: <passed|warning|blocked>
gate_state: <promote|hold|block>
release_ready: <true|false>
required_failures: <count>
optional_failures: <count>
source_release_ready: <true|false>
```

Then attach the exact package and, when comparing a change, the exact diff
package. Do not summarize a hold as a source failure if the only failed check
is optional source readiness. Do not summarize a resolved review item as a
changed source finding.

## Compatibility decision table

| Input shape | Recognized as current ledger | Action |
| --- | :---: | --- |
| current four-file ledger, canonical bytes | yes | assure and gate |
| current ledger with extra file | no | reject |
| current ledger with unknown field | no | reject |
| current ledger with old version | no | reject |
| older observatory packet registry | no | reject |
| older federation gate package | no | reject |
| arbitrary JSON directory | no | reject |

The explicit rejection path makes the demo honest. Data can be downloaded and
used when it matches a declared boundary, but an old repository or old artifact
does not become a framework or a migration source by implication.

## Release acceptance matrix

| Acceptance question | Required answer |
| --- | --- |
| Are all finding/check counts conserved? | yes |
| Are all content addresses stable on a second build? | yes |
| Is source readiness preserved? | yes |
| Are blockers distinguished from warnings? | yes |
| Is the exact file set enforced? | yes |
| Are canonical bytes enforced? | yes |
| Is the public boundary recursive? | yes |
| Are CLI and HTTP surfaces aligned? | yes |
| Is the public inventory closed? | yes |
| Is current-format downloaded input covered? | yes |
| Is old-format input silently converted? | no |
| Are operator actions represented as source changes? | no |

The matrix is complete when each answer can be traced to code, a focused test,
and a persisted artifact or deterministic output.
