# Case + matched-RNA consequence workflow

> **Research use only.** This workflow produces inspectable research evidence. It does not
> produce a diagnosis, a calibrated clinical probability, or a treatment recommendation.

This path connects four previously separate operations:

1. prepare a case from inline variant and regulatory-track sources;
2. analyze a matched expression outlier and allele-specific RNA counts;
3. integrate those results into one sample-free `RNAConsequenceEvidence` object; and
4. execute and replay-verify the case with that consequence attached to its exact
   element-to-gene edge and causal-path aggregate.

The implementation is local-first. The example below uses no network access and only Python's
standard library plus `glio_noncode`.

## Run the complete example

From the repository root:

```console
python examples/case_expression_workflow_demo.py --temporary-data-root
```

The temporary option removes the runtime store after replay verification. To retain the local
content-addressed dossier, events, and run record, choose a directory:

```console
python examples/case_expression_workflow_demo.py --data-root .glio-case-expression-demo
```

With neither option, the persistent default is `.glio-case-expression-demo` in the current
directory. The program prints one compact JSON document. It contains preparation and evaluation
identities, evidence addresses, the matched claim identity, exact edge identities, derived support
strengths, and replay state. It deliberately excludes the data-root path, subject identifier,
sample keys, VCF/BED payloads, expression values, reference vectors, and allelic counts.

The expected invariants are:

- `accepted`, `replay.accepted`, `replay.event_chain_valid`, and
  `replay.stored_dossier_matches_address` are `true`;
- `preparation.prepared_run_id` differs from `evaluation.evaluation_run_id` because non-empty RNA
  evidence participates in evaluation identity;
- `matched_rna_claim.edge_id` equals `element_to_gene_edge.edge_id`;
- `matched_rna_claim.claim_address` is present in the element-to-gene claim list and in the
  causal-path aggregate's supporting claim list; and
- `rna_evidence.state` is `supported` for this deliberately concordant synthetic fixture.

## Python path

The executable source is
[`examples/case_expression_workflow_demo.py`](../examples/case_expression_workflow_demo.py).
Its essential call sequence is:

```python
prepared = prepare_case(
    case_id="opaque-case-key",
    subject_id="opaque-subject-key",
    context=context,
    variant_source=VariantSource(...),       # inline VCF text
    regulatory_tracks=(RegulatoryTrackSource(...),),  # inline BED text
    live_reference=False,
)

expression_result = RobustExpressionOutlierAnalyzer().analyze(
    tumour_expression,
    matched_reference_batch,
    expected_direction=RegulatoryDirection.GAIN,
    expected_context_key=prepared.manifest.context.key,
)

allelic_result = AllelicImbalanceAnalyzer().analyze(
    phased_allelic_observation,
    expected_direction=RegulatoryDirection.GAIN,
    expected_context_key=prepared.manifest.context.key,
)

consequence = RNAConsequenceIntegrator().integrate(
    prediction,
    expression=expression_result,
    allelic=allelic_result,
)

result = run_case(
    prepared,
    data_root=".glio-case-expression-demo",
    rna_consequences=(consequence,),
)
```

`rna_consequences` accepts an iterable of typed `RNAConsequenceEvidence` instances or strict
canonical mappings produced by `RNAConsequenceEvidence.to_dict()`. Mappings with unknown fields,
unsupported schema versions, invalid values, or mismatched declared content addresses fail closed.
Passing `()` is exactly the legacy manifest-only execution path.

Always check both layers:

```python
if not prepared.accepted:
    # Inspect prepared.issues and do not execute.
    ...

if not result.accepted or not result.public_summary()["replay_valid"]:
    # Inspect result.issues and local receipts; do not publish the dossier.
    ...
```

## Preparation request shape

The Python façade, CLI `case prepare`, and HTTP preparation route share this inline-source shape.
The following is complete and reproducible JSON; newline characters inside payloads are escaped:

