# Bara: Requirements for the AI Builder Cup 2026 prototype

> Read this file top to bottom before writing code. It is the single source of truth for what we build, how the parts talk to each other, and what "done" means.
> When this file and your own assumptions disagree, this file wins. When this file is wrong about an external fact (a model ID, a dataset ID, an API flag), verify it, fix the code, and add a note to `docs/DECISIONS.md`.

---

## 0. Context in one minute

- **Competition:** Google Cloud AI Builder Cup 2026 (JAPAC), theme **Sustainability & Social Impact**.
- **Deadline:** submission closes **19 Oct 2026, 01:29 (GMT+7)**. Our internal submit target is **18 Oct, 23:00 (GMT+7)**.
- **What we submit:**
  1. A working deployed link on Cloud Run or Firebase.
  2. A public GitHub repo.
  3. A demo video under 3 minutes.
  4. A deck as a PDF.
- **Judging weights:**

  | Criterion | Weight |
  |---|---|
  | Technical Merit & Gen AI Implementation | 40% |
  | Problem Alignment & Impact | 25% |
  | Innovation & Creativity | 25% |
  | User Experience & Solution Design | 10% |

- **Rules that shape the build:**
  - Must use Google AI models (Gemini) or Google agent tooling.
  - Must be deployed on Cloud Run or Firebase.
  - Must be built during the hackathon window.
  - Everything in English.

### The product

**Bara** ("ember" in Indonesian) is a Gemini agent on Google Cloud that prevents peat fires in two moments.

1. **Before the dry season.** It ranks peat areas that are drying out and canal dams that are broken. A named team fixes the worst first and proves it with a photo.
2. **After a fire looks out.** It scores where burned peat may reignite underground, sends a patrol back on schedule, and reads their photos, video and voice notes for smoke or hot ground.

**The loop in both moments:** a risk signal goes to a named person, who must check and send evidence. Gemini reads the evidence. If smoke is found or nobody answers in time, Bara escalates to the fire brigade with an evidence pack.

**Who uses it:**
- **Ops** (a district fire-prevention desk) sees the ranking and the cases, and closes cases.
- **Volunteers, repair teams and patrols** get tasks and send evidence from a phone.
- **The fire brigade** gets escalations with an evidence pack.
- **The public** (villagers, local government, journalists, researchers) sees the risk, the response and the record on a public dashboard with no sign-in, and downloads the data.

**Demo region:** Riau, Indonesia (full flow). **Second region:** Congo Basin peat, Cuvette Centrale (ranking only), to prove it works anywhere. **Any region:** a user draws a polygon and gets a live ranking.

### Why this wins (keep these true in the code)

1. **Gemini does reasoning, not decoration.**
   - Gemini calls tools over Earth Engine and BigQuery.
   - It explains each rank using numbers it actually retrieved.
   - It writes tasks in the volunteer's language.
   - It reads multimodal evidence into structured verdicts.
   - It decides between escalating and reassigning.
2. **Every AI claim is measured.**
   - The drying score is validated against later fires.
   - The re-ignition model reports AUC and precision at top-k.
   - Gemini's photo verdicts are scored on a labelled set.
   - Numbers go in the README and the deck.
3. **Judges can drive it themselves.**
   - A guided tour runs the demo from the deployed link.
   - A "skip ahead" clock makes 48-hour deadlines demoable in seconds.
4. **Open by default.**
   - Anyone can see this week's risk map, how fast broken dams get fixed, and what the agent escalated, without signing in.
   - The ranked cells download as CSV and GeoJSON, and the public API is documented.
   - People stay private: no names, phone numbers, home points, photos or messages are public.
5. **Google Cloud is used deeply and correctly:** Earth Engine, BigQuery (plus Earth Engine in BigQuery), BigQuery ML registered to Vertex AI, Gemini on Vertex AI via ADK, Cloud Run services and jobs, Pub/Sub, Cloud Tasks, Cloud Scheduler, Firestore, Cloud Storage, Firebase Hosting and Auth, Secret Manager, Cloud Build, Cloud Logging and Trace, Google Maps Platform.

---

## 1. Hard constraints

| # | Constraint |
|---|---|
| C1 | All runtime services run on Google Cloud. Frontend on **Firebase Hosting**, backend on **Cloud Run**. |
| C2 | All LLM calls use **Gemini on Vertex AI** (now branded Gemini Enterprise Agent Platform in some docs). No other model providers. |
| C3 | The agent is built with **Agent Development Kit (ADK), Python**. |
| C4 | The repo is public. **No secrets in git.** Secrets live in Secret Manager. The Maps key is restricted by HTTP referrer. |
| C5 | Anything not real is labelled in the UI. Every screen showing sample dams, sample photos or simulated people shows an "Example data" chip. |
| C6 | No em dashes in UI copy. Plain, short English. Indonesian for volunteer-facing text. |
| C7 | A judge must complete the full demo from the deployed link in under 5 minutes, with no sign-up, on desktop or phone. |
| C8 | Model IDs, dataset IDs and regions come from config (`config/*.yaml` and env vars), never hard-coded in logic. |

---

## 2. Repo layout

```
bara/
├── README.md                    # what it is, live link, architecture, eval numbers, how to run
├── requirements.md              # this file
├── docs/
│   ├── ARCHITECTURE.md          # diagram + data flow (keep in sync)
│   ├── DECISIONS.md             # every deviation from this spec, one line each
│   ├── EVAL.md                  # generated by eval scripts
│   └── DEMO_SCRIPT.md           # the 3-minute video script
├── config/
│   ├── app.yaml                 # thresholds, deadlines, languages, feature flags
│   ├── regions.yaml             # AOIs: riau, congo_cuvette, (custom at runtime)
│   └── models.yaml              # Gemini model IDs + locations
├── infra/
│   ├── setup.sh                 # idempotent gcloud bootstrap (APIs, SAs, buckets, topics, queues, datasets)
│   ├── cloudbuild.yaml          # build + deploy api, jobs, web
│   └── firestore.rules
├── services/
│   ├── api/                     # Cloud Run service: FastAPI + ADK agent + event handlers
│   │   ├── main.py
│   │   ├── bara_agent/          # ADK agent package (root_agent)
│   │   │   ├── __init__.py
│   │   │   ├── agent.py
│   │   │   ├── prompts.py
│   │   │   └── tools/           # one file per tool
│   │   ├── routes/              # REST: public, volunteer, ops, brigade, judge, events, internal
│   │   ├── domain/              # case/task state machine, clock, channels
│   │   ├── adapters/            # firestore, bigquery, gcs, pubsub, cloudtasks, earthengine, whatsapp
│   │   ├── evals/               # ADK eval sets (*.test.json)
│   │   ├── tests/
│   │   ├── Dockerfile           # includes ffmpeg
│   │   └── pyproject.toml
│   └── pipelines/               # Cloud Run Jobs: Earth Engine + BigQuery batch work
│       ├── jobs/
│       │   ├── build_grid.py
│       │   ├── drying_score.py
│       │   ├── fire_events.py
│       │   ├── reignition_features.py
│       │   ├── train_reignition.sql
│       │   ├── score_reignition.py
│       │   ├── hotspot_ingest.py
│       │   └── publish_rankings.py
│       ├── ee_lib/              # shared Earth Engine expressions (drying, peat, rain)
│       ├── Dockerfile
│       └── pyproject.toml
├── apps/
│   └── web/                     # Vite + React + TanStack Router/Query, Bun
│       ├── src/routes/          # / (landing+tour), /ops, /v/$volunteerId, /brigade, /area/new
│       ├── src/components/
│       ├── src/lib/             # api client, auth, offline queue, design tokens
│       └── firebase.json
├── data/
│   ├── dams_riau_sample.geojson # hand-mapped sample dams (Example data)
│   ├── scenario_riau.yaml       # seeded demo scenario
│   └── eval/                    # labels.csv + LICENSES.md; the media lives in the exports bucket (15.1 P4)
└── scripts/
    ├── preflight.sh             # P1-P4 facts the plan rests on (15.1)
    ├── seed_scenario.py
    ├── eval_evidence.py         # Gemini verdict accuracy -> BigQuery + docs/EVAL.md
    ├── eval_drying.py           # drying score lift vs later hotspots
    └── smoke_test.sh            # end-to-end check against the deployed URL
```

