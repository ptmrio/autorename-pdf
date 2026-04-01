"""Bridge script that runs inside the PaddleOCR venv.

Reads image paths from stdin (one per line), outputs JSON to stdout.
Stays alive to avoid cold-start overhead on multiple pages.

Requires PaddleOCR 3.x+ (pinned to 3.4.0 by setup.ps1).

Usage: python _paddleocr_bridge.py <lang> [--device <auto|cpu|gpu>]
       [--det-model <model_name>] [--det-limit <pixels>] [--cpu-threads <n>]
"""
import os
import sys
import json

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

# --- Memory management ---
# CPU memory flags: only affect BuddyAllocator on macOS ARM64 (Windows/Linux
# CPU use plain malloc, so these are no-ops there). Defensive defaults.
# GPU flags: auto_growth avoids upfront VRAM pre-allocation.
# eager_delete: frees temporary tensors immediately (minor effect on inference path).
os.environ.setdefault("FLAGS_fraction_of_cpu_memory_to_use", "0.3")
os.environ.setdefault("FLAGS_initial_cpu_memory_in_mb", "100")
os.environ.setdefault("FLAGS_eager_delete_tensor_gb", "0.0")
os.environ.setdefault("FLAGS_allocator_strategy", "auto_growth")
os.environ.setdefault("FLAGS_fraction_of_gpu_memory_to_use", "0.3")
# oneDNN cache limit — defense-in-depth (mkldnn is disabled via enable_mkldnn=False)
os.environ.setdefault("MKLDNN_CACHE_CAPACITY", "10")


def _configure_stdio_utf8() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass


_configure_stdio_utf8()


# Lang code to PP-OCRv5 recognition model mapping.
# Mirrors PaddleOCR's _get_ocr_model_names() so we can use explicit model names
# (which avoids the "lang will be ignored" warning in PaddleOCR 3.4+).
_LANG_TO_REC_MODEL = {}
_lang_groups = {
    "PP-OCRv5_server_rec": ["ch", "chinese_cht", "japan"],
    "en_PP-OCRv5_mobile_rec": ["en"],
    "korean_PP-OCRv5_mobile_rec": ["korean"],
    "th_PP-OCRv5_mobile_rec": ["th"],
    "el_PP-OCRv5_mobile_rec": ["el"],
    "te_PP-OCRv5_mobile_rec": ["te"],
    "ta_PP-OCRv5_mobile_rec": ["ta"],
    "latin_PP-OCRv5_mobile_rec": [
        "af", "az", "bs", "ca", "cs", "cy", "da", "de", "es", "et", "eu",
        "fi", "fr", "french", "ga", "german", "gl", "hr", "hu", "id", "is",
        "it", "ku", "la", "lb", "lt", "lv", "mi", "ms", "mt", "nl", "no",
        "oc", "pi", "pl", "pt", "qu", "rm", "ro", "rs_latin", "sk", "sl",
        "sq", "sv", "sw", "tl", "tr", "uz", "vi",
    ],
    "eslav_PP-OCRv5_mobile_rec": ["ru", "be", "uk"],
    "arabic_PP-OCRv5_mobile_rec": ["ar", "fa", "ug", "ur", "ps", "sd", "bal"],
    "cyrillic_PP-OCRv5_mobile_rec": [
        "rs_cyrillic", "bg", "mn", "abq", "ady", "kbd", "ava", "dar", "inh",
        "che", "lbe", "lez", "tab", "kk", "ky", "tg", "mk", "tt", "cv",
        "ba", "mhr", "mo", "udm", "kv", "os", "bua", "xal", "tyv", "sah",
        "kaa",
    ],
    "devanagari_PP-OCRv5_mobile_rec": [
        "hi", "mr", "ne", "bh", "mai", "ang", "bho", "mah", "sck", "new",
        "gom", "sa", "bgc",
    ],
}
for _model, _langs in _lang_groups.items():
    for _lang in _langs:
        _LANG_TO_REC_MODEL[_lang] = _model
del _lang_groups


