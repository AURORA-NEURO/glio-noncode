# Live capability certification

GLIO-NONCODE maintains a 256-row capability catalog spanning sixteen domains.
The catalog state is product evidence, while live certification is executable
repository evidence.  This surface connects those two layers without copying
private data or mutable runtime objects into the public report.

## What is certified

Every row is evaluated independently.  The certificate records the public
catalog identity, domain, layer, order, capability label, kind, release wave,
MVP membership, catalog state, implementation reference receipts, test
reference receipts, ten row checks, a disposition, and a content address.

The ten row checks are:

1. the capability identifier parses to the declared domain and order;
2. the domain identifier has the closed `D01` through `D16` form;
3. the capability order remains inside the sixteen-row domain range;
4. the catalog row is explicitly marked verified;
5. at least one implementation reference is declared;
6. every implementation reference resolves in the current checkout;
7. at least one test reference is declared;
8. every test reference resolves in the current checkout;
9. a release wave is declared;
10. the public projection contains no private field keys.

The global plane adds twelve checks:

| Check | Closed requirement |
|---|---|
| Catalog cardinality | 256 rows |
| Identity uniqueness | no duplicate capability IDs |
| Domain cardinality | 16 domains |
| Domain balance | 16 rows per domain |
| Domain order | orders 1 through 16 in every domain |
| MVP denominator | 64 rows |
| Row acceptance | every row accepted |
| Summary addresses | all domain summaries addressed |
| Implementation addresses | all implementation receipts addressed |
| Test addresses | all test receipts addressed |
| Check addresses | all row checks addressed |
| Public report safety | no private field key enters the report |

The full report therefore contains `256 * 10 + 12 = 2,572` checks.  A report
is accepted only when every row and every global check passes.

## Runtime stages

`run_capability_certification` closes twelve ordered stages:

1. `catalog-loaded`
2. `catalog-addressed`
3. `implementation-references-resolved`
4. `test-references-resolved`
5. `row-certificates-closed`
6. `domain-denominator-closed`
7. `mvp-denominator-closed`
8. `global-checks-closed`
9. `quality-gate-closed`
10. `quality-evidence-closed`
11. `query-surface-closed`
12. `runtime-finalized`

Each stage contains an ordinal, state, predecessor address, output address,
detail, and its own content address.  The final runtime also contains the
complete certification report and an independent eighteen-check quality gate.

## Public projections

The Python surface provides:

- `certify_capability_catalog()` for the complete report;
- `run_capability_certification()` for the ordered runtime;
- `query_capability_certification()` for capability, domain, MVP, state, and
  text filters;
- `capability_certification_domain_matrix()` for dashboard rows;
- `diff_capability_certifications()` for addressed report comparison;
- `replay_capability_certification()` for deterministic replay;
- `run_capability_certification_failure_injections()` for missing evidence
  controls;
- JSON, summary JSON, capability CSV, domain CSV, checks CSV, and Markdown
  projections.

The projections contain reference strings, resolution states, and content
addresses.  They do not serialize imported modules, function objects, raw
source values, or subject-level fields.

## CLI

Run from the repository root:

```powershell
python -m glio_noncode capability-certification
python -m glio_noncode capability-certification-summary
python -m glio_noncode capability-certification-runtime
python -m glio_noncode capability-certification-report --format markdown
python -m glio_noncode capability-certification-csv
python -m glio_noncode capability-certification-domains-csv
python -m glio_noncode capability-certification-checks-csv
python -m glio_noncode capability-certification-query --domain-id D05
python -m glio_noncode capability-certification-query --mvp-only
python -m glio_noncode capability-certification-query --text "chromatin"
python -m glio_noncode capability-certification-replay
python -m glio_noncode capability-certification-failures
python -m glio_noncode capability-certification-bundle --destination capability-certification-bundle
python -m glio_noncode capability-certification-bundle-verify capability-certification-bundle
python -m glio_noncode capability-certification-bundle-query capability-certification-bundle --resource certificates --domain-id D05
python -m glio_noncode capability-certification-bundle-diff capability-certification-bundle-a capability-certification-bundle-b
python -m glio_noncode capability-certification-bundle-observability capability-certification-bundle --format metrics-csv
python -m glio_noncode capability-certification-bundle-schema
python -m glio_noncode capability-certification-bundle-validate capability-certification-bundle/bundle.json
python -m glio_noncode capability-certification-bundle-runtime
python -m glio_noncode capability-certification-bundle-audit capability-certification-bundle
```

