# Module change impact and release gate

`module-impact` compares two immutable outputs from the repository module
inventory. It is a static change-control surface for module-by-module work. It
does not import discovered modules, execute discovered functions, inspect local
machine identity, or make a release decision from an opaque aggregate score.

## What the subsystem closes

The implementation is split into explicit contracts:

1. `module_impact.py` compares module rows, public and private symbol shape,
   line deltas, test-reference deltas, and dependency edges.
2. `module_impact.py` also builds a reverse-dependency closure over both
   snapshots. Direct changes retain their kind and severity; dependent modules
   retain shortest paths back to changed sources.
3. `module_impact_verification.py` turns each impact into a stable review or
   replay task. A task has a priority, evidence strings, source modules, and a
   content address.
4. `module_impact_policy.py` evaluates explicit thresholds for critical and high
   impact, removals, unresolved direct edges, test-reference decreases, clean
   inputs, and minimum task coverage.
5. `module_impact_audit.py` independently checks ordering, path termination,
   count conservation, closure references, and the public boundary.
6. `module_impact_runtime.py` records seven deterministic stages: input, diff,
   impact, verification, policy, replay, and public.
7. `module_impact_observability.py` exposes timestamp-free event rows and
   aggregate metrics for dashboards and CI.
8. `module_impact_packet.py` writes a ten-artifact exact-byte offline handoff.
   The packet can be independently verified, loaded, queried, compared, and
   replayed without source access.

## Direct versus propagated impact

The diff contains one ordered row for every module in the union of the two
snapshots. A row is `added`, `removed`, `changed`, or `unchanged`. Changed rows
retain symbol additions, removals, shape changes, dependency additions and
removals, and scalar deltas.

The impact report contains only modules in the changed-source closure:

| Propagation | Meaning |
| --- | --- |
| `direct` | The module row itself changed, was added, or was removed. |
| `dependent` | The module directly imports a changed module in either snapshot. |
| `transitive` | The module is reached through two or more reverse edges. |

The reverse graph is built from the union of both snapshots. This makes removal
impact visible even when the target only exists in the left snapshot, and makes
new dependents visible when they only exist in the right snapshot. Shortest
paths are retained as `source->dependent->...` strings. Cycles terminate through
per-source visitation and do not duplicate an assessment.

Severity is explainable. Removing a module or a symbol is critical; removing a
dependency is high; added or shape-changed dependencies and symbols are high;
test-reference decreases are moderate; a plain content change is moderate; and
an added module begins at low. Propagated severity decreases with distance and
the report retains the source IDs and reasons that produced it. Risk is a
bounded 0–100 value derived from severity and distance, not a learned score.

## Commands

Build a same-tree baseline assessment:

```text
python -m glio_noncode module-impact
```

Compare two source trees and return a summary, full diff, report, CSV, or
bounded Markdown review:

```text
python -m glio_noncode module-impact \
  --left-source-root .artifacts/baseline/src \
  --right-source-root .artifacts/candidate/src \
  --format summary
python -m glio_noncode module-impact --format diff --output diff.json
python -m glio_noncode module-impact --format report --output impact.json
python -m glio_noncode module-impact --format changes-csv --output changes.csv
python -m glio_noncode module-impact --format impacts-csv --output impacts.csv
python -m glio_noncode module-impact --format tasks-csv --output tasks.csv
python -m glio_noncode module-impact --format markdown --output review.md
```

The source-root options can be paired with `--left-test-root` and
`--right-test-root`. If omitted, each root uses its adjacent repository test
root. A same-tree run is useful for checking scanner replay stability and should
have zero direct changes.

The focused commands expose each stage independently:

```text
python -m glio_noncode module-impact-policy
python -m glio_noncode module-impact-audit --left-source-root baseline --right-source-root candidate
python -m glio_noncode module-impact-verification --format csv
python -m glio_noncode module-impact-runtime
python -m glio_noncode module-impact-observability --format metrics-csv
python -m glio_noncode module-impact-schema
python -m glio_noncode module-impact-capabilities
```

## Policy behavior

The default policy is intentionally conservative about critical impact and
module removals while allowing a large high-impact review queue. It is a typed
object, so a caller can construct a stricter or more permissive policy without
changing the diff or report addresses. The gate retains every check when it
blocks. It never silently converts a blocked state into an accepted state.

