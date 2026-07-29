"""Configuración central del extractor de partituras.

Reúne todas las opciones ajustables del pipeline en un único ``dataclass``
para que cada etapa (descarga, extracción, OCR, OMR, PDF) lea de la misma
fuente de verdad.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Directorio base del paquete y carpeta de salida por defecto.
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"


@dataclass
class Config:
    """Opciones de configuración del pipeline completo."""

    # ── Descarga (yt-dlp) ──
    # Se limita a 1080p para no descargar vídeos innecesariamente grandes;
    # la resolución de una partitura escaneada rara vez necesita más.
    video_format: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    download_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUT_DIR / "downloads")

    # ── Extracción de frames ──
    frame_interval_sec: float = 1.0   # cada cuántos segundos se muestrea un frame
    ssim_threshold: float = 0.92      # similitud >= umbral => se considera el mismo frame
    resize_for_compare: tuple[int, int] = (320, 180)  # tamaño reducido para comparar rápido

    # Recortes relativos (0.0–1.0) aplicados a cada frame antes de procesar.
    # Útil para eliminar barras superiores/inferiores, marcas de agua, etc.
    crop_top: float = 0.0
    crop_bottom: float = 0.0
    crop_left: float = 0.0
    crop_right: float = 0.0

    # ── OCR (pytesseract) ──
    ocr_enabled: bool = True
    ocr_lang: str = "spa+eng"

    # ── OMR (oemer) ──
    # oemer es muy costoso (modelos de deep learning); desactivado por defecto.
    omr_enabled: bool = False
    use_omr_dedup: bool = False       # usar comparación musical para eliminar duplicados

    # ── Salida ──
    output_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUT_DIR)
    frames_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUT_DIR / "frames")
    pdf_name: str = "partitura.pdf"
    keep_frames: bool = True          # conservar los PNG de cada página

    def ensure_dirs(self) -> None:
        """Crea los directorios de trabajo si no existen."""
        for directory in (self.download_dir, self.output_dir, self.frames_dir):
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def pdf_path(self) -> Path:
        return self.output_dir / self.pdf_name
