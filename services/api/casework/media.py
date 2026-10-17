import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

from contracts import EvidenceKind

MAX_VIDEO_SECONDS = 30.0
VIDEO_GRACE_SECONDS = 0.5
FFMPEG_TIMEOUT_SECONDS = 60
AUDIO_RATE_HZ = "16000"
VIDEO_HEIGHT_PX = "480"
VIDEO_FPS = "10"
VIDEO_CRF = "30"
AUDIO_MIME = "audio/flac"
VIDEO_MIME = "video/mp4"


class UnreadableMedia(Exception):
    pass


class MediaTooLong(UnreadableMedia):
    pass


@dataclass(frozen=True)
class PreparedMedia:
    data: bytes
    mime_type: str
    kind: EvidenceKind = "photo"


async def spawn(args: tuple[str, ...]) -> asyncio.subprocess.Process:
    try:
        return await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise UnreadableMedia(f"{args[0]} is not installed") from None


async def run_tool(*args: str) -> bytes:
    process = await spawn(args)
    try:
        out, err = await asyncio.wait_for(
            process.communicate(), timeout=FFMPEG_TIMEOUT_SECONDS
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise UnreadableMedia(f"{args[0]} took too long") from None
    except asyncio.CancelledError:
        process.kill()
        raise
    if process.returncode != 0:
        reason = err.decode(errors="replace").strip().splitlines()[-1:] or ["failed"]
        raise UnreadableMedia(f"{args[0]} could not read the file: {reason[0]}")
    return out


def parse_duration(output: bytes) -> float:
    try:
        return float(output.decode().strip())
    except ValueError:
        raise UnreadableMedia("the file has no readable length") from None


async def duration_seconds(source: Path) -> float:
    output = await run_tool(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        str(source),
    )
    return parse_duration(output)


def check_video_length(seconds: float) -> None:
    if seconds > MAX_VIDEO_SECONDS + VIDEO_GRACE_SECONDS:
        raise MediaTooLong(
            f"the video is {seconds:.0f} s long; the limit is {MAX_VIDEO_SECONDS:.0f} s"
        )


async def to_flac(source: Path, target: Path) -> bytes:
    await run_tool(
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        AUDIO_RATE_HZ,
        "-c:a",
        "flac",
        str(target),
    )
    return target.read_bytes()


async def to_small_mp4(source: Path, target: Path) -> bytes:
    await run_tool(
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        f"scale=-2:{VIDEO_HEIGHT_PX}",
        "-r",
        VIDEO_FPS,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        VIDEO_CRF,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "32k",
        "-movflags",
        "+faststart",
        str(target),
    )
    return target.read_bytes()


async def prepare_audio(data: bytes) -> PreparedMedia:
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder, "in")
        source.write_bytes(data)
        flac = await to_flac(source, Path(folder, "out.flac"))
    return PreparedMedia(flac, AUDIO_MIME, "audio")


async def prepare_video(data: bytes) -> PreparedMedia:
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder, "in")
        source.write_bytes(data)
        check_video_length(await duration_seconds(source))
        mp4 = await to_small_mp4(source, Path(folder, "out.mp4"))
    return PreparedMedia(mp4, VIDEO_MIME, "video")
