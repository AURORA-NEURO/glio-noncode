# Reference registry and projection

`glio_noncode.reference_registry` keeps reference identity separate from
coordinate projection. The default registry exposes human GRCh38/hg38 and
GRCh37/hg19 aliases with source IDs for the public Ensembl and UCSC adapters.
An alias resolves to one canonical assembly; ambiguous aliases are rejected.

## Explicit mapping segments

Liftover is only performed through supplied `MappingSegment` records. Each
segment declares source and target assemblies, contigs, one-based inclusive
intervals, strand, and a source-map version. The implementation does not
download or invent a chain file. A production mapping adapter must validate
its chain or graph source before constructing the catalog.

`ReferenceProjector` then:

- returns an identity result for the same assembly;
- maps a full point or interval variant through one containing segment;
- reverse-complements alleles on a reverse-strand segment;
- records mapping ID, source/target assemblies, strand, and map version; and
- abstains for missing segments, partial/multiple coverage, different species,
  and breakends that need mate-aware graph projection.

An abstention is not a negative result. It is a typed projection outcome that
can be routed to a reference-build or structural review gate.
