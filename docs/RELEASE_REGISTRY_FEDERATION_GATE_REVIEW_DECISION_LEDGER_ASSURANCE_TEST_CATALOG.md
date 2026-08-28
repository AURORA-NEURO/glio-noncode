# Release Registry Federation Gate Review Decision Ledger Assurance Test Catalog

Status: implemented contract catalog

This catalog describes the verification depth for the release-registry federation gate review decision ledger assurance module. It is intended to make a downloaded ledger demonstrable, repeatable, and inspectable without relying on a private execution context.

The catalog has four purposes:

- identify the independent facts recomputed by assurance;
- describe the boundary between source ledger validation and assurance validation;
- give maintainers deterministic failure-injection scenarios;
- provide a release operator with a short, auditable completion record.

The catalog is written against the current persisted ledger contract. An older downloaded packet is not upgraded by inference. It is rejected when its version, shape, address graph, or public projection does not satisfy the current contract.

## 1. Test vocabulary

`source ledger` means the persisted federation review decision ledger produced by the review-store module.

`assurance report` means the independent finding collection built from the source ledger.

`release gate` means the second-stage promote, hold, or block decision built from the source ledger and assurance report.

`assurance gate bundle` means the typed pair of the assurance report and release gate, with a content address over both projections.

`candidate` means the later bundle in a diff comparison.

`baseline` means the earlier bundle in a diff comparison.

`public projection` means the recursively serializable data returned by the public API, CLI, JSON, CSV, and Markdown renderers.

`evidence address` means a content address or a permitted explicit no-evidence sentinel. It is never a local file path.

`canonical bytes` means UTF-8 canonical JSON with stable key ordering and stable separators.

`exact directory` means a persisted package containing exactly the files named by its manifest contract, with no symlinks and no unlisted extras.

## 2. Test layers

The module uses several layers because one successful constructor is not enough to establish release safety.

| Layer | Input | Primary question | Expected result |
| --- | --- | --- | --- |
| Shape | typed objects and mappings | Are fields bounded and typed? | invalid shapes are rejected |
| Address | canonical projections | Do addresses reproduce? | tampering is detected |
| Linkage | ledger, queue, item, decision, replay links | Does the graph remain connected? | broken edges fail required findings |
| Replay | decision sequence | Does independent replay reach the stored state? | state and counts match |
| Policy | source acceptance, readiness, and closure | Are promotion rules conserved? | invalid readiness fails the gate |
| Boundary | recursive public projections | Is private metadata excluded? | forbidden keys and path-like values fail |
| Persistence | manifests and exact files | Can a package be reloaded without drift? | byte and address equality hold |
| Query | findings, checks, and diff items | Are filters deterministic? | stable order and bounded limits |
| Diff | baseline and candidate bundles | Are changes classified correctly? | add, remove, change, unchanged |
| Interface | API and CLI | Can an operator use the contract? | schemas and exit semantics agree |
| Workflow | CI commands | Does automation exercise the boundary? | focused commands are runnable |

## 3. Assurance finding inventory

Every assurance build emits fourteen findings in fixed ordinal order. The fixed order is part of the contract because it makes review output comparable across downloads and runs.

### 3.1 Finding 0: ledger address

- Plane: ledger.
- Severity when failed: blocker.
- Required: yes.
- Input: the source ledger projection.
- Recomputed fact: the source ledger content address equals its declared content address.
- Positive fixture: a freshly built ready, held, or blocked current-format ledger.
- Negative fixture: change one source field without changing the declared address.
- Expected outcome: the finding fails and assurance state becomes `blocked`.
- Evidence: the source ledger address.
- Remediation: regenerate the source ledger address after changing content.

### 3.2 Finding 1: ledger contract

- Plane: contract.
- Severity when failed: blocker.
- Required: yes.
- Input: version, boundary, identifiers, and bounded collections.
- Recomputed fact: the ledger conforms to the current release-registry review contract.
- Positive fixture: a ledger built by the current review-store constructor.
- Negative fixture: replace the version, omit a required field, or inject an unknown field.
- Expected outcome: the finding fails or source loading rejects the mapping.
- Evidence: the ledger content address.
- Remediation: use the current persisted schema and rebuild the package.

### 3.3 Finding 2: queue linkage

