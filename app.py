import html
import os
import random
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

#-------------------------------------------------------------Aura v1.0
# By: Artork
#----------------------------------------------------------------------

from PySide6.QtCore import QDir, QPointF, QRectF, QSettings, QSize, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import (QColor, QDesktopServices, QIcon, QPainter, QPen,
                           QPixmap, QPolygonF)
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QColorDialog, QComboBox,
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QProgressBar,
    QPushButton, QSlider, QStyle, QTableWidget, QTableWidgetItem, QTabWidget,
    QTreeView, QVBoxLayout, QWidget,
)

try:  # en Qt6 vive en QtGui
    from PySide6.QtGui import QFileSystemModel
except ImportError:  # pragma: no cover
    from PySide6.QtWidgets import QFileSystemModel

from yt_dlp.utils import sanitize_filename

from core import tags
from core.models import Estado, Formato, Opciones
from core.playlist import obtener_lista
from core.queue import ColaDescargas
from tema import generar_paleta, generar_qss

TERMINALES = {Estado.COMPLETADO, Estado.ERROR, Estado.CANCELADO}
CFG = QSettings("Aura", "Aura")

# Todo vive dentro de esta carpeta: descargas y biblioteca.
def _carpeta_app() -> Path:
    # Empaquetado con PyInstaller, __file__ apunta a una carpeta interna/temporal:
    # las descargas deben vivir junto al .exe.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


RAIZ = _carpeta_app() / "descargas"
RAIZ.mkdir(exist_ok=True)
RAIZ = RAIZ.resolve()


def ruta_recurso(nombre: str) -> str:
    """Ruta de un archivo de «recursos» (junto a app.py o dentro del paquete
    de PyInstaller). Devuelve "" si no existe."""
    bases = [Path(__file__).resolve().parent]
    if hasattr(sys, "_MEIPASS"):
        bases.insert(0, Path(sys._MEIPASS))
    for base in bases:
        f = base / "recursos" / nombre
        if f.is_file():
            return str(f)
    return ""


def logo_para_tema(modo: str, fondo: str) -> str:
    """Variante del logo con buen contraste sobre el fondo del tema."""
    if modo == "claro":
        return "logo_negro.png"
    if modo == "color":
        return "logo_negro.png" if QColor(fondo).lightness() >= 128 else "logo_blanco.png"
    if modo == "imagen":
        return "logo_gris.png"
    return "logo_blanco.png"          # oscuro


def dentro_de_raiz(ruta) -> bool:
    try:
        Path(ruta).resolve().relative_to(RAIZ)
        return True
    except (ValueError, OSError):
        return False


def sub_a_ruta(sub: str) -> Path:
    """Convierte una subruta relativa en ruta real, siempre dentro de RAIZ."""
    destino = (RAIZ / sub).resolve() if sub else RAIZ
    return destino if dentro_de_raiz(destino) else RAIZ


def nombre_limpio(texto: str) -> str:
    return sanitize_filename(texto.strip(), restricted=False).strip(". ")


def clasificar_url(url: str) -> str:
    """Devuelve 'video', 'lista' o 'mixto' (video dentro de una lista)."""
    p = urlparse(url)
    q = parse_qs(p.query)
    hay_lista = "list" in q
    hay_video = "v" in q or p.netloc.endswith("youtu.be")
    if hay_lista and hay_video:
        return "mixto"
    return "lista" if hay_lista else "video"


def mostrar_en_explorador(ruta: str):
    """Abre el Explorador con el archivo seleccionado (o abre la carpeta)."""
    ruta = os.path.normpath(ruta)
    es_archivo = os.path.isfile(ruta)
    if sys.platform == "win32":
        if es_archivo:
            subprocess.Popen(f'explorer /select,"{ruta}"')
        else:
            os.startfile(ruta)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", ruta] if es_archivo else ["open", ruta])
    else:
        carpeta = os.path.dirname(ruta) if es_archivo else ruta
        QDesktopServices.openUrl(QUrl.fromLocalFile(carpeta))


def fmt_duracion(seg) -> str:
    seg = int(seg or 0)
    return f"{seg // 60}:{seg % 60:02d}" if seg else ""


def fmt_tiempo(ms) -> str:
    seg = max(int(ms or 0), 0) // 1000
    return f"{seg // 60}:{seg % 60:02d}"


def pixmap_icono(nombre: str, color: QColor, lado: int = 20, dpr: float = 2.0) -> QPixmap:
    """Dibuja un icono vectorial (cuadrícula 100x100) del color dado."""
    pm = QPixmap(int(lado * dpr), int(lado * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(lado / 100, lado / 100)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)

    def poli(*pts):
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))

    if nombre == "play":
        poli((30, 14), (30, 86), (86, 50))
    elif nombre == "pause":
        p.drawRoundedRect(QRectF(24, 16, 18, 68), 4, 4)
        p.drawRoundedRect(QRectF(58, 16, 18, 68), 4, 4)
    elif nombre == "stop":
        p.drawRoundedRect(QRectF(22, 22, 56, 56), 6, 6)
    elif nombre == "prev":
        p.drawRoundedRect(QRectF(16, 16, 12, 68), 4, 4)
        poli((84, 16), (84, 84), (32, 50))
    elif nombre == "next":
        p.drawRoundedRect(QRectF(72, 16, 12, 68), 4, 4)
        poli((16, 16), (16, 84), (68, 50))
    elif nombre == "volumen":
        poli((8, 38), (26, 38), (48, 18), (48, 82), (26, 62), (8, 62))
        lapiz = QPen(color, 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(lapiz)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(34, 32, 36, 36), -50 * 16, 100 * 16)
        p.drawArc(QRectF(26, 18, 60, 64), -55 * 16, 110 * 16)
    p.end()
    return pm


def crear_icono(nombre: str, color: QColor, lado: int = 20) -> QIcon:
    ic = QIcon(pixmap_icono(nombre, color, lado))
    apagado = QColor(color)
    apagado.setAlpha(100)
    ic.addPixmap(pixmap_icono(nombre, apagado, lado), QIcon.Mode.Disabled)
    return ic


class SliderSalto(QSlider):
    """Slider horizontal: un clic sobre la barra salta a ese punto."""

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.maximum() > self.minimum():
            v = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), int(e.position().x()), self.width())
            self.setValue(v)
            self.sliderMoved.emit(v)
        super().mousePressEvent(e)


