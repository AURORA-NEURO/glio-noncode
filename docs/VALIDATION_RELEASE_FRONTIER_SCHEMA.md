# Validation-release frontier schema and state transitions

## Top-level fixture

```text
ValidationReleaseFixture
├── fixture_id: string
├── fixture_version: string
├── context_key: string
├── evidence_boundary: string
├── sources: tuple[ValidationReleaseSourceReceipt, ...]
├── records: tuple[ValidationReleaseRecord, ...]
└── content_address: sha256 string
```

Every source and record is addressed independently. The fixture address is
calculated over the complete normalized body, including source receipts and
record payloads. Loading a fixture requires version, identity, and address
agreement with the checked-in contract.

## Record contract

```text
ValidationReleaseRecord
├── record_id: string
├── operation: off_target_risk | value_of_information |
│              experiment_package | claim_update
├── role: positive | control
├── context_key: string
├── source_ids: tuple[string, ...]
├── payload: object
├── expected_state: bounded state
├── expected_issue_codes: tuple[string, ...]
├── notes: string
└── content_address: sha256 string
```

The evaluator never infers an expected state from an observed result. It
compares the operation result against the record declaration and emits the
difference as a failed check.

## Operation result

```text
ValidationReleaseOperationResult
├── operation: enum
├── state: ready | review | blocked | packaged | updated | rejected | abstained
├── issue_codes: sorted tuple[string, ...]
├── output: safe projection object
└── content_address: sha256 string
```

The safe projection is intentionally narrower than the input. C13 exposes
burden summaries, C14 exposes selected planning IDs and totals, C15 exposes
manifest IDs and file addresses, and C16 exposes updated/review IDs and result
counts. No projection contains credentials or raw participant rows.

## State transitions

| Input condition | Result state | Release meaning |
| --- | --- | --- |
| valid C13 row below thresholds | `ready` | planning row may enter research handoff |
| valid C14 row with one or more selected experiments | `ready` | plan is dependency-safe under budget |
| valid C15 row with non-empty experiment set and unique IDs | `packaged` | manifest is complete for review |
| valid C16 row with known claim, exact context, and receipt | `updated` | declared result update is recorded |
| low-budget C14 row | `review` | no eligible selection was made |
| threshold or dependency control | `review` or `blocked` | inspect before continuation |
| malformed input contract | `rejected` | repair input and replay |

States are not scientific labels. `ready` does not mean effective, `packaged`
does not mean authorized, and `updated` does not mean true.

## Evaluation checks

For each of 16 records, the evaluator emits:

1. state agreement;
2. expected issue-code coverage;
3. positive/control role boundary;
4. content-address presence; and
5. secret-marker-free safe output.

The check address includes the check ID, observed value, required value, and
detail. This makes a changed control or changed wording a visible release
delta.

## Runtime closure

The runtime's 50 stages are ordered so that source and schema checks precede
execution, execution precedes quality and release, and release precedes
packaging and observability. The runtime report retains every stage object and
all major projections rather than collapsing the system to one boolean.
