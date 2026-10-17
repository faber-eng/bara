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
