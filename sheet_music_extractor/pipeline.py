"""
pipeline.py — Orquestación del extractor de partituras.

Etapas: descarga → extracción de páginas (con detección de pentagrama) →
OCR (título + acordes) → anotación de acordes → OMR → comparación con
referencia → generación del PDF.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import annotator
import comparator
import downloader
import frame_extractor
import ocr_engine
import omr_engine
import pdf_generator
from comparator import PageComparison
from config import Config

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[float, str], None]]


@dataclass
class PipelineResult:
    """Resultado de una ejecución completa del pipeline."""

    pdf_path: Path
    page_paths: List[Path] = field(default_factory=list)
    final_images: List[Path] = field(default_factory=list)
    title: str = ""
    num_pages: int = 0
    musicxml_paths: List[Path] = field(default_factory=list)
    comparisons: Optional[List[PageComparison]] = None


def _report(progress: ProgressCallback, fraction: float, message: str) -> None:
    if progress is not None:
        progress(fraction, message)
    logger.info("[%3d%%] %s", int(fraction * 100), message)


def run(
    config: Optional[Config] = None,
    url: Optional[str] = None,
    progress: ProgressCallback = None,
) -> PipelineResult:
    """Ejecuta el pipeline completo y devuelve el resultado.

    Args:
        config: Configuración; si es ``None`` se usan valores por defecto.
        url: URL a procesar; si es ``None`` se usa ``config.youtube_url``.
        progress: Callback opcional ``(fraccion 0-1, mensaje)``.
    """
    config = config or Config()
    if url:
        config.youtube_url = url
    config.ensure_dirs()

    # 1. Descarga -----------------------------------------------------------
    _report(progress, 0.05, "Descargando vídeo…")
    video_path = downloader.download_video(config)

    # 2. Extracción de páginas ---------------------------------------------
    _report(progress, 0.15, "Extrayendo páginas…")

    def _extract_progress(frac: float, msg: str) -> None:
        _report(progress, 0.15 + frac * 0.40, msg)  # tramo 15%–55%

    pages = frame_extractor.extract_pages(video_path, config, progress=_extract_progress)
    if not pages:
        raise RuntimeError("No se detectó ninguna página de partitura en el vídeo.")
    page_paths = frame_extractor.save_pages(pages, config.pages_dir)

    # 3. OCR del título -----------------------------------------------------
    title = ocr_engine.guess_title(page_paths[0], config)

    # 4. Detección y anotación de acordes ----------------------------------
    final_images: List[Path] = list(page_paths)
    if config.detect_chords:
        _report(progress, 0.60, "Detectando acordes (OCR)…")
        annotated: List[Path] = []
        for i, (page_path, page) in enumerate(zip(page_paths, pages), start=1):
            chords = ocr_engine.detect_chords(page.image, config)
            if config.annotate_chords:
                out = config.annotated_dir / f"page_{i:03d}.png"
                annotator.annotate_page(page_path, chords, out, config)
                annotated.append(out)
            if chords:
                logger.info("Página %d: %d acordes detectados", i, len(chords))
        if config.annotate_chords and annotated:
            final_images = annotated

    # 5. OMR ----------------------------------------------------------------
    musicxml_paths: List[Path] = []
    omr_xmls: List[Optional[Path]] = []
    if config.enable_omr:
        _report(progress, 0.70, "Reconociendo notas (OMR)…")
        for i, page_path in enumerate(page_paths, start=1):
            _report(
                progress,
                0.70 + 0.15 * (i / len(page_paths)),
                f"OMR página {i}/{len(page_paths)}…",
            )
            xml = omr_engine.image_to_musicxml(page_path, config.omr_dir, config)
            omr_xmls.append(xml)
            if xml is not None:
                musicxml_paths.append(xml)

    # 6. Comparación con referencia ----------------------------------------
    comparisons: Optional[List[PageComparison]] = None
    if config.reference_score_path and omr_xmls:
        _report(progress, 0.87, "Comparando con partitura de referencia…")
        comparisons = comparator.compare_to_reference(omr_xmls, config)

    # 7. Generación del PDF -------------------------------------------------
    _report(progress, 0.92, "Generando PDF…")
    pdf_name = f"{ocr_engine._sanitize(title)}.pdf" if title else "partitura.pdf"
    pdf_path = config.base / pdf_name
    pdf_generator.images_to_pdf(final_images, pdf_path, dpi=config.pdf_dpi)

    _report(progress, 1.0, "¡Listo!")
    return PipelineResult(
        pdf_path=pdf_path,
        page_paths=page_paths,
        final_images=final_images,
        title=title,
        num_pages=len(page_paths),
        musicxml_paths=musicxml_paths,
        comparisons=comparisons,
    )
