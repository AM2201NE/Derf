"""
Derf PQ Messenger Native Mobile UI for Android (Malewicz Method Structure-First Layout).
Designed with 100% Full Feature Parity with PC Desktop Application:
1. Multi-profile Vault Encryption & Master Password Unlocking
2. High-Contrast Dark Obsidian Theme (#0E0E0E) with 8pt Spacing Grid
3. Generous 48dp+ Touch Targets for Error-Free Tapping
4. 4 Main Navigation Tabs:
   - CHAT: Active peer banner, chat transcript, direct ciphertext packet decryption box, composer.
   - CONTACTS: Contact list cards with status, fingerprint, select button, and individual trash bin shred button.
   - PAIRING: 3-step Handshake Studio (Generate Invite, Accept Invite, Complete Handshake).
   - IDENTITY & SETTINGS: ML-KEM-768 public key bundle, fingerprint, safety code, freshness window config, global nuke.
5. In-Process Background Clipboard Auto-Scan for DERF:V1: Ciphertext Packets
"""
import sys
import os
import threading
import time
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, LEFT, RIGHT, CENTER, BOLD

import Derf

# Malewicz Systematic 8pt Grid & High-Contrast Color Palette
COLOR_OBSIDIAN = "#0E0E0E"   # Stage Background (Darkest)
COLOR_CARD     = "#18181C"   # Card Panel Background
COLOR_INPUT_BG = "#222228"   # High-Contrast Input Container
COLOR_CYAN     = "#00F0FF"   # Primary Brand / Accent
COLOR_GREEN    = "#00FF9D"   # Active / Paired Status Green
COLOR_WHITE    = "#FFFFFF"   # High-Contrast Crisp Reading Text
COLOR_MUTED    = "#A0A0A8"   # Secondary Subtitle Text
COLOR_BORDER   = "#2A2A32"   # Structural Divider Border
COLOR_ERROR    = "#FF5252"   # Error Red


