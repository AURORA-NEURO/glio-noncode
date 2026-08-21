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

The Domain 03 scientific-beta extensions add four conservative measurement
surfaces:

- `SomaticGermlineOriginClassifier` keeps tumor/normal presence, allele
  fractions, normal read evidence, and declared population frequency as
  separate channels. Conflicting channels remain uncertain.
- `MosaicismPosteriorEstimator` measures repeated low-fraction observations
  across distinct tissues and exposes calibration metadata. Without a declared
  calibration identifier, its posterior-shaped value is explicitly uncalibrated.
- `CancerCellFractionEstimator` uses purity, total copy number, alternate copy
  number, and VAF in a transparent model. Raw values outside the model range
  are retained and marked partial rather than clamped silently.
- `SubcloneAssigner` creates relative within-sample CCF clusters and keeps
  distance-to-cluster and boundary ambiguity. It does not infer phylogeny,
  mutation order, or named biological clones.

The beta command boundaries are:

```powershell
glio-noncode classify-origin origin-observations.json --output origin.json
glio-noncode estimate-mosaicism tissue-observations.json --output mosaicism.json
glio-noncode estimate-ccf ccf-input.json --output ccf.json
glio-noncode assign-subclones ccf-estimates.json --output subclones.json
```

## Domain 04 reference coordinates

The reference plane resolves assembly aliases separately from mapping
evidence. Chain-like tables are imported as explicit equal-length segments;
liftover scoring reports absent, unique, or competing mappings; and
pangenome coordinates retain every declared path candidate. The resolver
never treats a coordinate conversion as proof of sequence equivalence.

The Domain 04 scientific-beta adapters add versioned annotation governance:

- `GencodeTranscriptAdapter` parses GTF/JSON transcript snapshots, splits
  versioned Ensembl identifiers, retains attributes and coordinates, and
  reports gene-level one-to-many transcript ambiguity.
- `ManeTranscriptAdapter` preserves MANE Select/Plus Clinical status and
  RefSeq/Ensembl cross-identifiers without selecting a preferred record when
  the catalog remains one-to-many.
- `RegulatoryOntologyAdapter` matches only declared regulatory term IDs,
  labels, and aliases. Ambiguous aliases remain ambiguous and no scientific
  label-based ontology inference is performed.
- `DiseaseOntologyMapper` maps declared source terms to explicit target
  namespaces and relationships, retaining multiple targets. It is an identity
  mapping surface, not a disease diagnosis.

The beta command boundaries are:

```powershell
glio-noncode parse-gencode gencode.gtf --output gencode.json
glio-noncode parse-mane mane.tsv --output mane.json
glio-noncode normalize-regulatory-term term.json --catalog regulatory-ontology.json --output term-normalized.json
glio-noncode map-disease-term disease.json --catalog disease-mappings.json --output disease-mapped.json
```

## Domain 05 regulatory atlases

The atlas extension parses ENCODE SCREEN-style cCRE records and supports
brain-cell, adult-glioma, and pediatric-glioma profiles over a bounded local
snapshot. Queries preserve source versions and raw hashes, gate on declared
cell state, disease, and age context, and distinguish supported overlap from
absence, ambiguity, and out-of-domain context. Atlas overlap is an annotation
observation, not proof of activity or causality.

The Domain 05 scientific-beta extensions keep molecular states separate:

- `MolecularStateAtlasAdapter` supports IDH-mutant, IDH-wildtype, and
  H3K27-altered state records with exact state and `ReferenceContext.key`
  matching. Evidence from another state or context is not transported.
- `HistoneMarkTrackHarmonizer` converts histone-mark observations into atomic
  intervals at observed boundaries, reports median signal and replicate spread,
  and keeps one-replicate and high-disagreement intervals partial or ambiguous.
  Signal remains descriptive and is not a calibrated activity call.

The beta command boundaries are:

```powershell
glio-noncode query-state-atlas state-atlas.json --molecular-state "IDH-mutant" --chromosome 7 --start 100 --end 200 --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output state-query.json
glio-noncode harmonize-histone histone.tsv --output histone.json
```

## Domain 06 sequence and model adapters

The sequence plane emits deterministic context features separately from
external model outputs. Foundation-model and long-context adapters require
model/version and context-window metadata, validate reported deltas, retain
source hashes, and quarantine inconsistent rows. The delta ensemble reports
mean and disagreement by variant; it does not convert model output into a
probability or clinical interpretation.

The Domain 06 scientific-beta extensions make sequence grammar inspectable:

- `MotifDisruptionScanner` and `MotifCreationScanner` compare reference and
  alternate windows against declared IUPAC consensus motifs. Hits retain
  one-based coordinates, strand, match score, motif source/version, sequence
  hashes, exact context, and alternate-only or reference-only evidence.
- `MotifSpacingGrammarAnalyzer` evaluates declared motif-pair spacing and
  orientation rules, retains every compatible pair, and reports unmatched
  rules instead of selecting a preferred pair silently.
- `CooperativeTFGrammarModel` applies versioned weighted interactions to
  compatible motif hits and returns per-interaction contributions, required
  missing interactions, and a reproducible descriptive score. Its result is
  explicitly not a probability, binding claim, clinical interpretation, or
  calibrated regulatory-effect estimate.

The beta command boundaries are:

```powershell
glio-noncode scan-motif-disruption motif-window.json --output motif-losses.json
glio-noncode scan-motif-creation motif-window.json --output motif-gains.json
glio-noncode analyze-motif-grammar motif-grammar.json --output grammar.json
glio-noncode score-cooperative-grammar motif-grammar.json --model-id declared-grammar --model-version 2026.1 --output grammar-score.json
```

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

The Domain 07 scientific-beta extensions make methylation context explicit:

- `MethylationRecordParser` and `MethylationContextRetriever` preserve
  one-based or BED-like coordinates, beta values, coverage, assay/sample and
  replicate metadata, source versions, raw hashes, exact context keys, and
  replicate disagreement. Records from another context are reported as
  out-of-domain rather than borrowed.
- `CpGCreationLossAnalyzer` compares equal-length allele windows and emits
  reference-only or alternate-only CpG dinucleotides with genomic coordinates.
  It can attach exact measured methylation when supplied; length-changing
  windows are explicitly out of domain for this coordinate-safe beta operation.
- `MethylationSensitiveMotifAnalyzer` evaluates declared IUPAC motif hits and
  reports beta values at zero-based sensitive motif offsets, retaining missing
  and ambiguous methylation states without imputing neighbors.
- `IdhHypermethylationContextModel` summarizes a declared IDH-mutant panel
  against an IDH-wildtype comparator with minimum-site gates, coverage-weighted
  beta, panel threshold, and comparator delta. The output is descriptive
  context evidence, not a diagnostic or genome-wide epigenetic classifier.

The beta command boundaries are:

