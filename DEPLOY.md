# Deploying MoodMix

Two services: the **web app** (Next.js, `web/`, e.g. Vercel) and the **API** (FastAPI, `api.py`, e.g. PXXL via `Dockerfile.api` / `pxxl.toml`).

## API (PXXL or any Docker host)

| Setting | Value |
| --- | --- |
| Memory | **≥ 1 GB RAM** (both models loaded ≈ 525 MB RSS, plus audio decoding headroom) |
| Build | `pip install -r requirements-api.txt && python scripts/fetch_models.py` (downloads the GoEmotions ONNX model, pinned + SHA-256 checked) |
| Start | `uvicorn api:app --host 0.0.0.0 --port $PORT --workers 1 --proxy-headers --forwarded-allow-ips=* --timeout-keep-alive 5` |
| System packages | `ffmpeg`, `libsndfile1` (needed to decode iPhone `.m4a` / Android `.webm` recordings) |

Secrets / env:

| Variable | Required | Notes |
| --- | --- | --- |
| `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` | yes | Spotify app (client credentials). In development mode Spotify caps search at 10 results. |
| `FRONTEND_URL` | yes | Production web origin, e.g. `https://themoodmix.vercel.app` (CORS) |
| `FRONTEND_URLS` | no | Extra comma-separated origins (previews) |
| `FEEDBACK_DB` | recommended | Path on a **persistent volume** (default lives in the container and is lost on redeploy) |
| `FEEDBACK_EXPORT_TOKEN` | optional | Enables `GET /feedback/export` with a Bearer token |
| `ALLOW_EXPLICIT` | no | `1` to allow explicit tracks (filtered out by default) |
| `RATE_LIMIT_PER_MIN` | no | Per-IP limit on `/predict` + `/feedback` (default 30) |
| `ENABLE_DOCS` | no | Leave **unset** in production (`/docs` and `/openapi.json` are off) |

Check: `GET /health` → `{"status":"ok","speech_model_loaded":true,"text_model_loaded":true}` (503 if a model failed to load).

## Web app (Vercel)

| Variable | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | The API's public HTTPS URL (build fails over to an error message if missing) |
| `NEXT_PUBLIC_SITE_URL` | The site's own URL (absolute Open Graph / Twitter image links) |

- HTTPS is required for the microphone (browsers only allow `getUserMedia` on secure origins).
- Security headers, the PWA manifest, icons and share images are built in (`web/next.config.js`, `web/app/manifest.ts`).
- Redeploy after changing any `NEXT_PUBLIC_*` variable (they are inlined at build time).

## After deploying

1. Open the site on a real iPhone (Safari) and an Android phone (Chrome): record a voice clip, type a mood, tap Lift, correct a mood, open history.
2. Run **PageSpeed Insights** on the live URL (mobile). Local Lighthouse runs on this laptop are pessimistic: no GPU (software rendering) and a slow CPU benchmark.
3. Don't register videos using the trailer music with Content ID (Mixkit licence).
