# D02 Intake Architecture: deep implementation contract

Status: implemented, deterministic, and release-gated.

This document describes the D02 intake boundary in enough detail for a new
developer to execute it, inspect every receipt, reproduce the canonical
fixture, and diagnose a held control without reading private source data.

## 1. Boundary and non-goals

D02 is the public-aggregate intake layer for variant identity and source
admission. It converts bounded public reference records into addressed receipts
that later modules can join. It does not make a clinical claim, assign a
patient-level identity, infer treatment response, or silently promote a held
control.

The canonical context is:

```text
GRCh38|glioma|adult|aggregate|public_reference|pre_treatment
```

The deliberate control context is:

```text
GRCh38|glioma|adult|aggregate|public_reference|post_treatment
```

The control context is useful because it exercises a boundary decision while
remaining close enough to the canonical context to catch accidental string
normalization or permissive matching. A control is retained for review; it is
not deleted and it is not rewritten into the canonical context.

## 2. Closed denominators

| Quantity | Value | Meaning |
| --- | ---: | --- |
| public sources | 6 | HTTPS source receipts joined by stable identifiers |
| operations | 16 | ordered intake capabilities |
| scenarios per operation | 4 | positive, foreign context, malformed input, duplicate identity |
| cases | 64 | 16 operations multiplied by 4 scenarios |
| positive cases | 16 | one accepted path per operation |
| held controls | 48 | three controls per operation |
| validation planes | 7 | ingestion, parsing, normalization, identity, policy, provenance, release |
| runtime stages | 24 | ordered execution and release stages |
| evaluation checks | 458 | 7 per case plus 10 fixture checks |
| compliance checks | 12 | privacy, scope, transport, release, and address checks |
| quality checks | 24 | independent runtime quality gate |
| offline artifacts | 8 | bundle projections with separate content addresses |

Every denominator is represented in source code, the test suite, and the
runtime closure at `data/intake-architecture-d02-runtime-closure.json`.

## 3. Public source registry

| Source ID | Purpose | Transport | Scope |
| --- | --- | --- | --- |
| `ncbi-variation` | public variation index receipt | HTTPS | public aggregate |
| `ncbi-reference-assembly` | GRCh38 assembly receipt | HTTPS | public aggregate |
| `ga4gh-vrs` | variation representation contract | HTTPS | public aggregate |
| `ensembl-variation` | public variation documentation | HTTPS | public aggregate |
| `ucsc-encode-reference` | regulatory reference portal | HTTPS | public aggregate |
| `repository-controls` | local release control receipts | HTTPS | public aggregate |

Sources are not fetched as part of the deterministic runtime. Their URI,
version, scope, and content address are recorded so an external acquisition
step can be audited separately. This keeps replay offline and makes network
availability irrelevant to the acceptance decision.

## 4. Operation catalog

The plan is a single dependency-safe chain. Each operation has an operation ID,
capability ID, ordinal, plane, input contract, output contract, source join,
and review-on-control policy.

| Ordinal | Operation | Plane | Input contract | Output contract |
| ---: | --- | --- | --- | --- |
| 1 | case manifest ingestion | ingestion | `case.manifest.input.v1` | `case.manifest.receipt.v1` |
| 2 | VCF/BCF/gVCF parsing | parsing | `variant.bytes.input.v1` | `variant.parse.receipt.v1` |
| 3 | regulatory track parsing | parsing | `regulatory.track.input.v1` | `regulatory.track.receipt.v1` |
| 4 | VRS normalization | normalization | `variant.identity.input.v1` | `vrs.normalization.receipt.v1` |
| 5 | categorical VRS normalization | normalization | `categorical.variation.input.v1` | `catvrs.normalization.receipt.v1` |
| 6 | VA-Spec envelope | normalization | `annotation.statement.input.v1` | `va.spec.receipt.v1` |
| 7 | multiallelic decomposition | parsing | `multiallelic.record.input.v1` | `allele.decomposition.receipt.v1` |
| 8 | repeat-aware normalization | normalization | `repeat.window.input.v1` | `repeat.normalization.receipt.v1` |
| 9 | variant equivalence | identity | `identity.query.input.v1` | `identity.match.receipt.v1` |
| 10 | duplicate alias reconciliation | identity | `identity.batch.input.v1` | `identity.reconciliation.receipt.v1` |
| 11 | batch sample identity | identity | `batch.identity.input.v1` | `batch.identity.receipt.v1` |
| 12 | chain of custody | provenance | `custody.receipt.input.v1` | `custody.ledger.receipt.v1` |
| 13 | consent policy | policy | `data.use.policy.input.v1` | `data.use.policy.receipt.v1` |
| 14 | input quarantine | policy | `input.anomaly.input.v1` | `input.quarantine.receipt.v1` |
| 15 | completeness scoring | policy | `completeness.input.v1` | `completeness.receipt.v1` |
| 16 | reproducible bundle | release | `intake.bundle.input.v1` | `intake.bundle.receipt.v1` |

