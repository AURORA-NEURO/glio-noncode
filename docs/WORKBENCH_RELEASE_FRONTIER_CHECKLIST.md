# Workbench release frontier checklist

## Data boundary

- [ ] Five public HTTPS source receipts are present.
- [ ] Sixteen rows contain four positives and twelve controls.
- [ ] Four operations are balanced at four rows each.
- [ ] Every row source ID resolves to a declared receipt.
- [ ] No individual-level or credential-like marker is present.

## C13 review form

- [ ] Required fields are complete on the positive path.
- [ ] Choice vocabulary is enforced.
- [ ] Missing fields remain review.
- [ ] Foreign context is blocked.

## C14 report export

- [ ] JSON, Markdown, and CSV-oriented formats are bounded.
- [ ] Section order is deterministic.
- [ ] Section IDs are unique.
- [ ] Empty reports remain review.

## C15 search

- [ ] Query matching is case-insensitive and deterministic.
- [ ] Identity and title matches score above ordinary fields.
- [ ] Command matches are explicit.
- [ ] No-match rows remain review.
- [ ] Malformed record identities are rejected.

## C16 accessibility

- [ ] Keyboard, labels, focus, contrast, motion, and reading order are declared.
- [ ] Every finding has severity and remediation text.
- [ ] Any failed criterion remains review.
- [ ] Foreign context is blocked.

## Release

- [ ] Evaluation passes 80 checks.
- [ ] Replay addresses match.
- [ ] Quality, integrity, depth, and evidence matrices pass.
- [ ] Review queue contains every held row.
- [ ] Failure injection returns declared states.
- [ ] CLI outputs and CSV headers are stable.
