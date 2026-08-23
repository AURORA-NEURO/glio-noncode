# Workbench release frontier operations

The D15 C13-C16 surface is a deterministic, public-aggregate release boundary for
four workbench capabilities: structured review forms, report export, global search,
and accessibility and human-factors evaluation. These operations describe whether a
review surface is complete, whether an artifact is renderable, whether a query has
deterministic matches, and whether declared interface criteria pass. They do not
make a clinical or causal claim.

## Operation map

| Capability | Operation | Positive state | Control examples |
| --- | --- | --- | --- |
| C13 | structured review form | `reviewed` | missing required field, invalid choice, foreign context |
| C14 | report export | `exported` | empty sections, duplicate section ID, foreign context |
| C15 | search command palette | `searched` | no matches, malformed record identity, foreign context |
| C16 | accessibility and human factors | `passed` | failed criterion, partial criteria, foreign context |

Every operation has a typed input contract, explicit dispatch adapter, safe output
projection, and content address. A review state is a valid but incomplete result.
A blocked state quarantines a context boundary. A rejected state means the payload
cannot be safely interpreted.

## Review form behavior

Each form field has an identity, label, required flag, optional choices, response
presence, validity, and issue. Completion is a descriptive fraction of valid fields;
it is not a reviewer quality score. Required fields missing or choices outside the
declared vocabulary remain review. Foreign context is blocked before a form can be
treated as a release receipt.

## Report behavior

Reports accept JSON, Markdown, or CSV-oriented projections. Sections preserve ID,
title, order, rendered content, line count, and content address. The operation sorts
by declared order and section ID, detects duplicate identity, and refuses an empty
section list as a successful export. The rendered projection is deterministic over
the supplied content.

## Search behavior

Search lowercases the query, scans declared aggregate record fields, and scores
identity/title matches above ordinary field matches. Command matches are explicit
records with a command identity. Results sort by descending score, record type, and
record ID. A no-match result is review, not evidence that a record does not exist.
Record context is checked before a row is searchable.

## Accessibility behavior

The default criteria are keyboard access, labels, focus order, contrast, motion, and
reading order. Each criterion retains pass/fail, severity, and remediation text.
The score is a descriptive pass fraction. Any failed criterion is review and a
foreign context is blocked. The operation does not claim compliance with a specific
regulatory standard; it records the declared surface checks.

## Runtime

The runtime starts with data, schema, and adapter checks, evaluates 16 fixture rows,
then closes metrics, policy, lineage, reconciliation, quality, replay, review,
integrity, depth, validation, evidence, access, failure, artifact, release,
provenance, export, package, bundle, and observability planes. It emits 49 ordered
stages and requires every blocking plane to pass.
