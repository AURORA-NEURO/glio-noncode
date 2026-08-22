# Workspace frontier evidence gate

## Purpose

The Domain 15 C01–C04 frontier verifies four research-workspace surfaces:

1. case workspace construction;
2. cohort workspace construction;
3. single-variant detail resolution;
4. regulatory interval-track browsing.

The gate is a release-quality boundary around deterministic read models. It
does not claim clinical validity, diagnostic utility, treatment value, causal
activity, or performance at production scale. A passing gate means that the
declared fixture, typed primitives, state transitions, receipts, controls,
and exports agree with one another.

## Evidence boundary

The fixture is explicitly public and aggregate:

| Field | Value |
| --- | --- |
| Fixture ID | `workspace-frontier-public-aggregate` |
| Fixture version | `2026.08.d15-c01-c04.v1` |
| Boundary | `public_aggregate_non_patient` |
| Context | `GRCh38|glioma|adult|stem_like|core|untreated` |
| Sources | 5 HTTPS receipts |
| Records | 16 |
| Positive rows | 4 |
| Control rows | 12 |
| Operations | 4 |

No row contains a person identifier, clinical report, treatment decision, or
individual-level measurement. The subject and sample labels are aggregate
placeholders used only to exercise typed input contracts.

## Gate layers

The evidence gate has the following layers.

### Layer 1: fixture identity

The fixture version is stable and content addressed. Every source receipt has
an HTTPS URI, a title, an access note, and a SHA-256 content address. Every
record names one or more source IDs. Record IDs are unique and operations are
covered exactly once by a positive row and three control rows.

### Layer 2: typed execution

The evaluator calls the existing workspace primitives rather than copying
their behavior into a fixture-only simulation. Case records pass through
`CaseManifest` and `CaseWorkspaceBuilder`. Cohort records pass through
`CohortQuery`, `CohortQueryBuilder`, `CohortDiscoveryEvidenceBuilder`, and
`CohortWorkspaceBuilder`. Variant records pass through `VariantExplorer`.
Track records pass through `RegulatoryTrackParser` and
`RegulatoryTrackBrowser`.

Each execution retains:

- operation identity;
- positive or control role;
- state;
- issue codes;
- surface output;
- content address.

### Layer 3: control separation

Controls are expected to fail, abstain, or remain outside the requested
context. A control is never accepted merely because its observed state equals
the fixture expectation. Acceptance requires both the expected state and the
expected issue set, and only positive rows can become accepted executions.

This prevents a malformed or out-of-domain row from being promoted by an
overly broad state matcher.

### Layer 4: context protection

The exact context key is transported through fixture records, model objects,
workspace records, search requests, detail requests, and release metadata.
When a requested context does not equal the workspace context, the result is
`out_of_domain` and no records are returned as if they were applicable.

Context protection is checked for:

- case manifests from a different age group;
- cohort records available only in another context;
- variant detail requests with a mismatched context;
- regulatory tracks whose requested context differs from the fixture.

### Layer 5: state accounting

The gate preserves the distinction between:

| State | Meaning in this frontier |
| --- | --- |
| `supported` | The bounded surface can render the declared fixture path. |
| `partial` | A surface renders while an explicit limitation remains. |
| `absent` | The requested selection has no matching records. |
| `abstained` | The requested identity is not present and is not inferred. |
| `out_of_domain` | The request does not match the exact context. |
| `invalid` | The input violates a typed construction contract. |

The gate does not collapse these states into a Boolean success value.

## Positive paths

### Case workspace

The positive case contains two canonical variants and one candidate regulatory
element. It exposes five sections: variants, regulatory elements, hypotheses,
evidence, and validation. The optional dossier is intentionally absent, so the
workspace remains `partial` and carries `missing_dossier`.

The positive check set covers:

- case identity;
- exact context;
- two variant rows;
- one element row;
- five section IDs;
- deterministic facets;
- bounded page output;
- keyboard order;
- visible labels;
- focus boundary;
- input content address.

### Cohort workspace

The positive cohort contains two selected callable records. The workspace
keeps selected records, background summary, and controls in distinct sections
even when the latter are empty. Query accounting reports zero exclusions and
two selected records. The result is `supported` and retains row labels for a
future renderer.

### Variant explorer

The positive detail request resolves `v-frontier-1`. The result contains the
canonical variant record and an empty relationship list because no related
record was declared. Empty relationships are meaningful: the explorer does
not infer a relationship from coordinate proximity, labels, or shared tags.

