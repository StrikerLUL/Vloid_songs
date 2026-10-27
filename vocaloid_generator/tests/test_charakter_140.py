# test_charakter_140.py – Charakter 1.4.0: Akkorde, Melodie, Arrangement und Klangbild je Stil, ein eigenes Gesicht
# für jeden Song (style_dna.py, song_character.py)
import logging
import random

import numpy as np
import soundfile as sf

import config
import mixdown
import mixer
import pipeline
import song_character
import style_dna
from melody_writer import SectionMelodyWriter, _interval_costs
from settings import SongSettings
from song_plan import build_plan
from styles import STYLES, get_style

RATE = 44100
STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Outro"]


def _plan(style: str, own_chords: bool, mode: str = "major", seed: int = 5):
    return build_plan(get_style(style), 120, STRUCTURE, "C", mode, config.SECTION_CONFIG, random.Random(seed), {},
                      own_chords=own_chords)


def _vocal(tracks) -> list:
    return [(round(n.start, 3), n.pitch, round(n.end, 3)) for n in tracks["vocal_melody"]]


def _band(tracks) -> dict:
    return {key: [(round(n.start, 3), n.pitch, n.velocity, round(n.end, 3)) for n in value]
            for key, value in tracks.items()
            if key not in ("vocal_melody", "plan") and isinstance(value, list) and value and hasattr(value[0], "pitch")}


def test_every_style_has_its_own_dna():
    for style in STYLES:
        for mode in ("major", "minor"):
            assert style_dna.progressions(style, mode, "Chorus"), (style, mode)
            assert style_dna.cadences(style, mode)["to_chorus"], (style, mode)
        assert style_dna.character(style) is not style_dna.NEUTRAL, style
        assert style in style_dna.STYLE_SOUNDS, style
    # Intro, Outro und Drop spielen den Refrain an, alles andere ohne eigene Folge die Strophe
    assert style_dna.progressions("Rock", "major", "Outro") == style_dna.progressions("Rock", "major", "Chorus")
    assert style_dna.progressions("Rock", "major", "Solo") == style_dna.progressions("Rock", "major", "Verse")


def test_each_style_has_its_own_chords_and_cadences(new_140, tmp_path):
    rock, city = _plan("Rock", True), _plan("City Pop", True)
    assert rock.progressions["Chorus"] in style_dna.progressions("Rock", "major", "Chorus")
    assert city.progressions["Chorus"] in style_dna.progressions("City Pop", "major", "Chorus")
    assert rock.progressions["Chorus"] != city.progressions["Chorus"]
    # die Kadenz in den Refrain: Rock landet auf der Dominante, die Ballade auf Vsus4 und V
    pre = next(sec for sec in rock.sections if sec.kind == "PreChorus")
    assert pre.chords[-1].chord.root == 7
    ballad = _plan("Ballade", True)
    pre = next(sec for sec in ballad.sections if sec.kind == "PreChorus")
    assert [slot.chord.root for slot in pre.chords[-2:]] == [7, 7]
    # aus: dieselben Folgen wie bis 1.3
    assert _plan("Rock", False).progressions == build_plan(
        get_style("Rock"), 120, STRUCTURE, "C", "major", config.SECTION_CONFIG, random.Random(5), {}).progressions
    s = SongSettings(output_ordner=str(tmp_path), seed=7, style="Rock")
    on, _ = pipeline.compose(s)
    off, _ = pipeline.compose(s.with_updates(style_chords=False))
    assert on["plan"].progressions != off["plan"].progressions


def test_each_style_sings_with_its_own_melody_character(new_140, tmp_path):
    kawaii, ballad = style_dna.character("Kawaii Chiptune"), style_dna.character("Ballade")
    assert kawaii.staccato > ballad.staccato and kawaii.density > ballad.density
    # die Ballade geht lieber in Schritten, Kawaii springt in Terzen und Quarten
    assert _interval_costs(ballad)[2] < _interval_costs(kawaii)[2]
    assert _interval_costs(kawaii)[4] < _interval_costs(ballad)[4]
    assert style_dna.rhythm_fit((0, 8), "long") > style_dna.rhythm_fit((0, 3, 6, 10), "long")
    assert style_dna.rhythm_fit((0, 3, 6, 10), "syncopated") > style_dna.rhythm_fit((0, 4, 8, 12), "syncopated")
    assert style_dna.rhythm_fit((2, 6, 10, 12), "laid_back") > style_dna.rhythm_fit((0, 4, 8, 12), "laid_back")

    s = SongSettings(output_ordner=str(tmp_path), seed=3, style="Kawaii Chiptune")
    on, _ = pipeline.compose(s)
    off, _ = pipeline.compose(s.with_updates(melody_character=False))
    assert _vocal(on) != _vocal(off)

    def short(tracks) -> float:
        notes = sorted(tracks["vocal_melody"], key=lambda n: n.start)
        beat = 60.0 / s.bpm
        return sum(1 for a, b in zip(notes, notes[1:]) if a.end - a.start < 0.6 * (b.start - a.start) < beat) \
            / len(notes)
    assert short(on) > short(off), "Kawaii singt kurz und abgesetzt"


def test_the_melody_writer_without_character_writes_as_before():
    plan = _plan("J-Pop Energy", False)
    verse = next(sec for sec in plan.sections if sec.kind == "Verse")
    words = ["ら"] * 24
    plain = SectionMelodyWriter(plan, verse, random.Random(1), None, {}).write(words)
    again = SectionMelodyWriter(plan, verse, random.Random(1), None, {}).write(words)
    styled = SectionMelodyWriter(plan, verse, random.Random(1), None, {"melody_character": True}).write(words)
    assert [(n.start, n.pitch, n.dur) for n in plain] == [(n.start, n.pitch, n.dur) for n in again]
    assert [(n.start, n.pitch, n.dur) for n in plain] != [(n.start, n.pitch, n.dur) for n in styled]


