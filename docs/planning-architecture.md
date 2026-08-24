# D13 Planning and Validation Architecture

D13 is the public aggregate planning surface for glio-noncode. It joins four
independent, deterministic family fixtures into one typed release boundary:

| Family | Capabilities | Planning role |
| --- | --- | --- |
| validation design | GNC-D13-C01–C04 | evidence gaps, assay routing, MPRA, and STARR-seq packaging |
| editing design | GNC-D13-C05–C08 | CRISPR, base editing, prime editing, and allele reporter design |
| planning | GNC-D13-C09–C12 | model eligibility, guide adaptation, controls, and power planning |
| validation release | GNC-D13-C13–C16 | off-target risk, value of information, experiment packages, and claim updates |

The aggregate contains twenty public source receipts, sixteen operation
contracts, and sixty-four delegate-backed cases. Every operation contributes
one positive row and three controls. The aggregate retains the exact family
context, delegate fixture identity, delegate record identity, source joins,
observed state, issue codes, bounded counts, and content addresses.

D13 is a research-planning boundary. A state such as `ready`, `designed`,
`packaged`, or `updated` records the declared transformation of public
aggregate inputs. It does not establish experimental efficacy, biological
causality, therapeutic benefit, clinical validity, or authorization.

## Runtime closure

The runtime has twenty-four ordered stages covering fixture loading, source
audit, schema validation, dependency planning, four family boundaries, case
execution, review routing, lineage, ledger, metrics, replay, artifacts,
release, quality, depth, compliance, controls, reporting, and final addressing.
The evaluator emits seven checks per case plus ten global checks. All held
states remain visible in the review projection.

The checked-in fixture is
`data/planning-architecture-public-aggregate.json`. Its payloads are public
aggregate receipts and synthetic planning mappings. The compliance gate rejects
restricted identity or decision fields before release.
