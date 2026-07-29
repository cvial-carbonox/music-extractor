# 🎼 Extractor de Partituras

Extrae partituras de vídeos (YouTube y otras fuentes soportadas por `yt-dlp`)
y las compila en un **PDF** limpio con una página por cada partitura única.

Pensado para vídeos que muestran una partitura **página a página** o con
**scroll** mientras suena la música. El sistema detecta los frames que
representan páginas distintas, elimina duplicados y ensambla el resultado.

## ¿Cómo funciona?

El pipeline consta de las siguientes etapas:

| Módulo | Responsabilidad |
| --- | --- |
| `downloader.py` | Descarga el vídeo con `yt-dlp` y obtiene sus metadatos. |
| `frame_extractor.py` | `FrameExtractor`: extrae frames, detecta pentagramas y filtra páginas únicas (SSIM). Produce `PageResult`. |
| `staff_detector.py` | Detección de líneas de pentagrama usada por el OCR para ubicar la banda de acordes. |
| `ocr_engine.py` | Reconoce el título y los símbolos de acorde con Tesseract. |
| `annotator.py` | Dibuja los acordes detectados sobre cada página. |
| `omr_engine.py` | (Opcional) Convierte cada página a MusicXML con `oemer`. |
| `comparator.py` | (Opcional) Compara la partitura reconocida con una de referencia (`musicdiff`). |
| `pdf_generator.py` | Combina las páginas en un PDF a `pdf_dpi` con `img2pdf`. |
| `pipeline.py` | Orquesta todas las etapas. |
| `app.py` | Interfaz web con Gradio (punto de entrada). |
| `config.py` | Configuración central del pipeline. |

### Flujo

```
URL ─▶ Descarga ─▶ Extracción de páginas ─▶ OCR título + acordes ─▶ Anotación
        (yt-dlp)   (estabilidad + pentagrama)                          │
                              ┌────────────────────────────────────────┘
                              ▼
        OMR (oemer) ─▶ Comparación con referencia (opcional) ─▶ PDF
```

Una página sólo se captura cuando el frame ha sido **estable** durante
`min_stable_frames` muestras consecutivas **y** contiene un **pentagrama**
(al menos `min_staff_lines` líneas). Esto descarta portadas, transiciones y
frames borrosos.

## Instalación

```bash
cd sheet_music_extractor
python -m venv .venv
source .venv/bin/activate       # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Dependencias del sistema

**Tesseract OCR** (para `pytesseract`), sólo si quieres detección de título.
Instala también los paquetes de idioma que uses (`spa`, `eng`):

```bash
# Ubuntu/Debian:
sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa

# macOS:
brew install tesseract

# Windows: https://github.com/UB-Mannheim/tesseract/wiki
```

> En Windows, si el binario no queda en el `PATH`, indícalo en tu código con
> `pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"`.

Otras dependencias del sistema:

- **FFmpeg** (recomendado por `yt-dlp` para fusionar audio y vídeo).
- `oemer` descarga sus modelos la primera vez que se ejecuta (OMR es opcional
  y computacionalmente costoso).

## Uso

### Interfaz web (recomendado)

```bash
python app.py
```

Se abrirá una interfaz Gradio. Pega la URL, ajusta las opciones si lo deseas
y pulsa **Extraer**. Obtendrás el PDF descargable y una galería con las
páginas detectadas.

### Uso programático

```python
from config import Config
import pipeline

config = Config(
    youtube_url="https://www.youtube.com/watch?v=XXXX",
    fps_sample=2.0,
    ssim_threshold=0.88,
    detect_chords=True,
    enable_omr=False,               # activa oemer si quieres MusicXML
    reference_score_path="",        # opcional: comparar con una partitura
)
result = pipeline.run(config)

print(result.num_pages, "páginas en", result.pdf_path)
```

## Ajuste de parámetros

- **`fps_sample`**: frames por segundo a analizar. Súbelo si el vídeo cambia
  de página rápido; bájalo para acelerar.
- **`ssim_threshold`** (0–1): similitud a partir de la cual dos frames se
  consideran la misma página. Súbelo si se pierden páginas parecidas; bájalo
  si aparecen duplicados.
- **`min_stable_frames`**: muestras estables consecutivas antes de capturar
  una página (evita frames de transición).
- **`min_staff_lines` / `staff_line_min_width`**: sensibilidad de la detección
  de pentagramas.
- **`detect_chords` / `annotate_chords` / `chord_region_offset`**: detección de
  acordes por OCR encima del pentagrama y su dibujo sobre la página.
- **`enable_omr` / `omr_use_tf` / `omr_without_deskew`**: reconocimiento de
  notas a MusicXML con oemer (lento).
- **`reference_score_path` / `comparison_details`**: comparación de la
  partitura reconocida con una de referencia mediante `musicdiff`.
- **`pdf_dpi`**: resolución de las páginas del PDF final.

## Notas

- Funciona mejor con vídeos de tipo *page-turn* (una página fija durante unos
  segundos). Los vídeos con scroll continuo pueden requerir ajustar
  `fps_sample` y `ssim_threshold`.
- Todas las etapas basadas en dependencias opcionales (OCR, OMR, comparación
  musical) degradan con elegancia: si la herramienta no está instalada, el
  pipeline continúa sin ella.

## Estructura del proyecto

```
sheet_music_extractor/
├── requirements.txt
├── config.py
├── downloader.py
├── frame_extractor.py
├── staff_detector.py
├── ocr_engine.py
├── annotator.py
├── omr_engine.py
├── comparator.py
├── pdf_generator.py
├── pipeline.py
├── app.py              ← Interfaz Gradio (punto de entrada)
└── README.md
```