def _init_v3(lang="en", device="auto", det_model=None, det_limit=736, cpu_threads=4):
    """Initialize PaddleOCR v3.x (3.0+).

    lang: language code — mapped to the correct recognition model.
    device: "auto" (omit, let PaddleOCR decide), "cpu", or "gpu".
    det_model: detection model name (default: PP-OCRv5_mobile_det for lower RAM).
    det_limit: max image side length for detection (lower = less RAM).
    cpu_threads: CPU threads for inference (default: 4).
    If GPU init fails, falls back to auto-detect with a warning.

    Note: lang is not passed to PaddleOCR directly — PaddleOCR 3.4+ ignores it
    when explicit model names are set. Instead we resolve it to the correct
    text_recognition_model_name ourselves.
    """
    from paddleocr import PaddleOCR

    rec_model = _LANG_TO_REC_MODEL.get(lang)
    if not rec_model:
        print(json.dumps({
            "status": "warning",
            "message": f"Unknown lang '{lang}', falling back to English recognition model"
        }), file=sys.stderr)
        rec_model = "en_PP-OCRv5_mobile_rec"

    kwargs = {
        "text_recognition_model_name": rec_model,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        # Disable MKL-DNN/oneDNN — crashes on Windows with PaddlePaddle 3.x
        # (ConvertPirAttribute2RuntimeAttribute not support pir::ArrayAttribute)
        "enable_mkldnn": False,
        "text_det_limit_side_len": det_limit,
        "text_det_limit_type": "max",
        "cpu_threads": cpu_threads,
    }
    if det_model:
        kwargs["text_detection_model_name"] = det_model
    else:
        kwargs["text_detection_model_name"] = "PP-OCRv5_mobile_det"
    if device in ("gpu", "cpu"):
        kwargs["device"] = device

    try:
        return PaddleOCR(**kwargs)
    except Exception as e:
        if device == "gpu":
            print(json.dumps({
                "status": "warning",
                "message": f"GPU init failed ({e}), falling back to auto-detect"
            }), file=sys.stderr)
            kwargs.pop("device", None)
            return PaddleOCR(**kwargs)
        raise


def _extract_v3(ocr, path):
    """PaddleOCR v3.x: .predict() yields result objects with rec_texts.

    v3.4+ nests results under a "res" key: data["res"]["rec_texts"].
    Earlier v3.x had rec_texts at the top level.
    """
    texts = []
    for page_result in ocr.predict(input=path):
        if hasattr(page_result, "json"):
            data = page_result.json
        elif isinstance(page_result, dict):
            data = page_result
        else:
            data = {}
        # v3.4+: rec_texts is inside data["res"]
        # v3.0-3.3: rec_texts is at top level
        rec = data.get("res", data) if isinstance(data.get("res"), dict) else data
        texts.extend(rec.get("rec_texts", []))
    return texts


def main():
    lang = sys.argv[1] if len(sys.argv) > 1 else "en"
    device = "auto"
    if "--device" in sys.argv:
        idx = sys.argv.index("--device")
        if idx + 1 < len(sys.argv):
            device = sys.argv[idx + 1]

    det_model = None
    if "--det-model" in sys.argv:
        idx = sys.argv.index("--det-model")
        if idx + 1 < len(sys.argv):
            det_model = sys.argv[idx + 1]

    det_limit = 736
    if "--det-limit" in sys.argv:
        idx = sys.argv.index("--det-limit")
        if idx + 1 < len(sys.argv):
            det_limit = int(sys.argv[idx + 1])

    cpu_threads = 4
    if "--cpu-threads" in sys.argv:
        idx = sys.argv.index("--cpu-threads")
        if idx + 1 < len(sys.argv):
            cpu_threads = int(sys.argv[idx + 1])

    ocr = _init_v3(lang=lang, device=device, det_model=det_model, det_limit=det_limit, cpu_threads=cpu_threads)

    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue
        try:
            texts = _extract_v3(ocr, path)
            print(json.dumps({"status": "ok", "text": "\n".join(texts)}), flush=True)
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}), flush=True)


if __name__ == "__main__":
    main()
