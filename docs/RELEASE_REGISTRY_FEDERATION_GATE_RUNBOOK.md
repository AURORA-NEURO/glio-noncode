# Release-registry federation gate runbook

This runbook demonstrates the release-registry federation gate against
persisted downloaded-data packages.

The workflow is intentionally local and portable.

It reads release-registry directories.

It never clones a repository.

It never treats an old repository as a framework.

It never embeds a local source path in a public artifact.

It never requires private metadata.

It leaves the original downloaded directories untouched.

## 1. What the gate consumes

Each input directory must be a persisted release-registry package.

The release-registry package has an exact file set.

The source package is independently verified before federation.

The source package's registry entries retain release provenance.

The federation command sorts input members deterministically.

The federation command rejects duplicate registry identities.

The federation command records member and package conservation.

The federation command records policy, verification, and runtime receipts.

The gate consumes the persisted federation package.

The gate does not infer a registry from arbitrary JSON.

The gate does not accept a directory with an extra artifact.

The gate does not follow symlinked artifacts.

The gate does not silently repair malformed documents.

## 2. Prepare a downloaded-data root

A downloaded-data root may contain multiple provider or cohort directories.

Unrelated notes and archive metadata may remain beside the packages.

The discovery helper admits only exact registry package directories.

Use shallow discovery when packages are direct children of the root.

Use recursive discovery when a download groups packages under subdirectories.

The discovery result is sorted by stable path ordering.

The discovered paths are used only as input handles.

The paths are not serialized into the gate.

Inspect candidates before building the federation when reviewing a new source.

```text
python examples/release_registry_federation_gate_demo.py \
  --root ./downloaded-release-registries \
  --recursive \
  --output ./out/release-registry-gate \
  --format summary
```

The example exits with status `0` for promotion.

The example exits with status `2` for hold or block.

The JSON report still contains the decision when the status is `2`.

## 3. Curated explicit inputs

Explicit inputs are useful when discovery would admit too many packages.

Repeat `--input` once for each persisted registry directory.

The explicit sequence is sorted by the federation builder.

Duplicate paths are rejected before source loading.

```text
python examples/release_registry_federation_gate_demo.py \
  --input ./downloads/institution-a \
  --input ./downloads/institution-b \
  --output ./out/release-registry-gate \
  --format markdown \
  --report ./out/release-registry-gate-report.md
```

The report is separate from the exact gate package.

The report may be attached to a review ticket.

The package remains machine-readable.

## 4. Direct package commands

The full package command family is available through the module CLI.

The command name is deliberately long so it is discoverable beside the
release-registry federation command.

```text
FEDERATION_GATE=module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry-federation-gate
```

Build a federation first.

```text
python -m glio_noncode <release-registry-federation> \
  --input ./downloads/registry-a \
  --input ./downloads/registry-b \
  --destination ./out/federation \
  --format summary
```

Build an independent gate from that federation.

```text
python -m glio_noncode <release-registry-federation>-gate \
  --input ./out/federation \
  --destination ./out/federation-gate \
  --format summary
```

The gate build replays the source verification.

The gate build replays the source policy evaluation.

The gate build replays the source runtime closure.

The gate build computes new findings.

The gate build computes new release checks.

The source gate decision is not copied as an authority.

## 5. Assurance findings

The independent assurance contains ten findings.

`source-bundle-verified` checks the source closure.

`federation-address` recomputes the federation address.

`verification-recomputed` checks the structural receipt.

`policy-recomputed` checks the policy receipt.

`runtime-recomputed` checks the runtime receipt.

`runtime-accepted` checks runtime acceptance.

`aggregate-counts` checks member, package, and state totals.

`state-coherent` checks state and readiness relationships.

`public-boundary` checks path-free public projection closure.

`source-release-ready` checks promotion readiness.

The first nine findings are required blocker checks.

The readiness finding is an optional warning check.

An assurance blocker produces `block`.

An assurance warning produces `hold`.

No failed findings produces `promote`.

Every finding has an ordinal.

Every finding has a stable finding identifier.

Every finding has a plane.

Every finding has a severity.

Every finding has a boolean outcome.

Every finding has bounded detail.

Every finding has an evidence address.

Every finding has a content address.

The finding content address excludes its own address field.

## 6. Release-gate checks

The release gate contains eight checks.

`assurance-accepted` requires no blocker findings.

`assurance-no-blockers` conserves the blocker count.

`source-runtime-accepted` requires source runtime acceptance.