### Regulatory track browser

The positive track contains two BED intervals. The parser retains source ID,
genome build, row identity, raw row hash, normalized coordinates, and feature
attributes. The browser returns `chr7:100-120` and `chr7:181-230` coordinate
labels. Overlap is a navigation filter and is not a statement about activity.

## Control matrix

| ID | Surface | Control | Expected state | Issue |
| --- | --- | --- | --- | --- |
| C01-CTRL-001 | Case | different age context | out_of_domain | context_mismatch |
| C01-CTRL-002 | Case | no variants | invalid | invalid_workspace_input |
| C01-CTRL-003 | Case | duplicate variant ID | invalid | duplicate_variant_id |
| C02-CTRL-001 | Cohort | records in another context | out_of_domain | context_mismatch |
| C02-CTRL-002 | Cohort | record not callable | absent | no_matching_records |
| C02-CTRL-003 | Cohort | empty record set | absent | no_matching_records |
| C03-CTRL-001 | Variant | missing variant ID | abstained | variant_absent |
| C03-CTRL-002 | Variant | mismatched request context | out_of_domain | context_mismatch |
| C03-CTRL-003 | Variant | malformed case | invalid | invalid_workspace_input |
| C04-CTRL-001 | Track | invalid BED coordinate | partial | track_parse_issue |
| C04-CTRL-002 | Track | mismatched request context | out_of_domain | context_mismatch |
| C04-CTRL-003 | Track | empty input | invalid | invalid_track_input |

## Evaluation arithmetic

Each record receives seven checks:

1. observed state equals expected state;
2. observed issue codes equal expected issue codes;
3. role and acceptance agree;
4. operation identity is retained;
5. execution is content addressed;
6. record context equals fixture context;
7. output is retained.

Sixteen records produce 112 record checks. Eight global checks add:

- record count;
- source count;
- operation coverage;
- positive count;
- control count;
- issue vocabulary;
- execution addresses;
- public boundary.

The total is 120 checks. A release cannot skip a record because the evaluator
uses strict positional pairing between fixture rows and execution receipts.

## Quality gate

The quality gate has 14 checks:

| Check | Required result |
| --- | --- |
| fixture accepted | true |
| positive count | 4 |
| control count | 12 |
| contract count | 4 |
| issue vocabulary | non-empty |
| schema operation count | 4 |
| schema field addresses | all SHA-256 |
| lineage acyclic | true |
| lineage terminal count | 16 |
| reconciliation accepted | true |
| reconciliation item count | 16 |
| public boundary | exact boundary string |
| exact context | all records match |
| accessibility retention | labels remain in valid outputs |

The quality gate is independent of the review queue. A held row can be
correctly held while the release gate passes, because review visibility is a
required state rather than a failure of the fixture.

## Review interpretation

The policy allows only supported executions with no issue codes to become
research-navigation rows. In the default fixture, three rows are ready:

- the supported cohort workspace;
- the supported variant detail;
- the supported regulatory track.

The partial case workspace remains held because its dossier section is
incomplete. All controls remain held or withheld. A queue row contains source
IDs, operation, role, state, issues, priority, disposition, rationale, and a
content address.

## Release requirements

The release manifest requires:

- accepted bundle;
- accepted quality gate;
- stable replay;
- accepted runtime;
- exact public boundary;
- non-empty artifact addresses.

The manifest state is `ready` only when every check passes. The release state
does not alter the state of individual rows and does not erase review items.

## Reproducibility procedure

Run the following sequence from a clean checkout:

```powershell
glio-noncode workspace-frontier-data-audit
glio-noncode workspace-frontier-evaluate
glio-noncode workspace-frontier-replay
glio-noncode workspace-frontier-quality-gate
glio-noncode workspace-frontier-runtime
glio-noncode workspace-frontier-release
```

Then compare the two replay receipts produced from the same fixture. The
evaluation address and all 16 execution addresses must match. A change to a
fixture payload, model normalization, state mapping, or issue vocabulary must
change a content address and should receive a deliberate review.

## Non-goals

This gate does not certify:

- interactive graphical performance;
- screen-reader conformance in a browser;
- multi-user persistence;
- external usability studies;
- large-track rendering throughput;
- clinical interpretation;
- causal inference;
- treatment selection;
- individual privacy risk beyond the aggregate fixture boundary.

Those items remain explicit follow-on work in the partial capability ledger.
