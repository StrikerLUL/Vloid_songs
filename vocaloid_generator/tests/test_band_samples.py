# test_band_samples.py – Flügel, E-Bass und E-Gitarre aus echten Aufnahmen und ihr Download (v6 Nr. 3)
import os
import sys

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import band_library
import config
import einrichten
import guitar_amp
import rendering
import sfz
import systemcheck
from mixer import midi_zu_wav
from settings import SongSettings
from test_samples import RATE, note, peak_hz, tone, write_sfz

sys.path.insert(0, config.REPO_ROOT)
import setup_band  # noqa: E402

BAND = {band_library.PIANO: 440.0, band_library.BASS: 110.0, band_library.GUITAR: 660.0}


def fake_band(files=BAND):
    """SFZ-Dateien unter den Namen der echten; jede spielt einen eigenen Sinuston, egal welche Note."""
    for name, hz in files.items():
        tone(os.path.join(band_library.FOLDER, "rec", f"{hz:.0f}.wav"), hz, seconds=3.0)
        write_sfz(band_library.path(name), f"<region> sample=rec/{hz:.0f}.wav lokey=21 hikey=108 "
                                           "pitch_keycenter=60 pitch_keytrack=0 ampeg_release=0.1")


def track(program, *notes, bends=()):
    inst = pretty_midi.Instrument(program=program, name="Spur")
    inst.notes = list(notes)
    inst.pitch_bends = [pretty_midi.PitchBend(value, time) for time, value in bends]
    return inst


def _midi(tmp_path, *instruments):
    pm = pretty_midi.PrettyMIDI()
    pm.instruments = list(instruments)
    path = str(tmp_path / "band.mid")
    pm.write(path)
    return path


# ── sfz.py: Slides und eigene SFZ-Dateien ───────────────────────────────────────────

def test_written_sfz_files_read_back_the_same(tmp_path):
    regions = [sfz.Region(sample=str(tmp_path / "Samples" / "D#1v8.flac"), lokey=26, hikey=28, keycenter=27,
                          lovel=51, hivel=64, veltrack=30.0, release=0.45),
               sfz.Region(sample=str(tmp_path / "sustain" / "Bass leise.wav"), lokey=21, hikey=26, keycenter=25,
                          lorand=0.5, seq_length=2, seq_position=2, tune=-7.5)]
    path = str(tmp_path / "Eigen.sfz")
    sfz.write(path, regions, "zwei Zeilen\nKommentar")
    assert sfz.parse(path) == regions
    assert not os.path.exists(path + ".tmp")


def test_pitch_bends_slide_into_the_note(tmp_path):
    tone(tmp_path / "a3.wav", 220.0, lead=0.0)
    instrument = sfz.Instrument(write_sfz(tmp_path / "bass.sfz", "<region> sample=a3.wav key=57 ampeg_release=0.05"))
    plain = sfz.render(instrument, [note(57, 0.0, 1.0)])
    slid = sfz.render(instrument, [note(57, 0.0, 1.0)], bends=[(0.0, -2.0), (0.4, 0.0)])
    assert peak_hz(plain, 0.05, 0.35) == pytest.approx(220, abs=5)
    assert peak_hz(slid, 0.05, 0.35) == pytest.approx(220 * 2 ** (-2 / 12), abs=5)    # zwei Halbtöne darunter
    assert peak_hz(slid, 0.5, 0.95) == pytest.approx(220, abs=5)                      # dann auf dem Ton
    before = sfz.render(instrument, [note(57, 1.0, 2.0)], bends=[(0.0, -2.0), (0.5, 0.0)])
    assert peak_hz(before, 1.1, 1.9) == pytest.approx(220, abs=5)        # ein Bend vor dem Ton ist schon vorbei


# ── band_library.py ─────────────────────────────────────────────────────────────────

def test_piano_bass_and_clean_guitar_play_from_the_recordings():
    fake_band()
    for program, hz in ((0, 440), (1, 440), (33, 110), (34, 110), (26, 660), (27, 660)):
        inst = track(program, note(60, 0.0, 0.8))
        assert band_library.covers(inst)
        assert peak_hz(band_library.render(inst), 0.1, 0.7) == pytest.approx(hz, abs=8)
    assert not band_library.covers(track(48, note(60, 0.0, 0.8)))                    # Streicher: VSCO oder SoundFont
    assert not band_library.covers(track(29, note(60, 0.0, 0.8)))                    # verzerrt: über den Verstärker
    drums = track(0, note(36, 0.0, 0.2))
    drums.is_drum = True
    assert not band_library.covers(drums)
    assert not band_library.covers(track(0))                                         # ohne Töne


