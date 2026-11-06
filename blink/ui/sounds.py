"""Two soft chimes, generated rather than shipped, played by Windows itself.

Qt's QSoundEffect would work, but it drags QtMultimedia in, which drags
FFmpeg and OpenSSL into the build — roughly 40 MB of decoder and TLS
machinery to play two seconds of sine wave. It also sits awkwardly beside
a README that promises no network code.

winsound is in the standard library, is a thin wrapper over PlaySound, and
plays a PCM WAV asynchronously with no dependencies at all.
"""

from __future__ import annotations

import math
import struct
import wave
import winsound
from pathlib import Path

from ..core.models import Config
from ..storage.config import CONFIG_DIR

_RATE = 44100
# winsound has no volume control, so the level has to live in the samples.
# A quarter of full scale is present without being startling.
_AMPLITUDE = 3200


def _write_chime(path: Path, frequency: float, seconds: float = 0.45) -> None:
    frames = int(_RATE * seconds)
    data = bytearray()
    for i in range(frames):
        # Exponential decay: a soft bell rather than a beep.
        envelope = math.exp(-4.0 * i / frames)
        sample = math.sin(2 * math.pi * frequency * i / _RATE)
        sample += 0.3 * math.sin(4 * math.pi * frequency * i / _RATE)
        data += struct.pack("<h", int(_AMPLITUDE * envelope * sample))

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(_RATE)
        out.writeframes(bytes(data))


class Sounds:
    def __init__(self, config: Config) -> None:
        self.cfg = config
        directory = CONFIG_DIR / "sounds"
        self._start = directory / "start.wav"
        self._end = directory / "end.wav"

        for path, frequency in ((self._start, 523.25),   # C5, going in
                                (self._end, 783.99)):    # G5, coming back
            if not path.exists():
                _write_chime(path, frequency)

    def _play(self, path: Path) -> None:
        if not self.cfg.sound.enabled:
            return
        try:
            winsound.PlaySound(
                str(path),
                # NODEFAULT: silence rather than the system ding if the file
                # ever goes missing. ASYNC: never block the tick loop.
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except RuntimeError:
            pass    # no audio device is not a reason to stop reminding you

    def play_start(self) -> None:
        self._play(self._start)

    def play_end(self) -> None:
        self._play(self._end)
