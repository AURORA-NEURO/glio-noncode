# Local operations

The default runtime writes immutable JSON objects and run indexes below `.glio/`. Keep this directory on an encrypted, access-controlled volume when processing controlled data. The repository ignores local object stores and generated caches.

Before sharing an artifact, classify it with the project data policy. Synthetic fixtures and public schemas can be distributed when their license and provenance permit it. Case manifests and research dossiers remain local or move only to an explicitly approved collaborator target. Network egress is disabled by the default project policy.

The service binds to `127.0.0.1` by default. A deployment that exposes it to a network must add authentication, authorization, TLS, rate limits, request size limits, audit export, and operational monitoring at the boundary.
