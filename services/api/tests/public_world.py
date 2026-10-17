import json
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

import main
from adapters.firestore_repos import (
    BulletinRepository,
    CaseRepository,
    DamRepository,
    EscalationRepository,
    EvidenceRepository,
    RankingRepository,
    RankingRunRepository,
    TaskRepository,
)
from adapters.gemini import ModelGateway
from contracts import (
    Bulletin,
    Case,
    CitedValue,
    Dam,
    Escalation,
    EscalationPack,
    Evidence,
    GeoPoint,
    Message,
    RankedCell,
    RankingRun,
    Task,
    TimelineEntry,
    Volunteer,
)
from public_queries import PublicQueries
from tests.fakes import (
    FakeModels,
    FakeVerifier,
    InMemoryCollection,
    make_case,
    make_dam,
    make_escalation,
    make_evidence,
    make_message,
    make_ranked_cell,
    make_task,
    make_verdict,
    make_volunteer,
)

NOW = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)
WEEK = "2026-W42"
PEOPLE = {
    "uid-ari": ("Ari Wibowo", "+6281234500001", GeoPoint(lat=-0.48213, lon=101.39171)),
    "uid-sari": (
        "Sari Lestari",
        "+6281234500002",
        GeoPoint(lat=-0.51377, lon=101.42209),
    ),
    "uid-dedi": (
        "Dedi Gunawan",
        "+6281234500003",
        GeoPoint(lat=-0.39942, lon=101.31884),
    ),
    "uid-hana": ("Hana Putri", "+6281234500004", GeoPoint(lat=-0.60518, lon=101.50336)),
}
TRANSCRIPT = "Bendungan di belakang rumah Pak Dedi jebol sejak kemarin"
MESSAGE_TEXT = "Halo Ari, tolong cek sekat kanal di dekat rumahmu"
BRIEF = "Brigade brief: Ari reported smoke near the school"


def at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=UTC)


