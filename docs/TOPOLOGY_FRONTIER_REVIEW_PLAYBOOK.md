# Domain 09 topology frontier review playbook

This playbook turns the Domain 09 evidence gate into a repeatable review
practice. It is organized around observable artifacts and small diagnostic
decisions. A reviewer can use it during a local inspection, a pull request, a
release review, or an Actions failure.

## 1. Packet inventory

Collect these artifacts before reviewing a release:

| Artifact | Expected default shape |
| --- | --- |
| data audit | 9 checks |
| evaluation | 16 receipts and 120 checks |
| replay | 8 checks |
| scenarios | 16 rows and 48 checks |
| policy | 8 rules and 14 checks |
| schemas | 4 schemas and 20 checks |
| lineage | 16 edges and 5 source IDs |
| reconciliation | 16 items and 3 global checks |
| metrics | 4 operation rows |
| quality | 12 checks |
| runtime | named result |
| trace | 9 stages and 9 events |
| review view | 12 review rows and 5 source rows |
| release | accepted manifest |

If an artifact is missing, stop release review and return to the pipeline stage
that should have produced it. Do not reconstruct a missing artifact by hand.

## 2. Identity review

Check identity in this order:

1. fixture ID;
2. fixture version;
3. run ID;
4. exact context key;
5. evidence boundary;
6. bundle address;
7. record address;
8. release address.

The fixture ID and version identify the input contract. The run ID identifies an
execution. The bundle and record addresses identify content. Do not substitute
one class of identity for another.

## 3. Context review

The default context has six ordered positions:

| Position | Value |
| --- | --- |
| genome | GRCh38 |
| disease | glioma |
| cohort | adult |
| state | stem_like |
| compartment | tumor |
| sex | unknown |

Review every mismatch as a control. A row with valid topology values but an
incorrect cohort, compartment, or state is still out of domain for this run.
The gate does not transport a result from a nearby context because the values
look biologically similar.

## 4. Source review worksheet

For each source row, record the following:

- source identifier;
- title;
- locator;
- source kind;
- release label;
- declared scope;
- source content address;
- record IDs that refer to it;
- operations that refer to it;
- positive/control split.

The source matrix is a projection of fixture references. It does not add a new
source relationship. If the matrix differs from the fixture, inspect fixture
record source IDs before changing the view.

## 5. C13 review worksheet

### Required fields

The C13 row should show:

- amplicon ID;
- element ID;
- gene ID;
- contact score;
- source IDs;
- exact context;
- minimum contact score;
- minimum source count.

### Positive decision

The positive row is supported when score and source count clear their thresholds
and exact context matches. Check the normalized support value and the source set.

### Weak decision

The weak row is partial. Check that its issue tuple contains a weak-score issue.
When its source count is also below the threshold, both issues should remain
visible. An issue floor test allows additional adapter detail while preserving
the declared reason.

### Context decision

The other-context row is out of domain. Check both the wrapper context issue and
the adapter context issue. The wrapper state is the release-facing decision.

### Invalid decision

The malformed row is invalid. Check that it still receives a receipt, has zero
counts, and does not abort C14, C15, or C16 evaluation.

## 6. C14 review worksheet

### Required fields

The C14 row should show region ID, previous signed score, current signed score,
context, and switch threshold.

### Positive decision

The positive row crosses sign and threshold. Confirm the previous and current
compartment labels are retained, along with the delta-derived confidence.

### Stable decision

The stable row is partial because it does not meet the switch threshold. Confirm
that stable is a visible outcome, not an omitted outcome.

### Context decision

The normal-compartment row is out of domain. Confirm that a cross-sign delta does
not override the context boundary.

### Invalid decision

The missing-score row is invalid. Confirm the receipt is present and the invalid
issue is operation-specific.

## 7. C15 review worksheet

### Required fields

The C15 row should show path ID, ordered nodes, edge IDs, edge uncertainty,
signal, context, and minimum effective signal.

### Positive decision

The positive path has one more node than edge count, and its uncertainty-adjusted
signal clears the threshold. Confirm effective signal is bounded and addressed.

### Weak decision

The weak path has high edge uncertainty. Confirm the accumulated uncertainty and
weak-signal issue remain visible. Do not replace the effective value with the raw
signal in review output.

### Disconnected decision

The disconnected path has a node/edge mismatch. Confirm the path remains partial
and carries the disconnected-path issue.

### Context decision

The other-context path is out of domain. The path shape is not enough to qualify
it for this run.

## 8. C16 review worksheet

### Required fields

The C16 row should show path IDs, exact context, bundle ID, and assay IDs.

### Positive decision

The positive publication has two paths and two assay identifiers. Confirm both
the records address and the bundle address are present.

### Context decision

The other-context row is out of domain before publication. No bundle address
should be emitted for the rejected context.

### Assay decision

