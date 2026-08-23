# Evidence release frontier failure modes

| Failure | State | Required action |
| --- | --- | --- |
| low reclassification score | review | add evidence or change the proposal |
| fewer than two reviewers | review | obtain an independent review receipt |
| foreign context | blocked | quarantine; do not transport |
| missing supersession target | review | resolve the target or retain the old record |
| supersession cycle | blocked | break the chain with an adjudicated edit |
| missing bundle section | review | add the missing evidence, review, or release section |
| duplicate bundle identity | review | issue unique section IDs |
| expired dossier | review | regenerate the dossier within its declared window |
| signature mismatch | rejected | discard the receipt and sign the exact payload again |
| malformed input | rejected | repair the schema and rerun the row |

The recovery plan never auto-promotes a blocked or rejected row. A reviewer must
resolve the issue and replay the exact record. Replays are content addressed so an
operator can demonstrate which input and output were reviewed.

## Triage order

1. Confirm the fixture and schema addresses before interpreting any state.
2. Separate schema rejection from a valid control result.
3. Resolve context mismatch before checking scores or sources.
4. Resolve source and reviewer completeness before proposing a tier transition.
5. Resolve graph closure before publishing a supersession decision.
6. Resolve section identity and item addresses before assembling a bundle.
7. Resolve audience and expiry before inspecting a dossier signature.
8. Recompute the exact canonical payload before treating a signature mismatch as a
   key problem.
9. Rerun the single repaired record, then rerun the full fixture.
10. Compare the new release diff and obtain review signoff for any changed state.

Do not use a failure injection result as a replacement for a production review. It
is a deterministic rehearsal that proves the operation remains conservative when a
known failure shape is supplied.
