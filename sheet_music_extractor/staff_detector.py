"""
staff_detector.py — Detección de pentagramas (staff lines) en un frame.

Un frame sólo se considera "página de partitura" si contiene suficientes
líneas horizontales largas (las cinco líneas del pentagrama). Esto descarta
portadas, transiciones y frames sin música.

El algoritmo aísla las estructuras horizontales mediante morfología
(erosión + dilatación con un kernel horizontal) y agrupa las filas
resultantes en líneas individuales.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

import cv2
import numpy as np

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class StaffInfo:
    """Resultado de la detección de pentagramas en un frame."""

    line_ys: List[int] = field(default_factory=list)  # centro Y de cada línea

    @property
    def count(self) -> int:
        return len(self.line_ys)

    def systems(self, gap_ratio: float = 1.8) -> List[List[int]]:
        """Agrupa las líneas en sistemas (pentagramas).

        Dentro de un pentagrama las cinco líneas están casi equiespaciadas;
        entre pentagramas el hueco es mucho mayor. Se corta un sistema cuando
        el hueco supera ``gap_ratio`` veces el hueco mediano.
        """
        if len(self.line_ys) < 2:
            return [list(self.line_ys)] if self.line_ys else []
        ys = sorted(self.line_ys)
        gaps = np.diff(ys)
        median_gap = float(np.median(gaps)) or 1.0
        systems: List[List[int]] = [[ys[0]]]
        for prev_gap, y in zip(gaps, ys[1:]):
            if prev_gap > gap_ratio * median_gap:
                systems.append([y])
            else:
                systems[-1].append(y)
        return systems


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def detect(image: np.ndarray, config: Config) -> StaffInfo:
    """Detecta las líneas de pentagrama presentes en ``image`` (BGR o gris)."""
    gray = _to_gray(image)
    height, width = gray.shape[:2]

    # Binarización inversa: las líneas oscuras pasan a blanco.
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, -2
    )

    # Kernel horizontal de longitud mínima => sólo sobreviven líneas largas.
    min_len = max(int(width * config.staff_line_min_width), 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_len, 1))
    horizontal = cv2.erode(binary, kernel)
    horizontal = cv2.dilate(horizontal, kernel)

    # Filas que contienen píxeles de línea.
    row_has_line = horizontal.sum(axis=1) > 0
    rows = np.where(row_has_line)[0]
    if rows.size == 0:
        return StaffInfo(line_ys=[])

    # Agrupa filas consecutivas (grosor de la línea) en una sola línea.
    line_ys: List[int] = []
    group = [int(rows[0])]
    for r in rows[1:]:
        if r - group[-1] <= 2:
            group.append(int(r))
        else:
            line_ys.append(int(np.mean(group)))
            group = [int(r)]
    line_ys.append(int(np.mean(group)))

    return StaffInfo(line_ys=line_ys)


def has_staff(image: np.ndarray, config: Config) -> bool:
    """Indica si ``image`` contiene un pentagrama (>= ``min_staff_lines``)."""
    return detect(image, config).count >= config.min_staff_lines