`source-state-allowed` prevents blocked promotion.

`aggregate-counts-conserved` checks source count conservation.

`public-boundary-closed` checks the source public boundary.

`source-release-ready` preserves the readiness warning.

`assurance-warning-free` checks optional warnings.

Required failures are counted separately from optional failures.

Required failures produce `block`.

Optional failures produce `hold`.

A clean check set produces `promote`.

The decision equals the public state.

Acceptance means no required failure.

Release readiness means promotion.

The gate content address binds all public summary fields.

## 7. Decision table

| Source condition | Assurance state | Gate state | Accepted | Release-ready |
| --- | --- | --- | --- | --- |
| all findings pass | promote | promote | yes | yes |
| warning only | hold | hold | yes | no |
| blocker present | block | block | no | no |
| explicit empty source | hold | hold | yes | no |

An accepted hold is reviewable but not promotable.

A block is fail-closed.

An empty source remains explicit.

An empty source requires source policy permission.

The table is a contract, not a scientific interpretation.

## 8. Exact portable package

The gate package contains exactly three files.

```text
manifest.json
assurance.json
gate.json
```

The files are UTF-8.

The files use canonical JSON.

The manifest lists the exact file set.

The manifest records the federation address.

The manifest records the runtime address.

The manifest records the assurance address.

The manifest records the gate address.

The manifest records the byte length of each data document.

The manifest records a byte address for each data document.

The manifest has its own content address.

The assurance document has its own content address.

The gate document has its own content address.

Writes use a temporary sibling directory.

The completed directory is installed atomically.

Non-empty destinations require explicit overwrite.

The output directory can be copied between machines.

## 9. Verification commands

Verify a persisted gate package.

```text
python -m glio_noncode <FEDERATION_GATE>-verify \
  --input ./out/federation-gate
```

The verifier reloads canonical documents.

The verifier checks the exact file set.

The verifier checks regular-file status.

The verifier checks every nested content address.

The verifier checks the assurance-to-gate link.

The verifier checks source linkage.

The verifier checks manifest linkage.

The verifier checks byte receipts.

The verifier rejects an extra file.

The verifier rejects a missing file.

The verifier rejects changed bytes.

The verifier rejects noncanonical JSON.

The verifier rejects a symlink artifact.

The verifier returns `0` only for a release-ready gate.

The verifier returns `2` for a valid hold or block decision.

## 10. Query commands

Query the complete summary.

```text
python -m glio_noncode <FEDERATION_GATE>-query \
  --input ./out/federation-gate \
  --resource summary
```

Query all findings.

```text
python -m glio_noncode <FEDERATION_GATE>-query \
  --input ./out/federation-gate \
  --resource findings \
  --limit 64
```

Query only blockers.

```text
python -m glio_noncode <FEDERATION_GATE>-query \
  --input ./out/federation-gate \
  --resource blockers
```

Query only warnings.

```text
python -m glio_noncode <FEDERATION_GATE>-query \
  --input ./out/federation-gate \
  --resource warnings
```

Query failed checks.

```text
python -m glio_noncode <FEDERATION_GATE>-query \
  --input ./out/federation-gate \
  --resource failed-checks
```

Filter by plane.

```text
python -m glio_noncode <FEDERATION_GATE>-query \
  --input ./out/federation-gate \
  --resource findings \
  --plane runtime
```

Filter by severity.

```text
python -m glio_noncode <FEDERATION_GATE>-query \
  --input ./out/federation-gate \
  --resource findings \
  --severity warning
```

Filter by outcome.

```text
python -m glio_noncode <FEDERATION_GATE>-query \
  --input ./out/federation-gate \
  --resource findings \
  --passed
```

Filter by text.

```text
python -m glio_noncode <FEDERATION_GATE>-query \
  --input ./out/federation-gate \
  --resource findings \
  --text readiness
```

Use offset and limit for bounded pagination.

```text
python -m glio_noncode <FEDERATION_GATE>-query \
  --input ./out/federation-gate \
  --resource checks \
  --offset 0 \
  --limit 8
```

Every result carries the gate address.

Every result carries the assurance address.

Every result carries total and returned counts.

Every result carries a deterministic query address.

## 11. Export formats

JSON is the canonical machine interchange format.

CSV is useful for spreadsheet review.

Markdown is useful for a human review packet.

Summary mode avoids nested finding and check rows.

CSV output uses a stable header.

Markdown output includes a summary section.

