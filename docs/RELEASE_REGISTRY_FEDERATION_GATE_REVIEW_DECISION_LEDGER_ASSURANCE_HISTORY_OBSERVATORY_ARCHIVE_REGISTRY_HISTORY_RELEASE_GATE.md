# Registry history release gate

The history release gate is the policy boundary after history construction,
independent audit, and bounded inspection. It loads an exact four-file history
package, recomputes the independent thirteen-check history audit, evaluates a
typed public policy, and returns one deterministic decision.

The decision state is deliberately explicit:

| State | Meaning |
| --- | --- |
| `ready` | every gate check passed and the history is release-ready under the policy |
| `held` | the history is structurally valid but one or more policy checks require review |
| `blocked` | an integrity or public-boundary check prevents release use |

## Policy

`RegistryHistoryReleasePolicy` has no source paths, timestamps, ownership
fields, attribution fields, model fields, or language metadata. Its controls
are:

- `minimum_snapshots`, default `2`;
- `require_audit_complete`, default `true`;
- `require_all_snapshots_accepted`, default `true`;
- `require_final_release_ready`, default `true`;
- `allowed_transition_states`, default `unchanged` and `improved`;
- per-transition removed and changed-item budgets;
- regression and mixed-transition budgets.

The policy is content-addressed separately from the gate. Every gate check
contains a stable check address, severity, public observed values, and an
evidence address. Policy failures are `hold` checks; audit, public-boundary,
and content-address failures are `blocking` checks.

## Python

```python
from glio_noncode import (
    AssuranceHistoryObservatoryArchiveRegistryHistoryReleasePolicy,
    evaluate_assurance_history_observatory_archive_registry_history_release_gate_from_directory,
)

policy = AssuranceHistoryObservatoryArchiveRegistryHistoryReleasePolicy(
    policy_id="policy:downloaded-history",
    minimum_snapshots=2,
    allowed_transition_states=("unchanged", "improved"),
    max_regressed_transitions=0,
)
gate = evaluate_assurance_history_observatory_archive_registry_history_release_gate_from_directory(
    "./review-output/history",
    policy,
)
print(gate.state, gate.accepted, gate.content_address)
```

## CLI

```powershell
python -m glio_noncode <history-command>-release-gate `
  --input .\review-output\history `
  --minimum-snapshots 2 `
  --allowed-transition-state unchanged `
  --allowed-transition-state improved `
  --format markdown

python -m glio_noncode <history-command>-release-gate-policy-schema
python -m glio_noncode <history-command>-release-gate-check-schema
python -m glio_noncode <history-command>-release-gate-capabilities
```

The command exits `0` only for `ready`; a valid `held` or `blocked` result is
still emitted as inspectable JSON, CSV, or Markdown and exits `2`.

## HTTP

The route is the history route plus `/release-gate`. Query parameters mirror
the CLI using lower-case underscores. Repeated
`allowed_transition_state` parameters are accepted.

```text
GET /v1/.../history/release-gate?input=./review-output/history&format=json
GET /v1/.../history/release-gate/schema
GET /v1/.../history/release-gate/policy-schema
GET /v1/.../history/release-gate/check-schema
GET /v1/.../history/release-gate/capabilities
```

An accepted gate returns HTTP `200`. A valid held or blocked gate returns HTTP
`422` with the complete public decision body so callers can inspect the exact
failed checks.

## Downloaded-data demo

After the history demo has produced the local history package, run:

```powershell
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_demo.py `
  --input .\review-output\history `
  --format markdown
```

The example shows the full decision, policy address, audit address, check
addresses, and the final gate address. Its output is deterministic for the
same public history and policy.
