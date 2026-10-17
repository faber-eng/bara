from collections.abc import Callable

from google.cloud import firestore

from contracts import AreaRunState

LIMITS_COLLECTION = "area_rank_limits"


class FirestoreAreaLimitStore:
    def __init__(self, client):
        self._client = client

    def update(
        self,
        uid: str,
        apply: Callable[[AreaRunState | None], tuple[AreaRunState | None, int]],
    ) -> int:
        reference = self._client.collection(LIMITS_COLLECTION).document(uid)
        return run_update(self._client.transaction(), reference, apply)


@firestore.transactional
def run_update(transaction, reference, apply) -> int:
    snapshot = reference.get(transaction=transaction)
    current = (
        AreaRunState.model_validate(snapshot.to_dict()) if snapshot.exists else None
    )
    state, retry_after = apply(current)
    if state is not None:
        transaction.set(reference, state.model_dump())
    return retry_after
