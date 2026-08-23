# Deployment frontier failure modes

The failure matrix is part of the product contract. Controls must remain
negative controls; changing their expected state to make a gate green removes
evidence rather than fixing the implementation.

| Code | Operation | Trigger | Expected state | Recovery |
| --- | --- | --- | --- | --- |
| `role_not_allowed` | C13 | presented roles do not intersect policy roles | `denied` | route to privacy review |
| `required_role_missing` | C13 | request requires a role not presented | `denied` | obtain explicit role decision |
| `context_mismatch` | C13 | request context differs from policy context | `denied` | repair context or keep held |
| `sensitive_access_denied` | C13 | sensitive request has no explicit grant | `denied` | preserve deny-by-default |
| `invalid_digest` | C14 | artifact digest does not use SHA-256 style | `hold` | repair manifest and replay |
| `bundle_requirements_missing` | C14 | artifact or service inventory is empty | `hold` | complete manifest |
| `offline_mode_required` | C14 | online-only bundle crosses local boundary | `hold` | declare offline-compatible inputs |
| `site_unavailable` | C15 | required site is unavailable | `hold` | retain task-local review |
| `privacy_budget_exceeded` | C15 | task cost exceeds declared budget | `hold` | revise plan or budget under review |
| `context_not_supported` | C15 | site lacks exact requested context | `hold` | select a compatible site |
| `failed_check:<name>` | C16 | named release gate is false | `denied` | repair gate and rerun |
| `previous_version_missing` | C16 | rollback has no previous version | `denied` | provide explicit prior package |
| `version_already_current` | C16 | release target equals current version | `denied` | no-op and retain receipt |

## Failure injection rehearsal

`run_deployment_frontier_failure_injections` replays the twelve control rows
from the public fixture. It requires every control to produce at least one
issue code and reports the observed state. The runtime accepts the injection
stage only when all twelve controls remain blocked or held.

## Recovery classification

Retryable controls are limited to repairable manifest or availability issues:
`invalid_digest`, `bundle_requirements_missing`, and `site_unavailable`. These
produce a `repair_and_replay` action that still requires review. Policy,
privacy, context, and release-gate failures produce `review_and_hold`; they
are not automatically retried.

## Triage order

1. Confirm the fixture content address and exact context key.
2. Inspect the operation result and normalized issue codes.
3. Compare expected and observed states in reconciliation.
4. Inspect the row-specific validation and evidence cells.
5. Apply the declared recovery action.
6. Replay and compare content addresses.
7. Re-run the quality and release checks.

The failure mode output is a research operations receipt. It does not authorize
access to raw site data, deployment to a clinical environment, or a scientific
claim.
