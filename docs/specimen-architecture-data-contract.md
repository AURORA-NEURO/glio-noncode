# D03 data and release contract

## Source receipts

Every source is represented by:

```text
source_id
title
uri
version
scope = public_aggregate
license
content_address = sha256:<digest>
```

The intake audit requires HTTPS URIs, unique source IDs, a public aggregate
scope, and a non-empty license statement. Source rows do not contain local
paths or subject-level identity.

## Case receipts

The architecture fixture separates declaration from execution. A declaration
contains:

```text
case_id
operation_id
capability_id
operation
scenario
context_key
source_ids
aggregate_identifier
payload
parameters
expected_state
expected_result_state
expected_issue_codes
expected_counts
content_address
```

The positive payload is the only declaration sent through a scientific
adapter. Controls use a bounded marker payload and are routed by policy. This
keeps malformed input and identity conflict tests executable without allowing
them to create an accidental domain result.

The release receipt contains:

```text
case_id
operation_id
expected_state
observed_state
expected_result_state
observed_result_state
expected_issue_codes
observed_issue_codes
expected_counts
observed_counts
passed
output_address
content_address
```

It does not contain raw payloads.

## Addressing

The fixture, operations, cases, receipts, review items, ledger events, runtime
stages, and release artifacts are all addressed. A content address is used for
identity and replay; it is not a location and does not grant access.

The lineage ledger begins at `sha256:genesis` and links 64 ordered events. An
event carries the case input address, receipt output address, previous event
address, and observed state. A broken previous link blocks the ledger.

## Artifact set

The release contains exactly six artifacts:

| Artifact | Media type | Rows |
| --- | --- | ---: |
| fixture | application/json | 64 cases |
| evaluation | application/json | 64 receipts |
| review | application/json | 48 items |
| lineage | application/json | 64 events |
| metrics | application/json | 16 operation metrics |
| release_notes | text/markdown | release summary |

Each artifact retains upstream addresses and uses versioned public-release
retention. Access policy permits JSON and Markdown only at this boundary.

## Scope review

The scope scanner rejects direct identity fields including patient IDs,
subject IDs, participant IDs, medical record numbers, date of birth, email,
phone, and street address. Aggregate mechanics labels such as synthetic
specimen or sample identifiers remain allowed because they are needed by the
existing typed fixture adapters and do not identify a person in this fixture.

## Failure semantics

An expected review control is not a failure. A positive case that fails its
receipt contract is a high-severity contract mismatch and blocks release. A
control whose expected policy result is not observed is a control-policy
mismatch and also blocks release. The failure report contains case IDs,
category, severity, disposition, detail, and address only.

## Replay semantics

Replay runs the same fixture twice and compares receipt projections, check
projections, and evaluation addresses. Any difference blocks publication.
Replay does not use network calls or mutable state.
