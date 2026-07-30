"""Generate the bundled alarm tone using only the Python standard library."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44_100
OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "alarm_clock"
    / "assets"
    / "alarm.wav"
)


def envelope(position: float, duration: float) -> float:
    fade = 0.025
    return min(1.0, position / fade, (duration - position) / fade)


def main() -> None:
    sequence = [
        (0.42, 880.0),
        (0.12, 0.0),
        (0.42, 1_100.0),
        (0.12, 0.0),
        (0.42, 880.0),
        (0.50, 0.0),
    ]
    frames = bytearray()
    for duration, frequency in sequence:
        frame_count = round(duration * SAMPLE_RATE)
        for index in range(frame_count):
            position = index / SAMPLE_RATE
            if frequency:
                sample = (
                    0.32
                    * envelope(position, duration)
                    * math.sin(2 * math.pi * frequency * position)
                )
            else:
                sample = 0.0
            frames.extend(struct.pack("<h", round(sample * 32767)))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUTPUT), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(frames)


if __name__ == "__main__":
    main()