```powershell
glio-noncode parse-methylation methylation.tsv --output methylation.json
glio-noncode query-methylation-context methylation.tsv --chromosome 7 --start 100 --end 200 --context-key "GRCh38|glioma|adult|stem_like|tumor|unknown" --output methylation-query.json
glio-noncode analyze-cpg-change cpg-window.json --output cpg-changes.json
glio-noncode analyze-methylation-motifs methylation-motifs.json --output methylation-motifs.json
glio-noncode model-idh-hypermethylation idh-panel.json --model-id idh-panel --model-version 2026.1 --context-key "GRCh38|glioma|adult|stem_like|tumor|unknown" --output idh-context.json
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

The Domain 08 scientific-beta extensions add bounded context priors:

- `DevelopmentalLineagePrior` aggregates versioned developmental-lineage
  observations only for the declared glioma age routes, preserving candidate
  alternatives, source/evidence tiers, uncertainty, and ambiguity margins.
- `GlioblastomaMalignantStatePrior` has an explicit glioblastoma/GBM disease
  gate before summarizing stem-like, cycling, mesenchymal-like, hypoxic, or
  related malignant-state candidates.
- `IdhMutantLineageStatePrior` and
  `H3K27AlteredDevelopmentalStatePrior` require their declared molecular-state
  gates, so IDH-wildtype or unsupported-state observations are not silently
  transported into another prior family.

All four emit bounded support summaries, not calibrated probabilities. Missing
observations, exact-context mismatches, contradictory rows, and close
candidate scores remain visible as abstained, out-of-domain, contradictory, or
ambiguous states. The beta command boundaries are:

```powershell
glio-noncode parse-context-prior lineage-prior.tsv --output lineage-prior.json
glio-noncode estimate-developmental-lineage-prior lineage-prior.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output lineage-result.json
glio-noncode estimate-glioblastoma-state-prior gbm-prior.json --context-key "GRCh38|glioblastoma|adult|stem_like|core|unknown" --output gbm-result.json
glio-noncode estimate-idh-lineage-prior idh-prior.json --context-key "GRCh38|glioma|adult|proneural|core|unknown" --molecular-state "IDH-mutant" --output idh-result.json
glio-noncode estimate-h3k27-developmental-prior h3-prior.json --context-key "GRCh38|glioma|pediatric|stem_like|midline|unknown" --molecular-state "H3K27-altered" --output h3-result.json
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

The Domain 09 scientific-beta extensions add topology-specific adapters and
scorers:

- `LoopStripeAdapter` parses loop and stripe features with two normalized
  anchors, feature kind, signal, resolution, replicate/caller metadata,
  source versions, hashes, and row-level quarantine.
- `PromoterCaptureContactAdapter` preserves promoter and target-element
  identity, bait metadata, coordinates, signal, exact context, and source
  receipts for promoter-capture snapshots.
- `EnhancerPromoterContactScorer` summarizes exact-context contact observations
  with replicate spread and a declared bounded signal transform. It retains
  all observations and does not turn contact into a link claim.
- `ActivityByContactScorer` combines measured activity and contact components
  under explicit scales, retaining both component states, model/version, and
  missingness. The product is descriptive evidence, not a probability or
  causal regulatory effect.

The beta command boundaries are:

```powershell
glio-noncode parse-loop-stripe loops.tsv --output loops.json
glio-noncode parse-promoter-capture promoter-capture.json --coordinate-system one_based --output promoter-capture-normalized.json
glio-noncode score-enhancer-promoter-contact contact-evidence.json --enhancer-id enh-1 --promoter-id GENE1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output contact-score.json
glio-noncode score-activity-by-contact activity-contact.json --enhancer-id enh-1 --promoter-id GENE1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-id abc-model --model-version 2026.1 --output abc-score.json
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

The Domain 10 scientific-beta extensions add evidence-path linkers:

- `ActivityByContactLinkAdapter` preserves activity and contact components,
  declared scales, variant-element-gene identity, confidence, source versions,
  and raw hashes before any graph edge is produced.
- `CoaccessibilityLinker` and `MolecularQtlLinker` create candidate graph
  edges with method identity, effect metadata, exact context, alternatives,
  and single-method partial state. Molecular-QTL p/q values use a declared
  bounded transform and are not treated as causal evidence by themselves.
- `AlleleSpecificLinkEvidenceIntegrator` keeps allele-direction evidence and
  reports gain/loss conflicts as contradictory graph state instead of averaging
  them into a selected target gene.

The beta command boundaries are:

```powershell
glio-noncode parse-activity-contact-link activity-contact.tsv --output activity-contact.json
glio-noncode link-coaccessibility coaccessibility.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --variant-id v1 --output coaccessibility-links.json
glio-noncode link-molecular-qtl molecular-qtl.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --variant-id v1 --output qtl-links.json
glio-noncode integrate-allele-specific-links allele-links.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --variant-id v1 --output allele-integrated-links.json
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

