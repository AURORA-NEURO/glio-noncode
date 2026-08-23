# Validation-design frontier checklist

## Data

- [ ] five public HTTPS source receipts are present
- [ ] every record references a known source
- [ ] sixteen record identities are unique
- [ ] four positive and twelve control rows are present
- [ ] the public aggregate boundary is declared
- [ ] private markers are absent

## Operations

- [ ] gap coverage distinguishes covered and uncovered dimensions
- [ ] foreign context is blocked
- [ ] assay routing requires a supported matching capability
- [ ] MPRA validates allele change, controls, and budget
- [ ] STARR-seq validates strand, controls, and budget
- [ ] malformed payloads are rejected

## Assurance

- [ ] five checks are emitted per record
- [ ] reconciliation closes expected and observed states
- [ ] content addresses are present
- [ ] replay is deterministic
- [ ] review queue routes issue-bearing rows
- [ ] release planes are accepted
- [ ] compile and focused regression tests pass
