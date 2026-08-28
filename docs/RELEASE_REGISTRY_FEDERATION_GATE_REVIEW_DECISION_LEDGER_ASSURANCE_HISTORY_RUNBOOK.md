# Assurance-history operator runbook

This runbook is for a reviewer operating the longitudinal release-registry
federation gate review decision-ledger assurance history. It assumes that
upstream downloaded-data processing has already created current-format
decision-ledger or assurance-gate packages.

The runbook is intentionally offline-first. A reviewer can execute every
verification step against local package bytes and retain the resulting public
summary for a later review.

## 1. Before starting

Confirm that the current checkout is the intended `glio-noncode` build.

Confirm that the input directories are copies of persisted package outputs.

Confirm that each input directory is a regular directory.

Confirm that input order is the intended chronological or review order.

Confirm that the output location is separate from all input locations.

Confirm that no input is being edited in place.

Confirm that the output location may be created, or pass explicit overwrite
authorization for a prior demonstration output.

Do not rename an old artifact to make it resemble a current package.

Do not remove unknown fields from an old manifest.

Do not put local paths into a report intended for publication.

## 2. Package types

### Decision ledger input

A decision ledger is the preferred input when the upstream pipeline has
completed review routing and append-only decisions. The history demo recomputes
the independent assurance gate for each ledger.

Required current package files are owned by the review module and must be
verified by its loader.

The ledger is not itself a history entry.

The ledger becomes a history entry only after independent assurance succeeds.

### Assurance-gate input

An assurance-gate package can be used when independent assurance has already
been persisted. The history demo loads the exact current assurance package and
uses its typed gate projection.

The assurance package is not re-serialized into the history entry.

The assurance package remains available for detailed finding and check review.

### History output

A history output contains exactly three files:

```text
manifest.json
history.json
entries.json
```

### Diff output

A diff output contains exactly two files:

```text
manifest.json
diff.json
```

## 3. Fast path: one downloaded decision ledger

Run:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_demo.py \
  --ledger ./downloaded/review-run/ledger \
  --snapshot-id downloaded-review-run \
  --destination ./out/assurance-history \
  --format summary
```

Expected successful output includes:

`source_kind` equal to `decision-ledger`.

`source_count` equal to one.

`entry_count` equal to one.

`initial_count` equal to one.

`state` equal to `promote`, `hold`, or `block`.

`history_address` and `head_address` with deterministic prefixes.

`release_ready` equal to the terminal gate decision.

Exit status zero means the history is valid and promotable.

Exit status two means the history is valid but held or blocked.

Exit status one means the input or write operation failed.

The output status is not a replacement for inspecting the public summary.

## 4. Fast path: multiple downloaded decision ledgers

Pass each ledger in input order:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_demo.py \
  --ledger ./downloaded/run-one/ledger \
  --ledger ./downloaded/run-two/ledger \
  --ledger ./downloaded/run-three/ledger \
  --snapshot-id run-one \
  --snapshot-id run-two \
  --snapshot-id run-three \
  --destination ./out/assurance-history \
  --format markdown
```

The three snapshot IDs must align with the three ledgers.

If snapshot IDs are omitted, each assurance-gate bundle address is used.

Default IDs are stable but can be less descriptive for human review.

Use explicit IDs when the review protocol has a stable external run label.

Do not use timestamps as the only identity when a stable run identifier is
available.

The history entry ordinal is determined by argument order.

The module does not infer chronology from directory modification times.

## 5. Fast path: persisted assurance gates

Run:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_demo.py \
  --assurance-gate ./downloaded/run-one/assurance-gate \
  --assurance-gate ./downloaded/run-two/assurance-gate \
  --destination ./out/assurance-history \
  --format summary
```

Do not combine `--ledger` and `--assurance-gate`.

If both are needed for a review, run the ledger mode first, then separately
verify the assurance-gate packages and compare the resulting histories.

## 6. Verify a written history

The CLI verify command is:

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-verify \
  --input ./out/assurance-history
```

The loader checks the file set first.

The loader checks regular-file and symlink rules.

