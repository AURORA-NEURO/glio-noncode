# D16 coordination release gate

The coordination release gate closes the path from a public aggregate fixture
to an offline package projection. It does not release a biological or clinical
conclusion.

## Required artifacts

The canonical release retains five addressed artifacts:

1. runtime contract;
2. projection schema;
3. public source index;
4. deterministic test vectors;
5. bounded release notes.

Each artifact is offline-capable and has a digest and content address. Duplicate
addresses, missing digests, or non-offline artifacts block the release.

## Required gates

The release state is accepted only when:

- data and context audit is accepted;
- the 16-operation plan is dependency-safe;
- typed tools are deterministic and offline;
- the schedule fits capacity;
- positive and control cases reconcile;
- the hash-chained event ledger is intact;
- compute and reference registries are closed;
- monitoring and security boundaries pass;
- all 16 assignments are eligible public aggregate assignments;
- artifact addresses are unique;
- a rollback version is present;
- no blocker is retained.

## Rollback

Every release retains `rollback_version`. A rollback is a new addressed
decision with its own checks and does not delete or rewrite the source release.
If a release blocker is injected, the state becomes review and the failed
blocker remains in the manifest.

## Verification commands

```text
python -m glio_noncode coordination-runtime --output runtime.json
python -m glio_noncode coordination-quality --output quality.json
python -m glio_noncode coordination-depth --output depth.json
python -m glio_noncode coordination-replay --output replay.json
python -m glio_noncode coordination-failures --output failures.json
```

The CI workflow runs the same commands and the dedicated coordination test
modules. A nonzero result blocks the release build.
