import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum


class Estado(str, Enum):
    PENDIENTE = "pendiente"
    DESCARGANDO = "descargando"
    CONVIRTIENDO = "convirtiendo"
    COMPLETADO = "completado"
    ERROR = "error"
    CANCELADO = "cancelado"


class Formato(str, Enum):
    MP3 = "mp3"
    M4A = "m4a"
    OPUS = "opus"
    ORIGINAL = "original"  # solo baja el audio, sin recodificar


@dataclass
class Opciones:
    formato: Formato = Formato.MP3
    calidad: str = "192"          # kbps, solo aplica a mp3
    carpeta: str = "descargas"
    metadatos: bool = True        # etiquetas + carátula


@dataclass
class Job:
    url: str
    opciones: Opciones
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    estado: Estado = Estado.PENDIENTE
    titulo: str = ""
    progreso: float = 0.0
    archivo: str = ""
    error: str = ""
    cancelar: threading.Event = field(default_factory=threading.Event, repr=False)