The canonical implementation uses a small bounded public variation record. The
record exercises chromosome, interval, alleles, genome build, public aliases,
source joins, and a declared aggregate origin. It is not intended to represent
a cohort observation.

## 5. Scenario matrix

Each operation receives the same four scenario labels. Scenario construction is
operation-aware, so parser operations receive format-shaped public text,
normalizers receive structured variation, identity operations receive alias
sets, and policy operations receive bounded policy payloads.

### Positive

The positive payload has the canonical context, explicit aggregate scope, at
least one public identifier, valid source joins, and an operation-shaped input.
It must produce `accepted`, no issue codes, and one addressed primitive receipt.

### Foreign context

The payload context is the post-treatment control context while the case
contract remains canonical. The result must be `review` with
`foreign_context`. The payload is not mutated to hide the mismatch.

### Malformed input

The payload includes a deterministic malformed marker and an empty required
field. Parser cases also receive non-parseable input text. The result must be
`review` with `malformed_input`.

### Duplicate identity

The payload declares two equal public identity keys. The result must be
`review` with `duplicate_identity`. A duplicate is a review signal, not a
deduplication instruction.

## 6. Evaluation checks

The evaluator emits one `IntakeArchitectureEvaluationCheck` for each check.
Checks are content addressed independently of the containing evaluation. This
means a consumer can cite a single failed check without copying the surrounding
payload.

### Seven checks per case

1. `case-id-present` confirms a stable case key.
2. `operation-join` confirms that the result joins the declared operation.
3. `scenario-state` compares observed state to the scenario contract.
4. `issue-reconciliation` compares observed issue codes to expected codes.
5. `source-join` confirms at least one source join remains attached.
6. `public-identifier` confirms the output identity uses a public prefix.
7. `addressed-result` confirms the result receipt has an address.

### Ten fixture checks

The fixture checks confirm fixture identity, result cardinality, unique result
keys, partition conservation, zero failed cases, positive acceptance, control
holding, operation coverage, positive receipt retention, and the explicit claim
boundary. The global checks use the reserved case ID `__fixture__` so they are
separable from the 448 case-level checks.

## 7. Twenty-four runtime stages

| # | Stage | Acceptance evidence |
| ---: | --- | --- |
| 1 | fixture loaded | canonical fixture is addressed |
| 2 | sources audited | six HTTPS public receipts pass |
| 3 | plan compiled | sixteen ordered nodes pass dependency audit |
| 4 | formats admitted | public format paths are present |
| 5 | variant parsing closed | parser denominator is retained |
| 6 | normalization closed | three normalization paths are represented |
| 7 | completeness scored | positive required fields are complete |
| 8 | anomalies quarantined | all controls are held |
| 9 | cases evaluated | 64 cases reconcile |
| 10 | review routed | 48 controls have review items |
| 11 | policy gated | all positive policy decisions allow |
| 12 | ledger linked | 64 events form one addressed chain |
| 13 | bundle materialized | eight offline artifacts exist |
| 14 | release gated | artifact, blocker, and rollback checks pass |
| 15 | validation matrix closed | 112 plane-operation cells pass |
| 16 | schema closed | 18 public fields pass |
| 17 | replay closed | repeated fixture evaluation is deterministic |
| 18 | source registry closed | source join denominator is six |
| 19 | control boundary closed | no non-positive result is accepted |
| 20 | evaluation checks closed | 458 checks pass |
| 21 | compliance preflight | actual private, attribution, source, and release scan is materialized |
| 22 | compliance closed | 12 independent boundary checks pass |
| 23 | observability closed | every stage has an addressed trace |
| 24 | runtime finalized | final state and compliance are accepted |

The runtime never skips an ordinal. A future addition must either extend the
closed denominator and all dependent checks or remain outside the D02 runtime.

## 8. Bundle contents

| Artifact kind | Contents | Intended consumer |
| --- | --- | --- |
| `manifest` | fixture identity and source joins | loader and replay |
| `source_receipts` | six public source records | provenance review |
| `operation_results` | 64 sanitized results | downstream joins |
| `evaluation_checks` | 458 check receipts | audit and CI |
| `review_queue` | held-control count and routes | human review |
| `ledger` | 64 hash-linked events | custody and replay |
| `schema_manifest` | public field/privacy contract | validators |
| `release_receipt` | rollback and offline capability pointers | release tooling |

