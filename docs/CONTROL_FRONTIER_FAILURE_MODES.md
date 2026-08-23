# Control frontier failure modes

The runtime keeps failure modes explicit. A failure report describes the
boundary that was reached and the retained issue code; it does not replace a
missing input with a successful value.

## Admission and scope

| Mode | Detection | Retained response |
| --- | --- | --- |
| Sensitive path | Policy sees a declared sensitive-key path. | `blocked` with `sensitive_input`; raw value excluded. |
| Source gap | A source is outside the declared allowlist. | `blocked` with `source_allowlist_gap`. |
| Mutation scope | Request declares an unapproved mutation. | `blocked` with `mutation_scope_denied`. |
| Claim ceiling | Requested claim exceeds descriptive ceiling. | `rejected` with claim-boundary receipt. |
| Context mismatch | Context differs from the exact fixture key. | `out_of_domain` with `context_mismatch`. |

The policy surface is evaluated before the operation receipt is considered
publishable. The issue code is stable and the policy version is retained.

## Scheduling and fallback

| Mode | Detection | Retained response |
| --- | --- | --- |
| Capacity exceeded | Requested resource exceeds a declared budget. | Deferred or rejected item with resource totals. |
| Network limit | Optional network work is outside the schedule boundary. | Deferred item with `network_limit`. |
| Dependency cycle | Topological ordering cannot close. | Blocked schedule with cycle members. |
| Non-retryable failure | Current error does not permit route retry. | Blocked route with `non_retryable_failure`. |
| Missing input | Candidate lacks a required input. | Abstention with `no_eligible_candidate`. |
| Network-only route | Candidate requires a disallowed network. | Abstention with `no_eligible_candidate`. |

Scheduling does not execute work. Fallback selection does not contact an
external provider. These boundaries make dry-run receipts safe to replay.

## Review and ledger

| Mode | Detection | Retained response |
| --- | --- | --- |
| Review blocker | An item includes a blocker reason. | Bounded queue item with blocker and priority. |
| Queue omission | Queue limit removes lower-priority items. | Omission IDs and queue-bound warning. |
| Invalid transition | Event kind is not allowed from the current state. | Ledger issue with original sequence retained. |
| Duplicate event | An event ID repeats. | Duplicate issue; duplicate is not appended. |
| Foreign event | Event context differs from the ledger context. | Out-of-domain ledger result. |

Queue and ledger failures remain useful output. A failed queue or replay is
not deleted from the runtime report merely because the release gate is closed.

## Registry and monitoring

| Mode | Detection | Retained response |
| --- | --- | --- |
| Model context gap | Registry record does not support the requested context. | Out-of-domain compatibility result. |
| Model contract gap | Input or output contract differs. | Blocked compatibility result. |
| Missing model | Requested version is not registered. | Abstained resolution. |
| Coordinate mismatch | Reference uses another coordinate system. | Blocked reference result. |
| License mismatch | Requested license is not available. | Blocked reference result. |
| Missing reference | Dataset version is not registered. | Abstained resolution. |
| Watch signal | Current metric exceeds watch threshold. | `watch` state with review-visible signal. |
| Drift signal | Current metric exceeds drift threshold. | `drift` state with review-visible signal. |
| OOD support | Observation declares `in_domain` false. | `out_of_domain` state; no transport. |

Registry compatibility is metadata closure. Monitoring is threshold routing.
Neither surface supplies scientific validity or clinical interpretation.

## Integrity failures

Content addresses are recomputed from canonical object bodies. Integrity
checks cover the fixture, sources, records, executions, checks, unique row
IDs, and evaluation envelope. A changed execution address or changed nested
field fails integrity even if the replacement address uses the same SHA-256
prefix.

The failure-injection suite mutates an expected state, an execution address,
and control retention. All three mutations must be detected. This gives CI a
small regression probe for the most important receipt boundaries.

## Recovery behavior

Recovery is deterministic and local:

1. keep the original fixture and receipt;
2. classify the issue code;
3. route to review or abstention when required;
4. prevent a release receipt when a required stage fails;
5. preserve the report for later re-run; and
6. retry only a declared deterministic operation.

No recovery path silently broadens context, source scope, mutation scope,
network permissions, claim ceiling, or queue limit.
