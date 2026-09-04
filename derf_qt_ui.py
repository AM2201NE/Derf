# ==============================================================================
# DERF POST-QUANTUM MESSENGER — PYQT6 PREMIUM "DIGITAL CURATOR" UI
# Design Tokens & Layout based on Stitch Design System
# ==============================================================================
import os
import sys
import time
import json
import base64
import threading

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QListWidget, QListWidgetItem, QStackedWidget,
    QFrame, QDialog, QMessageBox, QGraphicsDropShadowEffect, QSpinBox, QScrollArea,
    QSplitter, QToolButton
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QBrush

import Derf
import derf_peek

# --- Stitch Design System Tokens ---
COLOR_SURFACE_LOWEST = "#0E0E0E"  # Darkest background
COLOR_CANVAS         = "#131313"  # Primary Stage
COLOR_SURFACE_CARD   = "#1C1B1B"  # Card Panel
COLOR_SURFACE_ELEV   = "#252424"  # Elevated Input / Container
COLOR_CYAN_ACCENT    = "#00F0FF"  # Electric Cyan Accent
COLOR_GREEN_ACTIVE   = "#00E073"  # Active / Paired Green
COLOR_TEXT_MAIN      = "#E5E2E1"  # Crisp high-contrast reading text
COLOR_TEXT_MUTED     = "#9EA2A8"  # Subtitle / secondary text
COLOR_BORDER_GHOST   = "rgba(0, 240, 255, 0.2)" # Subtle accent border

STYLESHEET_STITCH = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {COLOR_CANVAS};
    color: {COLOR_TEXT_MAIN};
    font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
}}

/* Sidebar & Navigation */
#Sidebar {{
    background-color: {COLOR_SURFACE_LOWEST};
    border-right: 1px solid rgba(255, 255, 255, 0.05);
}}

#CardPanel {{
    background-color: {COLOR_SURFACE_CARD};
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}}

#CardPanelElevated {{
    background-color: {COLOR_SURFACE_ELEV};
    border-radius: 12px;
    border: 1px solid {COLOR_BORDER_GHOST};
}}

/* Inputs & Text Area */
QLineEdit, QTextEdit, QSpinBox {{
    background-color: {COLOR_SURFACE_ELEV};
    color: {COLOR_TEXT_MAIN};
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
    selection-background-color: {COLOR_CYAN_ACCENT};
    selection-color: #0E0E0E;
}}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {{
    border: 1px solid {COLOR_CYAN_ACCENT};
}}

/* Buttons */
QPushButton {{
    background-color: {COLOR_CYAN_ACCENT};
    color: #040405;
    font-weight: 700;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
}}

QPushButton:hover {{
    background-color: #33F3FF;
}}

QPushButton:pressed {{
    background-color: #00C8D6;
}}

QPushButton#SecondaryButton {{
    background-color: {COLOR_SURFACE_ELEV};
    color: {COLOR_TEXT_MAIN};
    border: 1px solid rgba(255, 255, 255, 0.1);
}}

QPushButton#SecondaryButton:hover {{
    background-color: #2E2D2D;
    border: 1px solid {COLOR_CYAN_ACCENT};
}}

QPushButton#DangerButton {{
    background-color: rgba(255, 71, 71, 0.15);
    color: #FF4747;
    border: 1px solid rgba(255, 71, 71, 0.3);
}}

QPushButton#DangerButton:hover {{
    background-color: rgba(255, 71, 71, 0.3);
}}

/* Navigation Bar Buttons */
QPushButton#NavPill {{
    background-color: transparent;
    color: {COLOR_TEXT_MUTED};
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 16px;
    text-align: left;
}}

QPushButton#NavPill:hover {{
    background-color: rgba(255, 255, 255, 0.05);
    color: {COLOR_TEXT_MAIN};
}}

QPushButton#NavPillActive {{
    background-color: rgba(0, 240, 255, 0.12);
    color: {COLOR_CYAN_ACCENT};
    font-weight: 700;
    border-radius: 8px;
    padding: 8px 16px;
    text-align: left;
}}

/* Contacts List */
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}

QListWidget::item {{
    background-color: {COLOR_SURFACE_CARD};
    color: {COLOR_TEXT_MAIN};
    border-radius: 10px;
    padding: 10px;
    margin-bottom: 8px;
    border: 1px solid transparent;
}}

