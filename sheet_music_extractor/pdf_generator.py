"""
pdf_generator.py — Mejora imágenes, anota acordes OCR y genera PDF final.
"""
import cv2
import numpy as np
import img2pdf
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
from pathlib import Path
from config import Config
from frame_extractor import PageResult


class PDFGenerator:

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def enhance_and_annotate(self, page: PageResult) -> str:
        """Mejora la imagen y superpone información OCR."""
        img = Image.open(page.frame_path).convert("RGB")
        w, h = img.size

        # ── Auto-recorte de bordes negros ──
        gray_np = np.array(img.convert("L"))
        _, thresh = cv2.threshold(gray_np, 25, 255, cv2.THRESH_BINARY)
        coords = cv2.findNonZero(thresh)
        if coords is not None:
            x, y, cw, ch = cv2.boundingRect(coords)
            margin = 15
            x = max(0, x - margin)
            y = max(0, y - margin)
            cw = min(w - x, cw + 2 * margin)
            ch = min(h - y, ch + 2 * margin)
            img = img.crop((x, y, x + cw, y + ch))

        # ── Mejoras de imagen ──
        img = ImageEnhance.Contrast(img).enhance(1.4)
        img = ImageEnhance.Sharpness(img).enhance(1.5)
        img = ImageEnhance.Brightness(img).enhance(1.05)

        # ── Anotar acordes y metadata ──
        if self.cfg.annotate_chords and (page.chords_found or page.text_found):
            img = self._draw_annotations(img, page)

        # ── Guardar ──
        out_path = str(self.cfg.annotated_dir / f"page_{page.page_number:03d}.png")
        img.save(out_path, "PNG", dpi=(self.cfg.pdf_dpi, self.cfg.pdf_dpi))
        return out_path

    def _draw_annotations(self, img: Image.Image, page: PageResult) -> Image.Image:
        """Dibuja un panel con acordes e info OCR sobre la imagen."""
        draw = ImageDraw.Draw(img)
        w, h = img.size

        # Fuente
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16
            )
            font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12
            )
        except (OSError, IOError):
            font = ImageFont.load_default()
            font_small = font

        y_cursor = 8

        # ── Panel de acordes ──
        if page.chords_found:
            chord_text = "🎸 " + " | ".join(page.chords_found)
            bbox = draw.textbbox((0, 0), chord_text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

            # Fondo
            draw.rectangle([4, y_cursor - 2, tw + 16, y_cursor + th + 6],
                           fill=(255, 255, 220, 230))
            draw.text((10, y_cursor), chord_text, fill=(30, 30, 30), font=font)
            y_cursor += th + 14

        # ── Número de página + timestamp ──
        meta_text = f"Pág {page.page_number} | t={page.timestamp_sec:.1f}s"
        draw.text((10, h - 25), meta_text, fill=(120, 120, 120), font=font_small)

        return img

    def generate_pdf(self, pages: list, annotated_paths: list) -> str:
        """Genera el PDF final."""
        pdf_path = str(self.cfg.base / "partitura.pdf")

        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(annotated_paths))

        print(f"\n📄 PDF generado: {pdf_path} ({len(annotated_paths)} páginas)")
        return pdf_path

    def save_ocr_report(self, pages: list) -> str:
        """Guarda reporte textual completo del OCR."""
        report_path = str(self.cfg.base / "ocr_report.txt")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("═" * 60 + "\n")
            f.write("  REPORTE OCR — PARTITURA EXTRAÍDA\n")
            f.write(f"  Fuente: {self.cfg.youtube_url}\n")
            f.write("═" * 60 + "\n\n")

            for page in pages:
                f.write(f"{'─' * 50}\n")
                f.write(f"  PÁGINA {page.page_number}  (t = {page.timestamp_sec:.1f}s)\n")
                f.write(f"{'─' * 50}\n")

                if page.chords_found:
                    f.write(f"  Acordes: {' | '.join(page.chords_found)}\n")

                if page.omr_musicxml:
                    f.write(f"  MusicXML: {page.omr_musicxml}\n")

                if page.text_found:
                    f.write(f"\n{page.text_found}\n")

                f.write("\n")

        print(f"📝 Reporte OCR: {report_path}")
        return report_path
