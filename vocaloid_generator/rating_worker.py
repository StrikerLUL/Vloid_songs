# rating_worker.py – bewertet Songs mit Meta Audiobox Aesthetics
#
# Läuft nicht in der App, sondern in der eigenen Umgebung tools/bewertung (setup_bewertung.py legt sie an), damit
# PyTorch die Bibliotheken der App nicht berührt. Deshalb nutzt diese Datei nichts aus der App.
#
#   python rating_worker.py song1.wav song2.wav ...
#
# Die letzte Zeile der Ausgabe ist "BEWERTUNG " und eine JSON-Liste mit CE, CU, PC und PQ (1 bis 10) pro Datei.
import json
import sys

MARKER = "BEWERTUNG "


def main(paths: list) -> int:
    import numpy as np
    import soundfile as sf
    import torch
    from audiobox_aesthetics.infer import initialize_predictor

    predictor = initialize_predictor()
    results = []
    for path in paths:
        # selbst laden: torchaudio.load braucht in neuen Fassungen FFmpeg
        data, rate = sf.read(path, dtype="float32", always_2d=True)
        wav = torch.from_numpy(np.ascontiguousarray(data.T))
        results.append(predictor.forward([{"path": wav, "sample_rate": rate}])[0])
    print(MARKER + json.dumps(results), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