# ------------------------------------------------------------------ dialogos
class SelectorCarpeta(QDialog):
    """Elige una carpeta DENTRO de «descargas» (nunca fuera)."""

    def __init__(self, titulo, actual="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(460, 460)
        self.sub = None

        self.modelo = QFileSystemModel(self)
        self.modelo.setFilter(QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot)
        self.modelo.setRootPath(str(RAIZ))
        self.arbol = QTreeView()
        self.arbol.setModel(self.modelo)
        self.arbol.setRootIndex(self.modelo.index(str(RAIZ)))
        for c in (1, 2, 3):
            self.arbol.hideColumn(c)
        self.arbol.setHeaderHidden(True)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Todo se guarda dentro de «descargas».\n"
                             "Elige una subcarpeta, crea una nueva o usa la raíz."))
        lay.addWidget(self.arbol, 1)

        fila = QHBoxLayout()
        b_nueva = QPushButton("Nueva subcarpeta…")
        b_nueva.clicked.connect(self._nueva)
        b_raiz = QPushButton("Usar «descargas» (raíz)")
        b_raiz.clicked.connect(self._raiz)
        fila.addWidget(b_nueva)
        fila.addWidget(b_raiz)
        fila.addStretch()
        lay.addLayout(fila)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._elegir)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        if actual:
            idx = self.modelo.index(str(sub_a_ruta(actual)))
            if idx.isValid():
                self.arbol.setCurrentIndex(idx)

    def _raiz(self):
        self.sub = ""
        self.accept()

    def _elegir(self):
        idx = self.arbol.currentIndex()
        if not idx.isValid():
            QMessageBox.information(self, "Carpeta",
                                    "Elige una carpeta o pulsa «Usar descargas (raíz)».")
            return
        ruta = Path(self.modelo.filePath(idx))
        if not dentro_de_raiz(ruta):
            return
        self.sub = str(ruta.resolve().relative_to(RAIZ))
        self.accept()

    def _nueva(self):
        nombre, ok = QInputDialog.getText(self, "Nueva subcarpeta", "Nombre:")
        limpio = nombre_limpio(nombre) if ok else ""
        if not limpio:
            return
        padre = self.arbol.currentIndex()
        if not padre.isValid():
            padre = self.modelo.index(str(RAIZ))
        idx = self.modelo.mkdir(padre, limpio)
        if idx.isValid():
            self.arbol.expand(padre)
            self.arbol.setCurrentIndex(idx)
        else:
            QMessageBox.warning(self, "Carpeta", "No se pudo crear (¿ya existe?).")


class SelectorPistas(QDialog):
    def __init__(self, lista, parent=None):
        super().__init__(parent)
        self.lista = lista
        self.setWindowTitle("Elegir canciones")
        self.resize(520, 520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<b>{html.escape(lista.titulo)}</b> — "
                             f"{len(lista.pistas)} canciones"))

        self.lw = QListWidget()
        for p in lista.pistas:
            dur = fmt_duracion(getattr(p, "duracion", 0))
            it = QListWidgetItem(f"{p.titulo}   [{dur}]" if dur else p.titulo)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            self.lw.addItem(it)
        lay.addWidget(self.lw)

        self.lbl_cont = QLabel()
        self.lw.itemChanged.connect(self._contar)
        b1, b2, b3 = QPushButton("Todas"), QPushButton("Ninguna"), QPushButton("Invertir")
        b1.clicked.connect(lambda: self._marcar(Qt.CheckState.Checked))
        b2.clicked.connect(lambda: self._marcar(Qt.CheckState.Unchecked))
        b3.clicked.connect(self._invertir)
        fila = QHBoxLayout()
        for b in (b1, b2, b3):
            fila.addWidget(b)
        fila.addStretch()
        fila.addWidget(self.lbl_cont)
        lay.addLayout(fila)
        self._contar()

        self.chk_sub = QCheckBox("Guardar en una subcarpeta con el nombre de la lista")
        self.chk_sub.setChecked(True)
        lay.addWidget(self.chk_sub)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _contar(self, *_):
        n = sum(self.lw.item(i).checkState() == Qt.CheckState.Checked
                for i in range(self.lw.count()))
        self.lbl_cont.setText(f"{n} de {self.lw.count()} seleccionadas")

    def _invertir(self):
        for i in range(self.lw.count()):
            it = self.lw.item(i)
            it.setCheckState(Qt.CheckState.Unchecked
                             if it.checkState() == Qt.CheckState.Checked
                             else Qt.CheckState.Checked)

    def _marcar(self, estado):
        for i in range(self.lw.count()):
            self.lw.item(i).setCheckState(estado)

    def resultado(self):
        pistas = [self.lista.pistas[i] for i in range(self.lw.count())
                  if self.lw.item(i).checkState() == Qt.CheckState.Checked]
        return pistas, self.chk_sub.isChecked()


