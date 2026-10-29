# bilder_worker.py – malt die KI-Hintergründe fürs Musikvideo (LCM Dreamshaper v7)
#
# Läuft nicht in der App, sondern in der eigenen Umgebung tools/bilder (setup_bilder.py legt sie an), damit PyTorch
# die Bibliotheken der App nicht berührt. Deshalb nutzt diese Datei nichts aus der App.
#
#   python bilder_worker.py auftrag.json
#
# auftrag.json: {"model", "width", "height", "steps", "jobs": [{"path", "prompt", "seed"}]}. Die letzte Zeile der
# Ausgabe ist "BILDER " und eine JSON-Liste der gemalten Dateien.
import json
import sys

MARKER = "BILDER "


def without_links() -> None:
    """Echte Modelldateien statt Verknüpfungen (siehe rating_worker.py)."""
    try:
        import huggingface_hub.file_download as download
    except ImportError:
        return
    download.are_symlinks_supported = lambda *args, **kwargs: False


def main(path: str) -> int:
    import torch
    from diffusers import DiffusionPipeline

    with open(path, encoding="utf-8") as f:
        order = json.load(f)
    without_links()
    gpu = torch.cuda.is_available()
    pipe = DiffusionPipeline.from_pretrained(order["model"], torch_dtype=torch.float16 if gpu else torch.float32,
                                             safety_checker=None)
    if gpu:
        pipe = pipe.to("cuda")
        pipe.enable_attention_slicing()             # passt so auch in 4 GB Grafikspeicher
    print(f"Male auf {'der Grafikkarte' if gpu else 'dem Prozessor'}", flush=True)
    done = []
    for job in order["jobs"]:
        generator = torch.Generator("cuda" if gpu else "cpu").manual_seed(int(job["seed"]))
        image = pipe(job["prompt"], width=int(order["width"]), height=int(order["height"]),
                     num_inference_steps=int(order["steps"]), guidance_scale=8.0, generator=generator).images[0]
        image.save(job["path"])
        done.append(job["path"])
        print(f"  {job['path']}", flush=True)
    print(MARKER + json.dumps(done), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
