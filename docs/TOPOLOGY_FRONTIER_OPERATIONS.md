# Domain 09 topology frontier operations manual

This manual is the day-to-day reference for inspecting, testing, and releasing
the Domain 09 C13-C16 topology frontier surface. The module boundary is kept
explicit so a reviewer can locate the owner of each invariant.

## 1. Module ownership

| Module | Owns |
| --- | --- |
| `topology_frontier_public_data` | fixture, source receipts, records, data audit |
| `topology_frontier_contracts` | four operation contracts and issue vocabulary |
| `topology_frontier_fixture_eval` | adapter calls, state mapping, execution receipts |
| `topology_frontier_replay` | state and address repeatability |
| `topology_frontier_scenario_matrix` | positive/control expectations |
| `topology_frontier_policy` | boundary and interpretation rules |
| `topology_frontier_schema` | serialized operation shapes |
| `topology_frontier_lineage` | source-to-receipt edges |
| `topology_frontier_reconciliation` | expected versus observed state |
| `topology_frontier_metrics` | operation counts and issue totals |
| `topology_frontier_bundle` | composed evidence artifact |
| `topology_frontier_quality_gate` | twelve-check acceptance decision |
| `topology_frontier_runtime` | named pipeline run |
| `topology_frontier_release` | accepted release manifest |
| `topology_frontier_observability` | nine-stage trace and run comparison |
| `topology_frontier_views` | review queue and source matrix |
| `topology_frontier_exports` | JSON, CSV, and Markdown projections |

Do not fix a lineage failure in an export formatter. Do not fix a policy failure
by hiding a row in a view. Correct the invariant at its owning module.

## 2. Start a local inspection

The fastest complete inspection is:

```powershell
python -c "from glio_noncode.topology_frontier_quality_gate import run_topology_frontier_quality_gate; r=run_topology_frontier_quality_gate(); print(r.accepted, r.failed_check_ids)"
python -m glio_noncode topology-frontier-review-view
python -m glio_noncode topology-frontier-trace --run-id local-inspection
```

An accepted result should print an empty failed-check tuple. The review view
should contain twelve controls, and the trace should contain nine stages.

## 3. Source receipt procedure

The default fixture names five public sources. A source receipt is accepted only
when its identifier, locator, release, and purpose are explicit.

Review steps:

1. inspect the source identifier;
2. confirm the locator uses HTTPS;
3. inspect the declared scope;
4. compare the release value with the fixture version note;
5. confirm every fixture record source ID resolves;
6. confirm every lineage source ID resolves;
7. confirm the source matrix contains one row;
8. confirm the source export preserves the identifier.

The fixture does not fetch remote sources during ordinary test execution. A
source refresh must create a versioned fixture change, not a hidden test-time
network dependency.

## 4. C13 operation procedure

### Input review

Check that every C13 positive row has an amplicon, element, gene, score, source
set, and exact context. Check that the threshold and source-count parameter are
present in the record payload.

### Expected controls

The default controls cover:

- weak score and insufficient source count;
- other-cohort context;
- a non-object row.

The weak row should be partial and carry both threshold issues. The other-context
row should be out of domain and retain the adapter context issue. The malformed
row should be invalid with a stable invalid-row issue.

### Review interpretation

Normalized support is a bounded summary of supplied score and source count. It
is not a probability, a causal link, a target-gene proof, or a clinical result.

## 5. C14 operation procedure

### Input review

Check that each row has region ID, prior score, current score, and context. The
sign of each score supplies an A/B descriptive label. The threshold is explicit.

### Expected controls

The default controls cover:

- a stable same-compartment row below the switch threshold;
- a normal-compartment row outside the exact tumor context;
- a malformed row missing the current score.

The stable row is partial even though it is well formed. This is intentional: a
non-switch is still an observed state and should not disappear from review.

### Review interpretation

A signed score change is a descriptive comparison. It is not evidence that a
compartment change caused a gene expression or phenotype change.

## 6. C15 operation procedure

### Input review

Check node ordering, edge count, edge uncertainty, signal, and exact context.
Uncertainty is accumulated across edges and reduces effective signal.

### Expected controls

The default controls cover:

- a weak uncertainty-adjusted signal;
- a node/edge mismatch;
- an other-context path.

