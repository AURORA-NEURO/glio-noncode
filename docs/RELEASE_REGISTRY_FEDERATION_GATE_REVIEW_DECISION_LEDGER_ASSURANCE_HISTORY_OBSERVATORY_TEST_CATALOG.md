# Assurance-history observatory test catalog

The observatory suite is a contract suite, not only a happy-path unit suite.
It exercises typed construction, derived projections, persistence, query
windows, operator adapters, and public-boundary rules. Every test should
remain deterministic and path-independent in its asserted public output.

## Construction and state coverage

| ID | Scenario | Expected assertion |
| --- | --- | --- |
| O-001 | Build zero histories. | Explicit `empty`, non-accepted, non-ready observatory. |
| O-002 | Build two accepted ready histories. | `ready`, all members ready, promoted verification. |
| O-003 | Build one held history. | `held`, non-ready verification. |
| O-004 | Build one blocked history. | `blocked`, blocking verification. |
| O-005 | Mix empty and ready histories. | `mixed`, empty count conserved, no promotion. |
| O-006 | Supply histories in reverse order. | Members are canonically sorted by member ID. |
| O-007 | Supply explicit member IDs. | IDs are retained and affect only the aggregate identity graph. |
| O-008 | Repeat equal build. | Complete typed dictionaries and JSON are identical. |
| O-009 | Change observatory ID. | Member history addresses remain unchanged; aggregate address changes. |
| O-010 | Add a duplicate member ID. | Construction rejects the ambiguous source set. |
| O-011 | Add a duplicate history graph. | Construction rejects double-counted source evidence. |
| O-012 | Use a plain mapping as a history. | Typed boundary rejects the value. |

## Derived member and aggregate checks

| ID | Scenario | Expected assertion |
| --- | --- | --- |
| O-020 | History has two entries with a regression. | Member transition counter and terminal transition are correct. |
| O-021 | Sum member entry counts. | Equals aggregate entry count. |
| O-022 | Sum transition counters. | Equals each aggregate transition counter. |
| O-023 | Sum gate counters. | Equals each aggregate gate counter. |
| O-024 | Sum finding counters. | Passed, warning, blocker, and total counts conserve. |
| O-025 | Sum check counters. | Passed, warning, blocker, and total counts conserve. |
| O-026 | Fold member terminal state. | Equals the aggregate state vocabulary. |
| O-027 | Fold accepted flags. | Acceptance is conjunctive and requires a non-empty set. |
| O-028 | Fold readiness flags. | Readiness is conjunctive and requires aggregate ready state. |
| O-029 | Recompute member address. | Stored member address matches the canonical hash. |
| O-030 | Recompute aggregate address. | Stored observatory address matches the canonical hash. |
| O-031 | Insert forbidden public key. | Recursive public-boundary check rejects it. |
| O-032 | Insert a local path in public text. | Recursive public-boundary check rejects it. |

## Independent verification coverage

| ID | Scenario | Expected assertion |
| --- | --- | --- |
| O-040 | Build verification for ready aggregate. | Eight required checks pass and state is `promote`. |
| O-041 | Build verification for held aggregate. | Checks pass; state is `hold`; release-ready is false. |
| O-042 | Build verification for blocked aggregate. | Checks pass; state is `block`; release-ready is false. |
| O-043 | Change verification passed count. | Verification mapping rejects non-conservation. |
| O-044 | Change check address. | Verification mapping rejects address drift. |
| O-045 | Change verification observatory address. | Package linkage rejects the result. |
| O-046 | Change verification state only. | Reproducibility check rejects the result. |
| O-047 | Verify against original histories. | Independent recomputation returns the same object. |
| O-048 | Verify against a changed history. | Independent recomputation raises `ValidationError`. |

## Diff coverage

| ID | Scenario | Expected assertion |
| --- | --- | --- |
| O-060 | Diff identical observatories. | All members are `unchanged`; overall direction unchanged. |
| O-061 | Add a ready member. | Item is `added` and direction improved. |
| O-062 | Remove a member. | Item is `removed` and direction regressed. |
| O-063 | Change ready to held. | Item is `changed` and direction regressed. |
| O-064 | Change snapshot detail with equal quality. | Item is `changed` and direction mixed. |
| O-065 | Compare mixed change set. | Overall state retains mixed direction where required. |
| O-066 | Round-trip diff mapping. | Complete item and aggregate dictionaries match. |
| O-067 | Verify diff against both sources. | Independent recomputation matches. |
| O-068 | Tamper diff item address. | Verifier rejects the item. |
| O-069 | Supply plain mappings to diff builder. | Typed boundary rejects the inputs. |

## Query and renderer coverage

| ID | Scenario | Expected assertion |
| --- | --- | --- |
| O-080 | Query summary. | One addressed record is returned. |
| O-081 | Query all members. | Total and returned counts are bounded and conserved. |
| O-082 | Query ready members. | Only ready state records are returned. |
| O-083 | Query held members. | Only held state records are returned. |
| O-084 | Query blocked members. | Only blocked state records are returned. |
| O-085 | Query empty members. | Only empty records are returned. |
| O-086 | Query accepted and rejected. | Boolean filters match the member projection. |
| O-087 | Query latest transition. | Transition filter matches terminal entry state. |
| O-088 | Query text. | Search is case-insensitive over canonical member text. |
| O-089 | Query with limit one. | Returned window contains at most one record. |
| O-090 | Query with zero limit. | Query constructor rejects the window. |
| O-091 | Query unsupported resource. | Query constructor rejects the vocabulary. |
| O-092 | Render JSON. | Canonical public JSON is stable. |
| O-093 | Render CSV. | Fixed columns are present and deterministic. |
| O-094 | Render Markdown. | Report contains the declared title and records. |
| O-095 | Query diff added items. | Action filter selects only added items. |
| O-096 | Query diff regressions. | Direction filter selects only regressions. |
| O-097 | Query diff state. | Baseline or candidate state filter is honored. |
| O-098 | Query verification checks. | Summary, checks, failed, required, and optional resources are bounded. |
| O-099 | Filter verification checks. | Severity, pass-state, text, offset, and limit filters compose deterministically. |

