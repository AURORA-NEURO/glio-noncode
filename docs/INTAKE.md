# Variant intake

`glio_noncode.intake.VariantIntake` is the data-plane boundary between source
files and canonical `VariantIdentity` objects. It is intentionally a parser
and provenance layer, not a clinical annotation engine.

## Supported formats

| Format | Required fields | Preserved details |
| --- | --- | --- |
| VCF / gVCF | `#CHROM`, `POS`, `REF`, `ALT`, plus the standard eight-column record | INFO, QUAL, FILTER, FORMAT/sample values, selected sample, raw line hash, and typed reference blocks |
| BCF | BCF v2.2 header and records | decoded INFO and FORMAT/sample values, selected sample, record hash, and typed reference blocks |
| TSV | chromosome, position, reference, alternate | optional ID, build, sample, and all non-key columns |
| JSON | a list or an object containing `variants` | notation or coordinate fields, annotations, sample ID, source object hash |

VCF multiallelic records are split into identities only for ALT alleles called
by the selected sample's complete GT (for example, `0/2` with two ALT values
emits only ALT 2, while `1/2` emits both). Uncalled ALT indices are reported as
warnings, and the source record and ALT index remain traceable. If GT is absent
or partially missing, no allele-specific filtering is inferred. No-call
genotypes are skipped by default; `include_no_call=True` retains their ALT
values for downstream review but does not turn them into positive evidence.
A sample cell containing a single `.` is expanded to missing values for its
FORMAT keys, so a missing `GT` is not mistaken for an unfiltered alternate.
Empty sample cells and values with more colon-separated subfields than FORMAT
keys are rejected with an error.
A fully reference genotype such as `0/0` is not treated as an observed
alternate by default. These are explicit issue records, not silent data loss.
When `sample_id` is explicitly provided, it must exactly match a sample in the
VCF/BCF header. A missing name is an error and suppresses variant output rather
than silently substituting another sample. If `sample_id` is omitted, a
single-sample file selects its sole sample; multi-sample files require an
explicit ID and otherwise produce a `sample_selection_required` error. Files
without sample columns remain valid for sample-independent variant intake.
Duplicate sample IDs are rejected with `duplicate_sample_id`, because a name
that identifies multiple columns cannot safely select one genotype.
Records with repeated FORMAT keys are rejected with `duplicate_format_key`;
otherwise a repeated `GT` field could be silently overwritten during parsing.
FORMAT identifiers must match the VCF identifier syntax, and `GT` must be
first when present; violations are reported as `invalid_format_key` or
`genotype_format_key_not_first` rather than being interpreted permissively.
When `##FORMAT` declarations are present, selected-sample values are checked
against the declared Type and Number. Supported cardinality rules include
fixed counts, `A` (one value per ALT), `R` (REF plus each ALT), `G` (the
genotype likelihood count implied by ALT count and selected GT ploidy), `P`
(selected GT ploidy), and the local-allele `LA`, `LR`, and `LG` forms when a
valid `LAA` list supplies the local ALT indices. `Number=M` values have their
declared Type checked, but cardinality is left to a modified-base-aware
consumer because this intake boundary has no base-modification context.
VCF values are validated lexically without rewriting their source strings;
BCF values are validated in their decoded native types. Invalid or duplicate
schema declarations are reported, as are selected values with a type or
cardinality mismatch. Undeclared FORMAT values remain preserved but are not
claimed to be schema-validated.
INFO flags are preserved as `true`, scalar values as their original strings,
and comma-delimited values as lists of original strings; numeric meaning is
not guessed without the header's INFO schema. Both intake paths use the same
representation. Empty INFO entries, invalid keys or values, and duplicate
keys are rejected with an explicit issue instead of being silently ignored or
overwritten.
When an INFO definition is present, its declared Type and fixed, A, or R
Number cardinality are checked before variants are emitted. Number=G
cardinality is intentionally not inferred for site-level INFO because the
header does not identify one sample ploidy. Undeclared INFO values remain
available as source strings and are not treated as schema-validated.

Symbolic alleles such as `<DEL>` and breakend alleles containing brackets are
reported as `unsupported_symbolic_allele` and deferred to the structural
variation module. They are never coerced into an SNV or indel.
The VCF `*` spanning-deletion allele is likewise deferred so it cannot be
misclassified as a CNV. An ALT value of `.` is a no-variant site and produces
`no_alternate_allele`; it does not create a variant identity. A dot cannot be
combined with other ALT alleles in one record.

### gVCF reference-confidence blocks

A single-ALT `<*>` or `<NON_REF>` record is represented as a
`ReferenceBlockRecord`—not as a variant—when its selected genotype is reference,
no-call, or unavailable and the block has a valid span. The parser preserves
the selected sample, genotype state, source record hash, INFO and FORMAT values,
filter, quality, and source line. A called non-reference genotype is not
reinterpreted as a reference-only block; its symbolic allele remains on the
deferred structural-variation path.