- Plane: linkage.
- Severity when failed: blocker.
- Required: yes.
- Input: ledger queue address and nested queue projection.
- Recomputed fact: the queue address and queue identity agree with the source ledger.
- Positive fixture: an unchanged source ledger.
- Negative fixture: alter the queue address or queue identifier.
- Expected outcome: a required finding fails without changing unrelated findings.
- Evidence: the ledger and queue addresses.
- Remediation: restore the source queue projection or regenerate the ledger.

### 3.4 Finding 3: item addresses

- Plane: address graph.
- Severity when failed: blocker.
- Required: yes.
- Input: all queue items and their content addresses.
- Recomputed fact: each item address reproduces from its public item projection.
- Positive fixture: every item from a current-format fixture.
- Negative fixture: change priority, evidence, or state while preserving an old address.
- Expected outcome: the finding fails and the gate cannot promote.
- Evidence: the first mismatching item address.
- Remediation: regenerate changed item addresses through the source constructor.

### 3.5 Finding 4: entry chain

- Plane: decision chain.
- Severity when failed: blocker.
- Required: yes.
- Input: ordered decision entries and previous addresses.
- Recomputed fact: the first entry starts at the initial head and every later entry points to the prior entry.
- Positive fixture: a ledger with zero or more correctly chained decisions.
- Negative fixture: swap two entries or alter one previous address.
- Expected outcome: the finding fails while the original bytes remain available for inspection.
- Evidence: the first broken previous-address edge.
- Remediation: rebuild the decision chain in source order.

### 3.6 Finding 5: entry-item linkage

- Plane: linkage.
- Severity when failed: blocker.
- Required: yes.
- Input: entry item identifiers and item addresses.
- Recomputed fact: every decision references the item it claims to review and the current item address.
- Positive fixture: a ledger created from the current review queue.
- Negative fixture: point one decision to a different item or stale item address.
- Expected outcome: the required finding fails.
- Evidence: the decision content address and referenced item address.
- Remediation: regenerate the decision from the intended item snapshot.

### 3.7 Finding 6: action counters

- Plane: accounting.
- Severity when failed: blocker.
- Required: yes.
- Input: action totals and ordered decisions.
- Recomputed fact: promote, hold, block, and total counts equal the ordered entries.
- Positive fixture: ready, held, and blocked ledgers.
- Negative fixture: increment a counter without adding a decision.
- Expected outcome: the finding fails and the gate remains non-promotable.
- Evidence: the ledger summary and recomputed totals.
- Remediation: rebuild counters from entries instead of hand-editing them.

### 3.8 Finding 7: evidence policy

- Plane: policy.
- Severity when failed: blocker.
- Required: yes.
- Input: required flags, outcomes, evidence addresses, and no-evidence sentinel.
- Recomputed fact: required decisions carry meaningful evidence and optional decisions obey the declared sentinel policy.
- Positive fixture: source decisions using valid content addresses.
- Negative fixture: replace required evidence with a local path, empty value, or unapproved sentinel.
- Expected outcome: the finding fails.
- Evidence: the offending item or decision address.
- Remediation: attach a permitted evidence address or correct the item requirement.

### 3.9 Finding 8: transition policy

- Plane: state machine.
- Severity when failed: blocker.
- Required: yes.
- Input: item state, action, and decision order.
- Recomputed fact: every transition is allowed by the review state machine and the final state is the replayed state.
- Positive fixture: each supported transition path.
- Negative fixture: create a transition from a terminal or incompatible state.
- Expected outcome: the finding fails.
- Evidence: the transition ordinal and item identifier.
- Remediation: use an allowed action for the current state.

### 3.10 Finding 9: replay projection

- Plane: replay.
- Severity when failed: blocker.
- Required: yes.
- Input: initial queue state and ordered entries.
- Recomputed fact: independent replay reproduces item states, counts, and readiness.
- Positive fixture: all three source outcome fixtures.
- Negative fixture: alter a stored replay item, replay count, or source readiness flag.
- Expected outcome: the finding fails.
- Evidence: the replay content address and first differing row.
- Remediation: regenerate the replay projection from source entries.

### 3.11 Finding 10: source authority

