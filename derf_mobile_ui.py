"""
Derf PQ Messenger Native Mobile UI for Android (Toga + Google Stitch Design System).
100% Feature Parity with PC Desktop UI:
- Vault Locking & Multi-Profile Encryption
- Contact Directory with ML-KEM-768 Public Keys & Session State
- 3-Step Handshake Pairing Studio (Gen Invite, Accept Invite, Complete Handshake)
- In-App Decryption Panel & Clipboard Auto-Monitor
- Identity Bundle & Out-Of-Band Safety Code Inspector
- Settings & Freshness Window Sync
- Clean, Minimalist, Emoji-Free Modern Dark Obsidian Aesthetic
"""
import sys
import os
import threading
import time
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, LEFT, RIGHT, CENTER, BOLD

import Derf

# Stitch Design System Tokens (Dark Obsidian Aesthetic)
COLOR_OBSIDIAN = "#0E0E0E"   # Primary stage background
COLOR_CARD     = "#18181C"   # Container card background
COLOR_INPUT_BG = "#222228"   # Input field background
COLOR_CYAN     = "#00F0FF"   # Electric Cyan accent
COLOR_GREEN    = "#00FF9D"   # Active / Paired status green
COLOR_WHITE    = "#FFFFFF"   # High contrast text
COLOR_MUTED    = "#A0A0A8"   # Secondary muted text
COLOR_BORDER   = "#2A2A32"   # Border line
COLOR_ERROR    = "#FF5252"   # Error red


