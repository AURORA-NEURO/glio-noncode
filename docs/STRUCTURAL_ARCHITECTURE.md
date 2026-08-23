# Domain 02 structural architecture

The D02 architecture composes the existing structural adapters into one
replayable, public-aggregate boundary. It covers sixteen operation contracts,
four adapter families, seven validation planes, sixty-four executable cases,
twenty runtime stages, six offline artifacts, and a release quality gate.

## Operation surface

| Capabilities | Operation family | Adapter boundary |
| --- | --- | --- |
| C01–C04 | reconstruction and harmonization | breakends, consensus, complex rearrangements, copy number |
| C05–C08 | structural pattern interpretation | focal amplification, breakpoint clusters, circular DNA candidates, enhancer bridges |
| C09–C12 | allele and haplotype representation | phased paths, allele-aware events, pangenome projection, repeat/mobile annotation |
| C13–C16 | frontier evidence mechanics | tandem repeats, compound haplotypes, breakpoint intervals, evidence export |

The architecture layer does not replace those scientific adapters. A positive
case is converted into the adapter's typed fixture record and its result is
reduced to counts, result state, issue codes, and a content address. Raw
operation payloads are not copied into evaluation or release receipts.

## Fixture design

`examples/structural-architecture-public-aggregate.json` is a checked-in,
versioned aggregate fixture. It has:

- eight HTTPS source receipts with public aggregate scope;
- one exact six-field GRCh38 context;
- one positive case for every C01–C16 operation;
- three controls per operation: foreign context, malformed shape, and duplicate identity;
- public identifiers and bounded mechanics payloads only;
- deterministic addresses for sources, operation specs, cases, and the fixture.

The source receipts document the public resource and release framing; they do
not imply that the small fixture is a complete copy of any upstream callset.
Coordinates, labels, graph intervals, and genotype strings are bounded
mechanics observations. The architecture makes no sequence, homology,
transposition, or clinical claim from them.

## Runtime

`run_structural_architecture` executes the following ordered stages:

1. load the fixture;
2. audit sources and aggregate scope;
3. compile the dependency plan;
4. score context, source, and control policy;
5. close ingestion cardinality;
6. close the core family;
7. close the beta family;
8. close the haplotype family;
9. close the frontier family;
10. execute all cases;
11. route held controls;
12. hash-link lineage;
13. materialize operation metrics;
14. close the seven-plane validation matrix;
15. close the export schema;
16. materialize six artifacts;
17. close the export allow-list;
18. replay the evaluation;
19. apply the release gate;
20. finalize the addressed runtime.

The published state is reached only when positive adapter results, control
decisions, lineage, artifact inventory, replay, failure probes, and runbook
metadata all pass. Review is a valid result for a control, but it cannot be
promoted to publication by the runtime.

## Local commands

```text
python -m glio_noncode structural-architecture-data-audit
python -m glio_noncode structural-architecture-plan
python -m glio_noncode evaluate-structural-architecture
python -m glio_noncode structural-architecture-runtime
python -m glio_noncode structural-architecture-quality
python -m glio_noncode structural-architecture-depth
python -m glio_noncode replay-structural-architecture
```

The focused verification is:

```text
python -m unittest tests.test_structural_architecture tests.test_structural_architecture_cli -q
```
