# D01 release gate

The D01 release is a research-software release of a public aggregate intake
boundary. It is not a biological or clinical release.

## Required evidence

The following gates must all pass:

| Gate | Required |
| --- | --- |
| source scope | 6 HTTPS public aggregate receipts |
| operation denominator | 16 operation specifications |
| case denominator | 64 cases: 16 positive and 48 controls |
| quality | 18 deterministic checks |
| runtime | 20 accepted stages |
| validation | 112 cells across 7 planes |
| review | 48 held controls routed |
| provenance | 64 contiguous ledger events |
| bundle | 5 offline-capable artifacts |
| replay | identical evaluation and result addresses |
| rollback | non-empty previous release version |

## Public sources

The executable source registry records public HTTPS receipts for NCBI
Variation, the NCBI reference assembly, GA4GH VRS, Ensembl variation,
ENCODE/UCSC regulatory references, and the repository control record. Source
versions are explicit. A source URL does not by itself establish the validity
of a scientific claim; it only documents the public reference boundary used by
the fixture.

## Acceptance conditions

The release state is `accepted` only when positive cases are accepted, all
controls remain non-accepted, the plan has no dependency issue, the ledger has
no broken link, the schema is public-aggregate-only, and all artifact addresses
are present. The runtime's release object contains the artifact addresses and
the rollback version.

## Non-acceptance conditions

Hold the release if any control is accepted, any positive case is held, any
source is non-HTTPS, an operation or case is missing, a replay address changes,
or a lower-level primitive returns an unsupported or ambiguous result for a
positive row. A hold is a valid safety state; it is not converted to a pass by
dropping a row.

## Change procedure

Changes to operation contracts, source versions, context keys, state vocabulary,
or payload schemas require a new fixture version and a new release receipt.
Update the focused D01 tests, run the full test suite, run compileall, audit the
capability registry, inspect the metadata boundary, and commit the build on
the main repository after the acceptance gates pass.

## Scope statement

The D01 package preserves aggregate identifiers, parser counts, identity
equivalence receipts, review issue codes, and deterministic release metadata.
It does not store private subject identifiers, raw private data, institutional
signatures, clinical decisions, or claims about an individual.
