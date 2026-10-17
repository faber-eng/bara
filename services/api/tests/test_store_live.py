import os
import uuid

import pytest
from google.cloud import firestore

from adapters.store import (
    FirestoreCollection,
    FirestoreTransactor,
    Guard,
    GuardFailed,
    Put,
    Update,
)
from config import load_settings
from contracts import Case, Message
from tests.fakes import make_case, make_message

LIVE_CASES = "live_test_cases"
LIVE_MESSAGES = "live_test_messages"


@pytest.mark.live
def test_a_live_guarded_commit_writes_all_or_nothing():
    settings = load_settings(os.environ)
    client = firestore.Client(project=settings.project)
    case_id = f"live-{uuid.uuid4().hex[:12]}"
    cases = FirestoreCollection(client, LIVE_CASES, Case)
    messages = FirestoreCollection(client, LIVE_MESSAGES, Message)
    cases.put(case_id, make_case(id=case_id, status="open"))
    transactor = FirestoreTransactor(client)
    open_guard = Guard(LIVE_CASES, case_id, "status", "open")
    try:
        transactor.commit(
            [open_guard],
            [
                Update(LIVE_CASES, case_id, {"status": "assigned"}),
                Put(LIVE_MESSAGES, case_id, make_message(id=case_id)),
            ],
        )
        assert cases.get(case_id).status == "assigned"
        assert messages.get(case_id).id == case_id

        with pytest.raises(GuardFailed):
            transactor.commit(
                [open_guard], [Update(LIVE_CASES, case_id, {"status": "escalated"})]
            )
        assert cases.get(case_id).status == "assigned"
    finally:
        client.collection(LIVE_CASES).document(case_id).delete()
        client.collection(LIVE_MESSAGES).document(case_id).delete()
