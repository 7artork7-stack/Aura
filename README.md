# Aura

Aplicación de escritorio para descargar audio de YouTube y organizar tu música, con reproductor integrado.

## Qué hace

- Descarga el audio de un video o de una lista de reproducción, con selección de canciones.
- Formatos: MP3 (con calidad a elegir), M4A, Opus u original.
- Incrusta etiquetas y carátula en los archivos.
- **Biblioteca:** editar metadatos (uno o varios archivos a la vez), mover, renombrar, eliminar y organizar por artista o álbum.
- **Reproductor integrado:** reproducir/pausa, anterior/siguiente, barra de progreso, volumen, aleatorio y repetir.
- Temas: oscuro, claro, color personalizado o imagen de fondo.

## Instalación (Windows)

Descarga `Aura-Setup.exe` desde la sección **Releases** y ejecútalo. No necesitas instalar nada más.

## Ejecutar desde el código

Requiere Python 3.10 o superior y [ffmpeg](https://ffmpeg.org/) (`ffmpeg` y `ffprobe`) disponible en el PATH, o colocado junto a `app.py` o en una subcarpeta `ffmpeg/`.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Las descargas se guardan en la carpeta `descargas/`, junto a la app.

## Crear el .exe

```
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "Aura" --icon recursos\logo.ico --add-data "recursos;recursos" app.py
```

Copia `ffmpeg.exe` y `ffprobe.exe` dentro de `dist\Aura\`. El instalador se genera con Inno Setup a partir de `aura.iss`.

## Créditos

Usa [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org/), [PySide6](https://doc.qt.io/qtforpython/) y [mutagen](https://mutagen.readthedocs.io/).
