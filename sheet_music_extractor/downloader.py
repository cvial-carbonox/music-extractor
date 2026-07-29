"""
downloader.py — Descarga de video desde YouTube.
"""
import os
import yt_dlp
from pathlib import Path
from config import Config


def download_video(cfg: Config) -> str:
    """Descarga el video de YouTube. Retorna ruta al archivo."""
    video_path = str(cfg.base / "video.mp4")

    if os.path.exists(video_path):
        print(f"⏭️  Video ya existe: {video_path}")
        return video_path

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': video_path,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    print(f"⬇️  Descargando: {cfg.youtube_url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(cfg.youtube_url, download=True)
        title = info.get('title', 'desconocido')
        duration = info.get('duration', 0)
        print(f"   🎵 Título: {title}")
        print(f"   ⏱️  Duración: {duration // 60}:{duration % 60:02d}")

    print(f"✅ Descargado: {video_path}")
    return video_path


def get_video_info(url: str) -> dict:
    """Obtiene metadatos del video sin descargarlo."""
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        'title': info.get('title', ''),
        'duration': info.get('duration', 0),
        'uploader': info.get('uploader', ''),
        'thumbnail': info.get('thumbnail', ''),
    }