---

## 3. Architecture

### 3.1 Components

| Component | Google service | Job |
|---|---|---|
| Web app | **Firebase Hosting** | Landing + guided tour, Public dashboard, Ops dashboard, Volunteer chat (PWA), Brigade inbox, Draw-an-area |
| Auth | **Firebase Auth** (anonymous) | Judges get a session instantly. Role switcher in judge mode. |
| API + agent | **Cloud Run** service `bara-api` (Python 3.12, FastAPI, ADK) | REST, agent runs, Pub/Sub push handlers, Cloud Tasks handlers |
| Batch pipelines | **Cloud Run Jobs** `bara-jobs` | Earth Engine computations, exports to BigQuery, model scoring, ranking publish |
| Schedules | **Cloud Scheduler** | Triggers jobs (weekly drying, daily hotspots, daily re-ignition scoring) |
| Per-task deadlines | **Cloud Tasks** queue `task-deadlines` | One scheduled HTTP task per assignment deadline |
| Events | **Pub/Sub** | Decouples detection, assignment, evidence, overdue, escalation |
| Geo compute | **Earth Engine** (Python API, service account, Cloud project registered) | Drying score, peat mask, burn scars, fire history, map tiles |
| Analytics + ML | **BigQuery**, **Earth Engine in BigQuery** (`ST_REGIONSTATS`), **BigQuery ML** registered to **Vertex AI Model Registry** | Cell features, training tables, re-ignition model, eval results |
| LLM | **Gemini on Vertex AI** via `google-genai` and ADK | Agent reasoning, evidence reading, language, escalation briefs |
| Operational state | **Firestore** (Native mode) | Cases, tasks, evidence, messages, rankings snapshot, sim clock |
| Files | **Cloud Storage** | Evidence uploads (signed URLs), exported rasters, eval set |
| Maps | **Google Maps Platform** (Maps JavaScript API via `@vis.gl/react-google-maps`) | Base map, Earth Engine tile overlays, markers |
| Secrets | **Secret Manager** | WhatsApp token, Maps key (server copy), any API keys |
| CI/CD | **Cloud Build** trigger on `main` | Build and deploy api, jobs, web |
| Observability | **Cloud Logging**, **Cloud Trace** (ADK OpenTelemetry) | Structured logs, agent traces for the demo and debugging |

### 3.2 Regions

| Thing | Region | Why |
|---|---|---|
| Cloud Run, Cloud Tasks, Pub/Sub, Cloud Storage | `asia-southeast1` | Close to Indonesia and Singapore judges |
| Firestore | `asia-southeast1` | Same |
| BigQuery dataset `bara` | `US` multi-region | `ST_REGIONSTATS` on Earth Engine assets only works in US |
| Gemini | `global` endpoint | Gemini 3.x preview models are served on `global` |

### 3.3 Event flow

```
Cloud Scheduler ──► Cloud Run Job (EE) ──► BigQuery ──► publish_rankings ──► Firestore rankings
                                                   └──► Pub/Sub hotspot.detected / fire.quiet

Pub/Sub ──push──► bara-api /events/{topic} ──► ADK agent run ──► tools ──► Firestore task + message
                                                                     └──► Cloud Tasks deadline
Volunteer uploads evidence ──► GCS ──► /v/... ──► evidence.received ──► agent: check_evidence
Cloud Tasks deadline ──► /internal/deadline/{taskId} ──► task.overdue ──► agent: escalate or reassign
Every verdict ──► BigQuery bara.checks (labels for the next model version)
```

### 3.4 Design rule: the agent is event-driven and stateless

- Each event (a hotspot, a fire going quiet, evidence, an overdue task, a chat message) starts **one ADK agent run**.
- The run loads the case from Firestore and acts through tools.
- Domain state lives in Firestore, not in ADK sessions. Use the in-memory ADK session service per run.
- Persist the run transcript (tool calls, outputs, final text) to `cases/{id}/agent_runs/{runId}` so the UI can show "why the agent did this".

---

## 4. Configuration

### 4.1 `config/models.yaml`

```yaml
# Verify these IDs in Vertex AI Model Garden in the first hour. If a preview ID 404s, fall back and log it in DECISIONS.md.
reasoning:        # agent brain: ranking explanations, decisions, escalation briefs
  model: gemini-3.1-pro-preview
  location: global
  fallback: gemini-2.5-pro
fast:             # evidence reading, task wording, chat replies, classification
  model: gemini-3.5-flash      # verify exact ID; may carry a -preview suffix
  location: global
  fallback: gemini-2.5-flash
```

- Use `google-genai` (Python) with Vertex AI. Set `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION=global` and `GOOGLE_GENAI_USE_VERTEXAI=True`.
- Also set `GOOGLE_GENAI_USE_ENTERPRISE=True`, since newer ADK docs use it.
- Pin `google-genai` and `google-adk` to the latest stable versions at build time and record them in `docs/DECISIONS.md`.
- Wrap every model call in a function that retries once on the fallback model if the primary returns 404 or 429.

### 4.2 `config/app.yaml`

```yaml
grid_cell_m: 1000
drying:
  wet_baseline_months: [1, 2, 3]       # Jan-Mar wet-season reference
  s1_window_days: 12
  rain_window_days: 30
  weights: { s1_anomaly: 0.45, rain_deficit: 0.30, canal_proximity: 0.15, peat_class: 0.10 }
reignition:
  quiet_days: 3                        # no detection for >= 3 days = "looks out"
  label_window_days: [3, 30]           # new detection within this window = reignited
  label_radius_m: 1000
  recheck_spots_per_fire: 3
  recheck_after_hours: 48
tasks:
  default_deadline_hours: { dam_check: 72, dam_repair: 168, patrol_recheck: 24 }
  human_review_confidence: 0.7         # verdict confidence below this goes to a person
  location_tolerance_m: 300            # evidence GPS must be within this of the task point
languages: { default: id, supported: [id, en, ms, fr] }
judge_mode: { enabled: true, max_resets_per_hour: 20 }
```

### 4.3 `config/regions.yaml`

```yaml
riau:
  name: Riau, Indonesia
  aoi: data/aoi/riau_focus.geojson     # a focus polygon on peat (e.g. parts of Pelalawan / Siak); keep it ~ 3,000-8,000 km² for speed
  timezone: Asia/Jakarta
  language: id
  full_flow: true
congo_cuvette:
  name: Cuvette Centrale peatlands, Congo Basin
  aoi: data/aoi/congo_cuvette_focus.geojson
  timezone: Africa/Brazzaville
  language: fr
  full_flow: false                      # ranking + map only
```

---

## 5. Data and models

> Verify every dataset ID with `ee.data.getInfo(id)` before relying on it. Record the verified IDs in `docs/DECISIONS.md`.

### 5.1 Sources (Earth Engine unless noted)

