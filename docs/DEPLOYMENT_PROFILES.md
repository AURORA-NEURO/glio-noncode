# Deployment profiles

The local API is safe by default on loopback. Binding it to a private or
public network is a separate deployment decision and must be represented by a
profile. A non-loopback profile requires all of the following:

- API-key authentication;
- TLS intent;
- an enabled audit ledger; and
- at least one named principal with explicit scopes.

The profile is public policy metadata. API keys never appear in it. The server
accepts credential material only at startup, reduces each key to an in-memory
digest, and never places the key in a response, error, or audit event.

## Create a profile

```powershell
glio-noncode deployment-profile --output deployment-profile.json
glio-noncode deployment-profile `
  --profile-id glio-institutional `
  --host 10.0.0.12 `
  --exposure private_network `
  --authentication api_key `
  --principal-id institutional-operator `
  --principal-id institutional-auditor `
  --role operator `
  --scopes read write review audit `
  --output deployment-profile.json
glio-noncode deployment-profile-schema --output deployment-profile-schema.json
```

`deployment-profile` creates descriptors only. Put credentials in a separate
file. A plain file containing one key is mapped to the only profile principal;
a JSON object maps principal IDs to keys:

```json
{
  "institutional-operator": "replace-with-a-random-secret",
  "institutional-auditor": "replace-with-a-different-random-secret"
}
```

Start the API with the profile and credential file:

```powershell
glio-noncode serve `
  --host 10.0.0.12 `
  --deployment-profile deployment-profile.json `
  --api-key-file deployment-credentials.json
```

Requests to protected routes use `Authorization: Bearer <key>`. Scope mapping
is explicit: reads require `read`, writes require `write`, review and
assignment routes require `review`, and audit routes require `audit`. The
health and profile routes are public metadata routes. Authentication failures,
scope denials, rate-limit blocks, and successful requests are all retained in a
redacted hash chain.

## Audit export

The running server exposes the current redacted ledger at
`GET /v1/deployment/audit`. It contains no bearer token, credential, subject
identifier, agent attribution, model attribution, or programming-language
metadata. Save the response and verify or export it offline:

```powershell
glio-noncode deployment-audit deployment-audit.json --format markdown --output deployment-audit.md
glio-noncode deployment-audit deployment-audit.json --format csv --output deployment-audit.csv
```

Audit events contain a sequence number, UTC observation time, method, route,
operation, public principal ID, decision, bounded reason, previous event
address, and their own content address. The verifier checks sequence closure,
hash chaining, address reconstruction, and the accepted-state declaration.

This boundary authenticates API access; it does not authenticate a specimen,
approve a clinical action, or replace institutional identity, network, TLS,
secret-rotation, or incident-response controls.
