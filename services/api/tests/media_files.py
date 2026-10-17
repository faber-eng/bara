import subprocess


def ffmpeg_bytes(*args: str, container: str) -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", *args, "-f", container, "pipe:1"],
        check=True,
        capture_output=True,
    )
    return result.stdout


def silent_audio(container: str, seconds: int = 1) -> bytes:
    return ffmpeg_bytes(
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={seconds}",
        container=container,
    )


def short_video(seconds: int = 2) -> bytes:
    return ffmpeg_bytes(
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={seconds}:size=320x240:rate=10",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "frag_keyframe+empty_moov",
        container="mp4",
    )
