# Public atlas observations

`glio_noncode.atlas.PublicAtlasRetriever` is the boundary between public
reference retrieval and evidence claims. It consumes the live sequence and
annotation bundle, optionally queries ENCODE experiment metadata, and emits
source-scoped `AtlasObservation` objects.

An observation records its source, feature type, evidence tier, state, payload,
context key, retrieval receipt, and limitations. A returned Ensembl gene or
regulatory annotation is reference evidence that the public source reported an
annotation in the queried interval. It is not automatically a glioma-state
measurement, regulatory activity measurement, or causal mechanism.

The following states are kept distinct:

- `supported`: the source returned the requested reference object or metadata;
- `absent`: a successful query returned no rows for the requested feature class;
- `abstained`: retrieval or configuration did not support a conclusion.

`AtlasBundle.to_evidence_claims` converts observations to reference-tier
claims with no invented numeric score. Claim payloads include the observation
and an interpretation boundary, so later inference stages can require stronger
context or functional evidence before promoting a mechanism edge.

Every bundle also carries a deterministic sequence-analysis result when a
sequence window is available, plus an `UncertaintyReport` over the bundle's
typed observations. The report keeps missingness, contradiction, context
transport, source dependence, and optional domain-profile distance visible. It
is persisted as part of the content-addressed bundle rather than collapsed
into a hidden hypothesis score.

ENCODE catalog lookup is optional and metadata-only. Catalog presence does not
prove that an experiment measured the variant or interval. All live source
receipts remain attached to the bundle and its content address.