- Plane: source authority.
- Severity when failed: blocker.
- Required: yes.
- Input: ledger acceptance and source gate readiness.
- Recomputed fact: the ledger cannot override source acceptance or source readiness.
- Positive fixture: source and ledger flags agree.
- Negative fixture: set ledger acceptance true while source acceptance is false.
- Expected outcome: the finding fails.
- Evidence: the source gate and ledger summary.
- Remediation: preserve source authority and rebuild derived fields.

### 3.12 Finding 11: closure readiness

- Plane: policy.
- Severity when failed: warning.
- Required: no.
- Input: replay source readiness and final queue state.
- Recomputed fact: promotion requires source readiness and a clear replay state.
- Positive fixture: ready source with a clear replay.
- Warning fixture: source is accepted but the replay remains open.
- Expected outcome: a warning may hold release readiness without invalidating the source graph.
- Evidence: the replay summary.
- Remediation: resolve active review states before promoting.

### 3.13 Finding 12: public boundary

- Plane: public boundary.
- Severity when failed: blocker.
- Required: yes.
- Input: every nested public projection.
- Recomputed fact: private identity, local paths, and execution-language attributes are absent.
- Positive fixture: public data with content addresses only.
- Negative fixture: inject a forbidden key or a local path into a nested record.
- Expected outcome: the finding fails.
- Evidence: the boundary scanner result.
- Remediation: remove the private value from the public projection and rebuild addresses.

### 3.14 Finding 13: replay addresses

- Plane: replay.
- Severity when failed: blocker.
- Required: yes.
- Input: replay items and replay snapshot.
- Recomputed fact: item and replay content addresses reproduce independently.
- Positive fixture: current replay projections.
- Negative fixture: alter any replay address while leaving the projection intact.
- Expected outcome: the finding fails.
- Evidence: the mismatching replay address.
- Remediation: rebuild replay addresses from canonical data.

## 4. Gate check inventory

The release gate evaluates ten checks after assurance findings are built. Required failures block promotion; optional failures hold readiness when they represent incomplete closure rather than invalid structure.

| Ordinal | Check | Required | Plane | Promotion meaning |
| ---: | --- | :---: | --- | --- |
| 0 | assurance-accepted | yes | ledger | no blocker finding exists |
| 1 | assurance-release-ready | yes | ledger | no warning or blocker finding exists |
| 2 | source-accepted | yes | source | source authority accepts the ledger |
| 3 | source-release-ready | no | source | source is ready for promotion |
| 4 | ledger-clear | no | replay | no open queue state remains |
| 5 | no-open-items | no | replay | no open review items remain |
| 6 | no-blocked-items | yes | replay | no blocked item remains |
| 7 | no-escalated-items | no | replay | no escalation remains |
| 8 | head-continuity | yes | linkage | the declared head is the last decision |
| 9 | public-boundary | yes | public | the gate projection is safe to publish |

The gate state is derived from the complete check set:

- `promote` requires accepted assurance, release-ready assurance, source acceptance, no required failure, and no optional warning;
- `hold` represents a structurally valid graph with one or more optional warnings;
- `block` represents any required failure or rejected assurance.

The derivation is deterministic. It does not depend on wall-clock time, local path names, machine identity, or the order in which API and CLI calls occur.

## 5. Positive fixture matrix

The positive matrix ensures that outcome diversity does not accidentally become a single happy path.

| Fixture | Source state | Source accepted | Source ready | Expected assurance | Expected gate |
| --- | --- | :---: | :---: | --- | --- |
| ready | clear | yes | yes | passed | promote |
| held | open or escalated | yes | no | passed or warning | hold |
| blocked | blocked | no or no-ready | no | blocked | block |

For each fixture, the test suite verifies:

- the source ledger loads from an exact current-format directory;
- the typed assurance report is deterministic across repeated builds;
- the typed gate is deterministic across repeated builds;
- every finding has a unique fixed ordinal;
- every check has a unique fixed ordinal;
- counts equal the length of their corresponding sequences;
- the nested address graph is self-consistent;
- the public projection excludes private metadata;
- JSON, CSV, and Markdown outputs are stable;
- the exact package can be written and loaded;
- the package manifest addresses match its bytes;
- a same-snapshot diff is unchanged;
- a changed-snapshot diff identifies the intended key.

## 6. Address determinism protocol

Address determinism is tested independently from object identity.

