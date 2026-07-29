"""
app.py — Interfaz web con Gradio.
Punto de entrada principal de la aplicación.

Uso:  python app.py
Abre: http://localhost:7860
"""
import os
import json
import gradio as gr
from pathlib import Path
from config import Config
from pipeline import Pipeline
from downloader import get_video_info


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FUNCIÓN PRINCIPAL (llamada por Gradio)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def process_video(
    youtube_url: str,
    fps_sample: float,
    ssim_threshold: float,
    enable_omr: bool,
    reference_file,
    progress=gr.Progress(track_tqdm=True),
) -> tuple:
    """
    Procesa un video de YouTube y retorna todos los resultados.
    """
    if not youtube_url.strip():
        return "❌ Ingresa una URL de YouTube", None, None, None, None, None

    # Crear configuración
    cfg = Config(
        youtube_url=youtube_url.strip(),
        output_dir=f"output_{hash(youtube_url) % 10000:04d}",
        fps_sample=fps_sample,
        ssim_threshold=ssim_threshold,
        enable_omr=enable_omr,
    )

    # Partitura de referencia (si se subió)
    if reference_file is not None:
        cfg.reference_score_path = reference_file.name

    # Ejecutar pipeline
    pipeline = Pipeline(cfg)

    try:
        results = pipeline.run_full(
            progress_callback=lambda step, pct: progress(pct / 100, desc=step)
        )
    except Exception as e:
        return f"❌ Error: {str(e)}", None, None, None, None, None

    if 'error' in results:
        return f"❌ {results['error']}", None, None, None, None, None

    # ── Construir resumen ──
    summary_lines = [
        f"## ✅ Procesamiento Completado\n",
        f"| Métrica | Valor |",
        f"|---------|-------|",
        f"| Páginas detectadas | {results.get('pages', 0)} |",
        f"| Acordes OCR | {results.get('total_chords', 0)} |",
    ]

    if results.get('note_summary'):
        ns = results['note_summary']
        summary_lines.append(f"| Notas OMR | {ns.get('total_notes', 'N/A')} |")
        summary_lines.append(f"| Rango | {ns.get('pitch_range', 'N/A')} |")

    if results.get('comparison'):
        nc = results['comparison'].get('note_comparison', {})
        if nc and 'pitch_accuracy' in nc:
            summary_lines.append(f"| Precisión pitch | {nc['pitch_accuracy']:.1%} |")
            summary_lines.append(f"| Precisión ritmo | {nc['rhythm_accuracy']:.1%} |")
            summary_lines.append(f"| Similitud | {nc['sequence_similarity']:.1%} |")

    summary = "\n".join(summary_lines)

    # ── Archivos de salida ──
    pdf_file = results.get('pdf')
    ocr_file = results.get('ocr_report')
    musicxml_file = results.get('merged_musicxml')

    # Imágenes de páginas anotadas
    annotated_dir = cfg.annotated_dir
    gallery_images = sorted(annotated_dir.glob("page_*.png"))
    gallery = [str(p) for p in gallery_images]

    # Diff visual
    diff_pdf = None
    if results.get('comparison', {}).get('visual_pdf'):
        diff_pdf = results['comparison']['visual_pdf']

    return summary, pdf_file, ocr_file, musicxml_file, diff_pdf, gallery


