# test_diffsinger.py – DiffSinger als dritte Engine (F1): eine Attrappen-Stimme aus winzigen ONNX-Modellen
import os

import numpy as np
import pytest
import soundfile as sf

import diffsinger
import main
import pipeline
from lyrics import Mora
from settings import SongSettings

onnx = pytest.importorskip("onnx")
from onnx import TensorProto, helper  # noqa: E402

HOP, RATE, BINS = 512, 44100, 8
FRAME = HOP / RATE


def save(path, nodes, inputs, outputs, inits=()):
    graph = helper.make_graph(nodes, "g", inputs, outputs, list(inits))
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    onnx.save(model, str(path))


def tensor(name, kind, shape):
    return helper.make_tensor_value_info(name, kind, shape)


def acoustic(path, energy=False):
    """mel = f0 / 1000 (+ Energie / 10000) in jedem Band; tokens, durations und speedup kommen an, ohne zu wirken."""
    ones = helper.make_tensor("ones", TensorProto.FLOAT, [BINS], [1.0] * BINS)
    scale = helper.make_tensor("scale", TensorProto.FLOAT, [], [0.001])
    nodes = [helper.make_node("Mul", ["f0", "scale"], ["f"]),
             helper.make_node("Unsqueeze", ["f", "axis"], ["f3"]),
             helper.make_node("Mul", ["f3", "ones"], ["mel"] if not energy else ["m0"])]
    inits = [ones, scale, helper.make_tensor("axis", TensorProto.INT64, [1], [2])]
    inputs = [tensor("tokens", TensorProto.INT64, [1, "n"]), tensor("durations", TensorProto.INT64, [1, "n"]),
              tensor("f0", TensorProto.FLOAT, [1, "t"]), tensor("speedup", TensorProto.INT64, [1])]
    if energy:
        inits.append(helper.make_tensor("small", TensorProto.FLOAT, [], [0.0001]))
        nodes += [helper.make_node("Mul", ["energy", "small"], ["e"]),
                  helper.make_node("Unsqueeze", ["e", "axis"], ["e3"]),
                  helper.make_node("Add", ["m0", "e3"], ["mel"])]
        inputs.append(tensor("energy", TensorProto.FLOAT, [1, "t"]))
    save(path, nodes, inputs, [tensor("mel", TensorProto.FLOAT, [1, "t", BINS])], inits)


def vocoder(path):
    """Je Rahmen HOP Samples mit dem Mittel der Mel-Bänder: so steht die Tonhöhe des Rahmens im Audio."""
    nodes = [helper.make_node("ReduceMean", ["mel"], ["avg"], axes=[2], keepdims=1),
             helper.make_node("Expand", ["avg", "shape"], ["wide"]),
             helper.make_node("Reshape", ["wide", "flat"], ["waveform"])]
    inits = [helper.make_tensor("shape", TensorProto.INT64, [3], [1, 1, HOP]),
             helper.make_tensor("flat", TensorProto.INT64, [2], [1, -1])]
    save(path, nodes, [tensor("mel", TensorProto.FLOAT, [1, "t", BINS]), tensor("f0", TensorProto.FLOAT, [1, "t"])],
         [tensor("waveform", TensorProto.FLOAT, [1, "s"])], inits)


def variance(folder):
    """Linguistik: encoder_out aus den Tokens; Varianz: Energie −10 dB in jedem Rahmen."""
    save(folder / "linguistic.onnx", [helper.make_node("Cast", ["tokens"], ["tf"], to=TensorProto.FLOAT),
                                      helper.make_node("Unsqueeze", ["tf", "axis"], ["encoder_out"])],
         [tensor("tokens", TensorProto.INT64, [1, "n"]), tensor("word_div", TensorProto.INT64, [1, "w"]),
          tensor("word_dur", TensorProto.INT64, [1, "w"])],
         [tensor("encoder_out", TensorProto.FLOAT, [1, "n", 1])],
         [helper.make_tensor("axis", TensorProto.INT64, [1], [2])])
    save(folder / "variance.onnx", [helper.make_node("Mul", ["pitch", "zero"], ["z"]),
                                    helper.make_node("Add", ["z", "minus"], ["energy_pred"]),
                                    helper.make_node("Add", ["z", "minus"], ["breathiness_pred"])],
         [tensor("encoder_out", TensorProto.FLOAT, [1, "n", 1]), tensor("ph_dur", TensorProto.INT64, [1, "n"]),
          tensor("pitch", TensorProto.FLOAT, [1, "t"]), tensor("energy", TensorProto.FLOAT, [1, "t"]),
          tensor("breathiness", TensorProto.FLOAT, [1, "t"]), tensor("retake", TensorProto.BOOL, [1, "t", 2]),
          tensor("speedup", TensorProto.INT64, [1])],
         [tensor("energy_pred", TensorProto.FLOAT, [1, "t"]), tensor("breathiness_pred", TensorProto.FLOAT, [1, "t"])],
         [helper.make_tensor("zero", TensorProto.FLOAT, [], [0.0]),
          helper.make_tensor("minus", TensorProto.FLOAT, [], [-10.0])])