1. Build a source ledger from a fixture.
2. Build an assurance report with the default assurance identifier.
3. Build the same assurance report again from the same source object.
4. Assert equal canonical JSON.
5. Assert equal assurance content address.
6. Build the release gate twice.
7. Assert equal gate content address.
8. Build the combined bundle twice.
9. Assert equal bundle content address.
10. Serialize each projection with the public renderer.
11. Assert the renderer output is byte-for-byte stable.
12. Write the package to two different temporary directories.
13. Compare the manifest addresses.
14. Compare all artifact bytes.
15. Reload both packages.
16. Compare typed projections.
17. Change only an identifier explicitly allowed by the API.
18. Assert the identifier changes while the source ledger address remains stable.
19. Change a semantic field.
20. Assert the affected object and every dependent address change.

No address is based on an in-memory object identity, random value, timestamp, or local directory name.

## 7. Exact persistence protocol

An assurance package contains exactly these files:

| File | Purpose |
| --- | --- |
| `manifest.json` | package version, file list, sizes, and addresses |
| `assurance.json` | canonical independent findings |
| `gate.json` | canonical release checks |

The persistence tests cover the following cases:

- the destination is created when absent;
- existing files are replaced atomically only after the new bytes are complete;
- the manifest is written after artifacts are finalized;
- artifact bytes use canonical JSON encoding;
- artifact sizes equal manifest sizes;
- artifact addresses equal manifest addresses;
- the manifest lists no undeclared files;
- a missing assurance artifact is rejected;
- a missing gate artifact is rejected;
- a missing manifest is rejected;
- an extra artifact is rejected;
- an extra hidden artifact is rejected;
- a symbolic link is rejected;
- a changed artifact is rejected;
- a changed manifest is rejected;
- a wrong package version is rejected;
- an unsupported file name is rejected;
- a directory in place of a file is rejected;
- a file in place of the destination directory is rejected;
- reloading after a successful write returns typed objects;
- reloading and rewriting produces identical bytes.

The write path uses a short temporary prefix because Windows path limits are part of the supported environment. Temporary paths are internal and do not enter a public projection.

## 8. Mapping and strictness protocol

Mapping tests are intentionally stricter than rendering tests.

| Mutation | Mapping result | Reason |
| --- | --- | --- |
| omit required top-level field | reject | schema is incomplete |
| add unknown top-level field | reject | contract drift must be visible |
| change a boolean to a string | reject | typed semantics must not be inferred |
| change a count to a float | reject | counters are integral |
| change an ordinal to a negative value | reject | sequence bounds are violated |
| change an address to an empty string | reject | address graph is broken |
| change an enum to an unknown value | reject | state space is closed |
| change nested item field | reject or fail address | nested content is addressed |
| reorder findings | reject | ordinal order is fixed |
| reorder checks | reject | ordinal order is fixed |
| duplicate finding ordinal | reject | sequence identity is ambiguous |
| duplicate check ordinal | reject | gate interpretation is ambiguous |
| inject a local path | fail public boundary | local state cannot be published |
| inject private identity key | fail public boundary | public contract excludes identity |
| inject execution-language key | fail public boundary | public contract stays implementation-neutral |

The strict loader never silently drops unknown fields. A rejected mapping is more useful than a partially interpreted artifact because it preserves the difference between a current ledger and an older or incompatible download.

## 9. Independent recomputation protocol

The independent verifier is deliberately separate from the source constructor.

- It recomputes the source address from the source public projection.
- It recomputes every item address from the item projection.
- It checks the entry chain without using the source chain helper.
- It recomputes action counters from entries.
- It derives state transitions through an assurance-local transition function.
- It derives replay items and summary counts from the entries.
- It recomputes replay item addresses and replay snapshot address.
- It checks source authority and closure readiness separately.
- It scans the final projection for forbidden public values.

The verifier does not repair a bad source ledger. Its output is a finding report. This distinction matters in downloaded-data workflows: a repair could make an invalid artifact appear valid while an assurance report preserves the observed failure.

## 10. Failure-injection recipes

These recipes are used by the failure matrix and are suitable for manual demonstrations.

### Recipe A: changed ledger field

- Load a valid current ledger mapping.
- Change only the ledger display identifier.
- Retain the original content address.
- Build assurance from the typed mapping if the loader permits it.
- Expect `ledger-address` to fail.
- Expect `ledger-contract` to remain independently evaluated.
- Expect the gate state to be `block`.
- Expect the failure evidence to contain an address, not a local path.

