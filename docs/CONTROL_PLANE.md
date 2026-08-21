# Control plane

GLIO-NONCODE uses a bounded control plane to turn a research question into
inspectable work. The control plane is not a general-purpose tool runner: it
only executes handlers registered against a declared role and tool contract.

The implementation lives in
[`src/glio_noncode/control_plane.py`](../src/glio_noncode/control_plane.py).
The public registry is available with:

```text
python -m glio_noncode registry
python -m glio_noncode bindings
```

## Planes and roles

The registry contains 48 roles across six planes:

| Plane | Responsibility |
| --- | --- |
| Control | Mission planning, compilation, policy, resources, arbitration, review routing |
| Data | Intake, canonical identity, references, complex variation, lineage, origin, assay QC |
| Atlas | Regulatory, brain, glioma-state, chromatin, methylation, 3D, literature, functional context |
| Inference | Sequence, motif grammar, accessibility, topology, links, allele specificity, mechanism, cohort, causal, posterior, uncertainty |
| Validation | Negative controls, benchmarks, assay routing, reagents, power, validation value |
| Lifecycle | Evidence graph, reports, adjudication, reclassification, monitoring, security and privacy |

Every role declares its purpose, input and output contracts, dependencies,
claim ceiling, allowed tool IDs, review requirement, and prohibited actions.
Dependencies are expanded by `MissionPlanner`; omitted work is not silently
inserted into a plan.

## Tool contracts

Each role owns two explicit tools: an inspection tool and a publication tool,
for 96 total contracts. A contract declares:

- safety class and mutation scope;
- input and output contract names;
- resource envelope and deadline;
- determinism and network-egress behavior;
- allowed public source IDs;
- whether policy and human review are required.

The executor accepts injected handlers only after their tool ID is found in the
registry and owned by the selected role. A handler cannot discover arbitrary
functions, mutate upstream evidence, promote its own claim tier, or turn a
timeout into a negative result.

## Invocation boundary

Every request carries:

1. a `MissionContext` with research-only intent, claim ceiling, source and data
   allowlists, mutation scope, and network permission;
2. a `ProvenanceContext` with input hashes, source versions, upstream event
   IDs, reference build, model digests, and parent bundles;
3. an idempotency key;
4. a `WorkflowBudget` and effective resource envelope;
5. a typed input payload.

`PolicyClaimGate` runs before scheduling. It rejects prohibited claim language,
claim ceilings above the mission ceiling, undeclared sources, disallowed data
scopes, direct identifiers, and mutation scopes outside the mission. The
`ResourceScheduler` then enforces capacity, invocation, network, wall-time,
and deadline limits.

## Typed outcomes

Handlers return exactly one of:

- `EvidenceEnvelope`: an observation or evidence result with state, tier,
  payload hash, sources, provenance, confidence, and limitations;
- `WorkflowDecision`: a named plan with selected roles and tools;
- `TypedInvocationError`: a machine-readable failure that is never evidence;
- `Abstention`: an explicit non-answer with reason, missing inputs, and
  remediation.

`EvidenceArbiter` retains conflicts as abstentions when independent branches
disagree on a payload hash. `HumanReviewRouter` creates an explicit review
route for review-designated roles, abstentions, and non-retryable failures.
Every admitted invocation writes a hash-chained admission and completion event
containing input and response digests rather than raw sensitive payloads.

## Extension rules

New roles or tools must be added to the registry source table and must keep the
registry cardinality and ownership checks green. New handlers should be
deterministic where possible and must preserve source receipts, reference
versions, model digests, and explicit failure states. A model may help with
bounded planning, extraction, review, or explanation, but it may not invent
variants, measurements, statistical results, posterior values, or citations.

`ControlPlaneApplication` binds the core executable slice to registered
publication tools: mission planning (`A01`), VCF/TSV/JSON intake (`A07`),
identity normalization (`A08`), public atlas retrieval (`A15`), sequence
inference (`A23`), uncertainty/OOD aggregation (`A36`), power planning (`A41`),
human-review abstention (`A45`), and drift monitoring (`A47`).

Atlas execution has an additional runtime boundary because the current
publication handler can invoke the public adapters: the mission must set
`allow_network=True` and explicitly allowlist `SRC-ENSEMBL-REST` and
`SRC-UCSC-REST`; `SRC-ENCODE-REST` is required only when the query requests
the ENCODE catalog. If the boundary is missing, the handler abstains without
making a request. Sequence and uncertainty handlers accept receipt-backed
sequence/claim mappings and return content-addressed computed envelopes.

Other registered roles remain available for dependency planning and return
explicit handler-unavailable errors until their domain module is installed;
they do not silently report success.
