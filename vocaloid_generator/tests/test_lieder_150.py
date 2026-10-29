# test_lieder_150.py – Songs 1.5.0: „Wie dieser Song“ (vorbild_ablauf.py)
import os

import numpy as np
import pytest
import soundfile as sf

import pipeline
import reference
import vorbild_ablauf
from settings import ReferenceTrack, SongSettings

RATE = 22050
BPM = 120
TONIC = 2                                                   # D-Dur
VERSE = [(9, True), (5, False), (0, False), (7, False)]     # vi IV I V
PRE = [(2, True), (7, False)]                               # ii V
CHORUS = [(5, False), (7, False), (4, True), (9, True)]     # IV V iii vi
INTRO = [(0, False), (7, False)]                            # I V
SONG = [("Intro", 4, INTRO, 0.25), ("Verse", 8, VERSE, 0.4), ("PreChorus", 4, PRE, 0.55), ("Chorus", 8, CHORUS, 1.0),
        ("Verse", 8, VERSE, 0.4), ("PreChorus", 4, PRE, 0.55), ("Chorus", 8, CHORUS, 1.0), ("Outro", 4, INTRO, 0.25)]


def _tone(freq: float, n: int, amp: float) -> np.ndarray:
    t = np.arange(n) / RATE
    return amp * np.sin(2 * np.pi * freq * t) * np.minimum(1, t * 50) * np.exp(-t * 0.8)


def write_song(path: str) -> str:
    """Ein Song mit bekanntem Ablauf: Akkorde als Sinus-Töne, Bass auf jedem Schlag, Bassdrum auf 1 und 3, im Refrain
    lauter und mit Hi-Hats."""
    beat = 60 / BPM
    rng = np.random.default_rng(0)
    out = []
    for _, bars, chords, energy in SONG:
        for b in range(bars):
            degree, minor = chords[b % len(chords)]
            root = (TONIC + degree) % 12
            bar = np.zeros(int(4 * beat * RATE))
            for pc in (root, (root + (3 if minor else 4)) % 12, (root + 7) % 12):
                for octave in (4, 5):
                    bar += _tone(440 * 2 ** ((pc + 12 * octave - 57) / 12), len(bar), 0.08 * energy)
            for k in range(4):
                start, n = int(k * beat * RATE), int(beat * RATE)
                bar[start:start + n] += _tone(440 * 2 ** ((root - 33) / 12), n, 0.25 * energy)
                if k in (0, 2):
                    t = np.arange(int(0.15 * RATE)) / RATE
                    kick = np.sin(2 * np.pi * (50 + 80 * np.exp(-t * 30)) * t) * np.exp(-t * 20)
                    bar[start:start + len(kick)] += kick * (0.9 if k == 0 else 0.6) * (0.5 + energy / 2)
                if energy > 0.8:
                    for half in (0.0, 0.5):
                        at = int((k + half) * beat * RATE)
                        hat = rng.normal(0, 0.15, int(0.03 * RATE)) * np.exp(-np.arange(int(0.03 * RATE)) / RATE * 100)
                        bar[at:at + len(hat)] += hat
            out.append(bar)
    y = np.concatenate(out)
    sf.write(path, y / np.abs(y).max() * 0.8, RATE)
    return path


@pytest.fixture(scope="module")
def song(tmp_path_factory):
    return write_song(str(tmp_path_factory.mktemp("vorbild") / "vorbild.wav"))


def test_like_this_song_measures_tempo_key_structure_and_chords(song):
    template = vorbild_ablauf.measure(song, use_cache=False)
    assert template.bpm == BPM and (template.key, template.scale) == ("D", "major")
    assert template.structure() == [kind for kind, *_ in SONG]
    assert [p.bars for p in template.parts] == [bars for _, bars, *_ in SONG]
    chords = template.custom_chords()
    assert chords["Verse"] == "vi | IV | I | V" and chords["Chorus"] == "IV | V | iii | vi"
    assert chords["PreChorus"] == "ii | V"
    assert template.parts[3].start == pytest.approx(32.0, abs=0.1)


