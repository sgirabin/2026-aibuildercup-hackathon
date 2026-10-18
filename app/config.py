from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_version: str = os.getenv("KIASUCHECK_VERSION", os.getenv("SHOPPROOF_VERSION", "dev"))
    git_commit: str = os.getenv("GIT_COMMIT", "unknown")
    cloud_run_revision: str = os.getenv("K_REVISION", "local")
    project_id: str = os.getenv("GOOGLE_CLOUD_PROJECT", "gen-lang-client-0509152597")
    location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
    model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    demo_fallback: bool = os.getenv(
        "KIASUCHECK_DEMO_FALLBACK", os.getenv("SHOPPROOF_DEMO_FALLBACK", "false")
    ).lower() == "true"
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))


settings = Settings()

