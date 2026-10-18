# AI Builder Cup submission copy

## Project title

KiasuCheck — Check first. Trust smarter.

## Theme

Retail & Commerce

## Problem

Southeast Asian shoppers encounter the same-looking item across multiple stores and platforms at different prices. Existing comparisons can mislead because listings differ by model generation, storage, bundle, colour, warranty or seller identity. Mobile app shopping also makes browser-extension-only solutions difficult to adopt.

## Solution

KiasuCheck is an AI trust layer whose first capability is a mobile-first shopping verification agent with an optional Chrome extension. A shopper submits a screenshot, URL or product name. Gemini produces an exact product fingerprint, grounds discovery in public Google Search results, and explains which alternatives are genuine matches. Deterministic rules reject conflicting model numbers and important variants before price savings are shown.

## Google Cloud technology

- Gemini on Vertex AI for multimodal product understanding
- Grounding with Google Search for current public-web discovery and citations
- Cloud Run for a scalable web/API deployment
- Cloud Build and Artifact Registry through source deployment

## Agentic behaviour

KiasuCheck observes an unstructured product, plans targeted searches from normalized identity, gathers evidence across sites, checks conflicts, ranks alternatives and returns recommendations with uncertainty. The shopper—not the system—makes the purchasing decision.

## Innovation

The prototype separates product identity confidence, seller similarity and price. It does not allow a spectacular discount to hide a variant mismatch. One backend supports both the mobile journey and an in-context browser experience.

The same evidence-first interaction can later support News Check, Media Check and Scam Check. The hackathon deliverable intentionally proves the approach with Shop Check rather than overstating unfinished capabilities.

## Impact measures

- Percentage of misleading variant matches correctly rejected
- Average verified savings on strong matches
- Time required to compare an item across platforms
- Percentage of results with a usable public source
- Shopper confidence before opening the final seller page

## Limitations

The hackathon version relies on publicly indexed pages rather than official marketplace product APIs. Availability and prices must be verified on the destination page. Seller similarity is suggestive, not proof of common ownership.

