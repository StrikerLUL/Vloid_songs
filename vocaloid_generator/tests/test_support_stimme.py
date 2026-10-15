# test_support_stimme.py – Support-Modell (B5): eine zweite NEUTRINO-Stimme färbt die Hauptstimme
import os
import stat
import sys
import textwrap

import numpy as np
import pytest
import soundfile as sf

import main
import pipeline
import vocal_check
import vocal_synthesizer
from settings import SongSettings
from test_production import FAKE_LABEL, FAKE_NEUTRINO, RUN_BAT
from vocal_synthesizer import LETZTER_LAUF, erstelle_musicxml, neutrino_synthese

SUPPORT_BAT = "\n".join([
    "@echo off",
    "set BASENAME=sample1",
    "set NumThreads=3",
    "set ModelDir=MERROW",
    "set SupportModelDir=SOMA",
    "set StyleShift=0",
    r"bin\NEUTRINO.exe score\label\full\%BASENAME%.lab score\label\timing\%BASENAME%.lab output\%BASENAME%.f0"
    r" output\%BASENAME%.melspec output\%BASENAME%.wav model\%ModelDir%\ -s model\%SupportModelDir%\ "
    r"-n %NumThreads% -k %StyleShift% -t",
])


def neutrino(tmp_path, support_bat=True):
    root = tmp_path / "NEUTRINO"
    (root / "bin").mkdir(parents=True)
    for singer in ("MERROW", "SOMA"):
        (root / "model" / singer).mkdir(parents=True)
    for name, body in (("musicXMLtoLabel.exe", FAKE_LABEL), ("NEUTRINO.exe", FAKE_NEUTRINO)):
        exe = root / "bin" / name
        exe.write_text(textwrap.dedent(body).format(python=sys.executable))
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    (root / "Run.bat").write_text(RUN_BAT)
    if support_bat:
        (root / "Run_support_model.bat").write_text(SUPPORT_BAT)
    return root


@pytest.mark.skipif(os.name == "nt", reason="die Attrappen sind Python-Skripte, keine Windows-Programme")
def test_the_support_voice_comes_from_run_support_model_bat(tmp_path):
    root = neutrino(tmp_path)
    xml = erstelle_musicxml([(64, 4.0)], ["ら"], 240, str(tmp_path / "v.xml"))
    neutrino_synthese(xml, str(tmp_path / "vocals.wav"), str(root), str(root / "model" / "MERROW"), threads=5,
                      support_pfad=str(root / "model" / "SOMA"))
    args = eval((root / "bin" / "NEUTRINO.exe.args").read_text())
    assert args[5].rstrip("/\\").endswith("MERROW")
    assert args[6] == "-s" and args[7].rstrip("/\\").endswith("SOMA")
    assert args[8:] == ["-n", "5", "-k", "0", "-t"]
    assert LETZTER_LAUF["support"] == "SOMA"


@pytest.mark.skipif(os.name == "nt", reason="die Attrappen sind Python-Skripte, keine Windows-Programme")
def test_without_run_support_model_bat_the_voice_sings_alone(tmp_path, caplog):
    root = neutrino(tmp_path, support_bat=False)
    xml = erstelle_musicxml([(64, 4.0)], ["ら"], 240, str(tmp_path / "v.xml"))
    neutrino_synthese(xml, str(tmp_path / "vocals.wav"), str(root), str(root / "model" / "MERROW"),
                      support_pfad=str(root / "model" / "SOMA"))
    args = eval((root / "bin" / "NEUTRINO.exe.args").read_text())
    assert not any("SOMA" in a for a in args)
    assert LETZTER_LAUF["support"] == ""
    assert "Run_support_model.bat fehlt" in caplog.text


def test_run_bat_without_a_support_voice_is_not_taken_for_one(tmp_path):
    root = neutrino(tmp_path, support_bat=False)
    (root / "Run_support_model.bat").write_text(RUN_BAT)          # kein %SupportModelDir%
    files = {"full": "f.lab", "timing": "t.lab", ".f0": "a.f0", ".melspec": "a.mel", ".wav": "a.wav", "model": "M/",
             "support": "S/"}
    assert vocal_synthesizer._run_bat_aufruf(str(root), "NEUTRINO.exe", files, "4", 0,
                                             vocal_synthesizer.SUPPORT_BAT) is None


def test_only_the_lead_voice_gets_the_support_voice(tmp_path):
    root = tmp_path / "NEUTRINO"
    for singer in ("MERROW", "SOMA", "REINA"):
        (root / "model" / singer).mkdir(parents=True)
    s = SongSettings(neutrino_pfad=str(root), singer="MERROW", support_singer="SOMA")
    lead, duet = str(root / "model" / "MERROW"), str(root / "model" / "REINA")
    assert pipeline._support_model(s, str(root), lead) == str(root / "model" / "SOMA")
    assert pipeline._support_model(s, str(root), duet) is None                       # die Duett-Stimme singt allein
    assert pipeline._support_model(s.with_updates(support_singer=""), str(root), lead) is None
    assert pipeline._support_model(s.with_updates(support_singer="MERROW"), str(root), lead) is None
    assert pipeline._support_model(s.with_updates(support_singer="FEHLT"), str(root), lead) is None
    assert main.parse_args(["--support-stimme", "SOMA"]).support_stimme == "SOMA"


def test_the_vocal_check_names_the_support_voice():
    info = {"engine": "NEUTRINO", "chosen": "NEUTRINO", "voice": "MERROW", "version": "3.2.2", "support": "SOMA",
            "device": "Grafikkarte"}
    assert vocal_check.describe(info)[0] == "Gesungen von NEUTRINO 3.2.2, MERROW mit Support-Stimme SOMA, Grafikkarte"


def test_a_take_with_support_voice_is_kept_apart(tmp_path, monkeypatch):
    root = tmp_path / "NEUTRINO"
    for singer in ("MERROW", "SOMA"):
        (root / "model" / singer).mkdir(parents=True)
    xml = erstelle_musicxml([(64, 4.0)], ["ら"], 120, str(tmp_path / "v.xml"))
    seen = []

    def sing(xml, wav, neutrino_dir, model_dir, style_shift=0, **kw):
        seen.append(kw.get("support_pfad"))
        sf.write(wav, np.zeros(4800, dtype=np.float32), 48000)

    monkeypatch.setattr(vocal_synthesizer, "neutrino_synthese", sing)
    s = SongSettings(neutrino_pfad=str(root), singer="MERROW", reuse_steps=True)
    wav = str(tmp_path / "vocals.wav")
    pipeline._neutrino(s, xml, wav, str(root), str(root / "model" / "MERROW"), 0)
    pipeline._neutrino(s.with_updates(support_singer="SOMA"), xml, wav, str(root), str(root / "model" / "MERROW"), 0)
    pipeline._neutrino(s.with_updates(support_singer="SOMA"), xml, wav, str(root), str(root / "model" / "MERROW"), 0)
    assert seen == [None, str(root / "model" / "SOMA")]       # das dritte Mal kommt aus dem Zwischenspeicher
