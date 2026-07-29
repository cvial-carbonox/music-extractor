"""
frame_extractor.py — Extracción de frames, detección de pentagrama
y filtrado de páginas únicas (estáticas).
"""
import cv2
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from skimage.metrics import structural_similarity as ssim
from tqdm import tqdm
from config import Config


@dataclass
class PageResult:
    """Una página de partitura detectada."""
    frame_path: str
    page_number: int
    timestamp_sec: float
    staff_regions: list = field(default_factory=list)
    chords_found: list = field(default_factory=list)
    chord_boxes: list = field(default_factory=list)  # ChordHit(text, x, y) para anotar por posición
    text_found: str = ""
    omr_musicxml: str = ""
    omr_midi: str = ""


class FrameExtractor:

    def __init__(self, cfg: Config):
        self.cfg = cfg

    # ─────────────────────────────────────────────
    # EXTRAER FRAMES DEL VIDEO
    # ─────────────────────────────────────────────
    def extract_frames(self, video_path: str) -> list:
        """Extrae frames a la tasa configurada. Retorna [(path, timestamp), ...]."""
        cap = cv2.VideoCapture(video_path)
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps
        interval = max(1, int(video_fps / self.cfg.fps_sample))

        print(f"🎬 Video: {duration:.1f}s | {video_fps:.1f} FPS | {total_frames} frames")
        print(f"📸 Muestreo: 1 cada {interval} frames → ~{duration * self.cfg.fps_sample:.0f} capturas")

        frames = []
        count = 0
        saved = 0

        pbar = tqdm(total=total_frames, desc="Extrayendo", unit="frame")
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if count % interval == 0:
                timestamp = count / video_fps
                path = str(self.cfg.frames_dir / f"f_{saved:05d}.png")
                cv2.imwrite(path, frame)
                frames.append((path, timestamp))
                saved += 1

            count += 1
            pbar.update(1)

        pbar.close()
        cap.release()
        print(f"✅ {saved} frames extraídos\n")
        return frames

    # ─────────────────────────────────────────────
    # DETECTAR PENTAGRAMA (5 líneas)
    # ─────────────────────────────────────────────
    def detect_staff(self, gray: np.ndarray) -> list:
        """
        Detecta regiones de pentagrama buscando 5 líneas horizontales
        paralelas y equidistantes.
        Retorna [(x, y, w, h), ...] en coordenadas de la imagen escalada.
        """
        h, w = gray.shape

        # Binarización adaptativa (mejor que Otsu para partituras)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 15, 10
        )

        # Kernel horizontal: detecta líneas largas
        kernel_len = max(int(w * self.cfg.staff_line_min_width), 30)
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_len, 1))
        lines_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel, iterations=1)

        # Limpiar ruido vertical
        lines_mask = cv2.dilate(lines_mask, np.ones((2, 1), np.uint8), iterations=1)

        # Contornos de líneas
        contours, _ = cv2.findContours(lines_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filtrar: líneas largas y delgadas
        min_width = int(w * self.cfg.staff_line_min_width)
        staff_lines = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw >= min_width and ch < 8 and (cw / max(ch, 1)) > 10:
                staff_lines.append((x, y, cw, ch))

        if len(staff_lines) < self.cfg.min_staff_lines:
            return []

        # Agrupar líneas cercanas verticalmente → pentagramas
        staff_lines.sort(key=lambda r: r[1])
        groups = []
        current_group = [staff_lines[0]]

        for i in range(1, len(staff_lines)):
            gap = staff_lines[i][1] - current_group[-1][1]
            if gap < 45:  # Líneas del mismo pentagrama
                current_group.append(staff_lines[i])
            else:
                if len(current_group) >= 4:
                    groups.append(current_group)
                current_group = [staff_lines[i]]

        if len(current_group) >= 4:
            groups.append(current_group)

        # Bounding boxes de cada pentagrama
        regions = []
        for group in groups:
            xs = [r[0] for r in group]
            ys = [r[1] for r in group]
            ws = [r[2] for r in group]
            x = min(xs)
            y = min(ys) - 20
            w_max = max(ws)
            h_total = (max(ys) - min(ys)) + 40
            regions.append((x, y, w_max, h_total))

        return regions

    def has_sheet_music(self, frame_path: str) -> tuple:
        """Retorna (tiene_partitura, regiones) para un frame."""
        img = cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return False, []

        h, w = img.shape
        scale = 1000 / max(h, w)
        if scale < 1:
            img = cv2.resize(img, (int(w * scale), int(h * scale)))

        regions = self.detect_staff(img)
        return len(regions) > 0, regions

    # ─────────────────────────────────────────────
    # FILTRAR PÁGINAS ÚNICAS (sin scroll)
    # ─────────────────────────────────────────────
    def filter_unique_pages(self, frames: list) -> list:
        """
        Para páginas estáticas:
        - Detecta aparición de pentagrama
        - Espera N frames estables (misma imagen)
        - Captura la página cuando cambia a otra
        """
        print("🔍 Filtrando páginas únicas (modo estático)...")

        pages: list[PageResult] = []
        prev_gray = None
        stable_count = 0
        candidate = None
        page_num = 0

        for path, timestamp in tqdm(frames, desc="Analizando", unit="frame"):
            has_music, regions = self.has_sheet_music(path)

            if not has_music:
                # Sin partitura → si teníamos candidata estable, guardarla
                if stable_count >= self.cfg.min_stable_frames and candidate:
                    page_num += 1
                    pages.append(PageResult(
                        frame_path=candidate[0],
                        page_number=page_num,
                        timestamp_sec=candidate[1],
                        staff_regions=candidate[2],
                    ))
                stable_count = 0
                candidate = None
                prev_gray = None
                continue

            gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            gray_small = cv2.resize(gray, (640, 480))

            if prev_gray is None:
                prev_gray = gray_small
                candidate = (path, timestamp, regions)
                stable_count = 1
                continue

            score = ssim(prev_gray, gray_small)

            if score > self.cfg.ssim_threshold:
                # Misma página → acumular estabilidad
                stable_count += 1
                candidate = (path, timestamp, regions)  # Actualizar al más reciente
            else:
                # Nueva página → guardar anterior si era estable
                if stable_count >= self.cfg.min_stable_frames and candidate:
                    page_num += 1
                    pages.append(PageResult(
                        frame_path=candidate[0],
                        page_number=page_num,
                        timestamp_sec=candidate[1],
                        staff_regions=candidate[2],
                    ))

                stable_count = 1
                candidate = (path, timestamp, regions)

            prev_gray = gray_small

        # Última página
        if stable_count >= self.cfg.min_stable_frames and candidate:
            page_num += 1
            pages.append(PageResult(
                frame_path=candidate[0],
                page_number=page_num,
                timestamp_sec=candidate[1],
                staff_regions=candidate[2],
            ))

        print(f"✅ {len(pages)} páginas únicas detectadas")
        for p in pages:
            print(f"   📄 Página {p.page_number} @ {p.timestamp_sec:.1f}s")
        print()

        return pages