```json
{
  "case_id": "opaque-case-key",
  "subject_id": "opaque-subject-key",
  "context": {
    "genome_build": "GRCh38",
    "disease_class": "diffuse_glioma",
    "age_group": "adult",
    "cell_state": "stem_like",
    "territory": "tumor_core",
    "treatment_phase": "pre_treatment",
    "source_version": "local-v1"
  },
  "variant_source": {
    "source_id": "local-variants",
    "input_format": "vcf",
    "genome_build": "GRCh38",
    "payload": "##fileformat=VCFv4.3\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n7\t100\tvar-1\tA\tT\t99\tPASS\tDP=100\tGT\t0/1"
  },
  "regulatory_tracks": [
    {
      "source_id": "local-egfr-track",
      "input_format": "bed",
      "genome_build": "GRCh38",
      "context": {
        "genome_build": "GRCh38",
        "disease_class": "diffuse_glioma",
        "age_group": "adult",
        "cell_state": "stem_like",
        "territory": "tumor_core",
        "treatment_phase": "pre_treatment",
        "source_version": "local-v1"
      },
      "payload": "7\t90\t130\tEGFR\t800\t+\n",
      "target_gene_keys": ["Name"]
    }
  ],
  "requested_by": "local-researcher",
  "live_reference": false
}
```

The BED `Name` is used both as the candidate feature identifier and, because `Name` is selected in
`target_gene_keys`, as the target-gene key in this minimal example. Production adapters should use
the format and attributes that preserve their own stable element and gene identifiers.

## Private RNA input shapes

Private observations contain opaque sample keys and measurements. Keep them inside the trusted
analysis boundary. Their public result objects omit sample keys and cohort vectors.

An expression target object has this shape:

```json
{
  "schema_version": "1.0.0",
  "feature_id": "EGFR",
  "sample_key": "opaque-tumour-key",
  "value": 20.125,
  "scale": "log2_tpm",
  "context_key": "GRCh38|diffuse_glioma|adult|stem_like|tumor_core|pre_treatment",
  "source_id": "matched-rna",
  "source_version": "local-v1"
}
```

The reference file is an `ExpressionBatch` object, not a bare array:

```json
{
  "schema_version": "1.0.0",
  "observations": [
    {
      "schema_version": "1.0.0",
      "feature_id": "EGFR",
      "sample_key": "opaque-reference-1",
      "value": 3.125,
      "scale": "log2_tpm",
      "context_key": "GRCh38|diffuse_glioma|adult|stem_like|tumor_core|pre_treatment",
      "source_id": "matched-rna",
      "source_version": "local-v1"
    }
  ]
}
```

Supply at least five context-matched reference observations under the default policy. The demo uses
eight. A declared content address may be omitted on private input objects; if present, it must match
the canonical content.

The allele-specific observation shape is:

```json
{
  "schema_version": "1.0.0",
  "feature_id": "EGFR",
  "variant_id": "var-1",
  "sample_key": "opaque-tumour-key",
  "ref_count": 18,
  "alt_count": 82,
  "other_count": 0,
  "phase": "phased",
  "context_key": "GRCh38|diffuse_glioma|adult|stem_like|tumor_core|pre_treatment",
  "source_id": "matched-rna",
  "source_version": "local-v1",
  "expected_alt_fraction": 0.5,
  "mapping_bias": 0.01,
  "mapping_bias_flag": false
}
```

The alternate allele must be phased to the tested variant. The expected fraction must be declared,
as above, or derivable from copy number and purity. The analyzer never silently assumes `0.5` when
the baseline is absent.

The sample-free regulatory prediction shape is:

```json
{
  "schema_version": "1.0.0",
  "prediction_id": "prediction:local:egfr",
  "variant_id": "var-1",
  "feature_id": "EGFR",
  "direction": "gain",
  "context_key": "GRCh38|diffuse_glioma|adult|stem_like|tumor_core|pre_treatment",
  "source_id": "local-regulatory-model",
  "source_version": "local-v1",
  "confidence": null
}
```

Use the canonical `variant_id` from the prepared manifest rather than assuming that an input VCF ID
survived normalization unchanged.

## Consequence transport shapes

The consequence object produced by `RNAConsequenceIntegrator` is sample-free. Its strict shape is:

