# derf_windows_bg.py
import os
import sys
import time
import base64
import pyperclip

# Add the parent directory to path to import derf logic
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import ONLY what we need to avoid launching the Kivy UI
from Derf import (
    P, DATA_DIR, PACKET, ALIEN_COMPRESSION_ENABLED,
    zstd_decompressor, zlib, Session, contacts_load,
    id_bundle, id_fp, feed, ub64, clean_b64, b64
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

def decrypt_text(raw_block):
    """Minimal decryption logic for the background script"""
    try:
        is_compressed = False
        if raw_block.startswith("DERF:V1:C:"):
            raw_block = raw_block[10:]; is_compressed = True
        elif raw_block.startswith("DERF:V1:R:"):
            raw_block = raw_block[10:]
        elif raw_block.startswith("DERF:V1:"):
            raw_block = raw_block[8:]

        clean_block = raw_block.replace(' ', '').replace('\n', '')
        try:
            combined_binary = base64.b85decode(clean_block)
        except Exception:
            combined_binary = base64.b64decode(clean_block)

        pkts = [combined_binary[i:i + PACKET] for i in range(0, len(combined_binary), PACKET)]

        cs = contacts_load()
        me_fp = id_fp(id_bundle({"pq_pk": b"dummy"})) # Simplified for background check

        for peer, pub_bytes in cs.items():
            if os.path.exists(P(f"lc_session_{peer}.json")):
                sess = Session.load(peer)
                for p in pkts:
                    try:
                        out = feed(sess, p, me_fp, id_fp(pub_bytes), {})
                        if out:
                            if is_compressed:
                                try:
                                    if ALIEN_COMPRESSION_ENABLED and zstd_decompressor:
                                        out = zstd_decompressor.decompress(out)
                                    else:
                                        out = zlib.decompress(out)
                                except Exception:
                                    pass
                            return out.decode('utf-8', errors='replace')
                    except Exception:
                        pass
    except Exception:
        return None
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
