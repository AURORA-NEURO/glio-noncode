# Release-control operations guide

This guide translates the consensus release-control contract into repeatable
operator actions. It assumes downloaded package-registry directories have
already been produced by the registry package writer and that the operator
wants an explainable decision, not an opaque boolean.

## Operating principles

1. Treat every directory as an untrusted observation until its canonical
   registry loader verifies it.
2. Treat every consensus address as a value, not as a permission to edit a
   source registry.
3. Run the independent audits before handing a result to another boundary.
4. Preserve rejected receipts. Their failed checks are the remediation record.
5. Use package and history addresses when referring to a result across process
   boundaries.
6. Keep query limits explicit. A truncated query is an incomplete view, not a
   smaller truth.
7. Compare gate receipts when policy or source observations change.
8. Re-run the demo or focused contracts after changing adapters or schemas.

## One-shot clean evaluation

For two equivalent downloaded registries, run the gate runtime with a quorum
that both peers can satisfy:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-runtime `
  --peer primary=C:\downloads\primary `
  --peer replica=C:\downloads\replica `
  --federation-id production-downloads `
  --consensus-id production-consensus `
  --runtime-id production-gate-runtime `
  --gate-id production-release-gate `
  --quorum 2 `
  --limit 100 `
  --destination C:\handoffs\production-gate `
  --format json `
  --output C:\handoffs\production-gate-runtime.json
```

The successful response should contain:

| field | expected clean value |
| --- | --- |
| `gate.state` | `eligible` |
| `gate.decision` | `promote` |
| `gate.accepted` | `true` |
| `gate.failed_count` | `0` |
| `audit.accepted` | `true` |
| `persisted` | `true` |
| `package_address` | a consensus-gate-package address |

The command returns zero only when the gate and its independent audit accept.
The package directory is independently reloadable and contains the exact six
members listed in the release-control contract.

## One-shot divergent evaluation

When one downloaded registry contains a held or otherwise different package,
keep the same workflow and change only the peer directory:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-runtime `
  --peer primary=C:\downloads\primary `
  --peer archive=C:\downloads\archive `
  --federation-id production-downloads `
  --consensus-id production-consensus-divergent `
  --runtime-id production-gate-runtime-divergent `
  --destination C:\handoffs\divergent-gate `
  --format json `
  --output C:\handoffs\divergent-gate-runtime.json
```

The expected response is a valid rejection:

| field | expected divergent value |
| --- | --- |
| `gate.state` | `blocked` |
| `gate.decision` | `hold` |
| `gate.accepted` | `false` |
| `gate.failed_count` | greater than zero |
| `audit.accepted` | `true` when the receipt is intact |
| `query.returned_count` | greater than zero when failures exist |

An exit code of two is not a transport failure. It means the typed result was
constructed and failed its release policy. Preserve the JSON and package so an
operator can inspect the dissent and run remediation without reconstructing
the original downloads.

## Failure triage

Start with the gate summary, then narrow to failed checks:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-query `
  --input C:\handoffs\divergent-gate.json `
  --resource failures `
  --passed false `
  --limit 100 `
  --format markdown
