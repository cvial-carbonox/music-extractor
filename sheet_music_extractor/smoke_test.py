#!/usr/bin/env python3
"""
smoke_test.py — Prueba de humo end-to-end sin red ni binarios del sistema.

Genera un vídeo sintético con páginas de "partitura" (pentagramas dibujados),
ejecuta la extracción de frames + detección de pentagrama + deduplicación y
la generación del PDF, y verifica que el resultado sea un PDF válido.

NO requiere: yt-dlp, Tesseract, FFmpeg, oemer, music21, musicdiff ni Gradio.
Requiere:    numpy, opencv, scikit-image, Pillow, img2pdf, tqdm.

Uso:  python smoke_test.py
"""
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

from config import Config
from frame_extractor import FrameExtractor
from pdf_generator import PDFGenerator

W, H, FPS = 1280, 720, 10


def _staff_page(n_systems: int, label: str) -> np.ndarray:
    """Crea una imagen tipo partitura: ``n_systems`` pentagramas (5 líneas)."""
    img = np.full((H, W, 3), 255, np.uint8)
    cv2.putText(img, label, (60, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
    for s in range(n_systems):
        y0 = 150 + s * 220
        for k in range(5):  # 5 líneas horizontales = un pentagrama
            y = y0 + k * 14
            cv2.line(img, (80, y), (W - 80, y), (0, 0, 0), 2)
    return img


def _make_video(path: Path) -> None:
    """Escribe un vídeo AVI (MJPG) con dos páginas separadas por una en blanco."""
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
    if not vw.isOpened():
        raise RuntimeError("cv2.VideoWriter no pudo abrir el archivo de salida")
    blank = np.full((H, W, 3), 255, np.uint8)
    pages = [_staff_page(2, "Pagina 1"), _staff_page(3, "Pagina 2")]

    def hold(frame, secs):
        for _ in range(int(FPS * secs)):
            vw.write(frame)

    hold(pages[0], 2)
    hold(blank, 1)   # transición sin pentagrama → fuerza la separación de páginas
    hold(pages[1], 2)
    vw.release()


def main() -> int:
    workdir = Path(tempfile.mkdtemp(prefix="sme_smoke_"))
    video = workdir / "synthetic.avi"
    _make_video(video)

    cfg = Config(
        output_dir=str(workdir / "out"),
        fps_sample=2.0,
        ssim_threshold=0.88,
        detect_chords=False,   # sin Tesseract
        annotate_chords=False,
        enable_omr=False,      # sin oemer
    )
    cfg.ensure_dirs()

    extractor = FrameExtractor(cfg)
    frames = extractor.extract_frames(str(video))
    pages = extractor.filter_unique_pages(frames)

    assert frames, "No se extrajo ningún frame del vídeo"
    assert pages, "No se detectó ninguna página de partitura"

    pdfgen = PDFGenerator(cfg)
    annotated = [pdfgen.enhance_and_annotate(p) for p in pages]
    pdf_path = Path(pdfgen.generate_pdf(pages, annotated))

    assert pdf_path.exists(), "No se generó el PDF"
    assert pdf_path.read_bytes()[:5] == b"%PDF-", "El archivo generado no es un PDF válido"

    print(f"\n✅ SMOKE TEST OK — {len(pages)} página(s) detectada(s); PDF válido: {pdf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