```json
{
  "schema_version": "1.0.0",
  "prediction_id": "prediction:local:egfr",
  "prediction_address": "regulatory-effect-prediction:<64-hex-digest>",
  "variant_id": "var-1",
  "feature_id": "EGFR",
  "context_key": "GRCh38|diffuse_glioma|adult|stem_like|tumor_core|pre_treatment",
  "predicted_direction": "gain",
  "state": "supported",
  "expression_state": "supported",
  "expression_direction": "up",
  "expression_robust_z": 7.0,
  "expression_result_address": "expression-outlier:<64-hex-digest>",
  "allelic_state": "supported",
  "allelic_direction": "alt_enriched",
  "allelic_log2_ratio": 2.0,
  "allelic_q_value": 0.001,
  "allelic_result_address": "allelic-imbalance:<64-hex-digest>",
  "reason_codes": ["rna_direction_concordant"],
  "content_address": "rna-consequence-evidence:<64-hex-digest>"
}
```

The shown numbers and digests illustrate the schema; do not hand-author them. Preserve the exact
output from `expression integrate`. Three transports intentionally use different outer containers:

| Surface | Exact execution input |
| --- | --- |
| Python | `rna_consequences=(consequence,)` or an iterable of strict mappings |
| CLI | `--rna-consequences FILE`, where `FILE` is the bare JSON array `[{...}]` |
| HTTP | `{"prepared": {...}, "rna_consequences": [{...}]}` |

`{"consequences": [...]}` is not an alias. The HTTP route rejects unknown fields. The JSON Schema
at `case_workflow_schema()["$defs"]["rna_consequence_execution_input"]` describes the bare array.

## CLI walkthrough

1. Save the preparation object above as `case-request.json` and run:

   ```console
   glio-noncode case prepare --request case-request.json --output prepared.json
   ```

2. Save the target and a complete reference batch as `expression-target.json` and
   `expression-references.json`:

   ```console
   glio-noncode expression outlier \
     --target expression-target.json \
     --references expression-references.json \
     --expected-direction gain \
     --context-key 'GRCh38|diffuse_glioma|adult|stem_like|tumor_core|pre_treatment' \
     --output expression-result.json
   ```

3. Save the phased observation as `allelic-observation.json` and run:

   ```console
   glio-noncode expression allelic \
     --input allelic-observation.json \
     --expected-direction gain \
     --context-key 'GRCh38|diffuse_glioma|adult|stem_like|tumor_core|pre_treatment' \
     --output allelic-result.json
   ```

4. Save the prediction as `prediction.json`, then integrate the two public results:

   ```console
   glio-noncode expression integrate \
     --prediction prediction.json \
     --expression-result expression-result.json \
     --allelic-result allelic-result.json \
     --output rna-consequence.json
   ```

5. Put the complete consequence object inside a bare array. This standard-library command avoids
   copying or editing its content address:

   ```console
   python -c "import json; p=json.load(open('rna-consequence.json', encoding='utf-8')); json.dump([p], open('rna-consequences.json', 'w', encoding='utf-8'), indent=2)"
   ```

6. Execute and replay-verify:

   ```console
   glio-noncode case run \
     --prepared prepared.json \
     --rna-consequences rna-consequences.json \
     --data-root .glio-case-expression \
     --output run-result.json
   ```

`rna-consequences.json` must contain `[{...}]`, not
`{"rna_consequences": [{...}]}`. The latter wrapper belongs only to the HTTP run request.

## HTTP walkthrough

Start the local service with a server-owned runtime root:

```console
glio-noncode serve --host 127.0.0.1 --port 8765 --data-root .glio-case-expression-http
```

The examples below assume `Content-Type: application/json`.

Prepare the case:

```console
curl -sS -X POST http://127.0.0.1:8765/v1/case-workflow/prepare \
  -H 'Content-Type: application/json' \
  --data-binary @case-request.json \
  -o prepared-http.json
```

The route accepts either that bare preparation object or `{"request": <preparation object>}`.

Analyze and integrate RNA through these exact bodies:

```text
POST /v1/expression-evidence/outlier
{"target": {...}, "references": {...}, "expected_direction": "gain", "context_key": "..."}

POST /v1/expression-evidence/allelic
{"observation": {...}, "expected_direction": "gain", "context_key": "..."}

POST /v1/expression-evidence/integrate
{"prediction": {...}, "expression_result": {...}, "allelic_result": {...}}
```

Finally submit the complete prepared response and consequence response:

```text
POST /v1/case-workflow/run
{
  "prepared": <complete PreparedCase object>,
  "rna_consequences": [<complete RNAConsequenceEvidence object>]
}
```

