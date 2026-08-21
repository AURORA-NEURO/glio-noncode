# Specimen beta frontier operation reference

This reference describes the four C05-C08 operation contracts at the level of
inputs, transformations, outputs, invariants, and review behavior. It is
intended for maintainers extending the implementation and for reviewers
checking that a new fixture row exercises a meaningful boundary.

## 1. Shared execution architecture

Every operation follows the same six-layer path:

```text
source receipt
    -> aggregate fixture record
        -> typed adapter input
            -> typed measurement result
                -> sanitized receipt
                    -> quality, lineage, bundle, and runtime surfaces
```

The layers have different responsibilities:

| Layer | Responsibility | Must not do |
| --- | --- | --- |
| source receipt | identify public documentation and scope | claim that documentation contains synthetic rows |
| fixture record | declare payload, context, expected state, and counts | hide a missing control or repair a wrong address |
| typed adapter | parse rows and calculate a bounded result | discard malformed evidence silently |
| sanitized receipt | retain result state, issues, counts, and hashes | copy raw operation records |
| quality surface | compare independent reports and floors | convert review into acceptance by filtering |
| bundle/runtime | publish deterministic summaries | imply clinical or biological validity |

All four operations use the exact context key from the public fixture. Context
is an equality constraint, not a ranking feature. A record belongs to the
fixture only when every field matches in the declared order.

## 2. Common field normalization

The existing adapter module accepts several aliases so the command surface can
ingest common tabular projections:

| Canonical field | Accepted aliases |
| --- | --- |
| variant ID | `variant_id`, `variant`, `id` |
| observation ID | `observation_id`, `record_id` |
| sample ID | `sample_id`, `sample` |
| tissue ID | `tissue_id`, `specimen_id`, `sample_id` |
| VAF | `variant_allele_fraction`, `vaf`, `alternate_fraction`, `alt_fraction` |
| tumor VAF | `tumor_alt_fraction`, `tumor_vaf`, `vaf` |
| normal VAF | `normal_alt_fraction`, `normal_vaf` |
| purity | `purity`, `tumor_purity` |
| total CN | `total_copy_number`, `copy_number`, `CN` |
| alternate CN | `alternate_copy_number`, `alt_copy_number`, `alt_cn` |
| CCF | `estimated_ccf`, `ccf`, `cancer_cell_fraction` |

Fractions accept unit-interval values and percentage-shaped values from 1 to
100. Values outside the resulting unit interval are invalid. Empty values are
represented as missing when the operation permits a missing channel; required
fields create a structured issue.

Every accepted row retains a raw hash. The hash is a receipt for equality and
replay; it is not an identity claim about the person, specimen, or source.

## 3. Shared states

The adapter state enum is:

| State | Interpretation |
| --- | --- |
| `supported` | declared evidence crosses the local operation threshold |
| `partial` | a result exists but a required evidence channel or row is incomplete |
| `ambiguous` | incompatible evidence or a boundary prevents a single reading |
| `abstained` | the adapter cannot calculate a result from available evidence |
| `invalid` | a parameter or input contract is invalid |
| `out_of_domain` | the operation is outside its declared boundary |

States are descriptive. They are not probability labels, diagnosis labels, or
release approvals. The bundle and pipeline layers preserve the distinction
between adapter state and fixture role.

## 4. C05 origin algorithm

### 4.1 Input model

An origin row may contain:

```text
variant_id
observation_id
relationship
tumor_alt_fraction
normal_alt_fraction
present_in_normal
normal_alt_reads
normal_depth
population_frequency
source_id
```

Rows are grouped by variant ID. A missing variant ID creates
`missing_variant_id` and does not enter a classification group. A malformed
fraction creates `invalid_origin_fraction` and preserves the row hash, source
ID, row number, and bounded raw issue context in the adapter report.

### 4.2 Evidence channels

The classifier applies transparent score increments:

