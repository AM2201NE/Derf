# ==========================================
# DERF QUICK PEEK (Glass Overlay - PyQt6 Thread-Safe)
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

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont, QCursor

IS_WIN32 = (sys.platform == "win32")

BG_OBSIDIAN = QColor(14, 14, 18, 248)      # Glass Obsidian Backdrop
CYAN_PRIMARY = QColor(0, 240, 255)         # Electric Cyan Accent
TEXT_MAIN = QColor(238, 240, 248)          # Main text

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
        self.layout.setContentsMargins(16, 12, 16, 12)

        # Header bar
        self.hdr_layout = QHBoxLayout()
        self.hdr_layout.setContentsMargins(0, 0, 0, 6)

        self.lbl_title = QLabel("⚡ QUICK PEEK DECRYPT")
        self.lbl_title.setStyleSheet("color: #00F0FF; font-weight: 800; font-size: 11px; letter-spacing: 1px;")
        self.hdr_layout.addWidget(self.lbl_title)
        self.hdr_layout.addStretch()

        self.btn_close = QPushButton("×")
        self.btn_close.setFixedSize(18, 18)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("QPushButton { color: #8E8E93; background: transparent; border: none; font-size: 15px; font-weight: bold; } QPushButton:hover { color: #00F0FF; }")
        self.btn_close.clicked.connect(self.hide)
        self.hdr_layout.addWidget(self.btn_close)

        self.layout.addLayout(self.hdr_layout)

        # Message content box
        self.text_widget = QTextEdit()
        self.text_widget.setReadOnly(True)
        self.text_widget.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #E5E2E1;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 13px;
                font-weight: 500;
                border: none;
                selection-background-color: #00F0FF;
                selection-color: #0E0E10;
            }
            QScrollBar:vertical {
                border: none;
                background: #181A22;
                width: 4px;
                margin: 0px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: #00F0FF;
                min-height: 16px;
                border-radius: 2px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.layout.addWidget(self.text_widget)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(2.0, 2.0, self.width() - 4.0, self.height() - 4.0, 14.0, 14.0)

        # Obsidian Translucent Fill
        painter.fillPath(path, BG_OBSIDIAN)

        # Electric Cyan Subtle Border
        pen = QPen(CYAN_PRIMARY)
        pen.setWidthF(1.5)
        painter.setPen(pen)
        painter.drawPath(path)

    def show_text(self, text, x, y):
        self.text_widget.setPlainText(text)

        screen = QApplication.primaryScreen().geometry()
        screen_w = screen.width()
        screen_h = screen.height()

        max_w = min(520, int(screen_w * 0.45))
        max_h = min(380, int(screen_h * 0.45))
        min_w = 280
        min_h = 100

        char_len = len(text)
        est_lines = max(1, char_len // 32 + text.count('\n'))

        req_w = min(max(char_len * 9 + 48, min_w), max_w)
        req_h = min(max(est_lines * 22 + 48, min_h), max_h)

        self.resize(req_w, req_h)

        # Position overlay right next to the cursor
        final_x = min(max(x + 12, 10), screen_w - req_w - 15)
        final_y = min(max(y + 12, 10), screen_h - req_h - 15)

        self.move(final_x, final_y)
        self.show()
        self.raise_()
        self.activateWindow()

        # Reset 10-second auto hide timer
        self.timer.start(10000)

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
