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
```

The release example is checked into `examples/validation-design-public-aggregate.json` and can be compared to the in-code fixture by its content address.
