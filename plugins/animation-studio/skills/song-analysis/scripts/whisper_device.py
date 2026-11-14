"""Load the Whisper model on the graphics card if possible - otherwise on the CPU (int8).

The GPU needs the CUDA 12 libraries (cuBLAS, cuDNN). If they are installed as pip packages in the running Python
(nvidia-cublas-cu12, nvidia-cudnn-cu12), their bin folders are made visible to Windows here.
Usage in scripts:  from whisper_device import whisper_model;  model, where, name = whisper_model("auto")
Set the environment variable WHISPER_CPU=1 to force the CPU.
"""
import os
import site
import sys
from pathlib import Path


def _dll_paths():
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        nv = Path(sp) / "nvidia"
        if nv.is_dir():
            for b in nv.glob("*/bin"):
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(str(b))
                os.environ["PATH"] = str(b) + os.pathsep + os.environ.get("PATH", "")


GPU_MODEL, CPU_MODEL = "large-v3", "small"     # "auto": accurate model on the graphics card, small one on the CPU


def whisper_model(name="auto"):
    """-> (model, "GPU"/"CPU", model name). name="auto" picks large-v3 (GPU) or small (CPU)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _studio
    _studio.use()
    import config
    config.setup_env()
    from faster_whisper import WhisperModel
    if os.environ.get("WHISPER_CPU"):
        n = CPU_MODEL if name == "auto" else name
        return WhisperModel(n, device="cpu", compute_type="int8"), "CPU", n
    from gpu_lock import acquire
    acquire("whisper", model="whisper:" + (GPU_MODEL if name == "auto" else name))   # only one AI job at a time
    try:
        _dll_paths()
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            n = GPU_MODEL if name == "auto" else name
            m = WhisperModel(n, device="cuda", compute_type="float16")
            import numpy as np
            list(m.transcribe(np.zeros(16000, np.float32), language="de")[0])      # probe: really loads cuBLAS/cuDNN
            return m, "GPU", n
    except Exception as e:                                                           # missing DLLs, no CUDA ...
        print(f"Whisper: GPU not usable ({str(e)[:90]}) - using the CPU", file=sys.stderr)
    n = CPU_MODEL if name == "auto" else name
    return WhisperModel(n, device="cpu", compute_type="int8"), "CPU", n
