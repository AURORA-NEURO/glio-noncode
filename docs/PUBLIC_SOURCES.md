# Public source adapters

The live reference layer implements bounded metadata and sequence retrieval with the Python standard library.

## Ensembl REST

The adapter uses:

- `GET /sequence/region/:species/:region` for sequence fallback and reference checks;
- `GET /lookup/symbol/:species/:symbol` for explicit gene lookup; and
- `GET /overlap/region/:species/:region` for nearby gene, regulatory, and motif features.

Regional requests are limited by the endpoint contract and the local source specification. Nearby gene assignment is labeled `regional_overlap_baseline`; it is a candidate link, not a causal target-gene conclusion.

## UCSC Genome Browser REST

The adapter uses `/getData/sequence` for small-window sequence retrieval and `/getData/track` for bounded track retrieval. The API uses zero-based half-open coordinates, while the canonical case objects retain one-based inclusive intervals; the adapter records this conversion in the request URL and sequence interval.

## ENCODE REST

The adapter uses `/search/` for experiment metadata and `/<accession>/` for object metadata. It does not silently treat an assay file as usable evidence: assay type, biosample, assembly, processing, licensing, and context transport remain source metadata that must be reviewed before conversion into a claim.

## Cache and provenance

Every successful request records the source ID, source version, URL, request hash, response hash, retrieval time, attempts, elapsed time, and cache expiry. Cache hits retain the original retrieval receipt and are marked as `cache_hit`. HTTP 404, rate-limit, transport, malformed-payload, and response-size failures have distinct failure paths.

The adapters are suitable for small case windows and metadata exploration. Bulk reference construction should use source downloads and a local indexed representation, with a separate license, checksum, and release registry.