class EditorMetadatos(QDialog):
    CAMPOS = (("titulo", "Título"), ("artista", "Artista"), ("album", "Álbum"),
              ("genero", "Género"), ("anio", "Año"))

    def __init__(self, rutas, parent=None):
        super().__init__(parent)
        self.rutas = [Path(r) for r in rutas]
        self.unico = len(self.rutas) == 1
        self.portada_nueva = None
        self.setWindowTitle("Editar metadatos" if self.unico
                            else f"Editar {len(self.rutas)} canciones")
        self.setMinimumWidth(560)

        self.edits = {k: QLineEdit() for k, _ in self.CAMPOS}
        form = QFormLayout()
        for k, etiqueta in self.CAMPOS:
            form.addRow(etiqueta, self.edits[k])

        self.lbl_portada = QLabel("Sin portada")
        self.lbl_portada.setFixedSize(180, 180)
        self.lbl_portada.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_portada.setStyleSheet("border: 1px dashed #888;")
        b_portada = QPushButton("Cambiar portada…")
        b_portada.clicked.connect(self._elegir_portada)
        b_separar = QPushButton("Separar «Artista - Título»")
        b_separar.setEnabled(self.unico)
        b_separar.clicked.connect(self._separar)

        izq = QVBoxLayout()
        izq.addWidget(self.lbl_portada)
        izq.addWidget(b_portada)
        izq.addWidget(b_separar)
        izq.addStretch()

        cuerpo = QHBoxLayout()
        cuerpo.addLayout(izq)
        cuerpo.addLayout(form, 1)

        lay = QVBoxLayout(self)
        if not self.unico:
            lay.addWidget(QLabel(
                f"Editando {len(self.rutas)} canciones a la vez. Solo se cambian "
                "los campos que rellenes; los vacíos se dejan como están."))
        lay.addLayout(cuerpo)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._guardar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        if self.unico:
            self._cargar_uno(self.rutas[0])
        else:
            self._cargar_varios()

    def _cargar_uno(self, ruta):
        try:
            m = tags.leer(ruta)
            for k, _ in self.CAMPOS:
                self.edits[k].setText(getattr(m, k))
            datos = tags.leer_portada(ruta)
            if datos:
                self._mostrar(datos)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Aviso", f"No se pudieron leer las etiquetas:\n{e}")

    def _cargar_varios(self):
        metas = []
        for r in self.rutas:
            try:
                metas.append(tags.leer(r))
            except Exception:  # noqa: BLE001
                pass
        for k, _ in self.CAMPOS:
            valores = {getattr(m, k) for m in metas}
            self.edits[k].setPlaceholderText("(sin cambios)")
            if len(valores) == 1:
                self.edits[k].setText(valores.pop())
            elif len(valores) > 1:
                self.edits[k].setPlaceholderText("(varios valores)")
        self.lbl_portada.setText("Portada\n(sin cambios)")

    def _mostrar(self, datos: bytes):
        pm = QPixmap()
        if pm.loadFromData(datos):
            self.lbl_portada.setPixmap(pm.scaled(
                180, 180, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def _elegir_portada(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Elegir imagen", "", "Imágenes (*.png *.jpg *.jpeg *.webp)")
        if ruta:
            self.portada_nueva = Path(ruta).read_bytes()
            self._mostrar(self.portada_nueva)

    def _separar(self):
        t = self.edits["titulo"].text()
        if " - " in t:
            a, b = t.split(" - ", 1)
            self.edits["artista"].setText(a.strip())
            self.edits["titulo"].setText(b.strip())

    def _guardar(self):
        errores = []
        for r in self.rutas:
            try:
                if self.unico:
                    meta = tags.Metadatos(**{k: self.edits[k].text().strip()
                                             for k, _ in self.CAMPOS})
                else:
                    meta = tags.leer(r)
                    for k, _ in self.CAMPOS:
                        v = self.edits[k].text().strip()
                        if v:
                            setattr(meta, k, v)
                tags.escribir(r, meta)
                if self.portada_nueva:
                    tags.poner_portada(r, self.portada_nueva)
            except Exception as e:  # noqa: BLE001
                errores.append(f"{r.name}: {e}")
        if errores:
            QMessageBox.warning(self, "Algunos archivos fallaron", "\n".join(errores))
        self.accept()


# ------------------------------------------------------------------ ventana
class Ventana(QMainWindow):
    job_cambio = Signal(object)
    lista_lista = Signal(object, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aura")
        self.resize(1100, 720)
        self.fondo_pix = QPixmap()
        self.filas = {}  # job_id -> (item_titulo, item_estado, barra)

        sub = CFG.value("subcarpeta", "") or ""
        self.sub_actual = sub if sub and sub_a_ruta(sub).is_dir() else ""

        self.cola = ColaDescargas(max_concurrentes=2, on_update=self.job_cambio.emit)
        self.job_cambio.connect(self._actualizar_fila)
        self.lista_lista.connect(self._mostrar_selector)

        tabs = QTabWidget()
        tabs.addTab(self._tab_descargar(), "Descargar")
        tabs.addTab(self._tab_biblioteca(), "Biblioteca")
        tabs.addTab(self._tab_apariencia(), "Apariencia")
        self.lbl_logo = QLabel()
        self.lbl_logo.setContentsMargins(0, 0, 8, 0)
        self._logo_actual = ""
        tabs.setCornerWidget(self.lbl_logo, Qt.Corner.TopRightCorner)
        self.setCentralWidget(tabs)
        self.aplicar_tema()

    # ---- fondo con imagen
    def paintEvent(self, e):
        if self.fondo_pix.isNull():
            return super().paintEvent(e)
        p = QPainter(self)
        esc = self.fondo_pix.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap(-(esc.width() - self.width()) // 2,
                     -(esc.height() - self.height()) // 2, esc)
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))

    def closeEvent(self, e):
        self.player.stop()
        self.cola.cerrar()
        super().closeEvent(e)

    # ================================================================ DESCARGAR
    def _tab_descargar(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        fila = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("Pega el enlace de un video o de una lista…")
        self.url.returnPressed.connect(self.agregar)
        b = QPushButton("Agregar")
        b.setObjectName("primario")
        b.clicked.connect(self.agregar)
        fila.addWidget(self.url, 1)
        fila.addWidget(b)
        lay.addLayout(fila)

        opc = QHBoxLayout()
        self.cb_formato = QComboBox()
        for f in Formato:
            self.cb_formato.addItem(f.value.upper(), f)
        self.cb_calidad = QComboBox()
        self.cb_calidad.addItems(["128", "192", "256", "320"])
        self.cb_calidad.setCurrentText("192")
        self.cb_formato.currentIndexChanged.connect(self._sync_calidad)
        self.chk_meta = QCheckBox("Incrustar metadatos y carátula")
        self.chk_meta.setChecked(True)
        opc.addWidget(QLabel("Formato"))
        opc.addWidget(self.cb_formato)
        opc.addWidget(QLabel("Calidad (kbps)"))
        opc.addWidget(self.cb_calidad)
        opc.addWidget(self.chk_meta)
        opc.addStretch()
        lay.addLayout(opc)

        car = QHBoxLayout()
        self.ed_carpeta = QLineEdit()
        self.ed_carpeta.setReadOnly(True)
        bc = QPushButton("Elegir subcarpeta…")
        bc.clicked.connect(self.elegir_carpeta)
        bab = QPushButton("Abrir")
        bab.clicked.connect(lambda: mostrar_en_explorador(self._dir_descarga()))
        car.addWidget(QLabel("Guardar en"))
        car.addWidget(self.ed_carpeta, 1)
        car.addWidget(bc)
        car.addWidget(bab)
        lay.addLayout(car)
        self._refrescar_carpeta()

        self.tabla = QTableWidget(0, 3)
        self.tabla.setHorizontalHeaderLabels(["Título", "Estado", "Progreso"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        h = self.tabla.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(1, 120)
        self.tabla.setColumnWidth(2, 180)
        self.tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabla.customContextMenuRequested.connect(self._menu_tabla)
        self.tabla.cellDoubleClicked.connect(
            lambda fila, _c: self._abrir_ubicacion_job(self._job_de_fila(fila)))
        lay.addWidget(self.tabla, 1)

        bots = QHBoxLayout()
        bcan = QPushButton("Cancelar seleccionados")
        bcan.clicked.connect(self.cancelar_sel)
        blim = QPushButton("Quitar terminados")
        blim.clicked.connect(self.quitar_terminados)
        bots.addWidget(bcan)
        bots.addWidget(blim)
        bots.addStretch()
        lay.addLayout(bots)

        self._sync_calidad()
        return w

    def _sync_calidad(self):
        self.cb_calidad.setEnabled(self.cb_formato.currentData() == Formato.MP3)

    def _refrescar_carpeta(self):
        texto = "descargas"
        if self.sub_actual:
            texto += "/" + self.sub_actual.replace("\\", "/")
        self.ed_carpeta.setText(texto)

    def _dir_descarga(self) -> str:
        d = sub_a_ruta(self.sub_actual)
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def _opciones(self) -> Opciones:
        return Opciones(formato=self.cb_formato.currentData(),
                        calidad=self.cb_calidad.currentText(),
                        carpeta=self._dir_descarga(),
                        metadatos=self.chk_meta.isChecked())

    def elegir_carpeta(self):
        dlg = SelectorCarpeta("Guardar descargas en…", self.sub_actual, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.sub is not None:
            self.sub_actual = dlg.sub
            CFG.setValue("subcarpeta", self.sub_actual)
            self._refrescar_carpeta()

    def agregar(self):
        url = self.url.text().strip()
        if not url:
            return
        self.url.clear()
        tipo = clasificar_url(url)

        if tipo == "mixto":
            m = QMessageBox(self)
            m.setWindowTitle("¿Video o lista?")
            m.setText("Este enlace es de un video que pertenece a una lista.")
            solo = m.addButton("Solo este video", QMessageBox.ButtonRole.AcceptRole)
            toda = m.addButton("Toda la lista", QMessageBox.ButtonRole.ActionRole)
            m.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            m.exec()
            if m.clickedButton() is solo:
                tipo = "video"
            elif m.clickedButton() is toda:
                tipo = "lista"
            else:
                return

        if tipo == "video":
            self.cola.agregar(url, self._opciones())
            return

        self.statusBar().showMessage("Analizando lista…")

        def tarea():
            try:
                lista, err = obtener_lista(url), ""
            except Exception as e:  # noqa: BLE001
                lista, err = None, str(e)
            self.lista_lista.emit(lista, err)

        threading.Thread(target=tarea, daemon=True).start()

    @Slot(object, str)
    def _mostrar_selector(self, lista, err):
        self.statusBar().clearMessage()
        if err or lista is None or not lista.pistas:
            QMessageBox.warning(self, "Lista", err or "La lista está vacía.")
            return
        dlg = SelectorPistas(lista, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pistas, sub = dlg.resultado()
            if pistas:
                self.cola.agregar_lista(lista, pistas, self._opciones(), sub)

    @Slot(object)
    def _actualizar_fila(self, job):
        datos = self.filas.get(job.id)
        if datos is None:
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            it_t, it_e = QTableWidgetItem(), QTableWidgetItem()
            it_t.setData(Qt.ItemDataRole.UserRole, job.id)
            barra = QProgressBar()
            barra.setRange(0, 100)
            self.tabla.setItem(fila, 0, it_t)
            self.tabla.setItem(fila, 1, it_e)
            self.tabla.setCellWidget(fila, 2, barra)
            datos = self.filas[job.id] = (it_t, it_e, barra)
        it_t, it_e, barra = datos
        it_t.setText(job.titulo or job.url)
        it_e.setText(job.estado.value.capitalize())
        it_e.setToolTip(job.error)
        barra.setValue(int(job.progreso))

    def _job_de_fila(self, fila):
        item = self.tabla.item(fila, 0)
        return self.cola.jobs.get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _ruta_job(self, job):
        """Archivo descargado si existe; si no, la carpeta de destino si existe."""
        if job is None:
            return ""
        if job.archivo and os.path.exists(job.archivo):
            return job.archivo
        if os.path.isdir(job.opciones.carpeta):
            return job.opciones.carpeta
        return ""

    def _abrir_ubicacion_job(self, job):
        ruta = self._ruta_job(job)
        if ruta:
            mostrar_en_explorador(ruta)

    def _menu_tabla(self, pos):
        job = self._job_de_fila(self.tabla.rowAt(pos.y()))
        if job is None:
            return
        menu = QMenu(self)
        a = menu.addAction("Abrir ubicación del archivo",
                           lambda: self._abrir_ubicacion_job(job))
        a.setEnabled(bool(self._ruta_job(job)))
        b = menu.addAction("Reproducir", lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(job.archivo)))
        b.setEnabled(bool(job.archivo) and os.path.exists(job.archivo))
        c = menu.addAction("Cancelar", lambda: self.cola.cancelar(job.id))
        c.setEnabled(job.estado not in TERMINALES)
        menu.exec(self.tabla.viewport().mapToGlobal(pos))

    def cancelar_sel(self):
        for fila in {i.row() for i in self.tabla.selectedIndexes()}:
            self.cola.cancelar(self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole))

    def quitar_terminados(self):
        filas = []
        for jid, (it_t, _, _) in list(self.filas.items()):
            if self.cola.jobs[jid].estado in TERMINALES:
                filas.append(self.tabla.row(it_t))
                del self.filas[jid]
        for f in sorted(filas, reverse=True):
            self.tabla.removeRow(f)

    # ================================================================ BIBLIOTECA
    def _tab_biblioteca(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel(f"Biblioteca: <b>{html.escape(str(RAIZ))}</b> "
                             "— todo queda dentro de esta carpeta"))

        # barra de acciones (siempre visible)
        barra = QHBoxLayout()
        self.btn_reproducir = QPushButton("Reproducir")
        self.btn_reproducir.clicked.connect(self._rep_seleccion)
        self.btn_editar = QPushButton("Editar metadatos…")
        self.btn_editar.setObjectName("primario")
        self.btn_editar.clicked.connect(self._editar_sel)
        self.btn_mover = QPushButton("Mover a…")
        self.btn_mover.clicked.connect(self._mover_sel)
        self.btn_nueva = QPushButton("Nueva carpeta…")
        self.btn_nueva.clicked.connect(self._nueva_carpeta_sel)
        self.btn_organizar = QPushButton("Organizar ▾")
        menu_org = QMenu(self)
        menu_org.addAction("Por artista", lambda: self._organizar("artista"))
        menu_org.addAction("Por álbum", lambda: self._organizar("album"))
        menu_org.addAction("Por artista / álbum", lambda: self._organizar("artista_album"))
        self.btn_organizar.setMenu(menu_org)
        self.btn_ubic = QPushButton("Abrir ubicación")
        self.btn_ubic.clicked.connect(self._ubicacion_sel)
        self.btn_elim = QPushButton("Eliminar…")
        self.btn_elim.clicked.connect(self._eliminar_sel)
        for b in (self.btn_reproducir, self.btn_editar, self.btn_mover, self.btn_nueva,
                  self.btn_organizar, self.btn_ubic, self.btn_elim):
            barra.addWidget(b)
        barra.addStretch()
        lay.addLayout(barra)

        # árbol (raíz fija = descargas)
        self.fs = QFileSystemModel(self)
        self.fs.setReadOnly(False)
        self.fs.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot |
                          QDir.Filter.AllDirs)
        self.fs.setNameFilters(["*.mp3", "*.m4a", "*.opus"])
        self.fs.setNameFilterDisables(False)

        self.arbol = QTreeView()
        self.arbol.setModel(self.fs)
        self.arbol.setRootIndex(self.fs.setRootPath(str(RAIZ)))
        for col in (2, 3):
            self.arbol.hideColumn(col)
        self.arbol.setColumnWidth(0, 420)
        self.arbol.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.arbol.setDragEnabled(True)
        self.arbol.setAcceptDrops(True)
        self.arbol.setDropIndicatorShown(True)
        self.arbol.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.arbol.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        self.arbol.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.arbol.customContextMenuRequested.connect(self._menu_arbol)
        self.arbol.doubleClicked.connect(self._abrir)
        self.arbol.selectionModel().selectionChanged.connect(self._sel_cambio)

        # panel de detalles
        self.lbl_cover = QLabel("Sin portada")
        self.lbl_cover.setFixedSize(220, 220)
        self.lbl_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cover.setStyleSheet("border: 1px dashed #888;")
        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        panel = QVBoxLayout()
        panel.addWidget(self.lbl_cover)
        panel.addWidget(self.lbl_info, 1)
        panel_w = QWidget()
        panel_w.setLayout(panel)
        panel_w.setFixedWidth(240)

        cuerpo = QHBoxLayout()
        cuerpo.addWidget(self.arbol, 1)
        cuerpo.addWidget(panel_w)
        lay.addLayout(cuerpo, 1)

        lay.addWidget(self._barra_reproductor())

        lay.addWidget(QLabel("Doble clic en una canción para reproducirla. Selecciona una o "
                             "varias canciones (o carpetas) y pulsa «Editar metadatos». "
                             "Arrastra sobre una carpeta para mover."))
        self._sel_cambio()
        return w

    # ---- utilidades de selección
    def _rutas_sel(self):
        return [self.fs.filePath(i) for i in self.arbol.selectionModel().selectedRows(0)]

    def _audios_de(self, rutas):
        """Canciones de la selección; las carpetas aportan todo su contenido."""
        vistos, salida = set(), []
        for r in rutas:
            p = Path(r)
            candidatos = sorted(p.rglob("*")) if p.is_dir() else [p]
            for f in candidatos:
                if (f.is_file() and f.suffix.lower() in tags.EXT_SOPORTADAS
                        and f not in vistos):
                    vistos.add(f)
                    salida.append(f)
        return salida

    def _sel_cambio(self, *_):
        rutas = self._rutas_sel()
        audios = self._audios_de(rutas)
        self.btn_reproducir.setEnabled(bool(audios))
        self.btn_editar.setEnabled(bool(audios))
        self.btn_editar.setText(f"Editar metadatos ({len(audios)})…" if audios
                                else "Editar metadatos…")
        self.btn_organizar.setEnabled(bool(audios))
        for b in (self.btn_mover, self.btn_ubic, self.btn_elim):
            b.setEnabled(bool(rutas))
        self._mostrar_detalle(audios)

    def _mostrar_detalle(self, audios):
        self.lbl_cover.clear()
        self.lbl_cover.setText("Sin portada")
        if not audios:
            self.lbl_info.setText("Selecciona una canción o una carpeta.")
            return
        if len(audios) > 1:
            self.lbl_info.setText(f"<b>{len(audios)} canciones seleccionadas</b><br>"
                                  "Pulsa «Editar metadatos» para cambiarlas juntas.")
            return
        f = audios[0]
        try:
            m = tags.leer(f)
            datos = tags.leer_portada(f)
        except Exception as e:  # noqa: BLE001
            self.lbl_info.setText(f"No se pudieron leer las etiquetas:<br>{html.escape(str(e))}")
            return

        def v(x):
            return html.escape(x) if x else "<i>—</i>"

        self.lbl_info.setText(
            f"<b>{v(m.titulo)}</b><br>Artista: {v(m.artista)}<br>"
            f"Álbum: {v(m.album)}<br>Género: {v(m.genero)}<br>Año: {v(m.anio)}")
        if datos:
            pm = QPixmap()
            if pm.loadFromData(datos):
                self.lbl_cover.setPixmap(pm.scaled(
                    220, 220, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))

    def _abrir(self, idx):
        ruta = Path(self.fs.filePath(idx))
        if ruta.is_file() and ruta.suffix.lower() in tags.EXT_SOPORTADAS:
            self._rep_desde_doble_clic(ruta)

    # ================================================================ REPRODUCTOR
    def _barra_reproductor(self):
        self.cola_rep = []      # canciones en reproducción (rutas)
        self.pos_rep = -1       # índice de la actual
        self._rep_fallos = 0    # errores seguidos (para no entrar en bucle)

        self.player = QMediaPlayer(self)
        # Sin dispositivo de audio, Qt puede cerrarse al crear la salida:
        # en ese caso el reproductor queda sin sonido pero la app sigue viva.
        self.salida = None
        if not QMediaDevices.defaultAudioOutput().isNull():
            self.salida = QAudioOutput(self)
            self.player.setAudioOutput(self.salida)

        caja = QWidget()
        caja.setObjectName("reproductor")
        lay = QVBoxLayout(caja)
        lay.setContentsMargins(0, 4, 0, 4)

        self.lbl_sonando = QLabel("Nada en reproducción" if self.salida else
                                  "Nada en reproducción — no se detectó dispositivo de audio")
        self.lbl_sonando.setTextFormat(Qt.TextFormat.PlainText)
        lay.addWidget(self.lbl_sonando)

        fila = QHBoxLayout()

        def boton(tip, fn, ancho=40):
            b = QPushButton()
            b.setToolTip(tip)
            b.setFixedWidth(ancho)
            b.setIconSize(QSize(18, 18))
            b.clicked.connect(fn)
            return b

        self.btn_ant = boton("Anterior", self._rep_anterior)
        self.btn_play = boton("Reproducir / pausa", self._rep_toggle)
        self.btn_play.setObjectName("primario")
        self.btn_stop = boton("Detener", self._rep_detener)
        self.btn_sig = boton("Siguiente", lambda: self._rep_siguiente(False))
        self.lbl_vol = QLabel()
        self.lbl_vol.setToolTip("Volumen")
        self.chk_azar = QPushButton("Aleatorio")
        self.chk_azar.setCheckable(True)
        self.chk_rep = QPushButton("Repetir")
        self.chk_rep.setCheckable(True)
        self.chk_azar.setChecked(CFG.value("reproductor/azar", False, type=bool))
        self.chk_rep.setChecked(CFG.value("reproductor/repetir", False, type=bool))
        self.chk_azar.toggled.connect(lambda v: CFG.setValue("reproductor/azar", v))
        self.chk_rep.toggled.connect(lambda v: CFG.setValue("reproductor/repetir", v))

        self.lbl_t = QLabel("0:00")
        self.lbl_dur = QLabel("0:00")
        self.sl_pos = SliderSalto()
        self.sl_pos.setRange(0, 0)
        self.sl_pos.sliderMoved.connect(self.player.setPosition)

        self.sl_vol = SliderSalto()
        self.sl_vol.setRange(0, 100)
        self.sl_vol.setFixedWidth(100)
        self.sl_vol.setToolTip("Volumen")
        self.sl_vol.valueChanged.connect(self._rep_volumen)
        self.sl_vol.setValue(CFG.value("reproductor/volumen", 70, type=int))
        self._rep_volumen(self.sl_vol.value())

        for w in (self.btn_ant, self.btn_play, self.btn_stop, self.btn_sig):
            fila.addWidget(w)
        fila.addWidget(self.lbl_t)
        fila.addWidget(self.sl_pos, 1)
        fila.addWidget(self.lbl_dur)
        fila.addWidget(self.chk_azar)
        fila.addWidget(self.chk_rep)
        fila.addWidget(self.lbl_vol)
        fila.addWidget(self.sl_vol)
        lay.addLayout(fila)

        self.player.positionChanged.connect(self._rep_posicion)
        self.player.durationChanged.connect(self._rep_duracion)
        self.player.playbackStateChanged.connect(self._rep_estado)
        self.player.mediaStatusChanged.connect(self._rep_media)
        self.player.errorOccurred.connect(self._rep_error)
        self._rep_botones()
        self._rep_iconos()
        return caja

    def _rep_iconos(self):
        """(Re)dibuja los iconos con los colores del tema actual."""
        if not hasattr(self, "btn_play"):
            return
        pal = QApplication.palette()
        R = pal.ColorRole
        txt, txt_ac = pal.color(R.ButtonText), pal.color(R.HighlightedText)
        self._ic = {n: crear_icono(n, txt) for n in ("play", "pause", "stop", "prev", "next")}
        self._ic_ac = {n: crear_icono(n, txt_ac) for n in ("play", "pause")}
        self.btn_ant.setIcon(self._ic["prev"])
        self.btn_sig.setIcon(self._ic["next"])
        self.btn_stop.setIcon(self._ic["stop"])
        self.btn_reproducir.setIcon(self._ic["play"])
        self.lbl_vol.setPixmap(pixmap_icono("volumen", txt, 20))
        self._rep_icono_play()

    def _rep_icono_play(self):
        sonando = (self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        self.btn_play.setIcon(self._ic_ac["pause" if sonando else "play"])

    # ---- cola
    def _rep_actual(self):
        if 0 <= self.pos_rep < len(self.cola_rep):
            return self.cola_rep[self.pos_rep]
        return None

    def _rep_poner(self, rutas, inicio=0):
        """Reemplaza la cola y empieza a reproducir desde `inicio`."""
        if not rutas:
            return
        self.cola_rep = [Path(r) for r in rutas]
        self._rep_fallos = 0
        self._rep_cargar(inicio)

    def _rep_cargar(self, i):
        if not 0 <= i < len(self.cola_rep):
            return
        self.pos_rep = i
        ruta = self.cola_rep[i]
        self.player.setSource(QUrl.fromLocalFile(str(ruta)))
        self.player.play()
        self.lbl_sonando.setText(f"({i + 1}/{len(self.cola_rep)})  {self._rep_nombre(ruta)}")
        self._rep_botones()

    @staticmethod
    def _rep_nombre(ruta):
        try:
            m = tags.leer(ruta)
            if m.titulo:
                return f"{m.artista} — {m.titulo}" if m.artista else m.titulo
        except Exception:  # noqa: BLE001
            pass
        return ruta.stem

    def _rep_seleccion(self):
        audios = self._audios_de(self._rutas_sel())
        if audios:
            self._rep_poner(audios, 0)

    def _rep_desde_doble_clic(self, ruta):
        sel = self._audios_de(self._rutas_sel())
        if len(sel) > 1 and ruta in sel:
            self._rep_poner(sel, sel.index(ruta))
            return
        hermanas = sorted((f for f in ruta.parent.iterdir()
                           if f.is_file() and f.suffix.lower() in tags.EXT_SOPORTADAS),
                          key=lambda f: f.name.lower())
        self._rep_poner(hermanas, hermanas.index(ruta) if ruta in hermanas else 0)

    # ---- controles
    def _rep_toggle(self):
        est = self.player.playbackState()
        if est == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self._rep_actual() is not None and not self.player.source().isEmpty():
            if self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                self.player.setPosition(0)
            self.player.play()
        else:
            self._rep_seleccion()

    def _rep_detener(self):
        self.player.stop()

    def _rep_anterior(self):
        if self._rep_actual() is None:
            return
        if self.player.position() > 3000 or self.pos_rep == 0:
            self.player.setPosition(0)
            return
        self._rep_cargar(self.pos_rep - 1)

    def _rep_siguiente(self, auto):
        n = len(self.cola_rep)
        if n == 0:
            return
        if self.chk_azar.isChecked() and n > 1:
            opciones = [i for i in range(n) if i != self.pos_rep]
            self._rep_cargar(random.choice(opciones))
        elif self.pos_rep + 1 < n:
            self._rep_cargar(self.pos_rep + 1)
        elif self.chk_rep.isChecked():
            self._rep_cargar(0)
        elif auto:   # fin de la cola: queda detenido en el inicio de la última
            self.player.setPosition(0)
            self.player.pause()

    def _rep_volumen(self, v):
        if self.salida:
            self.salida.setVolume((v / 100) ** 2)   # curva suave: el oído es logarítmico
        CFG.setValue("reproductor/volumen", v)

    # ---- eventos del reproductor
    def _rep_posicion(self, ms):
        if not self.sl_pos.isSliderDown():
            self.sl_pos.setValue(ms)
        self.lbl_t.setText(fmt_tiempo(ms))

    def _rep_duracion(self, ms):
        self.sl_pos.setRange(0, max(ms, 0))
        self.lbl_dur.setText(fmt_tiempo(ms))

    def _rep_estado(self, est):
        sonando = est == QMediaPlayer.PlaybackState.PlayingState
        self._rep_icono_play()
        if sonando:
            self._rep_fallos = 0

    def _rep_media(self, st):
        if st == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.chk_rep.isChecked() and len(self.cola_rep) == 1:
                self.player.setPosition(0)
                self.player.play()
            else:
                self._rep_siguiente(True)

    def _rep_error(self, _err, texto):
        ruta = self._rep_actual()
        nombre = ruta.name if ruta else ""
        self.statusBar().showMessage(f"No se pudo reproducir {nombre}: {texto}", 6000)
        self._rep_fallos += 1
        if self._rep_fallos < len(self.cola_rep):
            QTimer.singleShot(0, lambda: self._rep_siguiente(True))

    def _rep_botones(self):
        hay = bool(self.cola_rep)
        for b in (self.btn_ant, self.btn_stop, self.btn_sig):
            b.setEnabled(hay)

    def _rep_liberar(self, rutas):
        """Suelta el archivo en reproducción si está afectado por mover/borrar/editar
        (en Windows un archivo abierto no se puede mover ni borrar)."""
        actual = self._rep_actual()
        if actual is None:
            return
        try:
            a = actual.resolve()
            afectado = any(a == Path(r).resolve() or Path(r).resolve() in a.parents
                           for r in rutas)
        except OSError:
            afectado = True
        if afectado:
            self.player.stop()
            self.player.setSource(QUrl())
            self.cola_rep, self.pos_rep = [], -1
            self.lbl_sonando.setText("Nada en reproducción")
            self.sl_pos.setRange(0, 0)
            self.lbl_t.setText("0:00")
            self.lbl_dur.setText("0:00")
            self._rep_botones()

    # ---- acciones
    def _editar_sel(self):
        audios = self._audios_de(self._rutas_sel())
        if audios:
            self._rep_liberar(audios)
            EditorMetadatos(audios, self).exec()
            self._sel_cambio()

    def _mover_sel(self):
        rutas = self._rutas_sel()
        if not rutas:
            return
        dlg = SelectorCarpeta("Mover a…", "", self)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.sub is None:
            return
        destino = sub_a_ruta(dlg.sub)
        self._rep_liberar(rutas)
        fallos = []
        for r in rutas:
            src = Path(r)
            try:
                if src.parent.resolve() == destino:
                    continue
                if src.is_dir() and (destino == src.resolve()
                                     or src.resolve() in destino.parents):
                    fallos.append(f"{src.name}: no se puede mover dentro de sí misma")
                    continue
                final = destino / src.name
                if final.exists():
                    fallos.append(f"{src.name}: ya existe en el destino")
                    continue
                shutil.move(str(src), str(final))
            except Exception as e:  # noqa: BLE001
                fallos.append(f"{src.name}: {e}")
        if fallos:
            QMessageBox.warning(self, "No se pudo mover todo", "\n".join(fallos))

    def _organizar(self, modo):
        audios = self._audios_de(self._rutas_sel())
        if not audios:
            return
        etiqueta = {"artista": "artista", "album": "álbum",
                    "artista_album": "artista y álbum"}[modo]
        r = QMessageBox.question(
            self, "Organizar",
            f"Se moverán {len(audios)} canciones a subcarpetas dentro de «descargas» "
            f"según su {etiqueta}.\n\nLas que no tengan ese dato irán a «Sin artista» "
            "o «Sin álbum». ¿Seguir?")
        if r != QMessageBox.StandardButton.Yes:
            return
        self._rep_liberar(audios)
        fallos = []
        for f in audios:
            try:
                m = tags.leer(f)
                artista = nombre_limpio(m.artista) or "Sin artista"
                album = nombre_limpio(m.album) or "Sin álbum"
                partes = {"artista": [artista], "album": [album],
                          "artista_album": [artista, album]}[modo]
                destino = RAIZ.joinpath(*partes)
                if not dentro_de_raiz(destino):
                    fallos.append(f"{f.name}: nombre de carpeta no válido")
                    continue
                if f.parent.resolve() == destino.resolve():
                    continue
                final = destino / f.name
                if final.exists():
                    fallos.append(f"{f.name}: ya existe en {destino.name}")
                    continue
                destino.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(final))
            except Exception as e:  # noqa: BLE001
                fallos.append(f"{f.name}: {e}")
        if fallos:
            QMessageBox.warning(self, "Algunas canciones no se movieron",
                                "\n".join(fallos))

    def _base_nueva_carpeta(self):
        rutas = self._rutas_sel()
        if len(rutas) == 1:
            p = Path(rutas[0])
            return p if p.is_dir() else p.parent
        return RAIZ

    def _nueva_carpeta_sel(self):
        base = self._base_nueva_carpeta()
        nombre, ok = QInputDialog.getText(
            self, "Nueva carpeta", f"Nombre (se creará dentro de «{base.name}»):")
        limpio = nombre_limpio(nombre) if ok else ""
        if not limpio:
            return
        nueva = base / limpio
        if not dentro_de_raiz(nueva):
            QMessageBox.warning(self, "Carpeta", "Debe quedar dentro de «descargas».")
            return
        nueva.mkdir(exist_ok=True)

    def _ubicacion_sel(self):
        rutas = self._rutas_sel()
        if rutas:
            mostrar_en_explorador(rutas[0])

    def _eliminar_sel(self):
        rutas = self._rutas_sel()
        if not rutas:
            return
        r = QMessageBox.question(
            self, "Eliminar",
            f"Se eliminarán {len(rutas)} elemento(s) de forma PERMANENTE. ¿Seguir?")
        if r != QMessageBox.StandardButton.Yes:
            return
        self._rep_liberar(rutas)
        for ruta in rutas:
            try:
                if not dentro_de_raiz(ruta) or Path(ruta).resolve() == RAIZ:
                    continue
                shutil.rmtree(ruta) if Path(ruta).is_dir() else os.remove(ruta)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "Error", f"{ruta}\n{e}")

    def _menu_arbol(self, pos):
        rutas = self._rutas_sel()
        audios = self._audios_de(rutas)
        menu = QMenu(self)
        if audios:
            menu.addAction("Reproducir", self._rep_seleccion)
            menu.addAction(f"Editar metadatos ({len(audios)})…", self._editar_sel)
            sub = menu.addMenu("Organizar")
            sub.addAction("Por artista", lambda: self._organizar("artista"))
            sub.addAction("Por álbum", lambda: self._organizar("album"))
            sub.addAction("Por artista / álbum", lambda: self._organizar("artista_album"))
        if rutas:
            menu.addAction("Mover a…", self._mover_sel)
        if len(rutas) == 1:
            menu.addAction("Renombrar",
                           lambda: self.arbol.edit(self.arbol.selectionModel()
                                                   .selectedRows(0)[0]))
        menu.addAction("Nueva carpeta…", self._nueva_carpeta_sel)
        if rutas:
            menu.addAction("Abrir ubicación del archivo", self._ubicacion_sel)
        menu.addAction("Abrir carpeta «descargas»",
                       lambda: mostrar_en_explorador(str(RAIZ)))
        if rutas:
            menu.addSeparator()
            menu.addAction("Eliminar…", self._eliminar_sel)
        menu.exec(self.arbol.viewport().mapToGlobal(pos))

    # ================================================================ APARIENCIA
    def _tab_apariencia(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()

        self.cb_tema = QComboBox()
        for etiqueta, clave in (("Oscuro", "oscuro"), ("Claro", "claro"),
                                ("Color personalizado", "color"), ("Imagen", "imagen")):
            self.cb_tema.addItem(etiqueta, clave)
        i = self.cb_tema.findData(CFG.value("tema/modo", "oscuro"))
        self.cb_tema.setCurrentIndex(max(i, 0))
        self.cb_tema.currentIndexChanged.connect(self._cambio_tema)
        form.addRow("Tema", self.cb_tema)

        b_fondo = QPushButton("Color de fondo…")
        b_fondo.clicked.connect(lambda: self._color("tema/fondo", "#2b3a55"))
        b_acento = QPushButton("Color de acento…")
        b_acento.clicked.connect(lambda: self._color("tema/acento", "#4f8cff"))
        b_img = QPushButton("Elegir imagen de fondo…")
        b_img.clicked.connect(self._imagen)
        form.addRow("Modo «Color personalizado»", b_fondo)
        form.addRow("Todos los temas", b_acento)
        form.addRow("Modo «Imagen»", b_img)

        lay.addLayout(form)
        lay.addStretch()
        return w

    def _cambio_tema(self):
        CFG.setValue("tema/modo", self.cb_tema.currentData())
        # Se aplica después de que se cierre la lista desplegable; hacerlo
        # dentro de la señal congela Qt.
        QTimer.singleShot(0, self.aplicar_tema)

    def _color(self, clave, defecto):
        c = QColorDialog.getColor(QColor(CFG.value(clave, defecto)), self)
        if c.isValid():
            CFG.setValue(clave, c.name())
            QTimer.singleShot(0, self.aplicar_tema)

    def _imagen(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Imagen de fondo", "", "Imágenes (*.png *.jpg *.jpeg *.webp)")
        if ruta:
            CFG.setValue("tema/imagen", ruta)
            CFG.setValue("tema/modo", "imagen")
            self.cb_tema.blockSignals(True)
            self.cb_tema.setCurrentIndex(self.cb_tema.findData("imagen"))
            self.cb_tema.blockSignals(False)
            QTimer.singleShot(0, self.aplicar_tema)

    def aplicar_tema(self):
        modo = CFG.value("tema/modo", "oscuro")
        fondo = CFG.value("tema/fondo", "#2b3a55")
        acento = CFG.value("tema/acento", "#4f8cff")
        self.fondo_pix = QPixmap()
        if modo == "imagen":
            self.fondo_pix = QPixmap(CFG.value("tema/imagen", ""))
            if self.fondo_pix.isNull():
                modo = "oscuro"  # aún no hay imagen elegida
        qss = generar_qss(modo, fondo, acento)
        if qss != getattr(self, "_qss_actual", None):
            self._qss_actual = qss
            self.setUpdatesEnabled(False)
            try:
                QApplication.setPalette(generar_paleta(modo, fondo, acento))
                QApplication.instance().setStyleSheet(qss)
            finally:
                self.setUpdatesEnabled(True)
        self._rep_iconos()
        self._actualizar_logo(modo, fondo)
        self.update()

    def _actualizar_logo(self, modo, fondo):
        nombre = logo_para_tema(modo, fondo)
        if nombre == self._logo_actual:
            return
        self._logo_actual = nombre
        ruta = ruta_recurso(nombre)
        pm = QPixmap(ruta) if ruta else QPixmap()
        if pm.isNull():
            self.lbl_logo.clear()
            return
        dpr = self.devicePixelRatioF()
        pm = pm.scaledToHeight(int(34 * dpr), Qt.TransformationMode.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        self.lbl_logo.setPixmap(pm)


if __name__ == "__main__":
    # En Windows, sin esto la barra de tareas agrupa la app bajo el icono de Python.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Aura.app")
        except Exception:  # noqa: BLE001
            pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Icono de la ventana (título) y de la barra de tareas: el violeta se ve
    # bien tanto sobre fondos claros como oscuros.
    _ico = QIcon(ruta_recurso("logo.ico"))
    if _ico.isNull():
        _ico = QIcon(ruta_recurso("logo_violeta.png"))
    if not _ico.isNull():
        app.setWindowIcon(_ico)
    fuente = app.font()
    fuente.setPointSize(10)
    app.setFont(fuente)
    v = Ventana()
    v.show()
    sys.exit(app.exec())
