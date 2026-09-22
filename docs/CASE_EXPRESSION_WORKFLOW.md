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

When live reference and Atlas sources are configured, each reference bundle binds a
versioned address over the complete canonical `ReferenceContext`; matching a display key
alone is insufficient. Persisted Atlas replay requires that exact retained reference bundle
and a separate `AtlasReplayInputs` artifact whose full variant, context, reference, and query
scope matches its paired bundle. Any sequence analysis is recomputed against the bundle's
sequence slice, and its interval, reference hash, observed allele, alternate-length delta,
and GC values must agree. Atlas out-of-domain assessments are independently addressed over
their complete retained fields; unverifiable legacy assessments must be recomputed.

## Host-configured evidence adapters

Evidence adapters are an untrusted host extension boundary, not request-supplied
code. An adapter implements `EvidenceAdapter` (or the variant-aware protocol),
publishes immutable `AdapterMetadata`, and returns exact typed
`CandidateElement` and `EvidenceClaim` tuples. Register it before constructing
the runtime:

```python
from glio_noncode import AdapterRegistry, CaseRuntime

registry = AdapterRegistry()
registry.register(institution_adapter)  # host-owned EvidenceAdapter implementation
runtime = CaseRuntime(".glio-case-expression-demo", adapter_registry=registry)

result = run_case(
    prepared,
    runtime=runtime,
    rna_consequences=(consequence,),
    adapter_ids=("institution-regulatory-v1",),
)
```

For HTTP use, inject the same registry with
`create_server(..., adapter_registry=registry)`. Clients can discover the
addressed snapshot at `GET /v1/case-workflow/adapters` and submit only its
canonical IDs. The command-line `case run` path does not load executable
adapters; use the Python host or configured HTTP service when adapters are
required.

Selection is part of scientific identity. Before dossier persistence, the
runtime freezes four ordered adapter source records: the base manifest, an atomic
selected-execution registry snapshot, adapter-resolution report, and attributed
claim-collection report. The claim report embeds the complete, addressed metadata
preimage for every selected adapter; the discovery endpoint remains the full
configured-registry view. It then materializes an effective manifest whose address
replaces the preparation manifest address in the evaluation run identity. Replay
requires those source objects and lifecycle events in their declared order and
verifies adapter metadata, producer, variant, element, context, source, channel, and
exact per-resolution-item hypothesis-edge membership. Factorized gene-to-state edges
can belong to multiple items sharing that relation; attribution is not false
exclusivity. Missing adapters, metadata drift, malformed output, resource-limit
violations, or conflicting elements fail atomically without a partial run record.

Always check both layers:

```python
if not prepared.accepted:
    # Inspect prepared.issues and do not execute.
    ...

if not result.accepted or not result.public_summary()["replay_valid"]:
    # Inspect result.issues and local receipts; do not publish the dossier.
    ...
```

## Bounded typed assay route

The root package also exposes the operational contracts used below the case façade. Use these
types when an application needs to inspect public-atlas observations, build hypotheses, rank assay
options, or run an explicit release gate. The limit objects are downward-configurable; their module
constants are hard ceilings, not recommended batch sizes.

```python
from glio_noncode import (
    ContractValidator,
    EvidenceGraph,
    EvidenceGraphLimits,
    ExperimentPlanner,
    ExperimentPlanningLimits,
    HypothesisBuilder,
    HypothesisWorkLimits,
    PolicyLimits,
    PublicAtlasRetriever,
    PublicReferenceRetriever,
    ReferenceRetrievalLimits,
    ReleaseGate,
    ResearchPolicy,
)

# `retrieve()` is the opt-in network boundary. Constructing these objects does not fetch.
reference_retriever = PublicReferenceRetriever(
    cache_root=".glio/source-cache",
    limits=ReferenceRetrievalLimits(
        max_window_bp=20_000,
        max_features_per_variant=500,
        max_variants=32,
        max_total_elements=5_000,
        max_total_canonical_bytes=64 * 1024 * 1024,
        max_total_sequence_bp=2_000_000,
    ),
)
atlas_retriever = PublicAtlasRetriever(reference_retriever=reference_retriever)
atlas_bundle = atlas_retriever.retrieve(variant, context)

built = HypothesisBuilder(
    limits=HypothesisWorkLimits(
        max_targets_per_element=32,
        max_work_items=5_000,
        max_rna_consequences=1_000,
    )
).build(
    prepared.manifest,
    prepared.run_id,
    rna_consequences=(consequence,),
)

graph = EvidenceGraph(
    limits=EvidenceGraphLimits(
        max_claims=5_000,
        max_claims_per_edge=1_000,
        max_dependencies_per_claim=1_000,
        max_claim_bytes=2_000_000,
        max_graph_bytes=32_000_000,
    )
)
graph.extend(built.claims)
edge = built.hypotheses[0].edges[0]
aggregate = graph.aggregate(edge)

assay_options = ExperimentPlanner(
    limits=ExperimentPlanningLimits(
        max_hypotheses=1_000,
        max_edges_per_hypothesis=256,
        max_total_edges=5_000,
    )
).plan_many(built.hypotheses)

manifest_report = ContractValidator().validate_manifest(prepared.manifest)
release_report = ReleaseGate(
    ResearchPolicy(limits=PolicyLimits(max_text_items=5_000))
).check(dossier)  # `dossier` must be the complete typed runtime/review artifact.
```