| Observation | Channel | Score direction |
| --- | --- | --- |
| `present_in_normal: true` | normal presence | germline +2.0 |
| normal fraction above threshold | normal fraction | germline +2.0 |
| `present_in_normal: false` | normal absence | somatic +2.0 |
| tumor relationship and tumor fraction above threshold | tumor alternate fraction | somatic +1.0 |
| zero normal alternate reads with positive normal depth | covered normal absence | somatic +1.0 |
| positive declared population frequency | population frequency | germline +0.5 |

The channels remain listed on the result in observation order with duplicate
channel labels removed while preserving first occurrence.

### 4.3 State transition

For each variant:

```text
somatic score > 0 and germline score > 0 -> uncertain, ambiguous
germline score >= 2 -> germline, supported
somatic score >= 2 -> somatic, supported
otherwise -> uncertain, partial
```

An observation with both normal presence and a tumor relationship retains a
conflicting observation ID. The conflict is not resolved by score ordering.

At batch level, `ambiguous` dominates `partial`, and `partial` dominates
`supported`. A batch with no classifications is `abstained` even if it retains
row issues.

### 4.4 Output invariants

- every classification has a non-empty variant ID;
- every observation ID in the result came from an accepted row;
- every raw hash is a SHA-256 content address;
- conflicting observation IDs are a subset of observation IDs;
- the median tumor and normal fractions are optional and never fabricated;
- `VariantOrigin.UNCERTAIN` is used for unresolved or conflicting evidence;
- no clinical somatic or germline conclusion is emitted.

## 5. C06 mosaicism algorithm

### 5.1 Input model

A mosaicism row contains variant ID, observation ID, tissue ID, alternate
fraction, relationship, optional contamination fraction, and source ID. Rows
are grouped by variant ID. Tissue IDs are sorted for deterministic output.

The low-fraction window is `(0, low_fraction_max]`. The default maximum is
0.35. A zero fraction is not a low-fraction observation because it is not
positive evidence of an alternate allele.

### 5.2 Evidence score

The estimator uses a declared prior and a reproducible logistic transform. Let

```text
L(p) = log(p / (1 - p))
T = number of distinct low-fraction tissues
O = number of low-fraction observations
C = number of observations at or above the contamination threshold
```

Then the evidence score is:

```text
E = 1.35 * max(0, T - 1) + 0.55 * O - 1.10 * C
```

If tumor rows exist and no low-fraction tissues exist, a further `-0.8`
penalty is applied. The result is:

```text
posterior-shaped value = sigmoid(L(prior) + E)
```

The value is marked `calibrated: false` unless the caller supplies a
calibration ID. The formula is a deterministic evidence score and is not a
calibrated population posterior.

### 5.3 State transition

```text
distinct low-fraction tissues >= minimum_tissues -> supported
otherwise -> partial
no valid estimates -> abstained
```

Contamination flags add a warning and an evidence channel. They do not
disappear from the result and do not automatically prove a laboratory cause.

### 5.4 Output invariants

- supporting tissue IDs are unique and sorted;
- low-fraction observation IDs correspond to supporting tissues;
- contamination flags are a subset of accepted observation IDs;
- calibration ID is absent when the result is uncalibrated;
- uncertainty is bounded away from zero by the declared local floor;
- no constitutional, diagnostic, or risk interpretation is emitted.

## 6. C07 cancer-cell fraction algorithm

### 6.1 Input model

A CCF row contains sample ID, variant ID, purity, VAF, total copy number,
alternate copy number, optional depth, optional alternate reads, and source ID.
Purity, VAF, and copy-number values must be finite. Purity and VAF are
normalized to the unit interval. Total and alternate copy numbers must be
positive.

### 6.2 Transparent model

With purity `p`, total copy number `CN`, normal copy number `N`, VAF `v`, and
alternate copy number `a`, the effective copy number is:

