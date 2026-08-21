# C09–C12 governance release format

The release manifest is the final bounded artifact for Domain 04 C09–C12. It
does not contain source payloads. It contains addresses and check results that
allow a later run to determine whether the same evidence plane was evaluated.

## Top-level fields

| Field | Meaning |
|---|---|
| `release_id` | stable release identity |
| `fixture_id` | public aggregate fixture identity |
| `fixture_version` | fixture release boundary |
| `context_key` | exact reference context |
| `state` | `published`, `review`, or `blocked` |
| `checks` | release checks with addresses |
| `evaluation_address` | execution report address |
| `quality_address` | integrated quality report address |
| `replay_address` | replay report address |
| `bundle_address` | accepted-only bundle address |
| `content_address` | manifest address over all release fields |

## State rules

`published` requires every release check to pass. The checks require:

1. all artifacts to use the same fixture ID;
2. all artifacts to use the same fixture version;
3. all artifacts to use the same context;
4. the execution report to be accepted;
5. the integrated quality gate to be accepted;
6. replay to pass all deterministic floors;
7. the accepted-only bundle to verify;
8. exactly four supported positive entries to be present;
9. all controls to be excluded from the accepted-only bundle;
10. the evaluation address chain to close;
11. no input collection to appear in the bundle.

If the execution and quality views are valid but a publication prerequisite
needs review, the state is `review`. If execution or quality is not accepted,
the state is `blocked`.

## Check format

Each check has this shape:

```json
{
  "check_id": "quality",
  "passed": true,
  "detail": "integrated quality gate is accepted",
  "content_address": "sha256:..."
}
```

The check address covers the check ID, Boolean outcome, and detail. A manifest
verifier recalculates every check address and then recalculates the manifest
address. A published manifest with any failed check is invalid.

## Bundle format

The accepted-only bundle entry fields are:

| Field | Meaning |
|---|---|
| `record_id` | fixture record identity |
| `capability_id` | C09, C10, C11, or C12 capability |
| `operation` | operation enum value |
| `role` | positive or control role |
| `state` | adapter state |
| `primary_count` | operation-specific bounded count |
| `secondary_count` | operation-specific bounded count |
| `issue_codes` | visible review issues |
| `accepted` | receipt acceptance result |
| `content_address` | entry address |

The JSON, CSV, and Markdown renderings carry the same entry fields. CSV joins
issue codes with a pipe. Markdown renders a compact table. None of the three
renderings includes original records, resource arrays, restriction rows, or
query payloads.

## Reproducibility

To regenerate the release locally:

```text
glio-noncode build-reference-governance-release examples/reference-governance-public-aggregate.json --output governance-release.json
```

To inspect the runtime stage sequence:

```text
glio-noncode run-reference-governance-pipeline examples/reference-governance-pipeline-accepted.json --output governance-pipeline.json
```

The runtime executes data audit, evaluation, replay, scenarios, lineage,
quality gate, reconciliation, bundle verification, and context verification.
Every stage has a bounded detail string and a content address.

## Review handling

Controls remain part of the evaluation and replay reports. They are not
deleted. The accepted-only bundle filters them out only after checking that
positive receipts are supported. A control can be inspected by generating a
full bundle without `--accepted-only` or by reading the evaluation report.

The distinction matters for the four operations:

- an ambiguous gene alias is not a selected gene;
- a population disagreement is not averaged away;
- a snapshot hash mismatch is not accepted as a stale cache;
- missing or conflicting permissions are not treated as permission.

## Source receipts

The release references public source receipt IDs through the fixture and
lineage artifacts. Source receipts carry public URI, release, access date,
license, and scope. They are pointers to a public boundary, not a claim that
the repository contains or controls the source bytes.

## Verification behavior

The writer refuses to write a manifest if address verification fails. The CLI
returns zero only for a publishable manifest. The CI job runs the full test
suite, format checks, compilation, source-boundary commands, bundle generation,
runtime execution, and release creation.