All commands write stdout by default and accept `--output` for a selected
file.  A failed certification or quality gate returns exit code `2`; successful
certification returns `0`.

## Portable certification bundle

`capability-certification-bundle` materializes the live 256-row certification
runtime into a deterministic twelve-artifact directory.  The inventory retains
the complete report, summary, certificate/check/domain CSV projections, runtime
and quality receipts, replay and negative-control receipts, the public catalog
projection, Markdown, and addressed observability events and metrics.

`capability-certification-bundle-verify` reopens the directory without relying
on the producing process.  It checks the canonical UTF-8 manifest, closed
schema, bundle address, artifact paths, exact bytes, line counts, content
addresses, regular-file closure, JSON public-boundary keys, and release state.
Unexpected files, tampering, missing artifacts, unsafe paths, symlinks, or
private/attribution fields fail closed.  The bundle carries both the 256/16/64
catalog denominators and the conserved 2,572 certification checks.

The query command supports bounded offline filtering over certificates,
domains, checks, and artifact metadata; `--mvp-only`, domain/capability/state
filters, text search, pagination, JSON, and CSV are deterministic.  Bundle diff
compares addressed capability rows and artifacts.  The staged bundle runtime
records materialization, inventory, manifest, observability, replay, and final
acceptance transitions.

`capability-certification-bundle-audit` is the independent reconciliation
plane. It checks the 12-artifact inventory, report/cardinality invariants,
certificate/domain/check CSV projections, runtime and 18-check quality receipt,
replay and two negative controls, observability metrics, Markdown closure, and
public-key safety. The filesystem verifier calls this audit after exact-byte
verification, so a bundle must be both byte-stable and internally coherent.

## Review and release rules

The certification report is evidence of repository coverage, not a biological
claim.  A resolved reference proves that the named symbol is importable in the
current checkout; it does not prove that a scientific conclusion is valid.
Reviewers should therefore preserve the catalog row, its evidence note, the
reference receipts, the report address, and the commit identifier together.

The following conditions block a clean certification:

- a catalog row loses its implementation or test surface;
- a declared reference no longer resolves;
- a domain loses a row or an order;
- the MVP denominator changes without a catalog change;
- a row is marked verified while its live checks fail;
- a report, summary, certificate, receipt, or check loses its address;
- a private field key enters any public projection.

## Determinism

Catalog order is domain/order order.  Reference receipts are cached within a
run and retain only stable strings and states.  Replaying the same registry
must produce equal catalog and report addresses.  A changed catalog or changed
reference surface must produce a changed certificate or report address.

## Negative controls

The failure controls remove the implementation surface from `GNC-D01-C01` and
the test surface from `GNC-D08-C01`.  Both mutated registries must produce a
review certificate, failed row checks, and a rejected report.  These controls
are part of the executable test surface rather than a documentation-only
assertion.

## Extension contract

When a new capability is added:

1. add the catalog row and preserve the domain/order denominator;
2. declare at least one implementation and test reference;
3. add evidence-backed registry state;
4. run live certification and inspect the row certificate;
5. update the checked-in closure artifact and projections;
6. add positive and missing-surface tests;
7. commit the source, tests, documentation, and closure together.

Do not make a row pass by weakening the global denominator, suppressing a
reference failure, or removing the test surface from the public report.
