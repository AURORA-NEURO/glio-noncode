# Structural architecture bundle format

The bundle writer creates six sibling files in an output directory. The files
are offline-capable and can be inspected without a service or database.

| File | Media type | Content |
| --- | --- | --- |
| `fixture.json` | `application/json` | versioned sources, operation specs, and cases |
| `evaluation.json` | `application/json` | sanitized case receipts and checks |
| `lineage.json` | `application/json` | hash-linked case ledger |
| `review.csv` | `text/csv` | case-level review view without raw payload |
| `release.md` | `text/markdown` | human-readable artifact receipt |
| `release.json` | `application/json` | state, checks, artifact addresses, rollback key |

## Address rules

Source and adapter output addresses use the canonical `sha256:` form. The
fixture, operation, case checks, stage receipts, and release checks are also
content-addressed. Canonical JSON uses sorted keys and compact hashing rules;
human-readable formatting does not alter the underlying address input.

The ledger begins at a fixture root address. Each event records its case input
address, adapter output address, previous event address, state, and its own
event address. The chain is accepted only when sequence numbers are
contiguous and every case appears exactly once.

## Review CSV columns

`review.csv` contains exactly these columns:

```text
case_id,operation_id,expected_state,observed_state,result_state,issue_codes,passed
```

There are no raw records, sequences, allele strings, graph sequences, or
subject-level identifiers in this view.

## Release receipt

`release.json` includes a release state, six artifact records, release checks,
and a rollback key derived from the fixture and artifact addresses. A release
is `published` only when all checks pass. The rollback key is a recoverable
pointer for replacing a release directory; it is not a claim about biological
validity.
