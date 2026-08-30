# Longitudinal query-snapshot comparisons

Two filtered runtime-query snapshot handoffs can now be compared as a
value-free longitudinal review. The comparison does not reopen the downloaded
archive. It loads the persisted five-file handoffs, requires their query shapes
to match, and pairs rows by the stable public key `(resource, identity, field)`.

## Result contract

The comparison is an exact four-file handoff:

- `diff.json` retains both handoff identities, source diff identities, query and
  audit addresses, query shapes, state transitions, and acceptance receipts.
- `items.json` records every paired row as `added`, `removed`, `changed`, or
  `unchanged`, along with both row receipts and changed-field evidence.
- `summary.json` folds the counts, endpoint metadata, direction, and query-shape
  match into one compact review projection.
- `manifest.json` records the exact file set and content addresses for the two
  derived artifacts.

The comparison direction is `improved` when the right handoff becomes accepted,
`regressed` when it stops being accepted, `mixed` when accepted state is stable
but rows changed, and `unchanged` when both acceptance and rows are stable. A
different query shape is rejected before a comparison is built because a change
in filters is not a data revision.

## Python

```python
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot as snapshot_model,
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff as comparison_model,
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_audit as audit_model,
)

comparison = comparison_model.run_diff(
    "artifacts/review-before",
    "artifacts/review-after",
    diff_id="review-before-to-after",
    destination="artifacts/review-before-to-after",
)
audit = audit_model.audit_diff(comparison)
assert comparison.query_shape_match and audit.accepted
reloaded = comparison_model.load_diff("artifacts/review-before-to-after")
assert reloaded.content_address == comparison.content_address
```

The comparison audit has 15 fixed checks covering endpoint linkage, query-shape
equality, row conservation, identity uniqueness, canonical order, change and
field-delta replay, direction/state-transition replay, artifact addresses,
mapping round trips, and the public boundary.

## CLI and HTTP

```powershell
glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff `
  artifacts/review-before artifacts/review-after `
  --diff-id review-before-to-after `
  --destination artifacts/review-before-to-after `
  --format markdown

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-audit `
  artifacts/review-before-to-after --format summary
```

The HTTP routes are rooted at:

```text
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/audit
```

Schema and capability routes cover the item, items, manifest, summary,
comparison, audit-check, audit, and audit-capability contracts. Persisted
comparison directories reject extra or missing files, symlinks, non-canonical
JSON, stale nested addresses, and tampered artifacts.

The module reports structural review facts from downloaded data. It does not
make a clinical, scientific, or product-validity claim.