| Purpose | Dataset | Notes |
|---|---|---|
| Peat mask | `projects/sat-io/open-datasets/GLOBAL-PEATLAND-DATABASE` (Global Peatland Map 2.0, 1 km) | Values 1 = peat dominated, 2 = peat in soil mosaic. License CC BY-NC-SA 4.0. Credit Greifswald Mire Centre in the README and UI footer. |
| Radar moisture proxy | `COPERNICUS/S1_GRD` (IW, VV, descending or ascending; pick one orbit per AOI) | Convert to dB if needed. Apply speckle smoothing (focal median 30 m) before aggregating. |
| Rainfall | `UCSB-CHG/CHIRPS/DAILY` | 30-day sum vs same-period climatology (2000-2025) |
| Fire history (training) | `FIRMS` (MODIS, 1 km, daily, from Nov 2000) | Bands `T21`, `confidence`. Use confidence >= 30. |
| Near-real-time fire | `NASA/LANCE/SNPP_VIIRS/C2` and `NASA/LANCE/NOAA20_VIIRS/C2` | 375 m. Rolling NRT window; use for the 2026 season and live ingest. |
| Burned area | `MODIS/061/MCD64A1` (500 m, monthly) | Burn scars for the "fire marked out" view |
| Canals | BigQuery public `bigquery-public-data.geo_openstreetmap` (ways with `waterway` in canal, ditch, drain) | Verify table names. Compute distance from cell centroid to nearest canal in BigQuery GIS. |
| Admin boundaries | `projects/sat-io/open-datasets/geoboundaries/HPSCGS-ADM1` | Labels and AOI helpers |
| Canal dams | `data/dams_riau_sample.geojson` (hand-mapped by us) | 30-60 points next to OSM canals inside the Riau AOI. Mark `example: true`. |
| Evidence eval set | `data/eval/labels.csv` + `gs://${PROJECT}-bara-exports/eval/` | 40-60 real photos plus 10 voice notes, CC-licensed or our own. `LICENSES.md` lists every source. No synthetic images in the eval set. |

### 5.2 Grid

- **`build_grid` job:** create a 1 km grid over each AOI in Earth Engine (`geometry.coveringGrid`). Keep only cells with peat class 1 or 2.
- Write it to BigQuery `bara.cells(cell_id STRING, region STRING, geom GEOGRAPHY, centroid GEOGRAPHY, peat_class INT64, canal_dist_m FLOAT64)`.
- Fill `canal_dist_m` with a BigQuery GIS join against OSM canals.
- **Bonus Google depth:** compute `peat_fraction` per cell with `ST_REGIONSTATS(geom, 'ee://projects/sat-io/open-datasets/GLOBAL-PEATLAND-DATABASE', 'b1')`. Verify the band name. Show the SQL in the README.

### 5.3 Drying score (before the dry season)

For each cell and each ISO week (2026-W20 to the latest available), the `drying_score` job computes:

- `s1_anom_db`: the median VV over the last `s1_window_days` minus the cell's wet-season median VV for the same year. More negative means drier peat. This is a proxy; never present it as a water-table measurement.
- `rain_deficit_pct`: `1 - (rain_30d / clim_rain_30d)`, clipped to [-1, 1].
- `canal_proximity`: `exp(-canal_dist_m / 1000)`.
- `peat_weight`: 1.0 for class 1, 0.6 for class 2.

Then:
- **Score:** z-score each component within region and week, then `drying_score = 100 * sigmoid(Σ wᵢ · zᵢ)`, using the weights in `app.yaml`.
- **Rank:** rank within region and week.
- **Output:** BigQuery `bara.cell_weekly_drying(cell_id, region, week_start DATE, s1_anom_db, rain_30d_mm, rain_deficit_pct, canal_dist_m, peat_class, drying_score, rank)`.
- **Map tiles:** the API endpoint `/api/tiles/drying?region=&week=` returns an Earth Engine `getMapId` tile URL for the same expression at pixel level. The map then shows a smooth surface, and the list uses cells.

**Validation (`scripts/eval_drying.py`, required):**
- For 2019, 2023 and 2026, for each week, take the top 10% of cells by `drying_score`.
- Compute the share of FIRMS/VIIRS hotspots in the following 1-4 weeks that fell in those cells. That share is the "capture rate".
- Report capture rate and lift (capture rate / 10%) to `bara.eval_drying` and `docs/EVAL.md`.
- This number goes in the deck.

### 5.4 Fire events and re-ignition model (after a fire)

**`fire_events` job:**
- Cluster FIRMS detections per cell into events (consecutive detection days, gaps of 2 days or less).
- An event "goes quiet" on the first day after the last detection when `quiet_days` pass with no detection within `label_radius_m`.
- Output to BigQuery `bara.fire_events(event_id, cell_id, region, start_date, last_detection_date, quiet_date, detection_days, max_t21, mean_confidence)`.

**Label:**
- `reignited = 1` if any detection occurs within `label_radius_m` of the cell between `quiet_date + 3d` and `quiet_date + 30d`.
- `reignited = 0` otherwise.

**`reignition_features` job (Earth Engine to BigQuery):** for each event at `quiet_date`, compute:
- `peat_class`, `peat_fraction`, `canal_dist_m`
- `s1_anom_db` at `quiet_date` (nearest 12-day window)
- Rain in the 7 and 14 days before `quiet_date`, and rain in the 7 days after (allowed: it is a forecastable input; also train a variant without it and report both)
- `detection_days`, `max_t21`, `mean_confidence`
- `month`, `prior_years_burned` (count of years with any detection in the cell, 2001 to year-1)

Write to `bara.reignition_training`.

**Training:**
- Train on Indonesia 2015-2024. Validate on 2025. Test on 2026 events. Use a temporal split only, never random.
- `train_reignition.sql`:

```sql
CREATE OR REPLACE MODEL `bara.reignition_v1`
OPTIONS (
  model_type = 'BOOSTED_TREE_CLASSIFIER',
  input_label_cols = ['reignited'],
  data_split_method = 'CUSTOM',
  data_split_col = 'is_eval',
  auto_class_weights = TRUE,
  enable_global_explain = TRUE,
  model_registry = 'VERTEX_AI',
  vertex_ai_model_id = 'bara_reignition'
) AS
SELECT * EXCEPT(event_id, cell_id, region, quiet_date, split) , split = 'valid' AS is_eval
FROM `bara.reignition_training`
WHERE split IN ('train','valid');
```

- **Evaluation:** report AUC, precision@top-10% and recall@top-10% on the 2026 test events. Compare against a baseline that ranks by `detection_days`. Use `ML.EVALUATE` and `ML.GLOBAL_EXPLAIN`, and write the results to `bara.eval_reignition` and `docs/EVAL.md`.
- **`score_reignition` job:** run daily. For newly quiet events, call `ML.PREDICT`. Write to `bara.reignition_scores(event_id, cell_id, quiet_date, p_reignite, top_features JSON)`. Publish `fire.quiet` with the top `recheck_spots_per_fire` cells.
- **Learning loop:** every patrol verdict lands in `bara.checks`. A view `bara.reignition_training_v2` unions field labels (smoke or hot ground found = 1) with satellite labels, so the next season's model trains on both. Show this view in the README. Do not retrain on the tiny demo set.

### 5.5 Rankings snapshot

The `publish_rankings` job:
- Copies the latest week's top 200 cells per region, with all components, into Firestore `rankings/{region}/cells/{cellId}`.
- Copies the top 50 dams by risk, where dam risk is the drying score of its cell plus its last known state, into `rankings/{region}/dams/{damId}`.
- The dashboard reads Firestore only, so it stays fast.
- Then calls `write_bulletin(region, week)` (6.6) so the public bulletin is ready when the week's ranking is.

---

## 6. The agent (ADK)

### 6.1 Shape

