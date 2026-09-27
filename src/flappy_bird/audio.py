"""Audio: procedurally generated sound effects, volume and mute.

The whole module is optional by construction. If ``pygame.mixer`` cannot be
opened — no sound card, a locked device, a headless CI box — the
:class:`AudioManager` quietly becomes a no-op and the game carries on in
silence. Nothing here is allowed to raise into the game loop, so a missing or
broken sound device can never end a run.

Every effect is synthesised from scratch into 16-bit PCM at start-up: there are
no audio files to ship, load or fail to find. The samples are built once per
process and shared, so creating a manager is cheap no matter how many rounds
the suite plays through.

Gameplay systems never import this module. :class:`~flappy_bird.game.Game` owns
the only instance and turns gameplay events into calls on it.
"""

from __future__ import annotations

import array
import math
import random

import pygame

from . import settings
from .utils import clamp

#: Sample format the synthesiser understands; anything else stays silent.
_PCM_FORMAT = -16

#: Generated PCM shared per (rate, channels), so the maths runs once a process.
_buffers: dict[tuple[int, int], dict[str, bytes]] = {}


def pre_init_mixer() -> None:
    """Ask for the small mono format before :func:`pygame.init` opens the mixer.

    ``pygame.init`` starts the mixer on its own with a larger default format, and
    the format cannot be changed afterwards, so the request has to happen first.
    Failing here is not a problem: the manager detects the real format and
    adapts, or falls back to silence.
    """
    try:
        pygame.mixer.pre_init(
            settings.AUDIO_FREQUENCY,
            settings.AUDIO_SIZE,
            settings.AUDIO_CHANNELS,
            settings.AUDIO_BUFFER,
        )
    except pygame.error:
        pass


# --- Synthesis ---------------------------------------------------------------


def _envelope(t: float, attack: float, decay: float) -> float:
    """A fast linear attack followed by an exponential decay, in ``[0, 1]``."""
    if t < attack:
        return t / attack
    return math.exp(-(t - attack) / decay)


def _glide(fraction: float, start_hz: float, end_hz: float) -> float:
    """Frequency at ``fraction`` of the way through a sweep, interpolated in log space.

    Sweeping logarithmically is what makes a glide read as musical instead of
    accelerating towards a click.
    """
    return start_hz * (end_hz / start_hz) ** fraction


def _flap_voice(count: int, rate: int) -> list[float]:
    """A bright upward blip: the sound of a single wingbeat."""
    duration = settings.FLAP_DURATION
    decay = duration * 0.35
    phase = 0.0
    samples = []
    for index in range(count):
        t = index / rate
        phase += 2.0 * math.pi * _glide(t / duration,
                                        settings.FLAP_START_HZ,
                                        settings.FLAP_END_HZ) / rate
        samples.append(
            settings.FLAP_GAIN * math.sin(phase) * _envelope(t, 0.004, decay)
        )
    return samples


def _score_voice(count: int, rate: int) -> list[float]:
    """Two rising notes, each with its own decay, like a small bell."""
    duration = settings.SCORE_DURATION
    split = settings.SCORE_TONE_SPLIT
    decay = duration * 0.30
    phase = 0.0
    samples = []
    for index in range(count):
        t = index / rate
        fraction = t / duration
        if fraction < split:
            note_t = t
            frequency = settings.SCORE_FIRST_HZ
        else:
            note_t = t - split * duration
            frequency = _glide(
                (fraction - split) / (1.0 - split),
                settings.SCORE_FIRST_HZ,
                settings.SCORE_SECOND_HZ,
            )
        phase += 2.0 * math.pi * frequency / rate
        # A touch of the octave makes it chime rather than beep.
        tone = math.sin(phase) + 0.3 * math.sin(2.0 * phase)
        samples.append(settings.SCORE_GAIN * tone * _envelope(note_t, 0.003, decay))
    return samples


def _hit_voice(count: int, rate: int, rng: random.Random | None = None) -> list[float]:
    """A soft filtered noise burst over a falling low tone: an impact, not a hiss."""
    duration = settings.HIT_DURATION
    decay = duration * 0.22
    # Seeded by default so the noise is identical on every run.
    rng = rng if rng is not None else random.Random(_HIT_SEED)
    phase = 0.0
    noise = 0.0
    samples = []
    for index in range(count):
        t = index / rate
        # A one-pole lowpass turns white noise into something with a body.
        noise += (rng.uniform(-1.0, 1.0) - noise) * 0.35
        phase += 2.0 * math.pi * _glide(t / duration,
                                        settings.HIT_START_HZ,
                                        settings.HIT_END_HZ) / rate
        value = math.sin(phase) * 0.8 + noise * 0.6
        samples.append(settings.HIT_GAIN * value * _envelope(t, 0.001, decay))
    return samples