def test_the_template_is_cached_and_fits_slow_songs(song, monkeypatch):
    first = vorbild_ablauf.measure(song)
    import librosa
    monkeypatch.setattr(librosa, "load", lambda *a, **k: (_ for _ in ()).throw(AssertionError("nicht neu messen")))
    again = vorbild_ablauf.measure(song)
    assert again.custom_chords() == first.custom_chords() and again.structure() == first.structure()
    # unter 100 BPM halbiert der Song-Plan lange Sektionen, die Vorlage gleicht das aus
    assert first.section_bars()["Chorus"] == 8 and first.section_bars(bpm=80)["Chorus"] == 16
    assert first.section_bars(bpm=80)["Intro"] == 8 and first.section_bars(bpm=80)["PreChorus"] == 8


def test_loops_are_found_or_the_first_eight_bars_kept():
    assert vorbild_ablauf.loop([["I"], ["V"]] * 4) == [["I"], ["V"]]
    assert vorbild_ablauf.loop([["vi"], ["IV"], ["I"], ["V"]] * 3 + [["vi"], ["IV"], ["I"], ["V7"]]) == \
        [["vi"], ["IV"], ["I"], ["V"]]
    odd = [[c] for c in "I ii iii IV V vi I V IV I".split()]
    assert vorbild_ablauf.loop(odd) == odd[:8]
    assert vorbild_ablauf._roman(vorbild_ablauf._TEMPLATES.index((10, "min")), 2) == "bvi"
    assert vorbild_ablauf._roman(vorbild_ablauf._TEMPLATES.index((0, "maj")), 2) == "bVII"


def test_from_references_takes_structure_and_chords_only_with_the_switch(song, monkeypatch, tmp_path):
    summary = reference.Summary(bpm=BPM, key="D", scale="major", style="J-Pop Energy", contrast_db=4.0, vocal_db=-3.0,
                                names=[os.path.basename(song)])
    monkeypatch.setattr(reference, "summarize", lambda *a: summary)
    s = SongSettings(output_ordner=str(tmp_path), reference_tracks=[ReferenceTrack(path=song)],
                     custom_chords={"Bridge": "IV | V"})
    taken = pipeline.from_references(s)
    assert taken.active_sections == [kind for kind, *_ in SONG]
    assert taken.custom_chords["Chorus"] == "IV | V | iii | vi" and taken.custom_chords["Bridge"] == "IV | V"
    assert taken.section_bars["Verse"] == 8
    kept = pipeline.from_references(s.with_updates(ref_structure=False))
    assert kept.active_sections == s.active_sections and kept.custom_chords == s.custom_chords
    # der Song spielt danach genau diesen Ablauf mit diesen Akkorden
    tracks, _ = pipeline.compose(taken.with_updates(seed=3))
    plan = tracks["plan"]
    assert [sec.kind for sec in plan.sections] == taken.active_sections
    chorus = next(sec for sec in plan.sections if sec.kind == "Chorus")
    assert [slot.chord.root for slot in chorus.chords[:4]] == [7, 9, 6, 11]       # G A F#m Bm in D


def test_a_reference_too_short_gives_no_template(tmp_path):
    short = str(tmp_path / "kurz.wav")
    sf.write(short, np.zeros(RATE * 5, dtype=np.float32), RATE)
    assert vorbild_ablauf.for_references([ReferenceTrack(path=short)]) is None
    assert vorbild_ablauf.for_references([]) is None


# ── S2 wichtige Wörter, S3 Ohrwurm ─────────────────────────────────────────────────
def _sung(text: str, pitches: list, durs: list, start: float = 0.0, strong=None) -> list:
    """MelNotes für Moren mit Wortanfang: text wie "なみだが|すき" (| trennt Wörter, Partikel hängen am Wort)."""
    from lyrics import Mora
    from melody_writer import MelNote
    morae = []
    for word in text.split("|"):
        morae += [Mora(m, word_start=i == 0) for i, m in enumerate(word)]
    out, t = [], start
    for i, (m, p, d) in enumerate(zip(morae, pitches, durs)):
        out.append(MelNote(t, d, p, m, strong=(strong or (lambda k, t: t % 1 == 0))(i, t)))
        t += d
    return out