The snippet shows the contracts, not a shortcut around the façade. Check for an empty hypothesis
tuple before indexing it in real code, stop when `manifest_report.valid` is false, and publish only
when the complete `release_report.valid` is true. `aggregate.score` is an evidence-strength summary,
not a probability. `assay_options` are research validation choices with required context, controls,
readouts, feasibility, cost class, and limitations; they do not execute an assay and are not a
treatment menu. The planner uses typed edges to propose MPRA, CRISPR interference, contact assays,
or an RNA-measurement fallback and bounds both per-hypothesis and aggregate edge work.

### Evidence semantics and lineage

`EvidenceGraph` is an in-memory, append-only, single-context graph. `extend()` stages the whole
bounded input and commits atomically, so a malformed claim, duplicate or colliding evidence ID,
oversized graph, edge-binding conflict, or invalid dependency leaves the graph unchanged. Internal
dependencies must point backward to an already retained or earlier staged claim. External
dependencies must be canonical content addresses. Reusing a later evidence ID that was previously
named as an external dependency is rejected instead of silently changing lineage.

The hard graph ceilings are 20,000 claims, 10,000 claims per edge, 10,000 dependencies per claim,
16 MiB per canonical claim, and 128 MiB per graph. `EvidenceGraphLimits` may only lower them.

Aggregation first removes superseded claims, then groups related channels so repeated correlated
observations do not count as independent replications. The result keeps supported, negative, and
missing/unsupported claim IDs in disjoint sorted tuples. Contradictory and measured-negative claims
apply a bounded penalty; absent, unsupported, out-of-domain, abstained, and unresolved declared
claims increase visible uncertainty rather than being treated as zero-valued support. Read
`AggregateSupport.rationale`, `context_support`, channel groups, and all three claim-ID collections
with the score. `context_support` averages the confidence of at most one representative claim per
informative dependence group: the highest-confidence claim, with lexicographically smallest evidence
ID breaking ties. `context_support_claim_ids` exposes those representatives. Adding a lower-confidence
correlated observation therefore cannot by itself raise or dilute context support or reduce the
reported uncertainty; a stronger observation may replace the group representative. This is a
dependence-aware descriptive summary, not a calibrated probability.

### Live-reference network, cache, and receipt boundary

Live reference lookup is disabled in the reproducible example. Calling
`PublicReferenceRetriever.retrieve()` or `enrich_manifest()` opts into bounded public GET requests
to the configured source catalog. `SourceClient` accepts only canonical HTTP(S) source URLs without
embedded credentials. Request paths must be relative, parameter names and values are bounded and
encoded, the completed URL must remain on the configured origin, and the standard transport rejects
cross-origin redirects. Timeouts, retry attempts and backoff, response bytes, query parameters,
regional windows, variant count, feature count, and total enriched elements all have hard ceilings.
The headline maxima are 100,000,000 response bytes, 1,000 variants per enrichment, a 5,000,000-base
window, 100,000 enriched elements, and 128 MiB per public reference bundle. Defaults and individual
source specifications are usually lower.

The filesystem cache is a performance layer, not authority. Entries are keyed by request hash and
are accepted only when their exact field shape, source ID/version, URL, origin, body hash, size,
timestamps, and expiry match the current request. Malformed, expired, oversized, or mismatched
entries become cache misses. Same-resource updates are locked across threads and processes and use
flushed same-directory atomic replacement. A custom `HttpTransport` must still return a valid
bounded `TransportResponse`; source-specific decoders reject duplicate JSON keys, non-finite JSON
numbers, unexpected content types, malformed rows, and receipt/content mismatches.

