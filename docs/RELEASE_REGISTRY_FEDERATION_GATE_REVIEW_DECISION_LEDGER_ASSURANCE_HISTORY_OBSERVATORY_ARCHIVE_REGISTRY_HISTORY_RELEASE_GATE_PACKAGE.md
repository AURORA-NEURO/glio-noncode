# Registry history release-gate package

The release-gate package is the durable handoff format for one evaluated
registry history. It contains exactly three canonical UTF-8 JSON files:

| File | Contents |
| --- | --- |
| `manifest.json` | package version, boundary, linked gate/policy addresses, and byte receipts |
| `policy.json` | the independent public release policy projection |
| `gate.json` | the complete public release decision and eleven checks |

The package does not contain the source history directory, filesystem paths,
timestamps, ownership metadata, attribution metadata, or language metadata.
The gate and policy are reloaded through their typed contracts; the manifest
and both artifact receipts must reproduce exactly before a load succeeds.

## Python

```python
from glio_noncode import (
    evaluate_assurance_history_observatory_archive_registry_history_release_gate_from_directory,
    load_assurance_history_observatory_archive_registry_history_release_gate_package,
    write_assurance_history_observatory_archive_registry_history_release_gate_package,
)

gate = evaluate_assurance_history_observatory_archive_registry_history_release_gate_from_directory(
    "./review-output/history"
)
write_assurance_history_observatory_archive_registry_history_release_gate_package(
    gate, "./review-output/release-gate"
)
replayed = load_assurance_history_observatory_archive_registry_history_release_gate_package(
    "./review-output/release-gate"
)
print(replayed.state, replayed.content_address)
```

## CLI

```powershell
python -m glio_noncode <history-command>-release-gate-package `
  --input .\review-output\history `
  --destination .\review-output\release-gate `
  --format manifest

python -m glio_noncode <history-command>-release-gate-package-verify `
  --input .\review-output\release-gate
python -m glio_noncode <history-command>-release-gate-package-manifest `
  --input .\review-output\release-gate
python -m glio_noncode <history-command>-release-gate-package-schema
python -m glio_noncode <history-command>-release-gate-package-manifest-schema
python -m glio_noncode <history-command>-release-gate-package-capabilities
```

Package creation reloads the output before reporting success. Existing
destinations require `--allow-existing` and must already be an exact compatible
three-file package. Verification returns exit code `0` for a ready gate and
`2` for a valid held or blocked decision.

## HTTP

```text
GET /v1/.../history/release-gate/package?input=./review-output/history&destination=./review-output/release-gate&format=manifest
GET /v1/.../history/release-gate/package/verify?input=./review-output/release-gate
GET /v1/.../history/release-gate/package/manifest?input=./review-output/release-gate
GET /v1/.../history/release-gate/package/schema
GET /v1/.../history/release-gate/package/manifest-schema
GET /v1/.../history/release-gate/package/capabilities
```

## Downloaded-data demo

```powershell
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_demo.py `
  --input .\review-output\history `
  --destination .\review-output\release-gate `
  --format manifest
```

The package is deterministic for the same downloaded history and policy, and
its three-file member set can be copied as a self-contained release decision.
