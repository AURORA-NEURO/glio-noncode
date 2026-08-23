# Validation-design frontier schema

The schema version is `validation-design-schema-v1`. It is explicit for each operation.

## Gap analysis

Required fields are `target_id`, `context_key`, `required_evidence`, and `available_evidence`. Each available evidence row carries a dimension, state, and optional public source identifiers. A dimension is covered only when its state is `supported` or `ready`.

## Assay eligibility

Required fields are `target_id`, `context_key`, `requested_assay`, and `capabilities`. A capability is routable only when its assay matches the request and its supported flag is true. Readouts and bounded limits remain in the route output.

## Reporter packages

MPRA and STARR-seq packages require `package_id`, `context_key`, `construct_budget`, `constructs`, and `controls`.

MPRA constructs require an identifier, reference allele, alternate allele, and positive sequence length. Equal reference and alternate alleles are held.

STARR-seq constructs require an identifier, element identifier, strand, and positive sequence length. Strand must be `+` or `-`.

## Addressing

Fixture, receipt, record, execution, and assurance objects use canonical JSON hashing with a `sha256:` prefix. The loader checks fixture identity and address before accepting an external JSON file.
