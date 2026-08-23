# Validation-release frontier failure modes

| Operation | Failure | State | Retained evidence | Recovery |
| --- | --- | --- | --- | --- |
| C13 | maximum candidate burden reaches blocking threshold | `blocked` | target, maximum, tier, issue code | inspect candidates and thresholds |
| C13 | exact context differs | `blocked` | requested and row context | verify context before replay |
| C13 | score or candidate shape is malformed | `rejected` | accepted field contract | repair input and replay |
| C14 | budget cannot fund a dependency-safe selection | `review` | budget, selected IDs, remaining budget | revise plan or budget |
| C14 | prerequisite dependency is missing | `review` | missing dependency IDs | supply prerequisite receipt |
| C14 | prerequisite graph contains a cycle | `blocked` | graph identity and cycle issue | revise dependency graph |
| C14 | context differs | `blocked` | plan context | stop transport and review |
| C15 | experiment set is empty | `rejected` | package identity and field contract | add declared experiment rows |
| C15 | IDs collide across files | `review` | duplicate IDs and file roles | resolve identity collision |
| C15 | context differs | `blocked` | package context | verify exact context |
| C16 | claim is unknown | `review` | claim and result IDs | route to claim-owner review |
| C16 | evidence receipt is missing or malformed | `review` | result ID and issue code | attach a valid receipt |
| C16 | result context differs | `blocked` | result context and claim context | verify context before update |

Controls are intentionally executable. `run_validation_release_failure_injections`
rehearses representative controls and requires the observed state and issue
code to match the declared failure boundary. A failed probe blocks the release
quality gate; it is not silently converted to success.

## Operational states

- `ready`: a C13 or C14 planning row passed its declared local boundary;
- `packaged`: a C15 manifest closed its declared IDs and file addresses;
- `updated`: a C16 known claim received an exact-context result receipt;
- `review`: the row remains inspectable but is not releaseable;
- `blocked`: a context, safety, or dependency boundary prevents continuation;
- `rejected`: the input contract is malformed or incomplete;
- `abstained`: reserved for explicit future source insufficiency handling.

None of these states means that an experiment succeeded or that a biological,
clinical, causal, or treatment claim is established.
