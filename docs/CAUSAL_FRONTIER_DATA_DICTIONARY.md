# Domain 11 data dictionary

## Reading this dictionary

The causal frontier stores evidence as immutable, content-addressed records.
This dictionary defines the fields that a reviewer sees in the fixture,
execution, quality, runtime, and release artifacts. A field can be present for
integrity without being a scientific conclusion.

## Identity fields

| Field | Present on | Definition | Review question |
| --- | --- | --- | --- |
| `fixture_id` | fixture, evaluation | stable fixture name | is this the intended fixture? |
| `fixture_version` | fixture, evaluation | pinned behavior version | did behavior change? |
| `record_id` | record, execution, row | one operation case | can the result be traced? |
| `operation` | record, execution, view | one of C13-C16 | which adapter ran? |
| `role` | record, execution, view | positive or control | is this a success path or boundary test? |
| `context_key` | fixture, record, execution | exact scope | was scope preserved? |
| `content_address` | all receipts | canonical hash | can the object be compared? |

## Boundary fields

| Field | Definition |
| --- | --- |
| `evidence_boundary` | public aggregate and non-patient scope |
| `source_ids` | references to source receipts |
| `source_kind` | functional, topology, archive, literature, or program context |
| `scope` | why this source is included |
| `allowed_uses` | uses allowed by the release manifest |
| `excluded_uses` | uses explicitly outside the module boundary |

The boundary fields travel with release outputs so a downstream consumer does
not need to infer them from module names.

## Input fields

`input_records` is an array. The evaluator requires it to be a list so an object
or scalar cannot be mistaken for one row. Empty input is allowed only for
negative controls and is expected to produce an empty-input issue.

Numeric fields are validated before calculation. Bounded fields accept values
from 0 through 1. The uncertainty field is finite and nonnegative. IDs are
trimmed, required where declared, and retained in output.

## C13 dictionary

| Field | Definition |
| --- | --- |
| `hypothesis_id` | local identity for a posterior component |
| `prior` | declared bounded prior |
| `likelihood` | declared bounded likelihood contribution |
| `measurement` | declared bounded measurement contribution |
| `dependency_penalty` | bounded downweight for dependence |
| `raw_posterior` | component product after penalty |
| `normalized_posterior` | raw value divided by total mass |
| `top_hypothesis_id` | identity with highest normalized value |

The C13 output is descriptive. It does not encode a causal graph or identify a
true mechanism.

## C14 dictionary

| Field | Definition |
| --- | --- |
| `driver_id` | local identity for a driver hypothesis |
| `evidence_ids` | named evidence paths |
| `evidence_support` | bounded support input |
| `prior` | bounded driver prior |
| `posterior` | normalized support-prior product |
| `rank` | deterministic order by score then ID |
| `top_driver_id` | first ranked driver identity |
| `minimum_support` | explicit review threshold |

The C14 output preserves alternatives. A top rank is not a declaration that an
entity is a biological driver.

## C15 dictionary

| Field | Definition |
| --- | --- |
| `prediction_id` | local prediction identity |
| `score` | bounded score input |
| `uncertainty` | finite uncertainty input |
| `threshold` | maximum of minimum score and twice uncertainty |
| `abstained` | boolean decision boundary |
| `accepted_ids` | IDs above the boundary |
| `abstained_ids` | IDs withheld by the boundary |
| `issues` | one or more reasons for review |

The consumer must preserve both accepted and abstained IDs. Dropping abstained
rows changes the meaning of the report.

## C16 dictionary

| Field | Definition |
| --- | --- |
| `dossier_id` | manifest identity |
| `hypothesis_ids` | declared identities bound by the manifest |
| `evidence_addresses` | receipts bound by the manifest |
| `top_hypothesis_id` | optional identity inside the set |
| `dossier_address` | content address of the manifest |
| `state` | published for a valid manifest |

The dossier has no clinical conclusion field. Any prose added by a downstream
system is outside this artifact and must carry its own review boundary.

## Execution fields

| Field | Definition |
| --- | --- |
| `state` | supported, partial, invalid, or published |
| `issue_codes` | sorted exact issue vocabulary |
| `output` | operation-specific JSON object |
| `error` | validation text when state is invalid |
| `accepted` | derived property for supported/published without error |

An invalid receipt remains useful for controls because it proves the boundary
responds to malformed input. It should not be converted into null output.

## Evaluation fields

| Field | Definition |
| --- | --- |
| `executions` | one receipt per record |
| `checks` | seven record checks plus eight globals |
| `positive_record_ids` | IDs with positive role |
| `control_record_ids` | IDs with control role |
| `passed_checks` | count of passing checks |
| `failed_check_ids` | exact failed check IDs |
| `accepted` | all checks pass |

The check body retains expected and observed values. This makes a mismatch
diagnostic without requiring a second run.

## Lineage fields

| Field | Definition |
| --- | --- |
| `edge_id` | stable edge identity |
| `parent_address` | source or fixture parent |
| `child_address` | execution receipt |
| `edge_kind` | source-to-execution or fixture-to-execution |
| `operation` | operation associated with edge |
| `explanation` | readable edge rationale |

## Metric fields

| Field | Definition |
| --- | --- |
| `metric_id` | stable metric identity |
| `operation` | all or one operation |
| `value` | ratio or normalized metric |
| `numerator` | counted passing or qualifying rows |
| `denominator` | counted eligible rows |
| `interpretation` | bounded process meaning |

Always read numerator and denominator alongside value. A ratio without its
denominator can hide the small fixture size.

## Quality fields

| Field | Definition |
| --- | --- |
| `check_id` | named gate check |
| `passed` | boolean check result |
| `severity` | blocking in the current gate |
| `observed` | measured value |
| `required` | required value |
| `rationale` | why the check exists |
| `blocking_check_ids` | failures that prevent acceptance |

## Runtime fields

| Field | Definition |
| --- | --- |
| `stage_id` | ten-stage runtime name |
| `sequence` | one-based execution order |
| `duration_ms` | observed elapsed time |
| `output_address` | stage result address |
| `detail` | stage purpose |

Runtime timing is diagnostic. It must not enter deterministic operation
addresses.

## Release fields

| Field | Definition |
| --- | --- |
| `release_id` | release identity |
| `version` | release version |
| `state` | draft, review, ready, blocked, or published |
| `bundle_address` | bundle receipt |
| `quality_gate_address` | gate receipt |
| `replay_address` | replay receipt |
| `checks` | four release checks |

## Review conventions

Use exact IDs and addresses in comments. Refer to issue codes rather than
paraphrasing them. Preserve the context key in exports. If a field is missing,
record the missing field as a boundary issue rather than manufacturing a default
scientific value.

## Data dictionary maintenance

Update this dictionary when a field is added, removed, renamed, or reinterpreted.
Update the schema manifest, contract, positive/control fixture, evaluator,
tests, depth audit, and release note in the same change. A field dictionary that
drifts away from the runtime is a release defect.