- **`root_agent` ("bara_coordinator")** uses the `reasoning` model. It receives one event and the case context, decides, and acts through tools.
- **`evidence_reader`** is not a sub-agent. It is a direct `google-genai` call inside the `check_evidence` tool, on the `fast` model with a strict response schema. This keeps verdicts deterministic and cheap.
- **`messenger`** is a direct `fast` call inside `assign_task` and `send_message`. It writes short, local-language text.

### 6.2 System instruction (put in `prompts.py`, keep it tight)

The instruction must say:

1. You coordinate peat-fire prevention for one region. You act only through tools.
2. Every number you state must come from a tool result in this run. Cite the tool name in the `evidence` field of your final output.
3. You never close a fire case. Only a person can close one.
4. If a verdict's confidence is below the threshold, or the evidence location is inconsistent, request human review.
5. When a task is overdue:
   - Escalate if risk is high (drying_score ≥ 80, or p_reignite ≥ 0.5, or smoke was ever reported in the case).
   - Otherwise reassign once to the next nearest available volunteer.
   - Escalate if it is overdue a second time.
6. Write to volunteers in their language, in at most 3 short sentences: where, by when, what to send.
7. Output a final JSON object: `{decision, reason, evidence: [tool names], next_check_at}`.

### 6.3 Tools (each one is a Python function with type hints and docstrings; ADK builds the schema)

| Tool | Input | Does | Output |
|---|---|---|---|
| `rank_areas(region, week?, limit=10)` | region | Reads Firestore rankings (or BigQuery if a week is given) | list of `{cell_id, drying_score, rank, components}` |
| `get_area_facts(cell_id)` | cell | BigQuery: components, 8-week trend, rain, canal distance, nearby dams, past fires, past checks | facts dict |
| `get_fire_context(event_id)` | event | Fire event, `p_reignite` per cell, top features, burn scar link | dict |
| `find_people(cell_id, role, k=3)` | cell, role | Nearest available volunteers or teams (Firestore, haversine) | list |
| `assign_task(case_id, assignee_id, task_type, target, deadline_hours, instructions_hint)` | | Creates `tasks/{id}`, writes the localized message via `fast`, delivers through channels, creates a Cloud Tasks deadline | `{task_id, deadline_at, message}` |
| `check_evidence(task_id, evidence_id)` | | Loads media from GCS, runs the evidence reader, runs the location check, stores the verdict | verdict (6.4) |
| `request_human_review(case_id, reason)` | | Flags the case in the Ops review queue | ok |
| `escalate(case_id, reason)` | | Builds the evidence pack, writes the brigade brief via `reasoning` (id + en), delivers to the brigade inbox and channels, publishes `case.escalated` | `{escalation_id}` |
| `schedule_recheck(case_id, cell_id, after_hours)` | | Creates a future patrol task via Cloud Tasks | ok |
| `explain_rank(cell_id)` | | Calls `get_area_facts`, then has `reasoning` write 2-3 sentences citing the numbers. Stored on the cell for the UI. | `{text, cited: {...}}` |
| `run_area_ranking(geojson)` | polygon ≤ 2,500 km² | Runs the drying expression on the fly in Earth Engine for a drawn area (current week). Returns the top cells. | list + tile URL |

### 6.4 Evidence verdict schema (response_schema, strict)

```json
{
  "subject": "canal_dam | burned_peat | smoke_scene | other",
  "dam_state": "intact | damaged | broken | overtopped | not_applicable | unknown",
  "smoke": "none | wisps | plume | unknown",
  "hot_ground_signs": "none | possible | clear | unknown",
  "open_flame": "yes | no | unknown",
  "transcript": "string (voice notes only, original language)",
  "transcript_en": "string",
  "reasons": ["short visual or audio cues, max 4"],
  "confidence": 0.0,
  "needs_human": false
}
```

**Media handling:**
- Images: JPEG or PNG, resized server-side to a max of 1600 px.
- Video: MP4 or MOV, max 30 s.
- Audio: the browser records `audio/webm`. Transcode with **ffmpeg** to FLAC or MP3 before sending to Gemini (WebM is not a supported Gemini audio type). The api Dockerfile must install ffmpeg.

**Location check (in code, not by the model):**
- Read EXIF GPS (Pillow), falling back to the device geolocation sent with the upload.
- `location_ok = distance(task.target, evidence.point) <= location_tolerance_m`.
- If false, set `needs_human = true` and give the reason "location mismatch".

**Caching:** cache verdicts by `sha256(media)` plus prompt version in Firestore `verdict_cache`, so judge-mode replays are instant. The first call is always live.

### 6.5 Agent evals (required)

- ADK eval sets live in `services/api/evals/*.test.json`. There must be at least 8 cases:
  - dam broken leads to a repair team being assigned
  - dam intact leads to the case being closed for the season by a person (the agent must not close it)
  - low-confidence verdict leads to human review
  - overdue on a high-risk case leads to escalation
  - overdue on a low-risk case leads to reassignment
  - second overdue leads to escalation
  - smoke wisps on a recheck lead to escalation
  - location mismatch leads to human review
- Run with `adk eval`. Put the pass rate in `docs/EVAL.md`.
- `scripts/eval_evidence.py` runs `check_evidence` over `data/eval/labels.csv`. It reports accuracy per field and a confusion matrix for `dam_state` and `smoke`, plus latency p50 and p95. It writes to `bara.eval_evidence` and `docs/EVAL.md`.

### 6.6 Public bulletin

A weekly plain-language summary for the public dashboard, in Indonesian and English.

- `write_bulletin(region, week)` is a direct `fast` call, not an agent run. It runs after `publish_rankings`, after `/judge/reset` and after `/judge/trigger`.
- **Input:** the `public_summary` for the region and week (9.1). Nothing else, so the model cannot cite a number the public cannot see.
- **Response schema:** `{text_id, text_en, cited: [{field, value}]}`. At most 4 sentences per language.
- **Check in code:** every `cited.value` must equal `public_summary[field]`, and every number in the text must appear in `cited`. If either check fails, retry once, then store a fixed template text filled from the summary and set `source: template`.
- **Store:** `bulletins/{region}_{week}` with `text_id, text_en, cited, source: gemini|template, model, prompt_version, created_at`.
- **Eval:** add 3 cases to `scripts/eval_bulletin.py`: a quiet week, a week with escalations, a week with a summary field at zero. Report the citation check pass rate in `docs/EVAL.md`.

---

## 7. Domain model (Firestore)

```
regions/{regionId}            name, aoi, timezone, language, full_flow
volunteers/{id}               name, role: volunteer|repair_team|patrol, region, home: GeoPoint, language, channels: {web: true, whatsapp?: "+62..."}, available: bool, example: true
contacts/{id}                 brigade/BPBD contacts: name, org, channels, region, example: true
dams/{id}                     point, canal_osm_id?, region, last_state, last_checked_at, example: true
cases/{id}                    type: dam_risk|reignition|hotspot, region, cell_id, dam_id?, event_id?, status (see 7.1), risk: {drying_score?, p_reignite?}, opened_at, closed_by?, closed_at?, history_flags: {smoke_seen: bool}
cases/{id}/agent_runs/{runId} trigger, tool_calls[{name,args,result_summary,ms}], final_json, model, started_at, ms
tasks/{id}                    case_id, type: dam_check|dam_repair|patrol_recheck, assignee_id, target: GeoPoint, deadline_at, status: open|done|overdue|reassigned|cancelled, cloud_task_name, attempt
evidence/{id}                 task_id, case_id, kind: photo|video|audio, gcs_uri, sha256, point?, captured_at, verdict?, location_ok, uploaded_by
messages/{id}                 thread: volunteer|brigade|ops, to_id, case_id, lang, text, text_en, channel, created_at, delivered
escalations/{id}              case_id, contact_id, brief_id, brief_en, pack: {photos[], map_url, timeline[]}, created_at, acknowledged_at?
rankings/{region}/cells/{id}  snapshot (5.5) + explanation?
rankings/{region}/dams/{id}
settings/clock                offset_seconds (sim clock), updated_by
verdict_cache/{hash}          verdict, model, prompt_version
bulletins/{region}_{week}     text_id, text_en, cited[{field,value}], source: gemini|template, model, prompt_version, created_at
events/{id}                   audit log of every Pub/Sub event processed (idempotency key)
```