The weak and disconnected rows remain partial. The other-context path is out of
domain even if its shape and signal are otherwise valid.

### Review interpretation

A path is a declared chain of observations. It is not proof of enhancer
activity, target-gene linkage, causality, or clinical actionability.

## 7. C16 operation procedure

### Input review

Check path IDs, exact context, bundle ID, and assay IDs. Publication requires at
least one assay receipt. The publisher emits record and bundle content addresses.

### Expected controls

The default controls cover:

- an other-context path;
- a path with no assay IDs;
- an empty path list.

The context row is out of domain. The missing-assay and empty rows are partial.
No control may be promoted to supported because it has a valid-looking path ID.

### Review interpretation

Publication packages evidence already present in the input. It does not add a
mechanistic or clinical interpretation.

## 8. Data audit procedure

Run the audit before reading adapter details. It checks fixture identity,
boundary, source count, HTTPS sources, record count, role balance, operation
coverage, source closure, and aggregate scope.

The audit is accepted only when all nine checks pass. If `no-subject-identifiers`
fails, inspect payload keys recursively. If `source-closure` fails, inspect the
source list and every record source tuple before touching evaluation code.

## 9. Evaluation procedure

The evaluator produces one receipt for every fixture record. It executes each
operation through the existing adapter and maps the adapter result to the gate
state. The summary is intentionally sanitized.

For each receipt inspect:

- record ID;
- operation;
- role;
- expected state;
- observed state;
- primary and secondary counts;
- issue code tuple;
- sanitized summary;
- content address.

The evaluator has seven checks per record and eight global checks. A record-level
failure does not suppress receipts for later records.

## 10. Replay procedure

Replay creates a second evaluation from the selected fixture and compares:

1. fixture ID;
2. fixture version;
3. context;
4. state sequence;
5. receipt-address sequence;
6. evaluation address;
7. acceptance status;
8. record count.

State replay and address replay are separate. A state-preserving serialization
change still requires review because addresses are part of the release contract.

## 11. Scenario procedure

Scenario evaluation checks state, issue floor, and role for each record. Positive
records require supported state. Controls require any non-supported state. The
expected issue tuple is a floor: an adapter may expose an additional issue when
the record has multiple applicable boundary conditions.

When changing a control, update the record expectation and add a test for the
new reason. Do not weaken `control-visibility` to make a test pass.

## 12. Policy procedure

Policy checks the evidence boundary, exact context, source closure, state
vocabulary, operation coverage, and research scope. It also gives each operation
an explicit interpretation rule.

Policy is deliberately separate from evaluation. Evaluation answers how the
adapter behaved. Policy answers whether the resulting shape and scope are
eligible for this public aggregate surface.

## 13. Schema procedure

The schema builder derives four schemas from the operation contract registry. Each
schema includes required payload fields, positive and control states, issue
vocabulary, and a content address.

Use schema checks to catch contract drift before adding a source. A new issue code
must appear in the contract and in a control test. A new required field must
appear in the fixture payload and schema documentation.

## 14. Lineage procedure

Lineage creates one edge for each evaluation receipt. Each edge records source
IDs, operation, output state, output address, and a transformation label.

Lineage closure requires:

- fixture identity matches;
- complete source set matches;
- every receipt has an edge;
- edge operation matches receipt operation;
- edge state matches receipt state;
- edge output address matches receipt address;
- edge source IDs resolve;
- edge address is present.

## 15. Reconciliation procedure

Reconciliation joins fixture records to receipts by record ID. It reports state
match, issue-floor match, source IDs, and three global closure checks.

Use reconciliation when a scenario fails. It gives the smallest useful view of
expected and observed behavior without requiring a reviewer to inspect a whole
bundle.

## 16. Bundle procedure

The bundle composes data audit, evaluation, replay, scenarios, policy, lineage,
reconciliation, and metrics. Its address is computed from all nested artifacts.

The bundle accepted property is the conjunction of upstream acceptance values.
It must never be manually set to true. If a nested artifact changes, the bundle
address changes.

## 17. Quality gate procedure

Run the quality gate after focused tests. Use its twelve check identifiers as the
single release decision. A passing evaluation alone is insufficient because
policy, schema, lineage, and reconciliation may still fail.