All eight artifacts are offline capable. The access manifest grants read access
to the public aggregate projection while disallowing writes and network use.

## 9. Compliance boundary

The compliance projection scans mapping keys recursively and records paths, not
values. It checks exact private-field keys, external attribution keys, source
scope, HTTPS transport, canonical context, explicit aggregate scope, positive
receipts, held controls, artifact/release addresses, runtime addresses, and
review queue cardinality.

A failed compliance check is a release blocker. The result is not converted to
`accepted` by deleting the offending path. The compliance report is included in
the runtime closure and receives its own address. The preflight result is also
retained on the runtime as `compliance_preflight`, including empty forbidden
and attribution paths, source/artifact denominators, and the scan disposition.
This makes the stage observable before the final compliance receipt is closed;
it is not a deferred or scheduled marker.

## 10. Failure and recovery behavior

| Failure | Result | Recovery |
| --- | --- | --- |
| source URI is not HTTPS | data audit fails | replace source receipt and replay |
| case source join is unknown | data audit fails | repair join before evaluation |
| foreign context | held review case | route to context review |
| malformed parser input | held review case | correct source-format input |
| duplicate identity | held review case | reconcile aliases with evidence |
| ledger discontinuity | quality failure | rebuild from the last valid address |
| missing artifact | release review | materialize the missing projection |
| compliance path found | release blocker | remove the disallowed field at ingestion |
| runtime address mismatch | replay failure | inspect changed input or serializer |

The failure-injection suite exercises negative controls without changing the
canonical fixture. Every injection is isolated from the accepted runtime.

## 11. Deterministic replay

Replay evaluates the same fixture twice and compares the evaluation address.
The acceptance equation is:

```text
accepted = (failed_cases = 0)
           AND all(evaluation_check.passed)
           AND all(positive observed_state = accepted)
           AND all(control observed_state != accepted)
           AND all(compliance_check.passed)
           AND release.state = accepted
```

Content addresses use the repository serialization helper. Tuple ordering,
operation ordinal, scenario ordering, and sorted issue codes are therefore
part of the replay contract.

## 12. Commands

The CLI writes to stdout when `--output` is omitted and to a file when it is
provided.

```text
glio-noncode intake-architecture-fixture
glio-noncode intake-architecture-data-audit --input examples/intake-architecture-public-aggregate.json
glio-noncode intake-architecture-compliance --input examples/intake-architecture-public-aggregate.json
glio-noncode intake-architecture-plan --input examples/intake-architecture-public-aggregate.json
glio-noncode intake-architecture-evaluate --input examples/intake-architecture-public-aggregate.json
glio-noncode intake-architecture-runtime --input examples/intake-architecture-public-aggregate.json
glio-noncode intake-architecture-quality --input examples/intake-architecture-public-aggregate.json
glio-noncode intake-architecture-depth --input examples/intake-architecture-public-aggregate.json
glio-noncode intake-architecture-receipts-csv --input examples/intake-architecture-public-aggregate.json
glio-noncode intake-architecture-review-csv --input examples/intake-architecture-public-aggregate.json
glio-noncode intake-architecture-report --format markdown --input examples/intake-architecture-public-aggregate.json
```

The fixture loader compares the input content address to the canonical fixture
before any operation runs. A changed example therefore fails early instead of
silently producing a different release.

## 13. Verification checklist

- Run the D02 focused tests.
- Run the D02 CLI tests.
- Run the compliance command and require exit code zero.
- Confirm 459 CSV lines: one header and 458 rows.
- Confirm the depth report is accepted.
- Confirm the quality report has 24 passing checks.
- Confirm the closure has 18 top-level sections.
- Scan newly added intake source lines for disallowed metadata field names.
- Review the git diff for generated data provenance and deterministic ordering.

## 14. Extension policy

New intake capabilities should add an operation row, four scenario cases, a
source join, a primitive receipt, a validation-matrix cell per plane, a plan
node, operation metrics, evaluation checks, and closure evidence together.
Partial operation additions are not considered a complete module build.

New source formats should add a parser receipt and a malformed control. New
identity mechanisms should add an equivalence or duplicate control. New policy
fields must be public aggregate fields with an explicit schema entry and a
privacy test.

The D02 boundary remains complete only while all of those joins are visible in
the runtime closure and the quality gate remains accepted.
