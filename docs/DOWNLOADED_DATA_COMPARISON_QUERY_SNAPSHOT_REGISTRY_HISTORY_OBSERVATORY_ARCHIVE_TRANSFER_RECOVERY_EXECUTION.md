# Downloaded-data observatory archive transfer recovery execution

The recovery execution boundary turns a path-free recovery plan into a
verifiable receipt for what has been satisfied, what remains pending, and what
must be blocked. It is built over the deterministic transfer and recovery
contracts and carries only addresses, indices, byte ranges, statuses, and
bounded explanations. It does not expose archive payload bytes or source
paths.

## Execution states

An execution receipt preserves the original recovery plan and partitions every
planned chunk action into exactly one of these statuses:

- `pending`: the recovery action remains to be applied;
- `applied`: the action is present in the verified assembler or was explicitly
  accepted as a public status; and
- `rejected`: the action was explicitly refused and the receipt is blocked.

The derived state is `planned` when no action has been applied, `in_progress`
when some actions are applied, `complete` when all actions are applied, and
`blocked` when any action is rejected. The receipt also derives a decision:
`resume`, `assemble`, or `block`. Index and byte conservation, ordered outcome
addresses, checkpoint state, and the next actionable index are validated at
construction and reload.

The assembler-backed builder is the strongest input mode. It verifies the
transfer, matches the recovery transfer identity, and derives applied indices
from the actual downloaded chunk receiver before issuing a receipt. Directory
input is supported through the same verifier. Explicit applied/rejected index
input is available for boundary integrations that carry statuses without
payloads.

## Independent inspection

The execution audit has 18 checks covering linkage, conservation, outcome
ordering, byte accounting, state/decision/safety replay, checkpoint replay,
public boundaries, and canonical round trips. The query surface is bounded to
seven resources: `summary`, `outcomes`, `applied`, `pending`, `rejected`,
`state`, and `bounds`. It supports status, index, and text filters with stable
row addresses. Its independent query audit has 12 checks for resource order,
filter/count replay, row membership, semantics, linkage, and mapping replay.

## CLI

The long downloaded-data command is:

```text
downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution
```

Examples:

```text
glio-noncode <command> recovery.json --execution-id run-1 --applied-index 4 --checkpointed --format json --output execution.json
glio-noncode <command>-verify execution.json --format summary
glio-noncode <command>-audit execution.json --format markdown --output execution-audit.md
glio-noncode <command>-query execution.json --resource pending --limit 25 --format csv --output pending.csv
glio-noncode <command>-query-audit query.json --execution-input execution.json --format summary
```

The command also exposes outcome, receipt, audit, query-row, query, and
query-audit schemas and capability descriptions. Replace `<command>` with the
full command above when invoking the CLI.

## HTTP API

The corresponding base route is:

```text
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution
```

The base route accepts a recovery or execution JSON input. `/verify`, `/audit`,
`/query`, and `/query/audit` provide the receipt operations. Schema and
capability documents are available below the base route, including
`/outcome-schema`, `/schema`, `/audit/schema`, `/query/schema`, and
`/query-audit/schema`. Query-audit intentionally accepts separate `input` and
`execution_input` documents so the query and the execution receipt remain
independently verifiable.

## Downloaded-data demonstration

`examples/downloaded_data_contract_resolution_history_diff_policy_demo.py`
builds the observatory archive and transfer from the attached downloaded ZIP,
creates a two-chunk partial receiver, records a planned receipt, adds one
missing chunk for an in-progress receipt, completes the assembler, and creates
a rejected-action blocked receipt. It persists the progression, all audit and
query documents, and the summary under the requested artifact directory. The
demonstration verifies the final archive bytes against the nested archive
contract and requires both independent execution audits to pass.
