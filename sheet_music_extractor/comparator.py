"""Comparación de partituras para detectar duplicados musicales.

Cuando OMR está activo, dos frames visualmente distintos (distinto zoom,
resaltado del compás actual, etc.) pueden corresponder a la misma música.
Comparando su MusicXML con ``musicdiff`` podemos detectar y descartar esos
duplicados. La función es best-effort: si las dependencias no están o la
comparación falla, devuelve ``None`` y el pipeline usa sólo el dedupe visual.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger(__name__)


def musical_difference(a: Union[str, Path], b: Union[str, Path]) -> Optional[int]:
    """Número de diferencias musicales entre dos MusicXML (0 = idénticas).

    Devuelve ``None`` si ``musicdiff`` no está disponible o la comparación
    no se puede realizar.
    """
    try:
        from musicdiff import diff
    except ImportError:
        logger.info("musicdiff no disponible; se omite la comparación musical")
        return None

    try:
        # diff() devuelve el número de diferencias detectadas. Se le pide que
        # no genere las visualizaciones PDF (out_path*=None).
        num = diff(str(a), str(b), out_path1=None, out_path2=None)
        return int(num) if num is not None else None
    except Exception as exc:
        logger.warning("Comparación musical falló entre %s y %s: %s", a, b, exc)
        return None


def deduplicate_by_music(
    page_paths: List[Path],
    xml_paths: List[Optional[Path]],
    max_diff: int = 0,
) -> List[Path]:
    """Elimina páginas cuya música coincida con una página anterior.

    Args:
        page_paths: rutas de las imágenes de cada página.
        xml_paths: MusicXML correspondiente a cada página (o ``None``).
        max_diff: máximo número de diferencias para considerar duplicado.

    Returns:
        La lista de imágenes conservadas, preservando el orden.
    """
    kept_pages: List[Path] = []
    kept_xml: List[Path] = []

    for page, xml in zip(page_paths, xml_paths):
        if xml is None:
            # Sin partitura reconocida no podemos comparar: conservar.
            kept_pages.append(page)
            continue

        is_duplicate = False
        for ref_xml in kept_xml:
            diff = musical_difference(xml, ref_xml)
            if diff is not None and diff <= max_diff:
                is_duplicate = True
                break

        if not is_duplicate:
            kept_pages.append(page)
            kept_xml.append(xml)

    logger.info(
        "Dedupe musical: %d -> %d páginas", len(page_paths), len(kept_pages)
    )
    return kept_pages