def test_the_key_word_of_the_chorus_should_sit_high_or_long_on_the_beat():
    import melody_score
    text = "きみと|いま|きみと"
    high = _sung(text, [72, 71, 69, 65, 67, 72, 71, 69], [1.0, 0.5, 0.5, 0.5, 0.5, 1.0, 0.5, 0.5])
    low = _sung(text, [60, 62, 64, 71, 72, 60, 62, 64], [0.5] * 8, start=0.5)
    assert melody_score.key_word(melody_score.words(high)) == "きみと"
    assert melody_score._key_words(high, "Chorus") > melody_score._key_words(low, "Chorus")
    feel_long = _sung("なみだ|ふる", [64, 65, 67, 65, 64], [0.5, 0.5, 2.0, 0.5, 0.5])
    feel_short = _sung("なみだ|ふる", [64, 65, 67, 65, 64], [0.5, 0.5, 0.5, 0.5, 0.5])
    assert melody_score._key_words(feel_long, "Verse") > melody_score._key_words(feel_short, "Verse")
    # aus zählt es nicht
    assert melody_score.parts(low, "Chorus")["words"] == 0.0
    assert melody_score.parts(low, "Chorus", extras=("key_words",))["words"] < 0


def test_a_catchy_chorus_repeats_its_first_phrase_with_a_small_change():
    import melody_score
    from melody_writer import MelNote
    phrase = [(0, 67), (0.5, 69), (1, 71), (1.5, 72), (2, 71)]
    def build(second):
        return [MelNote(t, 0.5, p) for t, p in phrase] + [MelNote(4 + t, 0.5, p) for t, p in second]
    varied = build([(0, 67), (0.5, 69), (1, 71), (1.5, 74), (2, 72)])       # gleich bis auf das Ende
    other = build([(0, 74), (0.75, 72), (1.25, 69), (2.5, 64), (3, 62)])    # ganz anders
    assert melody_score._catchy(varied) > melody_score._catchy(other)
    assert melody_score.parts(varied, "Chorus", extras=("catchy_chorus",))["catchy"] > 0
    assert melody_score.parts(varied, "Verse", extras=("catchy_chorus",))["catchy"] == 0.0
    assert melody_score.parts(varied, "Chorus")["catchy"] == 0.0


def test_the_best_melody_puts_key_words_up_and_is_catchier_with_the_switches(new_150, tmp_path, monkeypatch):
    import melody_score
    real = melody_score.pick
    chosen = []

    def spy(candidates, kind, *rest):
        found = real(candidates, kind, *rest)
        if kind == "Chorus":
            best = candidates[found[0]]
            sung = sorted((n for n in best if not getattr(n.syllable, "melisma", False)), key=lambda n: n.start)
            chosen.append((melody_score._key_words(best, kind), melody_score._catchy(sung)))
        return found
    monkeypatch.setattr(melody_score, "pick", spy)

    def mean(**switches):
        chosen.clear()
        for seed in range(1, 6):
            s = SongSettings(output_ordner=str(tmp_path), seed=seed, active_sections=["Verse", "PreChorus", "Chorus"],
                             **switches)
            pipeline.compose(s)
        return [sum(c[i] for c in chosen) / len(chosen) for i in (0, 1)]
    words_on, catchy_on = mean()
    words_off, _ = mean(key_words=False)
    _, catchy_off = mean(catchy_chorus=False)
    assert words_on > words_off + 0.3
    assert catchy_on >= catchy_off


# ── S5 Refrains steigern sich ─────────────────────────────────────────────────────
def test_the_first_chorus_is_leaner_and_the_last_has_everything(new_150, tmp_path):
    s = SongSettings(output_ordner=str(tmp_path), seed=6, style="Hyperpop", song_character=False,
                     active_sections=["Verse", "Chorus", "Verse", "Chorus", "Chorus"])
    on, _ = pipeline.compose(s)
    off, _ = pipeline.compose(s.with_updates(chorus_lift=False))
    plan = on["plan"]
    spb = 60.0 / s.bpm
    choruses = [sec for sec in plan.sections if sec.kind == "Chorus"]
    first, last = choruses[0], choruses[-1]

    def count(tracks, inst, sec, part=1.0):
        return sum(1 for n in tracks[inst] if sec.start <= n.start / spb < sec.start + (sec.end - sec.start) * part)
    assert count(off, "counter", first, 0.5) > 0 and count(on, "counter", first, 0.5) == 0
    assert count(on, "counter", first) > 0, "die Antwort-Melodie kommt in der zweiten Hälfte"
    layers = sum(count(on, inst, last, 0.5) - count(off, inst, last, 0.5) for inst in ("strings", "synth", "piano"))
    assert layers > 0, "Oktave schon in der ersten Hälfte des letzten Refrains"
    crashes = lambda t: sum(1 for n in t["drums"] if n.pitch == 49 and last.start <= n.start / spb < last.end)  # noqa
    assert crashes(on) > crashes(off)