QListWidget::item:hover {{
    background-color: {COLOR_SURFACE_ELEV};
    border: 1px solid rgba(0, 240, 255, 0.2);
}}

QListWidget::item:selected {{
    background-color: {COLOR_SURFACE_ELEV};
    border: 1px solid {COLOR_CYAN_ACCENT};
    color: {COLOR_TEXT_MAIN};
}}

/* Scrollbars */
QScrollBar:vertical {{
    border: none;
    background: {COLOR_SURFACE_LOWEST};
    width: 6px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.2);
    min-height: 20px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_CYAN_ACCENT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""


class VaultWindow(QWidget):
    unlocked_signal = pyqtSignal(bytes, str)

    def __init__(self, profile_name="default"):
        super().__init__()
        self.profile_name = profile_name
        self.setWindowTitle("Derf PQ Messenger — Unlock Vault")
        self.setFixedSize(460, 520)
        self.setStyleSheet(STYLESHEET_STITCH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(16)

        # Header Badge
        badge = QLabel("🛡️ POST-QUANTUM VAULT")
        badge.setStyleSheet(f"color: {COLOR_CYAN_ACCENT}; font-weight: bold; font-size: 11px; letter-spacing: 2px;")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(badge)

        title = QLabel("DERF MESSENGER")
        title.setStyleSheet(f"color: {COLOR_TEXT_MAIN}; font-weight: 800; font-size: 26px; letter-spacing: 1px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        prof_lbl = QLabel(f"PROFILE: [{self.profile_name.upper()}]")
        prof_lbl.setStyleSheet(f"color: {COLOR_GREEN_ACTIVE}; font-weight: bold; font-size: 12px;")
        prof_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(prof_lbl)

        layout.addSpacing(10)

        # Passphrase Frame
        card = QFrame()
        card.setObjectName("CardPanel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(14)

        lbl_desc = QLabel("Enter Master Passphrase to unlock private ML-KEM-768 identity keys & sessions.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px; line-height: 1.4;")
        card_layout.addWidget(lbl_desc)

        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pass.setPlaceholderText("Master Passphrase...")
        self.txt_pass.returnPressed.connect(self.do_unlock)
        card_layout.addWidget(self.txt_pass)

        self.btn_unlock = QPushButton("UNLOCK SECURE VAULT")
        self.btn_unlock.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_unlock.clicked.connect(self.do_unlock)
        card_layout.addWidget(self.btn_unlock)

        layout.addWidget(card)

        # Status footer
        self.lbl_status = QLabel("NIST FIPS 203 ML-KEM-768 • Double Ratchet")
        self.lbl_status.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        layout.addStretch()

    def do_unlock(self):
        pw = self.txt_pass.text().strip()
        if not pw:
            QMessageBox.warning(self, "Vault Error", "Passphrase required.")
            return

        try:
            vault_bytes = Derf.derive_vault(pw)
            v_tok = Derf.P(".vault_token")
            id_path = Derf.P("lc_identity.json")

            if os.path.exists(v_tok) and os.path.exists(id_path):
                Derf.VAULT = open(v_tok, "rb").read()
                try:
                    raw_idn = Derf.vload(id_path)
                    idn = Derf.norm_identity(raw_idn)
                except Exception:
                    Derf.VAULT = vault_bytes
                    raw_idn = Derf.vload(id_path)
                    idn = Derf.norm_identity(raw_idn)
                    open(v_tok, "wb").write(vault_bytes)
            else:
                Derf.VAULT = vault_bytes
                open(v_tok, "wb").write(vault_bytes)
                if not os.path.exists(id_path):
                    idn = Derf.make_identity()
                    Derf.vsave(id_path, {"pq_sk": Derf.b64(idn["pq_sk"]), "pq_pk": Derf.b64(idn["pq_pk"])})
                else:
                    raw_idn = Derf.vload(id_path)
                    idn = Derf.norm_identity(raw_idn)

            self.unlocked_signal.emit(vault_bytes, self.profile_name)
            self.close()

        except Exception as e:
            QMessageBox.critical(self, "Unlock Failed", f"Invalid Passphrase or corrupted vault.\nDetails: {e}")


class AddContactDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Contact")
        self.setFixedSize(480, 320)
        self.setStyleSheet(STYLESHEET_STITCH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("➕ Add New Contact")
        title.setStyleSheet(f"color: {COLOR_CYAN_ACCENT}; font-weight: bold; font-size: 16px;")
        layout.addWidget(title)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Contact Handle (e.g. Alice)...")
        layout.addWidget(self.txt_name)

        self.txt_key = QTextEdit()
        self.txt_key.setPlaceholderText("Paste LCAP1- Public Key...")
        self.txt_key.setFixedHeight(110)
        layout.addWidget(self.txt_key)

        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setObjectName("SecondaryButton")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("SAVE CONTACT")
        btn_save.clicked.connect(self.accept)

        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def get_data(self):
        return self.txt_name.text().strip(), self.txt_key.toPlainText().strip()


class DerfMainWindow(QMainWindow):
    def __init__(self, vault_bytes, profile_name="default"):
        super().__init__()
        self.vault_bytes = vault_bytes
        self.profile_name = profile_name
        self.idn = None
        self.selected_peer = None

        self.setWindowTitle(f"Derf PQ Messenger — [{profile_name.upper()}]")
        self.resize(1120, 740)
        self.setStyleSheet(STYLESHEET_STITCH)

        self.init_core_identity()
        self.init_ui()
        self.refresh_contacts()
        self.refresh_profile_keys()

    def init_core_identity(self):
        Derf.VAULT = self.vault_bytes
        id_path = Derf.P("lc_identity.json")
        if os.path.exists(id_path):
            raw_idn = Derf.vload(id_path)
            self.idn = Derf.norm_identity(raw_idn)

    def init_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------- SIDEBAR ----------------
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(280)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(18, 20, 18, 20)
        sb_layout.setSpacing(14)

        # Logo Header
        logo_lbl = QLabel("⚡ DERF MESSENGER")
        logo_lbl.setStyleSheet(f"color: {COLOR_CYAN_ACCENT}; font-weight: 800; font-size: 16px; letter-spacing: 1px;")
        sb_layout.addWidget(logo_lbl)

        sub_lbl = QLabel(f"PROFILE: {self.profile_name.upper()} • ML-KEM-768")
        sub_lbl.setStyleSheet(f"color: {COLOR_GREEN_ACTIVE}; font-weight: bold; font-size: 11px;")
        sb_layout.addWidget(sub_lbl)

        sb_layout.addSpacing(6)

        # Navigation Pills
        nav_box = QVBoxLayout()
        nav_box.setSpacing(4)

        self.nav_btns = {}
        tabs = [
            (0, "💬 Messages & Chat"),
            (1, "🤝 One-Time Pairing"),
            (2, "🛡️ Security Specs"),
            (3, "⚙️ Profile Settings")
        ]

        for idx, label in tabs:
            btn = QPushButton(label)
            btn.setObjectName("NavPillActive" if idx == 0 else "NavPill")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, i=idx: self.switch_view(i))
            nav_box.addWidget(btn)
            self.nav_btns[idx] = btn

        sb_layout.addLayout(nav_box)
        sb_layout.addSpacing(10)

        # Contacts Section Header
        lbl_c_hdr = QLabel("CONTACTS")
        lbl_c_hdr.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-weight: bold; font-size: 11px;")
        sb_layout.addWidget(lbl_c_hdr)

        self.contacts_list = QListWidget()
        self.contacts_list.currentItemChanged.connect(lambda curr, prev: self.on_contact_selected(curr))
        sb_layout.addWidget(self.contacts_list)

        # Sidebar Buttons
        btn_add_c = QPushButton("＋ ADD NEW CONTACT")
        btn_add_c.setObjectName("SecondaryButton")
        btn_add_c.clicked.connect(self.do_add_contact_dialog)
        sb_layout.addWidget(btn_add_c)

        btn_del_c = QPushButton("🗑️ SHRED CONTACT")
        btn_del_c.setObjectName("DangerButton")
        btn_del_c.clicked.connect(self.do_delete_contact)
        sb_layout.addWidget(btn_del_c)

        main_layout.addWidget(sidebar)

        # ---------------- MAIN STAGE ----------------
        self.stage_stack = QStackedWidget()
        self.stage_stack.addWidget(self.build_chat_view())
        self.stage_stack.addWidget(self.build_pair_view())
        self.stage_stack.addWidget(self.build_specs_view())
        self.stage_stack.addWidget(self.build_settings_view())

        main_layout.addWidget(self.stage_stack)
        self.switch_view(0)

    def switch_view(self, index):
        self.stage_stack.setCurrentIndex(index)
        for idx, btn in self.nav_btns.items():
            btn.setObjectName("NavPillActive" if idx == index else "NavPill")
            btn.setStyle(btn.style()) # Force stylesheet update

    # --- VIEW 1: CHAT VIEW ---
    def build_chat_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Chat Header Bar
        hdr_box = QFrame()
        hdr_box.setObjectName("CardPanel")
        hdr_layout = QHBoxLayout(hdr_box)
        hdr_layout.setContentsMargins(16, 12, 16, 12)

        self.lbl_chat_contact = QLabel("Select a contact to start messaging")
        self.lbl_chat_contact.setStyleSheet(f"color: {COLOR_TEXT_MAIN}; font-weight: bold; font-size: 15px;")
        hdr_layout.addWidget(self.lbl_chat_contact)

        hdr_layout.addStretch()

        self.lbl_chat_fp = QLabel("")
        self.lbl_chat_fp.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
        hdr_layout.addWidget(self.lbl_chat_fp)

        layout.addWidget(hdr_box)

        # Chat Display History
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        # Decrypt Received Ciphertext Panel
        dec_box = QFrame()
        dec_box.setObjectName("CardPanel")
        dec_layout = QVBoxLayout(dec_box)
        dec_layout.setContentsMargins(12, 10, 12, 10)
        dec_layout.setSpacing(8)

        lbl_dec = QLabel("🔓 Decrypt Received Message Packet:")
        lbl_dec.setStyleSheet(f"color: {COLOR_CYAN_ACCENT}; font-weight: bold; font-size: 12px;")
        dec_layout.addWidget(lbl_dec)

        dec_row = QHBoxLayout()
        self.txt_dec_in = QLineEdit()
        self.txt_dec_in.setPlaceholderText("Paste received DERF:V1: packet here to decrypt...")
        self.txt_dec_in.returnPressed.connect(self.do_decrypt_message)
        dec_row.addWidget(self.txt_dec_in)

        btn_dec_paste = QPushButton("PASTE & DECRYPT")
        btn_dec_paste.setObjectName("SecondaryButton")
        btn_dec_paste.clicked.connect(self.do_decrypt_message)
        dec_row.addWidget(btn_dec_paste)

        dec_layout.addLayout(dec_row)
        layout.addWidget(dec_box)

        # Encrypt & Send Outgoing Message Panel
        input_box = QHBoxLayout()
        self.txt_msg = QLineEdit()
        self.txt_msg.setPlaceholderText("Type plaintext message to encrypt & send...")
        self.txt_msg.returnPressed.connect(self.do_send_message)
        input_box.addWidget(self.txt_msg)

        btn_send = QPushButton("ENCRYPT & SEND")
        btn_send.clicked.connect(self.do_send_message)
        input_box.addWidget(btn_send)

        layout.addLayout(input_box)
        return page

    # --- VIEW 2: PAIRING VIEW ---
    def build_pair_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        hdr = QLabel("🤝 ONE-TIME PAIRING WIZARD")
        hdr.setStyleSheet(f"color: {COLOR_CYAN_ACCENT}; font-weight: bold; font-size: 16px;")
        layout.addWidget(hdr)

        card = QFrame()
        card.setObjectName("CardPanel")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 20, 20, 20)
        c_layout.setSpacing(14)

        lbl_step1 = QLabel("Step 1: Initiator — Generate & Send Invite Payload")
        lbl_step1.setStyleSheet(f"font-weight: bold; color: {COLOR_TEXT_MAIN}; font-size: 13px;")
        c_layout.addWidget(lbl_step1)

        self.txt_invite_out = QTextEdit()
        self.txt_invite_out.setFixedHeight(80)
        self.txt_invite_out.setPlaceholderText("Click 'Generate Invite' to create an ML-KEM-768 invite payload for the selected contact...")
        c_layout.addWidget(self.txt_invite_out)

        btn_gen_inv = QPushButton("GENERATE & COPY INVITE")
        btn_gen_inv.clicked.connect(self.do_generate_invite)
        c_layout.addWidget(btn_gen_inv)

        c_layout.addSpacing(10)

        lbl_step2 = QLabel("Step 2: Responder — Process Invite / Paste Reply")
        lbl_step2.setStyleSheet(f"font-weight: bold; color: {COLOR_TEXT_MAIN}; font-size: 13px;")
        c_layout.addWidget(lbl_step2)

        self.txt_reply_in = QTextEdit()
        self.txt_reply_in.setFixedHeight(80)
        self.txt_reply_in.setPlaceholderText("Paste received invite or reply payload here...")
        c_layout.addWidget(self.txt_reply_in)

        btn_proc_reply = QPushButton("PROCESS PAYLOAD / COMPLETE PAIRING")
        btn_proc_reply.clicked.connect(self.do_process_reply)
        c_layout.addWidget(btn_proc_reply)

        layout.addWidget(card)
        layout.addStretch()
        return page

    # --- VIEW 3: SPECS VIEW ---
    def build_specs_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        hdr = QLabel("🛡️ POST-QUANTUM SECURITY SPECIFICATIONS")
        hdr.setStyleSheet(f"color: {COLOR_CYAN_ACCENT}; font-weight: bold; font-size: 16px;")
        layout.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(12)

        specs = [
            ("NIST ML-KEM-768 (Kyber768)", "Derf uses NIST FIPS 203 ML-KEM-768 post-quantum key encapsulation. Handshakes resist quantum attacks running Shor's algorithm."),
            ("LC-AEAD Chained Encryption", "Per-letter chained ChaCha20-Poly1305 AEAD structure ensures payload integrity, message ordering, and truncation rejection."),
            ("Deniable Double Ratchet", "Axolotl-style double ratchet with per-message ephemeral key replacement provides complete Forward Secrecy and Post-Compromise Security."),
            ("Uniform Size Dummy Masking", "All ciphertext packets are padded to fixed uniform bucket sizes to prevent packet length traffic analysis.")
        ]

        for title, desc in specs:
            card = QFrame()
            card.setObjectName("CardPanel")
            l = QVBoxLayout(card)
            l.setContentsMargins(16, 14, 16, 14)
            l.setSpacing(6)

            t = QLabel(f"⚡ {title}")
            t.setStyleSheet(f"color: {COLOR_CYAN_ACCENT}; font-weight: bold; font-size: 13px;")
            l.addWidget(t)

            d = QLabel(desc)
            d.setWordWrap(True)
            d.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px; line-height: 1.4;")
            l.addWidget(d)

            c_layout.addWidget(card)

        scroll.setWidget(container)
        layout.addWidget(scroll)
        return page

    # --- VIEW 4: SETTINGS VIEW ---
    def build_settings_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        hdr = QLabel("⚙️ PROFILE & SECURITY SETTINGS")
        hdr.setStyleSheet(f"color: {COLOR_CYAN_ACCENT}; font-weight: bold; font-size: 16px;")
        layout.addWidget(hdr)

        card = QFrame()
        card.setObjectName("CardPanel")
        l = QVBoxLayout(card)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(12)

        lbl_pk = QLabel("Your LCAP1- Public Key (Share with contacts to pair):")
        lbl_pk.setStyleSheet(f"font-weight: bold; color: {COLOR_TEXT_MAIN}; font-size: 12px;")
        l.addWidget(lbl_pk)

        self.txt_my_pk = QTextEdit()
        self.txt_my_pk.setFixedHeight(70)
        self.txt_my_pk.setReadOnly(True)
        l.addWidget(self.txt_my_pk)

        btn_copy_pk = QPushButton("COPY MY PUBLIC KEY")
        btn_copy_pk.setObjectName("SecondaryButton")
        btn_copy_pk.clicked.connect(self.do_copy_my_pk)
        l.addWidget(btn_copy_pk)

        l.addSpacing(10)

        # Freshness Window Sync Config
        lbl_fresh = QLabel("Freshness Tolerance Window (Seconds):")
        lbl_fresh.setStyleSheet(f"font-weight: bold; color: {COLOR_TEXT_MAIN}; font-size: 12px;")
        l.addWidget(lbl_fresh)

        fresh_box = QHBoxLayout()
        self.spin_fresh = QSpinBox()
        self.spin_fresh.setRange(60, 86400)
        self.spin_fresh.setValue(int(Derf.FRESH))
        fresh_box.addWidget(self.spin_fresh)

        btn_save_fresh = QPushButton("SAVE TOLERANCE WINDOW")
        btn_save_fresh.clicked.connect(self.do_save_freshness)
        fresh_box.addWidget(btn_save_fresh)
        l.addLayout(fresh_box)

        layout.addWidget(card)
        layout.addStretch()
        return page

    # --- CONTROLLER LOGIC ---
    def refresh_contacts(self):
        self.contacts_list.clear()
        contacts = Derf.contacts_load()
        for name, key_bytes in contacts.items():
            sess_file = Derf.P(f"lc_session_{name}.json")
            paired = os.path.exists(sess_file)
            status = "PAIRED" if paired else "UNPAIRED"
            fp = Derf.id_fp(key_bytes).hex()[:12]

            item = QListWidgetItem(f"👤 {name} [{status}]\n   FP: {fp}...")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.contacts_list.addItem(item)

        if self.contacts_list.count() > 0:
            self.contacts_list.setCurrentRow(0)
            self.on_contact_selected(self.contacts_list.currentItem())

    def refresh_profile_keys(self):
        if self.idn and "pq_pk" in self.idn:
            pk_str = Derf.b64(Derf.id_bundle(self.idn))
            self.txt_my_pk.setPlainText(pk_str)

    def on_contact_selected(self, item):
        if not item: return
        name = item.data(Qt.ItemDataRole.UserRole)
        self.selected_peer = name
        contacts = Derf.contacts_load()
        if name in contacts:
            fp = Derf.id_fp(contacts[name]).hex()
            self.lbl_chat_contact.setText(f"💬 Chatting with {name}")
            self.lbl_chat_fp.setText(f"FP: {fp[:16]}...")

    def do_add_contact_dialog(self):
        dlg = AddContactDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, raw_key = dlg.get_data()
            if not name or not raw_key:
                QMessageBox.warning(self, "Add Error", "Provide both Handle and Key.")
                return
            try:
                pub_b = Derf.parse_pubkey(raw_key)
                Derf.contact_add(name, pub_b)
                self.refresh_contacts()
                QMessageBox.information(self, "Contact Saved", f"Saved contact '{name}'. You can now pair!")
            except Exception as e:
                QMessageBox.critical(self, "Invalid Key", str(e))

    def do_delete_contact(self):
        if not self.selected_peer:
            QMessageBox.warning(self, "Selection Required", "Select a contact to delete.")
            return

        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete contact '{self.selected_peer}' and shred all associated session keys?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            Derf.contact_delete(self.selected_peer)
            self.selected_peer = None
            self.refresh_contacts()
            self.chat_display.clear()
            QMessageBox.information(self, "Deleted", "Contact and session keys shredded.")

    def do_decrypt_message(self):
        raw_in = self.txt_dec_in.text().strip()
        if not raw_in:
            raw_in = Derf.safe_paste().strip()
            self.txt_dec_in.setText(raw_in)

        if not raw_in or "DERF:V1:" not in raw_in:
            QMessageBox.warning(self, "Invalid Packet", "Paste a valid DERF:V1: ciphertext packet first.")
            return

        try:
            decrypted = Derf.decrypt_alien_stack(raw_in, self.idn, custom_session_loader=Derf.load_sim_bob_session_standalone)
            if decrypted:
                peer_lbl = self.selected_peer or "Peer"
                self.chat_display.append(f"<font color='{COLOR_GREEN_ACTIVE}'><b>{peer_lbl}:</b></font> <font color='{COLOR_TEXT_MAIN}'>{decrypted}</font>")
                self.txt_dec_in.clear()
            else:
                QMessageBox.critical(self, "Decryption Failed", "Could not decrypt message packet. Wrong key, stale message, or corrupted payload.")
        except Exception as e:
            QMessageBox.critical(self, "Decryption Error", str(e))

    def do_send_message(self):
        msg = self.txt_msg.text().strip()
        if not msg: return
        if not self.selected_peer:
            QMessageBox.warning(self, "No Contact", "Select a contact from sidebar first.")
            return

        try:
            cipher_text = Derf.encrypt_alien_stack(msg, self.selected_peer, self.idn)
            if cipher_text:
                Derf.safe_copy(cipher_text)
                self.chat_display.append(f"<font color='{COLOR_TEXT_MUTED}'><b>Me:</b></font> <font color='{COLOR_TEXT_MAIN}'>{msg}</font>")
                self.chat_display.append(f"<font color='{COLOR_CYAN_ACCENT}'><i>[Ciphertext generated & copied to clipboard!]</i></font>\n")
                self.txt_msg.clear()
            else:
                QMessageBox.critical(self, "Encryption Error", f"Failed to encrypt for {self.selected_peer}. Perform key exchange/pairing first.")
        except Exception as e:
            QMessageBox.critical(self, "Encryption Error", str(e))

    def do_generate_invite(self):
        if not self.selected_peer:
            QMessageBox.warning(self, "No Contact Selected", "Select a contact from the sidebar first.")
            return

        contacts = Derf.contacts_load()
        if self.selected_peer not in contacts: return

        try:
            req_blob, pend = Derf.hs_req(self.idn, contacts[self.selected_peer])
            Derf.vsave(Derf.P(f"lc_pending_{self.selected_peer}.json"), pend)
            inv_b64 = Derf.b64(req_blob)
            self.txt_invite_out.setPlainText(inv_b64)
            Derf.safe_copy(inv_b64)
            QMessageBox.information(self, "Invite Created", f"Invite generated & copied to clipboard! Send this payload to {self.selected_peer}.")
        except Exception as e:
            QMessageBox.critical(self, "Invite Error", str(e))

    def do_process_reply(self):
        if not self.selected_peer:
            QMessageBox.warning(self, "No Contact Selected", "Select a contact from the sidebar first.")
            return

        raw_in = self.txt_reply_in.toPlainText().strip()
        if not raw_in:
            QMessageBox.warning(self, "Input Required", "Paste responder reply or initiator invite payload.")
            return

        try:
            p_file = Derf.P(f"lc_pending_{self.selected_peer}.json")
            if os.path.exists(p_file):
                # We are Initiator, processing responder reply
                pend = Derf.vload(p_file)
                sess = Derf.hs_complete(self.idn, pend, Derf.ub64(Derf.clean_b64(raw_in)))
                sess.save(self.selected_peer)
                os.remove(p_file)
                QMessageBox.information(self, "PAIRED!", f"Successfully completed pairing with {self.selected_peer}!")
            else:
                # We are Responder, processing initiator invite
                rsp_blob, sess = Derf.hs_rsp(self.idn, Derf.ub64(Derf.clean_b64(raw_in)))
                sess.save(self.selected_peer)
                reply_b64 = Derf.b64(rsp_blob)
                self.txt_invite_out.setPlainText(reply_b64)
                Derf.safe_copy(reply_b64)
                QMessageBox.information(self, "Reply Generated", f"Reply generated & copied! Send this back to {self.selected_peer} to finish pairing.")

            self.refresh_contacts()
        except Exception as e:
            QMessageBox.critical(self, "Pairing Error", str(e))

    def do_copy_my_pk(self):
        pk = self.txt_my_pk.toPlainText().strip()
        if pk:
            Derf.safe_copy(pk)
            QMessageBox.information(self, "Copied", "Your Public Key was copied to clipboard!")

    def do_save_freshness(self):
        val = self.spin_fresh.value()
        Derf.FRESH = float(val)
        with open(Derf.P("lc_fresh.json"), "w") as f:
            json.dump({"fresh": val}, f)
        QMessageBox.information(self, "Saved", f"Freshness tolerance window set to {val} seconds.")


def launch_pyqt_app(profile_name="default"):
    if Derf.PQ_KEM is None:
        try:
            Derf.PQ_KEM = Derf._load_pq()
        except Exception as e:
            print(f"FATAL: Could not load ML-KEM-768 backend: {e}")

    app = QApplication(sys.argv)

    main_win = None

    def on_vault_unlocked(vault_bytes, prof_name):
        nonlocal main_win
        main_win = DerfMainWindow(vault_bytes, prof_name)
        main_win.show()

        class AppRefMock:
            def __init__(self, idn, win):
                self.idn = idn
                self.main_screen = win

        app_ref = AppRefMock(main_win.idn, main_win)
        Derf.start_integrated_background_service(app_ref)

    vault_win = VaultWindow(profile_name)
    vault_win.unlocked_signal.connect(on_vault_unlocked)
    vault_win.show()

    return app.exec()

if __name__ == "__main__":
    sys.exit(launch_pyqt_app("default"))
