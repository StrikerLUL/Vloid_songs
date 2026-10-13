# test_polish.py – Klang-Veredler (ACE-Step 1.5, hier mit nachgebautem Modell)
import json
import os
import sys

import numpy as np
import pytest
import soundfile as sf

import config
import main
import pipeline
import polish
from mixer import mische_spuren
from settings import SongSettings

sys.path.insert(0, config.REPO_ROOT)
import setup_ace_step  # noqa: E402

RATE = 44100

# Nachgebautes ACE-Step: legt die Vorlage um 40 ms verspätet, leiser und in 48 kHz ab und merkt sich den Auftrag
FAKE_WORKER = '''
import json, os, sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
job = json.load(open(sys.argv[1], encoding="utf-8"))
with open(os.environ["POLISH_SEEN"], "w", encoding="utf-8") as f:
    json.dump({**job, "cwd": os.getcwd(), "root_env": os.environ.get("ACESTEP_PROJECT_ROOT")}, f)
if job.get("probe"):
    print("VEREDELT " + json.dumps({"cuda": True, "name": "RTX 3050 Laptop GPU", "memory_gb": 4.0}))
    sys.exit(0)
if job["caption"] == "kaputt":
    print("CUDA out of memory", file=sys.stderr)
    sys.exit(1)
data, rate = sf.read(job["source"], dtype="float32", always_2d=True)
data = resample_poly(data, 160, 147, axis=0)
data = np.vstack([np.zeros((int(0.04 * 48000), 2), np.float32), data * 0.5])
path = os.path.join(job["folder"], "ace.wav")
sf.write(path, data, 48000)
print("lade Modell ...")
print("VEREDELT " + json.dumps({"path": path}))
'''


def clicks(seconds=6.0, every=0.37):
    """Kurze Anschläge in unregelmäßigem Abstand, damit sich die Lage eindeutig finden lässt."""
    data = np.zeros(int(seconds * RATE), dtype=np.float32)
    t, k = 0.1, 0
    while t < seconds - 0.1:
        start = int(t * RATE)
        data[start:start + 2000] = np.sin(np.arange(2000) * 2 * np.pi * 300 / RATE) * np.linspace(0.6, 0, 2000)
        t += every + 0.05 * (k % 3)
        k += 1
    return np.stack([data, data], axis=1)


@pytest.fixture
def fake_ace_step(tmp_path, monkeypatch):
    os.makedirs(polish.FOLDER, exist_ok=True)
    worker = tmp_path / "worker.py"
    worker.write_text(FAKE_WORKER, encoding="utf-8")
    monkeypatch.setattr(polish, "python", lambda: sys.executable)
    monkeypatch.setattr(polish, "WORKER", str(worker))
    monkeypatch.setenv("POLISH_SEEN", str(tmp_path / "gesehen.json"))
    os.makedirs(polish.source(), exist_ok=True)
    with open(os.path.join(polish.FOLDER, polish.READY_FILE), "w", encoding="utf-8") as f:
        json.dump({"cuda": True, "name": "RTX 3050 Laptop GPU", "memory_gb": 4.0}, f)
    return tmp_path


def seen(tmp_path) -> dict:
    with open(tmp_path / "gesehen.json", encoding="utf-8") as f:
        return json.load(f)


def test_caption_and_key_follow_the_song():
    from song_plan import SongPlan
    s = SongSettings(style="Ballade")
    assert polish.caption(s).startswith("emotional j-pop ballad") and "instrumental" in polish.caption(s)
    assert polish.caption(s.with_updates(polish_caption="  dreamy shoegaze ")) == "dreamy shoegaze"
    assert polish.caption(s.with_updates(style="Unbekannt")).startswith(polish.DEFAULT_CAPTION)
    plan = SongPlan(bpm=120, style=None, tonic=9, mode="dorian", sections=[], progressions={})
    assert polish.key_scale(plan) == "A minor"
    assert polish.key_scale(SongPlan(bpm=120, style=None, tonic=13, mode="major", sections=[], progressions={})) \
        == "C# major"


def test_status_without_and_with_setup(fake_ace_step, monkeypatch):
    assert polish.status() == "Klang-Veredler (ACE-Step) ist eingerichtet: RTX 3050 Laptop GPU, 4 GB"
    assert polish.status(SongSettings(polish=False)) == "Klang-Veredler (ACE-Step): aus"
    monkeypatch.setattr(polish, "python", lambda: str(fake_ace_step / "fehlt" / "python"))
    assert not polish.available() and "setup_ace_step.py ausführen" in polish.status()