The missing-assay row is partial. A valid path ID alone is insufficient for a
publication bundle.

### Empty decision

The empty row is partial and carries an empty-evidence issue. It is not invalid
because the operation can represent an empty input as a controlled review state.

## 9. Receipt review

Use one receipt row at a time. Confirm:

1. record ID matches fixture;
2. operation matches contract;
3. role matches fixture;
4. expected state is retained;
5. observed state is bounded;
6. primary count is non-negative;
7. secondary count is non-negative;
8. issue tuple is stable;
9. summary omits raw input;
10. content address is present.

The summary is intended to help diagnosis without copying the source payload into
every downstream artifact.

## 10. Check review

Check IDs are stable review handles. Use exact IDs in review notes. A failed
record check should be read with its sibling checks:

- state;
- issue floor;
- context;
- operation;
- role;
- address;
- sanitization.

If only the address check fails, inspect serialization. If state and issue checks
fail together, inspect the adapter wrapper and expected record. If operation and
role checks fail together, inspect the fixture join.

## 11. Replay review

Replay is accepted when all eight checks pass. The most informative split is:

| Failure | Meaning |
| --- | --- |
| fixture ID | wrong fixture selected |
| fixture version | version changed between runs |
| context | context was not preserved |
| state | adapter behavior changed |
| receipt address | receipt content changed |
| evaluation address | aggregate content changed |
| accepted status | one run crossed the gate |
| record count | record selection changed |

Run comparison should use the state-change tuple to identify affected records.

## 12. Scenario review

The scenario report is the contract’s behavioral matrix. It requires every
positive row to be supported and every control to remain non-supported. It also
requires the expected issue floor.

When adding a new control, first write its expected state and issue floor. Then
write the adapter call and finally add the scenario assertion. This order makes
the intended boundary visible before implementation details.

## 13. Policy review

Policy rules are divided into global and operation-specific scope:

- public aggregate boundary;
- exact context;
- ecDNA descriptive interpretation;
- compartment descriptive interpretation;
- uncertainty transport interpretation;
- publication receipt requirements;
- research-only scope;
- aggregate-only scope.

The policy report does not duplicate adapter calculations. It checks whether the
calculated result is suitable for the declared release surface.

## 14. Schema review

Review schema fields against the contract registry. For each operation compare:

- required payload fields;
- positive state;
- control states;
- issue values;
- schema address.

Schema review is complete only when the 20 checks pass. A contract update without
a schema test is incomplete.

## 15. Lineage review

For each of sixteen edges, compare:

- edge record ID to receipt record ID;
- edge operation to receipt operation;
- edge output state to receipt state;
- edge output address to receipt address;
- edge source IDs to fixture source IDs;
- edge content address prefix.

The lineage report should preserve the full five-source set even when a source is
used by only one operation.

## 16. Reconciliation review

Reconciliation is a join view, not a second evaluator. It should show sixteen
items and three global checks. The item passes only when state, issue floor, and
source presence all pass.

If expected and observed states differ, inspect the record’s operation and role
before changing the expected state. Expected state changes are fixture contract
changes and require a reviewable reason.

## 17. Metrics review

The metric table should have one row for each operation. Verify:

- record count is four;
- positive count is one;
- control count is three;
- supported count is one;
- non-supported count is three;
- issue count is non-negative;
- operation address is present.

Totals should be sixteen, four, twelve, four, twelve, and the sum of operation
issues respectively.

## 18. Bundle review

The bundle address covers every nested artifact. Verify that the bundle contains
data audit, evaluation, replay, scenarios, policy, lineage, reconciliation, and
metrics. A nested artifact should not be recomputed by the release builder.

The bundle accepted property is a conjunction. It should be false if any
upstream report is rejected.

## 19. Quality review

Use the following order for a rejected quality report:

1. data audit;
2. evaluation;
3. replay;
4. scenarios;
5. policy;
6. schema;
7. lineage;
8. reconciliation;
9. closure checks;
10. bundle.

Fix the earliest failure and rerun. Do not assume later failures will persist.

## 20. Runtime review

The runtime result connects the quality report to a named run. Verify run ID,
fixture ID, fixture version, status, quality acceptance, and runtime address.

Two different run IDs should not change fixture receipt addresses. If they do,
inspect whether the run ID was included in an artifact that should be fixture
content-addressed.

## 21. Trace review

Review the nine trace stages as a timeline:

1. data audit;
2. evaluation;
3. replay;
4. scenarios;
5. policy;
6. schema;
7. lineage;
8. reconciliation;
9. bundle.

The trace is for inspection and comparison. It does not replace the quality
report’s decision.

## 22. View review

The review queue should contain exactly the twelve controls in the default run.
Priority four entries are context or malformed boundaries. Priority two entries
are parseable partial outcomes. Actions should explain the next inspection.

