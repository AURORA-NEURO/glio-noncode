# D16 Platform Execution Architecture

## Purpose

D16 defines the platform, control, and deployment boundary for GLIO-NONCODE. It
turns public aggregate execution evidence into typed, replayable, release-gated
records. It does not make efficacy, causal, or clinical decisions. It records
what a bounded execution surface accepts, rejects, holds, routes, or publishes.

The module is a fresh integration surface. Its source joins are explicit and
its receipts retain delegate fixture identifiers, delegate record identifiers,
source addresses, context keys, output addresses, state values, and issue codes.
No private subject records are required for the D16 fixture.

## Scope and inventory

| Dimension | D16 contract |
| --- | ---: |
| Public source registries | 19 |
| Capability operations | 16 |
| Cases | 64 |
| Cases per operation | 4 |
| Positive cases | 16 |
| Control cases | 48 |
| Evaluation checks | 458 |
| Ledger events | 80 |
| Projection artifacts | 6 |
| Runtime stages | 24 |
| Delegate families | 3 |
| Quality checks | 11 |

The four-case contract is stable for every operation: one positive path and
three controls. Controls preserve explicit outcomes such as abstention,
denial, hold, partial completion, context mismatch, capacity limits, and
release failure. A control is evidence about a boundary, not discarded noise.

## Family layout

### Platform control family: C01-C04

| Capability | Operation | Input contract | Output contract |
| --- | --- | --- | --- |
| GNC-D16-C01 | mission planner | mission request | mission plan |
| GNC-D16-C02 | workflow compiler | mission plan | workflow graph |
| GNC-D16-C03 | typed tool registry | workflow tool references | typed registry |
| GNC-D16-C04 | execution sandbox | admitted tool call | sandbox admission |

This family closes the front door to execution. The planner retains the
declared mission boundary. The compiler retains dependency order. The typed
registry requires a registered contract before a call can proceed. The sandbox
rejects direct identifiers and other calls that cannot be proven safe within
the declared public aggregate boundary.

### Quality control family: C05-C12

| Capability | Operation | Input contract | Output contract |
| --- | --- | --- | --- |
| GNC-D16-C05 | policy claim gate | claim and source policy | policy decision |
| GNC-D16-C06 | budget resource scheduler | budget and resource request | schedule decision |
| GNC-D16-C07 | deterministic fallback | failed execution candidates | fallback selection |
| GNC-D16-C08 | human review router | review items | review route |
| GNC-D16-C09 | execution ledger | execution events | ledger transition |
| GNC-D16-C10 | model registry | registry card | compatibility result |
| GNC-D16-C11 | data reference registry | data reference | compatibility result |
| GNC-D16-C12 | drift OOD monitor | metrics and declared domain | drift status |

This family makes control state durable. It bounds budget admission, retains
deterministic fallback behavior, routes review items with priority and reason,
closes append-only transitions, checks registry compatibility, checks reference
context, and distinguishes watch from drift and out-of-domain conditions.

### Deployment family: C13-C16

| Capability | Operation | Input contract | Output contract |
| --- | --- | --- | --- |
| GNC-D16-C13 | privacy security policy | access request | privacy decision |
| GNC-D16-C14 | local deployment bundle | release bundle | bundle admission |
| GNC-D16-C15 | federated execution | site execution request | federated status |
| GNC-D16-C16 | release rollback | release state | release disposition |

The deployment family keeps publication separate from execution. A bundle can
be held for digest or requirement failure. A federated path can be held for
site availability, privacy budget, or context support. Rollback can be denied
when integrity checks fail, a previous release is absent, or the current
version is already active.

## Typed contract surface

`platform_execution_architecture_contracts.py` contains the durable D16 data
model. The principal records are:

- `PlatformExecutionSource`: normalized public aggregate source receipt.
- `PlatformExecutionOperationSpec`: ordered operation, plane, contracts, and
  dependencies.
- `PlatformExecutionCase`: one positive or control case with safe payload,
  expected state, issue vocabulary, counts, and address.
- `PlatformExecutionFixture`: the complete 19-source, 16-operation, 64-case
  aggregate.
- `PlatformExecutionExecution`: observed delegate result.
- `PlatformExecutionReceipt`: expected-versus-observed closure for a case.
- `PlatformExecutionEvaluation`: 64 executions and 458 checks.
- `PlatformExecutionPlan`: dependency-safe operation graph.
- `PlatformExecutionReviewQueue`: held, denied, partial, and unresolved paths.
- `PlatformExecutionLedger`: 80 addressed append-only events.
- `PlatformExecutionArtifact`: six review-safe projections.
- `PlatformExecutionRelease`: publication state and limitations.
- `PlatformExecutionDepthReport`: counts for sources, operations, cases,
  checks, addresses, states, and issue codes.
