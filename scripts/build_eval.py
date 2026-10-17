#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS_DIR = ROOT / "docs/eval"
MERGED = ROOT / "docs/eval.json"
REPORT = ROOT / "docs/EVAL.md"
WEB_COPY = ROOT / "apps/web/src/eval/eval.json"
SECTIONS = ("drying", "reignition", "evidence", "agent")
EXIT_DRIFT = 1
KIND_NAMES = {"photo": "Photos", "audio": "Voice notes"}

DRYING_COMMANDS = """\
cd services/pipelines
for w in $(seq 20 44); do
  uv run python -m jobs.drying_score --region riau --week 2019-W$w
  uv run python -m jobs.drying_score --region riau --week 2023-W$w
done
uv run python -m jobs.eval_drying --region riau"""
REIGNITION_COMMANDS = """\
cd services/pipelines
uv run python -m jobs.train_reignition --region riau
uv run python -m jobs.eval_reignition --region riau"""
EVIDENCE_COMMANDS = """\
cd services/api
GOOGLE_CLOUD_PROJECT=ai-builder-cup-511906 uv run python evidence_eval_job.py"""
AGENT_COMMANDS = """\
cd services/api
GOOGLE_CLOUD_PROJECT=ai-builder-cup-511906 GOOGLE_GENAI_USE_ENTERPRISE=True \\
  uv run --with "google-adk[eval]==2.12.0" python -m evals.run_agent_eval"""
LATENCY_COMMANDS = "python3 scripts/measure_latency.py"
BUILD_COMMAND = "python3 scripts/build_eval.py"


def read_part(parts_dir, name):
    path = parts_dir / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def evidence_latency(evidence):
    if evidence is None:
        return []
    return [
        {
            "path": f"{KIND_NAMES[item['kind']]}: file to verdict (eval set)",
            "p50_ms": round(item["latency_ms"]["p50"], 1),
            "p95_ms": round(item["latency_ms"]["p95"], 1),
            "n": item["latency_ms"]["n"],
            "where": f"local, real Vertex ({evidence['model']}), 4 reads at a time",
            "source": "services/api/evidence_eval_job.py",
        }
        for item in evidence["sets"]
        if item["latency_ms"]["n"]
    ]


def paths_of(part):
    if part is None:
        return []
    return part["paths"]


def latency_rows(parts_dir, evidence):
    live = paths_of(read_part(parts_dir, "latency_live"))
    cited = paths_of(read_part(parts_dir, "latency_cited"))
    return live + evidence_latency(evidence) + cited


def newest_run(sections):
    runs = [part["run_at"] for part in sections.values() if part is not None]
    if not runs:
        return None
    return max(runs)


def merge(parts_dir):
    sections = {name: read_part(parts_dir, name) for name in SECTIONS}
    merged = {"generated_at": newest_run(sections)}
    for name, part in sections.items():
        if part is not None:
            merged[name] = part
    merged["latency"] = latency_rows(parts_dir, sections["evidence"])
    return merged


def day(stamp):
    return stamp[:10]


def percent(value):
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def times(value):
    if value is None:
        return "n/a"
    return f"{value:.2f}x"


def three(value):
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def milliseconds(value):
    if value is None:
        return "n/a"
    if value >= 1000:
        return f"{value / 1000:.1f} s"
    return f"{value:g} ms"


def count(value):
    if value is None:
        return "not stated"
    return f"{value:,}"


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def code(commands):
    return f"```sh\n{commands}\n```"


def not_run(title):
    return f"## {title}\n\nNot run yet.\n"


def drying_section(drying):
    if drying is None:
        return not_run("Drying score: capture rate and lift")
    rows = [
        [
            year["year"],
            year["weeks"],
            count(year["hotspots"]),
            count(year["captured"]),
            percent(year["capture_rate"]),
            times(year["lift"]),
        ]
        for year in drying["years"]
    ]
    first, last = drying["follow_weeks"]
    return f"""## Drying score: capture rate and lift

Run {day(drying["run_at"])}, region `{drying["region"]}`, top {percent(drying["top_share"])} of cells.

{table(["Year", "Weeks", "Hotspots (n)", "In top 10%", "Capture rate", "Lift"], rows)}

How it was made. For each ISO week 20 to 44 of the year (2026: the weeks that `bara.cell_weekly_drying` holds), take the top 10% of the region's peat cells by `drying_score`. Count the MODIS FIRMS detections (`bara.firms_detections`, confidence 30 or more) that fall inside a peat cell {first} to {last} weeks after the scored week, and the share of them inside the top 10% cells. That share is the capture rate; lift is the capture rate divided by 10%, so 1.00x is no better than chance. Counts are pooled over the weeks; a detection is counted once for each scored week whose window holds it (up to 4 times). A week counts only when its window ends on or before {drying["detections_through"]} (the detection table's last refresh minus 2 days). The 2019 and 2023 weeks were scored with the same `jobs.drying_score` as the live weeks. Rows: `bara.eval_drying`.

A year with few hotspots inside the peat cells (see the n column) gives a rate that rests on a small count.

{code(DRYING_COMMANDS)}
"""


