#!/usr/bin/env python3
"""
test_music_analysis.py — Verifica la mitad de análisis musical del pipeline
(comparador nota a nota + musicdiff, y fusión/resumen OMR) usando MusicXML
sintéticos, sin necesidad de vídeo, YouTube, Tesseract ni oemer.

Se salta con elegancia (SKIP, exit 0) si faltan music21 o musicdiff, para no
romper entornos que sólo tienen el núcleo CV/PDF.

Uso:  python test_music_analysis.py
"""
import sys
import tempfile
from pathlib import Path


def _require(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def _make_score(pitches, path):
    from music21 import stream, note
    s = stream.Stream()
    for p in pitches:
        s.append(note.Note(p, quarterLength=1.0))
    s.write("musicxml", fp=str(path))
    return str(path)


def test_comparator(work: Path) -> None:
    """El comparador debe medir bien las notas y producir diff/OMR-NED."""
    from config import Config
    from comparator import ScoreComparator

    ref = _make_score(["C4", "D4", "E4", "F4", "G4"], work / "ref.musicxml")
    ext = _make_score(["C4", "D4", "E4", "F#4", "G4"], work / "ext.musicxml")  # 1 nota

    cfg = Config(output_dir=str(work / "cmp_out"))
    cfg.ensure_dirs()
    res = ScoreComparator(cfg).compare(ext, ref)

    nc = res["note_comparison"]
    assert nc["extracted_notes"] == 5 and nc["reference_notes"] == 5, nc
    assert abs(nc["pitch_accuracy"] - 0.8) < 1e-6, f"pitch={nc['pitch_accuracy']}"
    assert nc["rhythm_accuracy"] == 1.0, f"rhythm={nc['rhythm_accuracy']}"
    assert nc["edit_distance"] == 1, f"edit={nc['edit_distance']}"

    # musicdiff (tras el fix del argumento -i): diff textual + OMR-NED.
    assert res.get("text_diff"), "musicdiff no produjo el diff textual"
    assert "OMR-NED" in res.get("omr_ned", {}), f"omr_ned={res.get('omr_ned')}"
    print("   ✅ comparador: note_comparison + text_diff + OMR-NED")


def test_omr_merge(work: Path) -> None:
    """merge_musicxml + extract_note_summary sobre MusicXML sintéticos."""
    from config import Config
    from frame_extractor import PageResult
    from omr_engine import OMREngine

    p1 = _make_score(["C4", "E4", "G4"], work / "p1.musicxml")
    p2 = _make_score(["A4", "B4"], work / "p2.musicxml")

    cfg = Config(output_dir=str(work / "omr_out"))
    cfg.ensure_dirs()
    omr = OMREngine(cfg)
    omr.cfg.enable_omr = True  # merge/summary no necesitan oemer, sólo music21

    pages = [
        PageResult(frame_path="", page_number=1, timestamp_sec=0.0, omr_musicxml=p1),
        PageResult(frame_path="", page_number=2, timestamp_sec=1.0, omr_musicxml=p2),
    ]
    merged = omr.merge_musicxml(pages)
    assert merged and Path(merged).exists(), "no se generó el MusicXML fusionado"

    summary = omr.extract_note_summary(merged)
    assert summary.get("total_notes", 0) > 0, f"summary={summary}"
    print(f"   ✅ OMR merge: {summary['total_notes']} notas en el resumen")


def main() -> int:
    if not (_require("music21") and _require("musicdiff")):
        print("⏭️  SKIP: music21/musicdiff no instalados (sólo núcleo CV/PDF).")
        return 0

    work = Path(tempfile.mkdtemp(prefix="sme_music_"))
    test_comparator(work)
    test_omr_merge(work)
    print("\n✅ MUSIC ANALYSIS TEST OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
