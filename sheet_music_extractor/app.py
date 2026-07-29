"""
app.py — Interfaz web con Gradio (punto de entrada).

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
    fps_sample: float,
    ssim_threshold: float,
    min_stable_frames: int,
    detect_chords: bool,
    enable_omr: bool,
    reference_file,
    progress: gr.Progress = gr.Progress(),
):
    """Callback del botón: ejecuta el pipeline y devuelve PDF + galería."""
    if not url or not url.strip():
        raise gr.Error("Introduce una URL de vídeo válida.")

    config = Config(
        youtube_url=url.strip(),
        fps_sample=float(fps_sample),
        ssim_threshold=float(ssim_threshold),
        min_stable_frames=int(min_stable_frames),
        detect_chords=bool(detect_chords),
        annotate_chords=bool(detect_chords),
        enable_omr=bool(enable_omr),
        reference_score_path=(reference_file.name if reference_file else ""),
    )

    def _cb(fraction: float, message: str) -> None:
        progress(fraction, desc=message)

    try:
        result = pipeline.run(config, progress=_cb)
    except Exception as exc:  # se muestra como error en la UI
        logger.exception("El pipeline falló")
        raise gr.Error(str(exc)) from exc

    gallery = [str(p) for p in result.final_images]
    summary = f"✅ {result.num_pages} página(s)"
    if result.title:
        summary += f" · {result.title}"
    if result.comparisons:
        total_diff = sum(c.num_differences for c in result.comparisons)
        summary += f" · {total_diff} diferencia(s) vs. referencia"
    return str(result.pdf_path), gallery, summary


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Extractor de Partituras") as demo:
        gr.Markdown(
            "# 🎼 Extractor de Partituras\n"
            "Pega la URL de un vídeo que muestre una partitura (página a página) "
            "y obtén un **PDF** limpio con las páginas únicas, con acordes "
            "anotados opcionalmente."
        )

        with gr.Row():
            url = gr.Textbox(
                label="URL del vídeo",
                value=Config().youtube_url,
                placeholder="https://www.youtube.com/watch?v=…",
                scale=4,
            )
            btn = gr.Button("Extraer", variant="primary", scale=1)

        with gr.Accordion("Opciones avanzadas", open=False):
            fps_sample = gr.Slider(
                0.5, 5.0, value=2.0, step=0.5,
                label="Muestreo (frames/segundo)",
                info="Cuántos frames por segundo se analizan.",
            )
            ssim_threshold = gr.Slider(
                0.50, 0.99, value=0.88, step=0.01,
                label="Umbral de similitud (SSIM)",
                info="Más alto = más sensible a cambios (más páginas).",
            )
            min_stable_frames = gr.Slider(
                1, 10, value=3, step=1,
                label="Frames estables antes de capturar",
            )
            detect_chords = gr.Checkbox(
                value=True, label="Detectar y anotar acordes (OCR)"
            )
            enable_omr = gr.Checkbox(
                value=False,
                label="OMR: reconocer notas a MusicXML (lento, requiere oemer)",
            )
            reference_file = gr.File(
                label="Partitura de referencia (opcional: MusicXML/MIDI/krn)",
                file_types=[".musicxml", ".xml", ".mxl", ".mid", ".midi", ".krn"],
            )

        status = gr.Textbox(label="Estado", interactive=False)
        pdf_out = gr.File(label="PDF resultante")
        gallery = gr.Gallery(
            label="Páginas detectadas", columns=3, height=420, object_fit="contain"
        )

        btn.click(
            fn=process,
            inputs=[
                url, fps_sample, ssim_threshold, min_stable_frames,
                detect_chords, enable_omr, reference_file,
            ],
            outputs=[pdf_out, gallery, status],
        )

    return demo


if __name__ == "__main__":
    build_ui().launch()
