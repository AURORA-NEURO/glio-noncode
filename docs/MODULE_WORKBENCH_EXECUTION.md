# Module Workbench Execution

The module workbench identifies deep implementation work and ranks it into a
bounded portfolio. The execution layer turns that portfolio into an immutable,
evidence-gated task ledger. It is a planning and verification surface: it does
not pretend that source code changed merely because a task was selected, and it
does not expose personal identity or private workflow metadata.

## Boundary

The public aggregate boundary is
`public_aggregate_module_workbench_execution`. Every persisted object has a
content address derived from its canonical body. The projection is timestamp-
free, path-free, and identity-free. Evidence addresses are opaque receipts;
the ledger never embeds a downloaded payload or a subject-level identifier.

The layer has five related public boundaries:

| Surface | Boundary | Purpose |
| --- | --- | --- |
| Execution ledger | `public_aggregate_module_workbench_execution` | Current task state and ordered events |
| Independent audit | `public_aggregate_module_workbench_execution_audit` | Reconstructive invariant checks |
| Progress policy | `public_aggregate_module_workbench_execution_policy` | Explicit readiness thresholds |
| Runtime handoff | `public_aggregate_module_workbench_execution_runtime` | Ordered portfolio-to-audit chain |
| Snapshot diff | `public_aggregate_module_workbench_execution_diff` | Task, evidence, and event deltas |

## From workbench task to execution item

`build_module_workbench_execution` accepts a typed workbench report and an
optional bounded portfolio. If no portfolio is supplied, the balanced default
portfolio is selected. Each selected task becomes one execution item with:

- stable task, module, family, kind, priority, and estimated-impact fields;
- prerequisites derived deterministically from the task kind order within a
  module;
- one or more declared evidence requirements;
- a minimum evidence count before completion;
- initial and current lifecycle states;
- completion, event, evidence, and blocker counters;
- a content address over the exact item body.

The execution ledger sorts items by task ID. That makes pagination, exports,
replays, and byte-for-byte comparisons stable even though work is selected by
priority. The initial item state is `ready` when it has no selected
prerequisite and `planned` when it must wait for another selected task in the
same module.

## Lifecycle

The allowed states are:

| State | Meaning |
| --- | --- |
| `planned` | Selected but waiting for a prerequisite |
| `ready` | Eligible to start |
| `in_progress` | Explicitly started and awaiting completion evidence |
| `blocked` | Paused with a retained blocker explanation |
| `completed` | Finished with the required evidence receipts |
| `skipped` | Deliberately not executed, with an explicit explanation |
| `superseded` | Replaced by a stronger or newer task, with an explicit reason |

Commands are immutable inputs. Applying a command returns a new ledger and
appends one addressed event; no existing event or item is rewritten. The
transition rules are:

| Action | Allowed transition | Additional condition |
| --- | --- | --- |
| `start` | `ready -> in_progress` | Every prerequisite is `completed` |
| `complete` | `in_progress -> completed` | Evidence count reaches the item requirement |
| `block` | `planned`, `ready`, or `in_progress -> blocked` | Detail is non-empty |
| `unblock` | `blocked -> ready` | Every prerequisite is `completed` |
| `skip` | Any non-terminal state -> `skipped` | Detail is non-empty |
| `reopen` | `completed` or `skipped -> ready` | Prerequisites remain complete |
| `supersede` | Any non-terminal state -> `superseded` | Replacement reason is non-empty |

Example:

```python
from glio_noncode.module_workbench_execution import (
    apply_module_workbench_execution_commands,
    execution_command,
)

updated = apply_module_workbench_execution_commands(
    ledger,
    (
        execution_command(task_id, "start", "begin bounded implementation"),
        execution_command(
            task_id,
            "complete",
            "completed with reviewed source and test receipts",
            evidence_addresses=("receipt:source", "receipt:test"),
        ),
    ),
)
```

The two resulting events preserve the complete state path. A completion command
without enough evidence fails closed with `ValidationError`; it cannot create a
partially completed row.

## Evidence requirements

Requirements are derived from the workbench task kind and sorted by their stable
value:

| Workbench task kind | Requirements | Minimum receipts |
| --- | --- | ---: |
| `repair_parse` | source, test | 1 |
| `resolve_dependency` | integration, source | 1 |
| `add_test` | test | 1 |
| `add_documentation` | documentation | 1 |
| `expand_public_contract` | documentation, test | 1 |
| `decompose_oversized` | review, test | 2 |
| `review_integration` | integration, review | 2 |
| `close_certification` | review | 2 |

The current contract checks the declared count and retains opaque receipt
addresses. It does not claim that a receipt proves a scientific result. A
future receipt resolver can attach independently verified artifacts without
changing the execution state machine.

## Queries and exports

The execution query supports four bounded resources:

- `items`: task, module, family, state, prerequisite, evidence, and blocker
  rows;
- `events`: contiguous transition history;
- `blockers`: only rows with explicit blockers;
- `summary`: state counts, completion percentage, event count, and evidence
  coverage.

Filters include task ID, module ID, family, state, task kind, free-text match,
offset, and limit. JSON is canonical. CSV exports are available for items and
events. Markdown keeps the state distribution, task rows, and event history
readable in review.

CLI examples:

