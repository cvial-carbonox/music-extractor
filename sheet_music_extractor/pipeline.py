"""
pipeline.py — Orquestador principal. Ejecuta todo el pipeline
o pasos individuales.
"""
from config import Config
from downloader import download_video
from frame_extractor import FrameExtractor, PageResult
from ocr_engine import OCREngine
from omr_engine import OMREngine
from comparator import ScoreComparator
from pdf_generator import PDFGenerator


class Pipeline:

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cfg.ensure_dirs()

        self.extractor = FrameExtractor(cfg)
        self.ocr = OCREngine(cfg)
        self.omr = OMREngine(cfg)
        self.comparator = ScoreComparator(cfg)
        self.pdf_gen = PDFGenerator(cfg)

        self.pages: list[PageResult] = []
        self.results: dict = {}

    def run_full(self, progress_callback=None) -> dict:
        """
        Ejecuta el pipeline completo.
        progress_callback(step: str, progress: float) para la UI.
        """
        def report(step, pct):
            print(f"\n{'━' * 50}")
            print(f"  [{pct:3.0f}%] {step}")
            print(f"{'━' * 50}")
            if progress_callback:
                progress_callback(step, pct)

        # ── 1. Descargar video ──
        report("Descargando video de YouTube...", 5)
        video_path = download_video(self.cfg)

        # ── 2. Extraer frames ──
        report("Extrayendo frames del video...", 15)
        frames = self.extractor.extract_frames(video_path)

        # ── 3. Filtrar páginas únicas ──
        report("Detectando páginas de partitura...", 30)
        self.pages = self.extractor.filter_unique_pages(frames)

        if not self.pages:
            report("❌ No se detectó partitura en el video", 100)
            return {'error': 'No se detectó partitura'}

        # ── 4. OCR en cada página ──
        report("Ejecutando OCR (acordes, texto, indicaciones)...", 45)
        for i, page in enumerate(self.pages):
            self.pages[i] = self.ocr.process_page(page)
            chords = ", ".join(page.chords_found) if page.chords_found else "—"
            print(f"   📄 Pág {page.page_number}: [{chords}]")

        # ── 5. OMR (reconocimiento de notas) ──
        if self.cfg.enable_omr:
            report("Ejecutando OMR (reconocimiento de notas)...", 60)
            for i, page in enumerate(self.pages):
                self.pages[i] = self.omr.process_page(page)

            # Fusionar MusicXML
            merged_xml = self.omr.merge_musicxml(self.pages)
            self.results['merged_musicxml'] = merged_xml

            # Resumen de notas
            if merged_xml:
                summary = self.omr.extract_note_summary(merged_xml)
                self.results['note_summary'] = summary
                if summary and 'total_notes' in summary:
                    print(f"\n   🎼 Total de notas reconocidas: {summary['total_notes']}")
                    print(f"   🎼 Rango: {summary.get('pitch_range', 'N/A')}")
        else:
            report("OMR desactivado (oemer no disponible)", 60)

        # ── 6. Comparación con referencia ──
        if self.cfg.reference_score_path and self.results.get('merged_musicxml'):
            report("Comparando con partitura de referencia...", 75)
            comparison = self.comparator.compare(
                self.results['merged_musicxml'],
                self.cfg.reference_score_path,
            )
            self.results['comparison'] = comparison
        else:
            report("Sin partitura de referencia (omitido)", 75)

        # ── 7. Mejorar imágenes + anotar ──
        report("Mejorando imágenes y anotando...", 85)
        annotated_paths = []
        for page in self.pages:
            path = self.pdf_gen.enhance_and_annotate(page)
            annotated_paths.append(path)

        # ── 8. Generar PDF ──
        report("Generando PDF final...", 92)
        pdf_path = self.pdf_gen.generate_pdf(self.pages, annotated_paths)
        self.results['pdf'] = pdf_path

        # ── 9. Reporte OCR ──
        report("Guardando reportes...", 97)
        ocr_report = self.pdf_gen.save_ocr_report(self.pages)
        self.results['ocr_report'] = ocr_report

        # ── Resumen final ──
        report("¡Completado!", 100)
        self.results['pages'] = len(self.pages)
        self.results['total_chords'] = sum(len(p.chords_found) for p in self.pages)

        self._print_summary()
        return self.results

    def _print_summary(self):
        """Imprime resumen final."""
        print("\n" + "═" * 60)
        print("  🎉 RESUMEN FINAL")
        print("═" * 60)
        print(f"  📄 Páginas detectadas:  {self.results.get('pages', 0)}")
        print(f"  🎸 Acordes OCR:         {self.results.get('total_chords', 0)}")
        print(f"  📄 PDF:                 {self.results.get('pdf', 'N/A')}")
        print(f"  📝 Reporte OCR:         {self.results.get('ocr_report', 'N/A')}")

        if self.results.get('merged_musicxml'):
            print(f"  🎼 MusicXML:            {self.results['merged_musicxml']}")

        if self.results.get('note_summary'):
            ns = self.results['note_summary']
            print(f"  🎵 Notas OMR:           {ns.get('total_notes', 'N/A')}")
            print(f"  🎵 Rango:               {ns.get('pitch_range', 'N/A')}")

        if self.results.get('comparison'):
            comp = self.results['comparison']
            nc = comp.get('note_comparison', {})
            if nc and 'pitch_accuracy' in nc:
                print(f"  📊 Precisión pitch:     {nc['pitch_accuracy']:.1%}")
                print(f"  📊 Precisión ritmo:     {nc['rhythm_accuracy']:.1%}")
                print(f"  📊 Similitud:           {nc['sequence_similarity']:.1%}")

        print("═" * 60 + "\n")