### Recipe B: stale item address

- Select the first queue item.
- Change its priority.
- Retain its old content address.
- Preserve all unrelated items.
- Expect `item-addresses` to fail.
- Expect `replay-addresses` to fail if the replay contains the stale item.
- Expect no unrelated source identifier to be invented.
- Expect the package writer to refuse the invalid assurance bundle.

### Recipe C: broken decision chain

- Select the second decision entry.
- Replace its `previous_address` with the initial head.
- Retain the declared head.
- Expect `entry-chain` to fail.
- Expect `head-continuity` to fail when the last entry no longer matches the chain.
- Expect the gate to block.
- Expect diff output to classify the changed entry if compared with a valid baseline.

### Recipe D: counter inflation

- Increase one action counter.
- Leave the entries untouched.
- Expect `action-counters` to fail.
- Expect replay summary checks to distinguish source counters from recomputed counters.
- Expect the output to remain deterministic.

### Recipe E: evidence path injection

- Replace required evidence with a Windows path.
- Preserve the item address to simulate an unsafe legacy projection.
- Expect `evidence-policy` or `public-boundary` to fail.
- Expect Markdown and JSON renderers not to publish the path.
- Expect the package to be rejected before release.

### Recipe F: state transition violation

- Change a decision action to one that is invalid for the item’s current state.
- Preserve the old item state.
- Expect `transition-policy` to fail.
- Expect `replay-projection` to fail if the derived state diverges.
- Expect the gate to block.

### Recipe G: replay projection drift

- Change one replay item state without changing source entries.
- Retain the replay content address.
- Expect `replay-projection` to fail.
- Expect `replay-addresses` to fail.
- Expect source authority to remain a separate finding.

### Recipe H: source authority override

- Set the ledger acceptance field to true.
- Set source replay acceptance to false.
- Preserve all other fields.
- Expect `source-authority` to fail.
- Expect `source-accepted` gate check to fail.
- Expect no automatic promotion.

### Recipe I: closure warning

- Use a source that is accepted but not release-ready.
- Keep the graph and addresses valid.
- Expect all required structural findings to pass.
- Expect a warning from `closure-readiness` or source readiness.
- Expect the gate to hold rather than block when no required invariant is broken.

### Recipe J: forbidden nested key

- Inject a forbidden key into a nested finding detail mapping.
- Keep all known fields unchanged.
- Expect the public boundary finding to fail.
- Expect recursive scanning to find the nested key.
- Expect API public serialization to reject or withhold the unsafe result.

### Recipe K: manifest tampering

- Write a valid assurance package.
- Change one manifest address without changing the artifact.
- Reload the package.
- Expect a manifest validation error.
- Expect no typed bundle to be returned.

### Recipe L: extra file

- Write a valid assurance package.
- Add an unlisted JSON file.
- Reload the package.
- Expect exact-directory validation to fail.

### Recipe M: symbolic link

- Write a valid package in a temporary directory.
- Replace one artifact with a symbolic link when the host supports it.
- Reload the package.
- Expect the package to fail exact-file validation.

### Recipe N: old downloaded artifact

- Point the loader at an older downloaded replay artifact.
- Do not transform or rename its fields.
- Expect current-format validation to reject it.
- Record the rejection as an incompatibility signal.
- Use a current-format download or current fixture for the positive demo.

### Recipe O: diff address drift

- Build a valid baseline and candidate.
- Change one diff item detail after construction.
- Retain the old diff item address.
- Expect diff verification to fail.
- Expect the bundle addresses to remain independently verifiable.

## 11. Query contract catalog

Assurance queries and diff queries are bounded, stable, and public-safe.

### Assurance query dimensions

- plane filters to ledger, contract, linkage, accounting, policy, state machine, replay, source authority, or public boundary;
- severity filters to pass, warning, or blocker;
- required filters separate mandatory findings from advisory findings;
- passed filters select only passing or failing findings;
- state filters select passed, warning, or blocked reports;
- limit bounds the returned row count;
- offset provides stable pagination over ordinal order.

### Diff query dimensions

- action filters to add, remove, change, or unchanged;
- outcome filters to promote, hold, or block where the item carries an outcome;
- plane filters to assurance or gate;
- kind filters to a specific finding or check kind;
- limit bounds the returned row count;
- offset preserves deterministic pagination.

