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
