"""OCR de texto (título, compositor) en frames con pytesseract.

Se usa para intentar deducir un nombre de archivo significativo a partir de
la cabecera de la primera página. Es totalmente opcional: si Tesseract no
está instalado, el pipeline continúa sin nombre.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Union

try:
    import pytesseract
    from PIL import Image
except ImportError:  # pragma: no cover
    pytesseract = None
    Image = None

from config import Config

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """Indica si pytesseract y el binario de Tesseract están disponibles."""
    if pytesseract is None:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:  # tesseract no instalado o no en PATH
        return False


def extract_text(image_path: Union[str, Path], config: Config) -> str:
    """Devuelve el texto reconocido en una imagen (o cadena vacía)."""
    if not is_available():
        logger.info("OCR no disponible; se omite la extracción de texto")
        return ""
    try:
        with Image.open(image_path) as img:
            return pytesseract.image_to_string(img, lang=config.ocr_lang).strip()
    except Exception as exc:
        logger.warning("OCR falló en %s: %s", image_path, exc)
        return ""


def guess_title(image_path: Union[str, Path], config: Config) -> str:
    """Intenta deducir un título a partir de la parte superior de una página.

    Toma la banda superior de la imagen (donde suele ir el título) y devuelve
    la primera línea de texto no vacía, saneada para usarse como nombre de
    archivo.
    """
    if not is_available() or Image is None:
        return ""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            header = img.crop((0, 0, width, max(int(height * 0.20), 1)))
            text = pytesseract.image_to_string(header, lang=config.ocr_lang)
    except Exception as exc:
        logger.warning("No se pudo deducir el título en %s: %s", image_path, exc)
        return ""

    for line in text.splitlines():
        line = line.strip()
        if len(line) >= 3:  # ignorar ruido de una o dos letras
            return _sanitize(line)
    return ""


def _sanitize(text: str) -> str:
    """Limpia una cadena para poder usarla como nombre de archivo."""
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:80]
