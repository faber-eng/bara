import asyncio
import subprocess
from pathlib import Path

import pytest

from casework.media import (
    MediaTooLong,
    UnreadableMedia,
    check_video_length,
    parse_duration,
    prepare_audio,
    prepare_video,
)
from tests.media_files import short_video, silent_audio


def test_webm_audio_becomes_mono_flac():
    flac = asyncio.run(prepare_audio(silent_audio("webm"))).data

    assert flac[:4] == b"fLaC"


def test_ogg_audio_becomes_flac():
    flac = asyncio.run(prepare_audio(silent_audio("ogg"))).data

    assert flac[:4] == b"fLaC"


def test_bytes_that_are_not_audio_are_unreadable():
    with pytest.raises(UnreadableMedia):
        asyncio.run(prepare_audio(b"plain text"))


def test_a_video_becomes_a_small_mp4():
    prepared = asyncio.run(prepare_video(short_video(2)))

    assert prepared.kind == "video"
    assert prepared.mime_type == "video/mp4"
    assert prepared.data[4:8] == b"ftyp"


def test_a_quicktime_video_is_accepted(tmp_path: Path):
    target = tmp_path / "clip.mov"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=320x240:rate=10",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ],
        check=True,
    )

    prepared = asyncio.run(prepare_video(target.read_bytes()))

    assert prepared.mime_type == "video/mp4"


def test_a_video_of_thirty_one_seconds_is_refused():
    with pytest.raises(MediaTooLong):
        asyncio.run(prepare_video(short_video(32)))


def test_the_length_limit_has_a_half_second_grace():
    check_video_length(30.4)
    with pytest.raises(MediaTooLong, match="31 s long"):
        check_video_length(30.6)


def test_a_length_that_is_not_a_number_is_unreadable():
    with pytest.raises(UnreadableMedia):
        parse_duration(b"N/A\n")
