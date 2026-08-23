# Evidence release frontier checklist

## Data boundary

- [ ] Five public HTTPS source receipts are present.
- [ ] The fixture has 16 rows: four positive and twelve controls.
- [ ] Four operations are balanced at four rows each.
- [ ] All row source IDs resolve to declared receipts.
- [ ] No individual-level or credential-like fields are present.

## C13 reclassification

- [ ] The proposed tier differs from the previous tier.
- [ ] The evidence score meets the declared threshold.
- [ ] At least two independent reviewer IDs are present.
- [ ] At least two source IDs are present.
- [ ] Foreign context is blocked.

## C14 supersession

- [ ] Every target exists or the row stays in review.
- [ ] Self-links are blocked.
- [ ] Cycles are blocked.
- [ ] Prior records remain in the chain and are not deleted.

## C15 and C16 release

- [ ] Evidence, review, and release sections are all addressed.
- [ ] Duplicate section identity is held for review.
- [ ] Dossier audience and expiry are explicit.
- [ ] The signature is recomputed before publication.
- [ ] The public output contains no signing material.

## Runtime and CI

- [ ] Fixture evaluation passes with 81 checks.
- [ ] Replay content addresses match.
- [ ] Quality, integrity, depth, and release checks pass.
- [ ] Failure injection returns the declared rejected/review/blocked states.
- [ ] The review CSV is deterministic.

## Evidence retention

- [ ] Retain the fixture content address with every review note.
- [ ] Retain the evaluation address and the runtime run ID.
- [ ] Retain the source registry receipt and public URI scope.
- [ ] Retain the reconciliation result before signing a dossier.
- [ ] Retain the signature verification result separately from the signature input.
- [ ] Retain blocked controls; do not delete them from an export.
- [ ] Retain the release package manifest and artifact inventory.
- [ ] Retain the stage transcript and append-only audit log.
- [ ] Retain the schema version used for the run.
- [ ] Retain any change-control receipt that altered a fixture or threshold.

## Stop conditions

- [ ] Stop when the fixture identity does not match the checked-in address.
- [ ] Stop when source IDs do not resolve to declared HTTPS receipts.
- [ ] Stop when the positive/control ratio changes without a change receipt.
- [ ] Stop when replay produces a different evaluation address.
- [ ] Stop when a signature verifies against a different canonical payload.
- [ ] Stop when a context-mismatch row reaches a terminal publication state.
- [ ] Stop when a review or blocked row is absent from the handoff queue.
- [ ] Stop when an output contains a private field marker.

## Signoff

- [ ] The reviewer records the exact run ID.
- [ ] The reviewer records the fixture address.
- [ ] The reviewer records the release checks address.
- [ ] The reviewer records unresolved control rows.
- [ ] The reviewer records the public source scope.
- [ ] The reviewer records whether the dossier was verified.
- [ ] The reviewer confirms the artifact package is reproducible.
- [ ] The reviewer confirms the claim boundary remains intact.
