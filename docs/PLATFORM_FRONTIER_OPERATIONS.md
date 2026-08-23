# Platform frontier operations

This document defines the Domain 16 C01-C04 W1 runtime as an operational
platform surface. It is based on the typed primitives in the repository and
uses the attached product package only as a requirements reference. The
starter implementation in that package is not used as a code basis.

## Shared boundary

The fixture context is `public_platform|research|aggregate|local|v1` and the
evidence boundary is `public_aggregate_platform_runtime`. Every row carries a
stable ID, operation, positive/control role, source receipt IDs, expected
state, expected issue codes, and a SHA-256 content address.

The runtime accepts a positive row only if the observed state equals the
declared state and the issue tuple is empty. A control row is successful as a
control when it remains visible and non-positive. This prevents a denied
request from being counted as a successful platform path.

## C01 mission planner

The planner consumes an approved mission context and a tuple of requested role
IDs. It expands declared dependencies through the registry, applies the
mission claim ceiling, compiles the requested workflow, and returns a plan ID,
selected roles, selected tools, registry address, workflow ID, step IDs, and
warnings.

The positive row requests a dependency-complete pair of control roles. The
empty-request control abstains without compiling hidden work. The unknown-role
control rejects before any workflow is built. The claim-ceiling control uses a
role that requires a higher claim class and retains a rejection. These are
different states and are not collapsed into a generic error.

## C02 workflow compiler

The compiler converts typed steps into a topologically ordered DAG. Each step
retains kind, dependencies, resource envelope, optionality, determinism,
input contract, and output contract. The compiled result retains total CPU,
peak memory, storage, wall-clock budget, and warnings.

The cycle control is rejected by the depth-first cycle guard. The missing
dependency control is rejected before traversal. The warning control compiles
but is partial because network egress or nondeterminism requires review. A
warning does not become a silent failure, and a missing step does not become an
implicit dependency.

## C03 typed tool registry

The registry adapter resolves only contracts present in the validated
96-tool catalog. The descriptor projection exposes tool ID, name, input and
output contracts, safety class, determinism, egress, mutation scope, and
cardinality. It does not expose arbitrary callables.

The controls cover an unknown tool, an input contract mismatch, and a catalog
cardinality mismatch. Contract compatibility is metadata evidence: it does not
assert the scientific quality of a handler or model behind the contract.

## C04 execution sandbox

The sandbox wraps the policy-gated executor. Admission requires a registered
typed handler. Local isolation disables network egress by default, rejects
dynamic imports and external processes, and requires an explicit source list
when network is enabled. The executor retains policy, scheduler, provenance,
event IDs, review state, typed errors, and idempotent replay.

The positive row registers a local handler for a typed event-writing tool and
executes it through the control plane. The unregistered control is denied
before handler execution. The network control is denied by local isolation.
The sensitive control is rejected by the privacy policy without exposing the
raw sensitive value in the output projection.

## Runtime surfaces

The ordered runtime has 24 stages:

1. data audit;
2. adapter registry;
3. schema inventory;
4. fixture evaluation;
5. metrics;
6. policy;
7. lineage;
8. reconciliation;
9. quality gate;
10. replay;
11. release manifest;
12. artifact inventory;
13. review view;
14. review queue;
15. review SLA;
16. handoff;
17. integrity;
18. depth audit;
19. operational matrix;
20. performance budget;
21. repeat benchmark;
22. public access manifest;
23. observability trace; and
24. package and bundle close.

Supporting modules add execution-plan accounting, resource totals, sandbox
policy checks, schema migration and diff reports, provenance, idempotency
locks, rollback, run manifests, freshness, diagnostics, query partitions,
failure injection, and release checks.

## Numeric boundaries

This plane reports operational counts only: 16 fixture rows, 80 row checks,
16 scenario cells, 16 threshold probes, 64 validation cells, 96 evidence
cells, 24 runtime stages, and 4 accepted positive paths. It does not calculate
biological quantities, posterior probabilities, clinical risk, or treatment
suitability.
