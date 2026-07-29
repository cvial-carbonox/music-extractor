"""Generación del PDF final a partir de las imágenes de cada página."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Union

import img2pdf

logger = logging.getLogger(__name__)


def images_to_pdf(
    image_paths: List[Union[str, Path]],
    output_path: Union[str, Path],
) -> Path:
    """Combina las imágenes dadas en un único PDF, en orden.

    Args:
        image_paths: rutas de las imágenes (una por página).
        output_path: ruta del PDF de salida.

    Raises:
        ValueError: si no se proporciona ninguna imagen.
    """
    if not image_paths:
        raise ValueError("No hay imágenes para generar el PDF")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    paths = [str(p) for p in image_paths]
    with open(output_path, "wb") as fh:
        fh.write(img2pdf.convert(paths))

    logger.info("PDF generado con %d páginas en %s", len(paths), output_path)
    return output_path
