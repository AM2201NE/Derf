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
# =============================================================

def draw_rounded_rect(canvas, x1, y1, x2, y2, radius=12, **kwargs):
    points = [
        x1+radius, y1,
        x1+radius, y1,
        x2-radius, y1,
        x2-radius, y1,
        x2, y1,
        x2, y1+radius,
        x2, y1+radius,
        x2, y2-radius,
        x2, y2-radius,
        x2, y2,
        x2-radius, y2,
        x2-radius, y2,
        x1+radius, y2,
        x1+radius, y2,
        x1, y2,
        x1, y2-radius,
        x1, y2-radius,
        x1, y1+radius,
        x1, y1+radius,
        x1, y1
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)

class PeekCard:
    def __init__(self):
        if not tk:
            self.root = None
            return
        self.root = tk.Tk()
        self.root.title("Derf Peek Glass")

        # Frameless & Always On Top
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)

        # Transparency Keying for true borderless rounded glass
        TRANS_KEY = "#000001"
        self.root.configure(bg=TRANS_KEY)
        if IS_WIN32:
            try:
                self.root.wm_attributes('-transparentcolor', TRANS_KEY)
            except Exception:
                pass

        # Native Windows Drop Shadow
        if IS_WIN32:
            try:
                hwnd = win32gui.GetParent(self.root.winfo_id())
                win32gui.SetClassLong(hwnd, win32con.GCL_STYLE,
                                      win32gui.GetClassLong(hwnd, win32con.GCL_STYLE) | win32con.CS_DROPSHADOW)
            except Exception:
                pass

        # Canvas for smooth rounded glass card
        self.canvas = tk.Canvas(self.root, bg=TRANS_KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill='both', expand=True)

        # Label embedded inside canvas for decrypted text
        self.label = tk.Label(self.canvas, text="", fg=CYAN_PRIMARY, bg=BG_OBSIDIAN,
                              font=("Segoe UI", 11, "bold"), justify='left', wraplength=420)

        # Bindings to dismiss
        self.root.bind('<Escape>', lambda e: self.hide())
        self.root.bind('<FocusOut>', lambda e: self.hide())
        self.canvas.bind('<Button-1>', lambda e: self.hide())
        self.label.bind('<Button-1>', lambda e: self.hide())

        self.root.withdraw()
        self._timer_id = None

    def show(self, text, x, y):
        if not self.root:
            print(f"[DERF PEEK] {text}")
            return
        # Thread-safe dispatch
        self.root.after(0, lambda: self._show_impl(text, x, y))

    def _show_impl(self, text, x, y):
        self.label.config(text=text)

        # Calculate dynamic size based on text length
        self.label.update_idletasks()
        req_w = min(max(self.label.winfo_reqwidth() + 32, 180), 460)
        req_h = self.label.winfo_reqheight() + 24

        self.root.geometry(f"{req_w}x{req_h}")

        # Clear & redraw rounded glass card background
        self.canvas.delete("all")
        draw_rounded_rect(self.canvas, 2, 2, req_w-2, req_h-2, radius=14,
                          fill=BG_OBSIDIAN, outline=CYAN_PRIMARY, width=1.5)

        # Position text label at center of canvas
        self.canvas.create_window(req_w // 2, req_h // 2, window=self.label, anchor='center')

        # Position near cursor, ensuring window stays on screen
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        final_x = min(max(x + 15, 10), screen_w - req_w - 20)
        final_y = min(max(y + 15, 10), screen_h - req_h - 20)

        self.root.geometry(f"+{final_x}+{final_y}")
        self.root.deiconify()
        self.root.focus_force()

        if self._timer_id:
            try: self.root.after_cancel(self._timer_id)
            except Exception: pass
        self._timer_id = self.root.after(6000, self.hide)

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
            # 1. Copy currently highlighted text
            if keyboard:
                keyboard.send('ctrl+c')
            time.sleep(0.12)

            selected_text = pyperclip.paste().strip()

            # 2. Check if it's a Derf message
            if "DERF:V1:" in selected_text:
                decrypted = decrypt_payload(selected_text)
                if decrypted:
                    x, y = 100, 100
                    if IS_WIN32:
                        try:
                            x, y = win32gui.GetCursorPos()
                        except Exception: pass
                    peek_card.show(decrypted, x, y)
                else:
                    print("[!] Could not decrypt. Wrong session, stale message, or corrupted data.")
            else:
                print("[*] No Derf payload selected.")
        except Exception as e:
            print(f"[!] Peek error: {e}")

    print("=========================================")
    print("  DERF QUICK PEEK GLASS CARD ACTIVE")
    print("  Highlight text in any app and press:")
    print("  [ Alt + Shift + Q ] to decrypt")
    print("=========================================")

    if keyboard:
        try:
            keyboard.add_hotkey('alt+shift+q', trigger_peek)
        except Exception as e:
            print(f"[!] Hotkey error: {e}")

    peek_card.run()