def score_row(label, score):
    return [label, f"`{score['name']}`", three(score["auc"]), percent(score["precision_top10"]), percent(score["recall_top10"])]


def reignition_section(reignition):
    if reignition is None:
        return not_run("Re-ignition model: AUC and precision at 10%")
    rows = [
        score_row("Trained model", reignition["model"]),
        score_row("Served model (no rain after the quiet date)", reignition["served"]),
        score_row("Baseline: rank by detection_days", reignition["baseline"]),
    ]
    return f"""## Re-ignition model: AUC and precision at 10%

Run {day(reignition["run_at"])}, region `{reignition["region"]}`, {reignition["split"]} split: {reignition["events"]} fire events, {reignition["positives"]} re-ignited.

{table(["", "Model", "AUC", "Precision at top 10%", "Recall at top 10%"], rows)}

How it was made. `jobs.train_reignition` trains a BigQuery ML logistic regression on the 2015 to 2024 Riau fire events and scores the 2026 test events, which the model never sees. AUC is the rank AUC; precision and recall are over the top 10% of events by score, with ties at the cut sharing the slots left. The baseline ranks the same events by `detection_days`. Rows: `bara.eval_reignition` (newest run).

Read it honestly: on the test split the baseline beats both models. The test split holds only {reignition["positives"]} positives, so the gap is inside the noise, and the model is not shown to be better than the simple rule. The served model leaves out rain after the quiet date, which is not known on the day.

{code(REIGNITION_COMMANDS)}
"""


def matrix_block(matrix):
    labels = matrix["labels"]
    rows = [[f"**{label}**", *cells] for label, cells in zip(labels, matrix["matrix"], strict=True)]
    return f"`{matrix['field']}` (rows: label, columns: verdict)\n\n" + table(["", *labels], rows)


def evidence_set_block(item):
    rows = [
        [f"`{field['field']}`", f"{field['correct']}/{field['n']}", percent(field["accuracy"])]
        for field in item["fields"]
    ]
    matrices = "\n\n".join(matrix_block(matrix) for matrix in item["confusion"])
    latency = item["latency_ms"]
    return f"""### {KIND_NAMES[item["kind"]]} (n = {item["n"]}, prompt `{item["prompt_version"]}`, failed reads {item["failed"]})

{table(["Field", "Correct", "Accuracy"], rows)}

{matrices}

Latency from file to verdict: p50 {milliseconds(latency["p50"])}, p95 {milliseconds(latency["p95"])} (n = {latency["n"]})."""


def evidence_section(evidence):
    if evidence is None:
        return not_run("Gemini verdict accuracy")
    blocks = "\n\n".join(evidence_set_block(item) for item in evidence["sets"])
    return f"""## Gemini verdict accuracy

Run {day(evidence["run_at"])}, model `{evidence["model"]}`.

{blocks}

How it was made. `evidence_eval_job.py` reads every row of `data/eval/labels.csv` (40 photos from Wikimedia Commons and the U.S. Fish and Wildlife Service, and 10 voice notes recorded by the team) with the same `EvidenceReader` and prompt that production uses, with no verdict cache. The task type is `dam_check` when the labelled subject is a canal dam, else `patrol_recheck`. A failed read counts as wrong. A field whose label is `unknown` is left out of that field's accuracy and matrix, so `n` per field can be smaller than the set. Several dam photos are weak matches (UK moorland dams and weirs, not Indonesian canal blocks; see the `notes` column of `labels.csv`). Rows: `bara.eval_evidence`.

{code(EVIDENCE_COMMANDS)}
"""


