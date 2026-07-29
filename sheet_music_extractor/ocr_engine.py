"""
ocr_engine.py — OCR de texto y detección de acordes con pytesseract.

Dos usos:
  * ``guess_title`` deduce un título de la cabecera de la primera página.
  * ``detect_chords`` busca símbolos de acorde (C, G7, Am, F#m7…) en la banda
    situada encima de cada pentagrama.

Todo es opcional: si Tesseract no está instalado, las funciones devuelven
resultados vacíos y el pipeline continúa.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

import numpy as np

try:
    import pytesseract
    from PIL import Image
except ImportError:  # pragma: no cover
    pytesseract = None
    Image = None

import staff_detector
from config import Config

logger = logging.getLogger(__name__)

# Patrón razonable para símbolos de acorde de cifrado americano.
CHORD_RE = re.compile(
    r"^[A-G](#|b|♯|♭)?"                       # tónica
    r"(maj7|maj|min|m|dim|aug|sus2|sus4|sus|add|°|ø)?"  # calidad
    r"\d{0,2}"                                # extensión (7, 9, 13…)
    r"(\((#|b)?\d{1,2}\))?"                    # alteración entre paréntesis
    r"(/[A-G](#|b)?)?$"                        # bajo invertido
)


@dataclass
class Chord:
    """Símbolo de acorde detectado con su posición en la imagen."""

    text: str
    x: int
    y: int


def is_available() -> bool:
    """Indica si pytesseract y el binario de Tesseract están disponibles."""
    if pytesseract is None:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def extract_text(image_path: Union[str, Path], config: Config) -> str:
    """Devuelve el texto reconocido en una imagen (o cadena vacía)."""
    if not is_available():
        logger.info("OCR no disponible; se omite la extracción de texto")
        return ""
    try:
        with Image.open(image_path) as img:
            return pytesseract.image_to_string(img, lang=config.ocr_languages).strip()
    except Exception as exc:
        logger.warning("OCR falló en %s: %s", image_path, exc)
        return ""


def guess_title(image_path: Union[str, Path], config: Config) -> str:
    """Deduce un título a partir de la banda superior de una página."""
    if not is_available() or Image is None:
        return ""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            header = img.crop((0, 0, width, max(int(height * 0.20), 1)))
            text = pytesseract.image_to_string(header, lang=config.ocr_languages)
    except Exception as exc:
        logger.warning("No se pudo deducir el título en %s: %s", image_path, exc)
        return ""

    for line in text.splitlines():
        line = line.strip()
        if len(line) >= 3:
            return _sanitize(line)
    return ""


def detect_chords(image: np.ndarray, config: Config) -> List[Chord]:
    """Detecta acordes en la banda encima de cada pentagrama de ``image``.

    Args:
        image: frame BGR de una página.
        config: configuración (``chord_region_offset``, ``ocr_languages``).

    Returns:
        Lista de :class:`Chord` con texto y coordenadas absolutas.
    """
    if not config.detect_chords or not is_available():
        return []

    info = staff_detector.detect(image, config)
    if info.count == 0:
        return []

    height, width = image.shape[:2]
    offset = max(config.chord_region_offset, 1)
    chords: List[Chord] = []

    for system in info.systems():
        top = min(system)
        band_top = max(top - offset, 0)
        if top <= band_top:
            continue
        band = image[band_top:top, 0:width]
        chords.extend(_ocr_chords_in_band(band, band_top, config))

    return chords


def _ocr_chords_in_band(band: np.ndarray, band_top: int, config: Config) -> List[Chord]:
    """OCR de una banda; devuelve los tokens que parecen acordes."""
    try:
        data = pytesseract.image_to_data(
            band, lang=config.ocr_languages, output_type=pytesseract.Output.DICT
        )
    except Exception as exc:
        logger.warning("OCR de acordes falló: %s", exc)
        return []

    found: List[Chord] = []
    for text, left, top, conf in zip(
        data["text"], data["left"], data["top"], data["conf"]
    ):
        token = (text or "").strip()
        try:
            confidence = float(conf)
        except (TypeError, ValueError):
            confidence = -1.0
        if token and confidence >= 40 and CHORD_RE.match(token):
            found.append(Chord(text=token, x=int(left), y=band_top + int(top)))
    return found


def _sanitize(text: str) -> str:
    """Limpia una cadena para usarla como nombre de archivo."""
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:80]
