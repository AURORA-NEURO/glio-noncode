# Security

GLIO-NONCODE is designed for local processing of sensitive research inputs. The initial service binds to loopback by default and does not transmit case data to an external service.

Report security issues privately to the repository maintainers. Do not include personal data, controlled genomic data, credentials, or full private case manifests in a public issue.

Operators should:

- pseudonymize subject identifiers before ingestion;
- isolate the `.glio` data root with filesystem permissions;
- treat adapters and imported evidence as untrusted input;
- review source licenses and data-use terms before redistribution; and
- use an authenticated reverse proxy before exposing the API beyond loopback.
