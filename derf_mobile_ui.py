"""
Derf PQ Messenger Native Mobile UI for Android (Toga + Google Stitch Design Tokens).
Designed specifically for BeeWare Briefcase on Android devices.
"""
import sys
import os
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, LEFT, RIGHT, CENTER, BOLD

import Derf

# Stitch Design System Tokens
COLOR_OBSIDIAN = "#0E0E0E"
COLOR_CARD = "#1C1B1B"
COLOR_CYAN = "#00F0FF"
COLOR_TEXT = "#E5E2E1"
COLOR_MUTED = "#8E8E93"
COLOR_SUCCESS = "#00FF9D"
COLOR_WARNING = "#FFB300"
COLOR_ERROR = "#FF5252"


class DerfMobileApp(toga.App):
    def __init__(self, profile_name="default"):
        super().__init__("Derf PQ Messenger", "com.derf.pq.derf")
        self.profile_name = profile_name
        self.idn_data = None
        self.contacts = {}
        self.active_peer_alias = None

    def startup(self):
        self.main_box = toga.Box(style=Pack(direction=COLUMN, flex=1, padding=10, background_color=COLOR_OBSIDIAN))
        self.show_vault_screen()
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.main_box
        self.main_window.show()

    def show_vault_screen(self):
        self.main_box.clear()

        title_lbl = toga.Label(
            "🔒 DERF PQ MESSENGER",
            style=Pack(padding_bottom=15, font_weight=BOLD, text_align=CENTER, color=COLOR_CYAN)
        )
        subtitle_lbl = toga.Label(
            f"Vault Profile: {self.profile_name}",
            style=Pack(padding_bottom=20, text_align=CENTER, color=COLOR_MUTED)
        )

        pass_lbl = toga.Label("Master Vault Password:", style=Pack(padding_bottom=5, color=COLOR_TEXT))
        self.pass_input = toga.PasswordInput(style=Pack(padding_bottom=15))

        btn_box = toga.Box(style=Pack(direction=ROW, padding_top=10))
        unlock_btn = toga.Button("UNLOCK VAULT", on_press=self.on_unlock_vault, style=Pack(flex=1, padding_right=5))
        create_btn = toga.Button("CREATE NEW", on_press=self.on_create_vault, style=Pack(flex=1, padding_left=5))

        btn_box.add(unlock_btn)
        btn_box.add(create_btn)

        self.status_lbl = toga.Label("", style=Pack(padding_top=15, text_align=CENTER, color=COLOR_WARNING))

        self.main_box.add(title_lbl)
        self.main_box.add(subtitle_lbl)
        self.main_box.add(pass_lbl)
        self.main_box.add(self.pass_input)
        self.main_box.add(btn_box)
        self.main_box.add(self.status_lbl)

    def _init_vault_data(self, pw):
        Derf.set_profile(self.profile_name)
        key = Derf.derive_vault(pw)
        vault_path = Derf.P("vault.enc")

        if not os.path.exists(vault_path):
            idn = Derf.make_identity()
            c = {}
            Derf.vsave(vault_path, (idn, c, key))
            self.idn_data = idn
            self.contacts = c
            return True

        res = Derf.vload(vault_path)
        if res is None:
            return False

        try:
            stored_idn, stored_contacts, stored_key = res
            if stored_key != key:
                return False
            self.idn_data = stored_idn
            self.contacts = stored_contacts
            return True
        except Exception:
            return False

    def on_unlock_vault(self, widget):
        pw = self.pass_input.value
        if not pw:
            self.status_lbl.text = "⚠️ Password cannot be empty"
            return

        if self._init_vault_data(pw):
            self.show_main_chat_screen()
        else:
            self.status_lbl.text = "❌ Invalid Password or Vault Error"

    def on_create_vault(self, widget):
        pw = self.pass_input.value
        if not pw:
            self.status_lbl.text = "⚠️ Password cannot be empty"
            return

        vault_path = Derf.P("vault.enc")
        if os.path.exists(vault_path):
            os.remove(vault_path)

        if self._init_vault_data(pw):
            self.show_main_chat_screen()
        else:
            self.status_lbl.text = "❌ Failed to create Vault"

    def show_main_chat_screen(self):
        self.main_box.clear()

        # Header
        header_box = toga.Box(style=Pack(direction=ROW, padding_bottom=10))
        title = toga.Label("🔐 DERF PQ (Mobile)", style=Pack(font_weight=BOLD, color=COLOR_CYAN, flex=1))
        lock_btn = toga.Button("🔒 LOCK", on_press=lambda w: self.show_vault_screen(), style=Pack(width=70))
        header_box.add(title)
        header_box.add(lock_btn)

        # Peer selection / Active contact
        peer_box = toga.Box(style=Pack(direction=ROW, padding_bottom=10))
        self.peer_lbl = toga.Label("Active Contact: [None]", style=Pack(color=COLOR_SUCCESS, flex=1))
        peer_box.add(self.peer_lbl)

        # Chat Log Box
        self.chat_multiline = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, padding_bottom=10, background_color=COLOR_CARD, color=COLOR_TEXT)
        )

        # Decryption Panel
        decrypt_box = toga.Box(style=Pack(direction=ROW, padding_bottom=10))
        self.packet_input = toga.TextInput(placeholder="Paste DERF ciphertext packet...", style=Pack(flex=1, padding_right=5))
        decrypt_btn = toga.Button("🔓 DECRYPT", on_press=self.on_decrypt_packet, style=Pack(width=100))
        decrypt_box.add(self.packet_input)
        decrypt_box.add(decrypt_btn)

        # Send Input Line
        send_box = toga.Box(style=Pack(direction=ROW, padding_bottom=5))
        self.msg_input = toga.TextInput(placeholder="Type message...", style=Pack(flex=1, padding_right=5))
        send_btn = toga.Button("🔒 ENCRYPT", on_press=self.on_encrypt_and_send, style=Pack(width=100))
        send_box.add(self.msg_input)
        send_box.add(send_btn)

        # Action bar (Invite / Pairing)
        action_box = toga.Box(style=Pack(direction=ROW, padding_top=5))
        gen_invite_btn = toga.Button("➕ Gen Invite", on_press=self.on_gen_invite, style=Pack(flex=1, padding_right=3))
        accept_invite_btn = toga.Button("📥 Accept Invite", on_press=self.on_accept_invite, style=Pack(flex=1, padding_left=3))
        action_box.add(gen_invite_btn)
        action_box.add(accept_invite_btn)

        self.main_box.add(header_box)
        self.main_box.add(peer_box)
        self.main_box.add(self.chat_multiline)
        self.main_box.add(decrypt_box)
        self.main_box.add(send_box)
        self.main_box.add(action_box)

        self.refresh_peers()

    def refresh_peers(self):
        if self.contacts:
            self.active_peer_alias = list(self.contacts.keys())[0]
            self.peer_lbl.text = f"Active Contact: {self.active_peer_alias}"
        else:
            self.active_peer_alias = None
            self.peer_lbl.text = "Active Contact: [No Contacts - Gen or Accept Invite]"

    def on_encrypt_and_send(self, widget):
        txt = self.msg_input.value
        if not txt or not self.active_peer_alias or self.active_peer_alias not in self.contacts:
            self.main_window.error_dialog("Encryption Error", "Select or pair with a contact first.")
            return

        peer_pub = self.contacts[self.active_peer_alias]
        pkt = Derf.encrypt_alien_stack(txt, peer_pub, self.idn_data)
        if pkt:
            self.app.clipboard.set_text(pkt)
            self.msg_input.value = ""
            self.chat_multiline.value += f"\n[Me -> {self.active_peer_alias}]: {txt}"
            self.main_window.info_dialog("Message Encrypted", "Encrypted packet copied to clipboard! Send it to your contact.")

    def on_decrypt_packet(self, widget):
        pkt = self.packet_input.value or self.app.clipboard.get_text()
        if not pkt:
            return

        res = Derf.decrypt_alien_stack(pkt, self.idn_data)
        if res and res[1]:
            sender_id, plain_txt = res[0], res[1]
            self.packet_input.value = ""
            self.chat_multiline.value += f"\n[Received Message]: {plain_txt}"
            self.main_window.info_dialog("Decryption Successful", f"Decrypted Message:\n{plain_txt}")
        else:
            self.main_window.error_dialog("Decryption Failed", "Invalid ciphertext packet or key out of sync.")

    def on_gen_invite(self, widget):
        if not self.idn_data:
            return
        inv = Derf.hs_req(self.idn_data, Derf.id_bundle(self.idn_data))
        if inv:
            self.app.clipboard.set_text(inv)
            self.main_window.info_dialog("Invite Generated", "Handshake Invite copied to clipboard! Send this code to your contact.")

    def on_accept_invite(self, widget):
        inv = self.app.clipboard.get_text()
        if not inv or "DERF" not in inv:
            self.main_window.error_dialog("Invalid Invite", "Clipboard does not contain a valid DERF invite packet.")
            return

        try:
            peer_id, rsp = Derf.hs_rsp(self.idn_data, inv)
            if peer_id and rsp:
                alias = f"Peer_{peer_id[:6]}"
                self.contacts[alias] = peer_id
                self.refresh_peers()

                safety = Derf.safety_code(Derf.id_fp(Derf.id_bundle(self.idn_data)), Derf.id_fp(peer_id))
                self.main_window.info_dialog("Pairing Complete", f"Paired with contact {alias}!\n\nSafety Code:\n{safety}")
        except Exception as e:
            self.main_window.error_dialog("Pairing Error", f"Failed to process handshake invite: {e}")


def launch_mobile_app(profile_name="default"):
    app = DerfMobileApp(profile_name)
    app.main_loop()

if __name__ == "__main__":
    launch_mobile_app()