## Persistence coverage

| ID | Scenario | Expected assertion |
| --- | --- | --- |
| O-100 | Write and load package. | Exactly five files and identical typed graph. |
| O-101 | Write same package twice. | All file bytes are identical. |
| O-102 | Write over existing package without flag. | Writer rejects replacement. |
| O-103 | Write over exact package with flag. | Replacement succeeds. |
| O-104 | Add extra file. | Loader rejects exact-file violation. |
| O-105 | Replace a regular file with symlink. | Loader rejects symlink boundary. |
| O-106 | Reformat valid JSON. | Loader rejects non-canonical bytes. |
| O-107 | Change manifest identity. | Loader rejects manifest drift. |
| O-108 | Change metrics total. | Loader rejects non-reproducible metrics. |
| O-109 | Change verification count. | Loader rejects non-reproducible verification. |
| O-110 | Write and load diff. | Exactly two files and identical diff graph. |
| O-111 | Add diff extra file. | Diff loader rejects exact-file violation. |
| O-112 | Load legacy history shape as observatory input. | Loader rejects incompatible package. |

## CLI, HTTP, demo, and CI coverage

| ID | Scenario | Expected assertion |
| --- | --- | --- |
| O-120 | CLI capabilities. | Exact files, limits, resources, and features are emitted. |
| O-121 | CLI schema. | Closed JSON schema is emitted. |
| O-122 | CLI build. | Current history directories produce a package. |
| O-123 | CLI verify. | Promotion returns zero; hold returns two. |
| O-124 | CLI query. | Member records are emitted in the selected format. |
| O-125 | CLI diff and diff verify. | Diff package and summary are emitted. |
| O-126 | HTTP schema routes. | Every documented schema returns `200`. |
| O-127 | HTTP build. | Repeated history and member values are aligned. |
| O-128 | HTTP verify and query. | Exact package is loaded and queried. |
| O-129 | HTTP diff. | Baseline/candidate package comparison is persisted. |
| O-130 | Real downloaded history. | Current persisted downloaded output is accepted. |
| O-131 | Demo report. | Report contains no local path or attribution metadata. |
| O-132 | Actions workflow. | Compile, focused tests, upstream tests, and capability command are registered. |
| O-133 | HTTP verification query. | Verification check resources and filters return addressed windows. |

## Archive and transfer coverage

| ID | Scenario | Expected assertion |
| --- | --- | --- |
| O-140 | Build an archive from a verified directory. | Exact six-member ZIP preserves all five observatory payload files. |
| O-141 | Build archive in memory and from disk. | Public projections and deterministic bytes match. |
| O-142 | Load archive bytes. | Byte loader returns the same verified address as file loading. |
| O-143 | Inspect archive manifest. | Canonical manifest links archive and manifest addresses. |
| O-144 | Tamper archive member bytes. | Archive loader rejects receipt drift. |
| O-145 | Add an archive member or comment. | Exact ZIP shape rejects the envelope. |
| O-146 | Extract archive. | Exact observatory package is rehydrated and independently verified. |
| O-147 | Build an archive transfer. | Contiguous bounded chunk receipts conserve archive bytes. |
| O-148 | Change chunk policy. | Transfer address changes while archive address remains stable. |
| O-149 | Assemble explicit chunk parts. | Nested archive verifier returns the original archive address. |
| O-150 | Remove or alter a transfer chunk. | Transfer loader rejects missing or changed bytes. |
| O-151 | Load a manifest-only transfer mapping. | Public inventory works; complete assembly is unavailable. |
| O-152 | Query summary, chunks, and missing. | Bounded addressed windows preserve deterministic records. |
| O-153 | Write and reload exact transfer directory. | Manifest, chunk names, hashes, and archive bytes round-trip. |
| O-154 | CLI archive and transfer operations. | Build, verify, manifest, query, schema, and capability commands work. |
| O-155 | HTTP archive and transfer routes. | Build, verification, manifest, query, and schema routes return expected outputs. |
| O-156 | Downloaded-data transfer demo. | A current-format downloaded archive is chunked, reloaded, and queried. |
| O-157 | Incremental out-of-order chunk assembly. | Idempotent receipt ingestion exposes missing indices and conserved bytes. |
| O-158 | Conflicting duplicate chunk. | Assembler rejects a different byte sequence for an already received index. |
| O-159 | Incomplete finalization. | Assembler refuses to produce archive bytes while any chunk is missing. |
| O-160 | Progress query and schema. | Complete and manifest-only transfers expose addressed progress projections. |
| O-161 | Audit complete transfer. | Eight independent checks pass and the report is complete. |
| O-162 | Audit partial transfer. | Valid incomplete state exposes deferred nested verification and missing progress. |
| O-163 | Tamper audit check. | Changed check address, count, state, or completion linkage is rejected. |
| O-164 | Persisted partial recovery. | A partial directory reloads, resumes, and finalizes to the original archive bytes. |

## Completion rule

The observatory boundary is not considered complete until the focused suite,
upstream history suite, public-surface audit, and Actions contract all pass.
A successful in-memory build without exact persistence, negative controls, and
downloaded-data coverage is insufficient for a release handoff.
