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
| `frame_extractor.py` | Muestrea frames y deduplica usando SSIM (scikit-image). |
| `ocr_engine.py` | Reconoce el título con Tesseract para nombrar el PDF. |
| `omr_engine.py` | (Opcional) Convierte cada página a MusicXML con `oemer`. |
| `comparator.py` | (Opcional) Elimina duplicados comparando la música con `musicdiff`. |
| `pdf_generator.py` | Combina las páginas en un PDF con `img2pdf`. |
| `pipeline.py` | Orquesta todas las etapas. |
| `app.py` | Interfaz web con Gradio (punto de entrada). |
| `config.py` | Configuración central del pipeline. |

### Flujo

```
URL ─▶ Descarga ─▶ Extracción de frames ─▶ Deduplicación ─▶ OCR (título)
                                                              │
                              ┌───────────────────────────────┘
                              ▼
                 OMR + dedupe musical (opcional) ─▶ PDF
```

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

config = Config(frame_interval_sec=1.0, ssim_threshold=0.92)
result = pipeline.run("https://www.youtube.com/watch?v=XXXX", config)

print(result.num_pages, "páginas en", result.pdf_path)
```

## Ajuste de parámetros

- **`frame_interval_sec`**: cada cuántos segundos se analiza un frame. Bájalo
  si el vídeo cambia de página rápido; súbelo para acelerar el proceso.
- **`ssim_threshold`** (0–1): similitud a partir de la cual dos frames se
  consideran la misma página. Súbelo si se pierden páginas parecidas; bájalo
  si aparecen duplicados.
- **`crop_*`**: recortes relativos para quitar barras, marcas de agua o
  interfaces del reproductor antes de comparar.
- **`omr_enabled` / `use_omr_dedup`**: activa OMR para deduplicar por
  contenido musical además de por apariencia visual (lento).

## Notas

- Funciona mejor con vídeos de tipo *page-turn* (una página fija durante unos
  segundos). Los vídeos con scroll continuo pueden requerir ajustar el
  intervalo y el umbral.
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
├── ocr_engine.py
├── omr_engine.py
├── comparator.py
├── pdf_generator.py
├── pipeline.py
├── app.py              ← Interfaz Gradio (punto de entrada)
└── README.md
```