Every completed HTTP or cache outcome carries a canonical `FetchReceipt`. `FETCHED`, `CACHE_HIT`,
`NOT_FOUND`,
`RATE_LIMITED`, `FAILED`, and `ABSTAINED` are distinct states: a transport or decode failure is not
negative biological evidence, and an explicit successful no-result is not a source failure. The
data-source `ReferenceBundle` is exported from the root as `PublicReferenceBundle` because the
legacy root already uses `ReferenceBundle` for an unrelated frontier contract. Construct public
bundles through `PublicReferenceBundle.create(...)`; it requires canonical ordering, validates
retained content, freezes nested feature mappings, requires sequence-receipt closure, and computes
the canonical address over `variant_id`, `context_key`, the full `context_address`, sequence,
elements, raw features, receipts, and warnings.
`ReferenceRetrievalLimits` also bounds one complete enrichment closure. Its hard/default ceilings
are 256 MiB of canonical JSON and 10,000,000 retained reference-sequence bases; callers can lower
both limits, as well as the variant, per-variant feature, and total-element ceilings. Direct
construction and the loader charge canonical components progressively before whole-closure
serialization or nested hydration. The live retriever projects the exact enriched manifest,
bundles, deduplicated warnings, wrapper, and fixed-width address before requesting a later bundle.

### Atlas honest-state behavior

`AtlasObservation` preserves its source, evidence tier, context key and optional match score,
receipt, frozen payload, and explicit limitations. `AtlasBundle` separately seals variant scope,
context scope, query, source-bundle and replay-input addresses, observations, receipts, sequence
analysis, uncertainty, and track reports. Its external `AtlasReplayInputs` preimage retains the
exact query scope, reference binding, motifs, domain profile, declared track adapters, and ENCODE
replay state. Reusing a query with a different variant, a variant with a different reference build,
or content whose declared addresses no longer close fails validation.

A standalone typed atlas bundle is capped at 25,000 observations and 256 MiB of canonical content.
`CaseRuntime` applies its stricter 128 MiB persisted-object ceiling before retaining that bundle as
a source record. Motif scanning has a 50,000,000-comparison ceiling in addition to motif,
potential-hit, sequence-hit, track-report, and track-match bounds. Crossing the preflighted
sequence/motif work budget produces an honest abstention rather than a partial result selected by
input order; structural tuple and byte caps fail validation.

Interpret atlas states literally. `SUPPORTED` means that a bounded source observation exists; it
does not establish a disease mechanism or causality. `ABSENT` is emitted only for a successful,
unambiguous no-result. A source failure, missing or conflicting receipt, truncated track query,
over-budget sequence/motif work, or unusable ENCODE response becomes `ABSTAINED` with limitations.
A valid analysis or track report that determines the query lies outside its supported domain or
window becomes `OUT_OF_DOMAIN`. A substituted source bundle whose declared context, contig, or
interval conflicts with the request is rejected as an integrity error. ENCODE catalog rows and
generic genome annotations remain reference metadata, not disease-state measurements.
`AtlasBundle.create()` without the exact `reference_bundle=` attachment is structural-only and
cannot emit claims. `to_evidence_claims(variant=..., context=...)` is a full deterministic replay
gate: it rechecks exact variant/context scope and reconstructs the derivation from that attached
reference bundle plus `AtlasReplayInputs` before exposing claims, without manufacturing effect
scores or certainty.
If an Ensembl response is valid source evidence but one or more annotations cannot be promoted to
typed candidate elements, including rows with missing or unsupported feature types, the exact raw
annotations and receipt remain in the reference bundle.
Atlas exposes those rows only as `ABSTAINED` audit observations with an explicit materialization
limitation; they never become supported biological evidence. A true retrieval failure may not
retain raw features and fails closed if a substituted bundle attempts to do so.

### Runtime source-closure admission and replay

One live run shares a 256 MiB aggregate canonical-byte budget across its optional RNA,
reference, Atlas, and adapter source records. For each variant, Atlas is represented by
an ordered two-record pair: an external, detached `AtlasReplayInputs` artifact followed
immediately by the `AtlasBundle` derived from it. Every stored source object is also
bounded by the runtime validator's 128 MiB canonical-object
ceiling. Both limits are downward-configurable; lowering the object limit also lowers
the loader's per-object allowance. The hard/default `source_bundle_addresses` ceiling
is 3,006: one RNA batch, one submitted manifest, up to 1,000 reference bundles, up to
1,000 detached Atlas replay-input artifacts, up to 1,000 Atlas bundles, and the four
adapter roles. The dossier retains their first-use order and stores a cross-stage
duplicate address only once.

