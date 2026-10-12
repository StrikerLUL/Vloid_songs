# polish_worker.py – läuft in der Umgebung von ACE-Step 1.5 (tools/ace-step), nicht in der App
#
# Aufruf: python -P polish_worker.py auftrag.json
# Der Auftrag beschreibt entweder eine Probe ({"probe": true}) oder eine Veredelung der Band: ACE-Step nimmt die
# fertige Band als Vorlage („Cover“), behält Takt, Akkorde und Melodie und spielt sie mit eigenem Klang neu ein.
# Die letzte Zeile mit MARKER enthält das Ergebnis als JSON.
import json
import os
import sys

MARKER = "VEREDELT "
MODEL = "acestep-v15-turbo"


def _gpu() -> dict:
    import torch
    if not torch.cuda.is_available():
        return {"cuda": False, "name": "", "memory_gb": 0.0}
    props = torch.cuda.get_device_properties(0)
    return {"cuda": True, "name": props.name, "memory_gb": round(props.total_memory / 1024 ** 3, 1)}


def _handler(root: str):
    """Das Modell so laden, wie es ACE-Step selbst für die erkannte Grafikkarte tut (Auslagern, INT8)."""
    from acestep.gpu_config import get_gpu_config, set_global_gpu_config
    from acestep.handler import AceStepHandler
    gpu = get_gpu_config()
    set_global_gpu_config(gpu)
    quantization = None
    if gpu.quantization_default:
        quantization = "int8_weight_only"
        import torch
        if torch.cuda.is_available() and torch.cuda.get_device_capability(0)[0] < 7:
            quantization = "w8a8_dynamic"
    dit = AceStepHandler()
    message, ok = dit.initialize_service(project_root=root, config_path=MODEL, device="auto",
                                         offload_to_cpu=gpu.offload_to_cpu_default,
                                         offload_dit_to_cpu=gpu.offload_dit_to_cpu_default,
                                         quantization=quantization)
    if not ok:
        raise SystemExit(f"ACE-Step startet nicht: {message}")
    return dit


def polish(job: dict) -> dict:
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    dit = _handler(job["root"])
    params = GenerationParams(
        task_type="cover", src_audio=job["source"], caption=job["caption"], lyrics="[Instrumental]",
        instrumental=True, bpm=job["bpm"], keyscale=job["key"], timesignature="4",
        inference_steps=8, shift=3.0, seed=job["seed"], thinking=False,
        use_cot_metas=False, use_cot_caption=False, use_cot_language=False,
        audio_cover_strength=1.0, cover_noise_strength=job["keep"])
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[job["seed"]], audio_format="wav")
    result = generate_music(dit, None, params, config, save_dir=job["folder"])
    if not result.success or not result.audios or not result.audios[0].get("path"):
        raise SystemExit(f"ACE-Step: {result.error or result.status_message}")
    return {"path": os.path.abspath(result.audios[0]["path"])}


def main(argv: list) -> int:
    with open(argv[1], encoding="utf-8") as f:
        job = json.load(f)
    if job.get("probe"):
        import acestep  # noqa: F401  (ist ACE-Step installiert?)
        found = _gpu()
    else:
        found = polish(job)
    print(MARKER + json.dumps(found), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
