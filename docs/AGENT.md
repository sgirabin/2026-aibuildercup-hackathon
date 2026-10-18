# KiasuCheck Shopping Verification Agent

## Goal

Find and verify supported cross-platform offers for the product a shopper is viewing. The agent ranks identity before price and reports insufficient evidence rather than inventing an offer.

## Agent contract

```yaml
ai_agent:
  name: KiasuCheck Shopping Verification Agent
  model: Gemini on Vertex AI
  runtime: Google Cloud Run
  maximum_investigations: 2
  human_in_the_loop: true
  tools:
    - extract_product_fingerprint
    - google_search_grounding
    - verify_product_identity
    - compare_supported_prices
```

## Decision loop

1. **Observe:** normalize a URL, product description, page metadata, or screenshot into a product fingerprint.
2. **Plan:** select target platforms and search objectives from the current marketplace and shopper request.
3. **Search:** call Gemini with Google Search grounding and retain only cited, allowed marketplace results.
4. **Evaluate:** proceed when at least one supported candidate exists. Otherwise, create exact quoted search terms and perform one final investigation.
5. **Verify:** apply deterministic model, brand, variant, storage, bundle, seller, and source checks.
6. **Recommend:** rank supported candidates by product identity before savings and return the evidence trace.

## Confidence scores

KiasuCheck keeps two different concepts visible:

- **Product match** estimates whether the candidate is the same product. Conflicting models or important variants override an attractive price.
- **Evidence confidence** measures completeness of grounded support, including a cited URL, visible price, exact model or brand evidence, observed facts, seller, and promotion.

Evidence confidence is labelled **High** at 80–100, **Medium** at 60–79, and **Low** below 60. A variant mismatch is capped at 45 even when the page contains extensive evidence. Price and savings never add confidence.

## Guardrails and stopping conditions

- Search only the requested target marketplaces.
- Accept URLs only from the grounding source catalogue and recognized marketplace domains.
- Never invent prices, promotions, sellers, URLs, or product attributes.
- Stop after evidence is sufficient. The interactive deployment uses one investigation for speed; an optional second investigation can be enabled for offline evaluation.
- Separate exact products, same-shop products, and similar alternatives.
- Show uncertainty and public-index freshness warnings.
- Keep the purchase decision with the shopper.

## Machine-readable output

Every analysis response includes an `agent` object containing the agent name, goal, status, iteration count, tools used, evidence confidence, and ordered execution steps. This provides observable proof for the UI, logs, tests, and evaluation tooling.
