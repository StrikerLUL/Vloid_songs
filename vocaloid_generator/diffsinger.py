# diffsinger.py – DiffSinger als dritte Engine (Gesang 1.1, F1, Versuch)
#
# DiffSinger-Stimmen für OpenUtau sind ONNX-Modelle mit einer dsconfig.yaml. OpenUtau hat keine Kommandozeile; diese
# Datei rechnet die Modelle deshalb selbst mit onnxruntime, Schritt für Schritt wie OpenUtau es tut
# (OpenUtau.Core/DiffSinger, MIT): Silben → Phoneme (dsdict.yaml der Stimme), Längen in Rahmen, Tonhöhe je Rahmen aus
# den Noten, Energie und Hauch aus dem Varianz-Modell der Stimme (dsvariance, falls das akustische Modell sie braucht),
# akustisches Modell → Mel-Spektrum, Vocoder (nsf_hifigan aus dsvocoder oder Dependencies von OpenUtau) → Audio.
# Konsonanten setzen kurz vor dem Ton ein, der Vokal auf dem Schlag. Jede Stimme hat ihre eigenen Nutzungsregeln
# (Lizenz im Ordner der Stimme). Die Schlüssel der dsconfig.yaml schreibt OpenUtau mit Unterstrich (use_energy_embed).
import glob
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import soundfile as sf

log = logging.getLogger(__name__)

HEAD_FRAMES = TAIL_FRAMES = 8        # Stille vor und nach jeder Phrase, wie OpenUtau (DiffSingerUtils)
STEPS = 20                           # Diffusionsschritte (Standard von OpenUtau)
DEPTH = 1.0                          # Tiefe der flachen Diffusion, höchstens max_depth der Stimme
CONSONANT_SECONDS = 0.07             # so lange klingt ein Konsonant vor seinem Ton
CONSONANT_SHARE = 0.4                # höchstens dieser Anteil des Tons oder der Pause davor
PHRASE_GAP = 0.3                     # ab dieser Pause (Sekunden) beginnt eine neue Phrase
GLIDE_SECONDS = 0.08                 # Übergang zwischen zwei Tönen (bei glide = 1)
VIBRATO = (5.5, 0.3, 0.3, 0.25)      # Hz, Halbtöne, Einsatz nach Sekunden, Einblenden in Sekunden (bei vibrato = 1)
VOWELS = set("aiueoAIUEO") | {"N", "SP", "AP", "cl"}
VARIANCES = ("energy", "breathiness", "voicing", "tension")
LIMITS = {"energy": (-96.0, 0.0), "breathiness": (-96.0, 0.0), "voicing": (-96.0, 0.0), "tension": (-10.0, 10.0)}


def available() -> bool:
    try:
        import onnxruntime  # noqa: F401
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


# ── Stimmen finden ──────────────────────────────────────────────────────────────
def search_folders() -> list:
    """Wo OpenUtau seine Stimmen ablegt (Ordner Singers), dazu der Datenordner der App."""
    import config
    home = os.path.expanduser("~")
    roots = [os.path.join(config.DATA_DIR, "DiffSinger"), os.path.join(home, "OpenUtau"),
             os.path.join(home, "Documents", "OpenUtau"), os.path.join(home, "Desktop", "OpenUtau"),
             os.path.join(os.environ.get("LOCALAPPDATA", home), "OpenUtau"),
             os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "OpenUtau")]
    return [os.path.join(r, "Singers") for r in roots] + [roots[0]]


def voicebanks(folders: Optional[list] = None) -> dict:
    """{Name: Ordner} aller DiffSinger-Stimmen (Ordner mit dsconfig.yaml und akustischem Modell)."""
    found = {}
    for folder in folders if folders is not None else search_folders():
        for config in sorted(glob.glob(os.path.join(folder, "*", "dsconfig.yaml"))):
            root = os.path.dirname(config)
            found.setdefault(os.path.basename(root), root)
    return found


def find(choice: str = "", folders: Optional[list] = None) -> str:
    """Ordner der gewählten Stimme (ein Pfad oder ein Name); leer: die erste gefundene; "" ohne Stimme."""
    if choice and os.path.isfile(os.path.join(choice, "dsconfig.yaml")):
        return choice
    banks = voicebanks(folders)
    if choice:
        return banks.get(choice, "")
    return next(iter(banks.values()), "")


