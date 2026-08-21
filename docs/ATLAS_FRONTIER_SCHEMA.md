# Domain 05 C13-C16 typed schema

The schema registry declares one input and one output contract for each
operation. All contracts require the following input fields:

| Field | Type | Interpretation |
| --- | --- | --- |
| `input_text` | serialized aggregate text | local source-shaped records |
| `input_format` | enum | explicit parser format |
| `source_id` | string | source receipt identity |
| `source_version` | string | source-shaped version |
| `context_key` | string | exact six-part context |

Every output contains a state, counts or addresses appropriate to the
operation, and bounded issue codes. Review states are `review`,
`out_of_domain`, `abstained`, and `invalid`; `accepted` and `published` are
success states with operation-specific meaning.

## Operation outputs

### C13 boundary atlas

`state`, `observation_count`, `strong_boundary_ids`, `review_ids`, and
`issue_codes`. Low support and invalid intervals remain review outcomes.

### C14 hotspot atlas

`state`, `observation_count`, `supported_ids`, `review_ids`, and `issue_codes`.
Independent source count and direction concordance are retained as evidence
features, not mechanistic claims.

### C15 evidence tier

`state`, `decision_count`, `high_confidence_ids`, `review_ids`,
`evidence_tiers`, and `issue_codes`. Tier labels are review labels and are not
probabilities.

### C16 snapshot publication

`state`, `record_count`, `records_address`, `snapshot_address`,
`schema_version`, and `issue_codes`. Empty records abstain; only non-empty,
context-qualified records with valid snapshot metadata can publish.

## Validation requirements

The schema validator checks four schemas, operation coverage, exact fixture
context, one positive plus three controls per operation, declared states,
declared summary outputs, bounded issue vocabulary, and prohibited-claim
absence. The accepted fixture currently emits 23 passing schema checks.

```powershell
python -m glio_noncode frontier-atlas-schema examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-schema.json
```

The schemas intentionally prohibit causal, mechanistic, clinical, treatment,
and probability interpretations at this boundary. A downstream system must
retain the schema version, context, source receipts, issue codes, and content
addresses when transporting an accepted output.
