"""Interfaz web con Gradio (punto de entrada).

Ejecuta::

    python app.py

y abre el navegador para pegar la URL de un vídeo y obtener el PDF con la
partitura extraída.
"""
from __future__ import annotations

import logging

import gradio as gr

import pipeline
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def process(
    url: str,
    frame_interval: float,
    ssim_threshold: float,
    ocr_enabled: bool,
    omr_enabled: bool,
    progress: gr.Progress = gr.Progress(),
):
    """Callback del botón: ejecuta el pipeline y devuelve PDF + galería."""
    if not url or not url.strip():
        raise gr.Error("Introduce una URL de vídeo válida.")

    config = Config(
        frame_interval_sec=float(frame_interval),
        ssim_threshold=float(ssim_threshold),
        ocr_enabled=bool(ocr_enabled),
        omr_enabled=bool(omr_enabled),
        use_omr_dedup=bool(omr_enabled),
    )

    def _cb(fraction: float, message: str) -> None:
        progress(fraction, desc=message)

    try:
        result = pipeline.run(url.strip(), config, progress=_cb)
    except Exception as exc:  # se muestra como error en la UI
        logger.exception("El pipeline falló")
        raise gr.Error(str(exc)) from exc

    gallery = [str(p) for p in result.page_paths]
    summary = f"✅ {result.num_pages} página(s)"
    if result.title:
        summary += f" · {result.title}"
    return str(result.pdf_path), gallery, summary


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Extractor de Partituras") as demo:
        gr.Markdown(
            "# 🎼 Extractor de Partituras\n"
            "Pega la URL de un vídeo que muestre una partitura (página a página "
            "o con scroll) y obtén un **PDF** limpio con las páginas únicas."
        )

        with gr.Row():
            url = gr.Textbox(
                label="URL del vídeo",
                placeholder="https://www.youtube.com/watch?v=…",
                scale=4,
            )
            btn = gr.Button("Extraer", variant="primary", scale=1)

        with gr.Accordion("Opciones avanzadas", open=False):
            frame_interval = gr.Slider(
                0.25, 5.0, value=1.0, step=0.25,
                label="Intervalo de muestreo (s)",
                info="Cada cuántos segundos se analiza un frame.",
            )
            ssim_threshold = gr.Slider(
                0.50, 0.99, value=0.92, step=0.01,
                label="Umbral de similitud (SSIM)",
                info="Más alto = más sensible a cambios pequeños (más páginas).",
            )
            ocr_enabled = gr.Checkbox(
                value=True, label="Detectar título con OCR"
            )
            omr_enabled = gr.Checkbox(
                value=False,
                label="OMR + deduplicación musical (lento, requiere oemer)",
            )

        status = gr.Textbox(label="Estado", interactive=False)
        pdf_out = gr.File(label="PDF resultante")
        gallery = gr.Gallery(
            label="Páginas detectadas", columns=3, height=420, object_fit="contain"
        )

        btn.click(
            fn=process,
            inputs=[url, frame_interval, ssim_threshold, ocr_enabled, omr_enabled],
            outputs=[pdf_out, gallery, status],
        )

    return demo


if __name__ == "__main__":
    build_ui().launch()