The Domain 11 scientific-beta extensions make the three mediator steps and the
allele comparison explicit:

- `SequenceToElementCausalMediator` evaluates sequence-to-element evidence only
  when source and target nodes, exact context, and mediator kind match. It
  requires independent source paths for `supported`, keeps against-direction
  and negative-control evidence, and reports bounded uncertainty and sensitivity.
- `ElementToGeneCausalMediator` and `GeneToStateCausalMediator` apply the same
  source/version, context, contradiction, and abstention gates to downstream
  mediator edges. A single positive source remains partial and a context-only
  mismatch is out of domain.
- `CounterfactualAlleleStateSimulator` compares declared reference and
  alternate state observations, reports the alternate-minus-reference delta,
  retains replicate ambiguity, and carries model/version receipts. The delta
  is descriptive and is not proof of causality or clinical effect.

The beta command boundaries are:

```powershell
glio-noncode parse-causal-evidence causal-evidence.json --output causal-evidence-parsed.json
glio-noncode evaluate-sequence-element-mediator causal-evidence.json --source-node variant:v1 --target-node element:enh-1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-id seq-element-beta --model-version 1 --output sequence-element.json
glio-noncode evaluate-element-gene-mediator causal-evidence.json --source-node element:enh-1 --target-node gene:GENE1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-id element-gene-beta --model-version 1 --output element-gene.json
glio-noncode evaluate-gene-state-mediator causal-evidence.json --source-node gene:GENE1 --target-node state:stem_like --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-id gene-state-beta --model-version 1 --output gene-state.json
glio-noncode simulate-counterfactual-allele-state allele-state.json --state-id state:open --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-id allele-state-beta --model-version 1 --output allele-state-delta.json
```

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

The Domain 12 scientific-beta extensions add four convergence surfaces:

- `RegulatoryRecurrenceTester` deduplicates variant and sample observations,
  applies callable and exact-context gates, identifies recurrence in distinct
  samples, and clusters nearby distinct variants into thresholded hotspots.
- `RegionalBurdenTester` reports callable-base burden, a declared background
  comparator, expected count, and excess ratio for one exact-context region.
  Missing comparator data remains partial, and the result is not a significance
  test.
- `FunctionalConvergenceTester` aggregates declared feature support by variant,
  contrasts observed and control pools, retains leading-feature ties, and keeps
  feature direction counts and source lineage.
- `PathwayRegulonConvergenceTester` aggregates gene-set membership for pathway
  and regulon namespaces, reports observed/control contrasts and gene coverage,
  and marks opposing activation/repression evidence contradictory.

The beta command boundaries are:

```powershell
glio-noncode parse-regulatory-recurrence recurrence.tsv --output recurrence.json
glio-noncode test-regulatory-recurrence recurrence.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output recurrence-test.json
glio-noncode test-regional-burden regional-burden.json --region-id reg-1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --background-rate 0.001 --output regional-burden-test.json
glio-noncode parse-functional-convergence functional.tsv --output functional.json
glio-noncode test-functional-convergence functional.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output functional-test.json
glio-noncode parse-pathway-regulon pathway-regulon.json --output pathway-regulon-parsed.json
glio-noncode test-pathway-regulon-convergence pathway-regulon.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --set-kind pathway --output pathway-test.json
```

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

The Domain 13 scientific-beta extensions add intervention and allele-specific
design packages:

- `CRISPRiDesignPlanner` and `CRISPRaDesignPlanner` generate deterministic,
  context-gated guide candidates with declared overlap, PAM, heuristic
  on-target, specificity, off-target, control, readout, and budget receipts.
- `BaseEditingDesignPlanner` restricts candidates to declared single-base edit
  substitutions and editing windows, retaining unsupported chemistry and
  bystander-edit blockers.
- `PrimeEditingDesignPlanner` adds explicit PBS, RTT, edit-length, and flank
  gates. These sequences are design placeholders and require editor-specific
  validation.