def _game_over_voice(count: int, rate: int) -> list[float]:
    """Three descending notes with a soft attack: a short sad jingle."""
    duration = settings.GAME_OVER_DURATION
    decay = duration * 0.32
    phase = 0.0
    samples = []
    for index in range(count):
        t = index / rate
        fraction = t / duration
        note = settings.GAME_OVER_NOTES[0]
        for candidate in settings.GAME_OVER_NOTES:
            if fraction >= candidate[0]:
                note = candidate
        phase += 2.0 * math.pi * note[1] / rate
        note_t = t - note[0] * duration
        tone = math.sin(phase) + 0.25 * math.sin(2.0 * phase)
        samples.append(settings.GAME_OVER_GAIN * tone * _envelope(note_t, 0.006, decay))
    return samples


#: The four effects, as ``(name, builder)`` pairs. Every builder takes the same
#: ``(count, rate)`` arguments, so they are interchangeable here and can be
#: exercised directly by a test without a mixer at all.
VOICES = (
    ("flap", _flap_voice),
    ("score", _score_voice),
    ("hit", _hit_voice),
    ("game_over", _game_over_voice),
)

#: Seed for the one noisy effect, so its buffer is reproducible.
_HIT_SEED = 0xF1A9

#: How long each effect lasts, read at call time so the settings stay the
#: single source of truth.
_DURATIONS = {
    "flap": "FLAP_DURATION",
    "score": "SCORE_DURATION",
    "hit": "HIT_DURATION",
    "game_over": "GAME_OVER_DURATION",
}

#: Silence prepended to an effect, in seconds. Pygame cannot delay a play, so
#: the pause is generated into the buffer.
_LEAD_INS = {"game_over": "GAME_OVER_LEAD_IN"}


