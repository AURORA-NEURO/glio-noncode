# Domain 01 identity evidence gate

This runbook describes the public aggregate evidence boundary for Domain 01
capabilities C09-C12. It is a software and data-governance gate. It is not a
specimen-authentication procedure, clinical interpretation, consent decision,
or institutional custody attestation.

## Scope and module map

The gate exercises the existing operations in `identity_beta.py` through a
separate, deterministic evidence layer.

| Capability | Operation | Primary question | Stronger state |
| --- | --- | --- | --- |
| GNC-D01-C09 | `VariantEquivalenceResolver` | Which supplied records resolve to one normalized identity? | `supported` |
| GNC-D01-C10 | `DuplicateAliasReconciler` | Which records share identity or collide through aliases? | `supported` |
| GNC-D01-C11 | `BatchSampleIdentityChecker` | Are declared mappings complete and non-conflicting? | `supported` |
| GNC-D01-C12 | `ChainOfCustodyCapture` | Do artifact events preserve order and hash continuity? | `supported` |

| Layer | Module | Responsibility |
| --- | --- | --- |
| Public data | `identity_public_data.py` | Parse receipts, context, records, controls, and privacy boundary |
| Execution | `identity_fixture_eval.py` | Run positive records and negative controls through real operations |
| Replay | `identity_replay.py` | Compare fixture identity, context, sources, and count floors |
| Contracts | `identity_contracts.py` | Publish required inputs, outputs, states, and external boundaries |
| Scenarios | `identity_scenario_matrix.py` | Execute every positive and review transition independently |
| Quality | `identity_quality_gate.py` | Reconcile all component receipts into one verdict |
| Bundle | `identity_bundle.py` | Export compact JSON, CSV, or Markdown receipts |

The fixture is `examples/identity-public-aggregate.json`. It contains public
aggregate identifiers, declared hashes, and deterministic software inputs. It
does not contain patient-level values.

## Public data boundary

Every source receipt must declare:

- a stable source ID;
- an HTTPS URL;
- a source version;
- the exact six-field context key;
- `public_aggregate=true`;
- `patient_level_data=false`; and
- a license or access-scope description.

Fixture provenance must declare `data_scope=public_aggregate`,
`patient_level_data=false`, a deterministic creation timestamp, and an
`evidence_boundary` sentence describing claims that are deliberately not made.

The audit records paths and issue codes, not restricted values. It retains a
review state rather than dropping an offending row.

The audit rejects or reviews:

- missing or mismatched fixture versions;
- absent source receipts;
- duplicate source, record, or control IDs;
- positive/control identity collisions;
- source or operation context mismatches;
- unknown source IDs;
- non-public or patient-level source declarations;
- missing aggregate-scope declarations;
- missing evidence-boundary text; and
- restricted field names such as patient, donor, medical record, MRN, email,
  phone, password, token, or secret.

## Exact context

The checked-in context is:

```text
GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment
```

The six fields are ordered and required:

1. `genome_build`
2. `disease_class`
3. `age_group`
4. `cell_state`
5. `territory`
6. `treatment_phase`

The context key is used for source receipts, operation envelopes, replay
expectations, quality checks, and bundle metadata. A query that matches an
identity only outside the requested build or context returns `out_of_domain`;
it is not silently projected into the active context.

## Positive operation records

The fixture contains one positive record per operation family.

| Record | Input shape | Expected state | Proof retained |
| --- | --- | --- | --- |
| `equivalence:rs121913502` | Two source-qualified records and one alias query | `supported` | normalized key, record IDs, aliases, methods, sources, address |
| `reconciliation:rs121913502` | Two records with one normalized identity | `partial` | duplicate IDs, groups, aliases, source IDs, warning |
| `sample:public-aggregate-01` | Two complete observations for one mapping | `supported` | mappings, versions, observations, address |
| `custody:public-aggregate-artifact-01` | Received, validated, exported events | `supported` | order, hashes, chain digest |

`partial` is expected for the reconciliation record. It means duplicate source
records were retained and need stewardship. It does not mean one record was
discarded.

### C09: equivalence resolution

The positive record exercises:

