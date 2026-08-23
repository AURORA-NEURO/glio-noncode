# Planning frontier data dictionary

The executable dictionary is returned by `build_planning_data_dictionary()`.
It assigns each field an operation, direction, type, required flag, definition,
and content address.

Important distinctions:

- `declared_context_keys` is source-declared support, not inferred similarity.
- `sequence` is preserved as a normalized DNA string; adaptation is not an
  activity assay.
- `randomization_seed` makes assignments reproducible; it does not certify
  balance or execution order.
- `required_replicates` is an approximation result with explicit assumptions,
  not a guarantee of statistical power.
