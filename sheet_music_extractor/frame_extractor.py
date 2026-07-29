"""
frame_extractor.py — Extracción de páginas de partitura desde el vídeo.

Estrategia para vídeos tipo "pasa-páginas":

1. Se muestrea a ``fps_sample`` fotogramas por segundo.
2. Un frame se considera *estable* cuando se parece (SSIM) al frame muestreado
   anterior. Tras ``min_stable_frames`` muestras estables consecutivas, el
   frame es candidato a página (evita capturar transiciones borrosas).
3. El candidato se acepta como página nueva sólo si contiene un pentagrama
   (``staff_detector``) y difiere de la última página capturada.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

import staff_detector
from config import Config

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[float, str], None]]

# Tamaño reducido usado para las comparaciones SSIM (rápido y estable).
COMPARE_SIZE = (320, 180)


@dataclass
class Page:
    """Una página de partitura capturada del vídeo."""

    index: int          # índice del frame en el vídeo original
    timestamp: float    # segundos desde el inicio
    image: np.ndarray   # imagen BGR

    @property
    def gray(self) -> np.ndarray:
        return cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)


def _prepare(image: np.ndarray) -> np.ndarray:
    """Convierte a gris reducido para comparar con SSIM."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return cv2.resize(gray, COMPARE_SIZE, interpolation=cv2.INTER_AREA)


def _similar(a: np.ndarray, b: np.ndarray, threshold: float) -> bool:
    return float(ssim(a, b)) > threshold


def extract_pages(
    video_path: Path,
    config: Config,
    progress: ProgressCallback = None,
) -> List[Page]:
    """Extrae las páginas de partitura distintas de ``video_path``."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir el vídeo: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(int(round(fps / max(config.fps_sample, 0.01))), 1)

    config.frames_dir.mkdir(parents=True, exist_ok=True)

    pages: List[Page] = []
    prev_small: Optional[np.ndarray] = None       # muestra anterior
    candidate: Optional[Page] = None              # frame estable en observación
    last_page_small: Optional[np.ndarray] = None  # última página aceptada
    stable_count = 0
    idx = 0
    sample_n = 0

    try:
        while True:
            if not cap.grab():
                break
            if idx % step == 0:
                ok, frame = cap.retrieve()
                if ok and frame is not None:
                    small = _prepare(frame)

                    if prev_small is not None and _similar(prev_small, small, config.ssim_threshold):
                        stable_count += 1
                    else:
                        stable_count = 1
                        candidate = Page(index=idx, timestamp=idx / fps, image=frame)
                    prev_small = small

                    # Guarda cada frame muestreado (útil para depurar).
                    cv2.imwrite(str(config.frames_dir / f"frame_{sample_n:05d}.png"), frame)
                    sample_n += 1

                    # ¿Frame estable el tiempo suficiente y con pentagrama?
                    if (
                        candidate is not None
                        and stable_count == config.min_stable_frames
                        and staff_detector.has_staff(candidate.image, config)
                    ):
                        is_new = last_page_small is None or not _similar(
                            last_page_small, small, config.ssim_threshold
                        )
                        if is_new:
                            pages.append(candidate)
                            last_page_small = small
                            logger.info(
                                "Página %d capturada en t=%.1fs", len(pages), candidate.timestamp
                            )

                if progress and total:
                    progress(min(idx / total, 1.0), f"Extrayendo frames… ({len(pages)} páginas)")
            idx += 1
    finally:
        cap.release()

    logger.info("Total de páginas capturadas: %d", len(pages))
    return pages


def save_pages(pages: List[Page], out_dir: Path) -> List[Path]:
    """Guarda cada página como PNG numerado y devuelve las rutas."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for i, page in enumerate(pages, start=1):
        path = out_dir / f"page_{i:03d}.png"
        cv2.imwrite(str(path), page.image)
        paths.append(path)
    return paths
