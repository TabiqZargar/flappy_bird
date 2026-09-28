"""Tests for the audio layer and the game's sound wiring.

No test here needs a sound device. The mixer is a fake in almost every case:
``AudioManager`` takes one as a parameter for the same reason ``PipeManager``
takes an ``rng``, and the game is given a recorder in place of its real manager.
The handful of tests that do touch the real mixer run under SDL's ``dummy``
audio driver, which is a silent sink.
"""

import array
import inspect

import pygame
import pytest

from flappy_bird import audio, settings
from flappy_bird.audio import AudioManager, render_buffers
from flappy_bird.game import Game
from flappy_bird.pipe import Pipe
from flappy_bird.state import GameState
from flappy_bird.visuals import Visuals
from tests.helpers import DT, add_passed_pipe, crash

RATE = settings.AUDIO_FREQUENCY


# --- Fakes -------------------------------------------------------------------


class FakeSound:
    """Stands in for ``pygame.mixer.Sound`` and counts what it was asked to do."""

    def __init__(self, buffer: bytes, owner: "FakeMixer") -> None:
        self.buffer = buffer
        self.owner = owner
        self.volume: float | None = None
        self.plays = 0
        self.stops = 0

    def play(self):
        self.plays += 1
        self.owner.log.append("play")
        if self.owner.breaks_on_play:
            raise RuntimeError("the sound card fell over")
        return f"channel-{self.plays}"

    def set_volume(self, value: float) -> None:
        self.volume = value

    def stop(self) -> None:
        self.stops += 1
        self.owner.log.append("stop")


class FakeMixer:
    """A mixer that never touches a device, and can be told to misbehave."""

    FORMAT = (settings.AUDIO_FREQUENCY, settings.AUDIO_SIZE, settings.AUDIO_CHANNELS)

    def __init__(self, fmt=None, init_error=None, breaks_on_play=False) -> None:
        self._fmt = fmt
        self.init_error = init_error
        self.breaks_on_play = breaks_on_play
        self.sounds: list[FakeSound] = []
        self.log: list[str] = []
        self.init_calls = 0

    def get_init(self):
        return self._fmt

    def init(self) -> None:
        self.init_calls += 1
        if self.init_error is not None:
            raise pygame.error(self.init_error)
        self._fmt = self.FORMAT

    # Used as ``mixer.Sound(buffer=...)``; an instance attribute is not bound,
    # so this takes only the keyword the real class takes.
    def Sound(self, buffer: bytes) -> FakeSound:
        sound = FakeSound(buffer, self)
        self.sounds.append(sound)
        return sound

    def sound(self, name: str) -> FakeSound:
        index = AudioManager.SOUND_NAMES.index(name)
        return self.sounds[index]


