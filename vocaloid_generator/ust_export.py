# ust_export.py – Gesangsnoten als UTAU-Projekt (.ust), das OpenUtau und UTAU öffnen
#
# Eine UST ist eine Textdatei: Tempo im Kopf, danach jede Note mit Länge (480 Ticks pro Viertel), Silbe
# und Tonhöhe; Pausen heißen "R". Geschrieben wird in Shift-JIS, wie UTAU es erwartet.
import os

TICKS_PER_QUARTER = 480
REST = "R"


def schreibe_ust(melodie_daten, silben, bpm: float, pfad: str, transpose: int = 0, projekt: str = "") -> str:
    """
    melodie_daten: [(Tonhöhe oder None für Pause, Dauer in Vierteln)] ab Songanfang, silben: eine pro Note.
    Gibt den Pfad zurück. Ticks werden aus den Gesamtzeiten gerundet, damit sich nichts verschiebt.
    """
    noten, t, i = [], 0.0, 0
    for pitch, dauer in melodie_daten:
        start, t = t, t + float(dauer)
        if pitch is None:
            if noten and noten[-1][2] == REST:
                noten[-1] = (noten[-1][0], t, REST, 60)
            else:
                noten.append((start, t, REST, 60))
            continue
        silbe = str(silben[i]) if i < len(silben) else "ら"
        noten.append((start, t, silbe, int(pitch) + transpose))
        i += 1

    zeilen = ["[#VERSION]", "UST Version1.2", "[#SETTING]", f"Tempo={bpm:.2f}", "Tracks=1",
              f"ProjectName={projekt or os.path.splitext(os.path.basename(pfad))[0]}", "Mode2=True"]
    for k, (start, ende, silbe, notenummer) in enumerate(noten):
        laenge = round(ende * TICKS_PER_QUARTER) - round(start * TICKS_PER_QUARTER)
        if laenge <= 0:
            continue
        zeilen += [f"[#{k:04d}]", f"Length={laenge}", f"Lyric={silbe}", f"NoteNum={notenummer}",
                   "PreUtterance=", "Intensity=100", "Modulation=0"]
    zeilen.append("[#TRACKEND]")
    os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
    with open(pfad, "w", encoding="cp932", errors="replace", newline="\r\n") as f:
        f.write("\n".join(zeilen) + "\n")
    return pfad


def lies_ust(pfad: str) -> list:
    """[(Länge in Ticks, Silbe, Notennummer)] einer UST, für Tests und zum Prüfen."""
    noten, aktuell = [], None
    with open(pfad, encoding="cp932") as f:
        for zeile in f.read().splitlines():
            if zeile.startswith("[#") and zeile[2:6].isdigit():
                aktuell = {}
                noten.append(aktuell)
            elif aktuell is not None and "=" in zeile:
                key, value = zeile.split("=", 1)
                aktuell[key] = value
            elif zeile.startswith("[#TRACKEND]"):
                aktuell = None
    return [(int(n["Length"]), n["Lyric"], int(n["NoteNum"])) for n in noten]