def agent_section(agent):
    if agent is None:
        return not_run("ADK agent eval")
    rows = [[f"`{result['case']}`", "pass" if result["passed"] else "fail"] for result in agent["results"]]
    return f"""## ADK agent eval

Run {day(agent["run_at"])}, model `{agent["model"]}`: {agent["passed"]} of {agent["cases"]} cases passed ({percent(agent["pass_rate"])}).

{table(["Case", "Result"], rows)}

How it was made. `services/api/evals/agent.test.json` holds the 8 cases of §6.5; each user message is the real run input the coordinator gets. `adk eval` runs the real coordinator (instructions `agent-v6`) on Vertex, with tools wired to an in-memory world and fixed evidence verdicts (no vision call). A case passes when the agent calls exactly the expected tools in the expected order with the expected ids, roles and task types (custom metric `tool_trajectory_subset_args`; free-text arguments such as `reason` are not compared). In production, a high-risk or second overdue is escalated in code before the agent runs (`overdue_events.py`); cases 4 and 6 test the agent's own rule.

{code(AGENT_COMMANDS)}
"""


def latency_section(rows):
    if not rows:
        return not_run("Latency")
    lines = [
        [row["path"], milliseconds(row["p50_ms"]), milliseconds(row["p95_ms"]), milliseconds(row.get("max_ms")), count(row["n"]), row["where"], row["source"]]
        for row in rows
    ]
    return f"""## Latency

{table(["Path", "p50", "p95", "Slowest", "n", "Where", "Source"], lines)}

The live rows time the public GET routes of the deployed site with no sign-in, one request a second, with a random query value so the Hosting CDN cache is skipped. Rows from `docs/DECISIONS.md` are quoted as written there; "n/a" means that entry gives no such number.

{code(LATENCY_COMMANDS)}
"""


def summary_rows(merged):
    rows = []
    drying = merged.get("drying")
    if drying is not None:
        for year in drying["years"]:
            rows.append([f"Drying lift {year['year']}", times(year["lift"]), f"{count(year['hotspots'])} hotspots", day(drying["run_at"])])
    reignition = merged.get("reignition")
    if reignition is not None:
        model, baseline = reignition["model"], reignition["baseline"]
        n = f"{reignition['events']} events, {reignition['positives']} positive"
        rows.append(["Re-ignition AUC (baseline)", f"{three(model['auc'])} ({three(baseline['auc'])})", n, day(reignition["run_at"])])
        rows.append(["Re-ignition precision at 10% (baseline)", f"{percent(model['precision_top10'])} ({percent(baseline['precision_top10'])})", n, day(reignition["run_at"])])
    evidence = merged.get("evidence")
    if evidence is not None:
        for item in evidence["sets"]:
            for field in item["fields"]:
                if field["field"] in ("dam_state", "smoke"):
                    rows.append([f"Verdict `{field['field']}`, {KIND_NAMES[item['kind']].lower()}", percent(field["accuracy"]), str(field["n"]), day(evidence["run_at"])])
    agent = merged.get("agent")
    if agent is not None:
        rows.append(["ADK eval pass rate", percent(agent["pass_rate"]), f"{agent['cases']} cases", day(agent["run_at"])])
    return rows


def render(merged):
    sections = [
        drying_section(merged.get("drying")),
        reignition_section(merged.get("reignition")),
        evidence_section(merged.get("evidence")),
        agent_section(merged.get("agent")),
        latency_section(merged["latency"]),
    ]
    return f"""# Evals

Generated by `{BUILD_COMMAND}` from the result files in `docs/eval/`. Do not edit by hand: re-run the eval, then the build. The web EVAL panel on `/public` reads the same numbers (`apps/web/src/eval/eval.json`).

{table(["Metric", "Value", "n", "Run"], summary_rows(merged))}

""" + "\n".join(sections)


def outputs(parts_dir):
    merged = merge(parts_dir)
    text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
    return {MERGED: text, WEB_COPY: text, REPORT: render(merged)}


def drifted(files):
    return [path for path, text in files.items() if not path.exists() or path.read_text() != text]


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Merge docs/eval/*.json into docs/eval.json, write docs/EVAL.md "
        "and copy the JSON to the web app."
    )
    parser.add_argument("--check", action="store_true", help="exit 1 when an output is out of date; write nothing")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    files = outputs(PARTS_DIR)
    if args.check:
        stale = drifted(files)
        for path in stale:
            print(f"out of date: {path.relative_to(ROOT)}; run {BUILD_COMMAND}", file=sys.stderr)
        return EXIT_DRIFT if stale else 0
    for path, text in files.items():
        path.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
