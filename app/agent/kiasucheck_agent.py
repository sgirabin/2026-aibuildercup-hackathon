from __future__ import annotations

from dataclasses import dataclass

from app.models import AgentStep, AgentTrace, Candidate, ProductFingerprint, SearchIntent, Source
from app.services.gemini import extract_fingerprint, search_candidates
from app.services.matching import confidence_level, rank_candidates


@dataclass(frozen=True)
class AgentResult:
    fingerprint: ProductFingerprint
    candidates: list[Candidate]
    sources: list[Source]
    trace: AgentTrace


class KiasuCheckShoppingVerificationAgent:
    """Goal-directed shopping investigator with tools, retry logic and guardrails.

    Gemini observes and plans from unstructured input, Google Search supplies grounded
    evidence, and deterministic scoring verifies identity. The agent may refine its
    search once when the first investigation produces no supported candidate.
    """

    name = "KiasuCheck Shopping Verification Agent"
    goal = "Find and verify supported cross-platform offers"
    max_iterations = 2

    def run(
        self,
        query: str,
        image_bytes: bytes | None,
        mime_type: str | None,
        intent: SearchIntent,
        target_marketplace: str | None,
        objectives: list[str],
    ) -> AgentResult:
        steps: list[AgentStep] = []
        tools_used = ["extract_product_fingerprint"]

        fingerprint = extract_fingerprint(query, image_bytes, mime_type)
        steps.append(
            AgentStep(
                stage="observe",
                tool="extract_product_fingerprint",
                summary=f"Identified {fingerprint.product_name} from the submitted shopping context.",
            )
        )

        targets = self._targets(fingerprint, target_marketplace)
        selected = objectives or [self._default_objective(intent)]
        steps.append(
            AgentStep(
                stage="plan",
                summary=(
                    f"Planned {', '.join(selected)} checks across {', '.join(targets)} "
                    f"using {len(fingerprint.search_terms)} product-specific search term(s)."
                ),
            )
        )

        all_candidates: list[Candidate] = []
        all_sources: list[Source] = []
        iterations = 0
        for iteration in range(1, self.max_iterations + 1):
            iterations = iteration
            if "google_search_grounding" not in tools_used:
                tools_used.append("google_search_grounding")
            candidates, sources = search_candidates(
                fingerprint, intent, target_marketplace, selected
            )
            all_candidates = self._merge_candidates(all_candidates, candidates)
            all_sources = self._merge_sources(all_sources, sources)
            steps.append(
                AgentStep(
                    stage="search",
                    tool="google_search_grounding",
                    summary=(
                        f"Investigation {iteration} examined grounded public results and retained "
                        f"{len(candidates)} supported candidate(s)."
                    ),
                )
            )
            if all_candidates:
                steps.append(
                    AgentStep(
                        stage="evaluate",
                        summary="Evidence was sufficient to proceed to deterministic verification.",
                    )
                )
                break
            if iteration < self.max_iterations:
                self._refine_search_terms(fingerprint, targets)
                steps.append(
                    AgentStep(
                        stage="evaluate",
                        summary="Evidence was insufficient, so the agent refined the query for one final search.",
                    )
                )

        if "verify_product_identity" not in tools_used:
            tools_used.extend(["verify_product_identity", "compare_supported_prices"])
        ranked = rank_candidates(fingerprint, all_candidates)
        rejected = sum(candidate.verdict == "Variant mismatch" for candidate in ranked)
        steps.append(
            AgentStep(
                stage="verify",
                tool="verify_product_identity",
                summary=f"Verified {len(ranked)} candidate(s) and rejected {rejected} identity conflict(s).",
            )
        )

        evidence_score = self._run_confidence(ranked)
        status = "completed" if ranked else "insufficient_evidence"
        steps.append(
            AgentStep(
                stage="recommend",
                tool="compare_supported_prices",
                summary=(
                    "Ranked supported offers by identity before price."
                    if ranked
                    else "Reported insufficient public evidence instead of inventing an offer."
                ),
            )
        )
        return AgentResult(
            fingerprint=fingerprint,
            candidates=ranked,
            sources=all_sources,
            trace=AgentTrace(
                name=self.name,
                goal=self.goal,
                status=status,
                iterations=iterations,
                tools_used=tools_used,
                evidence_confidence_score=evidence_score,
                evidence_confidence_level=confidence_level(evidence_score),
                steps=steps,
            ),
        )

    @staticmethod
    def _default_objective(intent: SearchIntent) -> str:
        return {
            "seller": "same_shop_product",
            "similar": "similar_product",
            "exact": "same_product",
            "multi": "same_product",
        }[intent]

    @staticmethod
    def _targets(
        fingerprint: ProductFingerprint, target_marketplace: str | None
    ) -> list[str]:
        if target_marketplace:
            return [target_marketplace]
        return [
            platform
            for platform in ["Shopee", "Lazada", "TikTok Shop"]
            if platform.lower() != (fingerprint.source_marketplace or "").lower()
        ]

    @staticmethod
    def _refine_search_terms(
        fingerprint: ProductFingerprint, targets: list[str]
    ) -> None:
        exact_parts = [
            fingerprint.brand,
            fingerprint.model_number,
            fingerprint.variant,
            fingerprint.storage,
            fingerprint.colour,
        ]
        exact_identity = " ".join(part for part in exact_parts if part)
        if not exact_identity:
            exact_identity = fingerprint.product_name
        refined = [f'"{exact_identity}" {platform} Singapore' for platform in targets]
        fingerprint.search_terms = list(dict.fromkeys([*fingerprint.search_terms, *refined]))

    @staticmethod
    def _merge_candidates(
        existing: list[Candidate], incoming: list[Candidate]
    ) -> list[Candidate]:
        by_url = {candidate.url: candidate for candidate in existing}
        by_url.update({candidate.url: candidate for candidate in incoming})
        return list(by_url.values())

    @staticmethod
    def _merge_sources(existing: list[Source], incoming: list[Source]) -> list[Source]:
        by_url = {str(source.url): source for source in existing}
        by_url.update({str(source.url): source for source in incoming})
        return list(by_url.values())

    @staticmethod
    def _run_confidence(candidates: list[Candidate]) -> int:
        supported = [
            candidate.evidence_confidence_score
            for candidate in candidates[:3]
            if candidate.verdict != "Variant mismatch"
        ]
        return round(sum(supported) / len(supported)) if supported else 20