### 7.1 Case state machine

```
open ──assign──► assigned ──evidence──► reviewing ──verdict──► resolved_pending_human ──person closes──► closed
   │                │                         └─needs_human──► human_review ──person decides──► (assigned | escalated | closed)
   │                └─overdue──► overdue ──agent──► (reassigned → assigned) | escalated
   └─smoke/high risk──────────────────────────────────────────────► escalated ──brigade acks──► monitoring ──recheck──► assigned
```

- Transitions live in `domain/case_machine.py` with unit tests for every edge.
- Illegal transitions raise errors.
- **Idempotency:** every Pub/Sub handler checks `events/{messageId}` before acting.

### 7.2 Simulated clock

- All time reads go through `domain/clock.now()`, which returns `utcnow() + settings/clock.offset_seconds`.
- `POST /api/judge/advance {hours}` increases the offset, then runs `sweep_due()`. The sweep finds tasks with `deadline_at <= now()` and `status == open` and processes them exactly as the Cloud Tasks handler would. This is what makes 48-hour deadlines demoable.
- Real deadlines still use Cloud Tasks. Both paths call the same `handle_deadline(task_id)`.

---

## 8. Events (Pub/Sub)

All messages are JSON with `{type, id, occurred_at, region, payload}`. Push subscriptions go to `bara-api` with OIDC auth (service account `bara-pubsub-invoker`).

| Topic | Producer | Payload | Consumer |
|---|---|---|---|
| `hotspot.detected` | `hotspot_ingest` job | `{cell_id, lat, lon, frp?, confidence, source}` | agent: open or attach a `hotspot` case |
| `fire.quiet` | `score_reignition` job | `{event_id, cells:[{cell_id, p_reignite, top_features}]}` | agent: open a `reignition` case, schedule rechecks |
| `drying.ranked` | `publish_rankings` job | `{region, week, top_cells:[...], top_dams:[...]}` | agent: open `dam_risk` cases for the top N dams without an open case |
| `evidence.received` | api upload route | `{evidence_id, task_id, case_id}` | agent: `check_evidence`, then decide |
| `task.overdue` | deadline handler | `{task_id, case_id, attempt}` | agent: escalate or reassign |
| `case.escalated` | `escalate` tool | `{case_id, escalation_id}` | notifier: channels + brigade inbox |

Use a dead-letter topic `bara.dlq` with max 5 delivery attempts.

---

## 9. API (FastAPI on Cloud Run, all under `/api`)

Auth: a Firebase ID token in `Authorization: Bearer`, verified with `firebase-admin`. The role comes from custom claims or, in judge mode, from `X-Bara-Role` set by the role switcher.

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/health` | public | liveness, model IDs in use, git sha |
| GET | `/regions` | public | list regions |
| GET | `/rankings/{region}?week=` | ops | cells + dams + explanations |
| GET | `/tiles/{layer}?region=&week=` | public | EE tile URL template for `drying`, `peat`, `burn_scars`, `reignition` |
| GET | `/cells/{cellId}` | ops | facts + trend + explanation (calls `explain_rank` if missing) |
| POST | `/areas/rank` | ops | body: GeoJSON polygon; runs `run_area_ranking` (≤ 2,500 km², 60 s timeout) |
| GET | `/cases?region=&status=` | ops | case list |
| GET | `/cases/{id}` | ops | case + tasks + evidence + agent runs + timeline |
| POST | `/cases/{id}/close` | ops | a person closes (records `closed_by`) |
| POST | `/cases/{id}/review` | ops | a person resolves human review: `{action: assign|escalate|close, note}` |
| GET | `/v/{volunteerId}/inbox` | volunteer | tasks + messages |
| POST | `/v/{volunteerId}/uploads` | volunteer | returns a V4 signed PUT URL for GCS + `evidence_id` |
| POST | `/v/{volunteerId}/evidence/{evidenceId}/complete` | volunteer | marks the upload done with `{point?, captured_at}` and publishes `evidence.received` |
| POST | `/v/{volunteerId}/chat` | volunteer | free text to the agent ("I can't reach it", "road flooded"); the agent replies |
| GET | `/brigade/{contactId}/inbox` | brigade | escalations |
| POST | `/brigade/escalations/{id}/ack` | brigade | acknowledge, which moves the case to monitoring |
| POST | `/judge/reset` | judge | reseed the scenario, reset the clock (rate-limited) |
| POST | `/judge/advance` | judge | `{hours}`, then sweep |
| POST | `/judge/trigger` | judge | `{event: drying.ranked|fire.quiet|hotspot.detected}` from the seeded scenario |
| POST | `/events/{topic}` | Pub/Sub OIDC | push handler |
| POST | `/internal/deadline/{taskId}` | Cloud Tasks OIDC | deadline handler |
| POST | `/webhooks/whatsapp` | Meta signature | inbound WhatsApp messages and media |
| GET | `/public/{region}/summary?week=` | public | the week's headline numbers (9.1) |
| GET | `/public/{region}/cells?week=&limit=50` | public | ranked cells: `cell_id`, centroid, score, rank, rank change, components |
| GET | `/public/{region}/dams` | public | dam point, `last_state`, `last_checked_at`, open repair due date |
| GET | `/public/{region}/record?limit=50` | public | the response record (9.1), newest first |
| GET | `/public/{region}/bulletin?week=` | public | the stored bulletin (6.6) |
| GET | `/public/{region}/export.{csv\|geojson}?week=` | public | all scored cells for the week, with a license and credits header |

### 9.1 Public endpoints

- **No auth.** Rate limit 60 requests per minute per IP. `Cache-Control: public, max-age=300`.
- **Serializers are allow-lists.** A public response is built field by field in `api/public/serializers.py`, never from a whole Firestore document. A public response never contains a person's name, ID, phone number, home point or language, an evidence URL or thumbnail, message text, a brigade contact, or agent run detail.
- **Location:** a case is shown only as its `cell_id` (the 1 km grid cell), never as a task target or evidence point. Dams are public infrastructure and keep their point.
- **`public_summary`** for a region and week, computed in `domain/public_summary.py`:
  - `high_risk_cells`: cells with `drying_score` ≥ 80
  - `dams_broken`: dams whose `last_state` is `broken` or `damaged`
  - `cases_open`, `cases_escalated`, `cases_closed` in the week
  - `median_days_to_repair`: from a `dam_repair` task's creation to the verdict `dam_state: intact`, closed cases only
  - `tasks_on_time_pct`: tasks done before `deadline_at` over tasks due in the week
  - `data_as_of`: the date of the latest Sentinel-1 pass used, and the ranking run time
- **Response record:** one line per case transition, in plain words: what was found, in which cell, what happens next and by when. Example: "Dam reported broken in riau-0412. Repair due 28 Jul." It is written from the case state and task, not by Gemini.
- **Export license:** the peat mask is CC BY-NC-SA 4.0, so the export carries CC BY-NC-SA 4.0 and the source credits from 5.1.

**Streaming:** `GET /cases/{id}/stream` (SSE) streams agent run steps live. The UI shows the agent thinking through tool calls during the demo. The web app can use Firestore listeners for everything else.

---

## 10. Channels

- **Web chat (primary).** It is part of the PWA, and judges use it.
- **WhatsApp Cloud API (secondary, for the video).**
  - Use the Meta test number.
  - Outbound: the first message to a user is the approved template; free text is allowed after the user replies within 24 h.
  - Inbound media is downloaded via the Graph API and pushed through the same evidence path.
  - Feature flag `channels.whatsapp`. The app must work fully with it off.
- **Brigade inbox.** A web view. Escalations also go to WhatsApp if a brigade test number is configured.
- **Channel interface:** `domain/channels.py` defines `send(to, text, lang, attachments)`. Implement `WebChannel` (writes `messages`) and `WhatsAppChannel`.

---

## 11. Web app

### 11.1 Stack

- Vite, React 18, TypeScript, TanStack Router and TanStack Query; Bun as the package manager.
- `@vis.gl/react-google-maps`, with Earth Engine tiles added as `google.maps.ImageMapType` overlays.
- Firebase JS SDK: Auth (anonymous) and Firestore listeners.
- A PWA with a service worker. An offline evidence queue in IndexedDB, with retries when back online.

### 11.2 Design system: Arva (landing, app and deck)

One style for every surface, adapted from arva.com: a warm cream canvas, a deep forest green, pastel card tiles and one lime accent. The full guideline is `design/kit.html`, built on the shared tokens and parts in `design/kit.css`. The landing prototype at `design/index.html` uses the same file.

```css
:root {
  --forest-ink:#07503f; --vivid-lime:#e8fe85; --bone:#f1efdf; --pure-white:#ffffff;
  --charcoal:#212529; --graphite:#353535; --pewter:#646464; --moss:#c3cda7;
  --sky-card:#b2cee7; --peach-card:#fceace; --sage-card:#e6ecd5; --ash-gray:#efefef;
  --risk-1:#fceace; --risk-2:#f6cf9f; --risk-3:#e9a066; --risk-4:#c4612a; --risk-5:#8a3a12;
  --serif:'Newsreader', Georgia, serif; --font: Inter, system-ui, sans-serif;
}
```

- **Canvas and surfaces.** The page background is always bone, never pure white. Cards are pure white or one pastel tile (sky, peach, sage, ash), one colour per card. Header, dark bands and footer are solid forest ink. No shadows: depth comes from a change of surface colour.
- **Accent.** Vivid lime only on the top announcement strip, the "Example data" chip and small highlights. No other saturated colour, except the map risk ramp.
- **Type.** Headlines in Newsreader (free substitute for Arva's Reckless) at weight 300, letter-spacing -0.012em, 24 px and up only. Everything functional and all body text in Inter. Body text is left-aligned, max 60ch.
- **Shape.** Buttons and nav pills are fully round (radius 100 px): forest fill for primary, 1px graphite or white outline for secondary. Inputs 33 px radius. Cards 20 px, large photo cards 30 px.
- **Imagery.** Real, licensed field and satellite photos, full-bleed where possible, credited. No illustrations. A dark gradient behind white text on photos, so text keeps AA contrast.
- **Map risk ramp.** A sequential warm ramp `--risk-1` (peach) to `--risk-5` (deep ember), only on map layers and their legend. A legend is always visible. Do not rely on colour alone: the list carries the numbers.
- **Contrast (checked).** Charcoal on bone 13.3:1. White on forest 9.4:1. Lime on forest 8.5:1. Pewter `#646464` on bone 5.1:1, on sage 4.9:1, on peach 5.0:1. Arva's original pewter `#6d6d6d` is 4.47:1 on bone and fails AA, so it is darkened here. On the sky tile, secondary text uses graphite, never pewter (3.6:1).
- WCAG AA contrast. All interactive targets are at least 44 px. Full keyboard navigation. Visible focus ring: 2px forest outline, offset 3px; lime on forest surfaces.