Markdown output includes an items table when rows exist.

Empty queries still produce a header.

Exporters verify typed inputs before rendering.

Exporters never add a local path field.

## 12. HTTP routes

The gate is exposed below the release-registry federation route.

```text
/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate
```

The root route builds a gate from a persisted federation.

The `/assurance` route returns the assurance projection.

The `/release` route returns the release-gate projection.

The `/verify` route reloads a persisted gate package.

The `/query` route loads and queries a persisted gate package.

The `/schema` route returns the bundle schema.

The `/assurance-schema` route returns the assurance schema.

The `/finding-schema` route returns the finding schema.

The `/gate-schema` route returns the release-gate schema.

The `/gate-check-schema` route returns the check schema.

The `/query-schema` route returns the query schema.

The `/manifest-schema` route returns the manifest schema.

The `/capabilities` route returns bounded capability metadata.

CSV responses use `text/csv`.

Markdown responses use `text/markdown`.

Invalid input returns a client error.

An unready but valid decision returns HTTP 422.

## 13. Failure response guide

If discovery finds no package, inspect the exact file set.

If a source package fails, run its registry verifier first.

If federation rejects duplicate identities, choose one source.

If the gate blocks, query `blockers`.

If the gate holds, query `warnings`.

If the manifest fails, compare the recorded byte receipts.

If canonical JSON fails, rewrite through the package writer.

If an extra file exists, remove it from the output package after review.

If a source path appears in output, stop and treat it as a defect.

If a private field appears in output, stop and treat it as a defect.

If a report is stale, rebuild from the persisted source package.

If a destination is non-empty, choose a new destination or explicit overwrite.

If HTTP returns 400, verify the input query parameter.

If HTTP returns 422, inspect the returned decision body.

If HTTP returns 500, preserve the response and investigate the server boundary.

## 14. CI usage

Run the focused test module in CI.

```text
python -m unittest tests.test_assurance_history_series_release_registry_federation_gate -v
```

Run the source linter.

```text
ruff check src/glio_noncode/assurance_history_series_release_registry_federation_gate.py
```

Compile the source and package initializer.

```text
python -m py_compile src/glio_noncode/assurance_history_series_release_registry_federation_gate.py src/glio_noncode/__init__.py
```

Emit each contract command.

```text
python -m glio_noncode <FEDERATION_GATE>-schema
python -m glio_noncode <FEDERATION_GATE>-assurance-schema
python -m glio_noncode <FEDERATION_GATE>-finding-schema
python -m glio_noncode <FEDERATION_GATE>-gate-schema
python -m glio_noncode <FEDERATION_GATE>-gate-check-schema
python -m glio_noncode <FEDERATION_GATE>-query-schema
python -m glio_noncode <FEDERATION_GATE>-manifest-schema
python -m glio_noncode <FEDERATION_GATE>-capabilities
```

The Actions workflow runs the focused tests.

The Actions workflow emits schema artifacts.

The Actions workflow can preserve a gate package as an artifact.

The package can be verified on a separate runner.

## 15. Privacy and provenance review

Public JSON contains addressed release data only.

Public JSON does not contain a local source path.

Public JSON does not contain a user field.

Public JSON does not contain an author field.

Public JSON does not contain a model field.

Public JSON does not contain a language field.

Public JSON does not contain an agent field.

Public JSON does not contain private metadata.

Evidence addresses point to public typed receipts.

Source directories remain outside the output package.

The runbook does not require clinical records.

Downloaded data should still be reviewed for license and privacy constraints.

The gate expresses transport and release integrity.

The gate does not claim clinical efficacy.

The gate does not replace domain review.

## 16. Completion checklist

- [ ] source registry packages load successfully;
- [ ] source federation verification is accepted;
- [ ] source federation policy is understood;
- [ ] the gate has been built from the persisted federation;
- [ ] assurance findings have been queried;
- [ ] failed findings have been reviewed;
- [ ] gate checks have been queried;
- [ ] blocker and warning counts are understood;
- [ ] the exact three-file gate package is present;
- [ ] the manifest byte receipts are present;
- [ ] the persisted gate reloads successfully;
- [ ] the public projection contains no private fields;
- [ ] the output decision is recorded;
- [ ] the decision status is appropriate for promotion;
- [ ] the report and package are retained together;
- [ ] any downloaded-data license restrictions are recorded;
- [ ] the review owner has accepted the result.

The package is ready for the next release-review boundary only when the
checklist and the returned decision agree.