For a reproducible file-based request, combine the two canonical outputs without editing them:

```console
python -c "import json; p=json.load(open('prepared-http.json', encoding='utf-8')); r=json.load(open('rna-consequence.json', encoding='utf-8')); json.dump({'prepared': p, 'rna_consequences': [r]}, open('run-request-http.json', 'w', encoding='utf-8'), indent=2)"
curl -sS -X POST http://127.0.0.1:8765/v1/case-workflow/run \
  -H 'Content-Type: application/json' \
  --data-binary @run-request-http.json \
  -o run-result-http.json
```

The HTTP server ignores the optional client `data_root` field and always uses its configured
server-side runtime. Clients cannot select server-local paths. A successful execution responds
`200`; blocked scientific or integrity inputs respond `422`; malformed transport input responds
`400`. The focused case/expression routes reject duplicate JSON keys, non-finite JSON numbers,
unknown request-envelope fields, and simultaneous use of both names of an accepted alias.

The optional claim endpoints expose the same exact matching logic separately:

```text
POST /v1/expression-claims/derive
{"evidence": <consequence>, "target": <element-gene target>}

POST /v1/expression-claims/match
{"evidence": [<consequence>], "targets": [<target>], "require_complete": true}
```

Claim matching uses exactly `(variant_id, feature_id/gene_id, ReferenceContext.key)`. Zero or
multiple matching targets emit no claim; `require_complete: true` turns either condition into a
fail-closed error.

## Identity and provenance semantics

The workflow distinguishes scientific identity from observation and execution receipts:

- `manifest_address` hashes the canonical prepared scientific input. Receipt timestamps and inline
  source observation time do not enter that identity.
- `prepared_run_id` is derived from the manifest-only identity.
- With non-empty RNA, `evaluation_run_id` is derived from the manifest and the sorted
  `RNAConsequenceEvidence.content_address` values. Caller order cannot change it.
- Empty RNA preserves the prepared run ID exactly.
- Each prediction, expression result, allelic result, and integrated consequence has its own
  canonical content address. A declared address is reverified on hydration.
- The runtime receipt records consequence count, sorted consequence addresses, and one aggregate
  `rna_input_address`. It does not record sample keys, raw values, or cohort vectors.
- The addressed RNA input artifact contains canonical sample-free consequence mappings, not the
  private observations used to derive them.
- The deterministic matched-RNA claim identity begins `ev-rna-`; it is attached to exactly one
  element-to-gene edge and listed as a dependency of the causal-path aggregate claim.
- Replay checks both the event chain and the stored dossier's canonical content address.

Preparation and run `workflow_address` values also cover stage receipts and therefore preserve
operational history. Do not substitute those receipt-bearing addresses for the manifest and
evaluation identities described above.

## Interpretation

The robust expression analyzer reports an outlier relative to a declared, context-matched reference
batch. It uses median/MAD dispersion with an IQR fallback. Raw-count expression is intentionally not
compared across samples.

The allelic analyzer runs an exact two-sided binomial test against a declared or
copy-number/purity-derived expected alternate fraction. A significant alternate enrichment can
support a predicted gain; reference enrichment can support a predicted loss. Directional disagreement
is retained as contradictory evidence.

RNA states remain distinct:

- `supported`: measured evidence is directionally concordant;
- `contradictory`: measured evidence opposes the prediction;
- `measured_negative`: the measurement passed gates but did not support an effect;
- `out_of_domain`: identifiers or context do not match the prediction; and
- `abstained`: a required baseline, phase, depth, dispersion, or quality condition was absent.

Scores on matched-RNA claims, edges, and causal paths are **bounded evidence strengths, not
probabilities**. They are not posterior probabilities, disease risks, effect sizes, clinical
confidence, or action thresholds. Read every score with its state, support level, uncertainty,
reason codes, source addresses, and missing/negative evidence.

## Fail-closed gates

Case preparation blocks on intake errors, regulatory-track errors, genome-build mismatch, duplicate
element IDs, or no candidate elements when live reference expansion is disabled. `live_reference`
is `false` in the reproducible example, so no network retrieval can occur.

