from collections.abc import Mapping
from types import MappingProxyType

from contracts import CaseStatus


class IllegalTransition(Exception):
    def __init__(self, current: CaseStatus, target: CaseStatus):
        super().__init__(f"illegal case transition: {current} -> {target}")
        self.current = current
        self.target = target


EDGES: Mapping[CaseStatus, frozenset[CaseStatus]] = MappingProxyType(
    {
        "open": frozenset({"assigned", "escalated"}),
        "assigned": frozenset({"reviewing", "overdue"}),
        "reviewing": frozenset({"resolved_pending_human", "human_review"}),
        "resolved_pending_human": frozenset({"closed"}),
        "human_review": frozenset({"assigned", "escalated", "closed"}),
        "overdue": frozenset({"assigned", "escalated"}),
        "escalated": frozenset({"monitoring"}),
        "monitoring": frozenset({"assigned"}),
        "closed": frozenset(),
    }
)


def can_transition(current: CaseStatus, target: CaseStatus) -> bool:
    return target in EDGES[current]


def transition(current: CaseStatus, target: CaseStatus) -> CaseStatus:
    if not can_transition(current, target):
        raise IllegalTransition(current, target)
    return target