The default checks are:

- accepted diff, report, and verification inputs;
- critical-impact threshold;
- high-impact threshold;
- removal allowance;
- unresolved direct-edge threshold;
- optional test-reference decrease policy;
- minimum verification-task count; and
- direct-change closure.

Policy evaluation does not run tests or handlers. It produces work for those
activities and leaves execution to a separately controlled environment.

## Offline packet

`module-impact-packet` writes a directory containing `manifest.json` and ten
declared artifacts:

| Artifact | Purpose |
| --- | --- |
| `left-inventory.json` | The baseline inventory projection. |
| `right-inventory.json` | The candidate inventory projection. |
| `diff.json` | Ordered module and dependency changes. |
| `impacts.json` | Direct and propagated impact assessments. |
| `verification.json` | Review and replay task plan. |
| `gate.json` | Policy decision and all checks. |
| `audit.json` | Independent cross-artifact audit. |
| `runtime.json` | Seven-stage runtime receipt. |
| `observability.json` | Events and aggregate metrics. |
| `summary.md` | Bounded human review projection. |

Materialization is atomic per file and refuses an existing destination unless
`--allow-existing` is supplied. Verification rejects symlinks, unsafe paths,
extra files, missing files, invalid UTF-8, byte-count drift, line-count drift,
address drift, manifest drift, and forbidden public keys.

Offline query and replay require successful independent packet verification:

```text
python -m glio_noncode module-impact-packet \
  --left-source-root baseline \
  --right-source-root candidate \
  --destination .artifacts/module-impact
python -m glio_noncode module-impact-packet-verify .artifacts/module-impact
python -m glio_noncode module-impact-packet-query .artifacts/module-impact \
  --resource impacts --severity high --limit 25
python -m glio_noncode module-impact-packet-replay .artifacts/module-impact
python -m glio_noncode module-impact-packet-diff .artifacts/old .artifacts/new
```

## API surface

The loopback service exposes the same projections under `/v1/module-impact`.
All source-building routes accept optional `left_source_root`,
`right_source_root`, `left_test_root`, and `right_test_root` query parameters.
Schema and capability routes do not scan source.

| Route | Purpose |
| --- | --- |
| `/v1/module-impact` | Summary, diff, report, CSV, or Markdown projection. |
| `/v1/module-impact/query` | Bounded changes, dependency, impact, or task query. |
| `/v1/module-impact/schema` | Combined machine-readable schema declarations. |
| `/v1/module-impact/capabilities` | Operation and boundary declarations. |
| `/v1/module-impact/audit` | Independent closure audit. |
| `/v1/module-impact/policy` | Default static policy. |
| `/v1/module-impact/verification` | Verification task plan. |
| `/v1/module-impact/verification/query` | Bounded task query. |
| `/v1/module-impact/runtime` | Staged runtime receipt. |
| `/v1/module-impact/observability` | Events and aggregate metrics. |
| `/v1/module-impact/observability/schema` | Observability schema. |
| `/v1/module-impact/observability/capabilities` | Observability capabilities. |
| `/v1/module-impact/packet` | Packet manifest projection. |
| `/v1/module-impact/packet/verify` | Offline packet verification. |
| `/v1/module-impact/packet/query` | Verified packet query. |
| `/v1/module-impact/packet/diff` | Verified packet comparison. |
| `/v1/module-impact/packet/replay` | Verified packet replay. |

The service returns a bounded error object for invalid filters and uses an
unprocessable response for a valid but blocked closure. No route executes a
discovered module.

## Performance and limits

The inventory scanner first reduces each source file into immutable rows and
does not retain the complete AST forest. The impact layer operates on those
rows. Reverse traversal uses per-seed visitation and a union reverse index.
Public outputs are bounded by query pagination and packet artifact limits.

Large repositories should persist a baseline packet and compare it offline
instead of rebuilding both trees for every dashboard request. Packet query and
replay never re-open source files.

## Scope and limitations

The subsystem reports static structural impact. It does not claim that a
changed module is scientifically correct, clinically validated, or behaviorally
safe. It does not execute a test suite, infer runtime call graphs, or resolve
third-party packaging behavior. Those limitations remain visible in the schema,
capabilities, and verification task kinds.