### 11.3 Screens

1. **`/` Landing and tour.**
   - A one-line problem statement, a 30-second "what you'll see" summary, and two buttons: "Start the guided tour" and "Explore freely".
   - The tour is a docked step card that drives the demo script in section 13: it navigates, switches roles, triggers events and advances the clock, with a "Next" button.
2. **`/public` Public dashboard (no sign-in).**
   - Region switcher (Riau, Congo) and week selector.
   - Read-only map: drying, burn scars, re-ignition risk, dams coloured by `last_state`, cells with an open case outlined.
   - A stat strip from `public_summary`: high-risk cells, dams broken, open cases, median days to repair, tasks on time. Each with its unit, source tooltip and `data_as_of`.
   - The Gemini bulletin in Indonesian and English, with the Gemini chip and a "How this was written" note: model, prompt version, the cited fields. A template bulletin is labelled as such.
   - The response record feed.
   - Open data: CSV and GeoJSON download for the week, a link to the public API, the license and credits.
   - Example data is labelled. Congo shows ranking only and says so.
3. **`/ops` Ops dashboard.**
   - Region switcher (Riau, Congo, + Draw an area).
   - Week slider (2026-W20 to the latest), which animates the drying surface.
   - Map layers: drying, peat, burn scars, re-ignition risk, dams, live cases.
   - **Right panel tabs:**
     - **Ranked areas:** score, rank change, components bars, Gemini explanation with cited numbers.
     - **Dams:** risk, last state, last photo.
     - **Cases:** status chips, deadline countdown on the sim clock.
     - **Review queue.**
   - **Case drawer:** timeline; evidence thumbnails with verdict fields; the "Agent runs" list showing each tool call, its result summary and timings; Close and Review actions.
4. **`/v/$volunteerId` Volunteer PWA (phone-first).**
   - A chat thread in Indonesian with an English toggle.
   - Task cards: map pin, deadline, "what to send".
   - Big buttons: Take photo, Record voice note, Record video.
   - Upload progress, an offline queue badge, the verdict summary returned in plain words.
   - A free-text reply to the agent.
5. **`/brigade` Brigade inbox.**
   - Escalation cards: brief (id/en), photo, mini-map, timeline, Acknowledge button.
6. **`/area/new` Draw an area.**
   - Draw a polygon anywhere on Earth (max 2,500 km²), then "Rank this area".
   - Shows a progress state, then the top cells and the tile layer.
   - Shows a note when the area has no mapped peat.
7. **Judge bar** (always visible in judge mode, top right):
   - Role switcher (Ops, Volunteer Ari, Repair team Sari, Patrol Dedi, Brigade Pekanbaru).
   - Sim clock with "+6h", "+24h" and "+48h" buttons.
   - "Reset scenario".
   - All example people are fictional and labelled.

### 11.4 UX rules

- Every number on screen has a unit and a source tooltip.
- Every AI output shows "Gemini" plus confidence, and a "Why?" that opens the agent run.
- Empty, loading and error states are designed, not left blank.
- The volunteer UI works on a 360 px wide phone on a slow connection. Compress images client-side to 1600 px, JPEG quality 0.8.

---

## 12. Seeded scenario (`data/scenario_riau.yaml`)

The scenario is deterministic, and `POST /api/judge/reset` restores it in under 10 seconds. It contains:

- **Region and time:** region `riau`, sim start `2026-07-20T08:00+07:00` (early dry season).
- **People:**
  - 6 volunteers, 2 repair teams and 2 patrols, with homes spread around the AOI and Indonesian names.
  - 1 brigade contact ("Manggala Agni Daops Pekanbaru (example)").
  - All marked example.
- **Dams:** 40 dams from `dams_riau_sample.geojson` with prior states. 3 dams sit in top-10 cells: 1 broken, 1 damaged, 1 intact.
- **Evidence fixtures** (real, licensed photos from the eval set, 15.1 P4):
  - a broken-dam photo
  - an intact-dam photo
  - a burned-peat photo with smoke wisps
  - a clear burned-peat photo
  - an Indonesian voice note: "Sekatnya jebol di sisi kiri, air kanal sudah turun"