def get_video_preview(url: str) -> str:
    """Obtiene info del video para preview."""
    if not url.strip():
        return ""
    try:
        info = get_video_info(url.strip())
        dur = info['duration']
        return (
            f"🎵 **{info['title']}**\n\n"
            f"- Canal: {info['uploader']}\n"
            f"- Duración: {dur // 60}:{dur % 60:02d}\n"
            f"- Thumbnail: {info['thumbnail'][:80]}..."
        )
    except Exception as e:
        return f"⚠️ No se pudo obtener info: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INTERFAZ GRADIO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_ui():
    """Construye la interfaz web."""

    with gr.Blocks(
        title="🎼 Extractor de Partituras",
        theme=gr.themes.Soft(
            primary_hue="indigo",
            secondary_hue="amber",
        ),
        css="""
        .main-header { text-align: center; margin-bottom: 10px; }
        .output-box { border: 2px solid #e0e0e0; border-radius: 8px; padding: 15px; }
        """
    ) as app:

        # ── Header ──
        gr.Markdown(
            """
            # 🎼 Extractor de Partituras de YouTube
            ### Video → Pentagrama → OCR + OMR → PDF + MusicXML + MIDI
            """,
            elem_classes="main-header",
        )

        with gr.Row():
            # ── Columna izquierda: Entradas ──
            with gr.Column(scale=1):
                gr.Markdown("### 📥 Entrada")

                url_input = gr.Textbox(
                    label="URL de YouTube",
                    placeholder="https://www.youtube.com/watch?v=...",
                    value="https://www.youtube.com/watch?v=wIdVXJlTfQk",
                    lines=2,
                )

                video_preview = gr.Markdown("")

                url_input.change(
                    fn=get_video_preview,
                    inputs=url_input,
                    outputs=video_preview,
                )

                gr.Markdown("### ⚙️ Configuración")

                fps_slider = gr.Slider(
                    minimum=0.5, maximum=5.0, value=2.0, step=0.5,
                    label="Frames por segundo (muestreo)",
                    info="Más alto = más preciso pero más lento",
                )

                ssim_slider = gr.Slider(
                    minimum=0.75, maximum=0.98, value=0.88, step=0.01,
                    label="Umbral SSIM (similitud de página)",
                    info="Menor = más sensible a cambios",
                )

                omr_checkbox = gr.Checkbox(
                    value=True,
                    label="Activar OMR (reconocimiento de notas con oemer)",
                    info="Requiere oemer instalado. Genera MusicXML y MIDI.",
                )

                gr.Markdown("### 📎 Partitura de Referencia (opcional)")

                reference_input = gr.File(
                    label="Subir partitura de referencia",
                    file_types=[".musicxml", ".xml", ".mid", ".midi", ".krn", ".mei"],
                    type="filepath",
                )

                gr.Markdown(
                    "*Formatos: MusicXML, MIDI, Kern (.krn), MEI*\n"
                    "*Se usa para comparar y evaluar la precisión del OMR.*"
                )

                run_button = gr.Button(
                    "🚀 Extraer Partitura",
                    variant="primary",
                    size="lg",
                )

            # ── Columna derecha: Resultados ──
            with gr.Column(scale=2):
                gr.Markdown("### 📊 Resultados")

                summary_output = gr.Markdown(
                    value="*Los resultados aparecerán aquí...*",
                    elem_classes="output-box",
                )

                with gr.Tabs():
                    with gr.Tab("📄 PDF"):
                        pdf_output = gr.File(
                            label="Partitura PDF",
                            file_types=[".pdf"],
                        )

                    with gr.Tab("🖼️ Páginas"):
                        gallery_output = gr.Gallery(
                            label="Páginas detectadas",
                            columns=3,
                            height="auto",
                        )

                    with gr.Tab("🎼 MusicXML / MIDI"):
                        musicxml_output = gr.File(
                            label="MusicXML (OMR)",
                            file_types=[".musicxml", ".xml"],
                        )

                    with gr.Tab("📝 OCR"):
                        ocr_output = gr.File(
                            label="Reporte OCR",
                            file_types=[".txt"],
                        )

                    with gr.Tab("🔍 Comparación"):
                        diff_output = gr.File(
                            label="Diff Visual (PDF)",
                            file_types=[".pdf"],
                        )

        # ── Footer ──
        gr.Markdown(
            """
            ---
            **Pipeline:** yt-dlp → OpenCV → SSIM → Tesseract OCR → oemer OMR → music21 → musicdiff → img2pdf
            """
        )

        # ── Conexión del botón ──
        run_button.click(
            fn=process_video,
            inputs=[url_input, fps_slider, ssim_slider, omr_checkbox, reference_input],
            outputs=[
                summary_output,
                pdf_output,
                ocr_output,
                musicxml_output,
                diff_output,
                gallery_output,
            ],
        )

    return app


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EJECUCIÓN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    app = build_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,       # True para link público temporal
        inbrowser=True,    # Abrir navegador automáticamente
    )
