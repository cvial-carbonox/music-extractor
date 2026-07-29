"""
omr_engine.py — OMR (Optical Music Recognition) con oemer.
Convierte imágenes de partitura → MusicXML → MIDI.
Extrae notas, ritmos, claves, armaduras.
"""
import subprocess
import shutil
from pathlib import Path
from config import Config
from frame_extractor import PageResult


class OMREngine:

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._check_oemer()

    def _check_oemer(self):
        """Verifica que oemer esté instalado."""
        if shutil.which("oemer") is None:
            print("⚠️  oemer no encontrado en PATH. OMR desactivado.")
            print("   Instalar: pip install oemer")
            self.cfg.enable_omr = False

    def process_page(self, page: PageResult) -> PageResult:
        """
        Ejecuta OMR sobre la imagen de una página.
        Genera MusicXML y MIDI.
        """
        if not self.cfg.enable_omr:
            return page

        print(f"   🎵 OMR en página {page.page_number}...")

        # oemer necesita la imagen en un directorio de trabajo
        page_img = Path(page.frame_path)
        omr_output = self.cfg.omr_dir / f"page_{page.page_number:03d}"
        omr_output.mkdir(parents=True, exist_ok=True)

        # Copiar imagen al directorio OMR
        work_img = omr_output / page_img.name
        shutil.copy2(page.frame_path, work_img)

        # Construir comando oemer
        cmd = ["oemer", str(work_img), "-o", str(omr_output)]
        if self.cfg.omr_use_tf:
            cmd.append("--use-tf")
        if self.cfg.omr_without_deskew:
            cmd.append("--without-deskew")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min por página
                cwd=str(omr_output),
            )

            if result.returncode != 0:
                print(f"   ⚠️  OMR error en página {page.page_number}:")
                print(f"      {result.stderr[:200]}")
                return page

            # Buscar archivos de salida
            musicxml_files = list(omr_output.glob("*.musicxml")) + \
                             list(omr_output.glob("*.xml"))
            midi_files = list(omr_output.glob("*.midi")) + \
                         list(omr_output.glob("*.mid"))

            if musicxml_files:
                page.omr_musicxml = str(musicxml_files[0])
                print(f"   ✅ MusicXML: {musicxml_files[0].name}")

            if midi_files:
                page.omr_midi = str(midi_files[0])
                print(f"   ✅ MIDI: {midi_files[0].name}")

            # También buscar la imagen de análisis de oemer
            analysis_imgs = list(omr_output.glob("*_analysis.png")) + \
                            list(omr_output.glob("*_out.png"))
            if analysis_imgs:
                print(f"   🖼️  Análisis visual: {analysis_imgs[0].name}")

        except subprocess.TimeoutExpired:
            print(f"   ⚠️  OMR timeout en página {page.page_number}")
        except FileNotFoundError:
            print("   ⚠️  Comando 'oemer' no encontrado")
            self.cfg.enable_omr = False
        except Exception as e:
            print(f"   ⚠️  OMR error: {e}")

        return page

    def merge_musicxml(self, pages: list, output_name: str = "partitura_completa.musicxml") -> str:
        """
        Fusiona los MusicXML de todas las páginas en uno solo
        usando music21.
        """
        if not self.cfg.enable_omr:
            return ""

        try:
            from music21 import converter, stream, metadata

            xml_files = [p.omr_musicxml for p in pages if p.omr_musicxml]
            if not xml_files:
                print("⚠️  No hay archivos MusicXML para fusionar")
                return ""

            print(f"\n🔗 Fusionando {len(xml_files)} páginas en un solo MusicXML...")

            # Parsear la primera como base
            merged = converter.parse(xml_files[0])

            # Append de las siguientes
            for xml_path in xml_files[1:]:
                try:
                    part_score = converter.parse(xml_path)
                    # Extraer compases y agregarlos
                    for part in part_score.parts:
                        for measure in part.getElementsByClass('Measure'):
                            # Append al primer part del merged
                            if merged.parts:
                                merged.parts[0].append(measure)
                except Exception as e:
                    print(f"   ⚠️  Error fusionando {xml_path}: {e}")

            # Metadatos
            merged.metadata = metadata.Metadata()
            merged.metadata.title = "Partitura extraída de YouTube"
            merged.metadata.composer = "Extraído con Sheet Music Extractor"

            output_path = str(self.cfg.omr_dir / output_name)
            merged.write('musicxml', fp=output_path)
            print(f"✅ MusicXML fusionado: {output_path}")

            # También exportar MIDI
            midi_path = output_path.replace('.musicxml', '.mid')
            merged.write('midi', fp=midi_path)
            print(f"✅ MIDI fusionado: {midi_path}")

            return output_path

        except ImportError:
            print("⚠️  music21 no instalado. No se puede fusionar.")
            return ""
        except Exception as e:
            print(f"⚠️  Error fusionando MusicXML: {e}")
            return ""

    def extract_note_summary(self, musicxml_path: str) -> dict:
        """Extrae un resumen de notas del MusicXML usando music21."""
        if not musicxml_path:
            return {}

        try:
            from music21 import converter

            score = converter.parse(musicxml_path)
            notes = score.recurse().notes

            pitch_names = [n.nameWithOctave for n in notes if hasattr(n, 'nameWithOctave')]
            durations = [float(n.quarterLength) for n in notes]

            return {
                'total_notes': len(pitch_names),
                'pitch_range': f"{min(pitch_names)} – {max(pitch_names)}" if pitch_names else "N/A",
                'unique_pitches': len(set(pitch_names)),
                'first_20_notes': pitch_names[:20],
                'durations': durations[:20],
            }
        except Exception as e:
            return {'error': str(e)}
