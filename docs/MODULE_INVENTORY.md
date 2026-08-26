# Module inventory and depth control plane

The module inventory is a static repository inspection surface for the local
`glio_noncode` package. It exists because a large research workbench needs a
measurable module boundary in addition to domain-level release receipts. The
inventory is aggregate and structural: it reports what is present, how source
files connect, how much test surface references each module, and which rows
need review. It does not claim that source size or import connectivity proves
scientific validity.

## Contract boundary

`build_module_inventory` discovers Python files below the package source root,
normalizes their paths to forward-slash form, and maps each file to a stable
dotted module identifier. It reads bytes and parses syntax trees locally. It
does not import a discovered module, call a discovered function, load a plugin,
resolve an optional dependency, or execute package initialization from the
discovered source tree.

The public inventory contains:

| Resource | Meaning |
| --- | --- |
| `modules` | One row per discovered Python module with source digest, line counts, static role, family, and symbol/import counts |
| `symbols` | Public and private class/function declarations with source line spans |
| `dependencies` | Local import edges with raw import spelling and explicit resolution state |
| `issues` | Encoding or syntax failures retained as bounded rows |
| `indexes` | Addressed family, role, state, package, symbol, and dependency-target lookups |

Absolute machine paths are not emitted. A packet uses the fixed label
`src/glio_noncode` and content addresses; it does not disclose a workstation
root. Test references are counts of checked-in test files containing a module
identifier, not a claim that every behavior is covered.

## Module record

Every module row contains the following fields:

1. `module_id`: stable dotted name derived from the relative source path;
2. `relative_path`: safe POSIX path below the inspected root;
3. `package`: containing dotted package;
4. `family`: deterministic domain grouping such as `intake`, `reference`,
   `topology`, `evidence`, `workspace`, `release`, or `platform`;
5. `role`: `core`, `domain`, `frontier`, `integration`, or `support`;
6. `state`: `parsed`, `empty`, or `parse_error`;
7. source and symbol counters;
8. import and local-edge counters;
9. `test_reference_count`;
10. a raw source digest and row content address.

The density property is derived from nonblank lines divided by physical lines.
It is included as a view and is not used as a scientific score.

## Static graph

The graph projection groups repeated imports into one edge between two module
vertices. Each edge retains the imported spelling, whether it was relative,
and whether the target was found among the discovered module identifiers.
Unresolved edges are not removed. Nodes contain incoming, outgoing, and
unresolved-outgoing counts. The graph additionally reports:

- root modules with no incoming local edge;
- leaf modules with no outgoing local edge;
- strongly connected cycle components; and
- the total unresolved-edge count.

The graph is suitable for architectural review and change planning. It does
not infer runtime import behavior, optional loading behavior, or packaging
metadata. A relative import that points to a package boundary is represented
using the normalized target that can be checked from the source tree.

## Depth report

`build_module_inventory_depth` produces one explainable assessment per module.
The aggregate percentage is the mean of five bounded static dimensions:

| Dimension | Signal |
| --- | --- |
| Parse | Valid syntax-tree parse state |
| Tests | Number of checked-in test files referencing the module, capped at three |
| Public surface | Number of public classes/functions, capped at eight |
| Dependency resolution | Resolved local imports divided by local imports |
| Implementation scale | Nonblank lines, capped at four hundred |

Rows are classified as `blocked`, `review`, `established`, or `deep`. A parse
failure, missing test reference, or unresolved local import remains visible in
the row blockers. This percentage is a repository maturity indicator only. It
is not a probability, quality certification, clinical interpretation, or
measure of biological evidence.

The report is intentionally transparent so a team can challenge its weighting
or replace it with a different review policy without changing the underlying
inventory addresses.

## Review queue

The queue turns structural signals into next actions. It can contain multiple
items for a single module because a large module can also have unresolved
imports and no test reference. Sort order is deterministic:

1. priority number;
2. severity;
3. stable item identifier.

The queue recognizes parse failures, unresolved imports, absent test
references, large modules, modules with no public symbols, isolated modules,
high fan-out, and dependency cycles. Items are recommendations, not automatic
mutations. The queue never rewrites source files or closes a review item by
deleting it.

## Runtime stages

The staged runtime emits seven addressable receipts:

| Order | Stage | Output |
| ---: | --- | --- |
| 1 | `discover` | module rows |
| 2 | `parse` | parse-state counts |
| 3 | `symbols` | class/function rows |
| 4 | `dependencies` | local import edges |
| 5 | `indexes` | lookup rows |
| 6 | `graph` | nodes, edges, roots, leaves, cycles |
| 7 | `audit` | independent consistency checks |

Stage receipts contain counts and stable addresses. They intentionally omit
wall-clock durations and machine names so repeating a build on the same bytes
does not create a different public result merely because it ran at a
different time or on a different workstation.