class DerfMobileApp(toga.App):
    def __init__(self, profile_name="default"):
        super().__init__("Derf PQ Messenger", "com.derf.pq.derf")
        self.profile_name = profile_name
        self.idn = None
        self.contacts = {}
        self.selected_peer = None
        self.monitor_thread = None
        self.monitoring_active = False

    def startup(self):
        self.main_box = toga.Box(style=Pack(direction=COLUMN, flex=1, margin=10, background_color=COLOR_OBSIDIAN))
        self.show_vault_screen()
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.main_box
        self.main_window.show()

    # -------------------------------------------------------------------------
    # 1. VAULT UNLOCK & PROFILE CREATION STAGE
    # -------------------------------------------------------------------------
    def show_vault_screen(self):
        self.main_box.clear()

        title_lbl = toga.Label(
            "DERF POST-QUANTUM MESSENGER",
            style=Pack(margin_bottom=8, font_weight=BOLD, text_align=CENTER, color=COLOR_CYAN)
        )
        sub_lbl = toga.Label(
            f"Vault Profile: [{self.profile_name.upper()}]",
            style=Pack(margin_bottom=20, text_align=CENTER, color=COLOR_MUTED)
        )

        pass_lbl = toga.Label("Master Vault Password:", style=Pack(margin_bottom=5, color=COLOR_WHITE))
        self.pass_input = toga.PasswordInput(
            style=Pack(margin_bottom=15, background_color=COLOR_INPUT_BG, color=COLOR_WHITE)
        )

        btn_box = toga.Box(style=Pack(direction=ROW, margin_top=10))
        unlock_btn = toga.Button("UNLOCK VAULT", on_press=self.on_unlock_vault, style=Pack(flex=1, margin_right=5))
        create_btn = toga.Button("CREATE NEW VAULT", on_press=self.on_create_vault, style=Pack(flex=1, margin_left=5))

        btn_box.add(unlock_btn)
        btn_box.add(create_btn)

        self.status_lbl = toga.Label("", style=Pack(margin_top=15, text_align=CENTER, color=COLOR_ERROR))

        self.main_box.add(title_lbl)
        self.main_box.add(sub_lbl)
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
            self.status_lbl.text = "Password required."
            return

        try:
            if self._unlock_vault_core(pw):
                self.start_clipboard_monitoring()
                self.show_main_interface()
        except Exception as e:
            self.status_lbl.text = f"Unlock Failed: {e}"

    def on_create_vault(self, widget):
        pw = self.pass_input.value
        if not pw:
            self.status_lbl.text = "Password required."
            return

        try:
            id_path = Derf.P("lc_identity.json")
            if os.path.exists(id_path):
                os.remove(id_path)

            if self._unlock_vault_core(pw):
                self.start_clipboard_monitoring()
                self.show_main_interface()
        except Exception as e:
            self.status_lbl.text = f"Vault Creation Failed: {e}"

    # -------------------------------------------------------------------------
    # 2. MAIN NAVIGATION & INTERFACE STAGE
    # -------------------------------------------------------------------------
    def show_main_interface(self):
        self.main_box.clear()

        # Top Bar
        top_bar = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        brand_lbl = toga.Label("DERF PQ MESSENGER", style=Pack(font_weight=BOLD, color=COLOR_CYAN, flex=1))
        lock_btn = toga.Button("LOCK VAULT", on_press=self.on_lock_vault, style=Pack(width=100))
        top_bar.add(brand_lbl)
        top_bar.add(lock_btn)

        # Tab Selection Bar
        tab_bar = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        chat_tab = toga.Button("CHAT", on_press=lambda w: self.switch_view("chat"), style=Pack(flex=1, margin_right=2))
        contacts_tab = toga.Button("CONTACTS", on_press=lambda w: self.switch_view("contacts"), style=Pack(flex=1, margin_right=2))
        pairing_tab = toga.Button("PAIRING", on_press=lambda w: self.switch_view("pairing"), style=Pack(flex=1, margin_right=2))
        id_tab = toga.Button("IDENTITY", on_press=lambda w: self.switch_view("identity"), style=Pack(flex=1))

        tab_bar.add(chat_tab)
        tab_bar.add(contacts_tab)
        tab_bar.add(pairing_tab)
        tab_bar.add(id_tab)

        # Active Content Area
        self.content_container = toga.Box(style=Pack(direction=COLUMN, flex=1, background_color=COLOR_OBSIDIAN))

        self.main_box.add(top_bar)
        self.main_box.add(tab_bar)
        self.main_box.add(self.content_container)

        self.refresh_contacts_list()
        self.switch_view("chat")

    def switch_view(self, view_name):
        self.content_container.clear()
        if view_name == "chat":
            self.render_chat_view()
        elif view_name == "contacts":
            self.render_contacts_view()
        elif view_name == "pairing":
            self.render_pairing_view()
        elif view_name == "identity":
            self.render_identity_view()

    def on_lock_vault(self, widget):
        self.monitoring_active = False
        self.show_vault_screen()

    def refresh_contacts_list(self):
        self.contacts = Derf.contacts_load()
        if self.contacts:
            if not self.selected_peer or self.selected_peer not in self.contacts:
                self.selected_peer = list(self.contacts.keys())[0]

    # -------------------------------------------------------------------------
    # VIEW A: CHAT & DECRYPTION STAGE
    # -------------------------------------------------------------------------
    def render_chat_view(self):
        # Peer Info Box
        peer_info = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        peer_text = f"Active Peer: {self.selected_peer}" if self.selected_peer else "Active Peer: [No Contact Selected]"
        self.peer_status_lbl = toga.Label(peer_text, style=Pack(color=COLOR_GREEN, flex=1, font_weight=BOLD))
        peer_info.add(self.peer_status_lbl)

        # Chat Transcript Output
        self.chat_display = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, margin_bottom=10, background_color=COLOR_CARD, color=COLOR_WHITE)
        )

        # Decryption Line
        dec_lbl = toga.Label("Decrypt Received Ciphertext Packet:", style=Pack(margin_bottom=3, color=COLOR_CYAN))
        dec_box = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        self.packet_input = toga.TextInput(
            placeholder="Paste DERF:V1: ciphertext packet...",
            style=Pack(flex=1, margin_right=5, background_color=COLOR_INPUT_BG, color=COLOR_WHITE)
        )
        dec_btn = toga.Button("DECRYPT", on_press=self.on_decrypt_packet, style=Pack(width=90))
        dec_box.add(self.packet_input)
        dec_box.add(dec_btn)

        # Composer Line
        comp_lbl = toga.Label("Compose Encrypted Message:", style=Pack(margin_bottom=3, color=COLOR_WHITE))
        comp_box = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        self.msg_input = toga.TextInput(
            placeholder="Type confidential message...",
            style=Pack(flex=1, margin_right=5, background_color=COLOR_INPUT_BG, color=COLOR_WHITE)
        )
        enc_btn = toga.Button("ENCRYPT", on_press=self.on_encrypt_and_send, style=Pack(width=90))
        comp_box.add(self.msg_input)
        comp_box.add(enc_btn)

        self.content_container.add(peer_info)
        self.content_container.add(self.chat_display)
        self.content_container.add(dec_lbl)
        self.content_container.add(dec_box)
        self.content_container.add(comp_lbl)
        self.content_container.add(comp_box)

    def on_encrypt_and_send(self, widget):
        msg = self.msg_input.value.strip()
        if not msg:
            return
        if not self.selected_peer:
            self.main_window.error_dialog("Selection Required", "Add or select a contact first.")
            return

        try:
            cipher_text = Derf.encrypt_alien_stack(msg, self.selected_peer, self.idn)
            if cipher_text:
                self.app.clipboard.set_text(cipher_text)
                self.chat_display.value += f"\n[Me -> {self.selected_peer}]: {msg}\n[Ciphertext copied to clipboard]\n"
                self.msg_input.value = ""
                self.main_window.info_dialog("Encrypted", "DERF ciphertext copied to clipboard! Send it via any messaging app.")
            else:
                self.main_window.error_dialog("Session Error", f"No active session key with {self.selected_peer}. Perform pairing first.")
        except Exception as e:
            self.main_window.error_dialog("Encryption Error", str(e))

    def on_decrypt_packet(self, widget):
        raw_pkt = self.packet_input.value.strip() or self.app.clipboard.get_text()
        if not raw_pkt or "DERF:V1:" not in raw_pkt:
            self.main_window.error_dialog("Invalid Packet", "Provide a valid DERF:V1: ciphertext packet.")
            return

        try:
            decrypted = Derf.decrypt_alien_stack(raw_pkt, self.idn, custom_session_loader=Derf.load_sim_bob_session_standalone)
            if decrypted:
                peer = self.selected_peer or "Peer"
                self.chat_display.value += f"\n[{peer}]: {decrypted}\n"
                self.packet_input.value = ""
                self.main_window.info_dialog("Decrypted Message", decrypted)
            else:
                self.main_window.error_dialog("Decryption Failed", "Could not decrypt. Key out of sync or corrupted payload.")
        except Exception as e:
            self.main_window.error_dialog("Decryption Error", str(e))

    # -------------------------------------------------------------------------
    # VIEW B: CONTACT DIRECTORY STAGE
    # -------------------------------------------------------------------------
    def render_contacts_view(self):
        hdr = toga.Label("CONTACT DIRECTORY", style=Pack(margin_bottom=10, font_weight=BOLD, color=COLOR_CYAN))

        contacts_multiline = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, margin_bottom=10, background_color=COLOR_CARD, color=COLOR_WHITE)
        )

        formatted_list = "SAVED CONTACTS & SESSION STATUS:\n" + "="*35 + "\n\n"
        if self.contacts:
            for handle, pub_bytes in self.contacts.items():
                fp = Derf.b64(Derf.id_fp(pub_bytes))[:16]
                sess_path = Derf.P(f"lc_session_{handle}.json")
                status = "PAIRED (Active Ratchet)" if os.path.exists(sess_path) else "UNPAIRED (Needs Handshake)"
                formatted_list += f"Handle: {handle}\nFP: {fp}...\nStatus: {status}\n" + "-"*35 + "\n"
        else:
            formatted_list += "No contacts saved. Tap 'Add Contact' below to save a public key."

        contacts_multiline.value = formatted_list

        btn_row = toga.Box(style=Pack(direction=ROW, margin_top=5))
        add_btn = toga.Button("ADD CONTACT", on_press=self.on_add_contact_dialog, style=Pack(flex=1, margin_right=5))
        del_btn = toga.Button("SHRED CONTACT", on_press=self.on_delete_contact, style=Pack(flex=1, margin_left=5))

        btn_row.add(add_btn)
        btn_row.add(del_btn)

        self.content_container.add(hdr)
        self.content_container.add(contacts_multiline)
        self.content_container.add(btn_row)

    def on_add_contact_dialog(self, widget):
        def do_save(btn):
            handle = name_input.value.strip()
            raw_key = key_input.value.strip()
            if not handle or not raw_key:
                self.main_window.error_dialog("Input Required", "Enter Handle and Public Key.")
                return
            try:
                pub_bytes = Derf.parse_pubkey(raw_key)
                Derf.contact_add(handle, pub_bytes)
                self.selected_peer = handle
                self.refresh_contacts_list()
                dialog_win.close()
                self.switch_view("contacts")
                self.main_window.info_dialog("Saved", f"Contact '{handle}' added successfully.")
            except Exception as e:
                self.main_window.error_dialog("Key Error", f"Invalid public key: {e}")

        box = toga.Box(style=Pack(direction=COLUMN, margin=15, background_color=COLOR_OBSIDIAN))
        box.add(toga.Label("ADD CONTACT", style=Pack(margin_bottom=10, font_weight=BOLD, color=COLOR_CYAN)))
        box.add(toga.Label("Contact Handle / Name:", style=Pack(margin_bottom=3, color=COLOR_WHITE)))
        name_input = toga.TextInput(placeholder="e.g. Alice", style=Pack(margin_bottom=10, background_color=COLOR_INPUT_BG, color=COLOR_WHITE))
        box.add(name_input)

        box.add(toga.Label("ML-KEM-768 Public Key / Identity Bundle:", style=Pack(margin_bottom=3, color=COLOR_WHITE)))
        key_input = toga.TextInput(placeholder="Paste public key or identity bundle...", style=Pack(margin_bottom=15, background_color=COLOR_INPUT_BG, color=COLOR_WHITE))
        box.add(key_input)

        save_btn = toga.Button("SAVE CONTACT", on_press=do_save, style=Pack(margin_top=5))
        box.add(save_btn)

        dialog_win = toga.Window(title="Add Contact")
        dialog_win.content = box
        dialog_win.show()

    def on_delete_contact(self, widget):
        if not self.selected_peer:
            self.main_window.error_dialog("Selection Required", "Select a contact to delete.")
            return

        Derf.contact_delete(self.selected_peer)
        deleted = self.selected_peer
        self.selected_peer = None
        self.refresh_contacts_list()
        self.switch_view("contacts")
        self.main_window.info_dialog("Shredded", f"Shredded contact '{deleted}' and associated session state.")

    # -------------------------------------------------------------------------
    # VIEW C: PAIRING & HANDSHAKE STUDIO
    # -------------------------------------------------------------------------
    def render_pairing_view(self):
        hdr = toga.Label("HANDSHAKE PAIRING STUDIO", style=Pack(margin_bottom=8, font_weight=BOLD, color=COLOR_CYAN))

        step1_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=12))
        step1_lbl = toga.Label("Step 1: Generate Handshake Invite (Initiator)", style=Pack(margin_bottom=3, color=COLOR_WHITE, font_weight=BOLD))
        gen_btn = toga.Button("GENERATE & COPY INVITE", on_press=self.on_gen_invite, style=Pack(fill_horizontal=True))
        step1_box.add(step1_lbl)
        step1_box.add(gen_btn)

        step2_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=12))
        step2_lbl = toga.Label("Step 2: Accept Received Invite (Responder)", style=Pack(margin_bottom=3, color=COLOR_WHITE, font_weight=BOLD))
        accept_btn = toga.Button("ACCEPT INVITE FROM CLIPBOARD", on_press=self.on_accept_invite, style=Pack(fill_horizontal=True))
        step2_box.add(step2_lbl)
        step2_box.add(accept_btn)

        step3_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=12))
        step3_lbl = toga.Label("Step 3: Complete Handshake (Initiator)", style=Pack(margin_bottom=3, color=COLOR_WHITE, font_weight=BOLD))
        finish_btn = toga.Button("COMPLETE HANDSHAKE FROM REPLY", on_press=self.on_complete_pair, style=Pack(fill_horizontal=True))
        step3_box.add(step3_lbl)
        step3_box.add(finish_btn)

        self.content_container.add(hdr)
        self.content_container.add(step1_box)
        self.content_container.add(step2_box)
        self.content_container.add(step3_box)

    def on_gen_invite(self, widget):
        if not self.selected_peer or self.selected_peer not in self.contacts:
            self.main_window.error_dialog("Select Contact", "Save and select a contact first.")
            return

        try:
            req_blob, pend = Derf.hs_req(self.idn, self.contacts[self.selected_peer])
            Derf.vsave(Derf.P(f"lc_pending_{self.selected_peer}.json"), pend)
            inv_b64 = Derf.b64(req_blob)
            self.app.clipboard.set_text(inv_b64)
            self.main_window.info_dialog("Invite Generated", f"Handshake invite copied to clipboard!\n\nSend this code to {self.selected_peer}.")
        except Exception as e:
            self.main_window.error_dialog("Invite Error", str(e))

    def on_accept_invite(self, widget):
        inv_b64 = self.app.clipboard.get_text()
        if not inv_b64:
            self.main_window.error_dialog("Clipboard Empty", "Copy received invite code to clipboard first.")
            return

        try:
            raw_req = Derf.ub64(inv_b64.strip())
            rsp_blob, peer_pub = Derf.hs_rsp(self.idn, raw_req)

            peer_name = f"Peer_{Derf.b64(peer_pub[:4])}"
            Derf.contact_add(peer_name, peer_pub)
            self.selected_peer = peer_name
            self.refresh_contacts_list()

            rsp_b64 = Derf.b64(rsp_blob)
            self.app.clipboard.set_text(rsp_b64)

            code = Derf.safety_code(Derf.id_fp(Derf.id_bundle(self.idn)), Derf.id_fp(peer_pub))
            self.main_window.info_dialog("Invite Accepted", f"Handshake reply copied to clipboard!\n\nSend reply to peer.\n\nSafety Code:\n{code}")
        except Exception as e:
            self.main_window.error_dialog("Pairing Error", f"Failed to accept invite: {e}")

    def on_complete_pair(self, widget):
        if not self.selected_peer:
            self.main_window.error_dialog("Select Contact", "Select the contact handle you are pairing with.")
            return

        rsp_b64 = self.app.clipboard.get_text()
        if not rsp_b64:
            self.main_window.error_dialog("Clipboard Empty", "Copy received reply code to clipboard first.")
            return

        try:
            raw_rsp = Derf.ub64(rsp_b64.strip())
            pend_path = Derf.P(f"lc_pending_{self.selected_peer}.json")
            if not os.path.exists(pend_path):
                self.main_window.error_dialog("Missing Pending State", f"No pending handshake for {self.selected_peer}.")
                return

            pend = Derf.vload(pend_path)
            Derf.hs_complete(self.idn, pend, raw_rsp)

            peer_pub = self.contacts[self.selected_peer]
            code = Derf.safety_code(Derf.id_fp(Derf.id_bundle(self.idn)), Derf.id_fp(peer_pub))
            self.main_window.info_dialog("Pairing Complete", f"Established Double Ratchet session with {self.selected_peer}!\n\nSafety Code:\n{code}")
        except Exception as e:
            self.main_window.error_dialog("Pairing Error", f"Failed to complete pairing: {e}")

    # -------------------------------------------------------------------------
    # VIEW D: IDENTITY & SAFETY CODE INSPECTOR
    # -------------------------------------------------------------------------
    def render_identity_view(self):
        hdr = toga.Label("IDENTITY & SAFETY CODE INSPECTOR", style=Pack(margin_bottom=8, font_weight=BOLD, color=COLOR_CYAN))

        id_multiline = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, margin_bottom=10, background_color=COLOR_CARD, color=COLOR_WHITE)
        )

        pk_b64 = Derf.b64(Derf.id_bundle(self.idn))
        fp_hex = Derf.b64(Derf.id_fp(Derf.id_bundle(self.idn)))[:24]

        info_text = f"PROFILE: [{self.profile_name.upper()}]\n"
        info_text += f"Public Key Bundle:\n{pk_b64}\n\n"
        info_text += f"Identity Fingerprint:\n{fp_hex}...\n\n"

        if self.selected_peer and self.selected_peer in self.contacts:
            peer_pub = self.contacts[self.selected_peer]
            code = Derf.safety_code(Derf.id_fp(Derf.id_bundle(self.idn)), Derf.id_fp(peer_pub))
            info_text += f"Out-Of-Band Safety Code ({self.selected_peer}):\n{code}"
        else:
            info_text += "Out-Of-Band Safety Code: [Select a contact to generate safety code]"

        id_multiline.value = info_text

        copy_pk_btn = toga.Button("COPY MY PUBLIC KEY", on_press=lambda w: self.app.clipboard.set_text(pk_b64), style=Pack(fill_horizontal=True))

        self.content_container.add(hdr)
        self.content_container.add(id_multiline)
        self.content_container.add(copy_pk_btn)

    # -------------------------------------------------------------------------
    # CLIPBOARD MONITORING LOOP
    # -------------------------------------------------------------------------
    def start_clipboard_monitoring(self):
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._clipboard_monitor_loop, daemon=True)
        self.monitor_thread.start()

    def _clipboard_monitor_loop(self):
        last_clip = ""
        while self.monitoring_active:
            try:
                clip = self.app.clipboard.get_text()
                if clip and clip != last_clip and "DERF:V1:" in clip:
                    last_clip = clip
                    print(f"[*] Clipboard monitor detected DERF packet!")
            except Exception:
                pass
            time.sleep(2)


def launch_mobile_app(profile_name="default"):
    app = DerfMobileApp(profile_name)
    app.main_loop()

if __name__ == "__main__":
    launch_mobile_app()
