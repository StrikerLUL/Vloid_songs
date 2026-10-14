# accompaniment_worker.py – der Anticipatory Music Transformer schreibt eine Begleitung zu Melodie, Bass und Schlagzeug
#
# Läuft nicht in der App, sondern in der eigenen Umgebung tools/begleitung (setup_begleitung.py legt sie an), damit
# PyTorch die Bibliotheken der App nicht berührt. Deshalb nutzt diese Datei nichts aus der App.
#
#   python -P accompaniment_worker.py auftrag.json
#
# Der Auftrag nennt die vorgegebenen Töne ("notes": [[Start, Ende, Tonhöhe, Instrument], ...], Sekunden, Instrument
# wie im Modell: GM-Programm, 128 = Schlagzeug), die Länge, den Seed und wohin das Ergebnis soll. Das Modell kennt nur
# 100 Sekunden; deshalb schreibt es in Stücken von CHUNK Sekunden, jedes mit den letzten HISTORY Sekunden davor als
# Anfang. Die letzte Zeile der Ausgabe ist "BEGLEITET " und JSON mit Gerät, Modell und Zahl der Töne.
import json
import sys

MARKER = "BEGLEITET "
MODELS = {"cuda": "stanford-crfm/music-medium-800k", "cpu": "stanford-crfm/music-small-800k"}
CHUNK = 30.0
HISTORY = 5.0


def tokens(notes: list, base: float, control: bool) -> list:
    """Töne ab base als Tokens (Zeit, Dauer, Note) des Modells, Zeit relativ zu base."""
    from anticipation.config import MAX_DUR, TIME_RESOLUTION
    from anticipation.vocab import CONTROL_OFFSET, DUR_OFFSET, NOTE_OFFSET, TIME_OFFSET
    shift = CONTROL_OFFSET if control else 0
    out = []
    for start, end, pitch, instr in sorted(notes):
        time = round((start - base) * TIME_RESOLUTION)
        dur = max(1, min(MAX_DUR - 1, round((end - start) * TIME_RESOLUTION)))
        out += [shift + TIME_OFFSET + time, shift + DUR_OFFSET + dur, shift + NOTE_OFFSET + 128 * instr + pitch]
    return out


def notes_of(events: list, base: float) -> list:
    from anticipation.config import TIME_RESOLUTION
    from anticipation.vocab import DUR_OFFSET, NOTE_OFFSET, TIME_OFFSET
    out = []
    for time, dur, note in zip(events[0::3], events[1::3], events[2::3]):
        start = base + (time - TIME_OFFSET) / TIME_RESOLUTION
        instr, pitch = divmod(note - NOTE_OFFSET, 128)
        out.append([round(start, 3), round(start + (dur - DUR_OFFSET) / TIME_RESOLUTION, 3), pitch, instr])
    return out


def accompany(model, given: list, seconds: float, top_p: float) -> list:
    from anticipation.sample import generate
    written = []
    start = 0.0
    while start < seconds:
        base = max(0.0, start - HISTORY)
        end = min(seconds, start + CHUNK)
        controls = tokens([n for n in given if base <= n[0] < end + HISTORY], base, control=True)
        history = tokens([n[:4] for n in written if n[0] >= base], base, control=False)
        events = generate(model, start - base, end - base, inputs=history, controls=controls, top_p=top_p)
        written += [n for n in notes_of(events, base) if start <= n[0] < end]
        print(f"Begleitung bis {end:.0f} von {seconds:.0f} Sekunden", flush=True)
        start = end
    return written


def main(args: list) -> int:
    import torch
    from transformers import AutoModelForCausalLM

    with open(args[0], encoding="utf-8") as f:
        job = json.load(f)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    name = job.get("model") or MODELS[device]
    torch.manual_seed(int(job.get("seed", 0)))
    model = AutoModelForCausalLM.from_pretrained(name).to(device)
    model.eval()
    written = accompany(model, job["notes"], float(job["seconds"]), float(job.get("top_p", 0.95)))
    with open(job["output"], "w", encoding="utf-8") as f:
        json.dump({"notes": written, "model": name}, f)
    print(MARKER + json.dumps({"device": device, "model": name, "notes": len(written)}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
