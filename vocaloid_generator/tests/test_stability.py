# test_stability.py – Protokoll, Fehlerbericht, Abbrechen, Weitermachen und ein ganzer Song mit nachgebautem NEUTRINO
import logging
import os
import subprocess
import sys
import threading
import time
import zipfile

import numpy as np
import pytest
import soundfile as sf

import applog
import cancel
import config
import fehlerbericht
import pipeline
import resume
import vocal_synthesizer
from settings import SongSettings

SLEEP = [sys.executable, "-c", "import time; time.sleep(30)"]


# ── Abbrechen ───────────────────────────────────────────────────────────────────
def test_run_returns_like_subprocess_run():
    done = cancel.run([sys.executable, "-c", "import sys; print('hallo'); sys.exit(3)"], capture_output=True,
                      text=True)
    assert done.returncode == 3 and done.stdout.strip() == "hallo"
    fed = cancel.run([sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"], capture_output=True,
                     input_bytes=b"abc")
    assert fed.stdout.strip() == b"ABC"


def test_cancel_kills_a_running_program_at_once():
    threading.Timer(0.5, cancel.request).start()
    started = time.monotonic()
    with pytest.raises(cancel.Cancelled):
        cancel.run(SLEEP)
    assert time.monotonic() - started < 10
    with pytest.raises(cancel.Cancelled):          # bis zum nächsten reset() startet nichts Neues
        cancel.run(SLEEP)
    cancel.reset()
    assert not cancel.requested()


def test_run_times_out():
    with pytest.raises(subprocess.TimeoutExpired):
        cancel.run(SLEEP, timeout=0.5)


def test_stream_passes_every_line_and_the_exit_code():
    lines = []
    code = cancel.stream([sys.executable, "-c", "import sys; print('eins'); print('zwei', file=sys.stderr); "
                                                "sys.exit(2)"], lines.append)
    assert code == 2 and sorted(lines) == ["eins", "zwei"]


def test_stream_can_be_cancelled():
    threading.Timer(0.5, cancel.request).start()
    with pytest.raises(cancel.Cancelled):
        cancel.stream(SLEEP, lambda line: None)


# ── Protokoll und Fehlerbericht ─────────────────────────────────────────────────
@pytest.fixture
def logfile(tmp_path, monkeypatch):
    root = logging.getLogger()
    level = root.level
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    path = applog.setup(True, str(tmp_path / "Protokolle"))
    yield path
    applog.close()
    root.setLevel(level)


def test_log_file_gets_messages_and_crashes_in_threads(logfile):
    logging.getLogger("vocaloid.test").info("ein Schritt")
    worker = threading.Thread(target=lambda: 1 / 0, name="kaputt")
    worker.start()
    worker.join()
    for handler in logging.getLogger().handlers:
        handler.flush()
    text = open(logfile, encoding="utf-8").read()
    assert "ein Schritt" in text
    assert "Unbehandelter Fehler im Thread kaputt" in text and "ZeroDivisionError" in text


def test_no_log_file_when_switched_off(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    assert applog.setup(False, str(tmp_path)) is None
    logging.getLogger("vocaloid.test").warning("nicht in die Datei")
    assert not os.path.exists(applog.path(str(tmp_path)))


def test_error_report_has_system_log_and_settings_but_no_songs(tmp_path, monkeypatch, logfile):
    monkeypatch.setattr(applog, "files", lambda folder=None: [logfile])
    logging.getLogger("vocaloid.test").error("etwas ging schief")
    for handler in logging.getLogger().handlers:
        handler.flush()
    out = tmp_path / "out"
    out.mkdir()
    (out / "song.mp3").write_bytes(b"mp3")
    path = fehlerbericht.save(str(tmp_path / "bericht.zip"), SongSettings(output_ordner=str(out), bpm=133))
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        system = z.read("system.txt").decode("utf-8")
        log_text = z.read("protokoll/vloid_songs.log").decode("utf-8")
        saved = z.read("Einstellungen.json").decode("utf-8")
    assert "Vloid Songs" in system and "Datenordner" in system and "Python" in system
    assert "etwas ging schief" in log_text
    assert '"bpm": 133' in saved
    assert not any(n.endswith((".mp3", ".wav")) for n in names)


# ── Weitermachen nach einem Absturz ────────────────────────────────────────────
def test_a_running_song_is_remembered_until_it_ends():
    s = SongSettings(seed=42, bpm=133)
    assert resume.pending() is None
    resume.start(s)
    saved, started = resume.pending()
    assert saved.seed == 42 and saved.bpm == 133 and started is not None
    resume.finish()
    assert resume.pending() is None


def test_a_broken_note_is_dropped():
    os.makedirs(os.path.dirname(resume.path()))
    with open(resume.path(), "w", encoding="utf-8") as f:
        f.write("{kaputt")
    assert resume.pending() is None and not os.path.exists(resume.path())


# ── Ein ganzer Song mit nachgebautem NEUTRINO (läuft auch in der Windows-CI) ─────────
@pytest.fixture
def fake_neutrino(tmp_path, monkeypatch):
    """NEUTRINO als Attrappe hinter vocal_synthesizer._run: die echten Aufrufe, aber Sinus statt Stimme."""
    root = tmp_path / "NEUTRINO"
    (root / "bin").mkdir(parents=True)
    (root / "model" / "MERROW").mkdir(parents=True)
    for name in ("musicXMLtoLabel.exe", "NEUTRINO.exe"):
        (root / "bin" / name).write_bytes(b"")
    calls = []
    lengths = {}

    def run(cmd, cwd, timeout):
        name = os.path.basename(cmd[0])
        calls.append(name)
        if name == "musicXMLtoLabel.exe":
            import music21
            xml = cmd[1]
            beats = float(music21.converter.parse(xml).highestTime)
            lengths[cmd[2]] = beats * 60.0 / vocal_synthesizer._tempo_aus_musicxml(xml)
            for path in cmd[2:4]:
                with open(path, "w") as f:
                    f.write("label")
        else:
            sr = 48000
            t = np.arange(int(lengths[cmd[1]] * sr)) / sr
            sf.write(cmd[5], (0.2 * np.sin(2 * np.pi * 330 * t)).astype(np.float32), sr)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(vocal_synthesizer, "_run", run)
    # die Windows-Sprachausgabe der Vorschau-Stimme hängt in der CI: sie darf hier nie singen
    monkeypatch.setattr(pipeline, "_sing_preview", lambda *a, **k: pytest.fail("die Vorschau-Stimme sang"))
    return root, calls


def e2e_settings(tmp_path, root, **changes) -> SongSettings:
    return SongSettings(active_sections=["Verse", "Chorus"], section_bars={"Verse": 4, "Chorus": 4},
                        output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root), singer="MERROW", seed=5,
                        polish=False, **changes)


def test_whole_song_end_to_end_with_neutrino(tmp_path, fake_neutrino):
    root, calls = fake_neutrino
    steps = []
    result = pipeline.generate_song(e2e_settings(tmp_path, root), lambda f, m: steps.append(m))
    assert "NEUTRINO.exe" in calls
    assert steps[0] == "Komponiere Song..." and steps[-1] == "Fertig"
    audio, _ = sf.read(result.audio if result.audio.endswith(".wav") else result.mix_wav)
    assert len(audio) and np.max(np.abs(audio)) > 0.01
    vocals, sr = sf.read(result.vocals_wav)
    assert np.sqrt(np.mean(vocals ** 2)) > 0.01
    assert result.history and os.path.exists(result.history)
    assert resume.pending() is None

    # derselbe Song noch einmal: NEUTRINO singt nicht neu, der Gesang wird übernommen
    sung = calls.count("NEUTRINO.exe")
    again = pipeline.generate_song(e2e_settings(tmp_path, root, master_lufs=-10.0))
    assert calls.count("NEUTRINO.exe") == sung
    assert os.path.exists(again.vocals_wav)

    # mit anderem Vibrato singt NEUTRINO neu
    pipeline.generate_song(e2e_settings(tmp_path, root, vibrato=0.5))
    assert calls.count("NEUTRINO.exe") > sung


def test_vocals_are_sung_again_when_reuse_is_off(tmp_path, fake_neutrino):
    root, calls = fake_neutrino
    s = e2e_settings(tmp_path, root)
    tracks, _ = pipeline.compose(s)
    out = s.output_dir()
    pipeline._synthesize_vocals(s, tracks, out)
    sung = calls.count("NEUTRINO.exe")
    pipeline._synthesize_vocals(s, tracks, out)
    assert calls.count("NEUTRINO.exe") == sung
    pipeline._synthesize_vocals(s.with_updates(reuse_steps=False), tracks, out)
    assert calls.count("NEUTRINO.exe") > sung


def test_cancelled_song_stops_and_keeps_its_vocals(tmp_path, fake_neutrino):
    root, calls = fake_neutrino

    def progress(fraction, message):
        if message.startswith("Rendere"):
            cancel.request()

    with pytest.raises(cancel.Cancelled):
        pipeline.generate_song(e2e_settings(tmp_path, root), progress)
    assert resume.pending() is None              # abgebrochen ist nicht abgestürzt
    assert not os.path.exists(os.path.join(tmp_path, "out", "final_mix.wav"))
    cancel.reset()
    sung = calls.count("NEUTRINO.exe")
    result = pipeline.generate_song(e2e_settings(tmp_path, root))
    assert calls.count("NEUTRINO.exe") == sung     # der Gesang vom abgebrochenen Lauf zählt
    assert os.path.exists(result.audio)


def test_crash_leaves_a_note_to_continue(tmp_path, fake_neutrino, monkeypatch):
    root, _ = fake_neutrino
    monkeypatch.setattr(resume, "finish", lambda: None)        # so sieht es nach einem Absturz aus

    def crash(*args, **kwargs):
        raise MemoryError("Absturz")
    monkeypatch.setattr(pipeline, "_render_instruments", crash)
    with pytest.raises(MemoryError):
        pipeline.generate_song(e2e_settings(tmp_path, root, bpm=111))
    saved, _ = resume.pending()
    assert saved.seed == 5 and saved.bpm == 111 and saved.neutrino_pfad == str(root)
    os.remove(resume.path())


def test_data_folder_paths():
    assert resume.path().startswith(config.DATA_DIR)
    assert applog.path().startswith(config.DATA_DIR)