The source matrix should contain five rows. Every matrix row should include one
or more record IDs and one or more operation IDs.

## 23. Export review

Expected line counts for the default exports are:

| Export | Lines |
| --- | ---: |
| receipts CSV | 17 |
| review CSV | 13 |
| metrics CSV | 5 |
| Markdown | header plus 12 review rows and summary |

The JSON projection should remain the source for machine comparison. CSV values
are flattened for review convenience and should not be parsed back as a new
canonical report.

## 24. Local test order

Use focused tests first:

```powershell
python -m pytest tests/test_topology_frontier_evidence.py -q
python -m pytest tests/test_topology_frontier_evidence_cli.py -q
python -m pytest tests/test_topology_frontier_contract_matrix.py -q
```

Then use the existing adapter tests:

```powershell
python -m pytest tests/test_frontier_inference_alpha.py -q
python -m pytest tests/test_topology_alpha.py tests/test_topology_beta.py -q
```

Finally run the complete suite. A focused green result does not replace the
complete suite because registry, CLI dispatch, and serialization are shared.

## 25. Actions review

The quality workflow runs the same commands on three Python versions. Check:

- each matrix job completed;
- the Domain 09 data audit passed;
- fixture evaluation passed;
- replay passed;
- quality gate passed;
- operation contracts passed;
- schema passed;
- lineage passed;
- reconciliation passed;
- pipeline passed;
- release passed;
- view and trace passed.

The command steps are intentionally explicit so a single failing stage is easy
to locate in the job summary.

## 26. Change review questions

Ask these questions for any changed module:

1. What invariant does this module own?
2. Which positive path exercises the change?
3. Which control proves the boundary?
4. Which issue code explains a rejected path?
5. Does the schema expose the changed field?
6. Does policy still describe the scope?
7. Does lineage retain source closure?
8. Does reconciliation expose expected/observed drift?
9. Does replay stay deterministic?
10. Do exports preserve the same state?

If one answer is missing, the change needs a deeper module-level test.

## 27. Common anti-patterns

Avoid these patterns:

- changing a control to positive because it is convenient;
- treating a score as a probability without calibration;
- dropping context mismatch rows from review;
- dropping malformed rows from the receipt set;
- recomputing a bundle inside the release formatter;
- adding source IDs only to a view;
- hiding a schema failure behind a serializer default;
- using a remote fetch in the deterministic test path;
- manually editing a content address;
- comparing only the final accepted flag.

## 28. Safe extension sequence

To add a fifth topology operation:

1. add the enum value;
2. add one contract row;
3. add one positive and three control records;
4. implement evaluator dispatch;
5. add issue vocabulary;
6. add schema generation coverage;
7. add policy rule;
8. add scenario rows;
9. add lineage and reconciliation coverage;
10. update metrics and views;
11. update CLI and CI;
12. update all four documentation surfaces;
13. run focused and complete tests;
14. perform staged diff review.

## 29. Safe source refresh sequence

To refresh a public source receipt:

1. inspect the new locator;
2. preserve the source identifier when purpose is unchanged;
3. update release and scope explicitly;
4. update fixture version;
5. recompute source address;
6. recompute fixture address;
7. rerun audit and lineage;
8. rerun replay and quality;
9. update release documentation;
10. retain the prior version for comparison.

## 30. Release handoff

The handoff note should include:

- commit ID;
- fixture version;
- run ID;
- quality status;
- failed-check tuple;
- source count;
- record count;
- positive/control counts;
- bundle address;
- release address;
- focused test result;
- full-suite result;
- Actions run links;
- next module.

Keep the handoff concise, but do not omit the addresses and check status needed
to reproduce the release decision.

## 31. Final reviewer checklist

- [ ] identity fields match;
- [ ] context is exact;
- [ ] boundary is public aggregate;
- [ ] five source receipts close;
- [ ] four operations are covered;
- [ ] four positives are supported;
- [ ] twelve controls are visible;
- [ ] C13 weak/context/invalid controls pass;
- [ ] C14 stable/context/invalid controls pass;
- [ ] C15 weak/disconnected/context controls pass;
- [ ] C16 context/assay/empty controls pass;
- [ ] receipts are sanitized;
- [ ] replay is accepted;
- [ ] scenarios are accepted;
- [ ] policy is accepted;
- [ ] schemas are accepted;
- [ ] lineage is accepted;
- [ ] reconciliation is accepted;
- [ ] metrics are complete;
- [ ] bundle is accepted;
- [ ] quality has twelve passing checks;
- [ ] release builds;
- [ ] trace has nine stages;
- [ ] view has twelve review rows;
- [ ] exports have expected counts;
- [ ] focused tests pass;
- [ ] full suite passes;
- [ ] staged scan is clean;
- [ ] main and build refs are pushed;
- [ ] Actions is green.