def _fade(samples: list[float], rate: int, seconds: float = 0.005) -> list[float]:
    """Ramp the first and last few milliseconds to zero.

    Every voice already starts on an attack, but a short buffer can still end
    mid-waveform, and a hard edge in the waveform is an audible click. Fading both
    ends makes every effect safe to cut off at any length.
    """
    count = min(round(seconds * rate), len(samples) // 2)
    if count < 1:
        return samples
    faded = list(samples)
    for index in range(count):
        gain = index / count
        faded[index] *= gain
        faded[-(index + 1)] *= gain
    return faded


def _to_pcm(samples: list[float], channels: int) -> bytes:
    """Pack floats in ``[-1, 1]`` into interleaved 16-bit signed PCM."""
    scaled = array.array(
        "h", (max(-32768, min(32767, round(value * 32767))) for value in samples)
    )
    if channels < 2:
        return scaled.tobytes()
    interleaved = array.array("h")
    for value in scaled:
        interleaved.append(value)
        interleaved.append(value)
    return interleaved.tobytes()


def render_buffers(
    rate: int,
    channels: int = settings.AUDIO_CHANNELS,
) -> dict[str, bytes]:
    """Raw PCM for every effect, generated once per ``(rate, channels)``.

    The hit effect draws from a seeded generator so the buffer is byte-for-byte
    identical on every run, which keeps the tests deterministic.
    """
    key = (rate, channels)
    cached = _buffers.get(key)
    if cached is not None:
        return cached

    built: dict[str, bytes] = {}
    for name, voice in VOICES:
        seconds = getattr(settings, _DURATIONS[name])
        samples = voice(round(seconds * rate), rate)
        lead_in = getattr(settings, _LEAD_INS.get(name, ""), 0.0)
        if lead_in:
            samples = [0.0] * round(lead_in * rate) + samples
        built[name] = _to_pcm(_fade(samples, rate), channels)
    _buffers[key] = built
    return built


# --- Manager -----------------------------------------------------------------


class AudioManager:
    """Plays the game's sound effects, and does nothing at all if it cannot.

    Every public method is safe to call in any state, including when the mixer
    never opened: the manager then reports :attr:`available` as ``False`` and
    every play is a cheap no-op.

    ``volume`` and :attr:`muted` are deliberately separate. Muting is a boolean
    that stops sounds being played at all; the volume is a ``[0.0, 1.0]`` level
    clamped on the way in and pushed down to every sound when it changes.

    ``enabled=False`` builds a manager that never touches the mixer at all, for
    headless runs where no one could hear the result.
    """

    SOUND_NAMES = tuple(name for name, _ in VOICES)

    def __init__(
        self,
        volume: float = settings.MASTER_VOLUME,
        muted: bool = False,
        mixer=None,
        enabled: bool = True,
    ) -> None:
        # The mixer is injectable for the same reason PipeManager takes an rng:
        # tests can supply a fake device, or one that refuses to open.
        self._mixer = mixer if mixer is not None else pygame.mixer
        self._volume = clamp(float(volume), 0.0, 1.0)
        self._muted = bool(muted)
        self._sounds: dict[str, object] = {}
        self._init_error: str | None = None
        self.available = False
        if enabled:
            self._initialize()
        else:
            # Headless runs never open a device: nothing could hear it, and the
            # open/close pair costs real time in a test suite.
            self._init_error = "disabled"

    def _initialize(self) -> None:
        """Open the mixer if needed and build the sounds; never raises."""
        try:
            if self._mixer.get_init() is None:
                self._mixer.init()
            self._sounds = self._build_sounds()
            self.available = True
        except Exception as error:  # noqa: BLE001 - audio must never be fatal
            self._init_error = f"{type(error).__name__}: {error}"
            self._sounds = {}
            self.available = False

    def _build_sounds(self) -> dict[str, object]:
        """Create one ``Sound`` per effect, sized for the real mixer format."""
        fmt = self._mixer.get_init()
        if fmt is None:
            return {}
        rate, size, channels = fmt[0], fmt[1], fmt[2]
        if size != _PCM_FORMAT:
            # 16-bit PCM is the only format the synthesiser produces; anything
            # else simply plays nothing rather than playing noise.
            return {}

        sounds: dict[str, object] = {}
        for name, buffer in render_buffers(rate, channels).items():
            sound = self._mixer.Sound(buffer=buffer)
            sound.set_volume(self._volume)
            sounds[name] = sound
        return sounds

    # --- Status ---------------------------------------------------------------

    @property
    def init_error(self) -> str | None:
        """Why audio is unavailable, or ``None`` when it is working."""
        return self._init_error

    @property
    def sound_names(self) -> tuple[str, ...]:
        """Names of the effects this manager knows about."""
        return self.SOUND_NAMES

    def has_sound(self, name: str) -> bool:
        return name in self._sounds

    def __len__(self) -> int:
        return len(self._sounds)

    # --- Volume and mute ------------------------------------------------------

    @property
    def volume(self) -> float:
        """Current master volume, always within ``[0.0, 1.0]``."""
        return self._volume

    def set_volume(self, value: float) -> float:
        """Clamp and store a new master volume, then push it to every sound."""
        self._volume = clamp(float(value), 0.0, 1.0)
        for sound in self._sounds.values():
            try:
                sound.set_volume(self._volume)
            except Exception:  # noqa: BLE001 - see play()
                pass
        return self._volume

    @property
    def muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool) -> bool:
        self._muted = bool(muted)
        return self._muted

    def toggle_mute(self) -> bool:
        """Flip the mute flag and return the new value."""
        self._muted = not self._muted
        return self._muted

    # --- Playing --------------------------------------------------------------

    def play(self, name: str) -> object | None:
        """Play one effect by name.

        Returns the channel it started on, or ``None`` when nothing was played —
        because audio is unavailable, the name is unknown, the manager is muted,
        or the mixer refused the call.
        """
        if not self.available or self._muted:
            return None
        sound = self._sounds.get(name)
        if sound is None:
            return None
        try:
            return sound.play()
        # Audio is decoration: anything at all the mixer or a Sound object throws
        # is swallowed here rather than allowed to end a run. The broad catch is
        # deliberate, and it is why an unexpected mixer build cannot crash play.
        except Exception:  # noqa: BLE001 - see above
            return None

    def play_flap(self) -> None:
        """The bird flapped."""
        self.play("flap")

    def play_score(self) -> None:
        """A pipe was passed."""
        self.play("score")

    def play_hit(self) -> None:
        """Something was hit."""
        self.play("hit")

    def play_game_over(self) -> None:
        """The round ended; the buffer carries its own lead-in after the impact."""
        self.play("game_over")

    def stop_all(self) -> None:
        """Silence anything still ringing; never raises."""
        for sound in self._sounds.values():
            try:
                sound.stop()
            except Exception:  # noqa: BLE001 - see play()
                pass