def test_a_missing_instrument_keeps_playing_from_the_soundfont():
    fake_band({band_library.BASS: 110.0})
    assert band_library.installed() == [band_library.BASS]
    assert not band_library.covers(track(0, note(60, 0.0, 0.8)))
    assert "E-Bass" in band_library.status() and "Flügel" not in band_library.status()


def test_slides_in_the_bass_follow_its_pitch_bends(tmp_path):
    tone(tmp_path / "rec.wav", 110.0, lead=0.0)
    write_sfz(band_library.path(band_library.BASS), f"<region> sample={tmp_path / 'rec.wav'} key=45")
    slid = band_library.render(track(33, note(45, 0.0, 1.0), bends=[(0.0, -8191), (0.4, 0)]))
    assert peak_hz(slid, 0.05, 0.35) == pytest.approx(110 * 2 ** (-2 / 12), abs=4)
    assert peak_hz(slid, 0.5, 0.95) == pytest.approx(110, abs=4)


def test_mixer_takes_the_recordings_and_the_switch_turns_them_off(tmp_path):
    fake_band()
    midi = _midi(tmp_path, track(33, note(40, 0.0, 1.0)))
    midi_zu_wav(midi, str(tmp_path / "an.wav"), band=True)
    midi_zu_wav(midi, str(tmp_path / "aus.wav"), band=False)
    on, _ = sf.read(str(tmp_path / "an.wav"), always_2d=True)
    off, _ = sf.read(str(tmp_path / "aus.wav"), always_2d=True)
    assert peak_hz(on.T, 0.1, 0.9) == pytest.approx(110, abs=5)
    assert peak_hz(off.T, 0.1, 0.9) != pytest.approx(110, abs=5)


def test_distorted_guitars_send_the_recorded_guitar_into_the_amp(tmp_path, monkeypatch):
    fake_band({band_library.GUITAR: 330.0})
    played = []
    real = band_library.render
    monkeypatch.setattr(band_library, "render", lambda inst, rate=RATE: played.append(inst.program) or real(inst, rate))
    drive = track(30, note(52, 0.0, 1.0), note(59, 0.0, 1.0))
    assert guitar_amp.play(drive, config.SOUNDFONT_PFAD, band=True) is not None
    assert played == [guitar_amp.CLEAN_PROGRAM]
    assert guitar_amp.play(drive, config.SOUNDFONT_PFAD, band=False) is not None
    assert played == [guitar_amp.CLEAN_PROGRAM]                           # ausgeschaltet: der SoundFont spielt


def test_pipeline_switch_and_own_soundfont(tmp_path):
    settings = SongSettings()
    assert rendering._render_job(settings, str(tmp_path), "bass")["band"] is True
    assert rendering._render_job(settings.with_updates(band_samples=False), str(tmp_path), "bass")["band"] is False
    own = tmp_path / "eigener.sf2"
    own.write_bytes(b"RIFF" + bytes(64))
    assert rendering._render_job(settings.with_updates(soundfont_pfad=str(own)), str(tmp_path), "bass")["band"] is False
    assert "band_library.py" in rendering.RENDER_CODE


def test_wizard_and_system_check_know_the_band(tmp_path):
    component = einrichten.find("band")
    assert component.script == "setup_band.py" and not einrichten.is_installed(component)
    assert systemcheck.check_band(SongSettings(), str(tmp_path)) == \
        (None, "Flügel, Bass und Gitarre aus Aufnahmen nicht geladen")
    assert "setup_band.py" in band_library.status()
    fake_band()
    assert einrichten.is_installed(component)
    ok, message = systemcheck.check_band(SongSettings(), str(tmp_path))
    assert ok and "Flügel" in message and "Gitarre" in message


# ── setup_band.py ───────────────────────────────────────────────────────────────────

PIANO_REGIONS = """
//Notes
<region> region_label=14 tune=$TUNE14 offset_oncc$OFFSET=$OFF14 lokey=59 hikey=61 pitch_keycenter=60 sample=C4$VEL.$EXT
<region> region_label=15 tune=$TUNE15 offset_oncc$OFFSET=$OFF15 lokey=62 hikey=64 pitch_keycenter=63 sample=D#4$VEL.$EXT

//Notes without dampers
<region> region_label=24 tune=$TUNE24 offset_oncc$OFFSET=$OFF24 ampeg_release=3 lokey=89 hikey=91 pitch_keycenter=90 sample=F#6$VEL.$EXT
"""