PHONEMES = ["SP", "AP", "a", "i", "u", "e", "o", "N", "k", "s", "t", "r", "cl"]
DSDICT = """\
symbols:
  - {symbol: a, type: vowel}
  - {symbol: i, type: vowel}
  - {symbol: u, type: vowel}
  - {symbol: e, type: vowel}
  - {symbol: o, type: vowel}
  - {symbol: N, type: vowel}
  - {symbol: k, type: stop}
  - {symbol: s, type: fricative}
  - {symbol: t, type: stop}
  - {symbol: r, type: liquid}
entries:
  - {grapheme: か, phonemes: [k, a]}
  - {grapheme: さ, phonemes: [s, a]}
  - {grapheme: ら, phonemes: [r, a]}
  - {grapheme: ん, phonemes: [N]}
"""


@pytest.fixture
def openutau(tmp_path):
    """Ein OpenUtau-Ordner mit einer Attrappen-Stimme (Singers/Probe) und dem Vocoder unter Dependencies."""
    root = tmp_path / "OpenUtau"
    bank = root / "Singers" / "Probe"
    bank.mkdir(parents=True)
    (bank / "phonemes.txt").write_text("\n".join(PHONEMES), encoding="utf-8")
    (bank / "dsdict.yaml").write_text(DSDICT, encoding="utf-8")
    (bank / "dsconfig.yaml").write_text(
        f"phonemes: phonemes.txt\nacoustic: acoustic.onnx\nvocoder: nsf_hifigan\nsample_rate: {RATE}\n"
        f"hop_size: {HOP}\nnum_mel_bins: {BINS}\n", encoding="utf-8")
    acoustic(bank / "acoustic.onnx")
    voc = root / "Dependencies" / "nsf_hifigan"
    voc.mkdir(parents=True)
    vocoder(voc / "model.onnx")
    (voc / "vocoder.yaml").write_text(f"model: model.onnx\nsample_rate: {RATE}\nhop_size: {HOP}\nnum_mel_bins: {BINS}\n",
                                      encoding="utf-8")
    return root, bank


def test_voicebanks_are_found_in_openutau(openutau):
    root, bank = openutau
    assert diffsinger.voicebanks([str(root / "Singers")]) == {"Probe": str(bank)}
    assert diffsinger.find("", [str(root / "Singers")]) == str(bank)
    assert diffsinger.find(str(bank)) == str(bank)
    assert diffsinger.find("Fehlt", [str(root / "Singers")]) == ""
    assert diffsinger.vocoder_folder(str(bank), "nsf_hifigan") == str(root / "Dependencies" / "nsf_hifigan")


def test_syllables_become_phonemes_with_the_consonant_before_the_beat(openutau):
    bank = diffsinger.load(str(openutau[1]))
    assert diffsinger.phonemes(bank, "か") == ["k", "a"]
    assert diffsinger.phonemes(bank, "て") == ["t", "e"]                   # nicht im Wörterbuch: aus den Romaji
    phrase = [(1.0, 1.5, 60, Mora("か")), (1.5, 2.0, 62, Mora("あ", melisma=True)), (2.0, 2.5, 64, Mora("ん"))]
    phones = diffsinger.layout(bank, phrase)
    assert [p.symbol for p in phones] == ["k", "a", "a", "N"]
    assert phones[0].end == pytest.approx(1.0) and phones[0].start == pytest.approx(1.0 - 0.07)
    assert phones[1].start == pytest.approx(1.0) and phones[2].start == pytest.approx(1.5)
    durations = diffsinger.frames(phones, FRAME)
    assert durations[0] == durations[-1] == diffsinger.HEAD_FRAMES
    assert sum(durations[1:-1]) == round((2.5 - 0.93) / FRAME)


