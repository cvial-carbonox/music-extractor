#!/bin/bash
# SessionStart hook — instala el núcleo testeable del pipeline en sesiones
# de Claude Code on the web, para poder ejecutar smoke_test.py y la lógica
# CV/PDF sin instalar nada a mano.
set -euo pipefail

# Sólo en el entorno remoto (Claude Code on the web).
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Núcleo sin binarios del sistema (no necesita Tesseract/FFmpeg/oemer).
# Idempotente: pip no reinstala lo ya presente. opencv-python-headless evita
# la dependencia de libGL de opencv-python en contenedores sin display.
pip install --quiet --disable-pip-version-check \
  numpy \
  opencv-python-headless \
  scikit-image \
  Pillow \
  img2pdf \
  tqdm

echo "session-start: núcleo del pipeline instalado (CV/PDF)."
echo "Para el pipeline completo (OCR/OMR/comparación) instala requirements.txt"
echo "y los binarios del sistema (tesseract-ocr, ffmpeg)."
