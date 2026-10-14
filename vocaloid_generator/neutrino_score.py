# neutrino_score.py – Noten so schreiben, wie NEUTRINO sie gut singen kann
#
# NEUTRINO schätzt aus den Noten, wie gesungen wird. Die FAQ von NEUTRINO (studio-neutrino.com/faq) nennt, was dabei
# hilft, und genau das macht dieses Modul aus der Gesangsmelodie, bevor music21 die MusicXML schreibt:
#   - Haltezeichen ー: ein lang gezogener Vokal und das Melisma (die Silbe gleitet auf einen zweiten Ton) bekommen „ー“
#     statt des Vokals als neue Silbe; laut FAQ wiederholt ー den Vokal davor.
#   - Atemzeichen: kurze Pausen werden wie bisher an die Note davor gebunden (wenige kleine Pausen klingen natürlicher),
#     aber nach spätestens zwei Takten Gesang wird dort geatmet, und eine lange Zeile ohne Pause bekommt nach vier
#     Takten ein Atemzeichen. NEUTRINO trennt die Phrasen dort; kürzere Phrasen brauchen weniger Grafikspeicher.
#   - Schnelle Stellen: sind zwei Töne kürzer als eine Sechzehntel bei 160 BPM und ist die zweite Silbe い, う oder ん,
#     singt NEUTRINO beide auf einem Ton (Doppelvokal wie かい), das klingt laut FAQ flüssiger.
# Ohne Optionen (options=None) kommt dasselbe heraus wie vor 1.1: nur die kurzen Pausen gebunden.
from dataclasses import dataclass
from typing import Optional

# Kurze Pausen in einer Phrase klingen bei NEUTRINO abgehackt; bis zu dieser Länge (Schläge) wird gebunden
LEGATO_BIS = 0.5
# Nach so vielen Schlägen Gesang wird an der nächsten gebundenen kurzen Pause geatmet
BREATH_AFTER_BEATS = 8.0
# Eine Zeile ohne jede Pause bekommt nach so vielen Schlägen ein Atemzeichen, auf dem ersten langen Ton danach
MAX_PHRASE_BEATS = 16.0
LONG_NOTE_BEATS = 1.0
# Kürzer als eine Sechzehntel bei 160 BPM: hier legt NEUTRINO laut FAQ besser zwei Moren auf einen Ton
FAST_NOTE_SECONDS = 0.1
FAST_MAX_STEP = 2                    # Halbtöne, die der zweite Ton höchstens neben dem ersten liegt
LONG_VOWEL = "ー"
# Zweite Silben, die mit der davor einen Doppelvokal bilden: {zweite Silbe: Vokale, auf die sie folgen darf}
DIPHTHONGS = {"い": "あいうえお", "う": "おう", "ん": "あいうえお"}


@dataclass(frozen=True)
class ScoreOptions:
    long_vowels: bool = True         # A1: ー statt des Vokals als neue Silbe
    breath_marks: bool = True        # A2: Atemzeichen in langen Phrasen
    fast_diphthongs: bool = True     # A4: zwei Moren auf einem schnellen Ton


@dataclass
class ScoreNote:
    pitch: Optional[int]             # None = Pause
    beats: float
    lyric: str = ""
    breath: bool = False             # Atemzeichen am Ende dieses Tons
    held: bool = False               # die Silbe ist der weiterklingende Vokal der Silbe davor (Melisma, ー)


def options(settings) -> ScoreOptions:
    """Die Optionen aus den Einstellungen eines Songs."""
    return ScoreOptions(long_vowels=getattr(settings, "long_vowel_mark", True),
                        breath_marks=getattr(settings, "breath_marks", True),
                        fast_diphthongs=getattr(settings, "fast_diphthongs", True))


def build(melody_data: list, syllables: list, bpm: float, opts: Optional[ScoreOptions] = None) -> list:
    """(Tonhöhe oder None, Dauer in Vierteln) und eine Silbe pro Ton → [ScoreNote], gleich lang wie die Melodie."""
    notes = _paired(melody_data, syllables)
    if opts is not None and opts.fast_diphthongs:
        notes = _merge_fast(notes, bpm)
    notes = _bind_short_rests(notes, opts is not None and opts.breath_marks)
    if opts is not None and opts.long_vowels:
        _long_vowels(notes)
    return notes


def _paired(melody_data: list, syllables: list) -> list:
    out, i = [], 0
    for pitch, beats in melody_data:
        if pitch is None:
            out.append(ScoreNote(None, float(beats)))
            continue
        syl = syllables[i] if i < len(syllables) else "ら"     # ohne Silbe bricht NEUTRINO ab
        out.append(ScoreNote(int(pitch), float(beats), str(syl), held=bool(getattr(syl, "melisma", False))))
        i += 1
    return out


def _merge_fast(notes: list, bpm: float) -> list:
    """Zwei schnelle Töne mit Doppelvokal (か + い) zu einem (かい) auf dem ersten Ton zusammenlegen."""
    from lyrics import vowel
    limit = FAST_NOTE_SECONDS * bpm / 60.0
    out = []
    for n in notes:
        prev = out[-1] if out else None
        if (prev is not None and prev.pitch is not None and n.pitch is not None and not n.held and not prev.breath
                and prev.beats < limit and n.beats < limit and abs(n.pitch - prev.pitch) <= FAST_MAX_STEP
                and len(prev.lyric) <= 2 and n.lyric in DIPHTHONGS
                and (vowel(prev.lyric) or "") in DIPHTHONGS[n.lyric]):
            prev.lyric += n.lyric
            prev.beats += n.beats
            continue
        out.append(n)
    return out


def _bind_short_rests(notes: list, breaths: bool) -> list:
    """Kurze Pausen der Note davor zuschlagen; mit breaths nach langen Strecken dort ein Atemzeichen setzen."""
    out, sung = [], 0.0                   # sung: Schläge seit der letzten richtigen Pause oder dem letzten Atmer
    for n in notes:
        prev = out[-1] if out else None
        if n.pitch is None:
            if n.beats <= LEGATO_BIS + 1e-9 and prev is not None and prev.pitch is not None:
                prev.beats += n.beats
                sung += n.beats
                if breaths and sung >= BREATH_AFTER_BEATS:
                    prev.breath, sung = True, 0.0
                continue
            out.append(n)
            sung = 0.0
            continue
        out.append(n)
        sung += n.beats
        if breaths and sung >= MAX_PHRASE_BEATS and n.beats >= LONG_NOTE_BEATS:
            n.breath, sung = True, 0.0
    return out


def _long_vowels(notes: list) -> None:
    """Weiterklingende Vokale als ー schreiben, wenn davor gesungen und nicht geatmet wird."""
    for prev, n in zip(notes, notes[1:]):
        if n.held and prev.pitch is not None and not prev.breath:
            n.lyric = LONG_VOWEL
