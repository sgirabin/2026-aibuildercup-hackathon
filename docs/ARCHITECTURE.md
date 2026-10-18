# KiasuCheck architecture and decisions

## Product boundary

KiasuCheck verifies product identity before comparing an observed price. It augments the shopper's decision; it does not buy products, scrape authenticated pages, or claim marketplace partnerships.

## Request flow

1. The agent observes text, a URL, page metadata, or a screenshot and creates a structured product fingerprint.
2. The agent plans objectives and target marketplaces from the shopper's request and current platform.
3. It uses Grounding with Google Search as an investigation tool and retains only cited marketplace evidence.
4. The agent evaluates evidence sufficiency. When no supported candidate exists, it refines exact search terms and performs one final investigation.
5. Deterministic tools score identity and evidence confidence. Conflicting models or important variants produce a mismatch verdict regardless of price.
6. The client shows the agent trace, product match, evidence confidence, seller similarity, sources, savings, and freshness warning.

## Why AI plus deterministic logic

Gemini is strong at interpreting messy screenshots and fuzzy listing language. Deterministic scoring is auditable and prevents the model from quietly trading identity accuracy for an attractive price. This combination is easier to defend to hackathon judges than a single opaque prompt.

## Data handling

- Inputs are processed in memory and are not persisted by the application.
- The application has no user accounts or database.
- The extension reads the active page only when opened and sends data only after the user presses the check button.
- No credentials are stored in the repository.

## Failure design

The live pipeline may fail because credentials are absent, Vertex AI is unavailable, search returns no eligible listing, or a marketplace page is not indexed. The app then uses labelled demonstration data only when `KIASUCHECK_DEMO_FALLBACK=true`. It never presents demo results as live prices.

## Next production steps

- Add per-IP quotas and request caching.
- Resolve Google Search redirect URLs and preserve citation-to-claim mappings.
- Add timestamped price history from licensed feeds or participating merchants.
- Add merchant identity verification instead of relying on storefront-name similarity.
- Introduce evaluation datasets across electronics, beauty, toys, and household products.