- **A 2026 fire event** from real VIIRS data inside the AOI, with `quiet_date` set to sim day 10. It has 3 high-`p_reignite` cells.
- **Pre-computed state:** rankings for weeks W20 to W40, so the slider animates without live compute.

---

## 13. The demo the product must support (maps to the video)

| Time | Beat | What happens in the product |
|---|---|---|
| 0:00 | The world | Landing page. One line on peat carbon and Indonesia 2026. Open `/public` Riau: anyone sees this week's risk, the response record and the Gemini bulletin. |
| 0:20 | Drying | `/ops` Riau. Slide W24 → W34; the drying surface spreads. The ranked list updates. Open the #1 cell: Gemini's explanation cites the S1 anomaly, rain deficit and canal distance. |
| 0:50 | Assign | Trigger `drying.ranked`. The agent run streams: `rank_areas` → `get_area_facts` → `find_people` → `assign_task`. Volunteer Ari's phone view gets an Indonesian task. |
| 1:15 | Evidence | As Ari, upload the broken-dam photo plus the voice note. Verdict: `dam_state: broken`, transcript shown, confidence 0.9. The agent assigns repair team Sari with a 7-day deadline. |
| 1:40 | After the fire | Trigger `fire.quiet`. The map shows the burn scar and 3 re-ignition cells with `p_reignite` and top features. The agent schedules a patrol recheck in 48h. |
| 2:00 | Smoke, no answer | +48h. Patrol Dedi uploads the smoke-wisps photo: `smoke: wisps`. Escalation is created. Then show a second case where nobody answered: +24h, overdue, high risk, escalated. The brigade inbox shows the brief in Indonesian and English with photo, map and timeline. |
| 2:35 | Anywhere | Switch to Congo: ranking + map. Or draw an area anywhere and rank it live. |
| 2:50 | Proof | The EVAL panel: drying lift, re-ignition AUC and precision@10%, Gemini verdict accuracy, ADK eval pass rate. |

---

## 14. Non-functional requirements

| Area | Requirement |
|---|---|
| Latency | Dashboard first paint < 2 s on broadband. Evidence verdict < 10 s p95 for photos, < 15 s for voice notes. Agent decision after an event < 20 s p95. |
| Reliability | Pub/Sub handlers are idempotent. Retries with backoff on Gemini 429 and 5xx. Dead-letter topic. Cloud Run min instances 1 for `bara-api` during judging (19 Oct to 6 Nov). |
| Security | Firestore rules: clients read only their own volunteer docs or ops data in judge mode; all writes go through the API. Signed URLs expire in 15 min, max 25 MB. Secrets only in Secret Manager. CORS limited to the Hosting domain. |
| Privacy | Example people only. No real phone numbers in the repo. Strip EXIF before storing thumbnails. Public endpoints use allow-list serializers (9.1) and never return person data, evidence media or messages. |
| Cost | Budget alert on the project. Verdict cache. `run_area_ranking` capped at 2,500 km² and 10 runs per hour per user. |
| Observability | Structured JSON logs with `case_id`, `task_id` and `run_id`. ADK traces to Cloud Trace. A `/api/health` page shows model IDs and the version. |
| Accessibility | WCAG 2.1 AA. Alt text on evidence thumbnails (from the verdict reasons). Language toggle. |
| Testing | `pytest`: the case machine (every transition), clock and sweep, channel adapters (mocked), location check, schema validation, public serializers (assert no private field in any `/public` response), `public_summary` math, bulletin citation check. Web: Playwright smoke test of the tour. `scripts/smoke_test.sh` runs against the deployed URL. |

---

## 15. Infrastructure bootstrap (`infra/setup.sh`, idempotent)

1. Enable the APIs: run, cloudbuild, artifactregistry, aiplatform, earthengine, bigquery, bigquerystorage, pubsub, cloudtasks, cloudscheduler, firestore, storage, secretmanager, firebase, firebasehosting, identitytoolkit, maps-backend, cloudtrace, logging.
2. **Register the Cloud project for Earth Engine** (noncommercial). Do this first; everything Earth Engine depends on it.
3. Create the service accounts and grant roles:
   - **`bara-api`:** aiplatform.user, datastore.user, storage.objectAdmin (evidence bucket), pubsub.publisher, cloudtasks.enqueuer, bigquery.dataEditor + jobUser, earthengine.writer, secretmanager.secretAccessor, iam.serviceAccountTokenCreator (on itself, for signed URLs).
   - **`bara-jobs`:** earthengine.writer, bigquery.dataEditor + jobUser, datastore.user, pubsub.publisher, storage.objectAdmin, serviceusage.serviceUsageConsumer.
   - **`bara-pubsub-invoker`** and **`bara-tasks-invoker`:** run.invoker on `bara-api`.
4. Create the resources:
   - **Buckets:** `${PROJECT}-bara-evidence` (uniform access, CORS for PUT from the Hosting origin) and `${PROJECT}-bara-exports`.
   - **BigQuery:** dataset `bara` (US).
   - **Firestore:** Native mode, `asia-southeast1`.
   - **Pub/Sub:** the topics in section 8, plus push subscriptions with OIDC and the DLQ.
   - **Cloud Tasks:** queue `task-deadlines`.
   - **Cloud Scheduler jobs:**
     - drying weekly (Mon 01:00 WIB)
     - hotspots daily (06:00 WIB)
     - reignition scoring daily (06:30 WIB)
     - publish rankings after drying
5. Create the Firebase project link, a Hosting site, rewrites `/api/**` → Cloud Run `bara-api` (`asia-southeast1`), and Anonymous Auth on.
6. Create a Maps JavaScript API key restricted to the Hosting domains and localhost.
7. Create the Cloud Build trigger on `main`: test → build images → deploy `bara-api` → deploy/update jobs → build web → `firebase deploy --only hosting`.

### 15.1 Preflight checks (`scripts/preflight.sh`)

Four facts the plan rests on. Run each with the `gcloud` CLI before the wave that needs it, and again after any change to the project. `scripts/preflight.sh` runs all four, prints `PASS` or `FAIL` per check, and exits non-zero if any check fails. A failed check follows its row in section 18.

**Inputs.** `PROJECT`, `FAST_MODEL`, `REASONING_MODEL` and the fallbacks come from `.secrets/bara.env` on the engineer's machine. That file is gitignored and never committed (C4). Model IDs must match `config/models.yaml` (4.1). Deployed services read secrets from Secret Manager only.

| # | Check | Needed by | Command | Pass |
|---|---|---|---|---|
| P1 | Earth Engine is registered for the project | Wave 0 | `curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "x-goog-user-project: $PROJECT" "https://earthengine.googleapis.com/v1/projects/$PROJECT/algorithms"` | `200`. A `403` means the project is not registered or the API is off. |
| P2 | Each Gemini model ID answers on Vertex (`global`) | Wave 0 | For `$FAST_MODEL` and `$REASONING_MODEL`: `curl -s -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" -H 'Content-Type: application/json' -d '{"contents":[{"role":"user","parts":[{"text":"ping"}]}]}' "https://aiplatform.googleapis.com/v1/projects/$PROJECT/locations/global/publishers/google/models/$MODEL:generateContent"` | `200` for both. A `404` on a primary ID: test the fallback, set it in `config/models.yaml`, log it in `docs/DECISIONS.md`. |
| P3 | Enough re-ignition positives to train | Before `train_reignition.sql` | `bq query --project_id=$PROJECT --use_legacy_sql=false --format=csv "SELECT COUNTIF(reignited = 1) AS positives FROM bara.reignition_training WHERE split = 'train'"` | `positives >= 300`. |
| P4 | The evidence eval set is complete | Before `scripts/eval_evidence.py` | `gcloud storage ls "gs://$PROJECT-bara-exports/eval/photos/" \| wc -l` and `gcloud storage ls "gs://$PROJECT-bara-exports/eval/voice/" \| wc -l`, and every file listed in `data/eval/labels.csv` exists in the bucket | 40 to 60 photos and at least 10 voice notes, each with a licence in `labels.csv`. |

