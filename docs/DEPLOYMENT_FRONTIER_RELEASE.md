# Deployment frontier release procedure

## Local command sequence

```powershell
python -m glio_noncode deployment-frontier-data-audit --output deployment-data.json
python -m glio_noncode deployment-frontier-evaluate --output deployment-evaluation.json
python -m glio_noncode deployment-frontier-depth --output deployment-depth.json
python -m glio_noncode deployment-frontier-thresholds --output deployment-thresholds.json
python -m glio_noncode deployment-frontier-validation-matrix --output deployment-validation.json
python -m glio_noncode deployment-frontier-pipeline --output deployment-runtime.json
python -m glio_noncode deployment-frontier-review-csv --output deployment-review.csv
```

The combined runtime is the release-facing command. It evaluates the public
data boundary, executes all 16 rows, checks 80 row assertions, builds 38
ordered stages, replays the evaluation, runs twelve failure probes, and closes
the package and bundle receipts.

## Required release conditions

- five HTTPS public source receipts are present;
- 16 records are present with four operations, four positives, and twelve controls;
- all 80 row checks pass;
- all four adapters and 14 schema fields are present;
- expected and observed states reconcile with no mismatch;
- replay addresses are identical;
- the policy, depth, integrity, compliance, and compatibility reports pass;
- the 12-control failure injection rehearsal remains negative;
- all public access surfaces remain aggregate-only;
- the package, release manifest, artifact inventory, and bundle are complete;
- the audit log and transcript retain contiguous ordering.

## Release artifacts

The runtime report contains:

- source and data audit;
- typed operation evaluation;
- metrics and policy manifest;
- source-to-execution lineage;
- reconciliation and quality gate;
- replay and release manifest;
- artifact inventory and stable review view;
- review queue, SLA, and handoff;
- integrity, scenario, validation, and evidence depth;
- operational, performance, assurance, and compliance reports;
- failure injection, diagnostics, plan, thresholds, and compatibility;
- runbook, freshness, audit log, transcript, summary, package, bundle, and trace.

Each nested object is serializable and content addressed. The report may be
written to a local output path or consumed by a CI job. No external network
request is required to execute the fixture.

## Rollback procedure

If a release gate fails, keep the failed release manifest and open review
queue. Use the rollback plan to freeze new admissions, retain current
receipts, restore the prior package address, and replay the quality gate.
Rollback is a state transition with evidence; it is not a destructive delete.

## Scope boundary

This procedure verifies software contracts, deterministic replay, public
provenance, and review routing. It does not verify clinical safety, institution
authorization, biological effect, or transportability. Those remain external
release gates.