Expression comparison abstains or exits its domain when the feature, context, scale, reference
count, or dispersion is unsuitable. The default minimum reference count is five.

Allelic analysis abstains when phase is unresolved, informative depth is below 20, other alleles
exceed 10% of total depth, absolute mapping bias exceeds 0.10 (or its flag is set), or no expected
alternate fraction can be established. Exact binomial inference is bounded at 100,000 informative
reads by default; observations above the declared policy maximum abstain with
`exact_binomial_depth_limit_exceeded` and do not enter multiple-testing correction. Mapping bias is
gated, not statistically corrected.

Integration preserves contradictory, out-of-domain, measured-negative, and abstained components; it
does not coerce them into support. Case execution blocks on malformed/tampered consequence mappings,
identity mismatch, persistence mismatch, or failed replay integrity.

## Privacy boundary

- Use opaque local `case_id`, `subject_id`, and `sample_key` values. Do not place names, MRNs, dates
  of birth, contact details, or other direct identifiers in them.
- Treat expression observations, reference vectors, VCF/BCF payloads, BED/GFF payloads, allelic
  counts, copy number, purity, and mapping-bias measurements as private inputs.
- `public_projection()` for expression, allelic, and consequence results is sample-free, but derived
  statistics can still be sensitive in a real project. Apply local access and release policy.
- The demo's JSON summary uses a strict allowlist and contains no local filesystem path. Full CLI and
  HTTP run-result objects are richer local artifacts; do not publish them without review.
- `--temporary-data-root` reduces persistence but is not a secure erasure guarantee. Persistent mode
  writes content-addressed run, event, dossier, and sample-free consequence artifacts under the
  selected directory.
- Keep the HTTP service on loopback unless an explicit authenticated deployment profile, filesystem
  policy, audit policy, and network boundary have been reviewed.

## Operational limits and reproducibility notes

- Focused CLI JSON readers accept at most 16 MiB per input. The local HTTP JSON body must be an
  object between 1 byte and 5 MB.
- Case execution accepts at most 10,000 unique RNA consequence objects. Duplicate content
  addresses and over-limit Python iterables fail closed before runtime persistence; the bound is
  published by both case schema and capabilities discovery.
- Case preparation accepts at most 1,000 regulatory-track sources through either Python iterable
  name. The limit is published by case capabilities; over-limit or non-iterable inputs fail before
  track parsing.
- Each regulatory-track parser accepts at most 1,000,000 data records and 100,000 auxiliary
  header/blank lines by default; callers may choose lower per-parser limits. Over-limit text inputs
  stop at one sentinel with a typed error issue, and regulatory JSON rejects duplicate keys and
  non-finite numbers.
- The in-memory `VariantIndex` accepts at most 100,000 canonical variants by default, supports a
  lower caller-selected ceiling, and consumes only one sentinel beyond that ceiling. Larger cohort
  indexing belongs on the separately bounded streaming/index surfaces.
- Direct RNA claim matching accepts at most 10,000 consequences and 10,000 element-gene targets.
  The bridge consumes at most one sentinel beyond either limit, rejects duplicate content
  identities, and publishes the limits in its schema and capabilities.
- All case sources on these façade routes are inline text or bytes; the server does not dereference
  client-provided local paths.
- Expression and consequence identifiers are bounded opaque keys; normalized free-text fields are
  bounded as well. Prefer short stable IDs.
- The case façade sorts regulatory tracks and RNA consequences canonically. Reversing consequence
  order does not change evaluation identity.
- The exact output addresses in this document are placeholders. Scientific input, evidence, claim,
  and run identities are reproducible from the same package version and canonical inputs;
  receipt-bearing workflow and stored-dossier addresses may also reflect observational history.
  Do not copy digests between runs.
- If a stage blocks, preserve the local issue codes and content addresses for review. Do not bypass a
  gate by editing a serialized result or its declared content address.

Machine-readable discovery is available without private inputs:

```console
glio-noncode case schema --component workflow
glio-noncode case schema --component prepare-request
glio-noncode case schema --component run-request
glio-noncode case capabilities
glio-noncode expression schema
glio-noncode expression capabilities
```

The workflow schema validates either canonical request shape through `oneOf`; its `$defs` retain
the standalone source, prepared-case, result, and RNA component contracts for tooling.
