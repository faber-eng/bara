from collections.abc import Callable

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import firestore

from contracts import AreaRunState

LIMITS_COLLECTION = "area_rank_limits"
CHAT_LIMITS_COLLECTION = "chat_limits"


class AreaLimitUnavailable(Exception):
    pass


class FirestoreAreaLimitStore:
    def __init__(self, client, collection: str = LIMITS_COLLECTION):
        self._client = client
        self._collection = collection

    def update(
        self,
        uid: str,
        apply: Callable[[AreaRunState | None], tuple[AreaRunState | None, int]],
    ) -> int:
        reference = self._client.collection(self._collection).document(uid)
        try:
            return run_update(self._client.transaction(), reference, apply)
        except GoogleAPICallError as error:
            raise AreaLimitUnavailable(str(error)) from error


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
