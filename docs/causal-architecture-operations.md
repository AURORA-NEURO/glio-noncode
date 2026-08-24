# D11 Operation Map

The operation map is ordered by declared dependencies. Each operation has a capability identifier, family, plane, input contract, output contract, source joins, and control policy. The map is represented by `CausalArchitectureOperationSpec` and is checked against the four-scenario matrix before execution.

| IDs | Family | Operations | Plane |
| --- | --- | --- | --- |
| C01-C04 | Foundation | typed hypothesis, factor graph, context prior, measurement likelihood | causal foundation |
| C05-C08 | Beta | sequence-to-element, element-to-gene, gene-to-state, counterfactual allele state | causal mediator |
| C09-C12 | Alpha | mediation sensitivity, confounding checklist, dependence correction, negative evidence | causal sensitivity |
| C13-C16 | Frontier | posterior decomposition, regulatory-driver posterior, selective abstention, causal dossier publication | causal release |

## Per-case execution

The operation adapter resolves a delegate record by family and record identifier, retains its observed result state, copies the declared issue vocabulary, and adds an aggregate output address. The aggregate receipt compares expected and observed state, result state, issue codes, and count fields. A receipt can close even when the observed result is a review-worthy result because expected review paths are part of the contract.

Positive cases are expected to be accepted, except for the declared partial result at C12 and the published terminal result at C16. Controls are expected to remain in review and retain family-specific issue codes or explicit context controls. Context mismatch is never silently converted into support.

## Review routing

All control cases enter the review queue. The queue records case, operation, scenario, priority, blocking disposition, reason, and required action. The required action keeps context, evidence dependence, and stated limitations visible before release. This makes the research surface useful for inspection without turning a review case into a downstream decision.

## Determinism

All records are ordered by ordinal, operation, and scenario. Each typed object receives a canonical SHA-256 content address derived from its serialized fields. Replay rebuilds the fixture and evaluation, compares addresses and receipt counts, and closes only when the same result is obtained. The query surface returns sanitized case rows and never replaces the full receipt or release record.
