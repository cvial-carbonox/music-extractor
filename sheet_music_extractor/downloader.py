"""
downloader.py — Descarga de vídeos con yt-dlp.

Envuelve la API de Python de ``yt-dlp`` para obtener el archivo de vídeo y sus
metadatos (título, id, duración). Descarga en ``config.base`` (output/).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

try:  # yt-dlp es una dependencia core, pero degradamos con elegancia.
    import yt_dlp
except ImportError:  # pragma: no cover
    yt_dlp = None

from config import Config

logger = logging.getLogger(__name__)

# Se limita a 1080p: la resolución de una partitura rara vez necesita más.
DEFAULT_VIDEO_FORMAT = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"


class DownloadError(RuntimeError):
    """Error al descargar un vídeo."""


@dataclass
class VideoInfo:
    """Resultado de una descarga."""

    path: Path
    title: str = ""
    video_id: str = ""
    duration: float = 0.0


def download_video(
    config: Config,
    url: Optional[str] = None,
    progress_hook: Optional[Callable[[dict], None]] = None,
) -> VideoInfo:
    """Descarga el vídeo a ``config.base`` y devuelve un :class:`VideoInfo`.

    Args:
        config: Configuración del pipeline.
        url: URL a descargar; si es ``None`` se usa ``config.youtube_url``.
        progress_hook: Callback opcional de progreso de yt-dlp.

    Raises:
        DownloadError: si yt-dlp no está instalado o la descarga falla.
    """
    if yt_dlp is None:
        raise DownloadError("yt-dlp no está instalado. Ejecuta: pip install yt-dlp")

    url = url or config.youtube_url
    config.base.mkdir(parents=True, exist_ok=True)
    outtmpl = str(config.base / "video.%(ext)s")

    ydl_opts = {
        "format": DEFAULT_VIDEO_FORMAT,
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
    }
    if progress_hook is not None:
        ydl_opts["progress_hooks"] = [progress_hook]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
            # Tras el merge, la extensión puede cambiar a .mp4.
            if not path.exists():
                merged = path.with_suffix(".mp4")
                if merged.exists():
                    path = merged
    except Exception as exc:  # yt-dlp lanza múltiples tipos de excepción.
        raise DownloadError(f"No se pudo descargar el vídeo: {exc}") from exc

    if not path.exists():
        raise DownloadError(
            f"Descarga completada pero no se encontró el archivo esperado: {path}"
        )

    logger.info("Vídeo descargado en %s", path)
    return VideoInfo(
        path=path,
        title=(info.get("title") or "").strip(),
        video_id=info.get("id") or "",
        duration=float(info.get("duration") or 0.0),
    )
