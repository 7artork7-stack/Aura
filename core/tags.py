import base64
import io
from dataclasses import dataclass
from pathlib import Path

from mutagen.id3 import (APIC, ID3, TALB, TCON, TDRC, TIT2, TPE1,
                         ID3NoHeaderError)
from mutagen.flac import Picture
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from PIL import Image

EXT_SOPORTADAS = {".mp3", ".m4a", ".opus"}


@dataclass
class Metadatos:
    titulo: str = ""
    artista: str = ""
    album: str = ""
    genero: str = ""
    anio: str = ""


def _ext(ruta: Path) -> str:
    ext = ruta.suffix.lower()
    if ext not in EXT_SOPORTADAS:
        raise ValueError(f"Formato no soportado: {ext}")
    return ext


# ---------------------------------------------------------------- portada
def preparar_portada(datos: bytes, recortar: bool = True, lado: int = 800):
    """Devuelve (jpeg_bytes, ancho, alto). Recorta al centro a cuadrado."""
    img = Image.open(io.BytesIO(datos)).convert("RGB")
    if recortar:
        m = min(img.size)
        izq, sup = (img.width - m) // 2, (img.height - m) // 2
        img = img.crop((izq, sup, izq + m, sup + m))
        if m > lado:
            img = img.resize((lado, lado), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue(), img.width, img.height


def leer_portada(ruta) -> bytes | None:
    ruta = Path(ruta)
    ext = _ext(ruta)
    if ext == ".mp3":
        try:
            apics = ID3(ruta).getall("APIC")
        except ID3NoHeaderError:
            return None
        return apics[0].data if apics else None
    if ext == ".m4a":
        covr = (MP4(ruta).tags or {}).get("covr")
        return bytes(covr[0]) if covr else None
    f = OggOpus(ruta)
    bloques = f.tags.get("metadata_block_picture") if f.tags else None
    if not bloques:
        return None
    return Picture(base64.b64decode(bloques[0])).data


def poner_portada(ruta, imagen, recortar: bool = True) -> None:
    """`imagen` puede ser bytes o la ruta a un archivo de imagen."""
    ruta = Path(ruta)
    ext = _ext(ruta)
    datos = imagen if isinstance(imagen, bytes) else Path(imagen).read_bytes()
    jpeg, ancho, alto = preparar_portada(datos, recortar)

    if ext == ".mp3":
        try:
            t = ID3(ruta)
        except ID3NoHeaderError:
            t = ID3()
        t.delall("APIC")
        t.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=jpeg))
        t.save(ruta, v2_version=3)
    elif ext == ".m4a":
        f = MP4(ruta)
        if f.tags is None:
            f.add_tags()
        f.tags["covr"] = [MP4Cover(jpeg, imageformat=MP4Cover.FORMAT_JPEG)]
        f.save()
    else:  # opus: la portada va como bloque FLAC en base64 dentro del comentario
        pic = Picture()
        pic.type, pic.mime, pic.desc = 3, "image/jpeg", "Cover"
        pic.width, pic.height, pic.depth, pic.data = ancho, alto, 24, jpeg
        f = OggOpus(ruta)
        f.tags["metadata_block_picture"] = [
            base64.b64encode(pic.write()).decode("ascii")
        ]
        f.save()


# -------------------------------------------------------------- metadatos
def leer(ruta) -> Metadatos:
    ruta = Path(ruta)
    ext = _ext(ruta)
    if ext == ".mp3":
        try:
            t = ID3(ruta)
        except ID3NoHeaderError:
            return Metadatos()

        def g(k):
            fr = t.get(k)
            return str(fr.text[0]) if fr and fr.text else ""

        return Metadatos(g("TIT2"), g("TPE1"), g("TALB"), g("TCON"), g("TDRC")[:4])

    if ext == ".m4a":
        t = MP4(ruta).tags or {}
        claves = ("\xa9nam", "\xa9ART", "\xa9alb", "\xa9gen", "\xa9day")
    else:
        t = OggOpus(ruta).tags or {}
        claves = ("title", "artist", "album", "genre", "date")

    def g(k):
        v = t.get(k)
        return str(v[0]) if v else ""

    m = Metadatos(*(g(k) for k in claves))
    m.anio = m.anio[:4]
    return m


def escribir(ruta, meta: Metadatos) -> None:
    ruta = Path(ruta)
    ext = _ext(ruta)

    if ext == ".mp3":
        try:
            t = ID3(ruta)
        except ID3NoHeaderError:
            t = ID3()
        for marco, valor in ((TIT2, meta.titulo), (TPE1, meta.artista),
                             (TALB, meta.album), (TCON, meta.genero),
                             (TDRC, meta.anio)):
            t.delall(marco.__name__)
            if valor:
                t.add(marco(encoding=3, text=valor))
        # v2.3 es la versión que el Explorador de Windows lee mejor
        t.save(ruta, v2_version=3)
        return

    if ext == ".m4a":
        f = MP4(ruta)
        if f.tags is None:
            f.add_tags()
        pares = (("\xa9nam", meta.titulo), ("\xa9ART", meta.artista),
                 ("\xa9alb", meta.album), ("\xa9gen", meta.genero),
                 ("\xa9day", meta.anio))
    else:
        f = OggOpus(ruta)
        pares = (("title", meta.titulo), ("artist", meta.artista),
                 ("album", meta.album), ("genre", meta.genero),
                 ("date", meta.anio))

    for clave, valor in pares:
        if valor:
            f.tags[clave] = [valor]
        elif clave in f.tags:
            del f.tags[clave]
    f.save()