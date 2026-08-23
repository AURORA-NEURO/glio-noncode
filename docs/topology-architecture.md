# D09 3D Genome and Regulatory Topology

D09 is the public aggregate for three-dimensional genome structure and regulatory topology in adult glioma. It joins four existing public-data tranches into one typed, deterministic release surface:

| Family | Operations | Focus |
| --- | ---: | --- |
| `topology_context_frontier` | C01-C04 | contact import, matrix quality, boundary ensemble, insulation delta |
| `topology_beta_frontier` | C05-C08 | loop and stripe evidence, promoter capture, enhancer-promoter contact, activity-by-contact |
| `topology_alpha_frontier` | C09-C12 | boundary motif, CTCF/cohesin support, IDH insulator state, structural-variant rewiring |
| `topology_frontier` | C13-C16 | ecDNA contact, compartment switch, topology uncertainty transport, release publication |

The public aggregate has a fixed boundary:

- reference assembly: `GRCh38`
- disease: `glioma`
- age scope: `adult`
- developmental state: `stem_like`
- territory: `tumor`
- unresolved dimension: `unknown`

The release contains 17 source records, 16 operation contracts, and four cases for every operation. Each operation has one accepted positive case and three held controls: foreign context, malformed input, and identity conflict. This produces 16 positive cases, 48 control cases, and 392 deterministic checks.

## Execution shape

The aggregate delegates positive records to the public family evaluators. Controls are held at the aggregate boundary before delegation. Every receipt retains the operation, family, plane, scenario, expected state, observed state, result state, issue codes, expected counts, observed counts, output address, and content address.

The runtime has 22 ordered stages:

1. fixture loaded
2. sources audited
3. schema validated
4. plan compiled
5. context family ready
6. beta family ready
7. alpha family ready
8. frontier family ready
9. cases executed
10. review routed
11. lineage linked
12. ledger closed
13. metrics materialized
14. replay closed
15. artifacts materialized
16. bundle closed
17. release built
18. quality gated
19. depth accounted
20. runtime finalized
21. controls closed
22. observability closed

The release is published only when typed validation, source joins, operation joins, positive receipts, control routing, replay, lineage, metrics, artifact safety, and the quality gate all pass.

## Public entry points

The stable package surface is `glio_noncode.topology_architecture_exports`. The root package also exposes the D09 constants, contracts, fixture loader, evaluator, runtime, query functions, release projections, and validation functions.

The checked-in aggregate is [data/topology-architecture-public-aggregate.json](../data/topology-architecture-public-aggregate.json). It is a reproducible public fixture, not a claim of clinical interpretation. Topology observations remain descriptive and are not converted into diagnosis, prognosis, or treatment decisions.
