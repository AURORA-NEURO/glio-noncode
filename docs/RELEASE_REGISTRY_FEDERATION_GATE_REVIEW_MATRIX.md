# Review contract matrix

This appendix enumerates concrete contract cases for the release-registry federation gate review boundary. Each record is a small executable expectation represented in the focused regression suite or in the shared package verification helpers. The matrix is intentionally path-free and data-shape focused so it can be used with downloaded artifacts without exposing private source metadata.

## Input boundary

### I-001 — missing source directory
- Setup: exercise the missing source directory condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the loader returns a typed validation failure.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-002 — source path is a regular file
- Setup: exercise the source path is a regular file condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: directory admission fails before JSON parsing.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-003 — source package has an extra file
- Setup: exercise the source package has an extra file condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: exact-file verification rejects the package.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-004 — source manifest is missing
- Setup: exercise the source manifest is missing condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the source gate cannot be treated as verified.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-005 — source assurance document is missing
- Setup: exercise the source assurance document is missing condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: gate loading fails closed.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-006 — source gate document has non-canonical bytes
- Setup: exercise the source gate document has non-canonical bytes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the source loader rejects formatting drift.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-007 — source gate document byte changes
- Setup: exercise the source gate document byte changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the manifest receipt mismatch is surfaced.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-008 — source gate contains a symlink
- Setup: exercise the source gate contains a symlink condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the artifact is rejected as non-portable.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-009 — source gate has an unknown version
- Setup: exercise the source gate has an unknown version condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the review boundary does not coerce the contract.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-010 — source gate has an unknown boundary
- Setup: exercise the source gate has an unknown boundary condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: review construction stops at the boundary.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-011 — source gate has a changed gate address
- Setup: exercise the source gate has a changed gate address condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: nested address validation rejects the input.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-012 — source gate has a changed assurance address
- Setup: exercise the source gate has a changed assurance address condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: nested source linkage fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-013 — source gate has a changed runtime address
- Setup: exercise the source gate has a changed runtime address condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: runtime linkage fails before routing.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-014 — source gate has a changed federation address
- Setup: exercise the source gate has a changed federation address condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: federation linkage fails before routing.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-015 — source gate contains private metadata
- Setup: exercise the source gate contains private metadata condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: public projection validation rejects the input.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-016 — source gate contains an agent key
- Setup: exercise the source gate contains an agent key condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the public-boundary audit fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-017 — source gate contains a language key
- Setup: exercise the source gate contains a language key condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the public-boundary audit fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-018 — source gate contains a sample identifier
- Setup: exercise the source gate contains a sample identifier condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the public-boundary audit fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-019 — source gate has duplicate finding IDs
- Setup: exercise the source gate has duplicate finding IDs condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: item projection refuses ambiguous source identity.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-020 — source gate has duplicate check IDs
- Setup: exercise the source gate has duplicate check IDs condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: item projection refuses ambiguous source identity.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-021 — source gate has zero findings and zero checks
- Setup: exercise the source gate has zero findings and zero checks condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: review construction rejects an empty item set.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-022 — source gate finding order changes
- Setup: exercise the source gate finding order changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the new queue receives a new ordered snapshot.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-023 — source gate check order changes
- Setup: exercise the source gate check order changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the new queue receives a new ordered snapshot.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-024 — source gate uses an unsupported severity
- Setup: exercise the source gate uses an unsupported severity condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: severity validation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-025 — source gate uses an unsupported plane
- Setup: exercise the source gate uses an unsupported plane condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: plane validation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-026 — source gate failed item has no evidence reference
- Setup: exercise the source gate failed item has no evidence reference condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the source gate remains the authority for that condition.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-027 — source gate accepts a warning-only result
- Setup: exercise the source gate accepts a warning-only result condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: queue state becomes review rather than clear.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-028 — source gate rejects a required result
- Setup: exercise the source gate rejects a required result condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: queue state becomes blocked.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-029 — source gate is accepted and ready
- Setup: exercise the source gate is accepted and ready condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: queue state becomes clear.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-030 — legacy downloaded gate shape is supplied
- Setup: exercise the legacy downloaded gate shape is supplied condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the loader reports incompatibility instead of converting.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-031 — source gate directory is read-only
- Setup: exercise the source gate directory is read-only condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: review construction remains input-only.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### I-032 — source gate is loaded twice
- Setup: exercise the source gate is loaded twice condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the same public source address yields deterministic review output.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

## Queue verification