- case and `chr` normalization;
- build-qualified identity;
- explicit alias lookup;
- two source records resolving to one key;
- source and version retention; and
- separate record IDs for one normalized identity.

The resolver does not rewrite source records, choose a preferred database, or
claim sequence equivalence beyond supplied normalized fields. RefGet-backed
truth sets and broad structural equivalence remain separate release gates.

### C10: duplicate and alias reconciliation

The positive record exercises:

- grouping by normalized build, contig, interval, allele, and kind;
- preservation of every record ID;
- preservation of every source ID;
- sorted group membership;
- explicit aliases; and
- the expected duplicate review state.

The operation never selects a winning record. An alias shared by competing
normalized identities becomes an `ambiguous` group and remains visible.

### C11: batch/sample identity

The positive record exercises:

- required batch, sample, and subject fields;
- two observations with one consistent mapping;
- source version retention;
- observation raw-hash retention;
- batch-to-sample projection; and
- sample-to-subject projection.

The result describes declared metadata only. A consistent mapping does not
authenticate a specimen, establish consent, or prove biological identity.

### C12: custody capture

The positive record exercises:

- a first `received` event;
- predecessor links from later events;
- input-hash continuity from the previous output;
- deterministic event ordering;
- per-artifact chain digests; and
- a global content address.

The operation records supplied transitions. It does not create signatures,
verify an institutional system, or infer a physical transfer absent from input.

## Negative controls

Eight controls prove that the operations preserve review boundaries.

| Control | Operation | Expected state | Required signal |
| --- | --- | --- | --- |
| `equivalence:out-of-domain-build` | equivalence | `out_of_domain` | `out_of_domain` |
| `equivalence:absent-query` | equivalence | `absent` | `absent` |
| `reconciliation:ambiguous-alias` | reconciliation | `ambiguous` | `ambiguous_aliases` |
| `reconciliation:duplicate-record-id` | reconciliation | `abstained` | `validation_error` |
| `sample:cross-subject` | sample | `contradictory` | `sample_maps_to_multiple_subjects` |
| `sample:missing-subject` | sample | `contradictory` | `missing_identity_field`, `missing_observation_ids` |
| `custody:broken-link` | custody | `contradictory` | `broken_previous_event_link`, `hash_continuity_gap`, `missing_previous_event` |
| `custody:invalid-timestamp` | custody | `abstained` | `validation_error` |

Malformed controls that raise `ValidationError` become serializable abstention
receipts with `error_code=validation_error`. The process does not crash and a
malformed input is never treated as a successful operation.

## Fixture evaluator

Run:

```powershell
python -m glio_noncode evaluate-identity-fixture `
  examples/identity-public-aggregate.json `
  --output identity-fixture-report.json
```

The evaluator emits 37 checks in stable order:

1. one public-data boundary check;
2. four positive state checks;
3. four positive trace checks;
4. four positive address checks;
5. four positive signal checks;
6. eight negative state checks;
7. eight negative signal checks;
8. one positive-record floor;
9. one negative-control floor;
10. one repeated-evaluation determinism check; and
11. one restricted-output check.

The evaluator serializes operation outputs through `to_dict()` and requires a
content address in every operation receipt. It does not copy raw fixture
payloads into the compact bundle layer.

The report contains fixture identity, exact context, sorted source IDs, the
data audit, positive receipts, negative receipts, every expected/observed
check, passed and failed IDs, the evidence-boundary sentence, and a report
content address.

## Scenario matrix

Run:

```powershell
python -m glio_noncode evaluate-identity-scenarios `
  examples/identity-public-aggregate.json `
  --output identity-scenarios.json
```

The matrix derives twelve scenarios directly from the fixture: four positive
and eight review. It calls the same adapters used by the evaluator. A scenario
passes only when its observed state equals the declaration and every required
signal is present.

Scenario receipts retain scenario ID, class, operation kind, public identifier,
expected state, observed state, observed signal set, pass/fail, operation
address, and a compact detail sentence. Changing a positive query, a review
expectation, or a required signal produces a review matrix result.

## Replay integrity

Run:

```powershell
python -m glio_noncode replay-identity-fixtures `
  examples/identity-public-aggregate.json `
  --required-context-key "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment" `
  --output identity-replay.json