- The eval media lives in the exports bucket, not in git. `data/eval/labels.csv` holds the labels, the object path and the licence for each file.
- `preflight.sh` uses only `gcloud`, `bq` and `curl`, so it runs on any machine with the Cloud SDK and in Cloud Build.
- Record each run's result in `docs/DECISIONS.md` when it changes a model ID, a label window or the eval set.

---

## 16. Build order (everything gets built; this is sequence, not scope)

Times are GMT+7. Each wave ends with a deploy to the live URL.

### Wave 0: Foundations (17 Oct, until 13:00)
- `infra/setup.sh` run, `scripts/preflight.sh` P1 and P2 pass (15.1), hello-world `bara-api` and web deployed via Cloud Build.
- **Done when:** `/api/health` on the Hosting URL returns model IDs.

### Wave 1: Thin end-to-end (17 Oct, until 22:00)
- Grid + drying score for Riau (current week), rankings snapshot, `/ops` map + list.
- Agent with `rank_areas`, `get_area_facts`, `find_people`, `assign_task`, `check_evidence`, `escalate`.
- Volunteer PWA photo upload, verdict, brigade inbox.
- Sim clock + sweep. Seeded scenario + reset.
- **Done when:** the demo beats 0:20 to 2:00 work on the deployed URL, ugly is fine.

### Wave 2: Depth (18 Oct, until 13:00)
- Fire events + re-ignition training + scoring + `fire.quiet` flow.
- Weekly history and the slider.
- `explain_rank` with citations. Voice notes (ffmpeg) and video.
- Location check, human review queue, reassignment logic, SSE agent run streaming.
- Congo region. Draw-an-area.
- Public dashboard: `/public` page reusing the ops map read-only, `public_summary`, the cells, dams and record endpoints, export.
- WhatsApp channel behind a flag.

### Wave 3: Proof and polish (18 Oct, until 17:00 code freeze)
- `eval_drying`, `eval_evidence`, ADK evals, re-ignition metrics, the EVAL panel and `docs/EVAL.md`.
- `write_bulletin` with the citation check and `eval_bulletin`.
- The guided tour. Empty, loading and error states. Accessibility pass. Smoke test green. README with the live link, architecture and eval numbers.

### Wave 4: Submission (18 Oct, 17:00 to 23:00)
- Record the video from the live URL (section 13).
- Update the deck with real screenshots and real eval numbers.
- Verify the repo is public and secrets-free (`gitleaks detect`).
- Submit by 23:00.

---

## 17. Acceptance checklist (the definition of done)

**Preflight**
- [ ] `scripts/preflight.sh` prints `PASS` for P1 to P4 against the demo project.

**Live link**
- [ ] The Hosting URL opens with no sign-up. The guided tour completes end to end in under 5 minutes.

**Earth Engine and BigQuery data**
- [ ] The Riau drying surface and the ranked list show 2026 data. The slider animates W20 to the latest week.
- [ ] Clicking a ranked cell shows a Gemini explanation whose numbers match `cell_weekly_drying` exactly.

**Agent and channels**
- [ ] Triggering `drying.ranked` creates cases and tasks. The agent run streams and is stored with its tool calls.
- [ ] Volunteer photo upload returns a schema-valid verdict in under 10 s. A voice note returns a transcript and a translation.
- [ ] A location mismatch or low confidence goes to the human review queue.
- [ ] `+48h` makes open tasks overdue. High risk escalates; low risk reassigns once, then escalates.
- [ ] The brigade inbox shows the brief in id and en with photo, map and timeline. Acknowledging moves the case to monitoring.

**Public dashboard**
- [ ] `/public` opens with no sign-in and shows the Riau map, the stat strip, the bulletin (id and en) and the response record for the current week.
- [ ] Every number in the bulletin matches `public_summary` (the citation check passes).
- [ ] The CSV and GeoJSON exports download and carry the license and credits.
- [ ] A test fails if any `/api/public` response contains a person name, ID, phone, home point, evidence URL or message text.

**Re-ignition model**
- [ ] `fire.quiet` produces 3 recheck spots with `p_reignite` and top features from BigQuery ML.
- [ ] The model is visible in the Vertex AI Model Registry.

**Any region**
- [ ] Congo shows a ranking. A drawn polygon (≤ 2,500 km²) anywhere with peat returns a ranking in under 60 s.

**Evals and README**
- [ ] `docs/EVAL.md` contains: drying capture rate and lift, re-ignition AUC and precision@10% vs baseline, verdict accuracy by field with confusion matrices, ADK eval pass rate, latency p50 and p95.
- [ ] The README has the live link, the architecture diagram, the Google services list with what each does, eval numbers, data credits and licenses, and how to run locally.

**Hygiene and submission**
- [ ] The repo is public. `gitleaks` is clean. No secrets. The Maps key is referrer-restricted.
- [ ] Every example item is labelled in the UI.
- [ ] The video is under 3:00 and shows the live URL. The PDF deck is updated with real numbers.

---

## 18. Known risks and what to do

| Risk | Signal | Response |
|---|---|---|
| Earth Engine registration or quota delay | Preflight P1 fails, or `ee.Initialize` fails | Register first thing. While waiting, build the agent and UI against fixtures in `data/fixtures/`. |
| Gemini preview ID not found | Preflight P2 fails, or 404 from Vertex | Automatic fallback (4.1). Log it in DECISIONS.md. |
| S1 coverage gaps for a week | null `s1_anom_db` | Carry the previous window forward and flag `stale_s1: true` in the UI. |
| Re-ignition labels too sparse | Preflight P3 fails (< 300 positives) | Widen the label window to 3-45 days or the region to all of Sumatra and Kalimantan. Report both. |
| ST_REGIONSTATS unavailable | SQL error | Compute `peat_fraction` in Earth Engine instead. Keep the SQL in the README as optional. |
| WhatsApp setup drags | > 1 h on it | Flag it off. Web chat is the primary channel anyway. |
| Signed URL CORS errors | PUT blocked | Set bucket CORS for the Hosting origin and `localhost:5173`. |
| Demo-day slowness | p95 > targets | min-instances 1, verdict cache, rankings from Firestore only. |

---

## 19. Instructions for Claude Code

1. Work wave by wave (section 16). At the end of each wave, deploy and run `scripts/smoke_test.sh` against the live URL before starting the next.
2. Before using any external ID (model, dataset, API flag), verify it with a real call and record it in `docs/DECISIONS.md`.
3. Keep contracts stable: the Pub/Sub payloads (section 8), API routes (section 9), Firestore shapes (section 7) and verdict schema (6.4). If you must change one, update this file in the same commit.
4. Write tests with the code. The case machine and the clock sweep must be fully covered.
5. Never commit secrets, real phone numbers or unlicensed images. Run `gitleaks detect` before every push.
6. UI copy: short, plain, no em dashes. Indonesian for volunteer text, with an English toggle. Label example data.
7. When something is faked for the demo (sim clock, example people, sample dams), it must be visible in the UI as such. Real data must stay real.
8. Prefer boring, correct code over clever code. Small modules, typed functions, explicit errors.
9. Commit messages: `wave-N: <what>`. Push often; Cloud Build deploys `main`.
