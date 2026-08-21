# C09-C12 schema catalog

The schema registry is the typed shape contract between the adapter receipts
and downstream review surfaces. It is separate from the scientific adapter
semantics: a schema can say that a field is present without claiming that the
field is biologically sufficient.

## Shared input fields

Every operation accepts the following declared fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `input_text` | serialized aggregate text | Local, deterministic fixture records |
| `input_format` | enum | Parser format, currently JSON for this fixture |
| `source_id` | string | Local source receipt identity |
| `source_version` | string | Version of the local source-shaped payload |
| `context_key` | string | Exact genome, disease, age, cell-state, territory, and treatment context |

Each operation adds its own numeric controls. All controls are explicit in the
record payload and are preserved in the content-addressed record object.

## Output fields

### C09 open chromatin

The output contains adapter `state`, accepted observation and interval counts,
signal spread tuples, replicate cardinalities, and issue codes. Signal spread
is a descriptive disagreement measure. It is not a calibrated accessibility
probability, activity estimate, or causal effect.

### C10 methylation

The output contains adapter `state`, observation and interval counts, coverage
totals, fraction spreads, and issue codes. Missing coverage remains visible.
The schema does not contain a biological-negative field, so zero coverage cannot
be silently interpreted as unmethylated or inactive.

### C11 regulatory role

The output contains adapter `state`, classification count, role tuples, missing
channel tuples, declared target-gene IDs, and issue codes. A role tuple may
contain more than one role. The schema therefore preserves multi-role ambiguity
instead of forcing an ordered label.

### C12 super-enhancer candidates

The output contains adapter `state`, constituent and candidate counts, candidate
IDs, declared target-gene IDs, and issue codes. Candidate IDs describe ranked
interval groupings. The schema deliberately has no causal or clinical-effect
field.

## Validation floors

`validate_atlas_alpha_evidence_schema` checks:

1. all four operation schemas exist;
2. the fixture context is retained on every receipt;
3. each operation has one positive and three controls;
4. supported and review states use the declared state vocabulary;
5. sanitized summaries expose every declared output field;
6. observed issues use the public review vocabulary; and
7. prohibited interpretation terms do not appear in adapter summaries.

The schema manifest is content-addressed and can be emitted with:

```powershell
glio-noncode atlas-alpha-evidence-schema --output atlas-alpha-schema.json
```

Schema acceptance is necessary but not sufficient for release. The quality
gate also requires source closure, fixture evaluation, deterministic replay,
scenario coverage, policy acceptance, lineage, reconciliation, metrics, and a
content-addressed bundle.
