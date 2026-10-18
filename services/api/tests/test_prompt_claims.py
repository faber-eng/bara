import re

import pytest

from bara_agent.prompts import INSTRUCTION as AGENT
from casework.brief import SYSTEM_INSTRUCTION as BRIEF
from casework.bulletin import SYSTEM_INSTRUCTION as BULLETIN
from casework.chat import SYSTEM_INSTRUCTION as CHAT
from casework.evidence_reader import (
    AUDIO_SYSTEM_INSTRUCTION,
    VIDEO_SYSTEM_INSTRUCTION,
)
from casework.evidence_reader import (
    SYSTEM_INSTRUCTION as PHOTO,
)
from casework.messenger import SYSTEM_INSTRUCTION as MESSENGER
from casework.rank_explanation import INSTRUCTION as EXPLAIN

PROMPTS = {
    "agent": AGENT,
    "brief": BRIEF,
    "bulletin": BULLETIN,
    "chat": CHAT,
    "messenger": MESSENGER,
    "explain": EXPLAIN,
    "photo": PHOTO,
    "audio": AUDIO_SYSTEM_INSTRUCTION,
    "video": VIDEO_SYSTEM_INSTRUCTION,
}
OVERCLAIM = re.compile(
    r"\bprevent\w*|\bensur\w*|\bguarantee\w*|\bmake sure\b|\bsafe\b|"
    r"\bwet peat does not burn\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize("name", PROMPTS)
def test_no_prompt_claims_that_bara_prevents_fires_or_makes_peat_safe(name):
    assert OVERCLAIM.findall(PROMPTS[name]) == []