The gate should be rerun after any fixture, contract, adapter, or serializer
change. The default run is inexpensive enough for local and CI execution.

## 18. Runtime procedure

The runtime accepts a named run ID and an optional fixture. It runs the quality
gate and returns accepted or rejected status. The runtime content address covers
the run ID, fixture, status, and quality report.

Use distinct run IDs when comparing executions. Run IDs are labels for the
execution record; they do not participate in nested fixture receipt addresses.

## 19. Trace procedure

The trace has nine stage receipts and nine ordered events. Each stage points to
the address of its artifact and reports a record count.

Trace review should confirm:

- sequence numbers are one through nine;
- stage order is stable;
- failed stages are marked as failed;
- evaluation and bundle events carry record IDs;
- every stage address is present.

## 20. Run comparison procedure

Run comparison reports status change, quality change, review-count delta, state
changes, and bundle-address change. Two runs with different run IDs may still be
equivalent if their state and quality outputs agree.

If a state change appears, compare the record ID first, then expected state,
issue codes, source IDs, and nested content addresses.

## 21. Review view procedure

The view includes four operation summaries, a twelve-row review queue, and five
source-matrix rows. Supported records are omitted from the default review queue.

Priority is four for out-of-domain or invalid, two for partial, and zero for
supported. Actions describe the next review focus. A view is a projection and
must not recalculate adapter state.

## 22. Export procedure

Use JSON for canonical machine inspection. Use receipt CSV for all sixteen
receipts. Use review CSV and Markdown for the twelve controls. Use metrics CSV
for four operation rows.

Before export:

1. run the quality gate;
2. build the view from the same evaluation;
3. export receipts or review rows;
4. confirm row counts;
5. compute an export receipt;
6. retain the export beside the release manifest.

## 23. Failure matrix

| Failure | First owner | Next inspection |
| --- | --- | --- |
| source count | public data | source receipts |
| context mismatch | public data/evaluator | row context and wrapper |
| unexpected supported control | scenario | control payload and adapter threshold |
| invalid positive | evaluator | required input fields |
| state replay | replay | adapter state sequence |
| address replay | replay/serialization | normalized nested values |
| schema issue | contracts/schema | vocabulary and required fields |
| lineage issue | lineage | source and receipt join |
| reconciliation issue | reconciliation | expected versus observed row |
| release rejection | quality gate | first failed check |
| export count mismatch | views/exports | queue or operation selection |

## 24. Change protocol

For any Domain 09 change:

1. identify the owning module;
2. update the contract if vocabulary changes;
3. add a positive or control fixture row;
4. update expected state and issue floor;
5. update schema and policy tests;
6. update lineage and reconciliation assertions;
7. run focused tests;
8. run targeted lint with the project formatter;
9. exercise affected CLI commands;
10. run the full suite;
11. inspect the staged diff;
12. scan staged additions for prohibited repository metadata markers;
13. commit a coherent build;
14. push the main and tracked build refs;
15. inspect all relevant Actions jobs.

## 25. Completion checklist

- [ ] four operation contracts are present;
- [ ] four positive rows are supported;
- [ ] twelve controls are non-supported;
- [ ] five sources close;
- [ ] exact context is preserved;
- [ ] malformed rows remain invalid;
- [ ] other-context rows remain out of domain;
- [ ] replay passes;
- [ ] scenario checks pass;
- [ ] policy checks pass;
- [ ] schema checks pass;
- [ ] lineage closes;
- [ ] reconciliation closes;
- [ ] bundle is accepted;
- [ ] quality gate has twelve passing checks;
- [ ] release manifest builds;
- [ ] trace has nine stages;
- [ ] view has twelve review rows;
- [ ] exports have expected row counts;
- [ ] focused tests pass;
- [ ] full suite passes;
- [ ] staged additions pass the repository metadata scan;
- [ ] main ref and build ref point to the release commit;
- [ ] both Actions matrix runs are green.

## 26. Final operating rule

Every released topology result must identify its operation, exact context,
public source boundary, observed state, issue codes, and release checks. If a
reviewer cannot answer those questions from the packet, keep the result in the
diagnostic surface and return to the owning module.