def test_the_pitch_glides_into_each_note_and_long_notes_get_vibrato():
    phrase = [(0.0, 1.0, 60, "ら"), (1.0, 3.0, 67, "ら")]
    t = np.arange(0, 3.0, 0.005)
    curve = diffsinger.pitch_curve(phrase, t)
    assert curve[np.searchsorted(t, 0.2)] == pytest.approx(60)                # vor dem Vibrato
    assert curve[np.searchsorted(t, 1.0)] == pytest.approx(63.5, abs=0.2)  # mitten im Übergang
    late = curve[(t > 2.0) & (t < 2.8)]
    assert late.max() > 67.2 and late.min() < 66.8                         # Vibrato
    assert np.abs(diffsinger.pitch_curve(phrase, t, vibrato=0.0)[(t > 2.0) & (t < 2.8)] - 67).max() < 1e-6


def test_the_voice_sings_each_note_at_its_place_and_pitch(openutau, tmp_path):
    data = [(None, 2.0), (69, 1.0), (None, 1.0), (72, 1.0)]                # 120 BPM: Töne bei 1,0 s und 2,0 s
    wav = str(tmp_path / "vocals.wav")
    diffsinger.sing(data, [Mora("ら"), Mora("か")], 120, wav, str(openutau[1]), vibrato=0.0)
    audio, rate = sf.read(wav)
    assert rate == RATE

    def hz(t):
        return audio[int(t * rate)] * 1000

    assert hz(1.25) == pytest.approx(440, rel=0.01)
    assert hz(2.25) == pytest.approx(523.25, rel=0.01)
    assert len(audio) >= int(2.5 * rate)


def test_a_voice_with_variance_model_gets_its_energy(openutau, tmp_path):
    bank = openutau[1]
    (bank / "dsconfig.yaml").write_text((bank / "dsconfig.yaml").read_text() + "use_energy_embed: true\n")
    acoustic(bank / "acoustic.onnx", energy=True)
    folder = bank / "dsvariance"
    folder.mkdir()
    (folder / "phonemes.txt").write_text("\n".join(PHONEMES), encoding="utf-8")
    (folder / "dsconfig.yaml").write_text(
        f"phonemes: phonemes.txt\nlinguistic: linguistic.onnx\nvariance: variance.onnx\nsample_rate: {RATE}\n"
        f"hop_size: {HOP}\n", encoding="utf-8")
    variance(folder)
    wav = str(tmp_path / "vocals.wav")
    diffsinger.sing([(None, 2.0), (69, 1.0)], [Mora("さ")], 120, wav, str(bank), vibrato=0.0)
    audio, rate = sf.read(wav)
    assert audio[int(1.25 * rate)] == pytest.approx(0.44 - 0.001, abs=1e-5)  # Energie −10 kam an


def test_diffsinger_sings_in_the_song_and_the_check_names_it(openutau, tmp_path, monkeypatch):
    monkeypatch.setattr(diffsinger, "search_folders", lambda: [str(openutau[0] / "Singers")])
    s = SongSettings(active_sections=["Verse"], output_ordner=str(tmp_path / "out"), vocal_engine="DiffSinger",
                     harmonies=False, final_choir=False, breaths=False)
    tracks, _ = pipeline.compose(s, seed=4)
    vocals = pipeline._synthesize_vocals(s, tracks, s.output_dir())
    import vocal_check
    info = vocal_check.read(s.output_dir())
    assert vocals and os.path.exists(vocals) and info["engine"] == "DiffSinger" and info["voice"] == "Probe"
    assert vocal_check.describe(info)[0] == "Gesungen von DiffSinger, Probe"
    args = main.parse_args(["--engine", "DiffSinger", "--diffsinger-stimme", str(openutau[1])])
    assert args.engine == "DiffSinger" and args.diffsinger_stimme == str(openutau[1])


def test_without_a_voice_the_next_engine_sings(tmp_path, monkeypatch):
    monkeypatch.setattr(diffsinger, "search_folders", lambda: [str(tmp_path / "leer")])
    with pytest.raises(FileNotFoundError):
        pipeline._sing_diffsinger(SongSettings(), {"melody_data": [(60, 1.0)], "silben": ["ら"]}, str(tmp_path),
                                  str(tmp_path / "vocals.wav"))
    assert pipeline.ENGINE_ORDER["DiffSinger"][1:] == ("NEUTRINO", "VOICEVOX")
