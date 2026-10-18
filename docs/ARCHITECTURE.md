# ShopProof architecture and decisions

## Product boundary

ShopProof verifies product identity before comparing an observed price. It augments the shopper's decision; it does not buy products, scrape authenticated pages, or claim marketplace partnerships.

## Request flow

1. The web client accepts text, a URL, or a screenshot. The extension extracts visible metadata from the active product page after the user clicks it.
2. Gemini normalizes the input into a fingerprint: brand, model, variant, colour, storage, bundle, seller, and observed price.
3. A second Gemini request uses Grounding with Google Search to discover publicly indexed Singapore listings.
4. The server accepts only recognized retailer domains and parses structured candidate facts.
5. Deterministic code scores every candidate. An exact model contributes most of the score; conflicting models or important variants produce a mismatch verdict.
6. The client shows product and seller similarity separately, source links, visible price, savings, and a freshness warning.

## Why AI plus deterministic logic

Gemini is strong at interpreting messy screenshots and fuzzy listing language. Deterministic scoring is auditable and prevents the model from quietly trading identity accuracy for an attractive price. This combination is easier to defend to hackathon judges than a single opaque prompt.

## Data handling

- Inputs are processed in memory and are not persisted by the application.
- The application has no user accounts or database.
- The extension reads the active page only when opened and sends data only after the user presses the check button.
- No credentials are stored in the repository.

## Failure design

The live pipeline may fail because credentials are absent, Vertex AI is unavailable, search returns no eligible listing, or a marketplace page is not indexed. The app then uses labelled demonstration data when `SHOPPROOF_DEMO_FALLBACK=true`. It never presents demo results as live prices.

## Next production steps

- Add per-IP quotas and request caching.
- Resolve Google Search redirect URLs and preserve citation-to-claim mappings.
- Add timestamped price history from licensed feeds or participating merchants.
- Add merchant identity verification instead of relying on storefront-name similarity.
- Introduce evaluation datasets across electronics, beauty, toys, and household products.

