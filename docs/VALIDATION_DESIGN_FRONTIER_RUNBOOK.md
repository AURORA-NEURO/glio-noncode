# Validation-design frontier runbook

1. Run the data audit and inspect the source and row counts.
2. Run the evaluator and confirm eighty checks pass.
3. Run the depth and validation-matrix commands.
4. Inspect the handoff and review CSV for held rows.
5. Run the full pipeline and retain its content address.
6. Review failure injection output before releasing a changed contract.
7. Compare the release bundle, report, and data dictionary.
8. Commit a coherent build after focused tests and regression tests pass.

A blocked row is quarantined by context. A review row remains visible with its issue codes and a repeatable rerun instruction. A positive row with an unexpected issue fails the fixture evaluation. Replays use the same public fixture and exact operation dispatch.
