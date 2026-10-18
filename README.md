# ShopProof

**Same product. Better proof.**

ShopProof is an AI shopping-verification prototype for the 2026 AI Builder Cup. A shopper can paste a product name or URL, upload a screenshot, or use the Chrome extension while browsing. Gemini extracts an exact product fingerprint, searches publicly indexed listings, and explains which offers are truly comparable.

ShopProof does **not** claim direct access to Shopee, Lazada, or TikTok Shop APIs. Live results come from Grounding with Google Search and are labelled as public indexed snapshots.

## Why it matters

Price comparison often fails at product identity. A cheaper result may be another generation, storage size, bundle, colour, warranty type, or accessory. ShopProof scores identity before price and exposes uncertainty instead of silently presenting a false bargain.

## Demo surfaces

- Mobile-first web application for screenshots, URLs, and product descriptions
- Manifest V3 Chrome extension for checking the product page currently being viewed
- Explicit demo-data switch/fallback so a three-minute presentation does not depend on marketplace indexing

## Status

The complete MVP is being prepared on the `codex/shopproof-mvp` branch.
