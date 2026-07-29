"""
annotator.py — Dibuja los acordes detectados sobre la imagen de la página.

Toma la lista de :class:`ocr_engine.Chord` y escribe cada símbolo en su
posición sobre una copia de la página, guardándola en ``annotated_dir``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Union

from PIL import Image, ImageDraw, ImageFont

from config import Config
from ocr_engine import Chord

logger = logging.getLogger(__name__)

_CHORD_COLOR = (200, 30, 30)  # rojo para que resalte sobre el pentagrama negro


def _load_font(size: int) -> ImageFont.ImageFont:
    """Intenta una fuente TrueType legible; si no, la de mapa de bits."""
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate_page(
    page_path: Union[str, Path],
    chords: List[Chord],
    out_path: Union[str, Path],
    config: Config,
) -> Path:
    """Dibuja ``chords`` sobre la imagen ``page_path`` y la guarda en ``out_path``.

    Si no hay acordes, copia la imagen tal cual para mantener la numeración.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(page_path) as img:
        page = img.convert("RGB")
        if chords:
            draw = ImageDraw.Draw(page)
            font = _load_font(size=max(int(config.chord_region_offset * 0.6), 14))
            for chord in chords:
                draw.text((chord.x, chord.y), chord.text, fill=_CHORD_COLOR, font=font)
        page.save(out_path)

    return out_path