```

The most important check groups are:

| checks | interpretation |
| --- | --- |
| `runtime-accepted` | consensus itself is not eligible |
| `consensus-audit` | the child audit cannot certify the consensus shape |
| `remediation-audit` | the action-to-step projection is not conserved |
| `remediation-query-audit` | the bounded remediation view cannot be replayed |
| `state-allowed`, `decision-allowed` | policy and consensus disposition disagree |
| `minimum-peers`, `minimum-quorum` | the observation set is too weak |
| `selected-packages`, `unresolved-packages` | package address selection is incomplete |
| `blocking-remediation`, `remediation-ready` | operator work remains before promotion |
| `consensus-query-complete`, `remediation-query-complete` | configured completeness policy failed |
| `address-links` | the typed execution graph is not internally linked |
| `policy-address` | policy bytes changed or were not replayed |
| `check-conservation` | the fixed gate vocabulary changed unexpectedly |
| `content-address`, `mapping-round-trip` | final receipt construction/replay failed |
| `path-free` | a private path or forbidden metadata crossed the boundary |

Do not treat a passing audit as a passing gate. The audit says the gate is
internally consistent; the gate decision says whether the release policy is
satisfied. A divergent gate can be rejected and still have a completely
passing independent audit.

## Inspecting bounded views

The gate query is designed for a terminal, API, or review queue. Use the
`summary` resource to confirm the disposition, `checks` to inspect every policy
result, `failures` to reduce the view to failed checks, and `evidence` to see
supporting addresses. All views are deterministic projections of the same gate.

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-query `
  --input C:\handoffs\production-gate.json `
  --resource summary `
  --resource checks `
  --resource evidence `
  --offset 0 `
  --limit 50 `
  --format json `
  --output C:\handoffs\production-gate-query.json
```

When `truncated` is true, continue at `next_offset`. Do not infer that rows
outside a page are absent. The query address changes when filters, resources,
offset, or limit change, which makes each review view auditable.

## Package transport

Transport the package directory as an atomic unit. A receiver should verify the
directory before reading individual projections:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-package-audit `
  --input C:\handoffs\production-gate `
  --format markdown
```

The loader checks these invariants in order:

1. the destination exists and is a directory;
2. its file names equal the six-file vocabulary exactly;
3. every file is canonical JSON;
4. `package.json` replays as a typed package;
5. the manifest replays from the package;
6. runtime, gate, audit, and query projections replay byte-for-byte;
7. nested addresses agree with the package envelope;
8. the package content address recomputes.

If any check fails, discard the transport copy and retain its diagnostic for
the sender. Do not repair one member in place: doing so makes the old package
address meaningless.

## Transition review

When a policy changes or a second download arrives, compare gate JSON values:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-diff `
  --left C:\handoffs\before-gate.json `
  --right C:\handoffs\after-gate.json `
  --format markdown `
  --output C:\handoffs\gate-transition.md
```

Then audit the serialized diff:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-diff-audit `
  --input C:\handoffs\gate-transition.json `
  --format summary
```

A diff with no items is a meaningful identity result: the two gate receipts
are equivalent at the compared resource boundary. A non-empty diff does not
say which side is correct. It identifies policy, check, disposition, and
receipt changes so a separate release decision can be made.

## Timeline and observatory review

Build a history from exact gate packages, not from unverified ad hoc summaries:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-history `
  --input C:\handoffs\before-gate `
  --input C:\handoffs\after-gate `
  --history-id production-gate-history `
  --destination C:\handoffs\production-gate-history
```

The history preserves source gate IDs, runtime IDs, state, decision, acceptance,
failed counts, and evidence addresses. `append_history` adds a new ordinal; it
does not replace an earlier entry with the same logical ID.

Aggregate multiple history files for a review queue:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-observatory `
  --input C:\handoffs\production-gate-history `
  --accepted false `
  --limit 100 `
  --format markdown