def test_the_new_band_is_laid_under_the_old_one(tmp_path):
    ref = clicks()
    sf.write(str(tmp_path / "vorlage.wav"), ref, RATE)
    from scipy.signal import resample_poly
    moved = np.vstack([np.zeros((int(0.065 * 48000), 2)), resample_poly(ref, 160, 147, axis=0)])[:, :1]
    sf.write(str(tmp_path / "ace.wav"), moved, 48000)                                 # später, 48 kHz, mono
    out = polish.fit(str(tmp_path / "ace.wav"), str(tmp_path / "vorlage.wav"), str(tmp_path / "neu.wav"))
    data, rate = sf.read(out)
    assert rate == RATE and data.shape == ref.shape
    assert abs(polish.offset(ref.mean(axis=1), data.mean(axis=1), RATE)) <= 2 * (RATE // 1000)
    assert polish.fit(str(tmp_path / "fehlt.wav"), str(tmp_path / "vorlage.wav"), str(tmp_path / "x.wav")) is None


def test_polish_runs_ace_step_in_its_own_folder(fake_ace_step):
    tmp = fake_ace_step
    sf.write(str(tmp / "band.wav"), clicks(), RATE)
    plan = pipeline.compose(SongSettings(output_ordner=str(tmp / "out"), seed=2, active_sections=["Chorus"]))[0]["plan"]
    s = SongSettings(style="Rock", polish_strength=0.3)
    out = polish.polish(str(tmp / "band.wav"), str(tmp / "out" / "band_veredelt.wav"), s, plan, seed=42)
    job = seen(tmp)
    assert job["keep"] == pytest.approx(0.7) and job["seed"] == 42 and job["caption"].startswith("japanese rock")
    assert job["root"] == polish.source() and job["root_env"] == polish.source()
    assert os.path.samefile(job["cwd"], polish.source())
    data, rate = sf.read(out)
    assert rate == RATE and len(data) == len(clicks())
    assert abs(polish.offset(clicks().mean(axis=1), data.mean(axis=1), RATE)) <= 2 * (RATE // 1000)
    assert [f for f in os.listdir(tmp / "out") if f.startswith("veredler_")] == []        # Zwischenordner weg
    log_file = os.path.join(polish.FOLDER, polish.LOG_FILE)
    assert "lade Modell" in open(log_file, encoding="utf-8").read()                     # zum Nachlesen
    assert polish.polish(str(tmp / "band.wav"), str(tmp / "x.wav"), s.with_updates(polish_caption="kaputt"),
                         plan, seed=1) is None
    assert "CUDA out of memory" in open(log_file, encoding="utf-8").read()


def test_the_mixer_swaps_the_band_and_keeps_the_voice(tmp_path):
    t = np.arange(4 * RATE) / RATE

    def stem(name, hz):
        sf.write(str(tmp_path / f"{name}.wav"), np.stack([0.3 * np.sin(2 * np.pi * hz * t)] * 2, axis=1), RATE)
        return str(tmp_path / f"{name}.wav")
    stems = [stem("piano", 220), stem("vocals", 440)]
    band = stem("neue_band", 1000)
    mische_spuren(stems, output_pfad=str(tmp_path / "normal.wav"))
    mische_spuren(stems, output_pfad=str(tmp_path / "veredelt.wav"), band=band)

    def level(path, hz):
        data, _ = sf.read(path)
        spectrum = np.abs(np.fft.rfft(data[RATE:3 * RATE].mean(axis=1)))
        return spectrum[int(hz * 2)]
    normal, swapped = str(tmp_path / "normal.wav"), str(tmp_path / "veredelt.wav")
    assert level(swapped, 220) < 0.05 * level(normal, 220)                    # das alte Klavier ist weg
    assert level(swapped, 1000) > 10 * level(normal, 1000)                    # die neue Band ist da
    assert level(swapped, 440) == pytest.approx(level(normal, 440), rel=0.35)  # der Gesang bleibt


@pytest.fixture
def song(tmp_path, monkeypatch):
    # Statt der lokalen Vorschau-Stimme ein Ton: die Windows-Sprachausgabe wartet in der CI ohne angemeldeten
    # Benutzer ewig (siehe test_vocals.py)
    def sing(settings, tracks, wav):
        t = np.arange(4 * RATE) / RATE
        sf.write(wav, 0.2 * np.sin(2 * np.pi * 440 * t), RATE)
        return True
    monkeypatch.setattr(pipeline, "_sing_preview", sing)
    return SongSettings(output_ordner=str(tmp_path / "out"), seed=4, active_sections=["Chorus"],
                        section_bars={"Chorus": 2})


def test_the_song_gets_a_second_polished_version(song, fake_ace_step):
    result = pipeline.generate_song(song, keep_history=False)
    out = result.output_dir
    assert result.polished_wav == os.path.join(out, "final_mix_veredelt.wav")
    assert os.path.exists(result.polished_wav) and os.path.exists(result.mix_wav)
    assert sf.info(result.polished_wav).frames == sf.info(result.mix_wav).frames
    assert os.path.exists(os.path.join(out, "band_veredelt.wav"))
    assert not os.path.exists(os.path.join(out, "band_vorlage.wav"))
    plan = pipeline.compose(song)[0]["plan"]
    assert seen(fake_ace_step)["key"] == polish.key_scale(plan)
    # ausgeschaltet: die alte veredelte Fassung gilt nicht mehr
    stems = list(result.wav_files.values())
    pipeline._polish(song.with_updates(polish=False), {"plan": plan}, result, stems, {}, lambda f, m: None)
    assert not os.path.exists(os.path.join(out, "final_mix_veredelt.wav"))
    assert not os.path.exists(os.path.join(out, "band_veredelt.wav"))


def test_without_setup_nothing_is_polished(song, tmp_path, monkeypatch):
    import mixer
    assert not polish.available()
    monkeypatch.setattr(mixer, "mische_spuren", lambda *a, **kw: pytest.fail("ohne ACE-Step wird nichts gemischt"))
    result = pipeline.SongResult(seed=1, output_dir=str(tmp_path), wav_files={"piano": str(tmp_path / "piano.wav")})
    pipeline._polish(song, {"plan": object()}, result, [], {}, lambda f, m: None)
    assert result.polished_wav is None


def test_cli_polish_options(song, monkeypatch, tmp_path):
    seen_settings = []
    monkeypatch.setattr(main, "generate_song", lambda settings, progress=None: seen_settings.append(settings) or
                        pipeline.SongResult(seed=1, output_dir=str(tmp_path), settings=settings))
    song.save()
    assert main.main(["--veredler-staerke", "0.6", "--veredler-klang", "dream pop"]) == 0
    assert (seen_settings[-1].polish, seen_settings[-1].polish_strength, seen_settings[-1].polish_caption) == \
        (True, 0.6, "dream pop")
    assert main.main(["--ohne-veredler"]) == 0
    assert seen_settings[-1].polish is False


def test_setup_installs_downloads_and_probes(fake_ace_step, monkeypatch):
    calls = []
    os.remove(os.path.join(polish.FOLDER, polish.READY_FILE))
    os.makedirs(polish.source(), exist_ok=True)
    open(os.path.join(polish.source(), "pyproject.toml"), "w").close()
    monkeypatch.setattr(setup_ace_step.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(setup_ace_step, "_platz_frei", lambda: 50.0)
    monkeypatch.setattr(setup_ace_step, "_ausfuehren", lambda befehl, **kw: calls.append(befehl) or True)
    assert setup_ace_step.setup()
    assert calls[0] == ["/bin/uv", "sync"] and "acestep.model_downloader" in calls[1]
    assert polish.status() == "Klang-Veredler (ACE-Step) ist eingerichtet: RTX 3050 Laptop GPU, 4 GB"


def test_setup_stops_without_uv_space_or_working_model(fake_ace_step, monkeypatch):
    os.remove(os.path.join(polish.FOLDER, polish.READY_FILE))
    monkeypatch.setattr(polish, "python", lambda: str(fake_ace_step / "noch_nicht" / "python"))
    monkeypatch.setattr(setup_ace_step.shutil, "which", lambda name: None)
    assert not setup_ace_step.setup()
    monkeypatch.setattr(setup_ace_step.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(setup_ace_step, "_platz_frei", lambda: 5.0)
    assert not setup_ace_step.setup()
    monkeypatch.setattr(setup_ace_step, "_platz_frei", lambda: 50.0)
    monkeypatch.setattr(setup_ace_step, "quelle_holen", lambda: True)
    monkeypatch.setattr(setup_ace_step, "_ausfuehren", lambda befehl, **kw: True)
    monkeypatch.setattr(setup_ace_step, "probe", lambda: {})
    assert not setup_ace_step.setup() and not polish.available()


def test_the_zip_is_unpacked_without_its_top_folder(tmp_path):
    import zipfile
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("ACE-Step-1.5-abc/pyproject.toml", "[project]")
        z.writestr("ACE-Step-1.5-abc/acestep/__init__.py", "")
    setup_ace_step._entpacken(str(archive), str(tmp_path / "ACE-Step-1.5"))
    assert sorted(os.listdir(tmp_path / "ACE-Step-1.5")) == ["acestep", "pyproject.toml"]
    with zipfile.ZipFile(tmp_path / "boese.zip", "w") as z:
        z.writestr("x/../../ausbruch.txt", "")
    with pytest.raises(ValueError):
        setup_ace_step._entpacken(str(tmp_path / "boese.zip"), str(tmp_path / "anders"))