```powershell
python -m glio_noncode module-workbench-execution --format summary
python -m glio_noncode module-workbench-execution --resource blockers --format json
python -m glio_noncode module-workbench-execution --resource items --format items-csv --output execution.csv
python -m glio_noncode module-workbench-execution --format markdown --output execution.md
```

The API exposes the equivalent read-only routes:

```text
GET /v1/module-workbench/execution
GET /v1/module-workbench/execution/query?resource=items&state=ready
GET /v1/module-workbench/execution/audit
GET /v1/module-workbench/execution/policy
GET /v1/module-workbench/execution/runtime
```

Schemas and capability declarations are available for every surface under its
`/schema` and `/capabilities` route.

## Independent audit

`audit_module_workbench_execution` does not use the transition builder as its
source of truth. It independently checks:

1. nested item, event, and ledger addresses;
2. contiguous event sequence and unique event IDs;
3. event task references and reconstructive transition legality;
4. prerequisite existence, acyclicity, and active-state eligibility;
5. completion evidence and blocker explanations;
6. state-count conservation;
7. item/event-count conservation;
8. forbidden public output keys.

The transition-graph check starts from each item’s persisted initial state,
replays the append-only event sequence, and compares the reconstructed state to
the persisted current state. This catches an event removed from the middle,
an altered `from_state`, a forged final state, and a duplicate sequence. The
audit remains useful for an empty event history because a plan is a valid
pre-execution state.

## Policy

The execution policy is deliberately separate from the audit. A policy can
require completion or evidence coverage for a release checkpoint while the
default planning policy allows a newly created plan with zero completed tasks.
Thresholds include:

- minimum aggregate completion percentage;
- minimum evidence coverage percentage;
- maximum blocked task count;
- maximum superseded task count;
- maximum event count;
- whether independent audit acceptance is required.

The gate retains one addressed check per threshold. A failed threshold is
returned to callers rather than hidden behind a boolean. A strict checkpoint
can be constructed without changing the underlying ledger:

```python
strict = build_module_workbench_execution_policy(
    minimum_completion_percent=100.0,
    minimum_evidence_coverage_percent=100.0,
)
gate = evaluate_module_workbench_execution_policy(ledger, strict)
```

## Runtime handoff

`run_module_workbench_execution` produces six ordered stages:

```text
portfolio -> plan -> replay -> policy -> audit -> handoff
```

The default command sequence is empty, so the runtime demonstrates plan
readiness. Supplying typed commands replays them in order and changes only the
ledger address retained by the runtime. Every stage stores its artifact
address, accepted state, and explanation. The runtime retains both the initial
and current ledger addresses so a reviewer can distinguish a plan from its
post-replay state.

## Snapshot diff

`build_module_workbench_execution_diff` compares two ledgers by task identity.
It classifies each task as added, changed, removed, or unchanged and reports
signed completion, evidence, event, and task deltas. A diff of the same ledger
is stable and conserves every task as unchanged. A changed row explains its
previous and current states while retaining its own content address.

```powershell
python -m glio_noncode module-workbench-execution-diff `
  --left-source-root . `
  --right-source-root . `
  --kind changed
```

## Failure behavior and limits

- Unknown task IDs fail closed.
- Terminal tasks cannot be blocked, skipped, or superseded.
- Prerequisites must be selected, known, acyclic, and completed before an
  active transition.
- Completed items cannot be created without the declared evidence count.
- Event sequences are contiguous and bounded.
- Query limits are bounded to protect local memory and response size.
- Public output is checked for identity, credential, attribution, and language
  keys.
- The layer is local-first and dependency-free; it does not download data or
  contact external services.

## Verification checklist

The focused regression suite covers:

- plan creation and prerequisite derivation;
- valid start and evidence-gated completion;
- invalid early completion and missing-evidence rejection;
- block, unblock, skip, reopen, and supersede transitions;
- independent address, graph, prerequisite, evidence, and boundary audits;
- strict and balanced policy decisions;
- task-level execution diffs;
- bounded queries, JSON/CSV/Markdown exports, schemas, and capabilities;
- runtime stage ordering and API schema routes.

The execution layer is operational planning infrastructure. It preserves review
accountability and deterministic state, but it does not assert that a module is
scientifically valid, clinically suitable, or complete merely because its task
state is `completed`.

## Module-level review routing

`build_module_workbench_execution_review` rolls the task ledger up by module so
reviewers can work at the same granularity as the original depth request. Each
module row conserves its task states and reports completion percentage, evidence
coverage, highest priority, critical-task count, blocker details, and bounded
next-task IDs. The routing state is derived in a fixed order:

```text
attention -> evidence_pending -> ready -> waiting -> verify -> complete -> superseded
```

Blocked work takes precedence, followed by active work that needs completion
evidence. Ready work is then routed for execution, while planned work remains
visible as waiting. A module with completed tasks is routed to verification until
all of its selected work is terminal; a fully completed module becomes complete.
This keeps a good completion score from hiding an unresolved sibling task.

The review projection has bounded `modules`, `tasks`, and `summary` resources,
CSV/JSON/Markdown exports, an addressed row per module, and dedicated API/CLI
schema and capability declarations. It is a read-only projection over the
ledger; it cannot mutate task state or bypass evidence requirements.
