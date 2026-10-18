from collections.abc import Callable

from google.cloud import firestore

from contracts import TriggerGateState
from domain.trigger_limit import Refusal

LIMITS_COLLECTION = "judge_limits"
TRIGGER_DOCUMENT = "trigger"
SEND_DOCUMENT = "send"


class FirestoreTriggerGateStore:
    def __init__(self, client, document: str = TRIGGER_DOCUMENT):
        self._client = client
        self._document = document

    def update(
        self,
        apply: Callable[
            [TriggerGateState | None], tuple[TriggerGateState | None, Refusal | None]
        ],
    ) -> Refusal | None:
        reference = self._client.collection(LIMITS_COLLECTION).document(self._document)
        return run_update(self._client.transaction(), reference, apply)


@firestore.transactional
def run_update(transaction, reference, apply) -> Refusal | None:
    snapshot = reference.get(transaction=transaction)
    current = (
        TriggerGateState.model_validate(snapshot.to_dict()) if snapshot.exists else None
    )
    state, refusal = apply(current)
    if state is not None:
        transaction.set(reference, state.model_dump())
    return refusal