Admission is progressive at runtime stage boundaries. The submitted manifest must fit
before reference enrichment is invoked. The runtime cannot interrupt a source callback
already in flight; it validates each complete returned result before beginning later
runtime work. In particular, per-variant or network work inside a reference retriever
may finish before its returned enrichment is rejected. RNA consequence input is
detached and charged one canonical row at a time; an exhausted byte allowance stops
the iterator before the remainder is materialized. The returned reference bundles
must fit before Atlas collection begins. Before each per-variant Atlas callback, the
runtime reserves both source-address slots required by the replay-input/bundle pair.
Afterward it detaches and validates the pair, retains `AtlasReplayInputs` first and its
`AtlasBundle` second, and requires both objects to fit the per-object and aggregate byte
allowances before the next callback. For adapters, the base manifest and atomically
selected registry snapshot must fit before resolution; the resolution report must then
fit before claim collection. The final attributed claim report must also fit before the
effective manifest can be published. Reusing one exact object at adjacent stages does
not charge it twice.

The 256,000 combined source-receipt ceiling counts occurrences in the ordered
reference-then-atlas receipt sequence. Atlas and adapter evidence share a hard/default,
downward-configurable limit of 10,000 external claims; only atlas observations promoted
to linked claims consume it, and adapter claim collection receives the smaller of its
own configured limit and the remaining runtime allowance. Per-edge validation headroom
is also passed into adapter collection before callbacks. The atomically selected live
adapter identities stay pinned through resolution and claim collection; substitution
fails closed and the selected slots are restored without rolling back unrelated
registrations. Capacity is
consumer-specific: source bytes and addresses gate every later source stage, receipt
and accumulated source-warning limits plus the Atlas event-payload limit gate later
atlas callbacks, and claim exhaustion gates later claim-producing atlas callbacks and
adapter claim callbacks. An atlas callback for a variant with no eligible element may
still retain unpromoted observations, and adapter resolution may run before claim
collection rejects a zero allowance. A ceiling failure leaves no partial run record.

The reference event retains the submitted and effective manifest addresses, one exact
bundle address per variant, the reference receipt count, and its unique warning list.
The Atlas event retains equal-length, variant-ordered `replay_input_addresses` and
`bundle_addresses` arrays. During replay, the loader rehydrates the submitted manifest
and typed reference bundles, reconstructs the enriched manifest, validates that
transition, then validates both Atlas arrays and interleaves each replay-input record
immediately before its corresponding bundle in the declared source closure. Missing,
substituted, reordered, duplicate, or mismatched pair members fail closed. The loader
reconstructs each `AtlasReplayInputs` artifact against the exact full
`VariantIdentity`, `ReferenceContext`, retained reference bundle, and `AtlasQuery`, and
requires its paired `AtlasBundle` to bind that replay-input address. It then
offline-rederives sequence and motif analysis, declared-track reports and observations,
ENCODE projection or abstention, receipt and warning closure, the receipt-derived
timestamp, out-of-domain and uncertainty outputs, and evidence claims. The retained
bundle and dossier claims must match those derivations exactly. The dossier receipt
sequence must match the exact ordered occurrences from all reference bundles followed
by all Atlas bundles;
an identical receipt may recur, but two definitions for the same request hash may not
conflict.

Warning proofs deliberately differ. Every reference-bundle warning must occur in the
reference event and every reference-event warning must remain in the dossier, but a
valid additional enrichment-level warning is not reconstructible from bundle content.
The Atlas event warning list must exactly equal the deduplicated Atlas-bundle and
claim-link warnings, and every entry must remain in the dossier. Each Atlas bundle must
also bind the same variant, context, exact reference-bundle content address, and exact
replay-input content address; its reconstructed claims must equal the dossier claims and
occur on a hypothesis edge.
Replay requires canonical source-event order, IDs, exact payload fields, and derived
receipt, claim, and adapter counters. Adapter replay similarly requires the ordered
base-manifest, selected-registry, resolution, and attributed-claim records and
recomputes their metadata, ownership, claim, and graph linkage.

This stricter closure is an intentional compatibility boundary. A run created with an
older live-source layout or adapter report version fails closed when the current loader
cannot prove the complete transition; recompute it from the original inputs rather than
rewriting stored objects. Immutable offline runs remain usable when their canonical
bytes, addresses, lifecycle events, and cross-links satisfy the current contracts.

