from datetime import UTC, datetime, timedelta

from adapters.channels import WebChannel
from contracts import ClockSettings
from domain.channels import OutboundMessage
from domain.clock import Clock
from tests.fakes import InMemoryClockStore

REAL_NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def test_the_web_channel_builds_a_delivered_web_message_at_sim_time():
    clock = Clock(
        InMemoryClockStore(ClockSettings(offset_seconds=7200, updated_by="t")),
        lambda: REAL_NOW,
    )
    channel = WebChannel(clock, lambda: "m-1")

    built = channel.build(
        OutboundMessage(
            to_id="v1",
            thread="volunteer",
            case_id="c1",
            lang="id",
            text="Cek sekat.",
            text_en="Check the dam.",
        )
    )

    assert built.id == "m-1"
    assert built.channel == "web"
    assert built.delivered is True
    assert built.to_id == "v1"
    assert built.thread == "volunteer"
    assert built.case_id == "c1"
    assert built.lang == "id"
    assert built.text == "Cek sekat."
    assert built.text_en == "Check the dam."
    assert built.created_at == REAL_NOW + timedelta(hours=2)
