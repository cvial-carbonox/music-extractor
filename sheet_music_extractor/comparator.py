"""
comparator.py — Comparación de la partitura reconocida con una de referencia.

Si se indica ``config.reference_score_path``, se compara cada página
reconocida por OMR (MusicXML) contra la partitura de referencia usando
``musicdiff``, generando las visualizaciones de diferencias en
``comparison_dir``. Es best-effort: si ``musicdiff`` no está instalado o falla,
devuelve ``None``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class PageComparison:
    """Resultado de comparar una página con la referencia."""

    page_index: int
    num_differences: int
    visual_a: Optional[Path] = None
    visual_b: Optional[Path] = None


def musical_difference(
    a: Union[str, Path],
    b: Union[str, Path],
    out_a: Optional[Path] = None,
    out_b: Optional[Path] = None,
) -> Optional[int]:
    """Número de diferencias musicales entre dos MusicXML (0 = idénticas).

    Devuelve ``None`` si ``musicdiff`` no está disponible o la comparación falla.
    Si se dan ``out_a``/``out_b``, genera las visualizaciones marcadas.
    """
    try:
        from musicdiff import diff
    except ImportError:
        logger.info("musicdiff no disponible; se omite la comparación musical")
        return None

    try:
        num = diff(
            str(a),
            str(b),
            out_path1=str(out_a) if out_a else None,
            out_path2=str(out_b) if out_b else None,
        )
        return int(num) if num is not None else None
    except Exception as exc:
        logger.warning("Comparación musical falló entre %s y %s: %s", a, b, exc)
        return None


def compare_to_reference(
    omr_xmls: List[Optional[Path]],
    config: Config,
) -> Optional[List[PageComparison]]:
    """Compara cada MusicXML reconocido con la partitura de referencia.

    Devuelve la lista de :class:`PageComparison`, o ``None`` si no hay
    referencia configurada o no existe el archivo.
    """
    ref = config.reference_score_path
    if not ref:
        return None
    ref_path = Path(ref)
    if not ref_path.exists():
        logger.warning("Partitura de referencia no encontrada: %s", ref_path)
        return None

    config.comparison_dir.mkdir(parents=True, exist_ok=True)
    # ``comparison_details`` describe qué elementos comparar; se registra para
    # trazabilidad (musicdiff aplica su nivel de detalle por defecto).
    logger.info("Detalles de comparación solicitados: %s", config.comparison_details)

    results: List[PageComparison] = []
    for i, xml in enumerate(omr_xmls, start=1):
        if xml is None:
            continue
        out_a = config.comparison_dir / f"ref_vs_page{i:03d}_ref.pdf"
        out_b = config.comparison_dir / f"ref_vs_page{i:03d}_page.pdf"
        num = musical_difference(ref_path, xml, out_a=out_a, out_b=out_b)
        if num is None:
            continue
        results.append(
            PageComparison(
                page_index=i,
                num_differences=num,
                visual_a=out_a if out_a.exists() else None,
                visual_b=out_b if out_b.exists() else None,
            )
        )

    logger.info("Comparación con referencia: %d páginas comparadas", len(results))
    return results
