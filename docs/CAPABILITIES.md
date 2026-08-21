# Capability coverage

GLIO-NONCODE is measured against the approved product blueprint, not against
the number of Python files or agent roles. The checked-in catalog at
`schemas/capability_catalog.csv` contains:

| Measure | Denominator | Meaning |
| --- | ---: | --- |
| Product capabilities | 256 | 16 domains × 16 ordered capabilities |
| MVP capabilities | 64 | The first four capabilities in each domain |
| Delivery surfaces | 4 per capability | Core, API, CLI, and review/operations surfaces |
| Feature instances | 1,024 | 256 capabilities × 4 delivery surfaces |
| Control-plane roles | 48 | Bounded agent responsibilities |
| Typed tool contracts | 96 | Two contracts per bounded role |

The 48-role and 96-contract figures describe orchestration coverage. They are
not a substitute for product implementation coverage. A capability is counted
as implemented only when the ledger names its modules; it is counted as
verified only when tests and the stated evidence boundary support that claim.
The registry reports planned, partial, implemented, and verified counts
separately so a single percentage cannot hide unfinished work.

Inspect the current ledger locally:

```powershell
glio-noncode capabilities
```

## Domain 01 intake boundary

The first vertical slice covers the source boundary for case material:

- VCF, gVCF, TSV, JSON, and binary BCF intake preserve source hashes,
  headers, typed fields, genotype decisions, deferred symbolic records, and
  malformed-record issues;
- BED and narrowPeak coordinates are converted from zero-based half-open to
  one-based closed intervals, while GFF3 remains one-based closed;
- regulatory-track rows are converted to context-qualified candidate
  elements only when their source accounting remains intact; unresolved
  targets are explicitly marked rather than inferred;
- supported SNV/indel identities receive a VRS-shaped allele representation;
  missing reference digests, repeat ambiguity, and unsupported breakend/CNV/
  haplotype forms remain visible as limitations or abstentions.

These adapters are a research-use boundary. They do not assert clinical
interpretation, and a VRS-shaped local representation is not presented as a
RefGet-equivalent digest unless a sequence digest is supplied.

The command-line equivalents are:

```powershell
glio-noncode intake variants.vcf --output intake.json
glio-noncode parse-track regulatory.bed --output track.json
glio-noncode normalize 7:140453136:A>T --genome-build GRCh38
```

The Domain 01 beta extensions deepen the variation contract without silently
coercing unresolved data:

- Cat-VRS-shaped categorical definitions can be loaded from versioned JSON,
  TSV, or CSV catalogs. Matching is limited to declared category IDs, aliases,
  ontology terms, and member variation IDs; a scientific label by itself never
  creates membership. The shape follows the [GA4GH Cat-VRS project](https://github.com/ga4gh/cat-vrs),
  while external schema validation remains a release gate.
- VA-Spec-shaped annotation envelopes retain subject, context, method,
  statement, evidence-line, source-version, and raw-hash provenance. Missing
  evidence, subject/context mismatch, and conflicting supported values are
  explicit states. The shape follows [GA4GH VA-Spec](https://va-spec.ga4gh.org/en/latest/core-information-model/index.html)
  and is not a clinical interpretation.
- Literal multi-allelic records become indexed child identities that retain the
  parent input hash, source version, original alternate, and allele-specific
  genotype projection. Symbolic structural alternates abstain and phasing is
  never inferred.
- Literal SNVs and indels can be replayed against a supplied local reference
  window to enumerate equivalent placements in homopolymers and short repeats.
  Reference mismatches, unsupported classes, and window limits abstain; global
  repeat equivalence is not claimed.

The beta command boundaries are:

```powershell
glio-noncode normalize-categorical variant.json --catalog categories.tsv --output category.json
glio-noncode build-annotation annotation.json --context-key "GRCh38|glioma|adult|unknown|unknown|unknown" --output annotation.json
glio-noncode decompose-multiallelic multiallelic.json --output alleles.json
glio-noncode normalize-repeat repeat.json --output repeat.json
```

## Domain 02 structural beta extensions

The structural beta plane adds four bounded detector contracts:

- `FocalAmplificationBoundaryMapper` thresholds copy-number segments, merges
  only observed neighboring intervals, and retains left/right boundary support
  from every caller. It does not impute uncovered sequence or make a gene-level
  amplification claim.
- `ChromothripsisPatternDetector` measures bounded breakpoint clustering,
  orientation switches, and supplied copy-number oscillation. Its evidence
  index is descriptive, not a probability, and missing copy-number state keeps
  the result partial.
- `ExtrachromosomalDnaCandidateDetector` requires explicit circular evidence,
  junction support, and amplification evidence before returning a stronger
  candidate state. High copy number by itself never creates an ecDNA result,
  and conflicting linear evidence remains ambiguous.
- `EnhancerHijackingCandidateDetector` requires an exact `ReferenceContext.key`,
  an explicit structural bridge, and declared evidence channels. It keeps
  alternative target genes and does not substitute nearest-gene proximity for
  a regulatory link.

The beta command boundaries are:

```powershell
glio-noncode map-focal-amplification segments.json --output focal.json
glio-noncode detect-chromothripsis breakpoints.json --output chromothripsis.json
glio-noncode detect-ecdna structural-evidence.json --output ecdna.json
glio-noncode detect-enhancer-hijacking links.json --context-key "GRCh38|glioma|adult|unknown|unknown|unknown" --output hijacking.json
```

Every future capability wave must add implementation modules, fixtures,
negative or abstention cases, and review-facing evidence before its ledger
state is advanced.

## Domain 03 specimen context

The specimen-context plane keeps sample and specimen labels project-local and
declarative. It maps conflicting ontology rows as ambiguous, resolves a
matched normal only when the same subject has exactly one declared normal,
imports purity/ploidy tables with caller receipts, and flags declared
fingerprint conflicts while abstaining on incomplete contamination evidence.
These are local partial capabilities until locked canonical fixtures and
external calibration benchmarks are available.

## Domain 04 reference coordinates

The reference plane resolves assembly aliases separately from mapping
evidence. Chain-like tables are imported as explicit equal-length segments;
liftover scoring reports absent, unique, or competing mappings; and
pangenome coordinates retain every declared path candidate. The resolver
never treats a coordinate conversion as proof of sequence equivalence.

## Domain 05 regulatory atlases

The atlas extension parses ENCODE SCREEN-style cCRE records and supports
brain-cell, adult-glioma, and pediatric-glioma profiles over a bounded local
snapshot. Queries preserve source versions and raw hashes, gate on declared
cell state, disease, and age context, and distinguish supported overlap from
absence, ambiguity, and out-of-domain context. Atlas overlap is an annotation
observation, not proof of activity or causality.

## Domain 06 sequence and model adapters

The sequence plane emits deterministic context features separately from
external model outputs. Foundation-model and long-context adapters require
model/version and context-window metadata, validate reported deltas, retain
source hashes, and quarantine inconsistent rows. The delta ensemble reports
mean and disagreement by variant; it does not convert model output into a
probability or clinical interpretation.

## Domain 07 chromatin context

The chromatin plane keeps accessibility and histone observations tied to a
source snapshot and exact reference context. ATAC, DNase, histone, and H3K27ac
BED-like TSV/JSON rows preserve one-based normalized coordinates, assay kind,
replicate identifiers, signal values, raw hashes, and malformed-row issues.
Retriever queries require both interval overlap and an exact
`ReferenceContext.key`; an overlap from another disease, age, cell state, or
territory is reported as out-of-domain rather than reused.

Accessibility deltas are measured reference-to-alternate comparisons with
missing-value abstention and zero-baseline guards. H3K27ac is summarized as an
observation with replicate spread and ambiguity retained. Neither signal nor
delta is promoted to a causal effect, enhancer truth label, target-gene link,
or calibrated probability without external truth sets and assay-specific
validation.

The command-line boundary is:

```powershell
glio-noncode parse-chromatin accessibility.tsv --track-kind atac --output accessibility.json
```

## Domain 08 cell state, disease class, and territory

The biological-context plane parses subject-scoped disease ontology, age-route,
molecular-class, molecular-state, and malignant-microenvironment territory
observations. Each row retains its source version, raw hash, confidence,
evidence state, and exact `ReferenceContext.key`. Resolvers exclude other
subjects, report out-of-domain context rather than transporting a taxonomy
silently, and preserve one-to-many territory candidates as ambiguous.

Adult/pediatric routing uses the declared age group and abstains for unknown or
unsupported routes. Molecular class and molecular state remain separate
dimensions, so an observed class cannot fill a missing state. The assembled
`GliomaStateContext` carries the weakest component state, source IDs, an
uncertainty summary, and explicit research-use limitations. It does not make a
clinical diagnosis, prognosis, pathogenicity, treatment, or actionability
claim.

The parser boundary is:

```powershell
glio-noncode parse-context context-observations.tsv --output context.json
```

## Domain 09 3D topology

The topology plane imports long-form Hi-C and Micro-C contacts and TAD-boundary
candidates with assay labels, one-based normalized coordinates, source
versions, raw hashes, replicate/caller metadata, and quarantined malformed
rows. Contact-pair lookup is order-independent but still requires an exact
reference context; other-context overlap is not reused.

Matrix QC reports duplicate canonical pairs, zero-signal rows, signal ranges,
and partial states. Mean/max normalization is available as a transparent
descriptive transform with explicit limitations; it is not hidden ICE balancing
or a correction for assay bias. TAD boundary ensembles group calls only within
a declared tolerance and retain competing clusters. Insulation-score deltas
retain alternate-minus-reference direction, missingness, replicate count, and
zero-baseline guards. These are topology observations, not proof of causality,
enhancer activity, target-gene linkage, or clinical actionability.

The parser boundaries are:

```powershell
glio-noncode parse-contacts contacts.tsv --assay hi-c --output contacts.json
glio-noncode parse-boundaries boundaries.tsv --assay micro-c --output boundaries.json
```

## Domain 10 candidate link graph

The link plane produces context-qualified candidate relationships among
variants, regulatory elements, and genes. Coordinate-overlap links require
exact element context. Gene intervals are imported with source receipts and
support a nearest-gene baseline that retains distance ties and can abstain
outside a declared distance window. Neither overlap nor proximity is treated
as a regulatory mechanism.

cCRE assignment retains every overlapping context-matched element and exposes
one-to-many ambiguity. Enhancer-gene consensus groups method-specific evidence
by variant, element, and gene, reports confidence-weighted support, keeps
alternative genes, and marks single-method evidence partial. Contradictory
evidence is not averaged away, and context-mismatched evidence is not
transported. Candidate graphs are research evidence structures, not causal,
clinical, pathogenicity, or actionability claims.

The gene-source boundary is:

```powershell
glio-noncode parse-genes genes.tsv --output genes.json
```

## Domain 11 causal evidence structures

The causal-evidence plane builds immutable factor-graph snapshots with parent
lineage, supersession history, active-factor views, orphan diagnostics,
contradictory-edge detection, and deterministic replay. Superseded factors are
never erased from history. A typed `RegulatoryCausalHypothesis` records its
factor graph, missing evidence, prior/likelihood proxies, and contradiction
state.

Context-conditioned priors use exact context profiles and bounded feature
contributions; missing or out-of-support features abstain. Measurement
likelihoods group dependent channels before aggregation and retain missing or
contradictory measurements. Both are explicitly proxies, not calibrated
probabilities, causal effects, diagnoses, prognoses, treatment recommendations,
or actionability claims.

The replayable factor boundary is:

```powershell
glio-noncode factor-graph factors.json --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output graph.json
```

## Domain 12 cohort discovery and controls

The cohort plane builds exact-context queries with variant-kind, origin, sample,
chromosome, and callable-space criteria. It returns selected records together
with exclusion reasons and never treats an empty or context-mismatched cohort
as negative evidence. The local background model reports observed variants per
callable base, target-space expectation, source intervals, and small-sample
uncertainty without emitting an unvalidated significance claim.

Sequence-context controls use bounded Hamming distance; chromatin controls use
declared feature ranges and RMS distance. Both retain candidate pools,
distances, source IDs, cutoff criteria, partial/absent states, and exact-context
out-of-domain behavior. These are negative-control constructions for research,
not causal null proofs, clinical risk estimates, or treatment evidence.

The query boundary is:

```powershell
glio-noncode cohort-query cohort.json --output cohort-selection.json
```

## Domain 13 validation planning

The validation plane converts typed hypothesis gaps into ranked review items
without filling missing evidence. Assay eligibility routes check declared
model systems, insert bounds, controls, and readouts, and retain blocked
alternatives plus sensitivity notes.

MPRA and STARR-seq planners validate target context and reference alleles,
generate reference/alternate constructs, enforce construct budgets, and attach
required controls and readouts. Context mismatch, allele mismatch, unsupported
length, and missing inventory remain blocked or abstained. Construct generation
does not establish expression, effect size, assay success, safety, or causal
validation; expert review and institutional approvals remain required.

## Domain 14 evidence lifecycle

The evidence-lifecycle plane resolves versioned citation manifests and retains
source version, URI, checksum, raw record, and retrieval metadata for every
accepted citation. TSV, CSV, and JSON rows that lack a URI, title, or citation
text are quarantined with a row hash instead of being silently dropped.

Versioned evidence claims are assembled into immutable graph snapshots. Parent
lineage, supersession, missing citations, citation-context mismatch, active
claim IDs, and historical claim IDs are all retained. A replay reconstructs the
same content address, while appending creates a new graph version without
erasing prior claims.

Edge validation checks exact graph context, active lineage, source coverage,
and disagreement state. The contradiction tracker keeps positive, negative,
contradictory, and declared-value alternatives separate; it never averages
conflicting evidence into a false consensus. A research-only dossier envelope
records a deterministic integrity digest and remains review-required. The
digest is a content-addressed reproducibility aid, not a cryptographic identity
signature, clinical conclusion, or treatment recommendation.

The lifecycle boundaries are:

```powershell
glio-noncode parse-citations citations.tsv --source-id source-1 --source-version v1 --output citations.json
glio-noncode evidence-graph graph-input.json --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output dossier.json
```

## Domain 15 research workspaces

The workspace plane is a deterministic read model for future CLI, API,
notebook, or graphical clients. Immutable records carry typed section identity,
exact reference context, source IDs, coordinates, tags, searchable fields, and
research state. Bounded queries support text search, chromosome/interval
overlap, source and state filters, tag conjunctions, pagination, facets, and a
command-palette surface. A context mismatch returns out-of-domain rather than
transporting records silently.

Case workspaces expose manifest variants and candidate regulatory elements, and
optionally add dossier hypotheses, evidence claims, and validation routes.
Cohort workspaces keep selected records, local callable/background summaries,
and matched controls in separate sections. The variant explorer resolves a
single variant and only declared relationships. The regulatory track browser
turns parsed intervals into source-accounted overlap-searchable records while
keeping parse issues and the annotation-only limitation visible.

These are research navigation artifacts. They do not infer activity, causality,
diagnosis, prognosis, actionability, or treatment.

```powershell
glio-noncode workspace-case manifest.json --output case-workspace.json
glio-noncode workspace-track regulatory.bed --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output track-workspace.json
```

## Domain 16 typed mission runtime

The mission runtime combines the declared control-plane registry with workflow
compilation. A mission request names its research boundary and requested roles;
planning expands only declared dependencies, checks claim ceilings and review
requirements, and records a registry content address. Workflow compilation
returns a topological order, aggregate resource envelope, and explicit
network/nondeterminism warnings. An empty request abstains without compiling
hidden work.

The typed tool facade exposes owner-checked input/output contracts, safety
class, deterministic flag, network sources, mutation scope, and review
requirements. The execution sandbox adds a local/network isolation contract
and requires a registered handler for every invocation. The underlying executor
then applies policy, data-scope, sensitive-key, resource, provenance, event-log,
typed-output, human-review, and idempotency controls. Unregistered or disallowed
work is rejected; it is never treated as an abstention-free success.

The mission boundary is:

```powershell
glio-noncode mission-plan mission.json --output mission-plan.json
```

This runtime is for bounded research orchestration. It does not authorize a
clinical claim, treatment decision, or release beyond the existing review and
research-use policy.
