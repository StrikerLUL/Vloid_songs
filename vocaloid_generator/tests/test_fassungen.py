# test_fassungen.py – Off-Vocal, A-cappella, True Peak und ID3-Tags (v6 Nr. 4 und 6)
import os

import numpy as np
import pytest
import soundfile as sf

import mixer
import pipeline
import tags
from settings import SongSettings

LYRICS = "[Verse]\n君[きみ]のこえがきこえる\n\n[Chorus]\nらららら るるる"
MP3_FRAME = b"\xff\xfb\x90\x00" + bytes(400)


def song_settings(tmp_path, root, **kw):
    s = SongSettings(active_sections=["Intro", "Verse", "Chorus"], section_bars={"Intro": 4, "Verse": 4, "Chorus": 4},
                     output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root), singer="MERROW", seed=5,
                     lyrics=LYRICS, harmonies=False, final_choir=False, breaths=False, phrase_expression=False,
                     syllable_dynamics=False, harmony_double=False, sung_pads=False, adlibs=False, polish=False,
                     auto_rating=False)
    return s.with_updates(**kw)


def rms_db(audio: np.ndarray) -> float:
    return 20 * np.log10(np.sqrt(np.mean(audio ** 2)) + 1e-12)


def share_of_the_voice(audio: np.ndarray, rate: int) -> float:
    """Anteil der Energie um 330 Hz: so singt die NEUTRINO-Attrappe (ein Sinus über den ganzen Song)."""
    spectrum = np.abs(np.fft.rfft(audio.mean(axis=1))) ** 2
    freqs = np.fft.rfftfreq(len(audio), 1 / rate)
    return float(spectrum[(freqs > 300) & (freqs < 360)].sum() / spectrum.sum())


@pytest.fixture
def tagged(monkeypatch):
    """MP3s ohne ffmpeg (ein Rahmen genügt) und welche MP3s Tags bekommen."""
    import exporter

    def mp3(wav_pfad, mp3_pfad=None):
        with open(mp3_pfad, "wb") as f:
            f.write(MP3_FRAME)
        return mp3_pfad
    written = []
    monkeypatch.setattr(exporter, "exportiere_song", mp3)
    monkeypatch.setattr(tags, "write", lambda path, result, title="", version="", cover=None: written.append(version))
    return written


