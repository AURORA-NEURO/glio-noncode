# Evidence release frontier runbook

## Prepare

1. Check out the public repository and install no external runtime dependency.
2. Run `python -m compileall -q src tests`.
3. Run the data audit and inspect its source count, record count, role balance,
   HTTPS receipt, and sensitive-marker checks.
4. Load `examples/evidence-release-public-aggregate.json` through the fixture
   loader. The loader recomputes the expected fixture identity and address.

## Evaluate

Run the evaluator and confirm:

- four positive rows are free of expected issues;
- twelve control rows retain their expected issue code;
- four operations are represented equally;
- all execution addresses use the canonical SHA-256 form;
- the positive dossier has `signature_verified: true`;
- no output projection contains signing material.

## Inspect transitions

For C13, inspect the score, threshold, reviewer count, source count, prior tier,
proposed tier, and decision-basis address. A score below threshold is review, not a
negative claim. One reviewer is review. A foreign context is blocked.

For C14, inspect the target closure and chain address. A missing target remains
review. A self-link or cycle is blocked. The old record stays in the chain so the
history remains reproducible.

For C15, inspect all three required section kinds. Empty sections, invalid item
addresses, or duplicate section IDs remain review. The bundle address covers the
manifest and section projections.

For C16, inspect audience, expiry, key ID, payload address, signature, and
verification state. Recompute the signature using the injected key material in an
isolated test. Publish only the public key ID and receipt; never publish the key.

## Release gates

Run the complete pipeline and review its ordered stages. The expected stage count is
53. A successful release requires data, source registry, evaluation, quality,
lineage, reconciliation, replay, reproducibility, release, artifacts, review,
integrity, depth, thresholds, scenarios, controls, validation, evidence, assurance,
claim boundary, failure injection, recovery, performance, operational, compliance,
diagnostics, partitions, resource accounting, provenance, access, freshness,
compatibility, release checks, runbook, run manifest, audit log, transcript, summary,
data dictionary, package, bundle, and trace closure.

An operator should stop if any gate is false. The generated recovery receipt maps the
row to one of: correct context, obtain evidence or review, repair schema, retain
history, store bundle, or verify the receipt. It does not provide an automatic path
from blocked to signed.

## Review handoff

The review CSV is the smallest row-level handoff. The JSON runtime is the complete
trace. The data dictionary defines the stable fields. The release note records the
boundary. Store all three with the fixture address and the run ID when a release is
reviewed.

## Rehearsal commands

```powershell
python -m glio_noncode evidence-release-frontier-data-audit
python -m glio_noncode evidence-release-frontier-evaluate
python -m glio_noncode evidence-release-frontier-depth
python -m glio_noncode evidence-release-frontier-quality
python -m glio_noncode evidence-release-frontier-pipeline
python -m glio_noncode evidence-release-frontier-failure-injection
python -m unittest tests.test_evidence_release_frontier tests.test_evidence_release_frontier_extensions tests.test_evidence_release_frontier_assurance tests.test_evidence_release_frontier_cli
```

The commands are deterministic over the checked-in fixture. Network retrieval is
not required for the rehearsal. The HTTPS links in the source receipts identify
public portals and scopes; they do not imply that the runtime copied or cached
private material.

When a run is handed off, attach the JSON runtime, the review CSV, the fixture
address, and the checklist. That set is sufficient to reconstruct the operational
decision without relying on an unstated local environment.
