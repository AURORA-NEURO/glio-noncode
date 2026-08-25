# Deployment frontier offline operations

The D16 deployment frontier is the public aggregate handoff for C13 privacy
and security policy, C14 local deployment bundles, C15 federated execution,
and C16 release/rollback control. The handoff is designed for review on a
machine that does not run the producer service.

## What is materialized

The bundle contains 51 exact-byte artifacts:

- one public fixture with five HTTPS source receipts and sixteen deployment
  records;
- thirty-seven runtime planes covering policy, bundle readiness, federated
  execution, release gates, lineage, quality, integrity, compliance,
  diagnostics, recovery, operational accounting, and observability;
- one normalized runtime trace with 38 ordered stages;
- eight address-only indexes for stages, denominators, operations, public
  keys, fixture identity, issue categories, and observed states;
- three review exports, a data dictionary, and a capability map.

The fixture is deliberately balanced: four positive records and twelve
controls, with one positive and three controls for each operation family. The
evaluation plane contains 16 execution receipts and 80 checks. The controls
retain explicit failure reasons, including invalid artifact digests, online
mode, privacy-budget overrun, unavailable sites, context mismatch, failed
integrity gates, and invalid rollback state.

## Create and verify

```text
glio-noncode deployment-frontier-offline-bundle \
  --destination deployment-frontier-bundle \
  --output deployment-frontier-bundle.json

glio-noncode deployment-frontier-offline-bundle-verify \
  deployment-frontier-bundle \
  --output deployment-frontier-verification.json
```

The writer creates only the manifest-listed relative paths. Verification
recomputes every payload address from the bytes on disk, checks byte and line
counts, rejects extra files and symlinks, and reconstructs the manifest root
address. A modified CSV, JSON plane, manifest, or hidden file makes the
verification result non-accepted.

## Query without the producer

```text
glio-noncode deployment-frontier-offline-bundle-query \
  deployment-frontier-bundle \
  --resource records \
  --operation privacy_security_policy \
  --format json

glio-noncode deployment-frontier-offline-bundle-query \
  deployment-frontier-bundle \
  --resource records \
  --role control \
  --format csv \
  --output deployment-controls.csv
```

Supported resource projections include artifacts, components, records,
executions, evaluation checks, sources, issues, states, runtime stages,
operations, denominators, public keys, and capabilities. All pages are
bounded by the 500-row maximum. Filters are exact for structured fields and
case-insensitive substring matches for `--text`.

## Independent assurance commands

```text
glio-noncode deployment-frontier-offline-bundle-audit deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-boundary deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-indexes deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-reconciliation deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-summary deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-certification deployment-frontier-bundle
```

The audits have separate responsibilities:

1. The bundle audit validates fixture-to-execution identity, denominator
   conservation, stage order, source joins, component addresses, and the
   stored public-key index.
2. The boundary audit inventories every JSON key and checks path safety,
   exact-byte address prefixes, identity uniqueness, and the absence of
   prohibited attribution or direct-identifier keys.
3. The index audit validates address-only lookup structures without copying
   payload bodies into the index.
4. Reconciliation closes the joins among records, executions, sources,
   stages, operation families, and the normalized runtime root.
5. The summary audit checks compact counters and operation-level review
   summaries.
6. Certification evaluates seven domains with 37 independent checks and
   reports failed check identifiers for bounded remediation.

## Runtime rehearsal and replay

```text
glio-noncode deployment-frontier-offline-bundle-runtime \
  --output deployment-frontier-offline-runtime.json
```

The offline runtime has ten stages: materialization, artifact closure,
cross-artifact audit, public-boundary closure, index closure, denominator
reconciliation, summary closure, observability closure, deterministic replay,
and finalization. The embedded replay rebuilds the normalized handoff twice
with the same run identity and requires all three root addresses to match.

The source deployment runtime itself has 38 ordered stages. The portable
trace retains their IDs, sequence numbers, completion states, output
addresses, and detail text while setting wall-clock duration to zero in the
transport projection. This preserves operational meaning and removes host
timing from the reproducibility contract.

## HTTP read surface

When the local API is running, the same projections are available at:

```text
/v1/deployment-frontier/bundle
/v1/deployment-frontier/bundle/schema
/v1/deployment-frontier/bundle/query?resource=records&operation=privacy_security_policy
/v1/deployment-frontier/bundle/audit
/v1/deployment-frontier/bundle/observability
/v1/deployment-frontier/bundle/runtime
/v1/deployment-frontier/bundle/indexes
/v1/deployment-frontier/bundle/boundary
/v1/deployment-frontier/bundle/reconciliation
/v1/deployment-frontier/bundle/summary
/v1/deployment-frontier/bundle/certification
```

The service builds a read-only public projection. It does not accept arbitrary
paths, does not expose payloads from outside the bundle inventory, and does
not add producer, model, language, or attribution metadata to responses.

## Safety and non-claims

The D16 fixture is an engineering and governance harness. It demonstrates
that the declared control paths, gates, receipts, and offline closure rules
execute as specified. It does not make a clinical, scientific, diagnostic,
or deployment-safety claim about any patient or site. Source receipts point to
public portals and the fixture carries only aggregate synthetic operational
measurements.

## Suggested review order

Reviewers should start with `bundle.json`, then run manifest validation and
filesystem verification. Next inspect the denominator and public-key indexes,
then query controls by operation, and finally read the certification report.
This order moves from identity to closure to domain-specific review while
keeping the raw payload inventory immutable.