# ── Stimme laden ───────────────────────────────────────────────────────────────
def _yaml(path: str) -> dict:
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _phonemes(path: str) -> dict:
    if path.lower().endswith(".json"):
        import json
        with open(path, encoding="utf-8") as f:
            return {str(k): int(v) for k, v in json.load(f).items()}
    with open(path, encoding="utf-8") as f:
        return {line.rstrip("\r\n"): i for i, line in enumerate(f)}


def _dictionary(*folders: str) -> tuple:
    """({Silbe: [Phoneme]}, {Vokale}) aus der ersten dsdict.yaml (japanisch bevorzugt)."""
    for folder in folders:
        for name in ("dsdict-ja.yaml", "dsdict.yaml"):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                data = _yaml(path)
                entries = {str(e["grapheme"]): [str(p) for p in e.get("phonemes", [])]
                           for e in data.get("entries", []) if "grapheme" in e}
                vowels = {str(s["symbol"]) for s in data.get("symbols", []) if s.get("type") == "vowel"}
                return entries, vowels
    return {}, set()


@dataclass
class Model:
    root: str
    config: dict
    tokens: dict
    session: object = None
    languages: dict = field(default_factory=dict)

    @property
    def frame(self) -> float:
        return self.config.get("hop_size", 512) / self.config.get("sample_rate", 44100)

    def knows(self, phoneme: str) -> bool:
        return phoneme in self.tokens or any(n.split("/", 1)[-1] == phoneme for n in self.tokens)

    def token(self, phoneme: str) -> int:
        if phoneme in self.tokens:
            return self.tokens[phoneme]
        for name, value in self.tokens.items():
            if name.split("/", 1)[-1] == phoneme:
                return value
        raise KeyError(f"Phonem {phoneme} kennt die Stimme nicht")

    def speaker(self, frames: int) -> Optional[np.ndarray]:
        speakers = self.config.get("speakers")
        if not speakers:
            return None
        size = int(self.config.get("hidden_size", 256))
        embed = np.fromfile(os.path.join(self.root, f"{speakers[0]}.emb"), dtype=np.float32)[:size]
        return np.repeat(embed[None, None, :], frames, axis=1)

    def language_ids(self, phonemes: list) -> np.ndarray:
        return np.array([[self.languages.get(p.split("/", 1)[0] if "/" in p else "", 0) for p in phonemes]],
                        dtype=np.int64)


@dataclass
class Voicebank:
    name: str
    acoustic: Model
    vocoder: object
    vocoder_config: dict
    dictionary: dict
    vowels: set
    variance: Optional[Model] = None
    linguistic: object = None


def _session(path: str):
    import onnxruntime as ort
    return ort.InferenceSession(path, providers=["CPUExecutionProvider"])


def _model(root: str, load: bool = True) -> Model:
    config = _yaml(os.path.join(root, "dsconfig.yaml"))
    tokens = _phonemes(os.path.join(root, config.get("phonemes", "phonemes.txt")))
    languages = {}
    if config.get("languages") and os.path.isfile(os.path.join(root, config["languages"])):
        import json
        with open(os.path.join(root, config["languages"]), encoding="utf-8") as f:
            languages = json.load(f)
    session = _session(os.path.join(root, config["acoustic"])) if load and config.get("acoustic") else None
    return Model(root, config, tokens, session, languages)


def vocoder_folder(root: str, name: str) -> str:
    """Der Vocoder: aus dsvocoder in der Stimme, sonst aus Dependencies von OpenUtau (Singers/../Dependencies)."""
    candidates = [os.path.join(root, "dsvocoder")]
    if name:
        candidates += [os.path.join(os.path.dirname(os.path.dirname(root)), "Dependencies", name),
                       os.path.join(os.path.dirname(root), "Dependencies", name)]
        candidates += [os.path.join(os.path.dirname(f), "Dependencies", name) for f in search_folders()]
    return next((c for c in candidates if os.path.isfile(os.path.join(c, "vocoder.yaml"))), "")


