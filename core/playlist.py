from dataclasses import dataclass, field

import yt_dlp


@dataclass
class Pista:
    id: str
    titulo: str
    url: str
    duracion: int = 0


@dataclass
class ListaInfo:
    titulo: str
    url: str
    pistas: list[Pista] = field(default_factory=list)


_INVALIDOS = {"[Private video]", "[Deleted video]"}


def obtener_lista(url: str) -> ListaInfo:
    """Lee una lista de reproducción SIN descargar nada. Bloqueante (usa red)."""
    opts = {
        "extract_flat": "in_playlist",
        "noplaylist": False,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # Si el enlace era un video suelto, lo tratamos como lista de 1 pista.
    if "entries" not in info:
        p = Pista(info.get("id", ""), info.get("title", url),
                  info.get("webpage_url") or url, int(info.get("duration") or 0))
        return ListaInfo(info.get("title") or "lista", url, [p])

    pistas = []
    for e in info.get("entries") or []:
        if not e:
            continue
        vid = e.get("id") or ""
        link = e.get("url") or ""
        if not link.startswith("http"):
            if not vid:
                continue
            link = f"https://www.youtube.com/watch?v={vid}"
        titulo = e.get("title") or vid or link
        if titulo in _INVALIDOS:
            continue
        pistas.append(Pista(vid, titulo, link, int(e.get("duration") or 0)))
    return ListaInfo(info.get("title") or "lista", url, pistas)
