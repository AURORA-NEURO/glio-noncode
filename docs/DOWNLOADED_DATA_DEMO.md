# Downloaded data boundary demo

This demo accepts a ZIP supplied by a user or downloaded from a trusted source. It reads the archive in place and creates a structural catalog before any downstream analysis is attempted.

The adapter is deliberately narrow:

- JSON, JSON Lines, NDJSON, CSV, TSV, YAML, and YML members are eligible.
- Prose, source code, bytecode, cache directories, test directories, and starter-code directories are excluded from the catalog.
- ZIP member paths are checked for traversal, absolute paths, encrypted entries, and symbolic links.
- Each included member is bounded by size, row count, and field count limits.
- JSON and delimited files are parsed only for shape, field names, and record counts. Values are not copied into the catalog.
- Every member digest, catalog digest, audit check, and mapping replay is independently verifiable.

## Run against the supplied download

From the repository root:

```text
python examples/downloaded_data_catalog_demo.py C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip artifacts/downloaded-data-demo
```

The output directory contains:

| File | Purpose |
| --- | --- |
| `catalog.json` | Canonical catalog with member structure and content addresses |
| `catalog.csv` | One row per included structured member |
| `catalog.md` | Human-readable review table |
| `audit.json` | Twelve independent structural checks |
| `audit.md` | Human-readable audit receipt |
| `summary.json` | Compact demo result for scripts and CI |

The supplied product bundle is treated as downloaded input only. Its prose and starter material are not used as repository code or as an implementation framework. The demo therefore proves the data-ingestion boundary without importing any old repository.

## Expected result shape

The current supplied bundle contains structured members from the start-here, baseline, product, capability, data, platform, evaluation, roadmap, research, and QA areas. The exact digest is a function of the bytes and remains stable when the same ZIP is rerun.

The summary reports:

```json
{
  "audit_passed": true,
  "replay_address_matches": true,
  "structured_member_count": 25,
  "json_count": 11,
  "delimited_count": 13,
  "yaml_count": 1
}
```

The count is informational and will change if the downloaded ZIP changes. The audit and replay booleans are the acceptance boundary.

## Decision-ledger relationship

The downloaded-data catalog is the safe intake surface. A canonical archive-registry federation plan can then be passed to the decision-ledger runtime:

```text
python -m glio_noncode registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-decision-ledger --input path/to/plan.json --destination artifacts/decision-ledger --format markdown
```

That second stage is explicit about operational decisions. No-op operations receive `not-required`; planned operations remain `pending` until a caller supplies a disposition; `approve`, `hold`, `reject`, and `defer` are all recorded as new content-addressed ledger states.

## Review sequence

1. Run the downloaded-data demo.
2. Review `catalog.md` and confirm the included members are the intended structured inputs.
3. Review `audit.md`; all checks must pass.
4. Retain `catalog.json` and `audit.json` beside the source checksum.
5. Feed only a verified canonical plan into the decision-ledger command.
6. Diff pending and approved ledgers before any external executor is allowed to act.
