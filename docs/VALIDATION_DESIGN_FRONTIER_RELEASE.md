# Validation-design frontier release

A release is accepted only when public data audit, schema adapters, fixture evaluation, reconciliation, integrity, evidence closure, depth, and named assurance planes are all accepted.

The release receipt carries:

- fixture identity
- evaluation address
- quality status
- integrity status
- run identity
- bundle address

The boundary is research-use planning. It does not make claims about assay efficacy, clinical value, individual diagnosis, or causal certainty.

## Verification commands

```text
glio-noncode validation-design-frontier-data-audit
glio-noncode validation-design-frontier-evaluate
glio-noncode validation-design-frontier-quality
glio-noncode validation-design-frontier-pipeline
glio-noncode validation-design-frontier-review-csv
glio-noncode validation-design-frontier-bundle --destination validation-design-bundle
glio-noncode validation-design-frontier-bundle-verify validation-design-bundle
glio-noncode validation-design-frontier-bundle-query validation-design-bundle --resource records --operation gap_analysis
glio-noncode validation-design-frontier-bundle-schema
glio-noncode validation-design-frontier-bundle-audit validation-design-bundle
glio-noncode validation-design-frontier-bundle-observability validation-design-bundle
glio-noncode validation-design-frontier-bundle-runtime
```

The release example is checked into `examples/validation-design-public-aggregate.json` and can be compared to the in-code fixture by its content address.

## Portable offline handoff

The bundle command runs the complete 79-stage D13 runtime and writes a closed
27-artifact public aggregate directory. It includes the five source receipts,
sixteen scenario rows, eighty evaluation checks, runtime stages, quality and
release receipts, review projections, lineage, replay, data dictionary,
schema, report, and observability outputs. Each file records UTF-8 byte and
line counts plus an exact-byte content address in `bundle.json`.

`bundle-verify` checks the manifest without relying on the producing runtime:
it rejects malformed JSON, non-UTF-8 bytes, unsafe or unexpected paths,
address drift, missing files, failed public-boundary checks, and inconsistent
denominators. It then runs the independent bundle reconciliation audit.
`bundle-query` supports bounded artifact, record, evaluation-check, and source
queries, while `bundle-diff` compares two verified manifests by artifact
address. Runtime wall-clock timings are normalized in `runtime.json` so an
identical public input produces the same bundle address on different hosts.
