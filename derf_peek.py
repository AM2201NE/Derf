# ==========================================
# DERF QUICK PEEK (The "Glass Card" Overlay)
# ==========================================
import os
import sys
import time
import base64
import pyperclip

# Safely import core logic from your main app without triggering the Kivy UI
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
    import tkinter as tk
except Exception:
    tk = None

IS_WIN32 = (sys.platform == "win32")
if IS_WIN32:
    import win32gui
    import win32con

# ================= DERF STITCH DESIGN TOKENS =================
BG_OBSIDIAN = "#0E0E10"      # Main background
CYAN_PRIMARY = "#00F0FF"     # Accent/Header
TEXT_MAIN = "#EEF0F8"        # Main text
BORDER_COLOR = "#292C38"     # Subtle border
TEXT_MUTED = "#555555"       # Footer hint
# =============================================================

class PeekCard:
    def __init__(self):
        if not tk:
            self.root = None
            return
        self.root = tk.Tk()
        self.root.title("Derf Peek")
        self.root.configure(bg=BG_OBSIDIAN)

        # 1. Make it frameless, transparent to clicks (optional), and always on top
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)

        # 2. Add a native Windows drop shadow for that "floating card" feel
        if IS_WIN32:
            try:
                hwnd = win32gui.GetParent(self.root.winfo_id())
                win32gui.SetClassLong(hwnd, win32con.GCL_STYLE,
                                      win32gui.GetClassLong(hwnd, win32con.GCL_STYLE) | win32con.CS_DROPSHADOW)
            except Exception:
                pass

        # 3. Build the UI (Border -> Inner Content)
        self.frame = tk.Frame(self.root, bg=BORDER_COLOR, padx=2, pady=2)
        self.frame.pack(fill='both', expand=True)

        self.inner = tk.Frame(self.frame, bg=BG_OBSIDIAN, padx=20, pady=20)
        self.inner.pack(fill='both', expand=True)

        # Header
        self.header = tk.Label(self.inner, text="🔓 DERF DECRYPTED", bg=BG_OBSIDIAN, fg=CYAN_PRIMARY,
                               font=("Segoe UI", 10, "bold"), anchor='w')
        self.header.pack(fill='x', pady=(0, 12))

        # Decrypted Text (Wraps automatically)
        self.text_label = tk.Label(self.inner, text="", bg=BG_OBSIDIAN, fg=TEXT_MAIN,
                                   font=("Segoe UI", 12), justify='left', wraplength=450, anchor='nw')
        self.text_label.pack(fill='both', expand=True)

        # Footer hint
        self.footer = tk.Label(self.inner, text="Press Esc or click outside to close", bg=BG_OBSIDIAN,
                               fg=TEXT_MUTED, font=("Segoe UI", 9), anchor='e')
        self.footer.pack(fill='x', pady=(12, 0))

        # 4. Bindings to close the card
        self.root.bind('<Escape>', lambda e: self.hide())
        self.root.bind('<FocusOut>', lambda e: self.hide())
        self.root.bind('<Button-1>', lambda e: self.hide()) # Click anywhere to close

        self.root.withdraw() # Hide initially

    def show(self, decrypted_text, x, y):
        if not self.root:
            print(f"[DERF PEEK DECRYPTED] {decrypted_text}")
            return
        self.text_label.config(text=decrypted_text)
        self.root.update_idletasks()

        # Calculate size to ensure it doesn't go off-screen
        win_width = self.root.winfo_reqwidth() + 40
        win_height = self.root.winfo_reqheight() + 40
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # Position slightly below and to the right of the cursor
        final_x = min(x + 15, screen_w - win_width)
        final_y = min(y + 15, screen_h - win_height)

        self.root.geometry(f"+{final_x}+{final_y}")
        self.root.deiconify()
        self.root.focus_force()

    def hide(self):
        if self.root:
            self.root.withdraw()

    def run(self):
        if self.root:
            self.root.mainloop()

# ================= DECRYPTION ENGINE =================
def decrypt_payload(raw_block):
    """Minimal, robust decryption logic for the Peek tool using Alien Stack"""
    try:
        raw_idn = vload(P("lc_identity.json"))
        idn = norm_identity(raw_idn)
        return decrypt_alien_stack(raw_block, idn, custom_session_loader=load_sim_bob_session_standalone)
    except Exception as e:
        print(f"[!] Decryption error: {e}")
        return None

# ================= MAIN EXECUTION =================
if __name__ == "__main__":
    peek_card = PeekCard()

    def trigger_peek():
        """Triggered by Alt+Shift+Q"""
        try:
            # 1. Copy the currently highlighted text
            if keyboard:
                keyboard.send('ctrl+c')
            time.sleep(0.15) # Brief pause for OS clipboard to update

            selected_text = pyperclip.paste().strip()

            # 2. Check if it's a Derf message
            if "DERF:V1:" in selected_text:
                decrypted = decrypt_payload(selected_text)
                if decrypted:
                    if IS_WIN32:
                        x, y = win32gui.GetCursorPos()
                    else:
                        x, y = 100, 100
                    peek_card.show(decrypted, x, y)
                else:
                    print("[!] Could not decrypt. Wrong session, stale message, or corrupted data.")
            else:
                print("[*] No Derf payload selected.")
        except Exception as e:
            print(f"[!] Peek error: {e}")

    print("=========================================")
    print("  DERF QUICK PEEK ACTIVE")
    print("  Highlight text in any app and press:")
    print("  [ Alt + Shift + Q ] to decrypt")
    print("=========================================")

    # Register the global hotkey Alt+Shift+Q
    if keyboard:
        try:
            keyboard.add_hotkey('alt+shift+q', trigger_peek)
        except Exception as e:
            print(f"[!] Hotkey error: {e}")

    peek_card.run()