```text
effective_CN = p * CN + (1 - p) * N
raw_CCF = v * effective_CN / (p * a)
```

When purity is zero, the denominator is invalid and `raw_CCF` is absent. The
raw calculation is retained when finite even if it is outside the model range.

If positive depth is supplied, the adapter computes a simple binomial standard
error and a 1.96-scaled interval before bounding the displayed interval to the
unit range. The interval is an uncertainty aid, not a calibrated interval.

### 6.3 State transition

```text
purity == 0 -> abstained item
raw_CCF < -tolerance or raw_CCF > 1 + tolerance -> partial, no estimate
otherwise -> supported, estimate bounded to [0, 1]
```

An invalid alternate-read/depth relationship adds a warning and changes the
item to partial. The batch is partial whenever any item is not supported.

### 6.4 No silent clamp invariant

The implementation stores both `raw_ccf` and `estimated_ccf`. For an out-of-
range raw value, `estimated_ccf` is `None`; the code never turns it into `0`
or `1` merely to satisfy a downstream consumer. This invariant is exercised by
the public control `control-ccf-out-of-range`.

## 7. C08 relative subclone algorithm

### 7.1 Input model

A subclone row contains sample ID, variant ID, estimated CCF, and optional
source ID. CCF must be finite and in `[0, 1]`. Invalid rows create
`invalid_subclone_record` and do not enter a cluster.

### 7.2 Deterministic clustering

Rows are grouped by sample ID and sorted by descending CCF, then variant ID.
The first row starts a cluster. Each next row joins the current cluster when
its distance from the current mean is at most `max_ccf_distance`; otherwise it
starts a new cluster. Cluster means are recomputed after each join.

Clusters are then sorted by descending final mean. IDs use:

```text
<sample_id>:relative-subclone:<one-based-rank>
```

The ID is a local ordering token. It has no meaning outside the sample and
fixture run.

### 7.3 Boundary behavior

For each assignment, the distance to the final mean is compared with the
declared cluster distance. If the absolute difference is within
`boundary_ambiguity`, the assignment is `ambiguous`. This makes threshold-edge
behavior visible instead of forcing a hard choice.

At batch level, any ambiguous assignment makes the batch ambiguous. Invalid
rows with otherwise valid assignments make the batch partial.

### 7.4 Output invariants

- every assignment belongs to one declared sample ID;
- each cluster mean is the mean of its assigned observations;
- every assignment references a cluster ID in `cluster_means`;
- assignment state is supported or ambiguous for valid rows;
- invalid rows remain in the issue list with row addresses;
- cluster IDs do not encode phylogeny or mutation order.

## 8. Fixture design matrix

The public fixture maps each contract to a positive and two controls:

| Record | Operation | Expected result | Boundary exercised |
| --- | --- | --- | --- |
| `positive-origin-separated` | origin | supported | separate tumor and normal channels |
| `control-origin-conflicting-presence` | origin | ambiguous | contradictory normal presence |
| `control-origin-invalid-fraction` | origin | abstained | malformed fraction quarantine |
| `positive-mosaic-recurrence` | mosaicism | supported | three distinct tissues |
| `control-mosaic-single-tissue` | mosaicism | partial | insufficient tissue recurrence |
| `control-mosaic-contamination` | mosaicism | partial | contamination penalty |
| `positive-ccf-purity-copy-number` | CCF | supported | purity and CN model |
| `control-ccf-out-of-range` | CCF | partial | no silent clamp |
| `control-ccf-zero-purity` | CCF | partial | denominator abstention |
| `positive-relative-subclones` | subclone | supported | two relative clusters |
| `control-subclone-boundary` | subclone | ambiguous | threshold-edge assignment |
| `control-subclone-invalid-row` | subclone | partial | invalid CCF quarantine |

The expected count fields are part of the record address. A test that changes
the expected count without recomputing the address is rejected by the data
audit; a test that recomputes the address but leaves the wrong expectation is
rejected by fixture evaluation.

