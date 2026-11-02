from PySide6.QtGui import QColor, QPalette


def _texto_para(c: QColor) -> str:
    return "#111111" if c.lightness() > 140 else "#f0f0f2"


def _rgba(c: QColor, a: int) -> str:
    return f"rgba({c.red()},{c.green()},{c.blue()},{a})"


def _colores(modo: str, fondo: str, acento: str):
    """Devuelve (bg, panel, borde, texto, acento) para el modo dado."""
    ac = QColor(acento)
    if modo == "claro":
        bg, panel, borde = QColor("#f2f3f5"), QColor("#ffffff"), QColor("#cfd2d8")
    elif modo == "color":
        bg = QColor(fondo)
        oscuro = bg.lightness() < 128
        panel = bg.lighter(130) if oscuro else bg.darker(106)
        borde = bg.lighter(175) if oscuro else bg.darker(130)
    elif modo == "imagen":
        # Paneles teñidos con el tono del acento (en vez de un gris fijo)
        h = ac.hslHueF()
        s = 0.0 if h < 0 else 1.0
        h = max(h, 0.0)
        bg = QColor.fromHslF(h, 0.25 * s, 0.10)
        panel = QColor.fromHslF(h, 0.28 * s, 0.17)
        borde = QColor.fromHslF(h, 0.25 * s, 0.32)
    else:  # oscuro
        bg, panel, borde = QColor("#1c1d22"), QColor("#2a2c33"), QColor("#3b3e48")
    return bg, panel, borde, QColor(_texto_para(bg)), ac


def generar_paleta(modo: str, fondo: str, acento: str) -> QPalette:
    """Paleta completa: cubre lo que la hoja de estilos no toca
    (barras de desplazamiento, casillas, tooltips, etc.)."""
    bg, panel, borde, texto, ac = _colores(modo, fondo, acento)
    ac_txt = QColor(_texto_para(ac))
    suave = QColor(texto)
    suave.setAlpha(120)

    p = QPalette()
    R = QPalette.ColorRole
    p.setColor(R.Window, bg)
    p.setColor(R.WindowText, texto)
    p.setColor(R.Base, panel)
    p.setColor(R.AlternateBase, bg)
    p.setColor(R.Text, texto)
    p.setColor(R.Button, panel)
    p.setColor(R.ButtonText, texto)
    p.setColor(R.BrightText, texto)
    p.setColor(R.Highlight, ac)
    p.setColor(R.HighlightedText, ac_txt)
    p.setColor(R.ToolTipBase, panel)
    p.setColor(R.ToolTipText, texto)
    p.setColor(R.PlaceholderText, suave)
    p.setColor(R.Link, ac)
    p.setColor(R.Mid, borde)
    p.setColor(R.Dark, borde)
    p.setColor(R.Light, panel)
    p.setColor(R.Shadow, QColor(0, 0, 0))
    for rol in (R.Text, R.WindowText, R.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, rol, suave)
    return p


def generar_qss(modo: str, fondo: str, acento: str) -> str:
    """modo: 'oscuro' | 'claro' | 'color' | 'imagen'."""
    bg, panel, borde, texto, ac = _colores(modo, fondo, acento)
    ac_txt = _texto_para(ac)
    imagen = modo == "imagen"
    panel_c = _rgba(panel, 175) if imagen else panel.name()
    solido = panel.name()

    ventana = "" if imagen else f"QMainWindow {{ background: {bg.name()}; }}"

    return f"""
{ventana}
QDialog {{ background: {bg.name()}; }}
QWidget {{ color: {texto.name()}; }}
QLineEdit, QComboBox, QListWidget, QTreeView, QTableWidget {{
    background: {panel_c}; border: 1px solid {borde.name()}; border-radius: 6px;
    padding: 4px; selection-background-color: {ac.name()}; selection-color: {ac_txt};
}}
QTreeView, QTableWidget, QListWidget {{ padding: 0; }}
QComboBox QAbstractItemView {{ background: {solido}; }}
QHeaderView::section {{ background: {panel_c}; border: none; padding: 6px; }}
QPushButton {{ background: {panel_c}; border: 1px solid {borde.name()};
    border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {ac.name()}; }}
QPushButton#primario {{ background: {ac.name()}; color: {ac_txt};
    border: none; font-weight: bold; }}
QPushButton:checked {{ border-color: {ac.name()}; color: {ac.name()}; }}
QPushButton:disabled {{ color: rgba({texto.red()},{texto.green()},{texto.blue()},110); }}
QSlider::groove:horizontal {{ height: 4px; background: {borde.name()}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ac.name()}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ac.name()}; width: 12px; height: 12px;
    margin: -5px 0; border-radius: 6px; }}
QProgressBar {{ border: 1px solid {borde.name()}; border-radius: 5px;
    text-align: center; background: {panel_c}; }}
QProgressBar::chunk {{ background: {ac.name()}; border-radius: 4px; }}
QTabWidget::pane {{ border: 1px solid {borde.name()}; border-radius: 8px; }}
QTabBar::tab {{ padding: 8px 18px; background: transparent;
    border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ border-bottom: 2px solid {ac.name()}; }}
QMenu {{ background: {solido}; border: 1px solid {borde.name()}; }}
QMenu::item {{ padding: 6px 22px; }}
QMenu::item:selected {{ background: {ac.name()}; color: {ac_txt}; }}
QToolTip {{ background: {solido}; color: {texto.name()};
    border: 1px solid {borde.name()}; }}
"""
