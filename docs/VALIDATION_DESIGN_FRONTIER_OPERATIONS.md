# Validation-design frontier operations

The D13 C01–C04 validation-design frontier is an independent implementation boundary for four planning operations:

- evidence-gap analysis
- assay eligibility routing
- MPRA construct packaging
- STARR-seq construct packaging

Each operation accepts a typed mapping, applies the context boundary, preserves issue codes, projects a safe output, and returns a SHA-256 content address. The public fixture uses aggregate source receipts from Europe PMC, PubMed, GDC, ENCODE, and Addgene.

## Execution contract

The operation states are deliberately narrow:

| Operation | Success state | Held states |
| --- | --- | --- |
| gap analysis | ready | review, blocked, rejected |
| assay eligibility | routed | review, blocked, rejected |
| MPRA package | packaged | review, blocked, rejected |
| STARR-seq package | packaged | review, blocked, rejected |

A context mismatch is always blocked. Missing evidence, unsupported assays, invalid construct fields, unchanged alleles, budget overflow, and empty packages remain visible as review conditions. The runtime does not infer experimental efficacy or clinical meaning.

## Runtime

Run the full deterministic rehearsal:

```text
glio-noncode validation-design-frontier-pipeline --output validation-design-runtime.json
```

The runtime records seventy-nine ordered stages, including source audit, adapter construction, schema validation, row evaluation, reconciliation, quality gating, replay, review routing, evidence closure, provenance, release checks, artifact indexing, failure rehearsal, and report surfaces. The fixture contains sixteen rows and the evaluator emits eighty checks: five planes per row.

## Safety boundary

Only public aggregate receipts and synthetic planning payloads belong in the fixture. Private credentials, individual-level records, and unsupported clinical conclusions are prohibited inputs. Outputs are suitable for research planning review and reproducibility checks.