```

Replay verifies:

- at least one path;
- expected fixture ID;
- exact expected context;
- exact expected source receipt set;
- accepted operation evaluation;
- the 37-check floor;
- the four-positive-record floor;
- the eight-negative-control floor;
- unique fixture IDs; and
- no duplicate public identities across distinct cases.

Copying a fixture to another path does not create a new case. The repeated
identity is reported as a replay failure.

## Operation contracts

Run:

```powershell
python -m glio_noncode identity-contracts --output identity-contracts.json
```

The registry publishes four contracts:

| Capability | Required input | Primary outputs | Review states |
| --- | --- | --- | --- |
| C09 | `records`, `query` | key, records, methods, sources | ambiguous, absent, out-of-domain, abstained |
| C10 | `records` | groups, duplicates, aliases | partial, ambiguous, abstained |
| C11 | `observations` | mappings, issues, missing IDs | partial, contradictory, abstained |
| C12 | `events` | chains, issues, counts | contradictory, abstained |

Contract declarations make expectations inspectable by callers. They do not
claim that an operation is scientifically valid.

## Combined quality gate

Run:

```powershell
python -m glio_noncode identity-quality-gate `
  examples/identity-public-aggregate.json `
  --output identity-quality.json
```

The twelve gate checks are:

1. fixture evaluation passes;
2. fixture check floor is 37;
3. public-data audit is accepted;
4. replay integrity passes;
5. positive record count is four;
6. negative-control count is eight;
7. scenario count is twelve and all pass;
8. contract count is four;
9. context keys match;
10. source sets match;
11. repeated evaluation has one address; and
12. combined receipts have no restricted field names.

Exit code zero requires every check. A review report is still serialized so
failed IDs and component receipts can be inspected.

## Compact evidence bundle

Run:

```powershell
python -m glio_noncode build-identity-bundle `
  examples/identity-public-aggregate.json `
  --output identity-bundle.json
```

The bundle contains twelve compact entries: four positive and eight review.
Each entry retains only stable entry ID, class, operation kind, state, source
ID, public identifier, and operation content address. Raw variant payloads,
sample observations, custody event metadata, and fixture provenance values are
not copied into entries.

JSON, CSV, and Markdown render the same entry data. JSON also contains
component summaries and contract metadata. The bundle address is computed from
the body before derived convenience fields such as counts and `accepted` are
added.

Verify a JSON bundle:

```python
import json
from pathlib import Path

from glio_noncode.identity_bundle import IdentityEvidenceBundleBuilder

payload = json.loads(Path("identity-bundle.json").read_text(encoding="utf-8"))
assert IdentityEvidenceBundleBuilder.verify(payload)
```

Changing an entry, context, source set, component receipt, contract manifest,
or boundary invalidates the address. Changing only derived count fields does
not.

## CI and promotion

Actions runs, for each supported Python version:

1. full unit tests;
2. public identity data audit;
3. fixture evaluator;
4. replay integrity;
5. quality gate;
6. scenario matrix;
7. contract manifest; and
8. compact bundle export.

Before C09-C12 are called locally verified, run the full test suite, inspect
all 37 evaluator checks, inspect all twelve scenarios, verify the bundle
address, confirm source versions and URLs remain declared, and confirm no
patient-level data or restricted values entered a report.

Verified here means the local public aggregate software contract passes. RefGet
identity truth, specimen authentication, consent review, signatures, and
institutional custody systems remain separate validation work.

## Extension checklist

An additional identity scenario must:

1. use a new stable record or control ID;
2. declare an existing operation kind or add a contract first;
3. retain an HTTPS public source receipt;
4. use the exact context or explicitly test context review;
5. declare expected state and required signals;
6. add positive and negative tests for its failure mode;
7. update evaluator, replay, scenario, quality, and bundle floors;
8. preserve deterministic timestamps and hashes;
9. avoid copying restricted values into reports; and
10. update CLI, CI, and documentation together.

External databases, sequence services, specimen systems, and signature systems
must be separately versioned source and release gates. A local fixture must not
imply that an unavailable dependency was queried.