- `PlatformExecutionQualityGate`: release and coordination closure.
- `PlatformExecutionRuntime`: complete 24-stage result.

Every durable record has a content address computed from normalized data. This
supports replay, comparison, and audit without depending on mutable filenames.
Input mappings are parsed through typed constructors, and schema validation
checks the exact fixture shape before a runtime can be accepted.

## Public aggregate normalization

The public data adapter reads three existing aggregate delegate fixtures:

1. Platform frontier C01-C04, five sources and sixteen records.
2. Control frontier C05-C12, nine sources and thirty-two records.
3. Deployment frontier C13-C16, five sources and sixteen records.

The adapter preserves delegate fixture and record identifiers while assigning
new D16 source, operation, case, check, output, and runtime addresses. Payload
normalization recursively strips restricted identity and decision fields. The
delegate context remains visible so an out-of-domain result can be explicit.
The aggregate context is `multi_context_public_aggregate`, while the reserved
control label is `foreign_context_control`.

The adapter is deterministic: cached family loading returns the same source
and record order, operation ordinals are contiguous from one through sixteen,
and case identifiers are derived from operation and scenario. The pinned JSON
fixture is emitted by the CLI and checked back through `from_file`.

## Evaluation depth

Each case receives seven checks:

1. observed state equals expected state;
2. observed issue codes equal expected issue codes;
3. bounded counts equal the expected count record;
4. operation join resolves;
5. source joins resolve;
6. delegate context is exact or mismatch is explicit;
7. receipt is addressed and passed.

Ten global checks then close fixture count, positive balance, control balance,
family balance, operation balance, source coverage, state coverage, output
addresses, context controls, and receipt coverage. The arithmetic is
`64 * 7 + 10 = 458`.

The evaluation keeps all 64 receipts even when the state is held, denied,
partial, or out of domain. This gives later review and release stages the
complete control surface rather than a success-only view.

## Runtime stages

The runtime executes these stages in order:

1. fixture-loaded
2. sources-audited
3. schema-validated
4. plan-compiled
5. platform-family-ready
6. control-family-ready
7. deployment-family-ready
8. cross-plane-ready
9. cases-executed
10. review-routed
11. ledger-closed
12. metrics-materialized
13. replay-closed
14. artifacts-materialized
15. bundle-closed
16. release-built
17. quality-gated
18. depth-accounted
19. compliance-closed
20. controls-closed
21. coordination-closed
22. report-materialized
23. runtime-seeded
24. runtime-finalized

The cross-plane stage is materialized by the platform, quality, and deployment
family operation addresses. The coordination quality check also evaluates the
existing D16 coordination fixture and requires its 64 cases to close. This
keeps family boundaries independent while requiring their shared handoff to be
valid before publication.

## Quality and release rules

The quality gate requires:

- public aggregate audit accepted;
- dependency plan accepted;
- all 458 evaluation checks accepted;
- deterministic replay accepted;
- six artifacts safe and addressed;
- metric invariants empty;
- release derivation publishable;
- ledger closure accepted;
- at least twelve observed states;
- coordination closure accepted;
- at least twenty distinct issue controls.

Publication is derived only after evaluation, artifacts, quality, compliance,
and release checks close. The release record retains limitations and artifact
addresses. A held or denied path stays in the runtime and review projection;
it does not silently become a success.

## Compliance boundary

The D16 compliance scan walks every case payload recursively. It requires all
source receipts to be public aggregate, all cases to be addressed, and all
delegate contexts to be non-empty. Restricted identity and decision keys are
rejected. The compliance report is independently queryable and is included in
the runtime bundle.

## Exports and integration

`platform_execution_architecture_exports.py` is the stable module surface. The
root package re-exports the typed classes, constants, evaluators, reports,
runtime, query functions, and validators. The capability registry attaches the
three D16 implementation paths and the focused test modules to every D16
record. The CLI and Actions workflow exercise fixture, audit, plan, evaluation,
runtime, quality, depth, replay, report, scenario, source, compliance,
validation, query, and bundle commands.

## Verification targets

The expected accepted result is:

```text
sources=19 operations=16 cases=64 checks=458 artifacts=6 stages=24
quality=True release=published runtime=True
```

Focused tests cover fixture shape, delegate states, receipt depth, plan,
review, ledger, replay, metrics, release, stage order, compliance, matrix,
query, exports, CLI files, and report projections.