def test_a_song_gets_off_vocal_and_a_cappella_as_loud_as_in_the_song(tmp_path, neutrino_attrappe, tagged):
    root, _ = neutrino_attrappe
    s = song_settings(tmp_path, root)
    result = pipeline.generate_song(s, keep_history=False)
    assert result.versions == {kind: os.path.join(result.output_dir, mp3)
                               for kind, (_, mp3, _) in pipeline.VERSIONS.items()}
    assert tagged == ["", "Off Vocal", "A Cappella"]
    full, rate = sf.read(result.mix_wav, always_2d=True)
    off, _ = sf.read(os.path.join(result.output_dir, "final_offvocal.wav"), always_2d=True)
    alone, _ = sf.read(os.path.join(result.output_dir, "final_acappella.wav"), always_2d=True)
    assert len(off) == len(full) == len(alone)
    intro = slice(int(0.5 * rate), int(4 * 4 * 60 / s.bpm * rate) - rate // 2)    # vier Takte ohne Gesang
    assert abs(rms_db(off[intro]) - rms_db(full[intro])) < 1.5        # die Band so laut wie im Song
    assert share_of_the_voice(alone, rate) > 0.8 > share_of_the_voice(full, rate)
    assert share_of_the_voice(off, rate) < 0.05
    assert mixer._loudness(off.T) < mixer._loudness(full.T)
    assert mixer._loudness(alone.T) < mixer._loudness(full.T)


def test_switched_off_there_are_no_versions_and_no_tags(tmp_path, neutrino_attrappe, tagged):
    root, _ = neutrino_attrappe
    s = song_settings(tmp_path, root, vocal_versions=False, id3_tags=False)
    result = pipeline.generate_song(s, keep_history=False)
    assert result.versions == {} and result.mp3 and tagged == []


def test_the_master_keeps_true_peaks_below_minus_one_db():
    rng = np.random.default_rng(1)
    loud = (0.2 * rng.standard_normal((2, mixer.SAMPLE_RATE * 6))).astype(np.float32)
    assert mixer.true_peak_db(mixer._limit_to(loud, -7.0, -0.3)) > mixer.TRUE_PEAK_DB
    assert mixer.true_peak_db(mixer._limit_to(loud, -7.0, -0.3, true_peak=True)) <= mixer.TRUE_PEAK_DB + 0.01
    assert mixer.true_peak_db(mixer.master(loud, target_lufs=-9.0, true_peak=True)) <= mixer.TRUE_PEAK_DB + 0.01


def test_true_peak_sees_the_peak_between_the_samples():
    t = np.arange(mixer.SAMPLE_RATE) / mixer.SAMPLE_RATE
    # ein Sinus auf einem Viertel der Abtastrate, um 45° verschoben: jedes Sample liegt 3 dB unter der Spitze
    tone = (0.5 * np.sin(2 * np.pi * mixer.SAMPLE_RATE / 4 * t + np.pi / 4)).astype(np.float32)[None, :]
    assert 20 * np.log10(np.abs(tone).max()) == pytest.approx(-9.03, abs=0.05)
    assert mixer.true_peak_db(tone) == pytest.approx(-6.02, abs=0.2)


def _fake_result(tmp_path, **kw):
    s = SongSettings(style="Dark Vocaloid", bpm=148, key="F#", scale="minor", lyrics=LYRICS, **kw)
    return pipeline.SongResult(seed=42, output_dir=str(tmp_path), settings=s)


def test_every_mp3_of_the_song_gets_title_lyrics_and_cover(tmp_path):
    from mutagen.id3 import ID3
    mp3 = tmp_path / "final_song.mp3"
    mp3.write_bytes(MP3_FRAME)                                  # ein MP3-Rahmen genügt für die Tags
    result = _fake_result(tmp_path)
    cover = tags.write(str(mp3), result)
    assert cover and cover.endswith("cover.png")
    found = ID3(str(mp3))
    assert str(found["TIT2"]) == "Dark Vocaloid (Seed 42)"
    assert str(found["TPE1"]) == "Vloid Songs feat. MERROW"
    assert (str(found["TCON"]), str(found["TBPM"]), str(found["TKEY"])) == ("Dark Vocaloid", "148", "F#m")
    assert found.getall("USLT")[0].text == "君のこえがきこえる\n\nらららら るるる"
    assert found.getall("APIC")[0].data[:4] == b"\x89PNG"
    off = tmp_path / "final_song_offvocal.mp3"
    off.write_bytes(MP3_FRAME)
    assert tags.write(str(off), result, version="Off Vocal", cover=cover) == cover
    found = ID3(str(off))
    assert str(found["TIT2"]) == "Dark Vocaloid (Seed 42) (Off Vocal)" and not found.getall("USLT")


def test_tags_leave_other_files_alone(tmp_path):
    wav = tmp_path / "final_mix.wav"
    wav.write_bytes(b"RIFF")
    assert tags.write(str(wav), _fake_result(tmp_path)) is None
    assert wav.read_bytes() == b"RIFF"


@pytest.mark.parametrize("engine, enabled, expected", [
    ("NEUTRINO", True, "Vloid Songs feat. MERROW"), ("VOICEVOX", True, "Vloid Songs"),
    ("NEUTRINO", False, "Vloid Songs")])
def test_the_artist_names_the_neutrino_voice(engine, enabled, expected):
    s = SongSettings(vocal_engine=engine)
    s.channels["vocals"].enabled = enabled
    assert tags.artist(s) == expected
