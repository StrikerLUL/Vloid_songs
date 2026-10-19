# chord_spice.py – Akkord-Würze (1.3.0, M6)
#
# Jeder Stil hat 4 bis 6 Akkordfolgen je Sektion. Die Würze ändert einzelne Takte so, wie es Anime- und
# Vocaloid-Songs tun: eine Zwischendominante vor dem Ziel (III7 vor vi, VI7 vor ii, I7 vor IV), Leihakkorde aus Moll
# (IV – iv – I, und bVI – bVII – I als Schluss), verminderte Durchgänge (I – #Idim – ii, IV – #IVdim – V), sus4 vor der
# Dominante und ein laufender Bass (I – I/7 – vi – vi/5 – IV). Im Refrain kann statt der Folge des Stils die
# Marusa-Folge spielen (IVmaj7 III7 vi7 I7), die es bis 1.2 nur im City Pop gab. amount (0 bis 1) sagt, wie oft;
# 0 ändert nichts. Gleiche Sektionsarten bekommen dieselbe Würze (der zweite Refrain klingt wie der erste).
import random

# Wie oft an einer passenden Stelle, bei voller Würze
CHANCES = {"secondary": 0.5, "borrowed": 0.4, "cadence": 0.35, "passing": 0.35, "sus4": 0.5, "walk": 0.5,
           "marusa": 0.3}
MARUSA = "IVmaj7 | III7 | vi7 | I7"
# Ziel der Zwischendominante → die Dominante dazu (Dur und Moll)
SECONDARY = {"major": {"vi": "III7", "ii": "VI7", "IV": "I7"}, "minor": {"iv": "I7", "bVI": "bIII7"}}
# Durchgang zwischen zwei Akkorden
PASSING = {("I", "ii"): "#Idim", ("IV", "V"): "#IVdim", ("ii", "iii"): "#iidim"}
NO_SPICE = ("Rap",)                  # dort spielt die Band wie in der Strophe, aber ohne Würze unter dem Sprechgesang


def _degree(symbol: str) -> str:
    """'vi7' → 'vi', 'V/3' → 'V', 'IVmaj7' → 'IV', 'bVII' → 'bVII'."""
    base = symbol.split("/")[0]
    for suffix in ("maj7", "7sus4", "sus4", "add9", "dim", "m7b5", "7", "9", "6", "o"):
        if base.endswith(suffix) and len(base) > len(suffix):
            base = base[:-len(suffix)]
            break
    return base


def marusa(kind: str, mode_class: str, amount: float, rng: random.Random) -> bool:
    """Spielt dieser Refrain die Marusa-Folge? Nur in Dur und nur, wenn die Würze an ist."""
    return kind == "Chorus" and mode_class == "major" and amount > 0 and rng.random() < CHANCES["marusa"] * amount


def season(bars: list, kind: str, mode_class: str, amount: float, rng: random.Random) -> tuple:
    """
    Die Takte [[Stufen]] einer Sektion mit Würze; nur Takte mit einem einzigen Akkord ändern sich (und der
    Schluss IV V vor I). Rückgabe: (neue Takte, [was geändert wurde]).
    """
    if amount <= 0 or kind in NO_SPICE:
        return bars, []
    out = [list(bar) for bar in bars]
    done = []

    def lucky(what: str) -> bool:
        return rng.random() < CHANCES[what] * amount

    for b in range(len(out) - 1):
        bar, nxt = out[b], out[b + 1]
        here, there = _degree(bar[-1]), _degree(nxt[0])
        if len(bar) != 1:
            if mode_class == "major" and [_degree(x) for x in bar] == ["IV", "V"] and there == "I" \
                    and lucky("cadence"):
                out[b] = ["bVI", "bVII"]
                done.append("bVI bVII vor I")
            continue
        if b + 2 < len(out) and here == "I" and there == "vi" and len(nxt) == 1 \
                and _degree(out[b + 2][0]) == "IV" and lucky("walk"):
            out[b] = [bar[0], "Imaj7/7"]
            out[b + 1] = [nxt[0], "vi/5"]
            done.append("laufender Bass")
            continue
        target = SECONDARY[mode_class].get(there)
        if target and here != _degree(target) and lucky("secondary"):
            if here == "iii" and target == "III7":
                out[b] = ["III7"]
            else:
                out[b] = [bar[0], target]
            done.append(f"{target} vor {there}")
            continue
        if mode_class == "major" and here == "IV" and there == "I" and lucky("borrowed"):
            out[b] = [bar[0], "iv"]
            done.append("iv vor I")
            continue
        passing = PASSING.get((here, there))
        if passing and mode_class == "major" and lucky("passing"):
            out[b] = [bar[0], passing]
            done.append(passing)
            continue
        if there == "V" and len(nxt) == 1 and nxt[0] in ("V", "V7") and lucky("sus4"):
            out[b + 1] = ["Vsus4" if nxt[0] == "V" else "V7sus4", nxt[0]]
            done.append("sus4 vor V")
    return out, done
