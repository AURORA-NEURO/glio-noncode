# Public atlas observations and deterministic replay

`glio_noncode.atlas.PublicAtlasRetriever` is the boundary between bounded
public reference retrieval and evidence claims. It consumes one canonical
variant, one exact `ReferenceContext`, one `AtlasQuery`, and one retained
`ReferenceBundle`. It may also use declared motif definitions, a domain
profile, local reference-track adapters, and ENCODE experiment metadata. The
result is an `AtlasBundle` of source-scoped `AtlasObservation` objects rather
than an inferred disease mechanism.

An observation records its source, feature type, evidence tier, state,
canonical payload, context key, retrieval receipt when one exists, and explicit
limitations. A returned sequence, Ensembl annotation, local track match, or
ENCODE catalog row means that the named source returned that object for the
declared query. It does not by itself establish regulatory activity, a
glioma-state measurement, target-gene control, phenotypic effect, or causality.

Source retrieval and typed candidate materialization are distinct outcomes. If
Ensembl returns a canonical response but a row cannot be safely promoted into a
typed candidate, the reference bundle retains the exact raw row and receipt for
audit. Atlas represents that row only as `ABSTAINED`, with an explicit
materialization limitation. A genuine retrieval failure cannot retain raw
features, and a bundle that combines the two is rejected.

## The three-artifact closure

A replayable Atlas result is a closure over three separately retained,
content-addressed artifacts:

1. The `ReferenceBundle` retains the public sequence, features, source
   receipts, and source warnings.
2. `AtlasReplayInputs` retains the exact non-reference inputs needed to repeat
   Atlas derivation offline.
3. `AtlasBundle` retains the derived observations, reports, sequence analysis,
   uncertainty, receipts, and warnings. Its serialized form binds the first
   two artifacts by `source_bundle_address` and `replay_inputs_address`.

`AtlasReplayInputs` is deliberately external to the serialized Atlas bundle.
The in-memory `AtlasBundle.replay_inputs` attachment is a validated convenience;
`AtlasBundle.to_dict()` emits only its address. Persist the replay-input record
as its own object and supply it explicitly when reopening a bundle:

```python
replay_record = bundle.replay_inputs.to_dict()
atlas_record = bundle.to_dict()

replay_inputs = AtlasReplayInputs.from_dict(
    replay_record,
    variant,
    context,
    reference_bundle=reference_bundle,
)
reopened = AtlasBundle.from_dict(
    atlas_record,
    variant,
    context,
    reference_bundle=reference_bundle,
    replay_inputs=replay_inputs,
)
```

The replay-input artifact has a closed, versioned JSON shape and a SHA-256
content address. It binds:

- the canonical variant identifier and complete variant-scope address;
- the context key and complete context-scope address;
- the exact bounded `AtlasQuery`;
- the exact `ReferenceBundle` address;
- canonical motif definitions;
- the optional canonical domain profile used for out-of-domain assessment;
- complete snapshots of every declared reference-track adapter; and
- the classified ENCODE replay state and the only payload or failure fields
  permitted by that state.

Rehydration rejects missing fields, extra fields, non-canonical representations,
unsupported schema versions, malformed nested objects, address mismatches, and
variant, context, query, or reference-bundle substitutions. The reference
bundle, replay inputs, and Atlas bundle therefore need to travel together as
three address-linked records.

## ENCODE replay states

`AtlasEncodeReplayState` preserves why an ENCODE observation exists without
requiring another network request.

| State | Required situation | Retained ENCODE data | Offline result |
| --- | --- | --- | --- |
| `NOT_REQUESTED` | `include_encode_catalog` is false | No payload, failure receipt, or failure warning | No ENCODE observation |
| `UNCONFIGURED` | ENCODE was requested but no client was configured | No payload or failure fields | The same explicit unconfigured abstention |
| `PAYLOAD` | The configured client returned an attributed `SourcePayload` | The complete canonical payload and receipt | The catalog projection is recomputed from the retained payload |
| `FAILURE` | The request raised a classified source failure | A required normalized warning and an optional correctly attributed receipt | The same explicit retrieval abstention |

`PAYLOAD` is also used when transport succeeded but the returned catalog body
cannot support a valid projection. Keeping the actual payload and receipt lets
offline replay reproduce the same abstention instead of disguising malformed
remote content as a transport failure. Unexpected dependency exceptions fail
the retrieval boundary; they are not converted into a replayable negative
result.

## What persisted-bundle revalidation proves

`PublicAtlasRetriever` validates the derivation before returning it.
`AtlasBundle.from_dict()` is the fail-closed path for reopening persisted Atlas
output. Given the exact variant, context, reference bundle, and replay inputs,
it reconstructs and compares all deterministic output:

- built-in sequence and feature observations are regenerated from the retained
  reference bundle;
- the complete declared track-adapter registry is reconstructed from its
  snapshots, queried again for the exact interval and context, and required to
  produce the same canonical reports and observations;
- the motif work-ceiling decision is repeated and, when work is admitted,
  built-in sequence inference is rerun from the retained sequence and motifs;
- the ENCODE projection or abstention is regenerated according to the retained
  replay state;
- receipts and warnings must equal the exact canonical closure of reference and
  classified ENCODE provenance, including an abstained observation for any
  otherwise uninterpreted receipt;
- `created_at` is derived again from the latest retained receipt timestamp, or
  from the stable epoch sentinel when no receipt exists;
- out-of-domain assessment is regenerated from the retained domain profile and
  sequence-derived features; and
