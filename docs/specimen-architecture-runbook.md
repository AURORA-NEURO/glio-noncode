# D03 runtime runbook

## Standard run

The runtime contains 24 ordered stages:

1. fixture-loaded
2. sources-audited
3. plan-compiled
4. policy-scored
5. ingestion-closed
6. context-family-ready
7. origin-family-ready
8. lineage-family-ready
9. preanalytic-family-ready
10. cases-executed
11. review-routed
12. lineage-linked
13. metrics-materialized
14. validation-matrix-closed
15. schema-closed
16. artifacts-materialized
17. access-closed
18. replay-closed
19. depth-accounted
20. compliance-closed
21. release-gated
22. quality-gated
23. observability-closed
24. runtime-finalized

Run the default fixture with:

```text
python -c "from glio_noncode.specimen_architecture_runtime import run_specimen_architecture; print(run_specimen_architecture().state)"
```

The expected final state is `published` when all gates pass.

## Gate order

Do not skip the gate order. The plan and policy reports must exist before
adapter execution; review and lineage must exist before artifacts; replay and
access must exist before release publication.

The release gate consumes:

- public source audit checks;
- the 458 evaluation checks;
- policy cardinality checks;
- 112 validation matrix cells;
- schema and access checks;
- replay checks;
- cross-module invariants;
- runbook and observability checks.

## Review queue

The queue has 48 held items. Priority 1 is identity conflict, priority 2 is
foreign context, and priority 3 is malformed input. Each item has a review ID,
case ID, operation ID, issue codes, disposition, next action, and address.

Review actions are deliberately descriptive:

- reconcile aggregate identity evidence;
- confirm reference context before replay;
- repair payload shape and replay.

## Troubleshooting

### Data audit fails

Inspect source URI, scope, content address, context key, operation join, and
the direct identity field list. A failed data audit should block the release
before adapter execution.

### Positive receipt fails

Compare expected result, observed result, issue codes, counts, and output
address. Re-run the family-specific fixture evaluator first, then re-run the
architecture evaluator. Do not loosen the architecture assertion to make a
fixture pass.

### Control receipt fails

Confirm the scenario and policy mapping. The expected mapping is context to
`out_of_domain`, malformed to `invalid`, and identity conflict to
`contradictory`. Controls must remain in `review` state.

### Replay fails

Compare the two evaluation addresses and the receipt projection. A replay
mismatch is a release blocker even if the second run appears reasonable.

### Ledger fails

Check the first event's `sha256:genesis` previous address and then walk each
sequence number. Every event must point to the previous event content address.

### Release fails

Keep the release blocked. Retain the artifact addresses, record failing check
IDs, and follow the rollback steps below.

## Rollback

1. mark the release state `blocked`;
2. retain all generated artifact addresses for audit;
3. restore the prior public manifest;
4. open a review item containing failing check IDs and the replay address.

Rollback does not delete the fixture, source receipts, or local artifacts.

## Verification checklist

- [ ] fixture has 15 or more sources;
- [ ] fixture has 16 operations and 64 cases;
- [ ] one positive and three controls exist per operation;
- [ ] evaluation has 64 passing receipts;
- [ ] validation matrix has 112 passing cells;
- [ ] review queue has 48 items;
- [ ] ledger has 64 linked events;
- [ ] artifacts count is six;
- [ ] replay addresses match;
- [ ] runtime has 24 stages;
- [ ] depth report is accepted at 100.0%;
- [ ] compliance report has eight passing checks;
- [ ] quality gate has twelve passing checks;
- [ ] final state is `published`.
