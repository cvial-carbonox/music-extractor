"""
config.py — Configuración central del proyecto.
"""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # ── Entrada ──
    youtube_url: str = "https://www.youtube.com/watch?v=wIdVXJlTfQk"
    output_dir: str = "output"

    # ── Extracción de frames ──
    fps_sample: float = 2.0           # Frames por segundo a muestrear
    ssim_threshold: float = 0.88      # Umbral SSIM: misma página si > threshold
    min_stable_frames: int = 3        # Frames estables antes de capturar página

    # ── Detección de pentagrama ──
    min_staff_lines: int = 5          # Líneas mínimas para detectar pentagrama
    staff_line_min_width: float = 0.25  # Ancho mínimo (% del frame) para línea

    # ── OCR ──
    ocr_languages: str = "eng+spa"
    detect_chords: bool = True
    chord_region_offset: int = 50     # px encima del pentagrama para buscar acordes

    # ── OMR ──
    enable_omr: bool = True           # Activar reconocimiento de notas
    omr_use_tf: bool = False          # Usar TensorFlow (True) u ONNX (False)
    omr_without_deskew: bool = True   # Desactivar deskew (imágenes de video son rectas)

    # ── Comparación ──
    reference_score_path: str = ""    # Ruta a partitura de referencia (MusicXML/MIDI/krn)
    comparison_details: list = field(default_factory=lambda: [
        "notesandrests", "beams", "ties", "slurs",
        "signatures", "directions", "chordsymbols"
    ])

    # ── PDF ──
    pdf_dpi: int = 300
    annotate_chords: bool = True      # Dibujar acordes OCR sobre la imagen

    # ── Rutas derivadas ──
    @property
    def base(self) -> Path:
        return Path(self.output_dir)

    @property
    def frames_dir(self) -> Path:
        return self.base / "frames"

    @property
    def pages_dir(self) -> Path:
        return self.base / "pages"

    @property
    def annotated_dir(self) -> Path:
        return self.base / "annotated"

    @property
    def omr_dir(self) -> Path:
        return self.base / "omr"

    @property
    def comparison_dir(self) -> Path:
        return self.base / "comparison"

    def ensure_dirs(self):
        for d in [self.frames_dir, self.pages_dir, self.annotated_dir,
                  self.omr_dir, self.comparison_dir]:
            d.mkdir(parents=True, exist_ok=True)