- `AlleleSpecificReporterPlanner` keeps reference and alternate constructs
  paired under the same context, control, readout, and construct-budget
  contract. A reporter package is not an endogenous causal claim.

The beta command boundaries are:

```powershell
glio-noncode plan-crispri validation-targets.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --max-guides 20 --output crispri.json
glio-noncode plan-crispra validation-targets.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --max-guides 20 --output crispra.json
glio-noncode plan-base-editing validation-targets.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --max-guides 20 --output base-editing.json
glio-noncode plan-prime-editing validation-targets.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --max-guides 20 --output prime-editing.json
glio-noncode plan-allele-specific-reporter validation-targets.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --max-guides 2 --output allele-reporter.json
```

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

The Domain 14 scientific-beta extensions add operational evidence views:

- `EvidenceTierAdjudicator` keeps every declared tier and support/against
  direction, reports the highest tier without deleting lower-tier alternatives,
  and marks unresolved or contradictory claims for review.
- `ProvenanceLineageViewer` projects parent claims, supersession history,
  active state, source versions, citation nodes, and content hashes without
  mutating the immutable graph.
- `UncertaintyLedgerBuilder` records measurement, context, provenance,
  transport, calibration, dependence, and review drivers with conservative
  per-claim maxima. It is not a calibrated probability.
- `ReviewerAssignmentRouter` routes active claims to explicit domain,
  provenance, statistical, assay, computational, and context roles using
  contradiction, tier, uncertainty, and context blockers.

The beta command boundaries are:

```powershell
glio-noncode adjudicate-evidence-tier tier-observations.json --context-key "GRCh38|glioma|adult|stem_like|core|untreated" --output tier-adjudication.json
glio-noncode view-provenance-lineage graph-input.json --claim-id claim-2 --output lineage.json
glio-noncode build-uncertainty-ledger uncertainty.json --context-key "GRCh38|glioma|adult|stem_like|core|untreated" --output uncertainty-ledger.json
glio-noncode route-reviewers graph-input.json --roles data_provenance domain_expert --output review-queue.json
```

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

The Domain 15 scientific-beta projections add four deep research surfaces:

- `TopologyViewer` builds a bounded two-anchor topology viewport from
  loop/stripe observations, promoter-capture contacts, contact scores, and
  activity-by-contact summaries. Interval focus, exact context, source
  versions, observation IDs, replicate metadata, deterministic node/edge
  limits, and out-of-context withholding are retained. The viewport does not
  convert contact into activity or causality.
- `CausalChainExplorer` joins sequence-to-element, element-to-gene, and
  gene-to-state mediator results. It keeps alternative paths, negative
  evidence, missing mediator kinds, contradictory edges, context mismatch,
  support, uncertainty, and source receipts visible rather than collapsing
  them into one chain score.
- `PosteriorDecompositionViewer` exposes the declared prior, exact-context
  support components, normalized descriptive shares, calibration status, and
  an unexplained residual. Components are never invented to reconcile a
  declared support value, and the result remains a research proxy rather than
  a calibrated clinical probability.
- `EvidenceTableAndFilters` provides text, context, channel, tier, state,
  source, confidence, pagination, and deterministic facet filters over saved
  workspace records. Partial, ambiguous, and unresolved evidence remains in
  the table, and filtering never changes the underlying evidence state.

These are research navigation artifacts. They do not infer activity, causality,
diagnosis, prognosis, actionability, or treatment.

```powershell
glio-noncode workspace-case manifest.json --output case-workspace.json
glio-noncode workspace-track regulatory.bed --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output track-workspace.json
glio-noncode view-topology topology.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output topology-view.json
glio-noncode explore-causal-chain causal-results.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output causal-chain.json
glio-noncode view-posterior-decomposition posterior.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output posterior-view.json
glio-noncode filter-evidence-table case-workspace.json --channel sequence --min-confidence 0.8 --output evidence-table.json
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
