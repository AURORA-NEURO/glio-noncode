# Streaming variant import

`glio-noncode` has two intake boundaries for variant files. `intake` is the
small-document adapter used to construct a case manifest. `stream-variants`
is the bounded transport boundary for larger VCF, gVCF, raw BCF, and BGZF BCF
sources.

## Guarantees

The streaming boundary:

- consumes VCF text one line at a time;
- decodes BGZF BCF one compressed member at a time;
- frames raw BCF from byte chunks without copying the complete body;
- accumulates a SHA-256 input address over every source byte;
- accumulates a separate header address;
- splits multiallelic records into one row per ALT while retaining the parent
  row hash;
- skips no-call and reference-only genotypes by default, with explicit opt-in
  switches for both policies;
- retains symbolic alleles as deferred rows instead of treating them as linear
  alleles;
- parses VCF breakend mate contig, coordinate, bracket, local side, and
  orientation into a structural boundary receipt; and
- bounds retained rows and retained issue detail independently from source
  traversal.

The receipt contains `record_count` for source records traversed and
`row_count` for rows produced after multiallelic decomposition. `accepted_count`
counts unique, linear rows with supported normalization. `deferred_count`
counts structural or symbolic rows that are intentionally retained for a
future specialized service. A report is not accepted when an error, invalid
row, record ceiling, or retained-row ceiling occurs. Warnings can be present in
an accepted report and are exposed through `requires_review`.

## CLI

```powershell
glio-noncode stream-variants calls.vcf `
  --source-id cohort-vcf `
  --genome-build GRCh38 `
  --max-records 1000000 `
  --max-retained-rows 100000 `
  --output streaming-receipt.json

glio-noncode stream-variants calls.bcf `
  --input-format bcf `
  --source-id cohort-bcf `
  --output streaming-bcf-receipt.json

glio-noncode stream-variants calls.gvcf `
  --input-format gvcf `
  --include-reference `
  --output streaming-gvcf-receipt.json

glio-noncode normalize-breakend 7 100 'G]17:198982]' `
  --reference N `
  --output breakend-receipt.json
glio-noncode streaming-intake-schema
glio-noncode streaming-intake-capabilities
glio-noncode breakend-normalization-schema
```

The command reads a file handle or byte stream directly. Its output rows are
bounded by `--max-retained-rows`; source traversal still continues so the
input hash and omitted-row count remain accurate. A non-zero exit code signals
that the report is invalid or lossy.

## API

The raw-body endpoint accepts a VCF or BCF body and does not use the JSON
reader:

```text
POST /v1/intake/stream?format=vcf&source_id=cohort-vcf&genome_build=GRCh38
Content-Type: text/vcf
Content-Length: ...
```

For BCF, use `format=bcf` and `Content-Type: application/octet-stream`.
Optional query controls are `sample_id`, `include_no_call`,
`include_reference`, `max_records`, `max_retained_rows`, and `max_issues`.
The loopback deployment permits the request under the existing deployment
policy; non-loopback deployments still require the configured write scope and
audit policy.

Read-only contract routes are:

- `GET /v1/intake/streaming/schema`
- `GET /v1/intake/streaming/capabilities`
- `GET /v1/intake/breakend/schema`

## Breakend boundary

The accepted grammar is the VCF bracket form with matching brackets around a
mate coordinate, for example `G]17:198982]`, `]13:123]A`, `G[17:20[`, or
`[13:123[A`. The parser normalizes contig spelling, validates a positive
one-based mate coordinate, and records the bracket orientation. It does not
claim that a single VCF ALT is a complete paired structural event. Pairing,
remote sequence resolution, reference-equivalence proof, and VRS structural
representation remain deferred and visible in the normalization report.

Malformed bracket forms are invalid. Symbolic forms such as `<DEL>` and
`<NON_REF>` are deferred without guessing a linear interval. This preserves
the source row for a structural or gVCF-specific downstream adapter.

## Determinism and resource limits

Reports have no wall-clock field. Equal source bytes, source ID, format, and
limits produce equal input, header, row, normalization, and report addresses.
Changing a source line ending changes the input address because the address is
over the bytes actually traversed.

The defaults are one million source records, one hundred thousand retained
rows, and ten thousand retained issues. Headers are bounded at five MB, one
BCF record at sixteen MB, and one BGZF member at 64 KiB. The HTTP raw-body
ceiling is twenty GB; callers should choose materially smaller limits for
interactive use. Limits are resource controls, not scientific quality claims.

This module is a research-use transport and review boundary. It does not
perform clinical interpretation, establish pathogenicity, or replace a
validated indexed variant and structural-variant service.
