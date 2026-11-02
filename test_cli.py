import sys
import time

from core.models import Estado, Formato, Opciones
from core.queue import ColaDescargas

TERMINALES = {Estado.COMPLETADO, Estado.ERROR, Estado.CANCELADO}


def mostrar(job):
    print(f"[{job.id}] {job.estado.value:<12} {job.progreso:5.1f}%  {job.titulo[:50]}")


cola = ColaDescargas(max_concurrentes=2, on_update=mostrar)
formato = Formato(sys.argv[2]) if len(sys.argv) > 2 else Formato.MP3
job = cola.agregar(sys.argv[1], Opciones(formato=formato))

while job.estado not in TERMINALES:
    time.sleep(0.5)

print("\nArchivo:", job.archivo or "-")
if job.error:
    print("Error:", job.error)
cola.cerrar()