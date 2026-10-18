#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-gen-lang-client-0509152597}"
DEPLOY_REGION="${CLOUD_RUN_REGION:-asia-southeast1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-shopproof}"
MODEL_NAME="${GEMINI_MODEL:-gemini-3.5-flash}"
APP_VERSION="${KIASUCHECK_VERSION:-${SHOPPROOF_VERSION:-0.5.0}}"
GIT_SHA="${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || echo unknown)}"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com \
  --project "${PROJECT_ID}"

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${DEPLOY_REGION}" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_ENTERPRISE=true,GEMINI_MODEL=${MODEL_NAME},KIASUCHECK_DEMO_FALLBACK=false,KIASUCHECK_VERSION=${APP_VERSION},GIT_COMMIT=${GIT_SHA}" \
  --memory 512Mi \
  --cpu 1 \
  --timeout 120 \
  --max-instances 3