def load(root: str) -> Voicebank:
    if not available():
        raise RuntimeError("DiffSinger braucht onnxruntime und PyYAML")
    acoustic = _model(root)
    folder = vocoder_folder(root, acoustic.config.get("vocoder", ""))
    if not folder:
        raise FileNotFoundError(f"Vocoder {acoustic.config.get('vocoder', '')} für {os.path.basename(root)} fehlt "
                                "(in OpenUtau unter Dependencies installieren)")
    vocoder_config = _yaml(os.path.join(folder, "vocoder.yaml"))
    for key in ("sample_rate", "hop_size", "num_mel_bins"):
        if key in vocoder_config and key in acoustic.config and vocoder_config[key] != acoustic.config[key]:
            raise ValueError(f"Vocoder und Stimme passen nicht zusammen ({key})")
    variance, linguistic = None, None
    needs = [v for v in VARIANCES if acoustic.config.get(f"use_{v}_embed")]
    if needs:
        vroot = os.path.join(root, "dsvariance")
        if not os.path.isfile(os.path.join(vroot, "dsconfig.yaml")):
            raise FileNotFoundError("Die Stimme braucht ein Varianz-Modell (dsvariance), das fehlt")
        variance = _model(vroot, load=False)
        variance.session = _session(os.path.join(vroot, variance.config["variance"]))
        linguistic = _session(os.path.join(vroot, variance.config["linguistic"]))
    dictionary, vowels = _dictionary(root, os.path.join(root, "dsvariance"), os.path.join(root, "dsdur"))
    return Voicebank(os.path.basename(os.path.normpath(root)), acoustic,
                     _session(os.path.join(folder, vocoder_config.get("model", "model.onnx"))), vocoder_config,
                     dictionary, vowels or VOWELS, variance, linguistic)


# ── Silben, Phoneme, Rahmen ─────────────────────────────────────────────────────
def _is_vowel(bank: Voicebank, phoneme: str) -> bool:
    bare = phoneme.split("/", 1)[-1]
    return phoneme in bank.vowels or bare in bank.vowels or bare in VOWELS


def phonemes(bank: Voicebank, mora: str) -> list:
    """Die Phoneme einer Silbe (Kana): aus dsdict.yaml, sonst aus den Romaji (か → k a). Was die Stimme nicht kennt,
    fällt weg (ein unbekannter Vokal wird a)."""
    import jaconv
    text = str(mora)
    romaji = jaconv.kana2alphabet(jaconv.kata2hira(text))
    found = next((list(bank.dictionary[k]) for k in (text, jaconv.hira2kata(text), jaconv.kata2hira(text), romaji)
                  if k in bank.dictionary), None)
    if found is None:
        if romaji == "n":
            found = ["N"]
        elif romaji and romaji[-1] in "aiueo":
            found = ([romaji[:-1]] if romaji[:-1] else []) + [romaji[-1]]
        else:
            found = ["a"]
    out = []
    for p in found:
        if bank.acoustic.knows(p):
            out.append(p)
        elif len(p) > 1 and not _is_vowel(bank, p) and all(bank.acoustic.knows(c) for c in p):
            out += list(p)                                       # ky → k y, wenn die Stimme nur k und y kennt
    if not any(_is_vowel(bank, p) for p in out):
        out.append("a")
    return out


@dataclass
class Phone:
    symbol: str
    start: float
    end: float


def phrases(melody_data: list, silben: list, bpm: float) -> list:
    """[[(Start, Ende, Tonhöhe, Silbe)]] in Sekunden, eine Liste je Phrase."""
    from vocal_synthesizer import _gebunden
    spb = 60.0 / bpm
    out, t, i, last_end = [], 0.0, 0, None
    for pitch, dur in _gebunden(melody_data):
        if pitch is not None:
            mora = silben[i] if i < len(silben) else "ら"
            i += 1
            if not out or last_end is None or t - last_end >= PHRASE_GAP:
                out.append([])
            out[-1].append((t, t + dur * spb, int(pitch), mora))
            last_end = t + dur * spb
        t += dur * spb
    return out


def layout(bank: Voicebank, phrase: list) -> list:
    """Die Phoneme einer Phrase mit Zeiten: der Vokal auf dem Ton, Konsonanten kurz davor."""
    phones, vowel = [], "a"
    for start, end, _, mora in phrase:
        if phones and start - phones[-1].end > 1e-6:
            phones.append(Phone("SP", phones[-1].end, start))
        text = str(mora)
        if getattr(mora, "melisma", False) or text == "ー":
            symbols = [vowel]
        elif text in ("っ", "ッ"):
            symbols = ["cl"] if "cl" in bank.acoustic.tokens else ["SP"]
        else:
            symbols = phonemes(bank, text)
        first = next((k for k, p in enumerate(symbols) if _is_vowel(bank, p)), len(symbols) - 1)
        before, body = symbols[:first], symbols[first:] or symbols[-1:]
        if before:
            room = (phones[-1].end - phones[-1].start) if phones else CONSONANT_SECONDS * len(before)
            length = min(CONSONANT_SECONDS * len(before), CONSONANT_SHARE * room if phones else room)
            if phones:
                phones[-1].end -= length
            t = start - length
            for p in before:
                phones.append(Phone(p, t, t + length / len(before)))
                t += length / len(before)
        step = (end - start) / len(body)
        for k, p in enumerate(body):
            phones.append(Phone(p, start + k * step, start + (k + 1) * step))
        vowel = next((p for p in reversed(body) if _is_vowel(bank, p) and p not in ("SP", "cl")), vowel)
    return phones


