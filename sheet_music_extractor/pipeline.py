"""Pipeline principal del extractor de partituras.

Orquesta todas las etapas: descarga → extracción de frames → deduplicación
→ OCR (título) → OMR + dedupe musical (opcional) → generación del PDF.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import comparator
import downloader
import frame_extractor
import ocr_engine
import omr_engine
import pdf_generator
from config import Config

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[float, str], None]]


@dataclass
class PipelineResult:
    """Resultado de una ejecución completa del pipeline."""

    pdf_path: Path
    page_paths: List[Path] = field(default_factory=list)
    title: str = ""
    num_pages: int = 0
    musicxml_paths: List[Path] = field(default_factory=list)


def _report(progress: ProgressCallback, fraction: float, message: str) -> None:
    if progress is not None:
        progress(fraction, message)
    logger.info("[%3d%%] %s", int(fraction * 100), message)


def run(
    url: str,
    config: Optional[Config] = None,
    progress: ProgressCallback = None,
) -> PipelineResult:
    """Ejecuta el pipeline completo sobre ``url`` y devuelve el resultado.

    Args:
        url: URL del vídeo con la partitura.
        config: Configuración; si es ``None`` se usan valores por defecto.
        progress: Callback opcional ``(fraccion 0-1, mensaje)``.
    """
    config = config or Config()
    config.ensure_dirs()

    # 1. Descarga -----------------------------------------------------------
    _report(progress, 0.05, "Descargando vídeo…")
    info = downloader.download_video(url, config)

    # 2. Extracción de frames ----------------------------------------------
    _report(progress, 0.15, "Extrayendo frames…")

    def _extract_progress(frac: float, msg: str) -> None:
        # Mapea el progreso de extracción al tramo 15%–55%.
        _report(progress, 0.15 + frac * 0.40, msg)

    frames = frame_extractor.extract_unique_frames(
        info.path, config, progress=_extract_progress
    )

    # 3. Deduplicación global ----------------------------------------------
    _report(progress, 0.60, "Eliminando páginas duplicadas…")
    frames = frame_extractor.deduplicate_frames(frames, config)
    if not frames:
        raise RuntimeError("No se detectó ninguna página en el vídeo.")

    page_paths = frame_extractor.save_frames(frames, config.frames_dir)

    # 4. OCR del título -----------------------------------------------------
    title = info.title
    if config.ocr_enabled and page_paths:
        _report(progress, 0.65, "Reconociendo título (OCR)…")
        guessed = ocr_engine.guess_title(page_paths[0], config)
        if guessed:
            title = guessed

    # 5. OMR + dedupe musical (opcional) -----------------------------------
    musicxml_paths: List[Path] = []
    if config.omr_enabled:
        _report(progress, 0.70, "Reconociendo música (OMR)…")
        omr_dir = config.output_dir / "musicxml"
        xmls: List[Optional[Path]] = []
        for i, page in enumerate(page_paths, start=1):
            _report(
                progress,
                0.70 + 0.15 * (i / len(page_paths)),
                f"OMR página {i}/{len(page_paths)}…",
            )
            xml = omr_engine.image_to_musicxml(page, omr_dir, config)
            xmls.append(xml)
        musicxml_paths = [x for x in xmls if x is not None]

        if config.use_omr_dedup:
            _report(progress, 0.86, "Deduplicando por contenido musical…")
            page_paths = comparator.deduplicate_by_music(page_paths, xmls)

    # 6. Generación del PDF -------------------------------------------------
    _report(progress, 0.90, "Generando PDF…")
    pdf_name = f"{ocr_engine._sanitize(title)}.pdf" if title else config.pdf_name
    pdf_path = config.output_dir / pdf_name
    pdf_generator.images_to_pdf(page_paths, pdf_path)

    # 7. Limpieza opcional --------------------------------------------------
    if not config.keep_frames:
        for page in page_paths:
            Path(page).unlink(missing_ok=True)

    _report(progress, 1.0, "¡Listo!")
    return PipelineResult(
        pdf_path=pdf_path,
        page_paths=page_paths,
        title=title,
        num_pages=len(page_paths),
        musicxml_paths=musicxml_paths,
    )
