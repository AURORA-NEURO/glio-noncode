# Editing-design frontier schema

The schema is `editing-design-schema-v1`.

CRISPR design requires `design_id`, `context_key`, `targets`, `modes`, `guide_length`, `max_guides`, `controls`, and `readouts`. Modes are limited to `crispri` and `crispra`.

Base editing requires target sequence, reference, alternate, variant offset, editing window, controls, and readouts. Reference and alternate must be single, different bases, and the offset must be inside the declared window.

Prime editing adds PBS length, RTT length, flank length, and maximum edit length. The edit and flank constraints are retained in the output package.

Allele-specific reporter design requires reference and alternate constructs, unique construct identifiers, a positive sequence for each construct, a construct budget, controls, and readouts.

Each operation emits operation, state, issue codes, output, and a SHA-256 content address.
