# Platform frontier failure modes

The platform runtime treats failure as structured state. A failure can block
release, route review, or permit an explicit abstention, but it never creates
hidden work or silently widens scope.

## Mission planning

| Mode | Detection | Response |
| --- | --- | --- |
| Empty request | No requested role IDs. | `abstained` with `no_roles_requested`. |
| Unknown role | Registry cannot resolve a requested ID. | `rejected` with `unknown_role`. |
| Claim ceiling | Requested role exceeds mission ceiling. | `rejected` with `claim_ceiling_exceeded`. |
| Dependency expansion | Declared dependency is absent. | Reject plan construction and retain registry address. |

## Workflow compilation

| Mode | Detection | Response |
| --- | --- | --- |
| Cycle | DFS revisits a visiting step. | `blocked` with `dependency_cycle`. |
| Missing dependency | A dependency ID is not in the step map. | `blocked` with `missing_dependency`. |
| Network step | A step requests egress. | `partial` with review-visible warning. |
| Nondeterministic step | A step lacks deterministic behavior. | `partial` with seed/model review warning. |

The compiler does not drop an optional step simply because it is difficult to
schedule. Optionality remains in the compiled object and later policy stages
decide whether it can run.

## Typed registry

| Mode | Detection | Response |
| --- | --- | --- |
| Missing tool | Tool ID is not in the validated catalog. | `rejected` with `tool_not_registered`. |
| Input mismatch | Query contract differs from descriptor. | `incompatible` with `input_contract_mismatch`. |
| Output mismatch | Query output contract differs. | `incompatible` with output mismatch. |
| Cardinality mismatch | Catalog count differs from 96. | `incompatible` with `registry_cardinality_mismatch`. |

The registry is descriptive. Resolving a contract does not execute its
handler, grant network access, or imply scientific validity.

## Sandbox isolation

| Mode | Detection | Response |
| --- | --- | --- |
| Handler missing | The tool was not registered in the sandbox. | `denied` with `handler_not_registered`. |
| Network boundary | Egress tool meets local-only isolation. | `denied` with `network_egress_disabled`. |
| Sensitive input | Policy detects a direct identifier path. | `rejected` with `direct_identifier`. |
| Dynamic import | Isolation requests dynamic imports. | Construction fails validation. |
| External process | Isolation requests process launch. | Construction fails validation. |
| Replay | Same idempotency key repeats. | Cached result and original event IDs. |

The sandbox still uses the control plane for policy, resource scheduling,
typed result classification, events, and review routing. A local sandbox is
not a security claim about an operating-system container; deployment-specific
hardening remains an operational gate.

## Receipt integrity

The integrity layer recomputes fixture, source, record, execution, check, and
evaluation addresses. Mutation probes alter an expected state, an execution
address, and control retention. All three mutations must be detected before a
release can be accepted.

## Recovery

Recovery preserves the failed receipt, classifies the first issue, routes
review when appropriate, and retries only the same typed operation with the
same input and configuration. A changed tool, context, contract, threshold,
network permission, or claim ceiling creates a new versioned run.
