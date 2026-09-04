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

import math

def draw_apple_squircle(canvas, x1, y1, x2, y2, radius_pct=0.2237, smoothness=0.60, **kwargs):
    w = x2 - x1
    h = y2 - y1
    n = 3.2 + (smoothness * 2.0)

    points = []
    steps = 64
    for i in range(steps):
        angle = (2 * math.pi * i) / steps
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        sign_x = 1 if cos_a >= 0 else -1
        sign_y = 1 if sin_a >= 0 else -1

        px = (w / 2.0) * (abs(cos_a) ** (2.0 / n)) * sign_x + (x1 + w / 2.0)
        py = (h / 2.0) * (abs(sin_a) ** (2.0 / n)) * sign_y + (y1 + h / 2.0)

        points.extend([px, py])

    return canvas.create_polygon(points, smooth=True, **kwargs)

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


class PeekCard:
    def __init__(self):
        self.root = None
        self.canvas = None
        self.text_widget = None
        self.scrollbar = None
        self.text_frame = None
        self._timer_id = None

    def init_ui(self):
        if not tk:
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

        # Canvas for smooth rounded glass card background
        self.canvas = tk.Canvas(self.root, bg=TRANS_KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill='both', expand=True)

        # Inner Frame holding scrollable Text widget
        self.text_frame = tk.Frame(self.canvas, bg=BG_OBSIDIAN, bd=0)

        self.scrollbar = tk.Scrollbar(self.text_frame, bg=BG_OBSIDIAN, activebackground=CYAN_PRIMARY, troughcolor=BG_OBSIDIAN, bd=0, width=8)
        self.text_widget = tk.Text(self.text_frame, fg=CYAN_PRIMARY, bg=BG_OBSIDIAN,
                                   font=("Segoe UI", 11, "bold"), wrap='word', bd=0, highlightthickness=0,
                                   padx=12, pady=10, yscrollcommand=self.scrollbar.set, insertbackground=CYAN_PRIMARY)
        self.scrollbar.config(command=self.text_widget.yview)

        self.scrollbar.pack(side='right', fill='y')
        self.text_widget.pack(side='left', fill='both', expand=True)

        # Bindings to dismiss
        self.root.bind('<Escape>', lambda e: self.hide())
        self.root.bind('<FocusOut>', lambda e: self.hide())
        self.canvas.bind('<Button-1>', lambda e: self.hide())
        self.text_widget.bind('<Button-1>', lambda e: self.hide())

        # Mousewheel scrolling bindings
        def _on_mousewheel(event):
            if IS_WIN32:
                self.text_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                if event.num == 4:
                    self.text_widget.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.text_widget.yview_scroll(1, "units")

        self.text_widget.bind("<MouseWheel>", _on_mousewheel)
        self.text_widget.bind("<Button-4>", _on_mousewheel)
        self.text_widget.bind("<Button-5>", _on_mousewheel)

        self.root.withdraw()

    def run(self):
        self.init_ui()
        if self.root:
            self.root.mainloop()

    def show(self, text, x, y):
        if not self.root:
            print(f"[DERF PEEK] {text}")
            return
        self.root.after(0, lambda: self._show_impl(text, x, y))

    def _show_impl(self, text, x, y):
        self.text_widget.config(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", text)
        self.text_widget.config(state="disabled")

        # Screen dimensions
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        max_w = min(520, int(screen_w * 0.48))
        max_h = min(380, int(screen_h * 0.48))
        min_w = 280
        min_h = 90

        # Calculate dynamic rectangular size based on text length & lines
        char_len = len(text)
        est_lines = max(1, char_len // 32 + text.count('\n'))
        req_w = min(max(char_len * 9 + 50, min_w), max_w)
        req_h = min(max(est_lines * 22 + 28, min_h), max_h)

        self.root.geometry(f"{req_w}x{req_h}")

        # Redraw rounded glass card background
        self.canvas.delete("all")
        draw_apple_squircle(self.canvas, 2, 2, req_w-2, req_h-2, radius_pct=0.2237, smoothness=0.60,
                            fill=BG_OBSIDIAN, outline=CYAN_PRIMARY, width=1.5)

        # Embed text frame inside canvas
        self.canvas.create_window(req_w // 2, req_h // 2, window=self.text_frame, width=req_w-6, height=req_h-6)

        # Position near cursor, ensuring window stays on screen
        final_x = min(max(x + 15, 10), screen_w - req_w - 20)
        final_y = min(max(y + 15, 10), screen_h - req_h - 20)

        self.root.geometry(f"+{final_x}+{final_y}")
        self.root.deiconify()

        if IS_WIN32:
            try:
                hwnd = win32gui.GetParent(self.root.winfo_id())
                win32gui.SetWindowPos(
                    hwnd, win32con.HWND_TOPMOST,
                    final_x, final_y, req_w, req_h,
                    win32con.SWP_SHOWWINDOW
                )
            except Exception as e:
                print(f"SetWindowPos error: {e}")

        if self._timer_id:
            try: self.root.after_cancel(self._timer_id)
            except Exception: pass
        self._timer_id = self.root.after(10000, self.hide)

    def hide(self):
        if self.root:
            self.root.withdraw()

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
            time.sleep(0.15)

            selected_text = clean_ciphertext_input(pyperclip.paste())

            # 2. Check if it's a Derf message
            selected_text = clean_ciphertext_input(selected_text)
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