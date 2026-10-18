from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.agent import KiasuCheckShoppingVerificationAgent
from app.models import AgentStep, AgentTrace, AnalysisResponse, SearchIntent
from app.services.demo_data import get_demo
from app.services.matching import rank_candidates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
verification_agent = KiasuCheckShoppingVerificationAgent()

app = FastAPI(title="KiasuCheck", version="0.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((BASE_DIR / "templates" / "index.html").read_text())


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "kiasucheck",
        "version": settings.app_version,
        "git_commit": settings.git_commit,
        "revision": settings.cloud_run_revision,
        "model": settings.model,
        "live_fallback": str(settings.demo_fallback).lower(),
    }


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze(
    query: str = Form(default=""),
    image: UploadFile | None = File(default=None),
    force_demo: bool = Form(default=False),
    intent: SearchIntent = Form(default="exact"),
    target_marketplace: str | None = Form(default=None),
    objectives: str = Form(default=""),
) -> AnalysisResponse:
    query = query.strip()
    if not query and not image:
        raise HTTPException(400, "Add a product name, URL, or screenshot.")

    image_bytes: bytes | None = None
    mime_type: str | None = None
    if image:
        mime_type = image.content_type
        if mime_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(415, "Use a JPEG, PNG, or WebP screenshot.")
        image_bytes = await image.read(settings.max_upload_bytes + 1)
        if len(image_bytes) > settings.max_upload_bytes:
            raise HTTPException(413, "Image must be 5 MB or smaller.")

    if force_demo:
        fingerprint, candidates = get_demo(query)
        ranked = rank_candidates(fingerprint, candidates)
        return AnalysisResponse(
            fingerprint=fingerprint,
            candidates=ranked,
            mode="demo",
            warning="Demo evidence is illustrative and not a live marketplace quote.",
            agent=_demo_trace(ranked),
        )

    try:
        selected_objectives = [item.strip() for item in objectives.split(",") if item.strip()]
        result = verification_agent.run(
            query,
            image_bytes,
            mime_type,
            intent,
            target_marketplace,
            selected_objectives,
        )
        return AnalysisResponse(
            fingerprint=result.fingerprint,
            candidates=result.candidates,
            sources=result.sources,
            mode="live",
            warning=(
                "Prices are publicly indexed snapshots; verify the final price, stock, shipping "
                "and voucher eligibility on the seller page."
                if result.candidates
                else "Gemini completed the live search, but found no supported indexed product listings."
            ),
            agent=result.trace,
        )
    except Exception as exc:
        logger.exception("Live analysis failed")
        if not settings.demo_fallback:
            detail = f"Live AI search failed: {type(exc).__name__}: {str(exc)[:300]}"
            raise HTTPException(503, detail) from exc
        fingerprint, candidates = get_demo(query)
        return AnalysisResponse(
            fingerprint=fingerprint,
            candidates=rank_candidates(fingerprint, candidates),
            mode="demo",
            warning=(
                "Live Vertex AI search failed and KiasuCheck switched to demonstration data. "
                f"Diagnostic: {type(exc).__name__}: {str(exc)[:180]}"
            ),
            agent=_demo_trace(rank_candidates(fingerprint, candidates)),
        )


def _demo_trace(candidates):
    score = round(
        sum(candidate.evidence_confidence_score for candidate in candidates[:3])
        / max(1, len(candidates[:3]))
    )
    level = "High" if score >= 80 else "Medium" if score >= 60 else "Low"
    return AgentTrace(
        status="completed",
        iterations=1,
        tools_used=["demo_fixture", "verify_product_identity", "compare_supported_prices"],
        evidence_confidence_score=score,
        evidence_confidence_level=level,
        steps=[
            AgentStep(stage="observe", summary="Loaded the labelled demonstration product."),
            AgentStep(stage="verify", tool="verify_product_identity", summary="Applied the same deterministic identity checks used for live results."),
            AgentStep(stage="recommend", tool="compare_supported_prices", summary="Ranked demonstration offers by identity before price."),
        ],
    )

