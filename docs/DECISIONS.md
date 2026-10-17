# Decisions

Every deviation from [`requirements.md`](../requirements.md), one line each, newest last (spec §2, §19.2).

| Date | Decision | Why |
|---|---|---|
| 2026-10-17 | `requirements.md` is a copy. The source of truth is `projects/ai-builder-cup-bara/requirements-phase/REQUIREMENTS.md` in `faber-eng/shared-context`; a spec change lands there first and is copied here the same day. | One source, so the two cannot drift. |
| 2026-10-17 | The pre-push hook runs `gitleaks git` instead of `gitleaks detect` (§19.5). | gitleaks 8.19 renamed `detect` to `git`; it is the same scan of the commit history. |
| 2026-10-17 | `.secrets/bara.env` holds only `PROJECT`. Model IDs come from `config/models.yaml` (C8). | One place for model IDs. |
