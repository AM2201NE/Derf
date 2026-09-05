"""
Derf PQ Messenger Native Mobile UI for Android (Toga + Google Stitch Design System).
100% Full Feature Parity with PC Desktop UI:
- Multi-profile Master Vault Encryption & Unlocking
- High-Contrast Obsidian Dark Theme (#0E0E0E) with crisp White (#FFFFFF) Text
- Chat & Direct Ciphertext Decryption Stage
- Contacts & Handshake Pairing Hub (Add, Shred, 3-Step Handshake)
- Identity Bundle & Out-Of-Band Safety Code Inspector
- Background Clipboard Auto-Scan for DERF:V1: Ciphertext Packets
"""
import sys
import os
import threading
import time
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, LEFT, RIGHT, CENTER, BOLD

import Derf

# Google Stitch Dark Theme Tokens
COLOR_OBSIDIAN = "#0E0E0E"   # Primary Stage Background
COLOR_CARD     = "#18181C"   # Card Panel Background
COLOR_INPUT_BG = "#222228"   # Input Field Background
COLOR_CYAN     = "#00F0FF"   # Electric Cyan Accent
COLOR_GREEN    = "#00FF9D"   # Active / Paired Green
COLOR_WHITE    = "#FFFFFF"   # High Contrast Reading Text
COLOR_MUTED    = "#A0A0A8"   # Muted Subtitle Text
COLOR_BORDER   = "#2A2A32"   # Container Border
COLOR_ERROR    = "#FF5252"   # Error Red