### Event pointer closure and release policy

`RuntimeEvent` freezes its JSON payload and seals the run ID, event ID/type, timestamp, previous
hash, and payload into an event hash. `EventLog` rejects duplicate IDs, wrong-run events, broken
previous-hash links, oversized payloads, too many events, and records that exceed the canonical byte
ceiling. The hard caps are 10,000 events, 16 MiB per event payload, and 64 MiB for the complete
record. When loading a record obtained through a stored pointer, close both layers:

```python
from glio_noncode import EventLog

event_log = EventLog.from_record(record, expected_address=stored_event_record_address)
if not event_log.verify():
    raise ValueError("event chain is not a valid closed record")
```

Hash-chain verification alone proves only internal continuity. Supplying `expected_address` also
proves that the complete record matches the external content-addressed pointer. `to_record()` returns
a detached representation; editing that mapping does not mutate the log and produces a different
address if persisted.

`ResearchPolicy.inspect_texts()` and `validate_dossier()` inspect bounded human-facing and nested
payload text, normalize common separator/confusable bypasses, preserve legitimate non-assertive
limitations, and fail closed on malformed structure, unsupported characters, excessive work, or
unsafe iteration. A `PolicyDecision` always retains its policy version and research-use warning;
`allowed` cannot disagree with its violations. Policy approval is necessary but does not certify
scientific validity. The hard policy ceilings are 500,000 text items, 33,554,432 total normalized
characters, and 100,000 candidate pattern matches; production callers should normally select lower
`PolicyLimits`.

`ReleaseGate` combines the structural `ContractValidator` report with the policy decision. It checks
typed/canonical manifest and dossier closure, evidence/edge/dependency references, review linkage,
source receipt and bundle pointers, status/review consistency, and bounded work before policy
approval is considered. An accepted review remains mandatory for a released-research dossier.
Abstained evidence stays visible and can produce a release warning; neither review nor policy may
rewrite it into support. Validation itself is capped at 128 MiB of canonical input and 100,000
reported issues, with finer limits available through `ValidationLimits`. Keep a dossier unreleased
whenever either structural or policy issues remain.

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

Discovery is available without submitting scientific content:

```text
GET /v1/case-workflow/schema
GET /v1/case-workflow/capabilities
GET /v1/expression-evidence/schema
GET /v1/expression-evidence/capabilities
GET /v1/expression-claims/schema
GET /v1/expression-claims/capabilities
```

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

POST /v1/expression-evidence/allelic-batch
{"batch": {...}, "expected_directions": {"variant-id": "gain"}, "context_key": "..."}