Each query test verifies:

- the same query returns the same rows;
- a zero limit returns an empty result with stable metadata;
- a limit above the contract maximum is rejected;
- a negative offset is rejected;
- an unknown plane is rejected;
- an unknown severity is rejected;
- an unknown action is rejected;
- filtered rows retain their original ordinals;
- filtered rows retain their content addresses;
- query result content addresses reproduce;
- query renderers contain no local paths.

## 12. Diff classification catalog

Diff classification is performed over stable logical keys, not array positions alone.

| Case | Baseline | Candidate | Classification |
| --- | --- | --- | --- |
| no record | absent | absent | not emitted |
| introduced finding | absent | present | add |
| removed finding | present | absent | remove |
| same record | present | equal | unchanged |
| changed record | present | unequal | change |
| added gate check | absent | present | add |
| removed gate check | present | absent | remove |
| changed outcome | present | present with changed fields | change |

The diff contract records both baseline and candidate addresses when present. A missing side is represented by the explicit no-record sentinel, not by a local path or a fabricated zero address.

The diff tests also verify:

- identical bundles produce no semantic changes;
- ready to held changes include the source readiness transition;
- held to blocked changes include the required failing check;
- changed finding severity is visible;
- changed evidence address is visible;
- item order is stable after classification;
- diff item addresses reproduce;
- diff package manifests are exact;
- diff verification rejects artifact tampering;
- diff queries expose action and outcome filters.

## 13. JSON, CSV, and Markdown output catalog

### JSON

- keys are canonical and stable;
- nested records remain typed after a round trip;
- no path-like local input appears;
- no forbidden identity or execution-language key appears;
- content addresses remain strings;
- booleans remain JSON booleans;
- counts remain JSON integers;
- enumeration values remain closed strings.

### CSV

- assurance findings use fixed columns;
- gate checks use fixed columns;
- diff items use fixed columns;
- header order is stable;
- line endings are stable;
- empty optional values do not shift columns;
- content addresses remain visible evidence references;
- CSV rendering does not mutate typed objects.

### Markdown

- the summary identifies the ledger and bundle addresses;
- finding counts agree with typed counts;
- gate state is visible;
- required failures are distinguishable from warnings;
- tables preserve ordinal order;
- remediation text is present for failures;
- no local paths appear;
- no private metadata appears;
- output is deterministic for the same bundle.

## 14. API contract catalog

The API exposes the assurance route under the full current review route plus `/decision-ledger/assurance`. The route is intentionally long because the public path identifies the module lineage and avoids collision with earlier packet families.

The API tests verify the following resources:

- base schema;
- assurance schema;
- finding schema;
- gate schema;
- check schema;
- query schema;
- diff schema;
- diff item schema;
- diff query schema;
- capabilities;
- verification;
- query;
- diff construction;
- diff verification;
- diff query.

For each resource, the tests verify:

- the response is JSON-serializable;
- the public route does not expose local input paths;
- schema fields match the typed model;
- additional properties are closed where required;
- bounded arrays declare their maximum sizes;
- capability resources enumerate the matching query resources;
- invalid payloads return the project’s validation error shape;
- a valid current ledger produces deterministic output;
- the verification result preserves promote, hold, or block semantics.

The API accepts a current-format persisted ledger directory or a server-local typed source selected by the existing route machinery. It does not accept a legacy artifact by guessing a conversion.

## 15. CLI contract catalog

The CLI has separate commands for construction, verification, querying, schemas, capabilities, and diffs. Each command writes only the requested public projection.

The CLI tests verify:

- build creates an exact package;
- verify returns a readable result;
- query filters by plane and outcome;
- schema commands are available;
- capabilities lists resources;
- diff compares two exact packages;
- diff verification detects tampering;
- diff query filters changed records;
- JSON output is deterministic;
- Markdown output is readable;
- CSV output has a fixed header;
- invalid source paths fail clearly;
- legacy artifact paths fail as incompatible current-format input;
- promote returns exit status 0;
- hold returns exit status 2;
- block returns exit status 2;
- no command writes hidden state into the public destination;
- no public output includes local machine identity or execution-language attributes.

The exit status is intentionally conservative. A non-promote state is not a successful release decision even when the data is structurally valid.