BASS_SFZ = """
<group> lokey=81 hikey=81 pitch_keycenter=81 ampeg_release=0.300
<region> sample=scrape\\scrape_1_rr1.wav hirand=0.5
<region> sample=scrape\\scrape_1_rr2.wav lorand=0.5
//========================
<group> lokey=44 hikey=46 pitch_keycenter=45 ampeg_release=0.300
"""
BASS_SFZ += "".join(f"<region> sample=sustain\\a2_{layer}_rr{k}.wav {vel} lorand={(k - 1) / 4} hirand={k / 4}\n"
                    for layer, vel in (("p", "hivel=95"), ("f", "lovel=96")) for k in (1, 2, 3, 4))


def _sources(tmp_path, missing=()):
    piano = tmp_path / "quelle" / "klavier"
    write_sfz(piano / "Data" / "region.txt", PIANO_REGIONS)
    for name, _, _ in setup_band.PIANO_LAYERS:
        for n in ("C4", "D#4", "F#6"):
            if f"{n}{name}" not in missing:
                tone(piano / "Samples" / f"{n}{name}.flac", 261.6, seconds=0.2)
    bass = tmp_path / "quelle" / "bass"
    write_sfz(bass / "growlybass_clean.sfz", BASS_SFZ)
    for layer in ("p", "f"):
        for k in (1, 2, 3, 4):
            tone(bass / "sustain" / f"a2_{layer}_rr{k}.wav", 55.0, seconds=0.2)
    return {"klavier": piano.as_uri() + "/", "bass": bass.as_uri() + "/"}


def test_setup_builds_the_piano_from_eight_velocity_layers(tmp_path):
    ziel = tmp_path / "Band"
    assert setup_band.setup(["klavier"], str(ziel), _sources(tmp_path))
    regions = sfz.parse(str(ziel / band_library.PIANO))
    assert len(regions) == 3 * len(setup_band.PIANO_LAYERS)
    layers = sorted({(r.lovel, r.hivel) for r in regions})
    assert layers[0] == (1, 34) and layers[-1] == (113, 127)
    assert all(a[1] + 1 == b[0] for a, b in zip(layers, layers[1:]))          # jeder Anschlag hat eine Schicht
    sharp = next(r for r in regions if r.keycenter == 63 and r.lovel == 51)
    assert os.path.basename(sharp.sample) == "D#4v8.flac" and os.path.isfile(sharp.sample)
    assert sharp.release == setup_band.PIANO_RELEASE and sharp.veltrack == setup_band.VELTRACK
    assert next(r for r in regions if r.keycenter == 90).release == 3.0       # die obersten Töne ohne Dämpfer
    assert "Alexander Holm" in (ziel / "LIZENZ.txt").read_text(encoding="utf-8")
    assert setup_band.hole(setup_band.QUELLEN[0], str(ziel), "file:///gibt/es/nicht/")    # schon da


def test_setup_takes_two_round_robins_without_noises_and_the_bass_an_octave_down(tmp_path):
    ziel = tmp_path / "Band"
    assert setup_band.setup(["bass"], str(ziel), _sources(tmp_path))
    regions = sfz.parse(str(ziel / band_library.BASS))
    assert sorted(os.path.basename(r.sample) for r in regions) == \
        ["a2_f_rr1.wav", "a2_f_rr2.wav", "a2_p_rr1.wav", "a2_p_rr2.wav"]     # keine Kratzer, zwei pro Anschlag
    assert {(r.lokey, r.hikey, r.keycenter) for r in regions} == {(32, 34, 33)}   # A1 klingt auf Taste 33
    soft = sorted((r for r in regions if r.hivel == 95), key=lambda r: r.sample)
    assert [(r.lorand, r.hirand) for r in soft] == [(0.0, 0.5), (0.5, 1.0)]
    assert not (ziel / "Growlybass" / "scrape").exists()
    assert not (ziel / "Growlybass" / "sustain" / "a2_p_rr3.wav").exists()


def test_setup_keeps_the_sfz_file_back_until_all_recordings_are_there(tmp_path):
    ziel = tmp_path / "Band"
    assert not setup_band.setup(["klavier"], str(ziel), _sources(tmp_path, missing=("C4v8",)))
    assert not (ziel / band_library.PIANO).exists()                         # die App nimmt ihn nicht halb
    assert (ziel / "Salamander" / "Samples" / "C4v6.flac").is_file()        # beim nächsten Mal schon da
    assert not setup_band.setup(["orgel"], str(ziel))