```

The observatory is a monitoring projection. It does not merge, rewrite, or
approve source histories. A `review` observation and a `blocked` observation
remain distinct even when they refer to the same download job.

## HTTP examples

Build a runtime from repeated peer values:

```text
GET /v1/registry/federation/consensus/gate/runtime?peer=primary=C:\downloads\primary&peer=replica=C:\downloads\replica&quorum=2&format=json
```

Read a bounded failure view:

```text
GET /v1/registry/federation/consensus/gate/query?input=C:\handoffs\gate.json&resource=failures&passed=false&limit=50&format=json
```

Read a schema:

```text
GET /v1/registry/federation/consensus/gate/runtime/schema
```

The API returns `200` for successful projections, `422` for valid but
non-accepted gate/runtime decisions, and `400` for malformed JSON, unsupported
filters, broken addresses, missing paths, or invalid package members. The
response body is intentionally concise; use the JSON projection or package
for complete evidence.

## Safe retry behavior

Retry a read or a complete build when a source directory is unavailable. Do
not retry by mutating an existing handoff directory. Use a sibling destination,
verify it, and then promote the directory at the outer transport layer if that
layer provides atomic rename semantics.

The gate runtime is content-addressed, so repeated evaluation of identical
canonical source data, policy, identifiers, and query parameters should yield
the same nested addresses. A changed timestamp, local path, or free-form note
must not be used to force uniqueness into a public receipt.

## CI expectations

The assurance workflow compiles every gate-family module and runs the focused
contract suites. Before pushing a gate change, run the local equivalents:

```powershell
$gateFiles=(Get-ChildItem src/glio_noncode/registry_federation_consensus_gate*.py).FullName
python -m py_compile $gateFiles src/glio_noncode/api.py src/glio_noncode/cli.py
pytest -q tests/test_registry_federation_consensus_gate.py `
  tests/test_registry_federation_consensus_gate_extended.py `
  tests/test_registry_federation_consensus_gate_validation.py `
  tests/test_registry_federation_consensus_gate_contract.py
```

The repository-wide public-surface audit should report 881 surfaces with zero
failures after this build. If a surface is intentionally added or removed,
update the expected inventory and the corresponding focused contract in the
same change.

## Handoff checklist

Before sharing a release-control result, confirm:

- source registries loaded successfully;
- the requested quorum is visible in the nested consensus runtime;
- gate state and decision match the intended policy;
- all required independent audits accept;
- the relevant query is not unexpectedly truncated;
- package reload produces the same package address;
- diff audit accepts when a transition is being reviewed;
- history and observatory audits accept when timeline projections are used;
- the receiver has the complete exact-member directory;
- no private path, agent metadata, or language attribution appears in public
  JSON, CSV, Markdown, or capability output.

The goal of this checklist is repeatability. A release decision should be
explainable from its content addresses and failed checks even after the source
directories are no longer mounted.

## Example result interpretation

For a clean pair, a compact runtime summary can be read as a sequence of
conserved facts:

```json
{
  "gate_id": "production-release-gate",
  "state": "eligible",
  "decision": "promote",
  "accepted": true,
  "audit_accepted": true,
  "failed_count": 0,
  "persisted": true
}
```

The summary does not replace the full receipt. It is a dashboard projection;
the gate JSON, audit JSON, query JSON, and package members are the evidence
needed for replay. The content addresses provide stable joins between those
objects:

```text
runtime.content_address
  -> gate.runtime_address
  -> gate.audit.gate_address
  -> gate.query.query.gate_address
  -> package.runtime_address
  -> package.gate_address
```

For a divergent pair, the corresponding summary can be concise while the
failure evidence remains detailed:

```json
{
  "gate_id": "production-release-gate",
  "state": "blocked",
  "decision": "hold",
  "accepted": false,
  "audit_accepted": true,
  "failed_count": 6,
  "persisted": true
}
```

The six failed checks are not necessarily six independent source defects. A
single unresolved package can correctly cause runtime acceptance, state,
decision, selection, unresolved-package, and remediation checks to fail. The
query rows retain the check IDs and evidence addresses so a consumer can group
failures without guessing from the count.

When only `minimum-quorum` fails, the result is normally `review/review`: the
execution graph is intact, but the policy does not approve its evidence
strength. When `runtime-accepted` or `unresolved-packages` fails, the result is
`blocked/hold`: selecting the result would discard dissent or an incomplete
observation. This distinction is useful for service-level dashboards and for
human review queues.

A package audit with `accepted=true` means its members and links replay; it
does not override a gate with `accepted=false`. An observatory audit with
`accepted=true` means its timeline is intact; it does not promote any
observation. Every boundary preserves this separation between integrity and
eligibility.
