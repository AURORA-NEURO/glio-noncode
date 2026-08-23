# Workbench release frontier runbook

1. Compile the source and tests.
2. Run the data audit and inspect five sources, sixteen rows, and balanced roles.
3. Run evaluation and confirm eighty checks with zero failures.
4. Inspect the four positive operation outputs and every control issue code.
5. Run replay and compare evaluation addresses.
6. Run depth, quality, integrity, evidence, and validation commands.
7. Inspect the review queue and ensure each review, blocked, or rejected row is
   present.
8. Inspect the report, CSV, artifact inventory, and access manifest.
9. Run failure injection and confirm malformed inputs do not become successful.
10. Run the complete pipeline and inspect all forty-nine ordered stages.

The checked-in fixture is self-contained. Public URLs act as provenance anchors and
scope declarations; the local run does not need a network request. Store the fixture
address, evaluation address, runtime run ID, review CSV, and release note with a
handoff. Keep the controls in the package so a reviewer can reproduce the boundary.

## Handoff contents

- fixture JSON and fixture content address;
- evaluation JSON and passed-check count;
- runtime JSON and ordered stage list;
- review CSV and stable header;
- source access manifest;
- artifact inventory and bundle receipt;
- failure-injection result;
- schema version and data dictionary;
- unresolved review and blocked row IDs;
- release note and reviewer decision.

## Interpretation rules

An exported report describes a rendering receipt, not the truth of its content.
A searched record describes a deterministic match, not evidence of absence.
An accessibility pass describes declared criteria, not a standards certification.
A reviewed form describes field completion, not reviewer correctness.
A blocked row remains in the handoff even when the rest of the runtime is accepted.
An accepted runtime closes the declared operational boundary and nothing beyond it.
