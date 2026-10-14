# separation_worker.py – zerlegt Songs mit Demucs (htdemucs) in Gesang, Schlagzeug, Bass und Rest
#
# Läuft nicht in der App, sondern in der eigenen Umgebung tools/demucs (setup_demucs.py legt sie an), damit
# PyTorch die Bibliotheken der App nicht berührt. Deshalb nutzt diese Datei nichts aus der App.
#
#   python separation_worker.py song.wav ordner [song2.wav ordner2 ...]
#
# Jeder Ordner bekommt vocals.wav, drums.wav, bass.wav und other.wav. Die letzte Zeile der Ausgabe ist "ZERLEGT "
# und eine JSON-Liste mit dem Gerät und den fertigen Ordnern.
import json
import os
import sys

MARKER = "ZERLEGT "
MODEL = "htdemucs"


def main(args: list) -> int:
    import numpy as np
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    model = get_model(MODEL)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    done = []
    for source, folder in zip(args[::2], args[1::2]):
        # selbst laden: torchaudio.load braucht in neuen Fassungen FFmpeg
        data, rate = sf.read(source, dtype="float32", always_2d=True)
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        wav = torch.from_numpy(np.ascontiguousarray(data[:, :2].T))
        ref = wav.mean(0)
        scale = ref.std() + 1e-8
        with torch.no_grad():
            parts = apply_model(model, ((wav - ref.mean()) / scale)[None], device=device, split=True, overlap=0.25,
                                progress=False)[0]
        parts = parts * scale + ref.mean()
        os.makedirs(folder, exist_ok=True)
        for name, part in zip(model.sources, parts):
            sf.write(os.path.join(folder, name + ".wav"), part.cpu().numpy().T, rate, subtype="FLOAT")
        done.append(folder)
    print(MARKER + json.dumps({"device": device, "done": done}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
