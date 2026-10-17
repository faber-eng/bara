# Decisions

Every deviation from [`requirements.md`](../requirements.md), one line each, newest last (spec §2, §19.2).

| Date | Decision | Why |
|---|---|---|
| 2026-10-17 | `requirements.md` is a copy. The source of truth is `projects/ai-builder-cup-bara/requirements-phase/REQUIREMENTS.md` in `faber-eng/shared-context`; a spec change lands there first and is copied here the same day. | One source, so the two cannot drift. |
| 2026-10-17 | The pre-push hook runs `gitleaks git` instead of `gitleaks detect` (§19.5). | gitleaks 8.19 renamed `detect` to `git`; it is the same scan of the commit history. |
| 2026-10-17 | `.secrets/bara.env` holds only `PROJECT`. Model IDs come from `config/models.yaml` (C8). | One place for model IDs. |
| 2026-10-17 | `infra/setup.sh` creates what can exist before a deploy. Pub/Sub push subscriptions, Cloud Scheduler jobs and the `run.invoker` grants (§15 steps 3 and 4) move to the Cloud Build step (OT-4). | They point at `bara-api` and `bara-jobs`, which do not exist until the first deploy. |
| 2026-10-17 | `setup.sh` also enables `iam` and `cloudresourcemanager` (not in §15 step 1). | The IAM grants in step 3 call these APIs. |
| 2026-10-17 | `bara-jobs` gets `storage.objectAdmin` on the exports bucket only; `bara-api` on the evidence bucket only. | §15 gives no bucket for `bara-jobs`; the jobs write exports and never touch evidence. |
| 2026-10-17 | `scripts/preflight.sh` reads model IDs from `config/models.yaml`; `FAST_MODEL` and `REASONING_MODEL` override them (§15.1 put them in `.secrets/bara.env`). | One place for model IDs (C8). |
| 2026-10-17 | Preflight P2 passed on `ai-builder-cup-511906`: `gemini-3.5-flash` and `gemini-3.1-pro-preview` both return 200 on the `global` endpoint. No fallback needed. | §19.2: every external ID verified with a real call. |
| 2026-10-17 | `data/eval/labels.csv` has a header row with at least `object_path` and `licence`; `object_path` is relative to `gs://$PROJECT-bara-exports/eval/` (for example `photos/001.jpg`). | §15.1 names the fields but not the format; P4 needs one to check. |
| 2026-10-17 | **Cost rule:** the project runs on the Google Cloud free trial, USD 300 of credit. Every resource uses the free tier or the lowest tier. A budget `bara-free-trial-300usd` (5,370,000 IDR, the account currency, at about 17,900 IDR per USD) alerts at 25, 50, 75, 90 and 100%. | A spend overrun ends the trial and stops the demo. |
| 2026-10-17 | Cloud Run (`bara-api`, `bara-jobs`): min instances 0, max instances 3, request-based billing, 1 vCPU and the smallest memory that runs (start at 512 MiB; raise only if ffmpeg needs it). | Scales to zero between demos; free tier covers 2M requests a month. |
| 2026-10-17 | Gemini: during development and tests, `REASONING_MODEL` is set to the fast model, and unit tests never call a model. The Pro model runs only for the agent evals and the recorded demo. | Pro costs several times Flash per token; dev traffic does not need it. |
| 2026-10-17 | BigQuery: on-demand pricing, every query sets `maximum_bytes_billed`, tables are partitioned or clustered by week and cell. The re-ignition training table stays small (cells by events, not pixels). | 1 TB of queries a month is free; BigQuery ML training is billed per TB processed. |
| 2026-10-17 | Cloud Scheduler: 3 jobs, not 4 (§15 step 4). "Publish rankings" runs as the last step of the weekly drying job. | 3 Scheduler jobs per billing account are free. |
| 2026-10-17 | Cloud Build on the default machine type only; Artifact Registry keeps the last 3 images per service; the exports bucket deletes objects after 30 days, except `eval/`. | Free build minutes apply to the default machine; storage stays inside the free 0.5 GB. |
| 2026-10-17 | `apps/web/src/styles/kit.css` is a verbatim copy of shared-context `projects/ai-builder-cup-bara/requirements-phase/design/kit.css`. A change lands there first and is copied here the same day. | One source for the design tokens, so the app and the kit cannot drift. |
||||||| parent of fe23bb1 (wave-0: freeze the contracts in contracts.py and contracts.ts)
| 2026-10-17 | The contracts live at `services/api/contracts.py` (flat, §2), not `services/api/bara/contracts.py` as the Wave 0 TRD wrote. `apps/web/src/lib/contracts.ts` mirrors the shapes the web app reads. | §2 has no `bara/` package under `services/api/`. |
| 2026-10-17 | `tasks/{id}` adds `created_at` and `done_at` (null until done) to the §7 fields. | §9.1 `median_days_to_repair` needs task creation; `tasks_on_time_pct` needs the time a task was done. |
| 2026-10-17 | A §7 field marked `?` is stored as `null`, never omitted. `agent_runs.final_json` is the §6.2 output `{decision, reason, evidence, next_check_at}`, or `null` if the run failed. `bulletins.model` is `null` when `source` is `template`. | One shape for Python and TypeScript; a failed run is still stored for "why the agent did this". |
| 2026-10-17 | `bara-api` pins `google-genai==2.31.0`, `fastapi==0.143.3`, `uvicorn==0.54.0`, `pydantic==2.14.1`, `pyyaml==6.0.3` on Python 3.12 (§4.1); `uv.lock` is committed. `google-adk` is pinned when the agent lands. | §4.1 asks for pinned stable versions, recorded here. |
| 2026-10-17 | Gemini 5xx is retried by the SDK (3 attempts, 500/502/503/504). 404 and 429 are not retried: the gateway calls the fallback model once, and an error from the fallback propagates (§4.1, §14). | A 429 retried on the same model spends the wait the fallback avoids. |
| 2026-10-17 | The client is built with `enterprise=True`, the current name of the `vertexai=True` flag in `google-genai` 2.x (§4.1). | Same Vertex endpoint; `vertexai` is the legacy flag. |
| 2026-10-17 | `git_sha` reaches `/api/health` through the Docker build arg `GIT_SHA` (default `unknown`). `fallback_used` is per instance: true once any model call on that instance has fallen back. | No git in the image; Cloud Run instances do not share memory. |