### Q-001 — finding projection omits one finding
- Setup: exercise the finding projection omits one finding condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: finding coverage verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-002 — check projection omits one check
- Setup: exercise the check projection omits one check condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: check coverage verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-003 — an item is routed twice
- Setup: exercise the an item is routed twice condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: source-scoped identity verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-004 — item ordinal skips a value
- Setup: exercise the item ordinal skips a value condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: contiguous-order verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-005 — item record type changes
- Setup: exercise the item record type changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: record-type verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-006 — item source ID changes
- Setup: exercise the item source ID changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: source linkage verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-007 — item source address changes
- Setup: exercise the item source address changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: source address verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-008 — item content address changes
- Setup: exercise the item content address changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: item address recomputation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-009 — passed item becomes open
- Setup: exercise the passed item becomes open condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: initial state verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-010 — warning item becomes clear
- Setup: exercise the warning item becomes clear condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: initial state verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-011 — blocker item becomes open
- Setup: exercise the blocker item becomes open condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: initial state verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-012 — warning priority becomes none
- Setup: exercise the warning priority becomes none condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: priority verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-013 — blocker priority becomes high
- Setup: exercise the blocker priority becomes high condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: priority verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-014 — queue item count changes
- Setup: exercise the queue item count changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: count conservation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-015 — queue failed count changes
- Setup: exercise the queue failed count changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: count conservation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-016 — queue blocker count changes
- Setup: exercise the queue blocker count changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: severity conservation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-017 — queue warning count changes
- Setup: exercise the queue warning count changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: severity conservation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-018 — queue state changes for a warning source
- Setup: exercise the queue state changes for a warning source condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: source-authority verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-019 — queue acceptance changes for a blocker source
- Setup: exercise the queue acceptance changes for a blocker source condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: source-authority verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-020 — queue release readiness changes
- Setup: exercise the queue release readiness changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: source-authority verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-021 — verification queue address points elsewhere
- Setup: exercise the verification queue address points elsewhere condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: bundle linkage verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-022 — verification gate address points elsewhere
- Setup: exercise the verification gate address points elsewhere condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: bundle linkage verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-023 — verification finding ordinal skips a value
- Setup: exercise the verification finding ordinal skips a value condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: verification order fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-024 — verification passed count changes
- Setup: exercise the verification passed count changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: verification count conservation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-025 — verification warning count changes
- Setup: exercise the verification warning count changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: verification severity conservation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-026 — verification state changes without findings
- Setup: exercise the verification state changes without findings condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: verification state recomputation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-027 — verification content address changes
- Setup: exercise the verification content address changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: verification address recomputation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-028 — queue public projection contains a path
- Setup: exercise the queue public projection contains a path condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: public-boundary verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-029 — queue query exceeds its limit
- Setup: exercise the queue query exceeds its limit condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: query result verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-030 — queue query offset is negative
- Setup: exercise the queue query offset is negative condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: query request validation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-031 — queue query filter is unknown
- Setup: exercise the queue query filter is unknown condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: query request validation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### Q-032 — queue is loaded after a clean round trip
- Setup: exercise the queue is loaded after a clean round trip condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: all queue checks pass with stable addresses.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

## Ledger decisions

### L-001 — ledger starts with no entries
- Setup: exercise the ledger starts with no entries condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: initial head and clear replay are explicit.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-002 — ledger starts from a held queue
- Setup: exercise the ledger starts from a held queue condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: source acceptance is retained and readiness is false.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-003 — ledger starts from a blocked queue
- Setup: exercise the ledger starts from a blocked queue condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: source acceptance and readiness remain false.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-004 — acknowledge targets one open item
- Setup: exercise the acknowledge targets one open item condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: replay state becomes acknowledged.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-005 — remediate targets an acknowledged item
- Setup: exercise the remediate targets an acknowledged item condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: replay state becomes resolved.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-006 — waive targets an acknowledged warning
- Setup: exercise the waive targets an acknowledged warning condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: replay state becomes waived.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-007 — escalate targets an open item
- Setup: exercise the escalate targets an open item condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: replay state becomes escalated.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-008 — reopen targets a resolved item
- Setup: exercise the reopen targets a resolved item condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: replay state becomes open.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-009 — reopen targets a waived item
- Setup: exercise the reopen targets a waived item condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: replay state becomes open.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-010 — remediate omits evidence
- Setup: exercise the remediate omits evidence condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the append fails closed.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-011 — waive omits evidence
- Setup: exercise the waive omits evidence condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the append fails closed.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-012 — acknowledge includes evidence
- Setup: exercise the acknowledge includes evidence condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the append fails closed.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-013 — critical blocker is waived
- Setup: exercise the critical blocker is waived condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the append fails closed.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-014 — action identifies no item
- Setup: exercise the action identifies no item condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the append fails closed.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-015 — action identifies two items
- Setup: exercise the action identifies two items condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the append fails closed.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-016 — item ID and address disagree
- Setup: exercise the item ID and address disagree condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the append fails closed.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-017 — unknown action is supplied
- Setup: exercise the unknown action is supplied condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: action vocabulary validation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-018 — invalid rationale is supplied
- Setup: exercise the invalid rationale is supplied condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: bounded text validation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-019 — expected head is absent
- Setup: exercise the expected head is absent condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: optimistic concurrency fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-020 — expected head is stale
- Setup: exercise the expected head is stale condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: optimistic concurrency fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-021 — entry predecessor changes
- Setup: exercise the entry predecessor changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: ledger ancestry verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-022 — entry decision address changes
- Setup: exercise the entry decision address changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: entry address verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-023 — replay item state changes
- Setup: exercise the replay item state changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: replay recomputation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-024 — ledger counter changes
- Setup: exercise the ledger counter changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: decision count conservation fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-025 — ledger head changes without an entry
- Setup: exercise the ledger head changes without an entry condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: head verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-026 — blocker is remediated with evidence
- Setup: exercise the blocker is remediated with evidence condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: item closes but source gate remains authoritative.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-027 — warning is resolved but another warning remains
- Setup: exercise the warning is resolved but another warning remains condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: ledger remains not release-ready.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-028 — all warnings are resolved
- Setup: exercise the all warnings are resolved condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: ledger can become release-ready only if source permits.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-029 — source gate is not accepted
- Setup: exercise the source gate is not accepted condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: ledger cannot become accepted through decisions.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-030 — ledger is written to an exact package
- Setup: exercise the ledger is written to an exact package condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: reload reconstructs the same replay.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-031 — ledger is queried by action
- Setup: exercise the ledger is queried by action condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: only matching entries are returned.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### L-032 — ledger is replayed twice
- Setup: exercise the ledger is replayed twice condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the same head and item states are produced.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

