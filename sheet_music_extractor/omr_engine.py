"""
omr_engine.py — Reconocimiento óptico de música (OMR) con oemer.

oemer convierte la imagen de una partitura en MusicXML. Es costoso (modelos de
deep learning) y opcional; se ejecuta vía su CLI respetando las opciones de la
configuración (TensorFlow vs ONNX, deskew) y degrada con elegancia si no está
instalado.
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
    """Indica si oemer está instalado (como CLI o como paquete)."""
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

    Respeta ``config.omr_use_tf`` y ``config.omr_without_deskew``. Devuelve la
    ruta al ``.musicxml`` generado, o ``None`` si no está disponible o falla.
    """
    image_path = Path(image_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if shutil.which("oemer") is None:
        logger.info("oemer no está en el PATH; se omite OMR para %s", image_path.name)
        return None

    cmd = ["oemer", str(image_path), "-o", str(out_dir)]
    if config.omr_use_tf:
        cmd.append("--use-tf")
    if config.omr_without_deskew:
        cmd.append("--without-deskew")

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        logger.warning("oemer falló en %s: %s", image_path.name, exc.stderr.strip())
        return None

    xml = out_dir / f"{image_path.stem}.musicxml"
    if xml.exists():
        return xml
    logger.warning("oemer no produjo MusicXML para %s", image_path.name)
    return None
