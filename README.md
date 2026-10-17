# Bara

A Gemini agent on Google Cloud that ranks drying peat before the dry season, scores where a burned area
may reignite, sends a named person to check, reads their evidence, and escalates to the fire brigade.

Google Cloud AI Builder Cup 2026, Sustainability and Social Impact.

The live link, architecture and eval numbers are added as each wave ships. The full spec is
[`requirements.md`](./requirements.md); every deviation from it is in [`docs/DECISIONS.md`](./docs/DECISIONS.md).

## Layout

| Path | What | Language |
|---|---|---|
| `services/api/` | Cloud Run service: FastAPI, the ADK agent, event handlers | Python 3.12 |
| `services/pipelines/` | Cloud Run Jobs: Earth Engine and BigQuery batch work | Python 3.12 |
| `apps/web/` | Web app on Firebase Hosting: Vite, React, TanStack Router and Query | TypeScript, Bun |
| `config/` | Thresholds, regions and model IDs. Logic reads these, never hard-coded values | YAML |
| `infra/`, `scripts/` | `gcloud` bootstrap, Cloud Build, preflight and smoke checks | bash |

## Set up a clone

```sh
git config core.hooksPath .githooks
mkdir -p .secrets && cp bara.env.example .secrets/bara.env
```

Set `PROJECT` in `.secrets/bara.env`. The pre-push hook runs
[gitleaks](https://github.com/gitleaks/gitleaks/releases), so it must be on your `PATH`. `.secrets/` is
gitignored; deployed services read secrets from Secret Manager only.

## Commits

`wave-N: <what>` (spec §19.9). Cloud Build deploys `main`.
