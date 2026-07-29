"""Reconocimiento óptico de música (OMR) con oemer.

oemer convierte la imagen de una partitura en un archivo MusicXML. Es una
etapa opcional y costosa (usa modelos de deep learning), por lo que se ejecuta
vía su CLI y se degrada con elegancia si no está instalado.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Union

from config import Config

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """Indica si oemer está instalado (como paquete o como CLI)."""
    if shutil.which("oemer") is not None:
        return True
    try:
        import oemer  # noqa: F401
        return True
    except ImportError:
        return False


def image_to_musicxml(
    image_path: Union[str, Path],
    out_dir: Union[str, Path],
    config: Config,
) -> Optional[Path]:
    """Convierte una imagen de partitura en MusicXML usando la CLI de oemer.

    Devuelve la ruta al ``.musicxml`` generado, o ``None`` si oemer no está
    disponible o la conversión falla.
    """
    image_path = Path(image_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if shutil.which("oemer") is None:
        logger.info("oemer no está en el PATH; se omite OMR para %s", image_path.name)
        return None

    try:
        subprocess.run(
            ["oemer", str(image_path), "-o", str(out_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("oemer falló en %s: %s", image_path.name, exc.stderr.strip())
        return None

    # oemer escribe <nombre>.musicxml en el directorio de salida.
    xml = out_dir / f"{image_path.stem}.musicxml"
    if xml.exists():
        return xml
    logger.warning("oemer no produjo MusicXML para %s", image_path.name)
    return None