- uncertainty is recomputed from the regenerated claims and must cite only
  evidence identifiers in the bundle.

The reopened observations, track reports, sequence analysis, receipts,
warnings, timestamp, uncertainty report, and final canonical bundle bytes must
all match. Removing a valid observation, injecting a motif result, rewriting an
ENCODE accession, changing track output, altering uncertainty, or substituting
a coherent but differently addressed replay artifact therefore fails
revalidation.

Live custom sequence-inference or uncertainty dependencies do not create an
opaque persisted trust boundary. Their returned values are canonicalized, and
the retained bundle is accepted only when those values equal the deterministic
built-in replay. Declared track integrations remain extensible because their
complete validated adapter snapshots are part of `AtlasReplayInputs` and are
rerun during replay.

Every callback checkpoint also pins the invocation scope, retriever
configuration, relevant package functions/classes, dataclass metadata, and
semantic lookup tables. A callback that rewrites those semantics is rejected,
the captured state is restored, and a later clean retrieval starts from the
original configuration. This applies to direct `PublicAtlasRetriever` use as
well as execution through `CaseRuntime`.

The callback-isolation boundary is specifically
`PublicAtlasRetriever.retrieve()`. It acquires the package-wide, process-local
callback lock before per-instance locking or input canonicalization, and it
holds that lock through live retrieval and deterministic derivation. Atlas
retrievals on different threads are therefore serialized while ordinary callbacks can
run. A nested Atlas retrieval on the same thread is rejected before semantic
capture, even when it targets a different retriever instance or enters through a fresh
`contextvars.Context`. Two private thread-local witnesses retain the same immutable
boundary marker, and the coordinator verifies and restores both on exit. The active
boundary stack and lock are closure-held rather than exposed as normal package state.
The boundary
pins the exact Atlas object shell; built-in scanner, uncertainty, public-source,
and declared-track configuration graphs; and custom dependency callable
bindings. Operational provider counters, source-cache files, and valid
rate-limiter timing advances are not treated as declarative mutation. Package
semantics are restored before instance state if a callback is rejected. This
serialization promise does not extend to `AtlasBundle.from_dict()` or
`AtlasBundle.to_evidence_claims()`, which perform deterministic replay without
executing the live retrieval callback boundary.

The coordinator is an in-process integrity and rollback mechanism, not a sandbox from
the Python interpreter hosting it. Deliberate traversal of private closures, native
memory manipulation, or equivalent fully reflective interference is outside this
serialization guarantee and requires process isolation when the callback is hostile.

This guarantee is reproducibility and tamper detection relative to the retained
inputs. It is not proof that a remote source was truthful, that its current
contents are unchanged, or that a scientifically incomplete query captured all
relevant biology.

## Evidence-claim address binding

`AtlasBundle.to_evidence_claims()` converts observations to reference-tier
claims without manufacturing an effect score. Every claim evidence identifier
binds the complete variant scope, context scope, query, reference-bundle
address, replay-input address, and canonical observation. The claim payload
also carries the Atlas bundle address and repeats the variant, context,
reference, and replay addresses with an explicit interpretation boundary.

Claim conversion is itself a replay gate. Before exposing any claim,
`to_evidence_claims()` reconstructs the complete derivation from the attached
reference bundle and `AtlasReplayInputs`. `AtlasBundle.create()` can still build
a structurally valid intermediate object, but an object created without the
exact `reference_bundle=` attachment cannot emit claims; attaching a bundle
does not help fabricated or stale observations because deterministic replay
must still match. `PublicAtlasRetriever.retrieve()` and `AtlasBundle.from_dict()`
attach the reference artifact only after its scope and address are validated.

The final bundle address is intentionally excluded from the evidence-identifier
preimage because the bundle contains uncertainty components that cite those
evidence identifiers. It is still present in the claim payload. This avoids a
hash cycle while ensuring that changing replay inputs changes claim identity,
and changing derived bundle output changes the bundle address or fails replay.

## Interpretation boundaries

The core public-source states retain distinct meanings:

- `supported` means the source returned the requested reference object or
  metadata under the declared query;
- `absent` means a successful bounded query returned no rows for that feature
  class, not that the feature is biologically absent in every assay or state;
- `abstained` means missing configuration, failed retrieval, unusable content,
  an exceeded work ceiling, or another declared limitation prevented a
  conclusion; and
- out-of-domain, contradictory, or measured-negative states remain explicit
  when a validated contributing component supplies them and are never silently
  collapsed into support.

Catalog presence does not prove that an experiment measured the variant or
interval. A local reference-track match is not a causal measurement. Sequence
motif creation or disruption is a sequence-level result, not evidence that the
motif is bound or functional in the declared cell state. Domain distance and
the `UncertaintyReport` expose missingness, contradiction, context transport,
source dependence, and model-domain limitations; they do not upgrade reference
evidence into a mechanism claim.

All live source receipts remain attached to the Atlas provenance closure.
Source failures remain abstentions and are never silently converted into
negative biological observations.

The retained upstream artifact may legitimately be larger than the 2 MiB
per-observation payload envelope. Atlas does not fail the whole retrieval in
that case. For a large raw annotation, sequence analysis, or reference-track
report, it emits a compact `ABSTAINED` observation containing the artifact
address, exact canonical byte count, source binding, and an explicit projection
reason. The complete annotation remains in `ReferenceBundle`; complete sequence
and track artifacts remain in `AtlasBundle` and `AtlasReplayInputs`. Offline
replay must reproduce the same compact projection exactly.
