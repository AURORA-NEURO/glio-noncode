# D10 Data Contract

## Fixture envelope

The public JSON envelope contains `fixture_id`, `version`, `boundary`, `context_key`, `foreign_context_key`, `sources`, `operations`, `cases`, and `content_address`.

| Collection | Count | Required joins |
| --- | ---: | --- |
| sources | 19 | source IDs are unique and public |
| operations | 16 | family, plane, ordinal, dependency, and source joins |
| cases | 64 | operation, family, delegate record, and source joins |

## Source records

Each aggregate source ID is prefixed by its family. The record also retains the delegate source ID, source kind, source version or release, HTTPS URI, exact context when present, public-aggregate flag, and content address. Prefixing keeps source joins collision-free when family fixtures use similar source identifiers.

## Operation records

Operations are ordered from C01 through C16. Four operations belong to each family plane. Every operation declares an input contract, output contract, dependencies, source IDs, and a control policy. Dependencies point to the prior operation, creating a deterministic chain that is easy to audit and replay.

## Case records

Each case contains the family fixture ID and family record ID used for delegation, the delegate context, sanitized delegate payload, delegate output address, expected aggregate state, expected family result state, expected issue codes, expected counts, and description. The four scenarios are `positive`, `control_a`, `control_b`, and `control_c`.

The aggregate state is `accepted` for positive cases and `review` for controls. The family result state is retained separately so `partial`, `supported`, `abstained`, `contradictory`, `invalid`, and `published` remain distinguishable.

## Safety and limitations

The compliance surface rejects patient or clinical-decision payload keys and requires public source receipts. Six release artifacts are marked `public_sanitized`. The aggregate is a research evidence surface; it is not a clinical target selector or causal effect estimator.