class DerfMobileApp(toga.App):
    def __init__(self, profile_name="default"):
        super().__init__("Derf PQ Messenger", "com.derf.pq.derf")
        self.profile_name = profile_name
        self.idn = None
        self.contacts = {}
        self.selected_peer = None
        self.monitoring_active = False

    def request_android_permissions(self):
        """Request Android permissions dynamically via Chaquopy."""
        is_android = ('ANDROID_DATA' in os.environ or 'ANDROID_ROOT' in os.environ or
                      hasattr(sys, 'getandroidapilevel') or sys.platform == 'android')
        if not is_android:
            return

        try:
            from java import jclass, jarray
            Activity = jclass("org.beeware.android.MainActivity")
            activity = Activity.singletonThis
            if activity is not None:
                ActivityCompat = jclass("androidx.core.app.ActivityCompat")
                StringClass = jclass("java.lang.String")
                VERSION = jclass("android.os.Build$VERSION")
                if VERSION.SDK_INT >= 33:
                    req_perms = ["android.permission.POST_NOTIFICATIONS"]
                else:
                    req_perms = ["android.permission.READ_EXTERNAL_STORAGE", "android.permission.WRITE_EXTERNAL_STORAGE"]

                permissions = jarray(StringClass)(req_perms)
                ActivityCompat.requestPermissions(activity, permissions, 101)
                print(f"[+] Requested Android runtime permissions successfully for SDK {VERSION.SDK_INT}.")
        except Exception as e:
            print(f"[!] Android runtime permissions request exception: {e}")

    def startup(self):
        # Trigger Android permissions on startup
        self.request_android_permissions()

        self.main_box = toga.Box(style=Pack(direction=COLUMN, flex=1, margin=8, background_color=COLOR_OBSIDIAN))
        self.show_vault_screen()
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.main_box
        self.main_window.show()

    # =========================================================================
    # 1. VAULT UNLOCK & INITIALIZATION STAGE
    # =========================================================================
    def show_vault_screen(self):
        self.main_box.clear()

        title_lbl = toga.Label(
            "DERF POST-QUANTUM MESSENGER",
            style=Pack(margin_bottom=8, font_weight=BOLD, text_align=CENTER, color=COLOR_CYAN)
        )
        sub_lbl = toga.Label(
            f"Vault Profile: [{self.profile_name.upper()}]",
            style=Pack(margin_bottom=24, text_align=CENTER, color=COLOR_MUTED)
        )

        pass_lbl = toga.Label("Master Vault Password:", style=Pack(margin_bottom=8, color=COLOR_WHITE))
        self.pass_input = toga.PasswordInput(
            style=Pack(margin_bottom=16, height=48, background_color=COLOR_INPUT_BG, color=COLOR_WHITE)
        )

        btn_box = toga.Box(style=Pack(direction=ROW, margin_top=8))
        unlock_btn = toga.Button("UNLOCK VAULT", on_press=self.on_unlock_vault, style=Pack(flex=1, height=48, margin_right=4))
        create_btn = toga.Button("CREATE NEW VAULT", on_press=self.on_create_vault, style=Pack(flex=1, height=48, margin_left=4))

        btn_box.add(unlock_btn)
        btn_box.add(create_btn)

        self.status_lbl = toga.Label("", style=Pack(margin_top=16, text_align=CENTER, color=COLOR_ERROR))

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

    # =========================================================================
    # 2. MAIN APPLICATION INTERFACE (MALEWICZ METHOD LAYOUT)
    # =========================================================================
    def show_main_interface(self):
        self.main_box.clear()

        # Top Bar
        top_bar = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        brand_lbl = toga.Label("DERF MESSENGER", style=Pack(font_weight=BOLD, color=COLOR_CYAN, flex=1))

        lock_btn = toga.Button("LOCK", on_press=self.on_lock_vault, style=Pack(width=70, height=44, margin_right=4))
        nuke_btn = toga.Button("💣 NUKE", on_press=self.on_nuke_all_data, style=Pack(width=85, height=44, background_color=COLOR_ERROR))

        top_bar.add(brand_lbl)
        top_bar.add(lock_btn)
        top_bar.add(nuke_btn)

        # 4 Main Navigation Tabs
        tab_bar = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        chat_tab = toga.Button("CHAT", on_press=lambda w: self.switch_view("chat"), style=Pack(flex=1, height=44, margin_right=2))
        contacts_tab = toga.Button("CONTACTS", on_press=lambda w: self.switch_view("contacts"), style=Pack(flex=1, height=44, margin_right=2))
        pairing_tab = toga.Button("PAIRING", on_press=lambda w: self.switch_view("pairing"), style=Pack(flex=1, height=44, margin_right=2))
        id_tab = toga.Button("IDENTITY", on_press=lambda w: self.switch_view("identity"), style=Pack(flex=1, height=44))

        tab_bar.add(chat_tab)
        tab_bar.add(contacts_tab)
        tab_bar.add(pairing_tab)
        tab_bar.add(id_tab)

        # Status Notification Banner
        self.banner_lbl = toga.Label("", style=Pack(margin_bottom=4, text_align=CENTER, color=COLOR_CYAN))

        # Dynamic Content Container & Touch Scroll Area
        self.content_container = toga.Box(style=Pack(direction=COLUMN, flex=1, background_color=COLOR_OBSIDIAN))
        self.scroll_area = toga.ScrollContainer(content=self.content_container, style=Pack(flex=1))

        self.main_box.add(top_bar)
        self.main_box.add(tab_bar)
        self.main_box.add(self.banner_lbl)
        self.main_box.add(self.scroll_area)

        self.refresh_contacts_list()
        self.switch_view("chat")

    def switch_view(self, view_name):
        self.content_container.clear()
        self.banner_lbl.text = ""
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

    def on_nuke_all_data(self, widget):
        Derf.nuke_all_files()
        self.monitoring_active = False
        self.show_vault_screen()
        self.status_lbl.text = "💣 All local profile vault data has been shredded!"

    def refresh_contacts_list(self):
        self.contacts = Derf.contacts_load()
        if self.contacts:
            if not self.selected_peer or self.selected_peer not in self.contacts:
                self.selected_peer = list(self.contacts.keys())[0]

    # =========================================================================
    # TAB 1: CHAT & DECRYPTION STAGE
    # =========================================================================
    def on_switch_chat_peer(self, handle):
        self.selected_peer = handle
        self.banner_lbl.text = f"Switched active recipient to '{handle}'"
        self.switch_view("chat")

    def render_chat_view(self):
        sel_hdr = toga.Label("SELECT RECIPIENT / PEER:", style=Pack(margin_bottom=3, color=COLOR_MUTED, font_weight=BOLD))
        self.content_container.add(sel_hdr)

        if self.contacts:
            picker_box = toga.Box(style=Pack(direction=ROW, margin_bottom=6))
            for handle in self.contacts.keys():
                is_sel = (handle == self.selected_peer)
                lbl_txt = f"🟢 {handle}" if is_sel else handle
                btn = toga.Button(lbl_txt, on_press=lambda w, h=handle: self.on_switch_chat_peer(h), style=Pack(margin_right=5, height=38))
                picker_box.add(btn)
            self.content_container.add(picker_box)

        # Active Peer Banner
        peer_info = toga.Box(style=Pack(direction=ROW, margin_bottom=6))
        peer_text = f"Active Peer: {self.selected_peer}" if self.selected_peer else "Active Peer: [No Contact Selected - Add Contact in Contacts Tab]"
        self.peer_status_lbl = toga.Label(peer_text, style=Pack(color=COLOR_GREEN, flex=1, font_weight=BOLD))
        peer_info.add(self.peer_status_lbl)

        # Chat Transcript Area
        self.chat_display = toga.MultilineTextInput(
            readonly=True,
            style=Pack(height=110, margin_bottom=6, background_color=COLOR_CARD, color=COLOR_WHITE)
        )

        # Decryption Panel Line
        dec_lbl = toga.Label("Decrypt Received Ciphertext Packet:", style=Pack(margin_bottom=2, color=COLOR_CYAN))
        dec_box = toga.Box(style=Pack(direction=ROW, margin_bottom=6))
        self.packet_input = toga.TextInput(
            placeholder="Paste DERF:V1: ciphertext packet here...",
            style=Pack(flex=1, height=48, margin_right=5, background_color=COLOR_INPUT_BG, color=COLOR_WHITE)
        )
        dec_btn = toga.Button("DECRYPT", on_press=self.on_decrypt_packet, style=Pack(width=100, height=48))
        dec_box.add(self.packet_input)
        dec_box.add(dec_btn)

        # Composer Line
        comp_lbl = toga.Label("Compose Encrypted Message:", style=Pack(margin_bottom=2, color=COLOR_WHITE))
        comp_box = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        self.msg_input = toga.TextInput(
            placeholder="Type confidential message...",
            style=Pack(flex=1, height=48, margin_right=5, background_color=COLOR_INPUT_BG, color=COLOR_WHITE)
        )
        enc_btn = toga.Button("ENCRYPT", on_press=self.on_encrypt_and_send, style=Pack(width=100, height=48))
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
            self.banner_lbl.text = "Error: Select a contact from Contacts tab first."
            return

        try:
            cipher_text = Derf.encrypt_alien_stack(msg, self.selected_peer, self.idn)
            if cipher_text:
                Derf.safe_copy(cipher_text)
                self.chat_display.value += f"\n[Me -> {self.selected_peer}]: {msg}\n[Ciphertext copied to clipboard]\n"
                self.msg_input.value = ""
                self.banner_lbl.text = "DERF Ciphertext copied to clipboard!"
            else:
                self.banner_lbl.text = f"Error: No active ratchet session with {self.selected_peer}. Complete handshake first."
        except Exception as e:
            self.banner_lbl.text = f"Encryption Error: {e}"

    def on_decrypt_packet(self, widget):
        raw_pkt = self.packet_input.value.strip() or Derf.safe_paste().strip()
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

    # =========================================================================
    # TAB 2: CONTACTS DIRECTORY STAGE (WITH INDIVIDUAL TRASH BIN SHREDDING)
    # =========================================================================
    def render_contacts_view(self):
        hdr = toga.Label("CONTACT DIRECTORY & RATCHET STATUS", style=Pack(margin_bottom=6, font_weight=BOLD, color=COLOR_CYAN))
        self.content_container.add(hdr)

        # Individual Contact Cards
        if self.contacts:
            contacts_container = toga.Box(style=Pack(direction=COLUMN, margin_bottom=8))
            for handle, pub_bytes in self.contacts.items():
                card = toga.Box(style=Pack(direction=ROW, margin_bottom=4, margin_top=2, background_color=COLOR_CARD))

                fp = Derf.b64(Derf.id_fp(pub_bytes))[:12]
                sess_path = Derf.P(f"lc_session_{handle}.json")
                paired = os.path.exists(sess_path)
                status_str = "[PAIRED]" if paired else "[UNPAIRED]"
                status_color = COLOR_GREEN if paired else COLOR_MUTED

                # Left Info Box
                info_box = toga.Box(style=Pack(direction=COLUMN, flex=1, margin=6))
                title_lbl = toga.Label(f"👤 {handle} {status_str}", style=Pack(color=COLOR_WHITE, font_weight=BOLD))
                fp_lbl = toga.Label(f"FP: {fp}...", style=Pack(color=COLOR_MUTED))
                info_box.add(title_lbl)
                info_box.add(fp_lbl)

                # Select / Activate Button
                select_btn = toga.Button("SELECT", on_press=lambda w, h=handle: self.on_select_contact(h), style=Pack(width=70, height=40, margin_right=4))

                # Trash Bin Shred Button (7-Pass Unrecoverable Shredding)
                shred_btn = toga.Button("🗑️ SHRED", on_press=lambda w, h=handle: self.on_shred_single_contact(h), style=Pack(width=85, height=40))

                card.add(info_box)
                card.add(select_btn)
                card.add(shred_btn)
                contacts_container.add(card)

            self.content_container.add(contacts_container)
        else:
            no_contacts_lbl = toga.Label("No contacts saved. Use the form below to add a contact.", style=Pack(margin_bottom=8, color=COLOR_MUTED))
            self.content_container.add(no_contacts_lbl)

        # Add Contact Form Box
        add_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=6))
        add_lbl = toga.Label("Add New Contact:", style=Pack(margin_bottom=3, color=COLOR_WHITE, font_weight=BOLD))

        input_row = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        self.new_handle_input = toga.TextInput(placeholder="Handle (e.g. Alice)", style=Pack(width=130, height=48, margin_right=5, background_color=COLOR_INPUT_BG, color=COLOR_WHITE))
        self.new_key_input = toga.TextInput(placeholder="Paste Public Key...", style=Pack(flex=1, height=48, background_color=COLOR_INPUT_BG, color=COLOR_WHITE))
        input_row.add(self.new_handle_input)
        input_row.add(self.new_key_input)

        save_contact_btn = toga.Button("SAVE CONTACT", on_press=self.on_save_contact_inline, style=Pack(fill_horizontal=True, height=48))

        add_box.add(add_lbl)
        add_box.add(input_row)
        add_box.add(save_contact_btn)

        self.content_container.add(add_box)

    def on_select_contact(self, handle):
        self.selected_peer = handle
        self.banner_lbl.text = f"Active Peer set to '{handle}'"

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
            self.switch_view("contacts")
            self.banner_lbl.text = f"Contact '{handle}' saved successfully!"
        except Exception as e:
            self.banner_lbl.text = f"Invalid Key: {e}"

    def on_shred_single_contact(self, handle):
        Derf.contact_delete(handle)
        if self.selected_peer == handle:
            self.selected_peer = None
        self.refresh_contacts_list()
        self.switch_view("contacts")
        self.banner_lbl.text = f"Permanently shredded contact '{handle}' & session state!"

    # =========================================================================
    # TAB 3: HANDSHAKE PAIRING STUDIO (3-STEP FLOW)
    # =========================================================================
    def render_pairing_view(self):
        hdr = toga.Label("HANDSHAKE PAIRING STUDIO", style=Pack(margin_bottom=6, font_weight=BOLD, color=COLOR_CYAN))

        sub_lbl = toga.Label(
            f"Target Contact: {self.selected_peer or '[None Selected - Select in Contacts Tab]'}",
            style=Pack(margin_bottom=8, color=COLOR_WHITE)
        )

        pair_btn_box = toga.Box(style=Pack(direction=COLUMN, margin_top=4))

        gen_inv_btn = toga.Button("1. GENERATE & COPY INVITE", on_press=self.on_gen_invite, style=Pack(fill_horizontal=True, height=48, margin_bottom=6))
        accept_inv_btn = toga.Button("2. ACCEPT INVITE FROM CLIPBOARD", on_press=self.on_accept_invite, style=Pack(fill_horizontal=True, height=48, margin_bottom=6))
        finish_pair_btn = toga.Button("3. COMPLETE HANDSHAKE FROM REPLY", on_press=self.on_complete_pair, style=Pack(fill_horizontal=True, height=48))

        pair_btn_box.add(gen_inv_btn)
        pair_btn_box.add(accept_inv_btn)
        pair_btn_box.add(finish_pair_btn)

        self.content_container.add(hdr)
        self.content_container.add(sub_lbl)
        self.content_container.add(pair_btn_box)

    def on_gen_invite(self, widget):
        if not self.selected_peer or self.selected_peer not in self.contacts:
            self.banner_lbl.text = "Save and select a contact first."
            return

        try:
            req_blob, pend = Derf.hs_req(self.idn, self.contacts[self.selected_peer])
            Derf.vsave(Derf.P(f"lc_pending_{self.selected_peer}.json"), pend)
            inv_b64 = Derf.b64(req_blob)
            Derf.safe_copy(inv_b64)
            self.banner_lbl.text = f"Handshake invite copied to clipboard! Send to {self.selected_peer}."
        except Exception as e:
            self.banner_lbl.text = f"Invite Error: {e}"

    def on_accept_invite(self, widget):
        inv_b64 = Derf.safe_paste().strip()
        if not inv_b64:
            self.banner_lbl.text = "Copy received invite code to clipboard first."
            return

        try:
            raw_req = Derf.ub64(inv_b64)
            rsp_blob, peer_pub = Derf.hs_rsp(self.idn, raw_req)

            peer_name = f"Peer_{Derf.b64(peer_pub[:4])}"
            Derf.contact_add(peer_name, peer_pub)
            self.selected_peer = peer_name
            self.refresh_contacts_list()

            rsp_b64 = Derf.b64(rsp_blob)
            Derf.safe_copy(rsp_b64)

            code = Derf.safety_code(Derf.id_fp(Derf.id_bundle(self.idn)), Derf.id_fp(peer_pub))
            self.banner_lbl.text = f"Invite accepted & reply copied! Safety Code: {code}"
        except Exception as e:
            self.banner_lbl.text = f"Accept Error: {e}"

    def on_complete_pair(self, widget):
        if not self.selected_peer:
            self.banner_lbl.text = "Select contact handle to complete pairing."
            return

        rsp_b64 = Derf.safe_paste().strip()
        if not rsp_b64:
            self.banner_lbl.text = "Copy received reply code to clipboard first."
            return

        try:
            raw_rsp = Derf.ub64(rsp_b64)
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

    # =========================================================================
    # TAB 4: MY IDENTITY & SAFETY CODE INSPECTOR & SETTINGS
    # =========================================================================
    def render_identity_view(self):
        hdr = toga.Label("MY IDENTITY & SETTINGS", style=Pack(margin_bottom=6, font_weight=BOLD, color=COLOR_CYAN))

        id_display = toga.MultilineTextInput(
            readonly=True,
            style=Pack(height=120, margin_bottom=8, background_color=COLOR_CARD, color=COLOR_WHITE)
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
            info_text += "Out-Of-Band Safety Code: [Select a contact in Contacts tab to view safety code]\n"

        id_display.value = info_text

        copy_pk_btn = toga.Button("COPY MY PUBLIC KEY BUNDLE", on_press=lambda w: self.copy_pk_to_clip(pk_b64), style=Pack(fill_horizontal=True, height=48, margin_bottom=10))

        # Freshness Window Config Section
        fresh_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=8))
        fresh_hdr = toga.Label("Freshness Window Tolerance (Seconds):", style=Pack(margin_bottom=3, color=COLOR_WHITE, font_weight=BOLD))

        fresh_row = toga.Box(style=Pack(direction=ROW))
        self.fresh_input = toga.TextInput(value=str(int(Derf.FRESH)), style=Pack(flex=1, height=48, margin_right=5, background_color=COLOR_INPUT_BG, color=COLOR_WHITE))
        save_fresh_btn = toga.Button("SAVE TOLERANCE", on_press=self.on_save_freshness, style=Pack(width=130, height=48))
        fresh_row.add(self.fresh_input)
        fresh_row.add(save_fresh_btn)

        fresh_box.add(fresh_hdr)
        fresh_box.add(fresh_row)

        self.content_container.add(hdr)
        self.content_container.add(id_display)
        self.content_container.add(copy_pk_btn)
        self.content_container.add(fresh_box)

    def copy_pk_to_clip(self, pk_b64):
        Derf.safe_copy(pk_b64)
        self.banner_lbl.text = "Public Key Bundle copied to clipboard!"

    def on_save_freshness(self, widget):
        try:
            val = float(self.fresh_input.value.strip())
            Derf.FRESH = val
            self.banner_lbl.text = f"Freshness tolerance set to {int(val)} seconds!"
        except Exception as e:
            self.banner_lbl.text = f"Invalid tolerance value: {e}"

    # =========================================================================
    # BACKGROUND CLIPBOARD AUTO-SCAN THREAD
    # =========================================================================
    def start_clipboard_monitoring(self):
        self.monitoring_active = True
        t = threading.Thread(target=self._clipboard_monitor_loop, daemon=True)
        t.start()

    def _clipboard_monitor_loop(self):
        last_clip = ""
        while self.monitoring_active:
            try:
                clip = Derf.safe_paste()
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
