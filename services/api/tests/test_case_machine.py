import itertools
import typing

import pytest

from contracts import CaseStatus
from domain import case_machine
from domain.case_machine import IllegalTransition, can_transition, transition

STATUSES = typing.get_args(CaseStatus)

LEGAL_EDGES = [
    ("open", "assigned"),
    ("open", "escalated"),
    ("assigned", "reviewing"),
    ("assigned", "overdue"),
    ("reviewing", "resolved_pending_human"),
    ("reviewing", "human_review"),
    ("resolved_pending_human", "closed"),
    ("human_review", "assigned"),
    ("human_review", "escalated"),
    ("human_review", "closed"),
    ("overdue", "assigned"),
    ("overdue", "escalated"),
    ("escalated", "monitoring"),
    ("monitoring", "assigned"),
]

ILLEGAL_EDGES = [
    pair for pair in itertools.product(STATUSES, STATUSES) if pair not in LEGAL_EDGES
]


def test_the_legal_edge_list_has_fourteen_pairs():
    assert len(LEGAL_EDGES) == 14
    assert len(ILLEGAL_EDGES) == 81 - 14


@pytest.mark.parametrize(("current", "target"), LEGAL_EDGES)
def test_a_legal_edge_passes(current, target):
    assert transition(current, target) == target
    assert can_transition(current, target) is True


@pytest.mark.parametrize(("current", "target"), ILLEGAL_EDGES)
def test_every_other_ordered_pair_raises_naming_both(current, target):
    with pytest.raises(IllegalTransition) as raised:
        transition(current, target)

    assert current in str(raised.value)
    assert target in str(raised.value)
    assert can_transition(current, target) is False


def test_reviewing_cannot_go_straight_back_to_assigned():
    with pytest.raises(IllegalTransition):
        transition("reviewing", "assigned")


def test_assigned_cannot_escalate_without_going_overdue():
    with pytest.raises(IllegalTransition):
        transition("assigned", "escalated")


def test_closed_has_no_exit():
    assert case_machine.EDGES["closed"] == frozenset()
    for target in STATUSES:
        with pytest.raises(IllegalTransition):
            transition("closed", target)


def test_every_status_is_a_key_of_the_table():
    assert set(case_machine.EDGES) == set(STATUSES)


def test_the_table_is_immutable():
    with pytest.raises(TypeError):
        case_machine.EDGES["closed"] = frozenset({"open"})
    with pytest.raises(AttributeError):
        case_machine.EDGES["open"].add("closed")


def test_removing_one_edge_makes_a_legal_test_fail(monkeypatch):
    without_overdue = dict(case_machine.EDGES)
    without_overdue["assigned"] = frozenset({"reviewing"})
    monkeypatch.setattr(case_machine, "EDGES", without_overdue)

    with pytest.raises(IllegalTransition):
        transition("assigned", "overdue")