class DerfMobileApp(toga.App):
    def __init__(self, profile_name="default"):
        super().__init__("Derf PQ Messenger", "com.derf.pq.derf")
        self.profile_name = profile_name
        self.idn = None
        self.contacts = {}
        self.selected_peer = None
        self.monitoring_active = False

    def startup(self):
        self.main_box = toga.Box(style=Pack(direction=COLUMN, flex=1, margin=10, background_color=COLOR_OBSIDIAN))
        self.show_vault_screen()
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.main_box
        self.main_window.show()

    # -------------------------------------------------------------------------
    # 1. VAULT UNLOCK & INITIALIZATION STAGE
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
    # 2. MAIN APPLICATION INTERFACE
    # -------------------------------------------------------------------------
    def show_main_interface(self):
        self.main_box.clear()

        # Top Bar
        top_bar = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        brand_lbl = toga.Label("DERF PQ MESSENGER", style=Pack(font_weight=BOLD, color=COLOR_CYAN, flex=1))
        lock_btn = toga.Button("LOCK VAULT", on_press=self.on_lock_vault, style=Pack(width=100))
        top_bar.add(brand_lbl)
        top_bar.add(lock_btn)

        # Tab Navigation Bar
        tab_bar = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        chat_tab = toga.Button("CHAT", on_press=lambda w: self.switch_view("chat"), style=Pack(flex=1, margin_right=2))
        hub_tab = toga.Button("CONTACTS & PAIRING", on_press=lambda w: self.switch_view("hub"), style=Pack(flex=1, margin_right=2))
        id_tab = toga.Button("MY IDENTITY", on_press=lambda w: self.switch_view("identity"), style=Pack(flex=1))

        tab_bar.add(chat_tab)
        tab_bar.add(hub_tab)
        tab_bar.add(id_tab)

        # Status Notification Banner
        self.banner_lbl = toga.Label("", style=Pack(margin_bottom=5, text_align=CENTER, color=COLOR_CYAN))

        # Dynamic Content Container
        self.content_container = toga.Box(style=Pack(direction=COLUMN, flex=1, background_color=COLOR_OBSIDIAN))

        self.main_box.add(top_bar)
        self.main_box.add(tab_bar)
        self.main_box.add(self.banner_lbl)
        self.main_box.add(self.content_container)

        self.refresh_contacts_list()
        self.switch_view("chat")

    def switch_view(self, view_name):
        self.content_container.clear()
        self.banner_lbl.text = ""
        if view_name == "chat":
            self.render_chat_view()
        elif view_name == "hub":
            self.render_hub_view()
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
    # TAB A: CHAT & DECRYPTION STAGE
    # -------------------------------------------------------------------------
    def render_chat_view(self):
        # Peer Selector Header
        peer_info = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        peer_text = f"Active Peer: {self.selected_peer}" if self.selected_peer else "Active Peer: [No Contact Selected - Add Contact in Hub]"
        self.peer_status_lbl = toga.Label(peer_text, style=Pack(color=COLOR_GREEN, flex=1, font_weight=BOLD))
        peer_info.add(self.peer_status_lbl)

        # Chat Transcript Area
        self.chat_display = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, margin_bottom=10, background_color=COLOR_CARD, color=COLOR_WHITE)
        )

        # Decryption Panel Line
        dec_lbl = toga.Label("Decrypt Received Ciphertext Packet:", style=Pack(margin_bottom=3, color=COLOR_CYAN))
        dec_box = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        self.packet_input = toga.TextInput(
            placeholder="Paste DERF:V1: ciphertext packet here...",
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
            self.banner_lbl.text = "Error: Select a contact from Contacts & Pairing first."
            return

        try:
            cipher_text = Derf.encrypt_alien_stack(msg, self.selected_peer, self.idn)
            if cipher_text:
                self.app.clipboard.set_text(cipher_text)
                self.chat_display.value += f"\n[Me -> {self.selected_peer}]: {msg}\n[Ciphertext copied to clipboard]\n"
                self.msg_input.value = ""
                self.banner_lbl.text = "DERF Ciphertext copied to clipboard!"
            else:
                self.banner_lbl.text = f"Error: No active ratchet session with {self.selected_peer}. Complete handshake first."
        except Exception as e:
            self.banner_lbl.text = f"Encryption Error: {e}"

    def on_decrypt_packet(self, widget):
        raw_pkt = self.packet_input.value.strip() or self.app.clipboard.get_text()
        if not raw_pkt or "DERF:V1:" not in raw_pkt:
            self.banner_lbl.text = "Provide a valid DERF:V1: ciphertext packet."
            return

        try:
            decrypted = Derf.decrypt_alien_stack(raw_pkt, self.idn, custom_session_loader=Derf.load_sim_bob_session_standalone)
            if decrypted:
                peer = self.selected_peer or "Peer"
                self.chat_display.value += f"\n[{peer}]: {decrypted}\n"
                self.packet_input.value = ""
                self.banner_lbl.text = f"Decrypted Message: {decrypted}"
            else:
                self.banner_lbl.text = "Decryption Failed: Key out of sync or corrupted payload."
        except Exception as e:
            self.banner_lbl.text = f"Decryption Error: {e}"

    # -------------------------------------------------------------------------
    # TAB B: CONTACTS & HANDSHAKE HUB STAGE
    # -------------------------------------------------------------------------
    def render_hub_view(self):
        hdr = toga.Label("CONTACTS & HANDSHAKE PAIRING HUB", style=Pack(margin_bottom=8, font_weight=BOLD, color=COLOR_CYAN))

        # Contacts Listing
        contacts_display = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, margin_bottom=8, background_color=COLOR_CARD, color=COLOR_WHITE)
        )

        formatted_list = "SAVED CONTACTS & RATCHET SESSION STATUS:\n" + "="*40 + "\n\n"
        if self.contacts:
            for handle, pub_bytes in self.contacts.items():
                fp = Derf.b64(Derf.id_fp(pub_bytes))[:16]
                sess_path = Derf.P(f"lc_session_{handle}.json")
                status = "PAIRED (Active Ratchet)" if os.path.exists(sess_path) else "UNPAIRED (Needs Handshake)"
                formatted_list += f"Handle: {handle}\nFingerprint: {fp}...\nStatus: {status}\n" + "-"*40 + "\n"
        else:
            formatted_list += "No contacts saved. Use the Add Contact section below."

        contacts_display.value = formatted_list

        # Add Contact Form Box (Inline without secondary windows)
        add_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))
        add_lbl = toga.Label("Add New Contact:", style=Pack(margin_bottom=3, color=COLOR_WHITE, font_weight=BOLD))

        input_row = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        self.new_handle_input = toga.TextInput(placeholder="Handle Name (e.g. Alice)", style=Pack(width=140, margin_right=5, background_color=COLOR_INPUT_BG, color=COLOR_WHITE))
        self.new_key_input = toga.TextInput(placeholder="Paste ML-KEM-768 Public Key...", style=Pack(flex=1, background_color=COLOR_INPUT_BG, color=COLOR_WHITE))
        input_row.add(self.new_handle_input)
        input_row.add(self.new_key_input)

        add_btn_row = toga.Box(style=Pack(direction=ROW))
        save_contact_btn = toga.Button("SAVE CONTACT", on_press=self.on_save_contact_inline, style=Pack(flex=1, margin_right=3))
        shred_btn = toga.Button("SHRED CONTACT", on_press=self.on_shred_contact, style=Pack(flex=1, margin_left=3))
        add_btn_row.add(save_contact_btn)
        add_btn_row.add(shred_btn)

        add_box.add(add_lbl)
        add_box.add(input_row)
        add_box.add(add_btn_row)

        # Handshake 3-Step Section
        pair_hdr = toga.Label("Handshake Pairing Actions:", style=Pack(margin_bottom=3, color=COLOR_CYAN, font_weight=BOLD))
        pair_btn_box = toga.Box(style=Pack(direction=ROW, margin_top=3))

        gen_inv_btn = toga.Button("1. GEN INVITE", on_press=self.on_gen_invite, style=Pack(flex=1, margin_right=2))
        accept_inv_btn = toga.Button("2. ACCEPT INVITE", on_press=self.on_accept_invite, style=Pack(flex=1, margin_right=2))
        finish_pair_btn = toga.Button("3. COMPLETE HANDSHAKE", on_press=self.on_complete_pair, style=Pack(flex=1))

        pair_btn_box.add(gen_inv_btn)
        pair_btn_box.add(accept_inv_btn)
        pair_btn_box.add(finish_pair_btn)

        self.content_container.add(hdr)
        self.content_container.add(contacts_display)
        self.content_container.add(add_box)
        self.content_container.add(pair_hdr)
        self.content_container.add(pair_btn_box)

    def on_save_contact_inline(self, widget):
        handle = self.new_handle_input.value.strip()
        raw_key = self.new_key_input.value.strip()
        if not handle or not raw_key:
            self.banner_lbl.text = "Provide both Handle Name and Public Key."
            return

        try:
            pub_bytes = Derf.parse_pubkey(raw_key)
            Derf.contact_add(handle, pub_bytes)
            self.selected_peer = handle
            self.refresh_contacts_list()
            self.switch_view("hub")
            self.banner_lbl.text = f"Contact '{handle}' saved successfully!"
        except Exception as e:
            self.banner_lbl.text = f"Invalid Key: {e}"

    def on_shred_contact(self, widget):
        if not self.selected_peer:
            self.banner_lbl.text = "Select a contact to shred."
            return

        shredded = self.selected_peer
        Derf.contact_delete(shredded)
        self.selected_peer = None
        self.refresh_contacts_list()
        self.switch_view("hub")
        self.banner_lbl.text = f"Shredded contact '{shredded}' & session state."

    # -------------------------------------------------------------------------
    # PAIRING HANDSHAKE WORKFLOWS
    # -------------------------------------------------------------------------
    def on_gen_invite(self, widget):
        if not self.selected_peer or self.selected_peer not in self.contacts:
            self.banner_lbl.text = "Save and select a contact first."
            return

        try:
            req_blob, pend = Derf.hs_req(self.idn, self.contacts[self.selected_peer])
            Derf.vsave(Derf.P(f"lc_pending_{self.selected_peer}.json"), pend)
            inv_b64 = Derf.b64(req_blob)
            self.app.clipboard.set_text(inv_b64)
            self.banner_lbl.text = f"Handshake invite copied to clipboard! Send to {self.selected_peer}."
        except Exception as e:
            self.banner_lbl.text = f"Invite Error: {e}"

    def on_accept_invite(self, widget):
        inv_b64 = self.app.clipboard.get_text()
        if not inv_b64:
            self.banner_lbl.text = "Copy received invite code to clipboard first."
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
            self.banner_lbl.text = f"Invite accepted & reply copied! Safety Code: {code}"
        except Exception as e:
            self.banner_lbl.text = f"Accept Error: {e}"

    def on_complete_pair(self, widget):
        if not self.selected_peer:
            self.banner_lbl.text = "Select contact handle to complete pairing."
            return

        rsp_b64 = self.app.clipboard.get_text()
        if not rsp_b64:
            self.banner_lbl.text = "Copy received reply code to clipboard first."
            return

        try:
            raw_rsp = Derf.ub64(rsp_b64.strip())
            pend_path = Derf.P(f"lc_pending_{self.selected_peer}.json")
            if not os.path.exists(pend_path):
                self.banner_lbl.text = f"No pending handshake for {self.selected_peer}. Generate invite first."
                return

            pend = Derf.vload(pend_path)
            Derf.hs_complete(self.idn, pend, raw_rsp)

            peer_pub = self.contacts[self.selected_peer]
            code = Derf.safety_code(Derf.id_fp(Derf.id_bundle(self.idn)), Derf.id_fp(peer_pub))
            self.banner_lbl.text = f"Double Ratchet session active with {self.selected_peer}! Safety Code: {code}"
        except Exception as e:
            self.banner_lbl.text = f"Handshake Error: {e}"

    # -------------------------------------------------------------------------
    # TAB C: MY IDENTITY & SAFETY CODE INSPECTOR
    # -------------------------------------------------------------------------
    def render_identity_view(self):
        hdr = toga.Label("MY IDENTITY & SAFETY CODE INSPECTOR", style=Pack(margin_bottom=8, font_weight=BOLD, color=COLOR_CYAN))

        id_display = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, margin_bottom=10, background_color=COLOR_CARD, color=COLOR_WHITE)
        )

        pk_b64 = Derf.b64(Derf.id_bundle(self.idn))
        fp_hex = Derf.b64(Derf.id_fp(Derf.id_bundle(self.idn)))[:24]

        info_text = f"PROFILE: [{self.profile_name.upper()}]\n" + "="*40 + "\n\n"
        info_text += f"Public Key Bundle:\n{pk_b64}\n\n"
        info_text += f"Identity Fingerprint:\n{fp_hex}...\n\n"

        if self.selected_peer and self.selected_peer in self.contacts:
            peer_pub = self.contacts[self.selected_peer]
            code = Derf.safety_code(Derf.id_fp(Derf.id_bundle(self.idn)), Derf.id_fp(peer_pub))
            info_text += f"Out-Of-Band Safety Code ({self.selected_peer}):\n{code}\n"
        else:
            info_text += "Out-Of-Band Safety Code: [Select a contact in Hub to view safety code]\n"

        id_display.value = info_text

        copy_pk_btn = toga.Button("COPY MY PUBLIC KEY BUNDLE", on_press=lambda w: self.copy_pk_to_clip(pk_b64), style=Pack(flex=1))

        self.content_container.add(hdr)
        self.content_container.add(id_display)
        self.content_container.add(copy_pk_btn)

    def copy_pk_to_clip(self, pk_b64):
        self.app.clipboard.set_text(pk_b64)
        self.banner_lbl.text = "Public Key Bundle copied to clipboard!"

    # -------------------------------------------------------------------------
    # BACKGROUND CLIPBOARD AUTO-SCAN THREAD
    # -------------------------------------------------------------------------
    def start_clipboard_monitoring(self):
        self.monitoring_active = True
        t = threading.Thread(target=self._clipboard_monitor_loop, daemon=True)
        t.start()

    def _clipboard_monitor_loop(self):
        last_clip = ""
        while self.monitoring_active:
            try:
                clip = self.app.clipboard.get_text()
                if clip and clip != last_clip and "DERF:V1:" in clip:
                    last_clip = clip
                    print("[*] Clipboard monitor detected DERF packet!")
            except Exception:
                pass
            time.sleep(2)


def launch_mobile_app(profile_name="default"):
    app = DerfMobileApp(profile_name)
    app.main_loop()

if __name__ == "__main__":
    launch_mobile_app()
