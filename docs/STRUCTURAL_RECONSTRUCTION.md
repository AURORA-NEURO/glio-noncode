# Structural reconstruction

`glio_noncode.structural_reconstruction.StructuralReconstructor` consumes the
raw deferred records emitted by variant intake. The deferred record retains the
source allele, source line hash, INFO fields, sample values, and source ID, so
reconstruction does not need to recover information from a lossy canonical
point-variant representation.

## Supported event forms

- Reciprocal VCF breakends with `MATEID` metadata become a
  `BREAKEND_PAIR` event with two typed `Breakend` objects. Both records must
  reference each other; missing or non-reciprocal mates are errors.
- `<DEL>`, `<DUP>`, `<INV>`, and `<CNV>` become typed symbolic events when INFO
  contains an integer `END`. The event retains both interval endpoints and the
  original INFO mapping.
- Records sharing a sample and `PS` phase set become a `HAPLOTYPE` event with
  ordered `HaplotypeSegment` objects. The path is not flattened into a single
  synthetic allele.

Unsupported symbolic types, malformed brackets, missing END, and non-structural
deferred records produce issue objects. They are not guessed into a supported
event. `reconstruction_support` describes the integrity of the deterministic
parse, not a clinical or empirical probability; source measurements remain
separate evidence inputs.

## Replay surface

`ReconstructionResult` includes the source ID, deferred count, events, issues,
and a content address over all of them. This allows a later workflow to persist
the result as a bundle and to distinguish a changed source record from a
changed reconstruction implementation.

## Multi-caller and copy-number extension plane

`glio_noncode.structural_extensions` adds three bounded Domain 02 adapters:

- `SVConsensusImporter` accepts caller TSV or JSON, preserves caller versions
  and row hashes, clusters only within a declared breakpoint tolerance (or an
  explicit shared event key), and reports partial or ambiguous consensus when
  support is insufficient or breakpoints disagree;
- `ComplexRearrangementResolver` builds connected breakpoint-locus components
  from typed events and retains ambiguity when multiple event identities share
  a locus. It does not infer a canonical complex rearrangement path;
- `CopyNumberSegmentHarmonizer` sweeps all observed segment boundaries into
  atomic intervals, reports median copy number as a view, and keeps caller
  disagreement visible in every output segment.

These extensions are currently partial capabilities: local fixtures prove
lossless parsing and safe reconciliation, while locked external truth sets,
caller conformance, and transport evaluation remain release gates.