For each selected sample, `FORMAT/LEN` takes precedence when it is present and
positive. If it is absent or missing, a positive one-based inclusive `INFO/END`
is used. A `POS`-to-`LEN` block becomes the zero-based half-open interval
`[POS - 1, POS - 1 + LEN)`; the inclusive `INFO/END` fallback becomes
`[POS - 1, END)`. A present but malformed `FORMAT/LEN` is an error rather than
silently falling back to `INFO/END`. No-call reference blocks are retained as
`no_call` independently of the variant-only `include_no_call` option.

`IntakeBatch.reference_blocks` and `IntakeReceipt.reference_block_count` keep
these intervals separate from canonical variants and their `accepted_count`.
Case preparation carries the typed block records and a content address in its
variant-source provenance; reopening a prepared case revalidates each block,
the count, and the aggregate address. The block is not a variant observation
and does not by itself assert that any specific alternate allele is absent or
present.

`ReferenceBlockIndex` supports bounded interval lookup and coverage partitioning
over these records. Given an `IntakeBatch` named `batch` from
`VariantIntake.parse_text` or `VariantIntake.parse_bytes`:

```python
from glio_noncode.intake import ReferenceBlockIndex

index = ReferenceBlockIndex(batch.reference_blocks)
coverage = index.coverage(
    genome_build="GRCh38",
    chromosome="7",
    start=55_000_000,
    end=55_000_100,
    sample_id="S1",
)
print(coverage.to_dict())
```

`VariantIdentity.start` and `.end` are one-based closed coordinates. To query
the full reference span of one canonical variant without converting the
coordinates by hand, call `coverage_for_variant`; the query still requires an
explicit sample and uses the variant's exact genome build. This is a coordinate
conversion only, not liftover or an assertion that the alternate allele is
absent:

```python
variant_coverage = index.coverage_for_variant(variant, sample_id="S1")
print(variant_coverage.to_dict())
```

The CLI exposes the same operation directly on a gVCF or BCF file:

```powershell
glio-noncode reference-block-query sample.g.vcf.gz `
  --sample-id SAMPLE_01 `
  --genome-build GRCh38 `
  --chromosome 7 `
  --start 55000000 `
  --end 55000100 `
  --output coverage.json
```

For a canonical SNV or indel, the CLI can derive the reference span directly
from one-based closed variant notation. Quote the notation in PowerShell because
`>` otherwise acts as a redirection operator:

```powershell
glio-noncode reference-block-query sample.g.vcf.gz `
  --sample-id SAMPLE_01 `
  --genome-build GRCh38 `
  --variant '7:55000001:A>T' `
  --output variant-coverage.json
```

The report includes the canonical variant and conversion mode alongside the
zero-based half-open coverage result. `--variant` cannot be combined with
`--chromosome`, `--start`, or `--end`.

Use `--format bcf` for a BCF file when its extension does not identify it.
The CLI requires an explicit sample ID, accepts at most 128 MiB of source bytes
and 256 MiB of decompressed text, and includes the source-file SHA-256 and
intake receipt in its report. Parse errors or a source with no reference blocks
produce a `blocked` report and exit status 2 rather than a misleading uncovered
result.

Queries require an explicit genome build and sample (`sample_id=None` selects
only records that themselves have no sample). Coordinates are zero-based and
half-open, as on `ReferenceBlockRecord`. The result partitions every queried
base into `reference`, `no_call`, `unknown`, `uncovered`, or `conflict`, and
reports per-state base counts plus the content addresses of the contributing
blocks. Disagreeing overlapping call states are marked `conflict`; repeated
overlapping blocks with the same state retain all provenance without being
called a conflict. The summary status distinguishes complete single-state
coverage, mixed states, partial coverage, conflicts, and wholly uncovered
queries.

The index is capped at `MAX_REFERENCE_BLOCK_INDEX_RECORDS` (100,000) records and
uses sorted per-build, chromosome, and sample intervals rather than expanding
blocks into per-base storage. A single coverage result is also capped at
`MAX_REFERENCE_COVERAGE_PROVENANCE_REFERENCES` (250,000 active-block references)
so pathological nested overlaps cannot produce unbounded provenance output.
The index does not apply a quality threshold, filter failed records, establish
assay callability, or infer that an alternate allele is absent. Review the
preserved block FILTER, QUAL, and sample fields before making downstream
scientific claims.

## Receipts and manifests

Every parse returns an `IntakeBatch` with accepted identities, raw normalized
records, issues, and an `IntakeReceipt`. The receipt contains input and header
hashes, format, counts, and its own content address. `IntakeBatch.to_manifest`
embeds the receipt in metadata and records the input hash in `input_versions`
so a later run can distinguish changed source material from changed code.

## Interval lookup

`VariantIndex` provides deterministic ID lookup and same-contig interval overlap
queries over accepted identities. It does not perform liftover or assume that
coordinates from different genome builds are comparable.
