# ==========================================
# DERF QUICK PEEK (Apple Squircle Glass Overlay)
# ==========================================
import os
import sys
import time
import math
import base64
import pyperclip

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

BG_OBSIDIAN = "#0E0E10"      # Glass Obsidian Backdrop
CYAN_PRIMARY = "#00F0FF"     # Electric Cyan Accent
TEXT_MAIN = "#EEF0F8"        # Main text
SCROLL_THUMB = "#00F0FF"     # Subtle 3px Scrollbar Pill
SCROLL_TROUGH = "#181A22"    # Subtle scrollbar trough

def generate_apple_squircle(x1, y1, x2, y2, radius_pct=0.2237, smoothness=0.60, points_count=128):
    w = x2 - x1
    h = y2 - y1
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    n = 3.2 + (smoothness * 2.0)
    half_w = w / 2.0
    half_h = h / 2.0

    pts = []
    for i in range(points_count):
        angle = (2.0 * math.pi * i) / points_count
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        sign_x = 1.0 if cos_a >= 0 else -1.0
        sign_y = 1.0 if sin_a >= 0 else -1.0
        px = cx + half_w * (abs(cos_a) ** (2.0 / n)) * sign_x
        py = cy + half_h * (abs(sin_a) ** (2.0 / n)) * sign_y
        pts.extend([px, py])
    return pts

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
        self.scroll_canvas = None
        self.text_frame = None
        self._timer_id = None
        self._req_w = 320
        self._req_h = 140

    def init_ui(self):
        if not tk:
            return
        self.root = tk.Tk()
        self.root.title("Derf Peek Glass")

        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)

        TRANS_KEY = "#000001"
        self.root.configure(bg=TRANS_KEY)
        if IS_WIN32:
            try:
                self.root.wm_attributes('-transparentcolor', TRANS_KEY)
            except Exception:
                pass

        if IS_WIN32:
            try:
                hwnd = win32gui.GetParent(self.root.winfo_id())
                win32gui.SetClassLong(hwnd, win32con.GCL_STYLE,
                                      win32gui.GetClassLong(hwnd, win32con.GCL_STYLE) | win32con.CS_DROPSHADOW)
            except Exception:
                pass

        self.canvas = tk.Canvas(self.root, bg=TRANS_KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill='both', expand=True)

        self.text_frame = tk.Frame(self.canvas, bg=BG_OBSIDIAN, bd=0)

        self.scroll_canvas = tk.Canvas(self.text_frame, bg=BG_OBSIDIAN, width=6, highlightthickness=0, bd=0)

        self.text_widget = tk.Text(self.text_frame, fg=CYAN_PRIMARY, bg=BG_OBSIDIAN,
                                   font=("Segoe UI", 11, "bold"), wrap='word', bd=0, highlightthickness=0,
                                   padx=14, pady=12, insertbackground=CYAN_PRIMARY)

        def _on_text_scroll(first, last):
            self._update_scroll_pill(float(first), float(last))

        self.text_widget.config(yscrollcommand=_on_text_scroll)

        self.scroll_canvas.pack(side='right', fill='y', padx=(0, 4), pady=10)
        self.text_widget.pack(side='left', fill='both', expand=True)

        self.root.bind('<Escape>', lambda e: self.hide())
        self.root.bind('<FocusOut>', lambda e: self.hide())
        self.canvas.bind('<Button-1>', lambda e: self.hide())
        self.text_widget.bind('<Button-1>', lambda e: self.hide())

        def _on_mousewheel(event):
            if IS_WIN32:
                self.text_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                if event.num == 4:
                    self.text_widget.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.text_widget.yview_scroll(1, "units")
            self._update_scroll_pill()

        self.text_widget.bind("<MouseWheel>", _on_mousewheel)
        self.text_widget.bind("<Button-4>", _on_mousewheel)
        self.text_widget.bind("<Button-5>", _on_mousewheel)

        self.root.withdraw()

    def _update_scroll_pill(self, first=None, last=None):
        if not self.scroll_canvas: return
        if first is None or last is None:
            try:
                first, last = self.text_widget.yview()
            except Exception:
                return

        self.scroll_canvas.delete("all")
        if first <= 0.0 and last >= 1.0:
            return

        c_h = self.scroll_canvas.winfo_height()
        if c_h <= 10: c_h = 100

        y1 = first * c_h
        y2 = max(last * c_h, y1 + 16)

        self.scroll_canvas.create_rectangle(1, y1, 4, y2, fill=CYAN_PRIMARY, outline="", width=0)

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

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        max_w = min(500, int(screen_w * 0.45))
        max_h = min(360, int(screen_h * 0.45))
        min_w = 260
        min_h = 90

        char_len = len(text)
        est_lines = max(1, char_len // 30 + text.count('\n'))

        req_w = min(max(char_len * 9 + 48, min_w), max_w)
        req_h = min(max(est_lines * 22 + 28, min_h), max_h)

        self._req_w, self._req_h = req_w, req_h
        self.root.geometry(f"{req_w}x{req_h}")

        self.canvas.delete("all")
        sq_points = generate_apple_squircle(2, 2, req_w-2, req_h-2, radius_pct=0.2237, smoothness=0.60)
        self.canvas.create_polygon(sq_points, smooth=True, fill=BG_OBSIDIAN, outline=CYAN_PRIMARY, width=1.5)

        self.canvas.create_window(req_w // 2, req_h // 2, window=self.text_frame, width=req_w-8, height=req_h-8)

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

def decrypt_payload(raw_block):
    try:
        raw_idn = vload(P("lc_identity.json"))
        idn = norm_identity(raw_idn)
        return decrypt_alien_stack(raw_block, idn, custom_session_loader=load_sim_bob_session_standalone)
    except Exception as e:
        print(f"[!] Decryption error: {e}")
        return None

if __name__ == "__main__":
    peek_card = PeekCard()

    def trigger_peek():
        try:
            if keyboard:
                keyboard.send('ctrl+c')
            time.sleep(0.15)

            selected_text = clean_ciphertext_input(pyperclip.paste())
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