## 16. Workflow contract catalog

The CI workflow runs the assurance tests as a focused contract gate in addition to the broad suite.

The workflow checks:

- compilation of changed Python modules;
- linting of the assurance implementation;
- linting of the assurance tests;
- focused assurance unit tests;
- public-surface audit;
- long CLI capabilities command;
- diff cleanliness;
- forbidden public metadata audit;
- exact persistence behavior;
- no uncommitted generated artifacts after the test run.

The workflow does not depend on a private developer path. Temporary directories are created by the test process and are cleaned up by test fixtures.

## 17. Real downloaded-data demo protocol

The demo is designed for a downloaded current-format ledger, not a synthetic in-memory-only object.

1. Obtain a current-format review decision ledger directory.
2. Confirm the directory contains the source package’s exact manifest and artifacts.
3. Run the assurance demo with the source directory and an output destination.
4. Read the compact summary.
5. Open `manifest.json`, `assurance.json`, and `gate.json`.
6. Compare the bundle address with the summary.
7. Run the verify command against the output directory.
8. Run a query for required failed findings.
9. Run a query for gate checks that did not pass.
10. Render Markdown for human review.
11. If a baseline is available, build a diff package.
12. Query the diff for changed records.
13. Treat `promote` as the only release-ready state.
14. Treat `hold` as a remediation queue.
15. Treat `block` as a source or assurance integrity failure.

The preserved older downloaded artifact is a negative compatibility fixture. It must remain rejected until a separately implemented migration contract exists. The demo therefore reports the compatibility boundary instead of pretending that the old data is equivalent to the current ledger.

## 18. Demonstration output checklist

For a ready current-format ledger, a reviewer should see:

- a typed source ledger loaded successfully;
- fourteen assurance findings;
- zero blocker findings;
- zero warning findings;
- ten gate checks;
- all required checks passing;
- gate state `promote`;
- a non-empty ledger address;
- a non-empty assurance address;
- a non-empty gate address;
- a non-empty bundle address;
- deterministic JSON bytes;
- fixed CSV headers;
- a Markdown summary with remediation columns;
- no local input path;
- no private identity fields;
- no execution-language metadata.

For a held ledger, the reviewer should see:

- source structure still valid;
- closure or readiness warning visible;
- gate state `hold`;
- required integrity checks still passing;
- remediation text that identifies the open state;
- no promotion exit status.

For a blocked ledger, the reviewer should see:

- the failing required finding or check;
- a blocker state;
- evidence address for the failure;
- a remediation instruction;
- gate state `block`;
- no attempt to auto-repair or auto-promote.

## 19. Review record template

Use this template when recording a downloaded-data demonstration.

```text
source_format: current release-registry federation gate review decision ledger
source_directory: omitted from public record
source_ledger_address: <content address>
assurance_address: <content address>
gate_address: <content address>
bundle_address: <content address>
finding_count: <integer>
passed_findings: <integer>
warning_findings: <integer>
blocker_findings: <integer>
check_count: <integer>
passed_checks: <integer>
warning_checks: <integer>
blocker_checks: <integer>
assurance_state: passed|warning|blocked
gate_state: promote|hold|block
release_ready: true|false
legacy_compatibility: accepted|rejected
public_boundary: passed|failed
diff_state: unchanged|changed|not-run
```

Do not include the local source directory in a public record. The address graph is the portable evidence reference.

## 20. Maintainer extension rules

When adding a new assurance finding:

- append it only when ordinal compatibility is preserved or a new contract version is declared;
- specify its plane, severity, requiredness, and evidence policy;
- add a positive fixture;
- add at least one targeted failure injection;
- add mapping and persistence coverage;
- add JSON, CSV, and Markdown coverage if it is public;
- add API and CLI coverage if it is exposed;
- add a public-boundary assertion;
- add a deterministic address assertion;
- update the matrix and runbook;
- update capabilities and roadmap inventory;
- update the focused workflow command if a new check needs a separate gate.

When changing a gate check:

- document whether the check is required or optional;
- preserve the meaning of promote, hold, and block;
- test ready, held, and blocked fixtures;
- test a changed-source diff;
- verify exit statuses;
- verify the API state mapping;
- verify that warning checks cannot silently become promotion success.

When changing persistence:

- preserve exact file allowlisting;
- preserve canonical bytes;
- verify manifest sizes and addresses;
- reject symlinks and extras;
- test a round trip from bytes;
- test a tampered artifact;
- test a tampered manifest;
- test old-format rejection.

## 21. Release sign-off matrix

| Sign-off question | Evidence | Pass condition |
| --- | --- | --- |
| Is the source current-format? | source loader result | typed load succeeds |
| Is the source address valid? | ledger-address finding | passed |
| Is the source contract valid? | ledger-contract finding | passed |
| Are item addresses valid? | item-addresses finding | passed |
| Is the entry chain valid? | entry-chain finding | passed |
| Are actions linked to items? | entry-item-linkage finding | passed |
| Do counters reconcile? | action-counters finding | passed |
| Is evidence permitted? | evidence-policy finding | passed |
| Are transitions allowed? | transition-policy finding | passed |
| Does replay reproduce? | replay-projection finding | passed |
| Does source authority hold? | source-authority finding | passed |
| Is public output clean? | public-boundary finding | passed |
| Do replay addresses reproduce? | replay-addresses finding | passed |
| Is assurance accepted? | assurance-accepted check | passed |
| Is assurance warning-free? | assurance-release-ready check | passed |
| Is the source accepted? | source-accepted check | passed |
| Are blocked items absent? | no-blocked-items check | passed |
| Is the head continuous? | head-continuity check | passed |
| Is the gate projection safe? | public-boundary check | passed |
| Does the gate promote? | gate state | `promote` |

Any required sign-off failure stops release. Optional warnings must be recorded and resolved before a promote decision.

## 22. Minimal operator run

The smallest useful run still preserves the whole assurance boundary:

1. Load the current-format downloaded ledger.
2. Build the assurance gate bundle.
3. Verify the bundle.
4. Print the summary.
5. Persist the exact package.
6. Reload the package.
7. Query failed findings.
8. Query non-passing checks.
9. Return the gate state.

The demo script implements this sequence while allowing the source directory and destination directory to be supplied by the operator. It does not require a network service, remote identity, private metadata, or a legacy repository.

## 23. Deep run for release review

For a full review, add these steps:

- run the source ledger verifier before assurance;
- record the source ledger address;
- build with a stable assurance identifier;
- compare repeated build bytes;
- inspect all fourteen findings;
- inspect all ten checks;
- query each plane separately;
- query required failures;
- render CSV for tabular review;
- render Markdown for sign-off;
- write and reload the exact package;
- verify package file sizes;
- verify package file addresses;
- compare against a prior baseline;
- query changes by action;
- inject a harmless test mutation in a disposable copy;
- confirm the expected finding fails;
- discard the disposable copy;
- rerun the clean build;
- record the final promote, hold, or block state.

This sequence separates clean evidence from negative testing. A failure-injection copy must never be confused with the source download used for a release decision.

## 24. Compatibility boundary

The assurance module accepts only the current review decision ledger contract. Compatibility is evaluated explicitly:

- current version and current boundary are accepted;
- missing current fields are rejected;
- unknown fields are rejected;
- old packet registry shapes are rejected;
- old federation gate shapes are rejected;
- local path-bearing records are rejected from public projection;
- ambiguous state names are rejected;
- unaddressed nested collections are rejected;
- unverified manifests are rejected.

This behavior is intentional. Data may be used as input when it is a current-format ledger or when a future migration module explicitly converts it. Data is not silently treated as equivalent merely because it is nearby on disk or has a similar name.

## 25. Completion criteria

The assurance module is ready for the next build wave when all of the following remain true:

- the focused assurance suite passes;
- the public-surface audit passes;
- lint passes for the new source, tests, and demo;
- compilation passes;
- diff check passes;
- the demo runs on a current-format persisted ledger;
- the preserved old downloaded artifact is rejected;
- the exact persistence package reloads;
- a same-snapshot diff is unchanged;
- a changed-snapshot diff is classified;
- API schemas and capabilities are available;
- CLI schema and capability commands are available;
- GitHub Actions includes the focused contract commands;
- public projections contain no local path, private identity, or execution-language attributes;
- the build is committed directly to the repository’s `main` branch.

This catalog is part of the module’s durable review surface. It should be updated whenever the assurance contract, release gate, persistence shape, or public interface changes.
