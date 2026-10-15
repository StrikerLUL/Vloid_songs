# rap.py – Rap- und Sprechteil (v6 Nr. 7)
#
# Eine Sektion „Rap“ wird gesprochen statt gesungen, wie der Rap in „Idol“: die Sprechstimme von VOICEVOX spricht den
# Text im Takt. Den Rhythmus schreibt melody_writer wie für jede Sektion (dichter, fast auf einem Ton); hier bekommt
# jede More von VOICEVOX genau die Länge, mit der ihr Vokal auf dem Einsatz ihrer Note beginnt. Die Satzmelodie kommt
# von VOICEVOX, so klingt es gesprochen. NEUTRINO kann nicht rappen: läuft VOICEVOX nicht oder ist der Schalter aus,
# singt die Gesangs-Engine den Rap auf seiner fast gleichbleibenden Melodie.
import io
import json
import logging
from typing import Optional

import numpy as np
import soundfile as sf

log = logging.getLogger(__name__)

KIND = "Rap"
PHRASE_GAP = 0.25           # Sekunden Pause, ab der VOICEVOX eine neue Phrase spricht
LEAD = 0.1                  # Sekunden Stille vor jeder Phrase
TAIL = 0.1
MAX_VOWEL = 0.45            # länger hält eine gesprochene Silbe ihren Vokal nicht
CONSONANT_SHARE = 0.45      # so viel der Zeit seit dem letzten Einsatz darf ein Konsonant höchstens vorweg nehmen
INTONATION = 1.15           # etwas mehr Satzmelodie als beim Vorlesen
EPS = 0.01                  # Schläge
_KANA = set("ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞただちぢっつづてでとどなにぬねのはばぱひびぴ"
            "ふぶぷへべぺほぼぽまみむめもゃやゅゆょよらりるれろゎわゐゑをんゔー")


def windows(plan) -> list:
    """[(Anfang, Ende)] der Rap-Sektionen in Schlägen; leer ohne Rap-Teil."""
    if plan is None:
        return []
    return [(sec.start, sec.end) for sec in plan.sections if sec.kind == KIND and sec.has_vocals]


def _span_of(beat: float, spans: list) -> Optional[int]:
    """Die Nummer der Rap-Sektion, in der beat liegt (melody_data rundet Dauern, daher etwas Spielraum)."""
    return next((k for k, (start, end) in enumerate(spans) if start - EPS <= beat < end - EPS), None)


def _inside(beat: float, spans: list) -> bool:
    return _span_of(beat, spans) is not None


def notes(melody_data: list, silben: list, spans: list) -> list:
    """[(Anfang, Dauer in Schlägen, Silbe)] der Töne im Rap. Ein Ton, der nur den Vokal davor weiterklingen lässt
    (Melisma), verlängert die Silbe davor."""
    out, t, i = [], 0.0, 0
    for pitch, dur in melody_data:
        if pitch is not None:
            syllable = silben[i] if i < len(silben) else "ら"
            i += 1
            if _inside(t, spans):
                if getattr(syllable, "melisma", False) and out and abs(out[-1][0] + out[-1][1] - t) < 1e-6:
                    out[-1] = (out[-1][0], out[-1][1] + dur, out[-1][2])
                else:
                    out.append((t, dur, syllable))
        t += dur
    return out


def without(tracks: dict, spans: list) -> dict:
    """tracks mit Pausen statt der Töne im Rap (melody_data, silben): was die Gesangs-Engine singen soll, wenn
    VOICEVOX den Rap spricht."""
    data, silben, t, i = [], [], 0.0, 0
    for pitch, dur in tracks["melody_data"]:
        if pitch is not None:
            if not _inside(t, spans) and i < len(tracks["silben"]):
                silben.append(tracks["silben"][i])
            i += 1
            pitch = None if _inside(t, spans) else pitch
        if pitch is None and data and data[-1][0] is None:
            data[-1] = (None, data[-1][1] + dur)
        else:
            data.append((pitch, dur))
        t += dur
    return {**tracks, "melody_data": data, "silben": silben}


def phrases(rap_notes: list, bpm: float, spans: list) -> list:
    """Die Töne als Phrasen zum Sprechen: [[(Einsatz in Sekunden, Dauer in Sekunden, Silbe)]]. Eine neue Phrase
    beginnt nach einer Pause ab PHRASE_GAP und in jeder Rap-Sektion."""
    spb = 60.0 / bpm
    out, end, span = [], None, None
    for start, dur, syllable in rap_notes:
        here = _span_of(start, spans)
        if not out or here != span or start * spb - end >= PHRASE_GAP:
            out.append([])
        out[-1].append((start * spb, dur * spb, syllable))
        end, span = (start + dur) * spb, here
    return out


def _kana(syllable) -> str:
    """Eine Silbe als Text für VOICEVOX: Hiragana, wie sie dasteht; alles andere spricht die Stimme als „ら“."""
    text = str(syllable).strip()
    hira = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)
    return hira if hira and all(c in _KANA for c in hira) else "ら"