def frames(phones: list, frame: float) -> list:
    """Längen in Rahmen, mit Stille davor und danach; gerundet wird die Summe, damit nichts wegläuft."""
    edges = [round((p.end - phones[0].start) / frame) for p in phones]
    lengths = [max(1, e - s) for s, e in zip([0] + edges[:-1], edges)]
    return [HEAD_FRAMES] + lengths + [TAIL_FRAMES]


def pitch_curve(phrase: list, times: np.ndarray, vibrato: float = 1.0, glide: float = 1.0) -> np.ndarray:
    """Tonhöhe (MIDI, mit Kommastellen) zu den Zeiten: Töne mit weichen Übergängen und Vibrato auf langen Tönen."""
    starts = np.array([n[0] for n in phrase])
    pitches = np.array([n[2] for n in phrase], dtype=np.float64)
    index = np.clip(np.searchsorted(starts, times, side="right") - 1, 0, len(phrase) - 1)
    curve = pitches[index].copy()
    half = GLIDE_SECONDS * glide / 2
    if half > 0:
        for k in range(1, len(phrase)):
            s = starts[k]
            near = (times > s - half) & (times < s + half)
            x = (times[near] - (s - half)) / (2 * half)
            curve[near] = pitches[k - 1] + (pitches[k] - pitches[k - 1]) * x * x * (3 - 2 * x)
    rate, depth, delay, fade = VIBRATO
    if vibrato > 0:
        for start, end, _, _ in phrase:
            if end - start < delay + fade:
                continue
            on = (times >= start + delay) & (times < end)
            t = times[on] - start - delay
            amount = np.minimum(1.0, t / fade) * np.minimum(1.0, (end - times[on]) / 0.1)
            curve[on] += depth * vibrato * amount * np.sin(2 * np.pi * rate * t)
    return curve


# ── Rechnen ───────────────────────────────────────────────────────────────────
def _run(session, inputs: dict) -> list:
    wanted = {i.name for i in session.get_inputs()}
    return session.run(None, {k: v for k, v in inputs.items() if k in wanted})


