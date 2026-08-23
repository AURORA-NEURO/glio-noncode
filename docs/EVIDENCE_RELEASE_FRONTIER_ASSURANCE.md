# Evidence release frontier assurance planes

The release runtime is intentionally wider than the four operation functions. A
research lifecycle transition is only useful when its provenance, review state,
replay behavior, output safety, and publication boundary can all be inspected.
The following planes are independent receipts rather than hidden side effects.

## Assurance planes

1. Data audit verifies that public source receipts, row counts, role balance, and
   URI schemes are declared before operation execution.
2. Source registry normalizes source identity, title, scope, URI, and address so a
   record can be joined to a public anchor without fetching it during a replay.
3. Schema validation checks required fields and nested collection shape before
   dispatch. It produces a rejected result for missing or malformed input.
4. Adapter dispatch maps exactly four operation values to four functions. Unknown
   work cannot fall through to a default operation.
5. Fixture evaluation compares observed states and issue codes to a positive/control
   contract and emits five checks per row.
6. Signature verification adds a separate check to the positive dossier path. A
   signed result is not considered published until its canonical payload verifies.
7. Metrics count states and issue codes without converting a count into a quality
   score or probability.
8. Lineage connects source IDs to records and record IDs to execution addresses.
9. Reconciliation compares expected and observed state values without deleting a
   mismatched row.
10. Quality gates stop the release when data, fixture, adapter, schema, or
    reconciliation checks fail.
11. Replay evaluates the same fixture twice and compares content addresses. This
    gives a local, deterministic reproducibility signal.
12. Reproducibility joins fixture, evaluation, replay, and lineage addresses into
    one packet that can be stored with a release.
13. Review views keep role, state, issue codes, and content address visible while
    omitting operation-only private values.
14. Review queues route `review`, `blocked`, and `rejected` rows. Terminal positive
    rows are not placed in the queue.
15. Review SLAs assign response bands based on explicit priority. There is no clock
    dependency in the receipt itself.
16. Review protocols turn issue codes into a repair-and-rerun instruction.
17. Handoff summaries preserve counts, queue identity, and blocked identity for the
    next reviewer.
18. Integrity recomputes address shape and identity closure for fixture records and
    executions.
19. Depth checks assert the expected 16 rows, four operations, five source
    receipts, 81 checks, and balanced roles.
20. Threshold probes exercise below, exact, and above score boundaries.
21. Scenario matrices reconcile every expected state to its observed state.
22. Control coverage requires a control set for every operation and confirms that
    control expectations replay successfully.
23. Validation matrices cover state, issue, role, integrity, and safety planes for
    all rows.
24. Evidence matrices retain source count, input address, output address, state,
    and closure for each execution.
25. Assurance combines quality, depth, and reconciliation without hiding a failed
    component behind an aggregate score.
26. Claim boundaries keep lifecycle wording separate from clinical, causal, or
    individual-outcome wording.
27. Failure injection exercises malformed input, empty chain, empty bundle, and
    wrong-signature paths.
28. Recovery plans map every observed state to an action. Blocked rows are
    quarantined; they are never auto-promoted.
29. Performance and resource receipts make fixture size and check volume explicit.
30. Compliance checks ensure aggregate-only scope and HTTPS source receipts.
31. Diagnostics provide severity and issue code views for operations staff.
32. Queries, partitions, and views give deterministic access patterns for review.
33. Execution plans and provenance join the stage order to a run ID and policy
    address.
34. Freshness and compatibility verify declared versions without relying on a
    mutable external service.
35. Release checks re-evaluate quality, integrity, and compatibility independently.
36. Runbooks, manifests, audit logs, transcripts, and traces make the ordered
    runtime inspectable after completion.
37. Summaries, data dictionaries, packages, bundles, and artifacts provide stable
    handoff forms for CI and public review.

## Generated assurance modules

The focused `evidence_release_frontier_*` modules also provide small, independently
addressable receipts for control catalogs, dossier verification, bundle
verification, supersession graph checks, reclassification policy, review metrics,
serialization profiles, fixture governance, signoff, runtime health, queue policy,
integrity repair, source lineage, safety projection, evidence requirements, change
impact, publication receipts, and review escalation. These modules use the same
canonical content-address format and can be composed without a shared mutable
registry.

## Review interpretation

An accepted runtime means the declared operational contract closed. It does not
mean that a source has been independently re-read, that a biological mechanism is
true, or that a research receipt is suitable for clinical decision-making. The
fixture is synthetic aggregate planning data linked to public portals. Its controls
are first-class evidence that the system preserves uncertainty and context
boundaries.
