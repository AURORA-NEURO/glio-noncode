# D14 Build and Review Runbook

This runbook describes the repeatable sequence for extending and reviewing the evidence architecture module.

## 1. Load the fixture

Use `default_evidence_architecture_fixture()` for the checked-in fixture or `EvidenceArchitectureFixture.from_file()` for a reviewed copy. The loader retains enums, tuples, mappings, and content addresses. It rejects malformed top-level objects and malformed typed values.

Confirm the following before continuing:

- fixture id is stable;
- boundary is `public_aggregate_non_patient`;
- aggregate context is `multi_context_public_aggregate`;
- there are three family contexts;
- source, operation, and case counts are 19, 16, and 64;
- each case has one of four scenario values.

## 2. Audit source receipts

`audit_evidence_architecture_data()` checks source count, operation count, case count, family contexts, public aggregate flags, contiguous operation ordinals, source joins, operation joins, four-case balance, and the reserved foreign context label.

An audit with any failed check must stop the release path. Fix the fixture or delegate normalization before evaluating cases.

## 3. Compile operation dependencies

`build_evidence_architecture_plan()` creates sixteen nodes in ordinal order. The dependency policy is visible on every operation spec. A node is ready only when every dependency is found in an earlier node.

The four planes are represented in the operation list as:

| Plane | Operations |
| --- | --- |
| Lifecycle foundation | citation resolution, graph construction, edge validation, disagreement tracking |
| Lifecycle adjudication | tier adjudication, provenance lineage, uncertainty ledger, review routing, blinded adjudication, comment change log, release decision, evidence delta |
| Evidence release | reclassification, supersession, reproducibility bundle, signed dossier |

## 4. Execute delegates

`evaluate_evidence_architecture_fixture()` resolves each case to a namespaced delegate record. Delegate output is normalized into an aggregate execution containing:

- observed lifecycle state;
- exact issue codes;
- bounded field counts;
- output content address;
- family and record references;
- delegate context;
- output field names;
- expected delegate state and issues;
- a stable execution detail.

Missing delegate joins produce an invalid execution with `missing_delegate_record`. They do not disappear from the result set.

## 5. Route review

`build_evidence_architecture_review_queue()` routes all controls and any positive result outside the successful-state set. Blocking controls receive critical priority. The queue retains operation, family, scenario, state, reason, required action, and item address.

The review queue is a projection. It does not overwrite the case result, and it does not turn a held result into a success.

## 6. Build lineage and ledger

`evidence_architecture_lineage_rows()` emits one row per case-to-source join. Each row retains the delegate source id, operation, capability, case, fixture, record, aggregate context, delegate context, source address, case address, and lineage address.

`build_evidence_architecture_ledger()` appends sixteen operation declaration events followed by sixty-four case execution events. Sequence numbers are contiguous from one, and every event receives an address. Ledger closure requires both sequence continuity and event addresses.

## 7. Materialize projections

Six artifacts are created:

1. public fixture;
2. source register;
3. evaluation receipts;
4. review projection;
5. lineage projection;
6. metrics and ledger projection.

All artifacts use `public_aggregate` visibility and are review safe only when the audit is accepted and all source addresses are present.

## 8. Evaluate quality and release

The quality gate evaluates ten checks. A published release requires an accepted evaluation, safe artifacts, and the accepted quality path. Limitations remain in the release object.

The release state is `published` only when all required conditions close. Otherwise it is `review`.

## 9. Query and report

Use `query_evidence_architecture()` to filter by operation, family, or scenario. Query rows expose state, issue codes, plane, and output address. Payloads are not returned by this compact query surface.

Use `build_evidence_architecture_report()` for a machine-readable report and `evidence_architecture_report_markdown()` for a concise review projection. The report includes metrics, evaluation view, contract summary, control summary, runtime view, and limitations.

## 10. Validation checklist

Run the following checks after any fixture or evaluator change:

1. ruff check on all D14 modules and tests;
2. direct fixture audit;
3. direct evaluation with 458 checks;
4. runtime acceptance with 24 stages;
5. replay address equality;
6. compliance with zero restricted keys;
7. schema mapping with no errors;
8. query count of four for `D14-C14`;
9. CLI fixture, audit, plan, evaluation, runtime, quality, depth, replay, report, scenario, source, compliance, validation, query, and bundle commands;
10. delegate regression suites for the three family modules;
11. staged added-line metadata boundary scan;
12. `git diff --cached --check` before commit.

## 11. Change discipline

Keep operation ids and case ids stable once published. Add a new scenario only with a corresponding schema, evaluation, query, report, and test update. Preserve explicit held states and issue codes. Do not replace a control with a success path to make the quality gate pass.

When a change reaches a coherent build of at least five thousand added lines, commit it on `main` with a scoped build message and push the same commit to the working branch. Keep the public repository action workflow green.
