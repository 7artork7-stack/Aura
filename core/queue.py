from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from yt_dlp.utils import sanitize_filename

from .downloader import descargar
from .models import Job, Opciones
from .playlist import ListaInfo, Pista

class ColaDescargas:
    def __init__(self, max_concurrentes: int = 2, on_update=None):
        self._pool = ThreadPoolExecutor(
            max_workers=max_concurrentes, thread_name_prefix="dl"
        )
        self._on_update = on_update or (lambda job: None)
        self.jobs: dict[str, Job] = {}

    def agregar(self, url: str, opciones: Opciones | None = None) -> Job:
        job = Job(url=url, opciones=opciones or Opciones())
        self.jobs[job.id] = job
        self._on_update(job)
        self._pool.submit(descargar, job, self._on_update)
        return job
    
    def agregar_lista(self, lista: ListaInfo, pistas: list[Pista] | None = None,
                      opciones: Opciones | None = None,
                      subcarpeta: bool = True) -> list[Job]:
        """Encola las pistas elegidas (o todas). Cada lista va a su subcarpeta."""
        base = opciones or Opciones()
        if subcarpeta:
            nombre = sanitize_filename(lista.titulo) or "lista"
            base = replace(base, carpeta=str(Path(base.carpeta) / nombre))
        elegidas = lista.pistas if pistas is None else pistas
        return [self.agregar(p.url, base) for p in elegidas]
    
    def cancelar(self, job_id: str) -> None:
        self.jobs[job_id].cancelar.set()

    def cerrar(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)