class RecordingAudio:
    """Stands in for the game's audio manager and logs every call."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.muted = False
        self.volume = settings.MASTER_VOLUME

    def play_flap(self) -> None:
        self.calls.append("flap")

    def play_score(self) -> None:
        self.calls.append("score")

    def play_hit(self) -> None:
        self.calls.append("hit")

    def play_game_over(self) -> None:
        self.calls.append("game_over")

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted

    def count(self, name: str) -> int:
        return self.calls.count(name)


# --- Helpers -----------------------------------------------------------------


def samples_of(buffer: bytes) -> array.array:
    values = array.array("h")
    values.frombytes(buffer)
    return values


def pitch(buffer: bytes, rate: int, start: float = 0.0, end: float = 1.0) -> float:
    """Rough pitch of a slice, from its zero crossings."""
    values = samples_of(buffer)
    low = int(len(values) * start)
    high = int(len(values) * end)
    chunk = values[low:high]
    # Each sample is compared with the one after it, so the two views are
    # deliberately one element shorter than `chunk`.
    crossings = sum(1 for a, b in zip(chunk, chunk[1:], strict=False) if a <= 0 < b)
    seconds = (high - low) / rate
    return crossings / seconds if seconds else 0.0


def post(game: Game, event_type: int, **attributes) -> None:
    pygame.event.post(pygame.event.Event(event_type, attributes))


def press(game: Game, key: int) -> None:
    post(game, pygame.KEYDOWN, key=key)
    game.handle_events()


@pytest.fixture()
def mixer() -> FakeMixer:
    return FakeMixer()


@pytest.fixture()
def manager(mixer: FakeMixer) -> AudioManager:
    return AudioManager(mixer=mixer)


@pytest.fixture()
def game():
    """A round in progress, with a recording stand-in for the audio manager."""
    instance = Game(headless=True)
    instance.start_round()
    instance.audio = RecordingAudio()
    pygame.event.clear()
    yield instance
    pygame.quit()


@pytest.fixture()
def idle_game():
    """A fresh game still waiting in START, with the same stand-in."""
    instance = Game(headless=True)
    instance.audio = RecordingAudio()
    pygame.event.clear()
    yield instance
    pygame.quit()


# --- Procedural synthesis ----------------------------------------------------


class TestSynthesis:
    """The sounds are generated, so their shape is worth asserting on."""

    def test_every_effect_gets_a_buffer(self):
        buffers = render_buffers(RATE)
        assert set(buffers) == set(AudioManager.SOUND_NAMES)

    def test_buffers_are_16_bit_mono_pcm(self):
        for name, buffer in render_buffers(RATE).items():
            assert len(buffer) % 2 == 0, name
            assert len(samples_of(buffer)) > 0, name

    def test_buffers_stay_small(self):
        # Four short effects; anything past a second apiece is not an arcade blip.
        for name, buffer in render_buffers(RATE).items():
            assert len(samples_of(buffer)) / RATE < 1.0, name

    def test_each_effect_lasts_about_its_configured_time(self):
        expected = {
            "flap": settings.FLAP_DURATION,
            "score": settings.SCORE_DURATION,
            "hit": settings.HIT_DURATION,
            "game_over": settings.GAME_OVER_DURATION + settings.GAME_OVER_LEAD_IN,
        }
        buffers = render_buffers(RATE)
        for name, seconds in expected.items():
            actual = len(samples_of(buffers[name])) / RATE
            assert actual == pytest.approx(seconds, abs=0.01), name

    def test_the_effects_all_differ(self):
        buffers = render_buffers(RATE)
        assert len({bytes(buffer) for buffer in buffers.values()}) == len(buffers)

    def test_no_effect_clips(self):
        for name, buffer in render_buffers(RATE).items():
            peak = max(abs(v) for v in samples_of(buffer)) / 32767
            assert peak < 1.0, name

    def test_every_effect_starts_and_ends_quietly(self):
        for name, buffer in render_buffers(RATE).items():
            values = samples_of(buffer)
            assert abs(values[0]) < 2000, name
            assert abs(values[-1]) < 2000, name

    def test_flap_rises_in_pitch(self):
        buffer = render_buffers(RATE)["flap"]
        assert pitch(buffer, RATE, 0.0, 0.25) < pitch(buffer, RATE, 0.7, 1.0)

    def test_game_over_falls_in_pitch(self):
        buffer = render_buffers(RATE)["game_over"]
        assert pitch(buffer, RATE, 0.3, 0.55) > pitch(buffer, RATE, 0.85, 1.0)

    def test_score_rises_in_pitch(self):
        buffer = render_buffers(RATE)["score"]
        assert pitch(buffer, RATE, 0.0, 0.3) < pitch(buffer, RATE, 0.7, 1.0)

    def test_game_over_leads_in_with_silence(self):
        # Pygame cannot delay a play, so the pause after the impact is silence
        # generated into the buffer itself.
        buffer = render_buffers(RATE)["game_over"]
        lead = samples_of(buffer)[: round(settings.GAME_OVER_LEAD_IN * RATE)]
        assert all(value == 0 for value in lead)

    def test_the_noise_in_the_hit_is_reproducible(self, monkeypatch):
        first = dict(render_buffers(32000))
        monkeypatch.setattr(audio, "_buffers", {})
        assert dict(render_buffers(32000)) == first

    def test_buffers_are_shared_per_format(self):
        assert render_buffers(RATE) is render_buffers(RATE)

    def test_a_different_rate_generates_its_own_buffers(self):
        assert render_buffers(16000) is not render_buffers(RATE)

    def test_stereo_buffers_interleave_each_sample_twice(self):
        mono = samples_of(render_buffers(RATE)["flap"])
        stereo = samples_of(render_buffers(RATE, channels=2)["flap"])
        assert len(stereo) == 2 * len(mono)
        assert stereo[0::2] == mono
        assert stereo[1::2] == mono


# --- Initialisation ----------------------------------------------------------


class TestInitialisation:
    def test_it_initialises_with_a_working_mixer(self, mixer):
        manager = AudioManager(mixer=mixer)
        assert manager.available is True
        assert len(manager) == 4
        assert manager.init_error is None

    def test_it_opens_a_mixer_that_is_not_running_yet(self):
        mixer = FakeMixer(fmt=None)
        manager = AudioManager(mixer=mixer)
        assert mixer.init_calls == 1
        assert manager.available is True

    def test_it_leaves_a_running_mixer_alone(self, mixer):
        AudioManager(mixer=mixer)
        mixer.init_calls = 0
        AudioManager(mixer=mixer)
        assert mixer.init_calls == 0

    def test_it_becomes_a_no_op_when_the_device_refuses(self):
        mixer = FakeMixer(fmt=None, init_error="Audio target not available")
        manager = AudioManager(mixer=mixer)
        assert manager.available is False
        assert len(manager) == 0
        assert "not available" in manager.init_error

    def test_it_survives_a_mixer_that_raises_anything(self):
        class Exploding:
            def get_init(self):
                raise RuntimeError("no mixer here")

            def init(self):
                raise RuntimeError("no mixer here")

        manager = AudioManager(mixer=Exploding())
        assert manager.available is False
        assert "no mixer here" in manager.init_error

    def test_disabling_it_never_touches_the_mixer(self, mixer):
        manager = AudioManager(mixer=mixer, enabled=False)
        assert manager.available is False
        assert manager.init_error == "disabled"
        assert mixer.init_calls == 0
        assert mixer.sounds == []

    def test_an_unsupported_format_stays_silent_instead_of_noisy(self):
        mixer = FakeMixer(fmt=(44100, -8, 1))
        manager = AudioManager(mixer=mixer)
        assert manager.available is True
        assert len(manager) == 0
        manager.play_flap()

    def test_it_works_against_the_real_mixer_under_the_dummy_driver(self):
        # The dummy driver is a silent sink, so this needs no sound hardware.
        manager = AudioManager()
        try:
            assert manager.available is True
            assert len(manager) == 4
            for name in manager.sound_names:
                assert manager.has_sound(name)
        finally:
            manager.stop_all()


# --- Volume ------------------------------------------------------------------


class TestVolume:
    def test_it_defaults_to_the_setting(self, manager):
        assert manager.volume == settings.MASTER_VOLUME

    def test_the_default_is_a_sane_level(self):
        assert 0.0 < settings.MASTER_VOLUME <= 1.0

    def test_it_clamps_above_one(self, manager):
        assert manager.set_volume(5.0) == 1.0
        assert manager.volume == 1.0

    def test_it_clamps_below_zero(self, manager):
        assert manager.set_volume(-2.0) == 0.0
        assert manager.volume == 0.0

    def test_it_keeps_a_level_inside_the_range(self, manager):
        assert manager.set_volume(0.42) == 0.42

    def test_it_clamps_the_level_it_is_constructed_with(self, mixer):
        assert AudioManager(volume=9.0, mixer=mixer).volume == 1.0
        assert AudioManager(volume=-9.0, mixer=mixer).volume == 0.0

    def test_a_new_level_reaches_every_sound(self, mixer):
        manager = AudioManager(mixer=mixer)
        manager.set_volume(0.25)
        assert all(sound.volume == 0.25 for sound in mixer.sounds)

    def test_the_constructed_level_reaches_every_sound(self, mixer):
        AudioManager(volume=0.5, mixer=mixer)
        assert all(sound.volume == 0.5 for sound in mixer.sounds)

    def test_silence_still_counts_as_unmuted(self, manager):
        manager.set_volume(0.0)
        assert manager.muted is False


# --- Mute --------------------------------------------------------------------


class TestMute:
    def test_it_starts_unmuted(self, manager):
        assert manager.muted is False

    def test_it_can_start_muted(self, mixer):
        assert AudioManager(muted=True, mixer=mixer).muted is True

    def test_toggling_flips_and_reports(self, manager):
        assert manager.toggle_mute() is True
        assert manager.muted is True
        assert manager.toggle_mute() is False
        assert manager.muted is False

    def test_it_can_be_set_directly(self, manager):
        manager.set_muted(True)
        assert manager.muted is True
        manager.set_muted(False)
        assert manager.muted is False

    def test_muting_stops_every_sound(self, manager, mixer):
        manager.set_muted(True)
        manager.play_flap()
        manager.play_score()
        manager.play_hit()
        manager.play_game_over()
        assert mixer.log == []

    def test_unmuting_lets_them_play_again(self, manager, mixer):
        manager.set_muted(True)
        manager.play_flap()
        manager.toggle_mute()
        manager.play_flap()
        assert mixer.sound("flap").plays == 1

    def test_muting_does_not_change_the_volume(self, manager):
        manager.set_volume(0.6)
        manager.toggle_mute()
        assert manager.volume == 0.6


# --- Playing -----------------------------------------------------------------


class TestPlaying:
    def test_each_method_plays_its_own_effect(self, manager, mixer):
        manager.play_flap()
        manager.play_score()
        manager.play_hit()
        manager.play_game_over()
        for name in AudioManager.SOUND_NAMES:
            assert mixer.sound(name).plays == 1, name

    def test_playing_returns_a_channel(self, manager):
        assert manager.play("flap") is not None

    def test_an_unknown_name_is_ignored(self, manager):
        assert manager.play("explosion") is None

    def test_nothing_plays_when_audio_is_unavailable(self):
        manager = AudioManager(mixer=FakeMixer(init_error="no device"))
        manager.play_flap()
        manager.play_score()
        manager.play_hit()
        manager.play_game_over()

    def test_nothing_plays_when_audio_is_disabled(self, mixer):
        manager = AudioManager(mixer=mixer, enabled=False)
        manager.play_flap()
        assert mixer.log == []

    def test_a_sound_that_throws_does_not_escape(self):
        mixer = FakeMixer(breaks_on_play=True)
        manager = AudioManager(mixer=mixer)
        manager.play_flap()
        manager.play_score()
        manager.play_hit()
        manager.play_game_over()
        assert mixer.sound("flap").plays == 1

    def test_the_sound_methods_return_none(self, manager):
        assert manager.play_flap() is None
        assert manager.play_score() is None
        assert manager.play_hit() is None
        assert manager.play_game_over() is None

    def test_stopping_is_safe_even_when_it_fails(self):
        class Broken:
            def stop(self):
                raise RuntimeError("no")

        manager = AudioManager(mixer=FakeMixer(), enabled=False)
        manager._sounds = {"flap": Broken()}
        manager.stop_all()


# --- Game wiring -------------------------------------------------------------


class TestFlapSound:
    def test_a_flap_sounds_once(self, game):
        game.flap()
        assert game.audio.count("flap") == 1

    def test_each_flap_sounds_again(self, game):
        for _ in range(4):
            game.flap()
        assert game.audio.count("flap") == 4

    def test_no_flap_means_no_sound(self, game):
        for _ in range(5):
            game.update(DT)
        assert game.audio.count("flap") == 0

    def test_a_flap_outside_playing_is_silent(self, idle_game):
        idle_game.flap()
        assert idle_game.audio.count("flap") == 0
        assert idle_game.state is GameState.START

    def test_starting_the_game_sounds_exactly_one_flap(self, idle_game):
        press(idle_game, pygame.K_SPACE)
        assert idle_game.state is GameState.PLAYING
        assert idle_game.audio.calls == ["flap"]

    def test_restarting_sounds_exactly_one_flap(self, game):
        crash(game)
        game.audio.calls.clear()
        press(game, pygame.K_SPACE)
        assert game.state is GameState.PLAYING
        assert game.audio.calls == ["flap"]

    def test_the_bird_actually_moves(self, game):
        game.flap()
        assert game.player.velocity_y == settings.JUMP_VELOCITY


class TestScoreSound:
    def test_a_point_sounds_once(self, game):
        add_passed_pipe(game)
        game.update(DT)
        assert game.score == 1
        assert game.audio.count("score") == 1

    def test_the_score_does_not_sound_again_while_idle(self, game):
        add_passed_pipe(game)
        game.update(DT)
        for _ in range(30):
            game.update(DT)
        assert game.score == 1
        assert game.audio.count("score") == 1

    def test_simultaneous_pipes_sound_once_not_once_each(self, game):
        for _ in range(3):
            add_passed_pipe(game)
        game.update(DT)
        assert game.score == 3
        assert game.audio.count("score") == 1

    def test_nothing_scores_before_a_pipe_is_passed(self, game):
        for _ in range(20):
            game.update(DT)
        assert game.audio.count("score") == 0

    def test_a_point_after_a_restart_sounds_again(self, game):
        add_passed_pipe(game)
        game.update(DT)
        game.restart()
        game.audio.calls.clear()
        add_passed_pipe(game)
        game.update(DT)
        assert game.audio.count("score") == 1


class TestGameOverSounds:
    def test_a_collision_sounds_the_impact_and_the_jingle(self, game):
        crash(game)
        assert game.state is GameState.GAME_OVER
        assert game.audio.count("hit") == 1
        assert game.audio.count("game_over") == 1

    def test_a_frozen_game_over_plays_nothing_more(self, game):
        crash(game)
        before = list(game.audio.calls)
        for _ in range(120):
            game.update(DT)
        assert game.audio.calls == before

    def test_the_round_end_is_idempotent(self, game):
        game.end_round()
        game.end_round()
        game.end_round()
        assert game.audio.count("hit") == 1
        assert game.audio.count("game_over") == 1

    def test_a_crashing_frame_pays_nothing_and_says_nothing(self, game):
        game.pipe_manager.pipes.append(Pipe(x=0, gap_y=settings.BIRD_START_Y))
        crash(game)
        assert game.score == 0
        assert game.audio.count("score") == 0
        assert game.audio.count("hit") == 1

    def test_the_ground_sounds_too(self, game):
        game.player.y = float(settings.GROUND_TOP - 4)
        game.update(DT)
        assert game.state is GameState.GAME_OVER
        assert game.audio.count("hit") == 1

    def test_setting_the_legacy_flag_directly_is_silent(self, game):
        # The flag is a compatibility view; it is not a gameplay event.
        game.game_over = True
        assert game.audio.calls == []


class TestMuteKey:
    def test_m_toggles_mute_while_playing(self, game):
        press(game, pygame.K_m)
        assert game.audio.muted is True
        press(game, pygame.K_m)
        assert game.audio.muted is False

    def test_m_toggles_mute_on_the_start_screen(self, idle_game):
        press(idle_game, pygame.K_m)
        assert idle_game.audio.muted is True
        assert idle_game.state is GameState.START

    def test_m_toggles_mute_on_the_game_over_screen(self, game):
        crash(game)
        press(game, pygame.K_m)
        assert game.audio.muted is True
        assert game.state is GameState.GAME_OVER

    def test_mute_does_not_start_a_round(self, idle_game):
        press(idle_game, pygame.K_m)
        assert idle_game.state is GameState.START
        assert idle_game.pipes == []

    def test_mute_does_not_restart_a_round(self, game):
        crash(game)
        press(game, pygame.K_m)
        assert game.state is GameState.GAME_OVER
        assert game.pipes

    def test_mute_leaves_the_score_alone(self, game):
        game.add_score(7)
        press(game, pygame.K_m)
        assert game.score == 7
        assert game.high_score == 7

    def test_mute_leaves_the_physics_alone(self, game):
        game.flap()
        position = (game.player.x, game.player.y, game.player.velocity_y)
        press(game, pygame.K_m)
        assert (game.player.x, game.player.y, game.player.velocity_y) == position

    def test_mute_makes_no_sound_of_its_own(self, game):
        press(game, pygame.K_m)
        assert game.audio.calls == []

    def test_mute_survives_a_round(self, game):
        press(game, pygame.K_m)
        crash(game)
        press(game, pygame.K_SPACE)
        assert game.audio.muted is True

    def test_the_toggle_method_reports_the_new_value(self, game):
        assert game.toggle_mute() is True
        assert game.toggle_mute() is False


# --- Game ownership and isolation -------------------------------------------


class TestOwnership:
    def test_a_game_owns_one_audio_manager(self):
        instance = Game(headless=True)
        try:
            assert isinstance(instance.audio, AudioManager)
        finally:
            pygame.quit()

    def test_a_headless_game_opens_no_device(self):
        instance = Game(headless=True)
        try:
            assert instance.audio.available is False
            assert instance.audio.init_error == "disabled"
        finally:
            pygame.quit()

    def test_a_headless_game_still_plays(self):
        instance = Game(headless=True)
        try:
            instance.start_round()
            instance.flap()
            add_passed_pipe(instance)
            instance.update(DT)
            crash(instance)
            instance.render()
        finally:
            pygame.quit()

    def test_the_start_screen_works_with_audio_disabled(self):
        instance = Game(headless=True)
        try:
            assert instance.audio.available is False
            instance.render()
            press(instance, pygame.K_SPACE)
            assert instance.state is GameState.PLAYING
        finally:
            pygame.quit()

    def test_sounds_that_raise_cannot_end_a_run(self):
        class HostileSound:
            def play(self):
                raise RuntimeError("the sound card fell over")

            def set_volume(self, value):
                raise RuntimeError("the sound card fell over")

            def stop(self):
                raise RuntimeError("the sound card fell over")

        instance = Game(headless=True)
        try:
            manager = AudioManager(enabled=False)
            manager._sounds = {
                name: HostileSound() for name in AudioManager.SOUND_NAMES
            }
            instance.audio = manager
            instance.start_round()
            instance.flap()
            add_passed_pipe(instance)
            instance.update(DT)
            crash(instance)
            instance.render()
            assert instance.state is GameState.GAME_OVER
            assert instance.high_score == 1
        finally:
            pygame.quit()

    @pytest.mark.parametrize(
        "module_name",
        [
            "player",
            "pipe",
            "pipe_manager",
            "collision",
            "scoring",
            "visuals",
            "state",
            "utils",
            "settings",
        ],
    )
    def test_gameplay_modules_never_touch_the_mixer(self, module_name):
        module = __import__(f"flappy_bird.{module_name}", fromlist=["*"])
        source = inspect.getsource(module)
        assert "pygame.mixer" not in source, module_name

    @pytest.mark.parametrize(
        "module_name",
        ["player", "pipe", "pipe_manager", "collision", "scoring", "visuals"],
    )
    def test_gameplay_modules_do_not_import_audio(self, module_name):
        module = __import__(f"flappy_bird.{module_name}", fromlist=["*"])
        source = inspect.getsource(module)
        assert "audio" not in source, module_name


# --- Game feel ---------------------------------------------------------------


class TestScorePulse:
    def test_it_starts_off(self):
        assert Visuals().score_color() == settings.TEXT_COLOR

    def test_a_point_brightens_the_score(self, game):
        game.render()
        resting = game.visuals.score_color()
        add_passed_pipe(game)
        game.update(DT)
        assert game.visuals.score_color() != resting

    def test_it_decays_back_to_resting(self, game):
        add_passed_pipe(game)
        game.update(DT)
        for _ in range(60):
            game.update(DT)
        assert game.visuals.score_color() == settings.TEXT_COLOR

    def test_it_is_bounded_so_the_text_cache_cannot_grow_forever(self, game):
        game.score = 1
        add_passed_pipe(game)
        game.update(DT)
        for _ in range(30):
            game.render()
            game.update(DT)
        # One rest colour plus SCORE_PULSE_STEPS brighter variants.
        assert len(game.visuals.text) <= settings.SCORE_PULSE_STEPS + 2

    def test_the_score_still_renders_while_pulsing(self, game):
        add_passed_pipe(game)
        game.update(DT)
        game.render()
        assert pygame.image.tostring(game.screen, "RGB")

    def test_pulsing_changes_nothing_about_the_score(self, game):
        add_passed_pipe(game)
        game.update(DT)
        assert game.score == 1
        assert game.player.rect == game.player.rect
