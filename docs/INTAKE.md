# Variant intake

`glio_noncode.intake.VariantIntake` is the data-plane boundary between source
files and canonical `VariantIdentity` objects. It is intentionally a parser
and provenance layer, not a clinical annotation engine.

## Supported formats

| Format | Required fields | Preserved details |
| --- | --- | --- |
| VCF | `#CHROM`, `POS`, `REF`, `ALT`, plus the standard eight-column record | INFO, QUAL, FILTER, FORMAT/sample values, selected sample, raw line hash |
| TSV | chromosome, position, reference, alternate | optional ID, build, sample, and all non-key columns |
| JSON | a list or an object containing `variants` | notation or coordinate fields, annotations, sample ID, source object hash |

VCF multiallelic records become one identity per ALT. The source record and
alternate index are retained in the annotations. A selected sample with `./.`
or another no-call genotype is skipped by default; a `0/0` record is also not
treated as an observed alternate. These are explicit issue records, not silent
data loss. `include_no_call=True` can retain a no-call record for downstream
review, but does not turn it into positive evidence.

Symbolic alleles such as `<DEL>` and breakend alleles containing brackets are
reported as `unsupported_symbolic_allele` and deferred to the structural
variation module. They are never coerced into an SNV or indel.

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