def timed(query: dict, onsets: list, durations: list) -> tuple:
    """
    Die Moren der VOICEVOX-Anfrage so lang, dass jeder Vokal genau auf dem Einsatz seiner Note beginnt (der Konsonant
    davor). Passt die Zahl der Moren nicht zur Zahl der Noten (z. B. weil VOICEVOX ein Wort anders liest), wird die
    ganze Phrase gleichmäßig auf ihre Länge gestreckt. Rückgabe (Anfrage, Sekunden vom Audio-Anfang bis zum ersten
    Einsatz). Zeiten in Sekunden ab dem ersten Einsatz.
    """
    query = json.loads(json.dumps(query))
    for phrase in query["accent_phrases"]:
        phrase["pause_mora"] = None
    moras = [m for phrase in query["accent_phrases"] for m in phrase["moras"]]
    last = min(max(durations[-1], 0.08), MAX_VOWEL)
    if len(moras) == len(onsets):
        cons = []
        for k, m in enumerate(moras):
            room = (onsets[k] - onsets[k - 1]) if k else LEAD
            cons.append(min(m.get("consonant_length") or 0.0, CONSONANT_SHARE * room) if m.get("consonant") else 0.0)
        for k, m in enumerate(moras):
            if m.get("consonant"):
                m["consonant_length"] = cons[k]
            following = onsets[k + 1] - cons[k + 1] if k + 1 < len(moras) else onsets[k] + last
            m["vowel_length"] = max(following - onsets[k], 0.01)
        first = cons[0]
    else:
        natural = sum((m.get("consonant_length") or 0.0) + m["vowel_length"] for m in moras)
        scale = (onsets[-1] + last - onsets[0]) / max(natural, 1e-3)
        for m in moras:
            if m.get("consonant"):
                m["consonant_length"] = (m.get("consonant_length") or 0.0) * scale
            m["vowel_length"] *= scale
        first = 0.0
        log.debug("Rap: %d Moren für %d Noten, die Phrase wird gestreckt", len(moras), len(onsets))
    query.update(speedScale=1.0, intonationScale=INTONATION, prePhonemeLength=LEAD, postPhonemeLength=TAIL)
    return query, LEAD + first


def speak(phrase: list, url: str, speaker: int, rate: int) -> tuple:
    """Eine Phrase sprechen. Rückgabe (Audio, mono, float32; Zeit des Audio-Anfangs im Song in Sekunden)."""
    import voicevox
    text = "".join(_kana(s) for _, _, s in phrase)
    query = json.loads(voicevox._request(url, "/audio_query", {"text": text, "speaker": speaker}, {}, 30.0))
    start = phrase[0][0]
    query, ahead = timed(query, [t - start for t, _, _ in phrase], [d for _, d, _ in phrase])
    query.update(outputSamplingRate=rate, outputStereo=False)
    data = voicevox._request(url, "/synthesis", {"speaker": speaker}, query, 120.0)
    audio, got = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    if got != rate:
        from scipy.signal import resample_poly
        audio = resample_poly(audio, rate, got).astype(np.float32)
    return audio, start - ahead


def render(melody_data: list, silben: list, bpm: float, spans: list, url: str, speaker: int, rate: int,
           length: int) -> Optional[np.ndarray]:
    """Alle Rap-Phrasen, gesprochen und an ihrem Platz: mono, length Samples. None ohne Rap-Töne."""
    groups = phrases(notes(melody_data, silben, spans), bpm, spans)
    if not groups:
        return None
    out = np.zeros(length, dtype=np.float32)
    for phrase in groups:
        audio, at = speak(phrase, url, speaker, rate)
        begin = int(round(at * rate))
        if begin < 0:
            audio, begin = audio[-begin:], 0
        if begin + len(audio) > len(out):
            out = np.concatenate([out, np.zeros(begin + len(audio) - len(out), dtype=np.float32)])
        out[begin:begin + len(audio)] += audio
    log.info("Rap-Teil gesprochen: %d Phrasen, %d Silben", len(groups), sum(len(p) for p in groups))
    return out


def level_like(rap_audio: np.ndarray, sung: np.ndarray, rate: int) -> np.ndarray:
    """Den Rap so laut wie den Gesang: gleicher Effektivwert der lauten Stellen (je 50 ms)."""
    def loud(x: np.ndarray) -> float:
        hop = max(1, int(0.05 * rate))
        frames = x[:len(x) // hop * hop].reshape(-1, hop) if len(x) >= hop else x.reshape(1, -1)
        rms = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1))
        active = rms[rms > 0.1 * rms.max()] if rms.max() > 0 else rms
        return float(np.median(active)) if len(active) else 0.0
    target, have = loud(sung), loud(rap_audio)
    if target <= 1e-5 or have <= 1e-5:
        return rap_audio
    return (rap_audio * (target / have)).astype(np.float32)
