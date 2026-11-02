import sys
from pathlib import Path

import yt_dlp
from yt_dlp.utils import DownloadCancelled, DownloadError

from .models import Estado, Formato, Job, Opciones


def _carpeta_ffmpeg():
    """Carpeta con ffmpeg/ffprobe junto a la app (o en una subcarpeta «ffmpeg»).
    Si no hay, devuelve None y yt-dlp lo busca en el PATH del sistema."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    for c in (base, base / "ffmpeg", base / "ffmpeg" / "bin"):
        if (c / "ffmpeg.exe").is_file() or (c / "ffmpeg").is_file():
            return str(c)
    return None


def _construir_opts(op: Opciones, hook) -> dict:
    # Si el formato final es m4a/original, pedimos m4a nativo: sin recodificar.
    if op.formato in (Formato.M4A, Formato.ORIGINAL):
        formato = "bestaudio[ext=m4a]/bestaudio/best"
    else:
        formato = "bestaudio/best"

    pps = []
    if op.formato == Formato.MP3:
        pps.append({"key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": op.calidad})
    elif op.formato == Formato.M4A:
        pps.append({"key": "FFmpegExtractAudio", "preferredcodec": "m4a"})
    elif op.formato == Formato.OPUS:
        pps.append({"key": "FFmpegExtractAudio", "preferredcodec": "opus"})

    opts = {
        "format": formato,
        "outtmpl": f"{op.carpeta}/%(title)s.%(ext)s",
        "windowsfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "concurrent_fragment_downloads": 4,
        "progress_hooks": [hook],
        "postprocessors": pps,
    }

    ff = _carpeta_ffmpeg()
    if ff:
        opts["ffmpeg_location"] = ff

    # Carátula: solo en formatos donde se puede incrustar de forma fiable.
    if op.metadatos and op.formato in (Formato.MP3, Formato.M4A, Formato.OPUS):
        opts["writethumbnail"] = True
        opts["postprocessors"] = [
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
            *pps,
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ]
    elif op.metadatos:
        opts["postprocessors"] = [*pps, {"key": "FFmpegMetadata"}]

    return opts


def descargar(job: Job, on_update=lambda j: None) -> None:
    """Bloqueante. Pensado para correr en un hilo de la cola."""
    if job.cancelar.is_set():
        job.estado = Estado.CANCELADO
        on_update(job)
        return

    def hook(d):
        if job.cancelar.is_set():
            raise DownloadCancelled()
        job.titulo = d.get("info_dict", {}).get("title", job.titulo)
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                job.progreso = d["downloaded_bytes"] / total * 100
            job.estado = Estado.DESCARGANDO
        elif d["status"] == "finished":
            job.progreso = 100.0
            job.estado = Estado.CONVIRTIENDO
        on_update(job)

    job.estado = Estado.DESCARGANDO
    on_update(job)
    try:
        with yt_dlp.YoutubeDL(_construir_opts(job.opciones, hook)) as ydl:
            info = ydl.extract_info(job.url, download=True)
        job.titulo = info.get("title", job.titulo)
        descargas = info.get("requested_downloads") or []
        if descargas:
            job.archivo = descargas[0].get("filepath", "")
        job.estado = Estado.COMPLETADO
    except DownloadCancelled:
        job.estado = Estado.CANCELADO
    except DownloadError as e:
        job.estado = Estado.ERROR
        job.error = str(e)
    finally:
        on_update(job)