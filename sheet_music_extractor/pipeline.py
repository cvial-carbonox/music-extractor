"""
pipeline.py — Orquestación del extractor de partituras.

Etapas: descarga → extracción de frames → filtrado de páginas únicas
(pentagrama + estabilidad) → OCR (título + acordes) → anotación → OMR →
comparación con referencia → generación del PDF.

La unidad de datos que fluye por el pipeline es ``PageResult``: cada etapa
va rellenando sus campos (``chords_found``, ``omr_musicxml``…).
"""
from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import annotator
import comparator
import downloader
import pdf_generator
from comparator import PageComparison
from config import Config
from frame_extractor import FrameExtractor, PageResult
from ocr_engine import OCREngine
from omr_engine import OMREngine

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[float, str], None]]


def _sanitize(text: str) -> str:
    """Limpia una cadena para usarla como nombre de archivo."""
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:80]


def _title_from_text(text: str) -> str:
    """Extrae un título del bloque de texto OCR de la primera página."""
    match = re.search(r"\[Título/Encabezado\]\s*(.+)", text)
    if not match:
        return ""
    first_line = match.group(1).splitlines()[0].strip()
    return _sanitize(first_line)


@dataclass
class PipelineResult:
    """Resultado de una ejecución completa del pipeline."""

    pdf_path: Path
    pages: List[PageResult] = field(default_factory=list)
    final_images: List[Path] = field(default_factory=list)
    title: str = ""
    num_pages: int = 0
    musicxml_paths: List[Path] = field(default_factory=list)
    merged_musicxml: str = ""
    merged_midi: str = ""
    note_summary: dict = field(default_factory=dict)
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

    # 2. Extracción de frames + filtrado de páginas ------------------------
    _report(progress, 0.15, "Extrayendo frames…")
    extractor = FrameExtractor(config)
    frames = extractor.extract_frames(video_path)

    _report(progress, 0.50, "Filtrando páginas únicas…")
    pages: List[PageResult] = extractor.filter_unique_pages(frames)
    if not pages:
        raise RuntimeError("No se detectó ninguna página de partitura en el vídeo.")

    # Copia cada página seleccionada a pages_dir con numeración limpia.
    for page in pages:
        dest = config.pages_dir / f"page_{page.page_number:03d}.png"
        shutil.copyfile(page.frame_path, dest)

    # 3-4. OCR (título, acordes, indicaciones, texto) + anotación ----------
    _report(progress, 0.55, "OCR de páginas…")
    ocr = OCREngine(config)
    title = ""
    final_images: List[Path] = []
    for i, page in enumerate(pages, start=1):
        _report(progress, 0.55 + 0.10 * (i / len(pages)), f"OCR página {i}/{len(pages)}…")
        page_img = config.pages_dir / f"page_{page.page_number:03d}.png"

        ocr.process_page(page)  # rellena page.chords_found y page.text_found
        if page.page_number == 1:
            title = _title_from_text(page.text_found)
        if page.chords_found:
            logger.info("Página %d: %d acordes", page.page_number, len(page.chords_found))

        if config.detect_chords and config.annotate_chords:
            out = config.annotated_dir / f"page_{page.page_number:03d}.png"
            annotator.annotate_page(page_img, page, out, config)
            final_images.append(out)
        else:
            final_images.append(page_img)

    # 5. OMR (notas → MusicXML/MIDI) + fusión -------------------------------
    musicxml_paths: List[Path] = []
    merged_musicxml = ""
    merged_midi = ""
    note_summary: dict = {}
    if config.enable_omr:
        _report(progress, 0.70, "Reconociendo notas (OMR)…")
        omr = OMREngine(config)  # puede desactivar enable_omr si falta oemer
        for i, page in enumerate(pages, start=1):
            _report(
                progress,
                0.70 + 0.12 * (i / len(pages)),
                f"OMR página {i}/{len(pages)}…",
            )
            omr.process_page(page)
            if page.omr_musicxml:
                musicxml_paths.append(Path(page.omr_musicxml))

        merged_musicxml = omr.merge_musicxml(pages)
        if merged_musicxml:
            note_summary = omr.extract_note_summary(merged_musicxml)
            midi = merged_musicxml.replace(".musicxml", ".mid")
            if Path(midi).exists():
                merged_midi = midi

    # 6. Comparación con la partitura de referencia ------------------------
    comparisons: Optional[List[PageComparison]] = None
    if config.reference_score_path:
        _report(progress, 0.87, "Comparando con partitura de referencia…")
        # Comparar la partitura fusionada (más significativa) o, en su defecto,
        # las páginas reconocidas individualmente.
        if merged_musicxml:
            omr_xmls: List[Optional[Path]] = [Path(merged_musicxml)]
        else:
            omr_xmls = [Path(p.omr_musicxml) if p.omr_musicxml else None for p in pages]
        comparisons = comparator.compare_to_reference(omr_xmls, config)

    # 7. Generación del PDF -------------------------------------------------
    _report(progress, 0.92, "Generando PDF…")
    pdf_name = f"{title}.pdf" if title else "partitura.pdf"
    pdf_path = config.base / pdf_name
    pdf_generator.images_to_pdf(final_images, pdf_path, dpi=config.pdf_dpi)

    _report(progress, 1.0, "¡Listo!")
    return PipelineResult(
        pdf_path=pdf_path,
        pages=pages,
        final_images=final_images,
        title=title,
        num_pages=len(pages),
        musicxml_paths=musicxml_paths,
        merged_musicxml=merged_musicxml,
        merged_midi=merged_midi,
        note_summary=note_summary,
        comparisons=comparisons,
    )
