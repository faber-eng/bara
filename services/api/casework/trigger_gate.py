from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from contracts import TriggerGateState
from domain.trigger_limit import Refusal, decide


class TriggerGateStore(Protocol):
    def update(
        self,
        apply: Callable[
            [TriggerGateState | None], tuple[TriggerGateState | None, Refusal | None]
        ],
    ) -> Refusal | None: ...


class TriggerGate:
    def __init__(self, store: TriggerGateStore, utcnow: Callable[[], datetime]):
        self.store = store
        self._utcnow = utcnow

    def admit(self) -> Refusal | None:
        now = self._utcnow()
        return self.store.update(lambda state: decide(state, now))