def _speedup_inputs(config: dict, steps: int = STEPS, depth: float = DEPTH) -> dict:
    variable = bool(config.get("use_variable_depth", config.get("use_shallow_diffusion", False)))
    max_depth = float(config.get("max_depth", 1000 if not config.get("use_continuous_acceleration") else 1.0))
    if config.get("use_continuous_acceleration"):
        out = {"steps": np.array([steps], dtype=np.int64)}
        if variable:
            out["depth"] = np.array([min(depth, max_depth)], dtype=np.float32)
        return out
    if variable:
        whole = int(round(min(depth, max_depth / 1000.0) * 1000))
        speedup = max(1, whole // steps)
        return {"depth": np.array([whole // speedup * speedup], dtype=np.int64),
                "speedup": np.array([speedup], dtype=np.int64)}
    speedup = max(1, 1000 // steps)
    while 1000 % speedup and speedup > 1:
        speedup -= 1
    return {"speedup": np.array([speedup], dtype=np.int64)}


def _variances(bank: Voicebank, symbols: list, durations: list, midi: np.ndarray) -> dict:
    """Energie, Hauch usw. aus dem Varianz-Modell der Stimme (Rahmen wie das akustische Modell)."""
    model = bank.variance
    config = model.config
    tokens = np.array([[model.token(p) for p in symbols]], dtype=np.int64)
    ph_dur = np.array([durations], dtype=np.int64)
    inputs = {"tokens": tokens}
    if config.get("predict_dur", True):
        vowels = [k for k, p in enumerate(symbols) if 0 < k < len(symbols) - 1 and _is_vowel(bank, p)] or \
                 [len(symbols) - 2]
        div = [vowels[0]] + [b - a for a, b in zip(vowels, vowels[1:])] + [len(symbols) - vowels[-1]]
        bounds = np.cumsum([0] + div)
        inputs["word_div"] = np.array([div], dtype=np.int64)
        inputs["word_dur"] = np.array([[sum(durations[a:b]) for a, b in zip(bounds, bounds[1:])]], dtype=np.int64)
    else:
        inputs["ph_dur"] = ph_dur
    if config.get("use_lang_id"):
        inputs["languages"] = model.language_ids(symbols)
    encoder_out = _run(bank.linguistic, inputs)[0]
    total = int(sum(durations))
    predicted = [v for v in VARIANCES if config.get(f"predict_{v}", v in ("energy", "breathiness"))]
    inputs = {"encoder_out": encoder_out, "ph_dur": ph_dur, "pitch": midi[None].astype(np.float32),
              "retake": np.ones((1, total, len(predicted)), dtype=bool), **_speedup_inputs(config)}
    for v in predicted:
        inputs[v] = np.zeros((1, total), dtype=np.float32)
    speaker = model.speaker(total)
    if speaker is not None:
        inputs["spk_embed"] = speaker
    names = [o.name for o in model.session.get_outputs()]
    out = dict(zip(names, _run(model.session, inputs)))
    return {v: np.clip(out[f"{v}_pred"].reshape(-1)[:total], *LIMITS[v]) for v in predicted if f"{v}_pred" in out}


def render_phrase(bank: Voicebank, phrase: list, vibrato: float = 1.0, glide: float = 1.0) -> tuple:
    """(Audio, Startzeit in Sekunden) einer Phrase."""
    model = bank.acoustic
    frame = model.frame
    phones = layout(bank, phrase)
    durations = frames(phones, frame)
    symbols = ["SP"] + [p.symbol for p in phones] + ["SP"]
    total = int(sum(durations))
    start = phones[0].start - HEAD_FRAMES * frame
    times = start + np.arange(total) * frame
    midi = pitch_curve(phrase, times, vibrato, glide)
    f0 = (440.0 * 2 ** ((midi - 69) / 12)).astype(np.float32)[None]
    inputs = {"tokens": np.array([[model.token(p) for p in symbols]], dtype=np.int64),
              "durations": np.array([durations], dtype=np.int64), "f0": f0, **_speedup_inputs(model.config)}
    if model.config.get("use_lang_id"):
        inputs["languages"] = model.language_ids(symbols)
    speaker = model.speaker(total)
    if speaker is not None:
        inputs["spk_embed"] = speaker
    if model.config.get("use_key_shift_embed"):
        inputs["gender"] = np.zeros((1, total), dtype=np.float32)
    if model.config.get("use_speed_embed"):
        inputs["velocity"] = np.ones((1, total), dtype=np.float32)
    if bank.variance is not None:
        for name, curve in _variances(bank, symbols, durations, midi).items():
            if model.config.get(f"use_{name}_embed"):
                inputs[name] = curve[None].astype(np.float32)
    mel = _run(model.session, inputs)[0]
    base, vocoder_base = str(model.config.get("mel_base", "10")), str(bank.vocoder_config.get("mel_base", "10"))
    if base != vocoder_base:
        mel = mel * (2.30259 if vocoder_base == "e" else 0.434294)
    audio = _run(bank.vocoder, {"mel": mel.astype(np.float32), "f0": f0})[0]
    return np.asarray(audio, dtype=np.float32).reshape(-1), start


def sing(melody_data: list, silben: list, bpm: float, wav: str, voicebank: str, transpose: int = 0,
         vibrato: float = 1.0, glide: float = 1.0) -> str:
    """Singt die Melodie mit der DiffSinger-Stimme im Ordner voicebank in die Datei wav (Beginn = Songanfang)."""
    bank = load(voicebank)
    rate = int(bank.vocoder_config.get("sample_rate", bank.acoustic.config.get("sample_rate", 44100)))
    parts = phrases([(None if p is None else p + transpose, d) for p, d in melody_data], silben, bpm)
    if not parts:
        raise ValueError("keine Töne zum Singen")
    rendered = [render_phrase(bank, phrase, vibrato, glide) for phrase in parts]
    length = max(int(max(0.0, s) * rate) + len(a) for a, s in rendered)
    out = np.zeros(length, dtype=np.float32)
    for audio, start in rendered:
        a = int(round(start * rate))
        if a < 0:
            audio, a = audio[-a:], 0
        out[a:a + len(audio)] += audio[:length - a]
    sf.write(wav, out, rate, subtype="FLOAT")
    log.info("DiffSinger (%s): %d Phrasen gesungen", bank.name, len(parts))
    return wav