def test_each_style_arranges_its_sections(new_140, tmp_path):
    rock = style_dna.arranged(get_style("Rock").parts, "Rock")
    assert rock["PreChorus"]["guitar"] == "palm_mute" and rock["Chorus"]["guitar"] == "power_chords"
    assert rock["Bridge"]["guitar"] == "power_chords" and rock["Verse:2"]["counter"] is None
    ballad = style_dna.arranged(get_style("Ballade").parts, "Ballade")
    assert ballad["Chorus"]["guitar"] is None and ballad["Chorus"]["synth"] is None
    assert get_style("Ballade").part("Chorus", "guitar") and \
        get_style("Ballade").part("Chorus", "piano") == ballad["Chorus"]["piano"]
    assert style_dna.arranged(get_style("Rock").parts, "Unbekannt") == get_style("Rock").parts
    s = SongSettings(output_ordner=str(tmp_path), seed=4, style="Rock", song_character=False)
    on, _ = pipeline.compose(s)
    off, _ = pipeline.compose(s.with_updates(style_arrangement=False))
    assert _band(on) != _band(off)


def test_each_song_gets_its_own_character_from_the_seed(new_140, tmp_path, caplog):
    faces = {song_character.choose("City Pop", str(seed)).describe() for seed in range(8)}
    assert len(faces) >= 6, "acht Songs eines Stils sehen fast alle anders aus"
    assert song_character.choose("Rock", "5") == song_character.choose("Rock", "5")
    face = song_character.choose("City Pop", "5")
    profile = song_character.apply(get_style("City Pop"), face)
    assert all(profile.programs[inst] == program for inst, program in face.programs.items())
    assert "Charakter" not in face.describe() and "Intro" in face.describe()

    s = SongSettings(output_ordner=str(tmp_path), seed=12, style="City Pop")
    with caplog.at_level(logging.INFO, logger="orchestrator"):
        on, _ = pipeline.compose(s)
    assert "Charakter: " in caplog.text and on.get("voices") is not None
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="orchestrator"):
        off, _ = pipeline.compose(s.with_updates(song_character=False))
    assert "Charakter: " not in caplog.text and "voices" not in off
    assert _band(on) != _band(off)


def test_the_song_ends_ringing_stopping_or_fading():
    plan = _plan("Rock", True)
    last = plan.sections[-1]

    class Ev:
        def __init__(self, start, dur, vel=100):
            self.start, self.dur, self.vel = start, dur, vel

    def events():
        return {"piano": [Ev(last.start, 1.0), Ev(last.end - last.bar_beats, 4.0)], "drums": [Ev(last.end - 4, 4.0)]}
    face = song_character.Character(ending="stop")
    stopped = events()
    assert song_character.finish(plan, stopped, face, ("drums",)) == "harter Stopp"
    assert stopped["piano"][1].dur == song_character.STOP_BEATS and stopped["drums"][0].dur == 4.0
    faded = events()
    assert song_character.finish(plan, faded, song_character.Character(ending="fade"), ("drums",)) == "wird leiser"
    assert faded["piano"][1].vel < faded["piano"][0].vel <= 100
    ringing = events()
    assert song_character.finish(plan, ringing, song_character.Character(ending="ring"), ("drums",)) == ""
    assert ringing["piano"][1].dur == 4.0


def _stems(tmp_path) -> list:
    t = np.arange(3 * RATE) / RATE
    clicks = np.zeros_like(t)
    clicks[:int(1.5 * RATE):RATE // 2] = 0.8
    paths = []
    for name, audio in (("drums", clicks), ("piano", 0.2 * np.sin(2 * np.pi * 220 * t) * (t < 1.0)),
                        ("vocals", 0.2 * np.sin(2 * np.pi * 440 * t) * (t < 1.5))):
        paths.append(str(tmp_path / f"{name}.wav"))
        sf.write(paths[-1], audio.astype(np.float32), RATE)
    return paths


def test_each_style_has_its_own_room_and_color(new_140, tmp_path):
    ballad, rock, lofi = style_dna.sound("Ballade"), style_dna.sound("Rock"), style_dna.sound("Lo-Fi")
    assert ballad.room > rock.room and ballad.hall_gain > rock.hall_gain
    assert lofi.high_db < 0 < style_dna.sound("City Pop").high_db and lofi.width < 1 < ballad.width
    assert "Raum" in ballad.describe()
    s = SongSettings(output_ordner=str(tmp_path), style="Ballade")
    tracks = {"plan": None}
    on = mixdown.mix_arguments(s, tracks, str(tmp_path), has_vocals=True)
    off = mixdown.mix_arguments(s.with_updates(style_sound=False), tracks, str(tmp_path), has_vocals=True)
    assert on["sound"] is ballad and off["sound"] is None

    def mixed(sound, name):
        out = str(tmp_path / name)
        mixer.mische_spuren(_stems(tmp_path), output_pfad=out, bpm=120, sound=sound)
        audio, _ = sf.read(out)
        return audio
    plain, big, small = mixed(None, "ohne.wav"), mixed(ballad, "ballade.wav"), mixed(rock, "rock.wav")
    assert not np.allclose(plain, big) and not np.allclose(big, small)
    # nach dem letzten Ton (ab 2 s) klingt der große Raum der Ballade länger nach als der kurze des Rocks

    def tail(audio):
        return float(np.sqrt(np.mean(audio[int(2.2 * RATE):int(2.45 * RATE)] ** 2)))
    assert tail(big) > tail(small)
