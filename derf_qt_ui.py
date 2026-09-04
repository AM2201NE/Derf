# ==============================================================================
# DERF PYQT6 HIGH-END PREMIUM UI & UX MODULE (Stitch "Digital Curator" Design)
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
    QFrame, QDialog, QMessageBox, QGraphicsDropShadowEffect, QSpinBox, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QBrush

import Derf
import derf_peek

# --- Stitch Design System Color Tokens ---
COLOR_BG_OBSIDIAN = QColor("#0E0E10")      # Deep Backdrop
COLOR_BG_SIDEBAR  = QColor("#131418")      # Navigation Sidebar
COLOR_SURFACE_CARD = QColor("#1F2129")     # Glass/Card Container
COLOR_SURFACE_ALT  = QColor("#292C38")     # Alternate Surface
COLOR_CYAN_PRIMARY = QColor("#00F0FF")     # Electric Cyan Accent
COLOR_TEXT_MAIN    = QColor("#EEF0F8")     # Bright Text
COLOR_TEXT_MUTED   = QColor("#858FA6")     # Muted Subtext
COLOR_GREEN_NEON   = QColor("#00E073")     # Active Green
COLOR_RED_DANGER   = QColor("#FF4747")     # Danger Red

STYLESHEET_PREMIUM = """
QMainWindow {
    background-color: #0E0E10;
}
QWidget {
    font-family: 'Segoe UI', 'SF Pro Text', 'Inter', sans-serif;
    color: #EEF0F8;
}
QFrame#Sidebar {
    background-color: #131418;
    border-right: 1px solid #1F2129;
}
QFrame#CardPanel {
    background-color: #1F2129;
    border-radius: 12px;
    border: 1px solid #292C38;
}
QLineEdit, QTextEdit {
    background-color: #131418;
    color: #00F0FF;
    border: 1px solid #292C38;
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
    selection-background-color: #00F0FF;
    selection-color: #0E0E10;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #00F0FF;
}
QPushButton {
    background-color: #00F0FF;
    color: #0E0E10;
    font-weight: bold;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 13px;
    border: none;
}
QPushButton:hover {
    background-color: #5CFFFA;
}
QPushButton:pressed {
    background-color: #00C8D6;
}
QPushButton#SecondaryButton {
    background-color: #1F2129;
    color: #EEF0F8;
    border: 1px solid #292C38;
}
QPushButton#SecondaryButton:hover {
    background-color: #292C38;
    border: 1px solid #00F0FF;
    color: #00F0FF;
}
QPushButton#DangerButton {
    background-color: #292C38;
    color: #FF4747;
    border: 1px solid #FF4747;
}
QPushButton#DangerButton:hover {
    background-color: #FF4747;
    color: #FFFFFF;
}
QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget::item {
    background-color: #1F2129;
    color: #EEF0F8;
    border-radius: 8px;
    padding: 10px;
    margin-bottom: 6px;
    border: 1px solid transparent;
}
QListWidget::item:selected {
    background-color: #292C38;
    color: #00F0FF;
    border: 1px solid #00F0FF;
}
QListWidget::item:hover {
    background-color: #252833;
}
QScrollBar:vertical {
    border: none;
    background: #131418;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #00F0FF;
    min-height: 20px;
    border-radius: 3px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


class VaultWindow(QWidget):
    unlocked_signal = pyqtSignal(bytes, str)

    def __init__(self, profile_name="default"):
        super().__init__()
        self.profile_name = profile_name
        self.setWindowTitle("Derf PQ Messenger — Secure Vault")
        self.setFixedSize(480, 560)
        self.setStyleSheet(STYLESHEET_PREMIUM)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 40, 36, 40)
        layout.setSpacing(16)

        # Header Badge
        badge = QLabel("🛡️ POST-QUANTUM AEAD VAULT")
        badge.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px; letter-spacing: 2px;")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(badge)

        title = QLabel("DERF MESSENGER")
        title.setStyleSheet("color: #EEF0F8; font-weight: 800; font-size: 24px; letter-spacing: 1px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        prof_lbl = QLabel(f"PROFILE: [{self.profile_name.upper()}]")
        prof_lbl.setStyleSheet("color: #00E073; font-weight: bold; font-size: 12px;")
        prof_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(prof_lbl)

        layout.addSpacing(10)

        # Passphrase Frame
        card = QFrame()
        card.setObjectName("CardPanel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)

        lbl_desc = QLabel("Enter Vault Passphrase to unlock private ML-KEM keys and ratchet sessions.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #858FA6; font-size: 12px;")
        card_layout.addWidget(lbl_desc)

        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pass.setPlaceholderText("Vault Passphrase...")
        self.txt_pass.returnPressed.connect(self.do_unlock)
        card_layout.addWidget(self.txt_pass)

        self.btn_unlock = QPushButton("UNLOCK SECURE VAULT")
        self.btn_unlock.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_unlock.clicked.connect(self.do_unlock)
        card_layout.addWidget(self.btn_unlock)

        layout.addWidget(card)

        # Status footer
        self.lbl_status = QLabel("Derf Core v1.0.0 • ML-KEM-768 Active")
        self.lbl_status.setStyleSheet("color: #858FA6; font-size: 11px;")
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

            # Verify existing identity or initialize fresh
            id_path = Derf.P("lc_identity.json")
            if os.path.exists(v_tok) and os.path.exists(id_path):
                Derf.VAULT = open(v_tok, "rb").read()
                try:
                    raw_idn = Derf.vload(id_path)
                    idn = Derf.norm_identity(raw_idn)
                except Exception:
                    # Test if user provided correct passphrase for stored token
                    Derf.VAULT = vault_bytes
                    raw_idn = Derf.vload(id_path)
                    idn = Derf.norm_identity(raw_idn)
                    open(v_tok, "wb").write(vault_bytes)
            else:
                Derf.VAULT = vault_bytes
                open(v_tok, "wb").write(vault_bytes)
                if not os.path.exists(id_path):
                    idn = Derf.make_identity()
                    Derf.vsave(id_path, idn)
                else:
                    raw_idn = Derf.vload(id_path)
                    idn = Derf.norm_identity(raw_idn)

            self.unlocked_signal.emit(vault_bytes, self.profile_name)
            self.close()

        except Exception as e:
            QMessageBox.critical(self, "Unlock Failed", f"Invalid Vault Passphrase or corrupted data.\nDetails: {e}")


class AddContactDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Contact")
        self.setFixedSize(420, 280)
        self.setStyleSheet(STYLESHEET_PREMIUM)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl = QLabel("➕ ADD DERF CONTACT")
        lbl.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 13px;")
        layout.addWidget(lbl)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Contact Handle (e.g., Alice)...")
        layout.addWidget(self.txt_name)

        self.txt_key = QTextEdit()
        self.txt_key.setPlaceholderText("Paste LCAP1- Public Key string here...")
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

        self.setWindowTitle(f"Derf PQ+FS Messenger — Profile: [{profile_name.upper()}]")
        self.resize(1080, 720)
        self.setStyleSheet(STYLESHEET_PREMIUM)

        self.init_core_identity()
        self.init_ui()
        self.refresh_contacts()
        self.refresh_profile_keys()

    def init_core_identity(self):
        Derf.VAULT = self.vault_bytes
        raw_idn = Derf.vload(Derf.P("lc_identity.json"))
        self.idn = Derf.norm_identity(raw_idn)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        root_layout = QHBoxLayout(main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- LEFT SIDEBAR ---
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(16, 20, 16, 20)
        sb_layout.setSpacing(12)

        # Header Logo
        logo_lbl = QLabel("⚡ DERF MESSENGER")
        logo_lbl.setStyleSheet("color: #00F0FF; font-weight: 800; font-size: 16px; letter-spacing: 1px;")
        sb_layout.addWidget(logo_lbl)

        sub_lbl = QLabel(f"PROFILE: {self.profile_name.upper()} • PQ-ACTIVE")
        sub_lbl.setStyleSheet("color: #00E073; font-weight: bold; font-size: 11px;")
        sb_layout.addWidget(sub_lbl)

        sb_layout.addSpacing(10)

        # Section Label
        sec_contacts = QLabel("CONTACTS & SESSIONS")
        sec_contacts.setStyleSheet("color: #858FA6; font-weight: bold; font-size: 11px;")
        sb_layout.addWidget(sec_contacts)

        # Contacts List
        self.contacts_list = QListWidget()
        self.contacts_list.itemClicked.connect(self.on_contact_selected)
        sb_layout.addWidget(self.contacts_list)

        # Contact Actions Bar (Add / Delete)
        act_box = QHBoxLayout()
        btn_add = QPushButton("➕ ADD")
        btn_add.setObjectName("SecondaryButton")
        btn_add.clicked.connect(self.do_add_contact_dialog)

        self.btn_del = QPushButton("🗑️ DELETE")
        self.btn_del.setObjectName("DangerButton")
        self.btn_del.clicked.connect(self.do_delete_contact)

        act_box.addWidget(btn_add)
        act_box.addWidget(self.btn_del)
        sb_layout.addLayout(act_box)

        sb_layout.addSpacing(10)

        # Navigation Buttons
        self.btn_nav_chat = QPushButton("💬 SECURE CHAT")
        self.btn_nav_chat.setObjectName("SecondaryButton")
        self.btn_nav_chat.clicked.connect(lambda: self.switch_view(0))

        self.btn_nav_pair = QPushButton("🤝 PAIR / INVITE")
        self.btn_nav_pair.setObjectName("SecondaryButton")
        self.btn_nav_pair.clicked.connect(lambda: self.switch_view(1))

        self.btn_nav_specs = QPushButton("🛡️ SECURITY SPECS")
        self.btn_nav_specs.setObjectName("SecondaryButton")
        self.btn_nav_specs.clicked.connect(lambda: self.switch_view(2))

        self.btn_nav_settings = QPushButton("⚙️ SETTINGS")
        self.btn_nav_settings.setObjectName("SecondaryButton")
        self.btn_nav_settings.clicked.connect(lambda: self.switch_view(3))

        sb_layout.addWidget(self.btn_nav_chat)
        sb_layout.addWidget(self.btn_nav_pair)
        sb_layout.addWidget(self.btn_nav_specs)
        sb_layout.addWidget(self.btn_nav_settings)

        sb_layout.addStretch()

        root_layout.addWidget(sidebar)

        # --- RIGHT MAIN STAGE ---
        self.stage_stack = QStackedWidget()
        root_layout.addWidget(self.stage_stack)

        # Build Page Views
        self.stage_stack.addWidget(self.build_chat_view())
        self.stage_stack.addWidget(self.build_pair_view())
        self.stage_stack.addWidget(self.build_specs_view())
        self.stage_stack.addWidget(self.build_settings_view())

        self.switch_view(0)

    def switch_view(self, index):
        self.stage_stack.setCurrentIndex(index)

    # --- VIEW 1: CHAT VIEW ---
    def build_chat_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Chat Header Bar
        hdr = QFrame()
        hdr.setObjectName("CardPanel")
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(16, 12, 16, 12)

        self.lbl_chat_contact = QLabel("Select a contact from sidebar to start encrypted messaging.")
        self.lbl_chat_contact.setStyleSheet("font-weight: bold; font-size: 14px; color: #00F0FF;")
        hdr_layout.addWidget(self.lbl_chat_contact)

        hdr_layout.addStretch()

        self.lbl_chat_fp = QLabel("FP: ----")
        self.lbl_chat_fp.setStyleSheet("color: #858FA6; font-size: 11px;")
        hdr_layout.addWidget(self.lbl_chat_fp)

        layout.addWidget(hdr)

        # Message Scroll Area
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #131418;
                border: 1px solid #1F2129;
                border-radius: 12px;
                padding: 16px;
                font-family: 'Segoe UI', 'Consolas', monospace;
                font-size: 13px;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.chat_display)

        # Input Box & Actions
        input_box = QHBoxLayout()
        input_box.setSpacing(10)

        self.txt_msg = QLineEdit()
        self.txt_msg.setPlaceholderText("Type a secret message to encrypt...")
        self.txt_msg.returnPressed.connect(self.do_send_message)
        input_box.addWidget(self.txt_msg)

        btn_send = QPushButton("ENCRYPT & COPY")
        btn_send.clicked.connect(self.do_send_message)
        input_box.addWidget(btn_send)

        layout.addLayout(input_box)

        # Quick Hotkey Note
        lbl_tip = QLabel("💡 HOTKEY TIP: Highlight text anywhere and press [ Alt+Shift+D ] or [ Ctrl+Shift+E ] to encrypt & paste, or [ Alt+Shift+Q ] to decrypt in Quick Peek Glass!")
        lbl_tip.setStyleSheet("color: #858FA6; font-size: 11px;")
        layout.addWidget(lbl_tip)

        return page

    # --- VIEW 2: PAIR / INVITE VIEW ---
    def build_pair_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        hdr = QLabel("🤝 POST-QUANTUM KEY EXCHANGE (PAIRED HANDSHAKE)")
        hdr.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 16px;")
        layout.addWidget(hdr)

        card = QFrame()
        card.setObjectName("CardPanel")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 20, 20, 20)
        c_layout.setSpacing(12)

        lbl_step1 = QLabel("Step 1: Initiator — Generate & Send Invite")
        lbl_step1.setStyleSheet("font-weight: bold; color: #EEF0F8; font-size: 13px;")
        c_layout.addWidget(lbl_step1)

        self.txt_invite_out = QTextEdit()
        self.txt_invite_out.setFixedHeight(80)
        self.txt_invite_out.setPlaceholderText("Click 'Generate Invite' to create an ML-KEM-768 invite payload for the selected contact...")
        c_layout.addWidget(self.txt_invite_out)

        btn_gen_inv = QPushButton("GENERATE & COPY INVITE")
        btn_gen_inv.clicked.connect(self.do_generate_invite)
        c_layout.addWidget(btn_gen_inv)

        c_layout.addSpacing(10)

        lbl_step2 = QLabel("Step 2: Responder — Process Reply & Complete")
        lbl_step2.setStyleSheet("font-weight: bold; color: #EEF0F8; font-size: 13px;")
        c_layout.addWidget(lbl_step2)

        self.txt_reply_in = QTextEdit()
        self.txt_reply_in.setFixedHeight(80)
        self.txt_reply_in.setPlaceholderText("Paste responder reply here or invite payload if responding...")
        c_layout.addWidget(self.txt_reply_in)

        btn_proc_reply = QPushButton("PROCESS REPLY / COMPLETE PAIRING")
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

        hdr = QLabel("🛡️ DERF SECURITY & CRYPTOGRAPHY SPECIFICATIONS")
        hdr.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 16px;")
        layout.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(12)

        specs = [
            ("Post-Quantum KEM (ML-KEM-768 / Kyber768)", "Derf uses NIST FIPS 203 ML-KEM-768 post-quantum key encapsulation. Handshakes resist quantum computers running Shor's algorithm."),
            ("LC-AEAD Chained Encryption", "Per-letter chained ChaCha20-Poly1305 AEAD structure ensures payload integrity, strict message order, and immediate truncation rejection."),
            ("Signal-Style Double Ratchet", "Every packet advances the key ratchet. Compromising future or past keys yields zero access to prior ciphertexts (Forward Secrecy + Post-Compromise Security)."),
            ("Unprovable Deniability (X3DH)", "Handshakes rely on symmetric HKDF MAC tags rather than non-repudiable digital signatures. Neither party can prove message authorship to third parties."),
            ("Uniform Bucket Sizing (LCA2)", "Every ciphertext packet is padded into fixed 256-byte buckets (uniform ~962 character Base64 blocks), preventing length side-channel leaks and fitting Instagram/Discord limits."),
            ("Vault at Rest (PBKDF2-HMAC-SHA256)", "All identity keys, pending sessions, and contact states are stored on disk encrypted using 600,000 PBKDF2 iterations.")
        ]

        for title, desc in specs:
            card = QFrame()
            card.setObjectName("CardPanel")
            l = QVBoxLayout(card)
            l.setContentsMargins(16, 14, 16, 14)
            l.setSpacing(6)

            t = QLabel(f"⚡ {title}")
            t.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 13px;")
            l.addWidget(t)

            d = QLabel(desc)
            d.setWordWrap(True)
            d.setStyleSheet("color: #858FA6; font-size: 12px;")
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
        hdr.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 16px;")
        layout.addWidget(hdr)

        card = QFrame()
        card.setObjectName("CardPanel")
        l = QVBoxLayout(card)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(12)

        lbl_pk = QLabel("Your LCAP1- Public Key (Share with contacts to pair):")
        lbl_pk.setStyleSheet("font-weight: bold; color: #EEF0F8; font-size: 12px;")
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
        lbl_fresh.setStyleSheet("font-weight: bold; color: #EEF0F8; font-size: 12px;")
        l.addWidget(lbl_fresh)

        fresh_box = QHBoxLayout()
        self.spin_fresh = QSpinBox()
        self.spin_fresh.setRange(60, 86400)
        self.spin_fresh.setValue(int(Derf.FRESH))
        self.spin_fresh.setStyleSheet("background-color: #131418; color: #00F0FF; border: 1px solid #292C38; padding: 6px; border-radius: 6px;")
        fresh_box.addWidget(self.spin_fresh)

        btn_save_fresh = QPushButton("SAVE WINDOW TOLERANCE")
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
            fp = Derf.id_fp(contacts[name])
            self.lbl_chat_contact.setText(f"💬 Chatting with {name}")
            self.lbl_chat_fp.setText(f"FP: {fp}")

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
                self.chat_display.append(f"<font color='#858FA6'><b>Me:</b></font> <font color='#EEF0F8'>{msg}</font>")
                self.chat_display.append(f"<font color='#00F0FF'><i>[Ciphertext generated & copied to clipboard!]</i></font>\n")
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
        Derf.FRESH = val
        with open(Derf.P("lc_fresh.json"), "w") as f:
            json.dump({"fresh": val}, f)
        QMessageBox.information(self, "Saved", f"Freshness tolerance window set to {val} seconds.")


def launch_pyqt_app(profile_name="default"):
    app = QApplication(sys.argv)

    # Store references to prevent garbage collection
    main_win = None

    def on_vault_unlocked(vault_bytes, prof_name):
        nonlocal main_win
        main_win = DerfMainWindow(vault_bytes, prof_name)
        main_win.show()

        # Start integrated background hotkey service
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
