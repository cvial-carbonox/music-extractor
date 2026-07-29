"""
annotator.py — Dibuja los acordes detectados sobre la imagen de la página.

``OCREngine`` produce una lista de acordes a nivel de página (cadenas ya
deduplicadas, sin coordenadas individuales). Por tanto se rotulan como una
banda-cabecera en la parte superior de la página, en lugar de sobre cada
posición concreta.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Union

from PIL import Image, ImageDraw, ImageFont

from config import Config

logger = logging.getLogger(__name__)

_CHORD_COLOR = (200, 30, 30)      # rojo, resalta sobre el pentagrama negro
_BANNER_BG = (255, 255, 210)      # fondo crema para legibilidad


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
    chords: List[str],
    out_path: Union[str, Path],
    config: Config,
) -> Path:
    """Rotula ``chords`` sobre la imagen ``page_path`` y la guarda en ``out_path``.

    Si no hay acordes, guarda la imagen tal cual para mantener la numeración.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(page_path) as img:
        page = img.convert("RGB")
        if chords:
            draw = ImageDraw.Draw(page)
            font = _load_font(size=max(int(page.height * 0.025), 16))
            label = "Acordes: " + "  ".join(chords)

            # Caja de fondo para que el texto sea legible sobre la partitura.
            left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
            pad = 8
            draw.rectangle(
                [0, 0, min(right - left + 2 * pad, page.width), bottom - top + 2 * pad],
                fill=_BANNER_BG,
            )
            draw.text((pad, pad), label, fill=_CHORD_COLOR, font=font)
        page.save(out_path)

    return out_path
