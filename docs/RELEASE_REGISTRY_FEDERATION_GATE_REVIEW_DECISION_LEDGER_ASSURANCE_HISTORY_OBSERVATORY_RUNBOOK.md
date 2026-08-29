# Assurance-history observatory runbook

This runbook is for an operator assembling a review view from several
downloaded release-registry runs. It assumes the upstream decision-ledger
assurance-history package has already been built and independently verified.

## 1. Establish the source set

Select one current-format history package per source run. Keep a stable public
member ID for each source. A member ID is a review identity, not a local path,
person name, account name, or machine name.

Example source layout:

```text
review-input/
  run-one/history/{manifest.json,history.json,entries.json}
  run-two/history/{manifest.json,history.json,entries.json}
```

Before building the observatory, verify each input with the upstream history
command:

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-verify \
  --input review-input/run-one/history
```

Repeat for every run. A failed upstream verification is corrected at the
source boundary; it is not bypassed by observing its raw files.

## 2. Build the observatory

Use repeated `--history-directory` values in the same chronological or review
order, and repeated `--member-id` values in the matching order:

```text
python -m glio_noncode.cli \
  <observatory-command> \
  --history-directory review-input/run-one/history \
  --history-directory review-input/run-two/history \
  --member-id download:run-one \
  --member-id download:run-two \
  --observatory-id review-observatory:release-window-2026-08-27 \
  --destination review-output/observatory \
  --format summary
```

The default command name is documented in the main operator contract. The
destination is an exact five-file package. A ready result exits `0`; a valid
hold, mixed, block, or empty result exits `2`; malformed input exits `1`.

## 3. Read the summary

The summary answers five immediate questions:

1. How many source histories were observed?
2. How many total review entries do they contain?
3. Are any members held, blocked, empty, or mixed?
4. Are all members accepted and release-ready?
5. What content address binds the exact observatory package?

The state rules are conservative. One blocked member blocks the aggregate. A
held member holds the aggregate. A ready state requires every member to be
accepted and release-ready. A mixture containing an empty member is explicit
and is not promoted.

## 4. Inspect members and metrics

Query all member projections:

```text
python -m glio_noncode.cli \
  <observatory-command>-query \
  --input review-output/observatory \
  --resource members \
  --format markdown
```

Inspect only non-ready member states:

```text
python -m glio_noncode.cli \
  <observatory-command>-query \
  --input review-output/observatory \
  --resource rejected \
  --format json
```

The `members` resource is source-scoped. The `metrics.json` artifact is the
aggregate view of the same records; it is useful for dashboards and batch
review, but it is not an independent authority.

Inspect the verification checks without unpacking or reconstructing the
package:

```text
python -m glio_noncode.cli \
  <observatory-command>-verification-query \
  --input review-output/observatory \
  --resource failed \
  --format markdown
```

Use `--resource checks` with `--severity required`, `--passed`, `--text`,
`--offset`, and `--limit` for bounded review windows. The query reloads and
verifies the exact package before selecting records. Its result carries the
verification content address and a separate query content address.

## 5. Review a non-promoted result

For `held`, `blocked`, `mixed`, or `empty` output:

- preserve the package as a review artifact;
- query `members` and identify the affected member IDs;
- inspect each upstream history package by its `history_address`;
- compare the observatory with the prior package if one exists; and
- document the domain reason separately from the operational state.

The observatory does not state why a scientific result is true or false. It
only reports the upstream review posture and contract outcomes.

## 6. Compare two observatories

Build a member-level diff:

```text
python -m glio_noncode.cli \
  <observatory-command>-diff \
  --baseline review-output/previous-observatory \
  --candidate review-output/observatory \
  --destination review-output/observatory-diff \
  --format summary
```

Then query regressions:

```text
python -m glio_noncode.cli \
  <observatory-command>-diff-query \
  --input review-output/observatory-diff \
  --resource regressed \
  --format markdown
```

An added member is not automatically evidence of scientific improvement. The
direction describes the stored operational quality vector. Use the upstream
history and domain review to interpret the change.

## 7. Verify package integrity

Verify the observatory package after copying or receiving it:

```text
python -m glio_noncode.cli \
  <observatory-command>-verify \
  --input review-output/observatory
```

Verify the diff separately:

```text
python -m glio_noncode.cli \
  <observatory-command>-diff-verify \
  --input review-output/observatory-diff
```

A verification failure indicates byte, manifest, linkage, or recomputation
drift. Treat the package as unusable until it is rebuilt from its source
histories.

## 8. HTTP use

The same operations are available below the existing decision-ledger
assurance-history route:

```text
.../decision-ledger/assurance-history/observatory
```

Build with repeated parameters:

```text
...?history_directory=review-input/run-one/history&history_directory=review-input/run-two/history&member_id=download:run-one&member_id=download:run-two&destination=review-output/observatory&format=summary
```

Use `/query?input=...&resource=members` for members and
`/verification/query?input=...&resource=failed` for failed verification checks.
Use `/diff?baseline=...&candidate=...&destination=...` for a diff. Use the schema
and capability endpoints before wiring a consumer so that resource names and
package files remain explicit.

## 9. Reproducibility checklist

For a reproducible handoff:

1. keep the same input history bytes;
2. keep the same public member IDs and observatory ID;
3. build with the same package version;
4. compare every file byte, not just the summary;
5. verify the manifest and all artifact receipts; and
6. retain the source history addresses with the review record.

Repeated builds with equal typed inputs produce equal member, observatory,
verification, metrics, and manifest bytes. A changed source path alone cannot
change the public result because paths never enter the content graph.

## 10. Privacy and licensing

Do not use patient, participant, subject, account, email, or machine names as
member IDs. Do not paste local paths into IDs or free-text fields. Keep source
downloads under their original access and license controls. The public package
contains addresses and bounded operational counters, not source file contents.

## 11. Troubleshooting

### The builder reports a duplicate history address

Two input directories resolve to the same history graph. Check whether the
same package was supplied twice or whether the producing step reused one
history ID and content graph. Use distinct, correctly generated histories.

### The builder reports mismatched member IDs

The number of `--member-id` values does not equal the number of histories.
Remove the explicit IDs to use history IDs, or provide one ID per source in
the same order.

### The package verifies but returns status 2

The package is structurally valid but not promoted. Inspect its state and
member projections. Status 2 is expected for a held or blocked review and is
not evidence of malformed JSON.

### The loader reports non-canonical JSON

A file was reformatted or edited after writing. Rebuild the exact package. Do
not repair it with a text editor because the manifest and content addresses
must agree with the bytes.

### The loader reports an extra file

The package directory is not exact. Move unrelated files outside the package
directory and rerun the build with an explicitly new destination.

### A legacy package is rejected

This boundary does not silently migrate old shapes. Re-run the producing
current-format history step and then observe that package.

## 12. Release handoff

Attach the following to a review handoff:

- exact observatory package;
- exact diff package when comparing with a prior run;
- CLI or HTTP summary;
- upstream history addresses for every member;
- verification result and status;
- license and privacy notes for the source data; and
- domain review notes explaining any non-promoted state.

Do not attach local working paths as public evidence. The addresses in the
package are sufficient to join the artifacts inside the declared boundary.
