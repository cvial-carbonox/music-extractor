"""
annotator.py — Dibuja los acordes detectados sobre la imagen de la página.

Representación preferida: cada acorde se rotula en su posición (x, y) detectada,
justo encima del pentagrama correspondiente (``page.chord_boxes``). Si no hay
posiciones disponibles, se recurre a una banda-cabecera con la lista de acordes
(``page.chords_found``).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

from PIL import Image, ImageDraw, ImageFont

from config import Config
from frame_extractor import PageResult

logger = logging.getLogger(__name__)

_CHORD_COLOR = (200, 30, 30)      # rojo, resalta sobre el pentagrama negro
_LABEL_BG = (255, 255, 210)       # fondo crema para legibilidad


def _load_font(size: int) -> ImageFont.ImageFont:
    """Intenta una fuente TrueType legible; si no, la de mapa de bits."""
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_label(draw: ImageDraw.ImageDraw, text: str, x: int, y: int,
                font: ImageFont.ImageFont) -> None:
    """Dibuja ``text`` en (x, y) con un fondo para legibilidad."""
    x = max(x, 0)
    y = max(y, 0)
    left, top, right, bottom = draw.textbbox((x, y), text, font=font)
    draw.rectangle([left - 2, top - 1, right + 2, bottom + 1], fill=_LABEL_BG)
    draw.text((x, y), text, fill=_CHORD_COLOR, font=font)


def annotate_page(
    page_path: Union[str, Path],
    page: PageResult,
    out_path: Union[str, Path],
    config: Config,
) -> Path:
    """Rotula los acordes de ``page`` sobre ``page_path`` y guarda en ``out_path``.

    Usa ``page.chord_boxes`` (posiciones) si están disponibles; si no, dibuja
    una cabecera con ``page.chords_found``. Sin acordes, copia la imagen.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    boxes = getattr(page, "chord_boxes", []) or []
    chords = getattr(page, "chords_found", []) or []

    with Image.open(page_path) as img:
        canvas = img.convert("RGB")
        draw = ImageDraw.Draw(canvas)

        if boxes:
            # Representación por posición: cada acorde sobre su compás.
            font = _load_font(size=max(int(canvas.height * 0.020), 14))
            for hit in boxes:
                _draw_label(draw, hit.text, int(hit.x), int(hit.y), font)
        elif chords:
            # Respaldo: banda-cabecera con la lista de acordes de la página.
            font = _load_font(size=max(int(canvas.height * 0.025), 16))
            label = "Acordes: " + "  ".join(chords)
            left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
            pad = 8
            draw.rectangle(
                [0, 0, min(right - left + 2 * pad, canvas.width), bottom - top + 2 * pad],
                fill=_LABEL_BG,
            )
            draw.text((pad, pad), label, fill=_CHORD_COLOR, font=font)

        canvas.save(out_path)

    return out_path
