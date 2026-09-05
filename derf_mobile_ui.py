"""
Derf PQ Messenger Native Mobile UI for Android (Toga + High-Contrast Premium Stitch Dark Theme).
Designed for seamless cross-platform post-quantum deniable messaging on Android devices.
"""
import sys
import os
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, LEFT, RIGHT, CENTER, BOLD

import Derf

# High-Contrast Stitch Dark Theme Tokens
COLOR_OBSIDIAN = "#0E0E0E"   # Stage background
COLOR_CARD     = "#18181C"   # Card container
COLOR_INPUT_BG = "#222228"   # Input box background
COLOR_CYAN     = "#00F0FF"   # Electric Cyan accent
COLOR_GREEN    = "#00FF9D"   # Active / Paired Green
COLOR_WHITE    = "#FFFFFF"   # High contrast text
COLOR_MUTED    = "#A0A0A8"   # Secondary text
COLOR_WARNING  = "#FFB300"   # Warning text
COLOR_ERROR    = "#FF5252"   # Error text


class DerfMobileApp(toga.App):
    def __init__(self, profile_name="default"):
        super().__init__("Derf PQ Messenger", "com.derf.pq.derf")
        self.profile_name = profile_name
        self.idn = None
        self.contacts = {}
        self.selected_peer = None

    def startup(self):
        self.main_box = toga.Box(style=Pack(direction=COLUMN, flex=1, margin=10, background_color=COLOR_OBSIDIAN))
        self.show_vault_screen()
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.main_box
        self.main_window.show()

    # -------------------------------------------------------------------------
    # VAULT UNLOCK / INITIALIZATION SCREEN
    # -------------------------------------------------------------------------
    def show_vault_screen(self):
        self.main_box.clear()

        title_lbl = toga.Label(
            "🔒 DERF PQ MESSENGER",
            style=Pack(margin_bottom=10, font_weight=BOLD, text_align=CENTER, color=COLOR_CYAN)
        )
        subtitle_lbl = toga.Label(
            f"Vault Profile: [{self.profile_name.upper()}]",
            style=Pack(margin_bottom=20, text_align=CENTER, color=COLOR_MUTED)
        )

        pass_lbl = toga.Label("Master Vault Password:", style=Pack(margin_bottom=5, color=COLOR_WHITE))
        self.pass_input = toga.PasswordInput(
            style=Pack(margin_bottom=15, background_color=COLOR_INPUT_BG, color=COLOR_WHITE)
        )

        btn_box = toga.Box(style=Pack(direction=ROW, margin_top=10))
        unlock_btn = toga.Button("UNLOCK VAULT", on_press=self.on_unlock_vault, style=Pack(flex=1, margin_right=5))
        create_btn = toga.Button("CREATE VAULT", on_press=self.on_create_vault, style=Pack(flex=1, margin_left=5))

        btn_box.add(unlock_btn)
        btn_box.add(create_btn)

        self.status_lbl = toga.Label("", style=Pack(margin_top=15, text_align=CENTER, color=COLOR_WARNING))

        self.main_box.add(title_lbl)
        self.main_box.add(subtitle_lbl)
        self.main_box.add(pass_lbl)
        self.main_box.add(self.pass_input)
        self.main_box.add(btn_box)
        self.main_box.add(self.status_lbl)

    def _unlock_vault_core(self, pw):
        Derf.set_profile(self.profile_name)
        key = Derf.derive_vault(pw)
        Derf.VAULT = key

        id_path = Derf.P("lc_identity.json")
        if not os.path.exists(id_path):
            idn = Derf.make_identity()
            Derf.vsave(id_path, {"pq_sk": idn["pq_sk"], "pq_pk": idn["pq_pk"]})
            self.idn = idn
        else:
            raw_idn = Derf.vload(id_path)
            self.idn = Derf.norm_identity(raw_idn)

        self.contacts = Derf.contacts_load()
        return True

    def on_unlock_vault(self, widget):
        pw = self.pass_input.value
        if not pw:
            self.status_lbl.text = "⚠️ Password cannot be empty"
            return

        try:
            if self._unlock_vault_core(pw):
                self.show_main_chat_screen()
        except Exception as e:
            self.status_lbl.text = f"❌ Invalid Password: {e}"

    def on_create_vault(self, widget):
        pw = self.pass_input.value
        if not pw:
            self.status_lbl.text = "⚠️ Password cannot be empty"
            return

        try:
            id_path = Derf.P("lc_identity.json")
            if os.path.exists(id_path):
                os.remove(id_path)

            if self._unlock_vault_core(pw):
                self.show_main_chat_screen()
        except Exception as e:
            self.status_lbl.text = f"❌ Failed to create Vault: {e}"

    # -------------------------------------------------------------------------
    # MAIN CHAT & ENCRYPTION SCREEN
    # -------------------------------------------------------------------------
    def show_main_chat_screen(self):
        self.main_box.clear()

        # Top Header Bar
        header_box = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        title = toga.Label("🔐 DERF MESSENGER", style=Pack(font_weight=BOLD, color=COLOR_CYAN, flex=1))
        lock_btn = toga.Button("🔒 LOCK", on_press=lambda w: self.show_vault_screen(), style=Pack(width=75))
        header_box.add(title)
        header_box.add(lock_btn)

        # Active Contact Selector
        peer_box = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        self.peer_lbl = toga.Label("Active Peer: [Select Contact]", style=Pack(color=COLOR_GREEN, flex=1))
        add_contact_btn = toga.Button("➕ Contact", on_press=self.on_add_contact_dialog, style=Pack(width=90))
        peer_box.add(self.peer_lbl)
        peer_box.add(add_contact_btn)

        # Chat Transcript Display Area
        self.chat_display = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, margin_bottom=10, background_color=COLOR_CARD, color=COLOR_WHITE)
        )

        # Decryption Panel Header
        dec_lbl = toga.Label("🔓 Decrypt Received Message Packet:", style=Pack(margin_bottom=3, color=COLOR_CYAN))
        decrypt_box = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        self.packet_input = toga.TextInput(
            placeholder="Paste DERF:V1: ciphertext packet here...",
            style=Pack(flex=1, margin_right=5, background_color=COLOR_INPUT_BG, color=COLOR_WHITE)
        )
        decrypt_btn = toga.Button("DECRYPT", on_press=self.on_decrypt_packet, style=Pack(width=90))
        decrypt_box.add(self.packet_input)
        decrypt_box.add(decrypt_btn)

        # Send Message / Encrypt Line
        send_lbl = toga.Label("💬 Send Encrypted Message:", style=Pack(margin_bottom=3, color=COLOR_WHITE))
        send_box = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        self.msg_input = toga.TextInput(
            placeholder="Type confidential message...",
            style=Pack(flex=1, margin_right=5, background_color=COLOR_INPUT_BG, color=COLOR_WHITE)
        )
        send_btn = toga.Button("ENCRYPT", on_press=self.on_encrypt_and_send, style=Pack(width=90))
        send_box.add(self.msg_input)
        send_box.add(send_btn)

        # Pairing Action Bar
        pairing_box = toga.Box(style=Pack(direction=ROW, margin_top=4))
        gen_inv_btn = toga.Button("➕ Gen Invite", on_press=self.on_gen_invite, style=Pack(flex=1, margin_right=2))
        accept_inv_btn = toga.Button("📥 Accept Invite", on_press=self.on_accept_invite, style=Pack(flex=1, margin_left=2))
        finish_pair_btn = toga.Button("✅ Complete Pair", on_press=self.on_complete_pair, style=Pack(flex=1, margin_left=2))

        pairing_box.add(gen_inv_btn)
        pairing_box.add(accept_inv_btn)
        pairing_box.add(finish_pair_btn)

        self.main_box.add(header_box)
        self.main_box.add(peer_box)
        self.main_box.add(self.chat_display)
        self.main_box.add(dec_lbl)
        self.main_box.add(decrypt_box)
        self.main_box.add(send_lbl)
        self.main_box.add(send_box)
        self.main_box.add(pairing_box)

        self.refresh_contacts_list()

    def refresh_contacts_list(self):
        self.contacts = Derf.contacts_load()
        if self.contacts:
            if not self.selected_peer or self.selected_peer not in self.contacts:
                self.selected_peer = list(self.contacts.keys())[0]
            self.peer_lbl.text = f"Active Peer: {self.selected_peer}"
        else:
            self.selected_peer = None
            self.peer_lbl.text = "Active Peer: [No Contacts Saved]"

    # -------------------------------------------------------------------------
    # CONTACT & KEY MANAGEMENT
    # -------------------------------------------------------------------------
    def on_add_contact_dialog(self, widget):
        # Quick inline window / dialog for adding contact
        def do_save(btn):
            handle = name_input.value.strip()
            raw_key = key_input.value.strip()
            if not handle or not raw_key:
                self.main_window.error_dialog("Input Required", "Please enter both Handle name and Public Key.")
                return
            try:
                pub_bytes = Derf.parse_pubkey(raw_key)
                Derf.contact_add(handle, pub_bytes)
                self.selected_peer = handle
                self.refresh_contacts_list()
                dialog_win.close()
                self.main_window.info_dialog("Contact Saved", f"Contact '{handle}' saved successfully!")
            except Exception as e:
                self.main_window.error_dialog("Invalid Key", f"Error parsing public key: {e}")

        dialog_box = toga.Box(style=Pack(direction=COLUMN, margin=15, background_color=COLOR_OBSIDIAN))
        dialog_box.add(toga.Label("➕ ADD CONTACT", style=Pack(margin_bottom=10, font_weight=BOLD, color=COLOR_CYAN)))
        dialog_box.add(toga.Label("Handle / Name:", style=Pack(margin_bottom=3, color=COLOR_WHITE)))
        name_input = toga.TextInput(placeholder="e.g. Alice", style=Pack(margin_bottom=10, background_color=COLOR_INPUT_BG, color=COLOR_WHITE))
        dialog_box.add(name_input)

        dialog_box.add(toga.Label("Public Key / Key Bundle:", style=Pack(margin_bottom=3, color=COLOR_WHITE)))
        key_input = toga.TextInput(placeholder="Paste ML-KEM-768 public key...", style=Pack(margin_bottom=15, background_color=COLOR_INPUT_BG, color=COLOR_WHITE))
        dialog_box.add(key_input)

        save_btn = toga.Button("SAVE CONTACT", on_press=do_save, style=Pack(margin_top=5))
        dialog_box.add(save_btn)

        dialog_win = toga.Window(title="Add Contact")
        dialog_win.content = dialog_box
        dialog_win.show()

    # -------------------------------------------------------------------------
    # ENCRYPTION & DECRYPTION WORKFLOWS
    # -------------------------------------------------------------------------
    def on_encrypt_and_send(self, widget):
        msg = self.msg_input.value.strip()
        if not msg:
            return
        if not self.selected_peer:
            self.main_window.error_dialog("No Contact", "Please add or select a contact first.")
            return

        try:
            cipher_text = Derf.encrypt_alien_stack(msg, self.selected_peer, self.idn)
            if cipher_text:
                self.app.clipboard.set_text(cipher_text)
                self.chat_display.value += f"\n[Me -> {self.selected_peer}]: {msg}\n[🔒 Ciphertext copied to clipboard!]\n"
                self.msg_input.value = ""
                self.main_window.info_dialog("Encrypted!", "Encrypted DERF packet copied to clipboard! Send it via any messaging app.")
            else:
                self.main_window.error_dialog("Encryption Failed", f"No active session with {self.selected_peer}. Generate or accept an invite to pair.")
        except Exception as e:
            self.main_window.error_dialog("Encryption Error", str(e))

    def on_decrypt_packet(self, widget):
        raw_pkt = self.packet_input.value.strip() or self.app.clipboard.get_text()
        if not raw_pkt:
            self.main_window.error_dialog("No Packet", "Paste a DERF:V1: ciphertext packet into the box or copy it to clipboard.")
            return

        if "DERF:V1:" not in raw_pkt:
            self.main_window.error_dialog("Invalid Packet", "Clipboard / Input does not contain a valid DERF:V1: packet.")
            return

        try:
            decrypted = Derf.decrypt_alien_stack(raw_pkt, self.idn, custom_session_loader=Derf.load_sim_bob_session_standalone)
            if decrypted:
                peer = self.selected_peer or "Peer"
                self.chat_display.value += f"\n[{peer}]: {decrypted}\n"
                self.packet_input.value = ""
                self.main_window.info_dialog("Decrypted!", f"Decrypted Message:\n\n{decrypted}")
            else:
                self.main_window.error_dialog("Decryption Failed", "Could not decrypt message packet. Key out of sync or corrupted payload.")
        except Exception as e:
            self.main_window.error_dialog("Decryption Error", str(e))

    # -------------------------------------------------------------------------
    # PAIRING & HANDSHAKE WORKFLOWS
    # -------------------------------------------------------------------------
    def on_gen_invite(self, widget):
        if not self.selected_peer or self.selected_peer not in self.contacts:
            self.main_window.error_dialog("Select Contact", "Add and select a contact handle first to generate an invite.")
            return

        try:
            req_blob, pend = Derf.hs_req(self.idn, self.contacts[self.selected_peer])
            Derf.vsave(Derf.P(f"lc_pending_{self.selected_peer}.json"), pend)
            inv_b64 = Derf.b64(req_blob)
            self.app.clipboard.set_text(inv_b64)
            self.main_window.info_dialog("Invite Generated", f"Handshake invite generated & copied to clipboard!\n\nSend this code to {self.selected_peer}.")
        except Exception as e:
            self.main_window.error_dialog("Invite Error", str(e))

    def on_accept_invite(self, widget):
        inv_b64 = self.app.clipboard.get_text()
        if not inv_b64:
            self.main_window.error_dialog("Clipboard Empty", "Copy the received invite code to your clipboard first.")
            return

        try:
            raw_req = Derf.ub64(inv_b64.strip())
            rsp_blob, peer_pub = Derf.hs_rsp(self.idn, raw_req)

            # Save or update contact
            peer_name = f"Peer_{Derf.b64(peer_pub[:4])}"
            Derf.contact_add(peer_name, peer_pub)
            self.selected_peer = peer_name
            self.refresh_contacts_list()

            rsp_b64 = Derf.b64(rsp_blob)
            self.app.clipboard.set_text(rsp_b64)

            code = Derf.safety_code(Derf.id_fp(Derf.id_bundle(self.idn)), Derf.id_fp(peer_pub))
            self.main_window.info_dialog("Invite Accepted!", f"Accepted invite! Handshake reply copied to clipboard.\n\nSend the reply back to peer.\n\nSafety Code:\n{code}")
        except Exception as e:
            self.main_window.error_dialog("Pairing Error", f"Failed to accept invite: {e}")

    def on_complete_pair(self, widget):
        if not self.selected_peer:
            self.main_window.error_dialog("Select Contact", "Select the contact you are pairing with.")
            return

        rsp_b64 = self.app.clipboard.get_text()
        if not rsp_b64:
            self.main_window.error_dialog("Clipboard Empty", "Copy the handshake reply code received from peer to clipboard first.")
            return

        try:
            raw_rsp = Derf.ub64(rsp_b64.strip())
            pend_path = Derf.P(f"lc_pending_{self.selected_peer}.json")
            if not os.path.exists(pend_path):
                self.main_window.error_dialog("Missing Pending State", f"No pending handshake found for {self.selected_peer}. Generate invite first.")
                return

            pend = Derf.vload(pend_path)
            Derf.hs_complete(self.idn, pend, raw_rsp)

            peer_pub = self.contacts[self.selected_peer]
            code = Derf.safety_code(Derf.id_fp(Derf.id_bundle(self.idn)), Derf.id_fp(peer_pub))
            self.main_window.info_dialog("Pairing Complete!", f"Successfully established Double Ratchet session with {self.selected_peer}!\n\nSafety Code:\n{code}")
        except Exception as e:
            self.main_window.error_dialog("Pairing Error", f"Failed to complete pairing: {e}")


def launch_mobile_app(profile_name="default"):
    app = DerfMobileApp(profile_name)
    app.main_loop()

if __name__ == "__main__":
    launch_mobile_app()
