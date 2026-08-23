# Validation-release frontier data dictionary

## Shared identity

| Field | Type | Required | Meaning | Boundary |
| --- | --- | ---: | --- | --- |
| `fixture_id` | string | yes | immutable fixture identity | replay key |
| `fixture_version` | string | yes | contract version | migration key |
| `context_key` | string | yes | genome, disease, age, state, territory, treatment tuple | exact-match join |
| `record_id` | string | yes | operation-row identity | duplicate-free |
| `operation` | enum | yes | one of C13-C16 operation families | typed dispatch |
| `role` | enum | yes | `positive` or `control` | expected-state boundary |
| `source_ids` | array[string] | yes | public receipt links | provenance |
| `content_address` | SHA-256 string | yes | canonical record address | replay/integrity |

The fixture context is
`GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment`. The context is
not inferred from free text and is never silently transported.

## Source receipts

| Field | Type | Meaning |
| --- | --- | --- |
| `source_id` | string | stable public portal identity |
| `title` | string | portal label |
| `uri` | HTTPS string | public provenance anchor |
| `scope` | string | declared reference scope |
| `version` | string | receipt version label |
| `content_address` | SHA-256 string | receipt identity |

The fixture links NCBI, Ensembl, ENCODE, Addgene, and the NCI Genomic Data
Commons. The runtime does not fetch the portals; the links are provenance
anchors and the checked-in fixture is the replay input.

## C13 fields

| Field | Type | Meaning |
| --- | --- | --- |
| `target_id` | string | target or guide identity |
| `on_target_score` | float 0-1 | supplied target score |
| `off_targets` | array[object] | candidate burden observations |
| `candidate_id` | string | candidate identity |
| `score` | float 0-1 | supplied candidate score |
| `weight` | positive float | declared burden weight |
| `review_threshold` | float 0-1 | review boundary |
| `blocking_threshold` | float 0-1 | blocking boundary |

The output contains maximum and weighted burden, descriptive specificity,
tier, and count. It does not contain a clinical recommendation.

## C14 fields

| Field | Type | Meaning |
| --- | --- | --- |
| `plan_id` | string | planning identity |
| `budget` | positive float | total planning budget |
| `experiments` | array[object] | candidate experiments |
| `experiment_id` | string | experiment identity |
| `cost` | positive float | declared resource cost |
| `information_gain` | float 0-1 | declared planning value |
| `risk_reduction` | float 0-1 | declared planning value |
| `prerequisites` | array[string] | dependency IDs |

Cycles and missing dependencies remain explicit failure states. The planner
does not allocate specimens, schedule people, or execute experiments.

## C15 fields

| Field | Type | Meaning |
| --- | --- | --- |
| `package_id` | string | package identity |
| `experiments` | array[object] | experiment manifest rows |
| `controls` | array[object] | control manifest rows |
| `protocols` | array[object] | protocol receipt rows |
| `experiment_id` | string | experiment identity |
| `control_id` | string | control identity |
| `protocol_id` | string | protocol identity |
| `objective` | string | declared planning objective |
| `readout` | string | declared readout label |

File projections contain row counts and addresses. Raw protocols are not
executed by the package builder.

## C16 fields

| Field | Type | Meaning |
| --- | --- | --- |
| `claims` | array[object] | known claim records |
| `claim_id` | string | claim identity |
| `state` | string | prior declared claim state |
| `results` | array[object] | incoming result records |
| `result_id` | string | result identity |
| `claim_state` | string | result-declared state |
| `effect_direction` | string | declared direction label |
| `effect_size` | numeric | supplied descriptive value |
| `evidence_address` | SHA-256 string | result evidence receipt |

An evidence address closes provenance but does not validate the underlying
measurement.

## Output rules

Every operation returns a state, normalized issue codes, a safe projection,
and a content address. Outputs may contain IDs, counts, states, thresholds,
and receipt references. They must not contain passwords, API keys, signing
secrets, access tokens, participant identifiers, or raw site rows.
