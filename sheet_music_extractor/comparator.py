"""
comparator.py — Compara la partitura extraída (OMR) con una partitura
de referencia usando musicdiff y music21.
Genera diff visual (PDF), diff textual y métricas OMR-NED.
"""
import json
import subprocess
from pathlib import Path
from config import Config


class ScoreComparator:

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def compare(self, extracted_xml: str, reference_path: str) -> dict:
        """
        Compara dos partituras:
        - extracted_xml: MusicXML generado por OMR
        - reference_path: Partitura de referencia (MusicXML, MIDI, .krn, .mei)

        Retorna dict con resultados.
        """
        if not extracted_xml or not reference_path:
            return {'error': 'Faltan archivos para comparar'}

        ref = Path(reference_path)
        if not ref.exists():
            return {'error': f'Archivo de referencia no encontrado: {reference_path}'}

        print(f"\n🔍 Comparando partituras...")
        print(f"   Extraída:    {extracted_xml}")
        print(f"   Referencia:  {reference_path}")

        results = {
            'extracted': extracted_xml,
            'reference': reference_path,
            'visual_pdf': '',
            'text_diff': '',
            'omr_ned': {},
            'note_comparison': {},
        }

        # ── 1. Diff visual + textual con musicdiff ──
        results.update(self._run_musicdiff(extracted_xml, reference_path))

        # ── 2. Comparación nota a nota con music21 ──
        results['note_comparison'] = self._compare_notes(extracted_xml, reference_path)

        return results

    def _run_musicdiff(self, file1: str, file2: str) -> dict:
        """Ejecuta musicdiff para diff visual y textual."""
        output = {}
        include_args = ",".join(self.cfg.comparison_details)

        # ── Diff visual (PDF) ──
        try:
            visual_cmd = [
                "python3", "-m", "musicdiff",
                "-i", include_args,
                "-o", "visual",
                "--", file1, file2,
            ]

            result = subprocess.run(
                visual_cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.cfg.comparison_dir),
            )

            # musicdiff genera PDFs en el directorio actual
            pdfs = list(self.cfg.comparison_dir.glob("*diff*.pdf")) + \
                   list(self.cfg.comparison_dir.glob("*_1.pdf")) + \
                   list(self.cfg.comparison_dir.glob("*_2.pdf"))

            if pdfs:
                output['visual_pdf'] = str(pdfs[0])
                print(f"   📄 Diff visual: {pdfs[0].name}")
            else:
                print(f"   ⚠️  musicdiff visual: {result.stderr[:200]}")

        except Exception as e:
            print(f"   ⚠️  Error en diff visual: {e}")

        # ── Diff textual ──
        try:
            text_cmd = [
                "python3", "-m", "musicdiff",
                "-i", include_args,
                "-o", "text",
                "--", file1, file2,
            ]

            result = subprocess.run(
                text_cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.stdout:
                diff_text_path = self.cfg.comparison_dir / "diff_output.txt"
                diff_text_path.write_text(result.stdout, encoding='utf-8')
                output['text_diff'] = str(diff_text_path)
                print(f"   📝 Diff textual: {diff_text_path.name}")

        except Exception as e:
            print(f"   ⚠️  Error en diff textual: {e}")

        # ── Métricas OMR-NED (JSON) ──
        try:
            ned_cmd = [
                "python3", "-m", "musicdiff",
                "-i", include_args,
                "-o", "omrned",
                "--", file1, file2,
            ]

            result = subprocess.run(
                ned_cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.stdout:
                try:
                    ned_data = json.loads(result.stdout)
                    output['omr_ned'] = ned_data
                    ned_path = self.cfg.comparison_dir / "omr_ned.json"
                    ned_path.write_text(json.dumps(ned_data, indent=2), encoding='utf-8')
                    print(f"   📊 OMR-NED: {ned_path.name}")

                    # Mostrar métricas clave
                    if isinstance(ned_data, dict):
                        for key in ['ned', 'precision', 'recall', 'f1']:
                            if key in ned_data:
                                print(f"      {key}: {ned_data[key]:.4f}")
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            print(f"   ⚠️  Error en OMR-NED: {e}")

        return output

    def _compare_notes(self, extracted_xml: str, reference_path: str) -> dict:
        """
        Comparación nota a nota usando music21.
        Calcula precisión de pitch y ritmo.
        """
        try:
            from music21 import converter, note, stream

            score_ext = converter.parse(extracted_xml)
            score_ref = converter.parse(reference_path)

            # Extraer secuencias de notas
            notes_ext = self._get_note_sequence(score_ext)
            notes_ref = self._get_note_sequence(score_ref)

            if not notes_ext or not notes_ref:
                return {'error': 'No se pudieron extraer notas de alguna partitura'}

            # ── Comparación de pitches ──
            pitch_match = 0
            min_len = min(len(notes_ext), len(notes_ref))
            for i in range(min_len):
                if notes_ext[i]['pitch'] == notes_ref[i]['pitch']:
                    pitch_match += 1

            pitch_accuracy = pitch_match / min_len if min_len > 0 else 0

            # ── Comparación de duraciones ──
            dur_match = 0
            for i in range(min_len):
                if abs(notes_ext[i]['duration'] - notes_ref[i]['duration']) < 0.01:
                    dur_match += 1

            dur_accuracy = dur_match / min_len if min_len > 0 else 0

            # ── Edit distance (Levenshtein) sobre pitches ──
            edit_dist = self._levenshtein(
                [n['pitch'] for n in notes_ext],
                [n['pitch'] for n in notes_ref]
            )
            max_len = max(len(notes_ext), len(notes_ref))
            similarity = 1 - (edit_dist / max_len) if max_len > 0 else 0

            result = {
                'extracted_notes': len(notes_ext),
                'reference_notes': len(notes_ref),
                'pitch_accuracy': round(pitch_accuracy, 4),
                'rhythm_accuracy': round(dur_accuracy, 4),
                'edit_distance': edit_dist,
                'sequence_similarity': round(similarity, 4),
                'first_10_extracted': [n['pitch'] for n in notes_ext[:10]],
                'first_10_reference': [n['pitch'] for n in notes_ref[:10]],
            }

            print(f"\n   📊 Resultados de comparación:")
            print(f"      Notas extraídas:     {result['extracted_notes']}")
            print(f"      Notas referencia:   {result['reference_notes']}")
            print(f"      Precisión pitch:    {result['pitch_accuracy']:.1%}")
            print(f"      Precisión ritmo:    {result['rhythm_accuracy']:.1%}")
            print(f"      Similitud global:   {result['sequence_similarity']:.1%}")
            print(f"      Edit distance:      {result['edit_distance']}")

            # Guardar reporte
            report_path = self.cfg.comparison_dir / "comparison_report.txt"
            with open(report_path, 'w', encoding='utf-8') as f:
                for k, v in result.items():
                    f.write(f"{k}: {v}\n")

            return result

        except ImportError:
            return {'error': 'music21 no instalado'}
        except Exception as e:
            return {'error': str(e)}

    def _get_note_sequence(self, score) -> list:
        """Extrae secuencia ordenada de (pitch, duración) de un score."""
        from music21 import note, chord

        notes = []
        for el in score.recurse():
            if isinstance(el, note.Note):
                notes.append({
                    'pitch': el.nameWithOctave,
                    'midi': el.pitch.midi,
                    'duration': float(el.quarterLength),
                    'offset': float(el.offset),
                })
            elif isinstance(el, chord.Chord):
                notes.append({
                    'pitch': el.pitchedCommonName,
                    'midi': el.bass().midi,
                    'duration': float(el.quarterLength),
                    'offset': float(el.offset),
                })

        notes.sort(key=lambda n: n['offset'])
        return notes

    @staticmethod
    def _levenshtein(seq1: list, seq2: list) -> int:
        """Distancia de Levenshtein entre dos secuencias."""
        n, m = len(seq1), len(seq2)
        dp = [[0] * (m + 1) for _ in range(n + 1)]

        for i in range(n + 1):
            dp[i][0] = i
        for j in range(m + 1):
            dp[0][j] = j

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = 0 if seq1[i - 1] == seq2[j - 1] else 1
                dp[i][j] = min(
                    dp[i - 1][j] + 1,
                    dp[i][j - 1] + 1,
                    dp[i - 1][j - 1] + cost,
                )

        return dp[n][m]
