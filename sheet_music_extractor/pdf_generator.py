"""
pdf_generator.py — Generación del PDF final a partir de las imágenes.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Union

import img2pdf

logger = logging.getLogger(__name__)


def images_to_pdf(
    image_paths: List[Union[str, Path]],
    output_path: Union[str, Path],
    dpi: int = 300,
) -> Path:
    """Combina las imágenes dadas en un único PDF, en orden y a ``dpi``.

    Args:
        image_paths: rutas de las imágenes (una por página).
        output_path: ruta del PDF de salida.
        dpi: resolución con la que se dimensionan las páginas del PDF.

    Raises:
        ValueError: si no se proporciona ninguna imagen.
    """
    if not image_paths:
        raise ValueError("No hay imágenes para generar el PDF")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    paths = [str(p) for p in image_paths]
    layout = img2pdf.get_fixed_dpi_layout_fun((dpi, dpi))
    with open(output_path, "wb") as fh:
        fh.write(img2pdf.convert(paths, layout_fun=layout))

    logger.info("PDF generado con %d páginas (%d dpi) en %s", len(paths), dpi, output_path)
    return output_path
