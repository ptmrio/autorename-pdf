"""Bridge script that runs inside the PaddleOCR venv.

Reads image paths from stdin (one per line), outputs JSON to stdout.
Stays alive to avoid cold-start overhead on multiple pages.

Supports PaddleOCR v2.x (.ocr()) and v3.x (.predict()).

Usage: python _paddleocr_bridge.py <lang> [--gpu]
"""
import os
import sys
import json

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"


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


def _init_v3(lang, use_gpu):
    """Initialize PaddleOCR v3.x (3.0+)."""
    from paddleocr import PaddleOCR

    kwargs = {
        "lang": lang,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        # Disable MKL-DNN/oneDNN — crashes on Windows with PaddlePaddle 3.x
        # (ConvertPirAttribute2RuntimeAttribute not support pir::ArrayAttribute)
        "enable_mkldnn": False,
    }
    if use_gpu:
        kwargs["device"] = "gpu"
    return PaddleOCR(**kwargs)


def _init_v2(lang):
    """Initialize PaddleOCR v2.x."""
    from paddleocr import PaddleOCR
    return PaddleOCR(lang=lang, show_log=False)


def _extract_v3(ocr, path):
    """PaddleOCR v3.x: .predict() yields result objects with rec_texts."""
    texts = []
    for page_result in ocr.predict(input=path):
        # Result object — access .json for dict or direct attributes
        if hasattr(page_result, "json"):
            data = page_result.json
        elif isinstance(page_result, dict):
            data = page_result
        else:
            data = {}
        texts.extend(data.get("rec_texts", []))
    return texts


def _extract_v2(ocr, path):
    """PaddleOCR v2.x: .ocr() returns nested list of [box, (text, conf)]."""
    result = ocr.ocr(path, cls=True)
    texts = []
    if result and result[0]:
        texts = [item[1][0] for item in result[0]]
    return texts


def main():
    lang = sys.argv[1] if len(sys.argv) > 1 else "en"
    use_gpu = "--gpu" in sys.argv

    # Detect API version and initialize
    try:
        import paddleocr
        version = tuple(int(x) for x in paddleocr.__version__.split(".")[:2])
    except Exception:
        version = (2, 0)

    if version >= (3, 0):
        ocr = _init_v3(lang, use_gpu)
        extract = _extract_v3
    else:
        ocr = _init_v2(lang)
        extract = _extract_v2

    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue
        try:
            texts = extract(ocr, path)
            print(json.dumps({"status": "ok", "text": "\n".join(texts)}), flush=True)
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}), flush=True)


if __name__ == "__main__":
    main()
