# Contributing

Contributions should preserve the inspectability and research boundary of the project.

## Before opening a change

1. Run the unit suite and bytecode compilation checks.
2. Add or update fixtures when changing a contract.
3. Keep every derived number traceable to supplied inputs and a versioned rule.
4. Preserve append-only evidence semantics and explicit missing/negative states.
5. Describe context, data access, calibration, limitations, and failure modes for new adapters.

## Change discipline

Use focused commits with a clear scope. Large functional builds should be committed once they are internally coherent, tested, and documented. Do not include generated caches, local data, credentials, or controlled data in the repository.

## Scientific review

Changes that alter evidence semantics, context transport, hypothesis aggregation, validation planning, or release policy need domain review. Passing tests is necessary but not sufficient evidence for a scientific claim.
