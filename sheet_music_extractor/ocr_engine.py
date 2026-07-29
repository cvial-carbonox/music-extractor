"""
ocr_engine.py — OCR con Tesseract para extraer acordes, título,
indicaciones de tempo/dinámica y texto general.
"""
import re
from dataclasses import dataclass
import cv2
import numpy as np
import pytesseract
from PIL import Image
from config import Config
from frame_extractor import PageResult


@dataclass
class ChordHit:
    """Un acorde detectado con su posición (en px, resolución completa)."""
    text: str
    x: int
    y: int


# Patrón regex para acordes: Am, G7, Cmaj7, Dm7, Bb, F#dim, Eb/G, etc.
CHORD_PATTERN = re.compile(
    r'\b([A-G][#b]?'                        # Nota fundamental
    r'(?:maj|min|m|dim|aug|sus[24]?)?'      # Cualidad
    r'(?:[0-9]{1,2})?'                      # Extensión (7, 9, 11, 13)
    r'(?:add[0-9]+)?'                       # add9, add11
    r'(?:/[A-G][#b]?)?'                     # Bajo (slash chord)
    r')\b'
)

# Indicaciones musicales comunes
MUSICAL_TERMS = re.compile(
    r'\b(p|pp|ppp|f|ff|fff|mf|mp|sfz|fp|'
    r'cresc|dim|rit|accel|rall|a tempo|'
    r'allegro|adagio|andante|moderato|largo|presto|vivace|'
    r'da capo|dal segno|coda|fine|'
    r'legato|staccato|pizz|arco|'
    r'dolce|espressivo|cantabile|grazioso)\b',
    re.IGNORECASE
)


class OCREngine:

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def process_page(self, page: PageResult) -> PageResult:
        """Ejecuta OCR completo sobre una página."""
        img = cv2.imread(page.frame_path)
        if img is None:
            return page

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # ── 1. Título / compositor (zona superior) ──
        top_region = gray[0:int(h * 0.12), :]
        top_text = self._ocr_clean(top_region, psm=6)

        # ── 2. Acordes (encima de cada pentagrama), con posición ──
        chord_hits = []
        if self.cfg.detect_chords:
            chord_hits = self._extract_chords(gray, page.staff_regions, h, w)

        # ── 3. Indicaciones musicales (tempo, dinámica) ──
        indications = self._extract_indications(gray)

        # ── 4. Texto completo ──
        full_text = self._ocr_clean(gray, psm=4)

        # ── Resultados ──
        page.chord_boxes = chord_hits  # posiciones para anotar sobre el pentagrama
        page.chords_found = list(dict.fromkeys(hit.text for hit in chord_hits))
        page.text_found = "\n".join(filter(None, [
            f"[Título/Encabezado] {top_text}" if top_text else "",
            f"[Acordes] {' | '.join(page.chords_found)}" if page.chords_found else "",
            f"[Indicaciones] {', '.join(indications)}" if indications else "",
            f"[Texto completo]\n{full_text}" if full_text else "",
        ]))

        return page

    def _extract_chords(self, gray: np.ndarray, regions: list,
                        img_h: int, img_w: int) -> list:
        """Extrae acordes (con posición) de la zona encima de cada pentagrama.

        Retorna una lista de :class:`ChordHit` con coordenadas en la resolución
        completa de la imagen, para poder anotar cada acorde sobre su compás.
        """
        hits = []
        scale = 2.5  # factor de ampliación del recorte antes del OCR

        for (rx, ry, rw, rh) in regions:
            # Escalar regiones (fueron detectadas en imagen escalada a 1000px)
            sx = img_w / 1000.0
            sy = img_h / 1000.0

            # Zona de acordes: encima del pentagrama
            y_start = max(0, int(ry * sy) - self.cfg.chord_region_offset)
            y_end = int(ry * sy) + 5
            x_start = max(0, int(rx * sx))
            x_end = min(img_w, int((rx + rw) * sx))

            if y_end <= y_start or x_end <= x_start:
                continue

            chord_region = gray[y_start:y_end, x_start:x_end]
            if chord_region.size == 0:
                continue

            # Preprocesar: ampliar + binarizar
            chord_region = cv2.resize(chord_region, None, fx=scale, fy=scale,
                                      interpolation=cv2.INTER_CUBIC)
            _, chord_bin = cv2.threshold(chord_region, 0, 255,
                                         cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # image_to_data devuelve la caja de cada palabra → conservamos posición.
            data = pytesseract.image_to_data(
                chord_bin,
                lang='eng',
                config='--psm 11 -c tessedit_char_whitelist='
                       'ABCDEFGabcdefgmajdinus0123456789#b/ ',
                output_type=pytesseract.Output.DICT,
            )

            for token, left, top in zip(data['text'], data['left'], data['top']):
                for chord in self._parse_chords(token or ""):
                    abs_x = int(x_start + left / scale)
                    abs_y = int(y_start + top / scale)
                    hits.append(ChordHit(text=chord, x=abs_x, y=abs_y))

        return hits

    def _extract_indications(self, gray: np.ndarray) -> list:
        """Busca términos musicales italianos y dinámicas."""
        text = pytesseract.image_to_string(gray, lang='eng+ita', config='--psm 4')
        matches = MUSICAL_TERMS.findall(text)
        return list(dict.fromkeys([m.strip() for m in matches]))

    def _parse_chords(self, text: str) -> list:
        """Parsea acordes válidos del texto OCR."""
        matches = CHORD_PATTERN.findall(text)
        valid = []
        for m in matches:
            m = m.strip()
            if len(m) >= 2 and m[0] in 'ABCDEFG':
                # Filtrar falsos positivos comunes
                if m.lower() not in ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'add'):
                    valid.append(m)
        return valid

    def _ocr_clean(self, img: np.ndarray, psm: int = 6) -> str:
        """OCR con preprocesamiento."""
        # Escalar para mejor reconocimiento
        scaled = cv2.resize(img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        _, binary = cv2.threshold(scaled, 0, 255,
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text = pytesseract.image_to_string(
            binary, lang=self.cfg.ocr_languages, config=f'--psm {psm}'
        )
        return text.strip()
