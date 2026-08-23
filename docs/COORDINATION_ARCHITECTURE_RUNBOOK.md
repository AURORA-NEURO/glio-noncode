# D16 coordination runbook

The executable runbook is generated from the 20 runtime stages. Each step
retains an ordinal, action, required stage receipt, and stop condition. The
runbook is accepted only when all steps are present and contiguous.

## Stop conditions

Stop the run when any of these occurs:

- public source or fixture audit fails;
- a dependency is missing or cyclic;
- the budget schedule exceeds capacity;
- a tool requests network access or fails aggregate scope;
- a private key-shaped payload field is observed;
- a policy, security, integrity, or release check fails;
- a held control is about to be promoted automatically.

The stop decision is retained as a state and issue code. No fallback route
overrides a stop condition.

## Stage procedure

1. Load the checked-in public fixture and verify its address.
2. Audit HTTPS source receipts and public scope.
3. Compile dependency edges and detect cycles.
4. Register one deterministic typed tool per operation.
5. Schedule 168 units within the 192-unit capacity.
6. Execute all 64 positive/control cases.
7. Admit positive tools in the local sandbox.
8. Apply claim, context, network, and scope policy.
9. Route all 48 controls to review.
10. Append all 64 events to the addressed ledger.
11. Resolve bounded compute profiles.
12. Resolve public reference receipts.
13. Inspect exact-context drift observations.
14. Apply security decisions to positive projections.
15. Materialize five offline artifacts.
16. Create 16 public aggregate assignments.
17. Apply release and rollback gates.
18. Verify the event ledger.
19. Verify that controls remain held.
20. Finalize the runtime and content address.

## Operator handoff

The operator receives the runtime JSON, quality report, depth report, runbook,
trace, review CSV, and failure report. Reviewers work only from the held-control
queue and its required evidence classes. A later resolution is a new addressed
artifact, never an in-place mutation of this run.
