# derf_windows_bg.py
import os
import sys
import time
import pyperclip

# Add the parent directory to path to import derf logic
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import Alien Stack decryption logic from Derf
from Derf import (
    P, vload, norm_identity, decrypt_alien_stack, Session, ub64
)

IS_WIN32 = (sys.platform == "win32")
if IS_WIN32:
    import win32gui
    import win32con

try:
    import keyboard
except Exception:
    keyboard = None

try:
    import tkinter as tk
except Exception:
    tk = None

class GhostOverlay:
    def __init__(self):
        if not tk or not IS_WIN32:
            self.root = None
            return
        self.root = tk.Tk()
        self.root.title("Derf Decrypt Overlay")
        self.root.configure(bg='black')
        self.root.overrideredirect(True)

        hwnd = win32gui.GetParent(self.root.winfo_id())
        ex_style = win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
        win32gui.SetLayeredWindowAttributes(hwnd, 0, 204, win32con.LWA_ALPHA)

        self.label = tk.Label(self.root, text="", fg="#00FF00", bg='black', font=("Consolas", 12), justify='left')
        self.label.pack(padx=10, pady=10)
        self.root.withdraw()

    def show(self, text, x, y):
        if not self.root:
            print(f"[GHOST OVERLAY] {text}")
            return
        self.label.config(text=text)
        self.root.update_idletasks()
        self.root.geometry(f"+{x}+{y}")
        self.root.deiconify()
        self.root.after(8000, self.root.withdraw) # Auto-hide after 8s

    def run(self):
        if self.root:
            self.root.mainloop()

overlay = GhostOverlay()
overlay_enabled = True

def toggle_overlay():
    global overlay_enabled
    overlay_enabled = not overlay_enabled
    print(f"[*] Overlay is now: {'ON' if overlay_enabled else 'OFF'}")

if keyboard:
    try:
        keyboard.add_hotkey('ctrl+shift+d', toggle_overlay)
    except Exception:
        pass

def load_sim_bob_session_standalone():
    p = P("lc_sim_bob_session.json")
    if not os.path.exists(p): return None, None
    try:
        d = vload(p)
        bob_sess = Session(
            sid=ub64(d["sid"]), root=b"", role=d["role"],
            sck=ub64(d["sck"]), rck=ub64(d["rck"]),
            sn=d["sn"], rn=d["rn"],
            hsend=ub64(d["hsend"]), hrecv=ub64(d["hrecv"]),
            skipped={}
        )
        bob_idn = norm_identity(d["bob_idn"])
        return bob_sess, bob_idn
    except Exception:
        return None, None

def decrypt_text(raw_text):
    """Minimal decryption logic for the background script using Alien Stack"""
    try:
        raw_idn = vload(P("lc_identity.json"))
        idn = norm_identity(raw_idn)
        return decrypt_alien_stack(raw_text, idn, custom_session_loader=load_sim_bob_session_standalone)
    except Exception:
        return None

def monitor_clipboard():
    last_text = ""
    print("[*] Derf Windows Background Service Running. Press Ctrl+Shift+D to toggle overlay.")
    while True:
        try:
            current = pyperclip.paste()
            if current and current != last_text and "DERF:V1:" in current:
                if overlay_enabled:
                    decrypted = decrypt_text(current)
                    if decrypted:
                        if IS_WIN32:
                            x, y = win32gui.GetCursorPos()
                        else:
                            x, y = 100, 100
                        overlay.show(decrypted, x + 20, y + 20)
            last_text = current
        except Exception:
            pass
        time.sleep(0.5)

if __name__ == "__main__":
    import threading
    threading.Thread(target=monitor_clipboard, daemon=True).start()
    overlay.run()
