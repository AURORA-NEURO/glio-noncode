# Sequence inference

`glio_noncode.sequence_inference.SequenceInference` compares a declared
variant against a real `SequenceSlice` retrieved from a public reference
source. It first verifies that the variant interval is inside the window and
that the declared reference allele matches the retrieved sequence. A mismatch
or an incomplete window produces a typed abstention.

`MotifScanner` supports explicit IUPAC motif patterns on both strands. The
result records reference and alternate sequence hashes, created and disrupted
hits, length delta, GC fractions, source ID, and limitations. These are
deterministic sequence observations, not binding measurements or causal
probabilities. `SequenceAnalysisResult.to_claim` therefore emits a computed
claim with `score=None`; downstream calibration and functional assays remain
separate modules.

The single-variant `analyze` application gate requires a matching assembly
(with only the declared `GRCh38`/`hg38` and `GRCh37`/`hg19` aliases treated as
equivalent), a matching contig, an interval consistent with the literal
reference allele, and unambiguous A/C/G/T alleles. SNVs and equal-length
literal substitutions can be analyzed. Structural, ambiguous, no-op,
malformed, or length-changing edits return an `abstained` result from this
single-variant path.

`SequenceInference.analyze_haplotype` is the explicit multi-variant path for
caller-phased SNVs and indels. Every record must name the same sample, phase
set, and haplotype index; the method never infers phase from unphased calls.
Each reference allele must match the supplied window, and overlapping records
abstain until the complex allele is normalized. For indels, shared allele
prefixes and suffixes retain their reference coordinates, inserted sequence
has no asserted genomic coordinate, and downstream unaffected bases keep their
original genomic mapping. Motif hits that cross inserted or deleted sequence
junctions therefore carry a haplotype-window interval while omitting a
misleading contiguous genomic interval. Reference-allele mismatch remains a
distinct `reference_mismatch` state, and a variant outside the supplied window
remains `out_of_window`.

`PhasedVariantIdentity.from_vcf_call` converts one selected ALT from a VCF
genotype into one or more haplotype assignments. It requires a complete,
pipe-separated `GT`, an explicit non-missing `PS` label, the declared ALT count
and index, and a variant identity carrying an explicit sample ID. It returns an
empty tuple when that ALT is not present. Slash-separated, haploid-without-an
explicit phase separator, and partially missing calls are rejected instead of
being assigned by allele order. For rows produced by `StreamingVariantImporter`,
`StreamingVariantRow.to_phased_variant_identities()` performs that mapping from
the retained source ALT index, sample name, `GT`, and `PS`; callers do not need
to parse split-record labels. The importer still does not establish that the
source phasing is biologically correct, and phase-set labels must be consistent
across records before their assignments are combined.

The haplotype result includes a content address, reference and alternate
sequence hashes, allele IDs, coordinate-aware motif deltas, and explicit
limitations. The VCF adapter decodes an explicit call but does not establish
that the source phasing is biologically correct or infer phase across records.

Motif scanning bounds input sequence length and consumes no more than one over
the configured motif-definition limit from a caller-provided iterable. It also
has explicit ceilings for estimated base comparisons, emitted hits, and copied
matched-sequence bases. Exceeding a ceiling raises a validation error before
returning a partial hit set. The per-scan hit ceiling is set so created and
disrupted hits together remain within the Atlas sequence-analysis result
ceiling. These bounds limit runaway work and output size; they do not make a
motif match a functional binding measurement.
