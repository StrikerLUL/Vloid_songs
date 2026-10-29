# hoercheck_worker.py – hört eine Gesangsspur mit japanischer Spracherkennung ab (faster-whisper, Hör-Check)
#
# Läuft nicht in der App, sondern in der eigenen Umgebung tools/hoercheck (setup_hoercheck.py legt sie an), damit
# ihre Bibliotheken die der App nicht berühren. Deshalb nutzt diese Datei nichts aus der App.
#
#   python hoercheck_worker.py auftrag.json
#
# auftrag.json: {"model", "audio", "output", "folder"}. Die Wörter mit Zeiten landen als JSON-Liste in "output", die
# letzte Zeile der Ausgabe ist "HOERCHECK " und ihre Anzahl. Der Text des Songs wird bewusst nicht mitgegeben: die
# Erkennung soll hören, was wirklich gesungen wurde, und nicht erraten, was gemeint war.
import json
import sys

MARKER = "HOERCHECK "


def without_links() -> None:
    """Echte Modelldateien statt Verknüpfungen (siehe rating_worker.py)."""
    try:
        import huggingface_hub.file_download as download
    except ImportError:
        return
    download.are_symlinks_supported = lambda *args, **kwargs: False


def main(path: str) -> int:
    from faster_whisper import WhisperModel

    with open(path, encoding="utf-8") as f:
        order = json.load(f)
    without_links()
    model = WhisperModel(order["model"], device="cpu", compute_type="int8", download_root=order.get("folder"))
    segments, _ = model.transcribe(order["audio"], language="ja", word_timestamps=True, beam_size=5,
                                   condition_on_previous_text=False, vad_filter=False)
    words = []
    for segment in segments:
        for word in segment.words or ():
            words.append({"start": round(float(word.start), 3), "end": round(float(word.end), 3),
                          "word": word.word, "p": round(float(word.probability), 3)})
    with open(order["output"], "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False)
    print(MARKER + str(len(words)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