## Offline packet

`module-inventory-packet` writes a dedicated directory with one manifest and
ten exact-byte artifacts:

| Artifact | Format | Purpose |
| --- | --- | --- |
| `inventory.json` | JSON | Complete typed inventory |
| `graph.json` | JSON | Dependency graph and cycle summary |
| `modules.csv` | CSV | Flat module table |
| `symbols.csv` | CSV | Flat symbol table |
| `dependencies.csv` | CSV | Flat import-edge table |
| `indexes.csv` | CSV | Flat index table |
| `summary.json` | JSON | Aggregate counts and family rollup |
| `audit.json` | JSON | Independent inventory checks |
| `runtime.json` | JSON | Seven-stage runtime receipt |
| `capabilities.json` | JSON | Offline operation declaration |

The writer uses temporary files and atomic replacement for each declared file.
The verifier checks the manifest shape, exact artifact count, safe relative
paths, unexpected files, byte counts, byte addresses, and the public-key
boundary. A blocked verification result retains the failing check rows so an
operator can inspect the reason without hydrating source files.

## Command line examples

```powershell
glio-noncode module-inventory --format summary --output module-summary.json
glio-noncode module-inventory --resource modules --family topology --format modules-csv --output topology-modules.csv
glio-noncode module-inventory --resource dependencies --module-id glio_noncode.topology_frontier_runtime
glio-noncode module-inventory-depth --format markdown --output module-depth.md
glio-noncode module-inventory-review --format markdown --output module-review.md
glio-noncode module-inventory-graph --format json --output module-graph.json
glio-noncode module-inventory-observability --format metrics-csv --output module-metrics.csv
glio-noncode module-inventory-packet --destination module-inventory-packet
glio-noncode module-inventory-packet-verify module-inventory-packet
glio-noncode module-inventory-packet-query module-inventory-packet --resource modules --family evidence
```

Use `--source-root` and `--test-root` only when inspecting an explicitly
scoped local source snapshot. The default command targets the repository
package itself. The packet is the preferred handoff when a second process or
offline reviewer must inspect the result without access to the source tree.

## HTTP surface

The loopback service exposes the same read-only projections:

```text
GET /v1/module-inventory
GET /v1/module-inventory/query?resource=modules&family=evidence
GET /v1/module-inventory/schema
GET /v1/module-inventory/capabilities
GET /v1/module-inventory/audit
GET /v1/module-inventory/depth
GET /v1/module-inventory/depth/query?tier=review
GET /v1/module-inventory/graph
GET /v1/module-inventory/graph/query?module_id=glio_noncode.evidence_release_frontier_runtime
GET /v1/module-inventory/observability
GET /v1/module-inventory/packet
GET /v1/module-inventory/packet/verify?directory=module-inventory-packet
```

Schema and capability routes are cheap declarations and do not scan the
source tree. Inventory-producing routes are bounded in each returned page but
may need to parse the full package before the first page is available. Clients
should cache a packet or use the packet query route for repeated exploration.

## Public-boundary rules

The inventory is designed to be safe for a public repository:

- source payloads are represented by digests, not copied into rows;
- absolute roots and workstation-specific paths are excluded;
- rows carry no personal, routing, attribution, or model metadata;
- unresolved source structure remains an explicit state;
- public schema and capability declarations are audited with the rest of the
  service surface; and
- packet verification fails closed on unexpected files or altered bytes.

The inventory does not modify the source tree, install dependencies, contact a
network service, or infer data that is not present in the scoped files.

## Performance and limits

The contract caps the default public surface at 8,000 modules, 120,000 symbols,
240,000 dependency rows, and 20,000 issue rows. Query pages default to fifty
rows and cannot exceed five hundred. Source traversal is lexical and symlink
files are skipped. A source root that exceeds a limit is rejected before a
partial accepted inventory can be emitted.

The implementation deliberately keeps parsing and dependency resolution in
memory because the repository is a local-first workbench. A future persisted
adapter may cache source digests and AST-derived rows, but it must preserve
the same row addresses, ordering, issue visibility, and public projection.

## Verification checklist

Before accepting a module packet, CI or an operator should confirm:

1. the inventory summary has the expected module and line counts;
2. the parse audit has no hidden failures;
3. unresolved dependency rows are either expected or routed to review;
4. the graph cycle list has been reviewed for intentional boundaries;
5. the depth report is treated as a static signal only;
6. test-reference gaps have an explicit next action;
7. packet verification passes after copying the directory; and
8. a repeated build produces the same inventory, graph, and packet addresses.

This control plane is complementary to domain evidence gates. It describes
the repository’s implementation shape so each module can be inspected deeply;
it does not replace domain fixtures, scientific review, or independent
validation.
