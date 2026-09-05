# ==========================================
# DERF QUICK PEEK (Glassmorphic Translucent Overlay - PyQt6)
# ==========================================
import os
import sys
import time
import base64
import pyperclip

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from Derf import (
        P, PACKET, ALIEN_COMPRESSION_ENABLED,
        zstd_decompressor, zlib, Session, contacts_load,
        id_bundle, id_fp, feed, vload, norm_identity,
        decrypt_alien_stack, load_sim_bob_session_standalone
    )
except ImportError as e:
    print(f"[!] CRITICAL: Could not import Derf core logic. Ensure Derf.py is in the same folder.\nError: {e}")
    sys.exit(1)

try:
    import keyboard
except Exception:
    keyboard = None

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QGraphicsDropShadowEffect
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QEvent
    from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QLinearGradient, QCursor
    PYQT6_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    PYQT6_AVAILABLE = False
    class QObject: pass
    class pyqtSignal:
        def __init__(self, *a, **k): pass
        def connect(self, *a, **k): pass
        def emit(self, *a, **k): pass
    class QColor:
        def __init__(self, *a, **k): pass

IS_WIN32 = (sys.platform == "win32")

# Glassmorphism Color Palette
GLASS_GRADIENT_TOP = QColor(22, 24, 32, 230)     # Translucent Top
GLASS_GRADIENT_BOT = QColor(10, 11, 16, 245)     # Translucent Bottom
GLASS_BORDER_CYAN  = QColor(0, 240, 255, 180)    # Glowing Cyan Accent Border
GLASS_HIGHLIGHT    = QColor(255, 255, 255, 30)   # Subtle Inner Sheen
TEXT_MAIN          = QColor(229, 226, 225)       # High-contrast crisp text

def clean_ciphertext_input(text):
    if not text: return ""
    import html
    text = html.unescape(text)
    replacements = {
        '’': "'", '‘': "'", '“': '"', '”': '"',
        '–': '-', '—': '-', '\u200b': '', '\u200c': '',
        '\u200d': '', '\ufeff': '', '\u00a0': '', '\r': ''
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.strip()


class PeekCardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 14, 16, 14)

        # Message content box
        self.text_widget = QTextEdit()
        self.text_widget.setReadOnly(True)
        self.text_widget.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #E5E2E1;
                font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
                font-size: 13px;
                font-weight: 500;
                line-height: 1.4;
                border: none;
                selection-background-color: #00F0FF;
                selection-color: #0E0E10;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(255, 255, 255, 0.03);
                width: 3px;
                margin: 0px;
                border-radius: 1px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 240, 255, 0.45);
                min-height: 14px;
                border-radius: 1px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00F0FF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.layout.addWidget(self.text_widget)

        # Auto-hide timer
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

        # Ambient Shadow Effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 240, 255, 35))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        path = QPainterPath()
        path.addRoundedRect(2.0, 2.0, w - 4.0, h - 4.0, 16.0, 16.0)

        # Glassmorphic Gradient Background
        gradient = QLinearGradient(0.0, 0.0, 0.0, h)
        gradient.setColorAt(0.0, GLASS_GRADIENT_TOP)
        gradient.setColorAt(1.0, GLASS_GRADIENT_BOT)
        painter.fillPath(path, gradient)

        # Glass Inner Highlight Sheen
        highlight_path = QPainterPath()
        highlight_path.addRoundedRect(3.0, 3.0, w - 6.0, h - 6.0, 15.0, 15.0)
        painter.setPen(QPen(GLASS_HIGHLIGHT, 1.0))
        painter.drawPath(highlight_path)

        # Glowing Accent Border
        pen = QPen(GLASS_BORDER_CYAN)
        pen.setWidthF(1.5)
        painter.setPen(pen)
        painter.drawPath(path)

    def show_text(self, text, x, y):
        self.text_widget.setPlainText(text)

        screen = QApplication.primaryScreen().geometry()
        screen_w = screen.width()
        screen_h = screen.height()

        # Strict screen-size relative expansion caps
        max_w = min(460, int(screen_w * 0.35))
        max_h = min(280, int(screen_h * 0.30))
        min_w = 260
        min_h = 80

        char_len = len(text)
        est_lines = max(1, char_len // 32 + text.count('\n'))

        req_w = min(max(char_len * 8 + 36, min_w), max_w)
        req_h = min(max(est_lines * 20 + 32, min_h), max_h)

        self.resize(req_w, req_h)

        # Position directly next to mouse cursor
        final_x = min(max(x + 12, 10), screen_w - req_w - 15)
        final_y = min(max(y + 12, 10), screen_h - req_h - 15)

        self.move(final_x, final_y)
        self.show()
        self.raise_()
        self.activateWindow()

        # Reset 12-second auto-hide timer
        self.timer.start(12000)

    def changeEvent(self, event):
        # Auto-close when clicking outside / losing focus
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                self.hide()
        super().changeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class PeekCard(QObject):
    show_signal = pyqtSignal(str, int, int)
    hide_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget = None
        self.show_signal.connect(self._on_show, Qt.ConnectionType.QueuedConnection)
        self.hide_signal.connect(self._on_hide, Qt.ConnectionType.QueuedConnection)

    def _on_show(self, text, x, y):
        if not self.widget:
            self.widget = PeekCardWidget()
        self.widget.show_text(text, x, y)

    def _on_hide(self):
        if self.widget:
            self.widget.hide()

    def show(self, text, x, y):
        self.show_signal.emit(text, int(x), int(y))

    def hide(self):
        self.hide_signal.emit()

    def run(self):
        pass


def decrypt_payload(raw_block):
    try:
        raw_idn = vload(P("lc_identity.json"))
        idn = norm_identity(raw_idn)
        return decrypt_alien_stack(raw_block, idn, custom_session_loader=load_sim_bob_session_standalone)
    except Exception as e:
        print(f"[!] Decryption error: {e}")
        return None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    peek_card = PeekCard()

    def trigger_peek():
        try:
            if keyboard:
                keyboard.send('ctrl+c')
            time.sleep(0.15)

            selected_text = clean_ciphertext_input(pyperclip.paste())
            selected_text = clean_ciphertext_input(selected_text)
            if "DERF:V1:" in selected_text:
                decrypted = decrypt_payload(selected_text)
                if decrypted:
                    pos = QCursor.pos()
                    x, y = pos.x(), pos.y()
                    peek_card.show(decrypted, x, y)
                else:
                    print("[!] Could not decrypt. Wrong session, stale message, or corrupted data.")
            else:
                print("[*] No Derf payload selected.")
        except Exception as e:
            print(f"[!] Peek error: {e}")

    print("=========================================")
    print("  DERF QUICK PEEK GLASS CARD ACTIVE (PyQt6)")
    print("  Highlight text in any app and press:")
    print("  [ Alt + Shift + Q ] to decrypt")
    print("=========================================")

    if keyboard:
        try:
            keyboard.add_hotkey('alt+shift+q', trigger_peek)
        except Exception as e:
            print(f"[!] Hotkey error: {e}")

    sys.exit(app.exec())
