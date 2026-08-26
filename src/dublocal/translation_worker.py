from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path


def _device_name(torch_module) -> str:
    try:
        if torch_module.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _translate(payload: dict) -> list[str]:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    model_dir = Path(str(payload["model_dir"])).expanduser().resolve()
    texts = [str(item) for item in payload.get("texts", [])]
    target_tag = str(payload.get("target_tag") or "").strip()
    batch_size = max(1, int(payload.get("batch_size") or 8))

    tokenizer = AutoTokenizer.from_pretrained(
        str(model_dir),
        local_files_only=True,
        trust_remote_code=False,
    )
    model = AutoModelForSeq2SeqLM.from_pretrained(
        str(model_dir),
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
    )
    model.eval()

    device = _device_name(torch)
    if device != "cpu":
        model.to(device)

    prepared = [f">>{target_tag}<< {text}" for text in texts] if target_tag else list(texts)

    def run(active_device: str) -> list[str]:
        output: list[str] = []
        for start in range(0, len(prepared), batch_size):
            batch = prepared[start : start + batch_size]
            encoded = tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            encoded = {key: value.to(active_device) for key, value in encoded.items()}
            with torch.inference_mode():
                generated = model.generate(**encoded, max_length=512)
            output.extend(
                tokenizer.batch_decode(
                    generated,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=True,
                )
            )
        return [item.strip() for item in output]

    try:
        try:
            return run(device)
        except RuntimeError:
            if device == "cpu":
                raise
            model.to("cpu")
            return run("cpu")
    finally:
        del model
        gc.collect()
        try:
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="DubLocal isolated translation worker")
    parser.add_argument("request", type=Path)
    parser.add_argument("response", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.request.read_text(encoding="utf-8"))
    try:
        translations = _translate(payload)
        result = {"ok": True, "translations": translations}
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    args.response.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