class PublicWorld:
    def __init__(self):
        self.ranked_cells = InMemoryCollection(RankedCell)
        self.dams = InMemoryCollection(Dam)
        self.cases = InMemoryCollection(Case)
        self.tasks = InMemoryCollection(Task)
        self.evidence = InMemoryCollection(Evidence)
        self.escalations = InMemoryCollection(Escalation)
        self.bulletins = InMemoryCollection(Bulletin)
        self.ranking_runs = InMemoryCollection(RankingRun)
        self.volunteers = InMemoryCollection(Volunteer)
        self.messages = InMemoryCollection(Message)
        self.seed()

    def seed(self):
        self.seed_cells()
        self.seed_dams()
        self.seed_people()
        self.seed_cases()
        self.seed_tasks()
        self.seed_evidence()
        self.seed_escalation()
        self.seed_bulletin()

    def seed_cells(self):
        scores = [95.0, 90.0, 80.0, 79.9, 40.0]
        for rank, score in enumerate(scores, start=1):
            cell = make_ranked_cell(
                cell_id=f"riau-{rank}-1", rank=rank, drying_score=score
            )
            self.ranked_cells.put(cell.cell_id, cell)
        old = make_ranked_cell(
            cell_id="riau-old", week_start=date(2026, 10, 5), drying_score=99.0
        )
        self.ranked_cells.put(old.cell_id, old)

    def seed_dams(self):
        for dam_id, state, region in [
            ("dam-1", "broken", "riau"),
            ("dam-2", "damaged", "riau"),
            ("dam-3", "intact", "riau"),
            ("dam-4", "broken", "congo_cuvette"),
        ]:
            self.dams.put(dam_id, make_dam(id=dam_id, last_state=state, region=region))

    def seed_people(self):
        for uid, (name, phone, home) in PEOPLE.items():
            self.volunteers.put(
                uid,
                make_volunteer(
                    id=uid,
                    name=name,
                    home=home,
                    channels={"web": True, "whatsapp": phone},
                ),
            )
        self.messages.put(
            "m1", make_message(id="m1", to_id="uid-ari", text=MESSAGE_TEXT)
        )

    def add_case(self, case_id, status, dam_id, **fields):
        self.cases.put(
            case_id,
            make_case(
                id=case_id,
                status=status,
                dam_id=dam_id,
                cell_id=f"riau-{case_id}",
                **fields,
            ),
        )

    def seed_cases(self):
        self.add_case("assigned", "assigned", "dam-1", opened_at=at(13))
        self.add_case("overdue", "overdue", "dam-2", opened_at=at(14))
        self.add_case("escalated", "escalated", "dam-2", opened_at=at(14))
        self.add_case("monitoring", "monitoring", "dam-1", opened_at=at(13))
        self.add_case("closed-a", "closed", "dam-3", opened_at=at(10), closed_at=at(15))
        self.add_case("closed-b", "closed", "dam-3", opened_at=at(11), closed_at=at(16))
        self.add_case("closed-old", "closed", "dam-3", opened_at=at(1), closed_at=at(5))
        self.add_case("future", "open", "dam-1", opened_at=at(19))

    def add_task(self, task_id, case_id, task_type, assignee, **fields):
        self.tasks.put(
            task_id,
            make_task(
                id=task_id,
                case_id=case_id,
                type=task_type,
                assignee_id=assignee,
                **fields,
            ),
        )

    def seed_tasks(self):
        self.add_task(
            "t-repair-a",
            "closed-a",
            "dam_repair",
            "uid-sari",
            created_at=at(10),
            deadline_at=at(17),
            status="done",
            done_at=at(14, 0),
        )
        self.add_task(
            "t-repair-b",
            "closed-b",
            "dam_repair",
            "uid-dedi",
            created_at=at(12, 0),
            deadline_at=at(19),
            status="done",
            done_at=at(13),
        )
        self.add_task(
            "t-late",
            "assigned",
            "dam_check",
            "uid-ari",
            created_at=at(13),
            deadline_at=at(16),
            status="done",
            done_at=at(17, 1),
        )
        self.add_task(
            "t-overdue",
            "overdue",
            "dam_check",
            "uid-hana",
            created_at=at(14),
            deadline_at=at(15),
            status="overdue",
        )
        self.add_task(
            "t-ontime",
            "escalated",
            "patrol_recheck",
            "uid-ari",
            created_at=at(14),
            deadline_at=at(16),
            status="done",
            done_at=at(15),
        )
        self.add_task(
            "t-pending",
            "assigned",
            "dam_repair",
            "uid-sari",
            created_at=at(13),
            deadline_at=at(22),
            status="open",
        )

    def seed_evidence(self):
        for evidence_id, task_id, case_id in [
            ("e-a", "t-repair-a", "closed-a"),
            ("e-b", "t-repair-b", "closed-b"),
        ]:
            self.evidence.put(
                evidence_id,
                make_evidence(
                    id=evidence_id,
                    task_id=task_id,
                    case_id=case_id,
                    gcs_uri=f"gs://private-evidence/{evidence_id}-face.jpg",
                    sha256="0" * 63 + evidence_id[-1],
                    uploaded_by="uid-sari",
                    point=GeoPoint(lat=-0.50123, lon=101.41456),
                    verdict=make_verdict(
                        dam_state="intact",
                        transcript=TRANSCRIPT,
                        transcript_en="The dam behind Mr Dedi's house broke",
                    ),
                ),
            )

    def seed_escalation(self):
        self.escalations.put(
            "x-esc",
            make_escalation(
                id="x-esc",
                case_id="escalated",
                brief_id=BRIEF,
                brief_en=BRIEF,
                created_at=at(15, 3),
                pack=EscalationPack(
                    photos=["https://storage.test/private/e-a-face.jpg"],
                    map_url="https://maps.test/?q=-0.50123,101.41456",
                    timeline=[TimelineEntry(at=at(15), text=BRIEF)],
                ),
            ),
        )

    def seed_bulletin(self):
        self.bulletins.put(
            f"riau_{WEEK}",
            Bulletin(
                id=f"riau_{WEEK}",
                text_id="Minggu ini 3 sel berisiko tinggi.",
                text_en="This week 3 cells are at high risk.",
                cited=[CitedValue(field="high_risk_cells", value=3)],
                source="gemini",
                model="private-model-name",
                prompt_version="bulletin-v1",
                created_at=at(17, 1),
            ),
        )

    def queries(self) -> PublicQueries:
        return PublicQueries(
            rankings=RankingRepository(lambda region: self.ranked_cells),
            dams=DamRepository(self.dams),
            cases=CaseRepository(self.cases),
            tasks=TaskRepository(self.tasks),
            evidence=EvidenceRepository(self.evidence),
            escalations=EscalationRepository(self.escalations),
            bulletins=BulletinRepository(self.bulletins),
            ranking_runs=RankingRunRepository(lambda region: self.ranking_runs),
            zones={"riau": "Asia/Jakarta", "congo_cuvette": "Africa/Brazzaville"},
        )

    def client(self, settings) -> TestClient:
        gateway = ModelGateway(
            settings.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
        )
        app = main.build_app(settings, gateway, FakeVerifier({}))
        app.state.public_queries = self.queries()
        app.state.utcnow = lambda: NOW
        return TestClient(app)

    def blocklist(self) -> list[str]:
        values: list[str] = []
        for uid, (name, phone, home) in PEOPLE.items():
            values += [uid, name, *name.split(), phone, str(home.lat), str(home.lon)]
        values += [TRANSCRIPT, MESSAGE_TEXT, BRIEF, "gs://", "private-evidence"]
        values += ["whatsapp", "-0.50123", "101.41456", "private-model-name"]
        values += [task.assignee_id for task in self.tasks.where()]
        values += [item.sha256 for item in self.evidence.where()]
        return values


def payload_text(response) -> str:
    return (
        response.text
        if not response.headers["content-type"].startswith("application/json")
        else json.dumps(response.json(), ensure_ascii=False)
    )


def walk_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_keys(item)
