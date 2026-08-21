# Domain 05 C13-C16 release format

The release boundary is produced only after the complete quality gate and a
runtime result exist. The release manifest is content-addressed and contains:

| Field | Meaning |
| --- | --- |
| `release_id` | stable release identity |
| `release_version` | fixture and contract version, currently `2026.08.d05-c13-c16.v1` |
| `fixture_id` | exact aggregate fixture identity |
| `context_key` | six-part context boundary |
| `operation_ids` | all four C13-C16 operations |
| `source_ids` | source receipt closure |
| `bundle_address` | immutable bundle address |
| `quality_address` | quality gate report address |
| `runtime_address` | runtime result address |
| `status` | `accepted` or `rejected` |
| `acceptance_statement` | descriptive scope and control statement |
| `content_address` | manifest address over all preceding fields |

## Publication conditions

The bundle is accepted only when source audit, evaluation, replay, scenarios,
policy, lineage, reconciliation, and schema validation pass. The runtime must
retain the requested context, and the release status is rejected when the
quality gate is rejected. Empty snapshot output is an abstention and cannot
become a published absence claim. Context drift and invalid metadata never
enter a published snapshot.

## Sanitized exports

The release surface supports:

- JSON bundle and manifest output for machine inspection;
- receipt CSV with state, issue, count, and address fields;
- review CSV with priority and remediation action;
- review Markdown for human inspection;
- operation metrics CSV with balanced positive/control counts;
- nine-stage trace JSON with artifact addresses and event sequence.

Exports do not contain raw fixture payload collections or parser input text.
Each export can receive a separate byte, line, and content-address receipt via
`frontier_atlas_export_receipt`.

## Commands

```powershell
python -m glio_noncode build-frontier-atlas-bundle examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-bundle.json
python -m glio_noncode build-frontier-atlas-release examples/frontier-atlas-evidence-pipeline-accepted.json --run-id frontier-atlas-release --output frontier-atlas-release.json
python -m glio_noncode frontier-atlas-trace examples/frontier-atlas-evidence-pipeline-accepted.json --run-id frontier-atlas-trace --output frontier-atlas-trace.json
python -m glio_noncode export-frontier-atlas-review-markdown examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-review.md
```

The release manifest is an evidence receipt, not a clinical report. External
validation, calibration, prospective performance, and institutional review are
outside this local public aggregate boundary.