## 9. Receipt projection

The evaluator reduces each adapter result to these bounded areas:

```text
operation
state
result summaries
issue codes
operation counts
content addresses
```

Origin summaries retain variant ID, origin, state, scores, evidence channels,
conflict IDs, and result address. Mosaicism summaries retain variant ID,
posterior-shaped value, calibration status, tissue and observation IDs,
contamination flags, state, uncertainty, and address. CCF summaries retain
sample and variant IDs, raw and estimated CCF, interval, state, channels, and
address. Subclone summaries retain sample, variant, relative cluster ID,
cluster mean, distance, state, and address.

No summary copies the payload's `records` array. Issue code lists omit raw issue
records and retain only stable codes in the compact boundary.

## 10. Failure taxonomy

| Failure | First reporting surface | Release effect |
| --- | --- | --- |
| wrong schema | catalog construction | command fails |
| direct identifier key | data audit | quality gate fails |
| context drift | data audit and lineage | replay fails |
| malformed fraction | adapter issue list | expected control may pass |
| invalid CCF | adapter item state | result remains partial or abstained |
| invalid subclone row | adapter issue list | valid assignments remain visible |
| wrong expected count | fixture evaluation | quality gate fails |
| duplicate record ID | data audit and replay | bundle blocked |
| duplicate output address | replay | release blocked |
| missing lineage endpoint | lineage audit | quality gate fails |
| failed runtime stage | runtime report | publication prevented |

The taxonomy intentionally distinguishes input invalidity from insufficient
evidence. A malformed fraction is not the same as a valid low-fraction row that
does not repeat across enough tissues.

## 11. Extension rules

Adding a new evidence channel requires:

1. a typed input alias or a documented rejection;
2. a deterministic transformation and address body;
3. a positive or control fixture record;
4. an expected count or issue code;
5. a contract safety note;
6. a scenario matrix assertion;
7. a quality-gate check where the boundary changes;
8. a bundle and lineage projection update;
9. unit and CLI tests;
10. an Actions command step if the release path changes.

Changing a threshold default is a contract change. It requires replay review,
fixture-address updates, and documentation of the new control behavior.

## 12. Review checklist

Reviewers can audit a C05-C08 change with this sequence:

```text
source scope -> exact context -> aggregate scan -> adapter result
-> issue and count comparison -> replay -> scenario matrix
-> quality gate -> lineage -> bundle -> runtime
```

The change is not ready for acceptance when any stage is skipped or when a
review control is removed to make the accepted path green. A successful local
adapter call is necessary but not sufficient for a verified ledger state.

## 13. Verification commands

```powershell
python -m unittest tests.test_specimen_beta_frontier_public_data
python -m unittest tests.test_specimen_beta_frontier_fixture_eval
python -m unittest tests.test_specimen_beta_frontier_quality_gate
python -m unittest tests.test_specimen_beta_frontier_bundle
python -m unittest tests.test_specimen_beta_frontier_lineage
python -m unittest tests.test_specimen_beta_frontier_runtime
python -m unittest tests.test_specimen_beta_frontier_cli
python -m glio_noncode specimen-beta-frontier-quality-gate examples/specimen-beta-frontier-public-aggregate.json --output beta-quality.json
python -m glio_noncode run-specimen-beta-frontier-pipeline examples/specimen-beta-frontier-pipeline-accepted.json --output beta-pipeline.json
```

## 14. Evidence ceiling

The C05-C08 release proves that the local software preserves declared
aggregate evidence, deterministic calculations, review states, and provenance
surfaces. It does not prove that any variant is pathogenic, that mosaicism is
constitutional, that a CCF estimate is clinically calibrated, that a sample is
contaminated for a particular cause, or that relative clusters are tumor
clones. Those claims require independent datasets, laboratory validation,
calibration studies, and domain review beyond this repository boundary.