The loader checks canonical bytes.

The loader checks manifest byte receipts.

The loader checks typed mapping fields.

The verifier checks entry ancestry.

The verifier checks snapshot uniqueness.

The verifier checks transition recomputation.

The verifier checks counter conservation.

The verifier checks terminal projection.

The verifier checks the history address.

Use this command after copying a package between workspaces.

## 7. Query a history

Summary:

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-query \
  --input ./out/assurance-history \
  --resource summary
```

All entries:

```text
...-history-query --input ./out/assurance-history --resource entries
```

Only regressions:

```text
...-history-query --input ./out/assurance-history --resource entries --transition regressed
```

Only held gates:

```text
...-history-query --input ./out/assurance-history --gate-state held
```

Only non-promotable entries:

```text
...-history-query --input ./out/assurance-history --release-ready false
```

The long-form examples are abbreviated with `...` only in this runbook. The
actual CLI requires the complete command string.

Use `--format csv` for fixed-column review tooling.

Use `--format markdown` for a human review packet.

Use `--format json` for programmatic processing.

Every result is bounded.

## 8. Compare histories

Build a diff:

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-diff \
  --baseline ./out/baseline-history \
  --candidate ./out/candidate-history \
  --destination ./out/history-diff \
  --format summary
```

The diff retains baseline and candidate history addresses.

The diff joins on stable snapshot IDs.

Added snapshots are visible.

Removed snapshots are visible.

Unchanged snapshots are visible.

Changed snapshots are visible.

Improved directions are visible.

Regressed directions are visible.

Mixed direction is retained when both kinds occur.

Verify the diff:

```text
...-history-diff-verify --input ./out/history-diff
```

Query only regressions:

```text
...-history-diff-query --input ./out/history-diff --resource items --direction regressed
```

## 9. Interpreting transitions

`initial` means the first entry has no comparison predecessor.

`stable` means the public quality projection is unchanged.

`improved` means the quality vector moved upward without a competing worse
dimension.

`regressed` means the quality vector moved downward without a competing better
dimension.

`changed` means the projection changed but the quality order is incomparable
or intentionally mixed.

Transition values describe the relationship between entries.

History state describes the terminal release decision.

Do not interpret `improved` as automatic release approval.

Do not interpret `stable` as proof that external evidence is scientifically
correct.

Do not interpret `changed` as a failure without inspecting the diff item.

## 10. Interpreting states

`empty` means no gate was observed.

`promote` means the terminal gate is accepted and release-ready.

`hold` means the terminal gate is accepted for review but not release-ready.

`block` means the terminal gate is not accepted for promotion.

An empty history is valid for typed construction but not promotable.

A held history is valid evidence and should be routed to review.

A blocked history is valid evidence of a blocking condition and should be
retained with its source package.

## 11. Address inspection

Record the history content address from the summary.

Record the terminal head address.

Record the entry address for every item needing review.

Record the baseline and candidate addresses from a diff.

Use addresses when communicating between workspaces.

Avoid using local directory names as evidence identifiers.

The same input projections should produce the same addresses across machines.

Different history IDs intentionally produce different history addresses.

Changing a snapshot ID changes the entry identity graph.

Changing input order changes the chain and therefore the history address.

## 12. Failure handling

### Missing path

Check spelling and package handoff completeness.

Do not create an empty directory and treat it as evidence.

### Wrong file count

List the directory without modifying it.

Compare it with the producing module's exact package contract.

Route the artifact back to the producer.

### Legacy shape

Preserve the rejected artifact.

Record that it is incompatible with the current history boundary.

Use the producing module to rebuild a current package if the source evidence is
still authorized and available.

### Manifest mismatch

Do not hand-edit byte counts or addresses.

Rebuild from typed values.

If the bytes came from an untrusted transfer, re-copy the package and verify
the original source.

### Duplicate snapshot

Choose stable unique IDs.

Do not append the same run twice under an alias.

If two records are distinct, make their stable identity explicit.

### Head mismatch

Reload the latest history.

Compare the expected address used by the writer.