## Transport and comparison

### T-001 — queue destination is empty
- Setup: exercise the queue destination is empty condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: atomic package creation succeeds.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-002 — queue destination is non-empty
- Setup: exercise the queue destination is non-empty condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: write fails without explicit overwrite.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-003 — queue destination is overwritten explicitly
- Setup: exercise the queue destination is overwritten explicitly condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: new bytes are written and reload-verified.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-004 — queue manifest receipt changes
- Setup: exercise the queue manifest receipt changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: queue load fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-005 — queue split document changes
- Setup: exercise the queue split document changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: queue load fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-006 — ledger destination is empty
- Setup: exercise the ledger destination is empty condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: atomic package creation succeeds.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-007 — ledger destination is non-empty
- Setup: exercise the ledger destination is non-empty condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: write fails without explicit overwrite.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-008 — ledger entries document changes
- Setup: exercise the ledger entries document changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: ledger load fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-009 — ledger replay document changes
- Setup: exercise the ledger replay document changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: ledger load fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-010 — ledger manifest receipt changes
- Setup: exercise the ledger manifest receipt changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: ledger load fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-011 — diff destination is empty
- Setup: exercise the diff destination is empty condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: atomic diff creation succeeds.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-012 — diff destination is non-empty
- Setup: exercise the diff destination is non-empty condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: write fails without explicit overwrite.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-013 — diff document changes
- Setup: exercise the diff document changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: diff load fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-014 — diff manifest receipt changes
- Setup: exercise the diff manifest receipt changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: diff load fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-015 — baseline and candidate are identical
- Setup: exercise the baseline and candidate are identical condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: all rows are unchanged.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-016 — one item state improves
- Setup: exercise the one item state improves condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the row is changed and improved.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-017 — one item state regresses
- Setup: exercise the one item state regresses condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the row is changed and regressed.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-018 — candidate adds an item
- Setup: exercise the candidate adds an item condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the row is added.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-019 — candidate removes an item
- Setup: exercise the candidate removes an item condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the row is removed.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-020 — item ordinals shift
- Setup: exercise the item ordinals shift condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: stable item IDs prevent false changes.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-021 — diff item address changes
- Setup: exercise the diff item address changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: diff verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-022 — diff baseline address changes
- Setup: exercise the diff baseline address changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: diff verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-023 — diff candidate address changes
- Setup: exercise the diff candidate address changes condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: diff verification fails.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-024 — JSON export is requested
- Setup: exercise the JSON export is requested condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: canonical public JSON is returned.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-025 — CSV export is requested
- Setup: exercise the CSV export is requested condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: bounded rows and stable columns are returned.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-026 — Markdown export is requested
- Setup: exercise the Markdown export is requested condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: review-facing state and rows are rendered.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-027 — schema command is requested
- Setup: exercise the schema command is requested condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: closed schema JSON is returned.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-028 — capability command is requested
- Setup: exercise the capability command is requested condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: fixed actions and package files are returned.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-029 — HTTP queue route is requested
- Setup: exercise the HTTP queue route is requested condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the queue summary is returned.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-030 — HTTP ledger query is requested
- Setup: exercise the HTTP ledger query is requested condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: bounded ledger rows are returned.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-031 — HTTP append has a stale head
- Setup: exercise the HTTP append has a stale head condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the request returns a typed conflict failure.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

### T-032 — HTTP append writes a destination
- Setup: exercise the HTTP append writes a destination condition at the boundary named by this section.
- Assertion: verify the corresponding addressed projection, state, or failure contract.
- Expected: the next ledger package reloads successfully.
- Retention: keep the resulting public summary or typed validation outcome; do not retain private payloads.

## Matrix maintenance

- Add a new row when a public field, state transition, file, query resource, or API route gains a new invariant.
- Keep row identifiers stable so downstream reports can compare test coverage across build waves.
- Link each row to a focused test before marking the corresponding roadmap item complete.
- Preserve negative cases as first-class coverage; a held or blocked result is often the correct outcome.
- Re-run the full module test file after changing queue, ledger, replay, diff, CLI, or HTTP behavior.