POST /v1/expression-evidence/integrate
{"prediction": {...}, "expression_result": {...}, "allelic_result": {...}}
```

Finally submit the complete prepared response and consequence response:

```text
POST /v1/case-workflow/run
{
  "prepared": <complete PreparedCase object>,
  "rna_consequences": [<complete RNAConsequenceEvidence object>],
  "adapter_ids": ["institution-regulatory-v1"]
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

The HTTP server always uses its configured server-side runtime and adapter registry. A client
`data_root` field or adapter implementation is rejected as an unknown field with HTTP 400; clients
cannot select server-local paths or executable code. Omit `adapter_ids` when the server has no
configured adapters. A successful
execution responds `200`; blocked scientific or integrity inputs respond `422`; malformed
transport input responds `400`. The focused case/expression routes reject duplicate JSON keys,
non-finite JSON numbers, unknown request-envelope fields, and simultaneous use of both names of
an accepted alias.

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
gated, not statistically corrected. A batch is preflighted before any exact test and is rejected as
a whole when its potential exact enumeration exceeds one million outcomes by default, so input
ordering cannot select a partially analyzed prefix.

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

- Focused CLI JSON readers accept at most 16 MiB per input and 100 object/array nesting levels. CLI
  and local HTTP JSON both reject duplicate keys and non-finite or overflowing numbers; CLI input
  also rejects noncanonical Unicode. The HTTP body must additionally be an object between 1 and
  5,000,000 bytes and rejects ambiguous length framing or truncated bodies.
- Case execution accepts at most 10,000 unique RNA consequence objects. Duplicate content
  addresses and over-limit Python iterables fail closed before runtime persistence; the bound is
  published by both case schema and capabilities discovery.
- Case preparation accepts at most 1,000 regulatory-track sources and 1,000,000 candidate elements
  across the case. Each track may declare at most 32 unique target-gene keys of 128 characters;
  aggregate conversion stops after the first source that crosses the case ceiling and later sources
  are not parsed. The same 1,000-source bound applies through either Python iterable name. Over-limit
  or non-iterable inputs fail before track parsing. These ceilings are published in request schemas
  and capabilities discovery.
- Every candidate element may contain at most 128 target genes and 128 state IDs. Preparation and
  hydration also cap conservative runtime work at 10,000 units, computed as
  `variant_count * max(1, sum(1 + max(1, target_gene_count) + max(1, state_id_count)))` across
  candidates. An over-budget preparation returns the typed `case_runtime_work_limit_exceeded` gate;
  a forged or stale persisted manifest fails validation before execution.
- Case, source, receipt, and hydrated run metadata are recursively canonicalized and frozen. Keys
  must be strings, numbers finite, recursive/non-JSON values are rejected, and user metadata cannot
  claim the reserved `case_workflow_provenance` key. Persisted manifests, dossiers, run records,
  replay proofs, and runtime receipts are revalidated and cross-linked before execution or reuse.
- Each regulatory-track parser accepts at most 1,000,000 data records and 100,000 auxiliary
  header/blank lines by default; callers may choose lower per-parser limits. Over-limit text inputs
  stop at one sentinel with a typed error issue, and regulatory JSON rejects duplicate keys and
  non-finite numbers.
- The in-memory `VariantIndex` accepts at most 100,000 canonical variants by default, supports a
  lower caller-selected ceiling, and consumes only one sentinel beyond that ceiling. Larger cohort
  indexing belongs on the separately bounded streaming/index surfaces.
- In-memory variant intake accepts at most 100,000 source records and 10,000 auxiliary header or
  blank lines by default, with lower caller-selected ceilings. VCF, gVCF, TSV, JSON, and decoded BCF
  normalization stop after one addressed sentinel; JSON additionally rejects duplicate keys and
  non-finite numbers.
- `BcfReader` separately bounds its work before intake normalization: 1 GB each for input and total
  decoded bytes, 100,000 BGZF members, 65,536 bytes per compressed or decoded BGZF member, 5 MB of
  header data, 1,000,000 records, and 16 MB per framed record. Every configurable ceiling can be
  lowered; large sources should use the streaming importer. These checks preserve legacy input,
  record, and document addresses without materializing whole-input hexadecimal copies.
- Expression and allelic-count batches each accept at most 10,000 observations and consume at most
  one sentinel beyond that ceiling. Duplicate scientific identities are rejected. Allelic batch
  inference additionally has a downward-configurable, one-million-outcome exact-work ceiling and
  rejects an over-budget batch before starting inference.
- Direct RNA claim matching accepts at most 10,000 consequences and 10,000 element-gene targets.
  The bridge consumes at most one sentinel beyond either limit, rejects duplicate content
  identities, and publishes the limits in its schema and capabilities.
- All case sources on these façade routes are inline text or bytes; the server does not dereference
  client-provided local paths.
- Expression and consequence identifiers are bounded opaque keys; normalized free-text fields are
  bounded as well. Prefer short stable IDs.
- The case façade sorts regulatory tracks and RNA consequences canonically. Reversing consequence
  order does not change evaluation identity.
- Content-addressed object writes and run-record access serialize the same resource across processes.
  Writes use a flushed unique sibling temporary and atomic same-directory replacement; run-index
  reads share the writer lock for a stable snapshot. A run retains at most 1,000 unique event-history
  entries and 1,000 unique dossier-history entries; malformed, mismatched, or over-limit histories
  fail closed.
- Identical canonical batch requests share one content-derived batch ID. A cross-process batch lock
  elects one evaluator and followers reopen that winner's verified result. Under normal completion,
  concurrent retries therefore share one indexed closure instead of creating competing result
  objects. A malformed index, input object, result, count, item link, or persisted closure is rejected
  instead of being silently overwritten or reevaluated.
- The persisted case contracts retain their v1 identifiers, and canonical v1 artifacts emitted by
  the package remain readable. Hydration is intentionally stricter: unknown fields, coercive scalar
  types, noncanonical JSON, broken content addresses, or incomplete cross-links that older permissive
  readers may have accepted now fail closed. Legacy v1 per-track provenance may omit its full
  `context`; when candidates survive, the compatibility path reconstructs a single unanimous context
  and verifies its context key, legacy parser order, and candidate address. Newly generated v1
  payloads always include the full track context.
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