Treat a mismatch as a concurrency signal, not a reason to overwrite.

### Valid hold or block

Keep the package.

Use status two as a review routing signal.

Inspect source findings, checks, and ledger decisions at the linked addresses.

## 13. Safe overwrite procedure

The writer refuses to reuse an existing destination by default.

First verify the existing package.

Second decide whether replacement is authorized.

Third preserve any package needed for audit.

Fourth pass `--allow-existing` only for the intended destination.

Fifth reload and verify the new package.

Never point overwrite at a workspace root.

Never use a wildcard destination.

Never overwrite a source package as a shortcut.

## 14. Review checklist per entry

- [ ] Snapshot ID is recognizable and unique.
- [ ] Previous entry address is correct.
- [ ] Gate address resolves to a current assurance-gate package.
- [ ] Assurance address resolves to current independent findings.
- [ ] Ledger address resolves to the review decision ledger.
- [ ] Gate state is understood.
- [ ] Acceptance matches the source gate.
- [ ] Release readiness matches the source gate.
- [ ] Finding counts conserve.
- [ ] Check counts conserve.
- [ ] Transition matches the prior entry.
- [ ] Entry content address recomputes.

## 15. Review checklist per diff

- [ ] Baseline history verifies.
- [ ] Candidate history verifies.
- [ ] Baseline and candidate addresses are retained.
- [ ] Every snapshot join has one action.
- [ ] Added records are expected.
- [ ] Removed records are explained.
- [ ] Changed records have both entry addresses.
- [ ] Improved records have a credible explanation.
- [ ] Regressed records have an assigned review owner.
- [ ] Aggregate state matches item directions.
- [ ] Diff content address recomputes.

## 16. Privacy checklist

- [ ] Reports contain no local input path.
- [ ] Reports contain no temporary directory name.
- [ ] Reports contain no email field.
- [ ] Reports contain no user field.
- [ ] Reports contain no model or language field.
- [ ] Reports contain no secret or token field.
- [ ] Reports contain only public address and outcome projections.
- [ ] Published packages contain only exact expected files.

## 17. Reproducibility checklist

- [ ] Same code build is used.
- [ ] Same input bytes are used.
- [ ] Same input order is used.
- [ ] Same snapshot IDs are used.
- [ ] Same history ID is used.
- [ ] Rebuilt history address matches.
- [ ] Rebuilt entry addresses match.
- [ ] Rebuilt diff address matches.
- [ ] Canonical JSON bytes match.

## 18. Offline handoff

Copy the complete history directory.

Copy the complete diff directory when a comparison exists.

Copy the source assurance and decision-ledger directories referenced by the
entries.

Copy the public summary separately if the review system needs a short index.

Do not copy only `history.json`; it is intentionally not a standalone package.

Do not copy only `entries.json`; the manifest is needed for byte verification.

Verify after copying.

Communicate addresses, not local paths.

## 19. CI interpretation

The Actions workflow compiles the integrated surface.

It runs focused history tests.

It runs upstream assurance tests.

It runs the public-surface audit.

It invokes the capability command.

CI does not fetch the private or external downloaded dataset.

Real downloaded-data validation belongs in a controlled local or review run.

A green CI result proves contract coverage, not scientific validity.

## 20. Escalation rules

Escalate a repeated canonical-byte failure to the package producer.

Escalate a repeated manifest linkage failure to the transfer owner.

Escalate unexpected regressions to the release reviewer.

Escalate a public-boundary failure before publishing any artifact.

Escalate a duplicate snapshot when identity cannot be resolved.

Escalate a head mismatch when concurrent writers are both active.

Escalate a legacy artifact when the source pipeline claims current format.

Do not resolve a contract failure by weakening the verifier.

## 21. Operator summary

Load only current typed packages.

Recompute assurance from ledgers.

Build histories in explicit order.

Persist exact packages.

Verify after writing.

Query bounded resources.

Diff verified histories.

Inspect regressions.

Keep held and blocked evidence.

Promote only a valid promotable terminal state.

Preserve public, path-free outputs.
