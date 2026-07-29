"""Extracción y deduplicación de frames de vídeo.

La estrategia es sencilla y robusta para vídeos tipo "pasa-páginas" o
"scroll" de partituras:

1. Se muestrea un frame cada ``frame_interval_sec`` segundos.
2. Cada frame se recorta (según la config), se pasa a gris y se reduce.
3. Se compara con el último frame *aceptado* usando SSIM. Si la similitud
   cae por debajo del umbral, se considera una página nueva.
4. Una segunda pasada global elimina páginas que reaparecen más tarde
   (p. ej. una repetición del estribillo mostrada dos veces).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

from config import Config

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[float, str], None]]


@dataclass
class Frame:
    """Un frame extraído del vídeo."""

    index: int          # índice del frame en el vídeo original
    timestamp: float    # segundos desde el inicio
    image: np.ndarray   # imagen BGR ya recortada

    @property
    def gray(self) -> np.ndarray:
        return cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)


def _crop(image: np.ndarray, config: Config) -> np.ndarray:
    """Aplica los recortes relativos definidos en la configuración."""
    h, w = image.shape[:2]
    top = int(round(h * config.crop_top))
    bottom = int(round(h * (1.0 - config.crop_bottom)))
    left = int(round(w * config.crop_left))
    right = int(round(w * (1.0 - config.crop_right)))
    # Salvaguarda: evita recortes degenerados.
    if bottom <= top or right <= left:
        return image
    return image[top:bottom, left:right]


def _prepare(gray: np.ndarray, config: Config) -> np.ndarray:
    """Reduce una imagen en gris al tamaño de comparación."""
    return cv2.resize(gray, config.resize_for_compare, interpolation=cv2.INTER_AREA)


def _similarity(a: np.ndarray, b: np.ndarray) -> float:
    """SSIM entre dos imágenes en gris ya normalizadas al mismo tamaño."""
    score = ssim(a, b)
    return float(score)


def extract_unique_frames(
    video_path: Path,
    config: Config,
    progress: ProgressCallback = None,
) -> List[Frame]:
    """Extrae los frames distintos de ``video_path``.

    Devuelve la lista de frames candidatos (una por página detectada),
    ya deduplicados frente al frame inmediatamente anterior.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir el vídeo: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(int(round(fps * config.frame_interval_sec)), 1)

    unique: List[Frame] = []
    last_small: Optional[np.ndarray] = None
    idx = 0

    try:
        while True:
            grabbed = cap.grab()
            if not grabbed:
                break
            if idx % step == 0:
                ok, raw = cap.retrieve()
                if ok and raw is not None:
                    cropped = _crop(raw, config)
                    small = _prepare(cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY), config)
                    if last_small is None or _similarity(last_small, small) < config.ssim_threshold:
                        unique.append(
                            Frame(index=idx, timestamp=idx / fps, image=cropped)
                        )
                        last_small = small
                if progress and total:
                    progress(min(idx / total, 1.0), f"Extrayendo frames… ({len(unique)} páginas)")
            idx += 1
    finally:
        cap.release()

    logger.info("Frames muestreados: %d páginas candidatas", len(unique))
    return unique


def deduplicate_frames(frames: List[Frame], config: Config) -> List[Frame]:
    """Elimina frames que se parezcan a *cualquier* frame ya conservado.

    Complementa a :func:`extract_unique_frames`, que sólo compara con el
    frame anterior, capturando duplicados no consecutivos.
    """
    kept: List[Frame] = []
    kept_small: List[np.ndarray] = []
    for frame in frames:
        small = _prepare(frame.gray, config)
        if all(_similarity(small, ref) < config.ssim_threshold for ref in kept_small):
            kept.append(frame)
            kept_small.append(small)
    logger.info("Tras deduplicación global: %d páginas únicas", len(kept))
    return kept


def save_frames(frames: List[Frame], out_dir: Path) -> List[Path]:
    """Guarda cada frame como PNG numerado y devuelve las rutas."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for i, frame in enumerate(frames, start=1):
        path = out_dir / f"page_{i:03d}.png"
        cv2.imwrite(str(path), frame.image)
        paths.append(path)
    return paths
