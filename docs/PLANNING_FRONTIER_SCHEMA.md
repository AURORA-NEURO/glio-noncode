# Planning frontier schema

The shared context field is an exact, pipe-delimited key:

`GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment`

The schema requires explicit source and context fields. Model eligibility rows
carry model identity, model family, cell state, declared context support,
evidence strength, blockers, and source identity. Guide rows carry design,
target, oligo, sequence, type, context, strand, offset, and source version.
Control rows carry target identity, condition, control types, replicate counts,
seed, and context. Power rows carry effect, variance, alpha, target power,
planned repetitions, blocking factors, and context.

`default_planning_schema()` is the executable schema registry. Missing fields
are reported before operation execution by `validate_planning_payload()`.
