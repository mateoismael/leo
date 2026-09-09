"""Genera una respuesta corta en español con Chatterbox Multilingual.

Adaptado del motor local de ``ytauto/voz/tts_chatterbox.py``. Este archivo se
ejecuta con el entorno de Chatterbox, separado del entorno del servidor.
"""
import argparse
import re
from pathlib import Path


MAX_CHARS = 280


def split_text(text, limit=MAX_CHARS):
    """Divide texto corto sin cortar oraciones siempre que sea posible."""
    sentences = re.split(r"(?<=[.!?…])\s+", text.replace("\n", " "))
    chunks, current = [], ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        parts = re.split(r"(?<=,)\s+", sentence) if len(sentence) > limit else [sentence]
        for part in parts:
            if len(current) + len(part) + 1 > limit and current:
                chunks.append(current)
                current = ""
            current = f"{current} {part}".strip()
    if current:
        chunks.append(current)
    return chunks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    text = args.text.strip()
    if not text:
        parser.error("El texto está vacío.")

    import torch
    import torchaudio as ta
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    # En esta máquina MPS provocó swap; el motor recuperado usa CPU por defecto.
    device = "cpu"
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    chunks = split_text(text)
    pieces = []
    kwargs = {"language_id": "es"}
    if args.reference:
        kwargs["audio_prompt_path"] = str(args.reference)
    with torch.inference_mode():
        for index, chunk in enumerate(chunks):
            pieces.append(model.generate(chunk, **kwargs).cpu())
            if index + 1 < len(chunks):
                pieces.append(torch.zeros(1, int(model.sr * 0.18)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ta.save(str(args.output), torch.cat(pieces, dim=-1), model.sr)


if __name__ == "__main__":
    main()
