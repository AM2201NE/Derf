"""
DERF BACKGROUND SERVICE (Desktop System Tray & Zero-Latency Layer)
Uses pynput + Win32 native keybd_event for instant single-click hotkey response.
Zero-delay instant Alt+Shift+D / Ctrl+Shift+E text replacement.
"""
import os, sys, re, time, threading
import pyperclip

# Fast local clipboard fallback
_BG_CLIPBOARD = ""

def safe_clip_copy(text):
    global _BG_CLIPBOARD
    _BG_CLIPBOARD = text
    try:
        pyperclip.copy(text)
    except Exception:
        pass

def safe_clip_paste():
    global _BG_CLIPBOARD
    try:
        val = pyperclip.paste()
        if val is not None:
            return val
    except Exception:
        pass
    return _BG_CLIPBOARD

# Import core crypto logic & Alien Stack from Derf without starting Kivy GUI
from Derf import (
    _load_pq, contacts_load, vload, vsave, P, DATA_DIR, Session,
    id_fp, id_bundle, b64, ub64, clean_b64, feed, VAULT, derive_vault,
    norm_identity, encrypt_alien_stack, decrypt_alien_stack
)

try:
    from plyer import notification
except Exception:
    notification = None

try:
    from pynput import keyboard
    from pynput.keyboard import Controller, Key
    kb_controller = Controller()
except Exception:
    keyboard = None
    kb_controller = None

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None

# Native Win32 keyboard event injection for zero-latency key release on Windows
IS_WINDOWS = (sys.platform == "win32")
if IS_WINDOWS:
    import ctypes
    user32 = ctypes.windll.user32
    VK_SHIFT = 0x10
    VK_CONTROL = 0x11
    VK_MENU = 0x12  # Alt
    VK_LALT = 0xA4
    VK_RALT = 0xA5
    VK_LSHIFT = 0xA0
    VK_RSHIFT = 0xA1
    KEYEVENTF_KEYUP = 0x0002

    def release_modifiers_native():
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_LALT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_RALT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_LSHIFT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_RSHIFT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    def trigger_copy_native():
        release_modifiers_native()
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(ord('C'), 0, 0, 0)
        user32.keybd_event(ord('C'), 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    def trigger_paste_native():
        release_modifiers_native()
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(ord('V'), 0, 0, 0)
        user32.keybd_event(ord('V'), 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
else:
    def release_modifiers_native():
        if kb_controller:
            for k in [Key.alt, Key.alt_l, Key.alt_r, Key.shift, Key.shift_l, Key.shift_r, Key.ctrl, Key.ctrl_l, Key.ctrl_r]:
                try: kb_controller.release(k)
                except Exception: pass

    def trigger_copy_native():
        release_modifiers_native()
        if kb_controller:
            with kb_controller.pressed(Key.ctrl):
                kb_controller.press('c')
                kb_controller.release('c')

    def trigger_paste_native():
        release_modifiers_native()
        if kb_controller:
            with kb_controller.pressed(Key.ctrl):
                kb_controller.press('v')
                kb_controller.release('v')

# Global state for background service
ACTIVE_PEER = None

def load_background_vault():
    global VAULT
    v_token_path = P(".vault_token")
    if os.path.exists(v_token_path):
        try:
            raw = open(v_token_path, "rb").read()
            if len(raw) == 32:
                VAULT = raw
                return True
        except Exception:
            pass
    return False

def get_first_paired_peer():
    cs = contacts_load()
    paired = [n for n in cs if os.path.exists(P(f"lc_session_{n}.json"))]
    return paired[0] if paired else None

_hotkey_lock = threading.Lock()

def do_hotkey_encrypt():
    if not _hotkey_lock.acquire(blocking=False):
        return
    try:
        load_background_vault()

        trigger_copy_native()
        time.sleep(0.04)

        selected_text = safe_clip_paste().strip()
        if not selected_text or selected_text.startswith("DERF:V1:"):
            return

        peer = ACTIVE_PEER or get_first_paired_peer()
        if not peer:
            # notification.notify(title="Derf Background", message="No paired contacts found for encryption.")
            return

        raw_idn = vload(P("lc_identity.json"))
        idn = norm_identity(raw_idn)

        cipher_text = encrypt_alien_stack(selected_text, peer, idn)
        if not cipher_text: return

        chunks = [b.strip() for b in re.split(r'\n\s*\n', cipher_text.strip()) if b.strip() and "DERF:V1:" in b]
        if not chunks:
            chunks = [b.strip() for b in cipher_text.strip().split('\n') if b.strip()]

        if len(chunks) == 1:
            safe_clip_copy(chunks[0])
            time.sleep(0.03)
            trigger_paste_native()
        else:
            for chunk in chunks:
                safe_clip_copy(chunk)
                time.sleep(0.03)
                trigger_paste_native()
                time.sleep(0.04)
                if IS_WINDOWS:
                    user32.keybd_event(0x0D, 0, 0, 0)
                    user32.keybd_event(0x0D, 0, KEYEVENTF_KEYUP, 0)
                elif kb_controller:
                    kb_controller.press(Key.enter)
                    kb_controller.release(Key.enter)
                time.sleep(0.18)

        if notification:
            notification.notify(
                title="Derf Encrypted",
                message=f"Encrypted message for {peer} & replaced instantly!"
            )
        print(f"[DERF BG] Encrypted & replaced text for {peer} instantly!")
    except Exception as e:
        print(f"[DERF BG Error] Hotkey encrypt: {e}")
    finally:
        _hotkey_lock.release()

def monitor_clipboard_loop():
    last_clip = ""
    while True:
        try:
            time.sleep(0.3)
            load_background_vault()
            clip_text = safe_clip_paste().strip()
            if clip_text and clip_text != last_clip and "DERF:V1:" in clip_text:
                last_clip = clip_text
                raw_idn = vload(P("lc_identity.json"))
                idn = norm_identity(raw_idn)

                dec_msg = decrypt_alien_stack(clip_text, idn)
                if dec_msg:
                    # notification.notify(
                            title="Derf Decrypted",
                            message=dec_msg[:200]
                        )
                    print(f"[DERF BG DECRYPTED] {dec_msg}")
        except Exception:
            pass

def create_tray_icon():
    if not pystray:
        print("pystray not installed; running in background console mode.")
        return None

    img = Image.new('RGB', (64, 64), color=(0, 240, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([16, 16, 48, 48], fill=(14, 14, 16))

    def on_exit(icon, item):
        icon.stop()
        sys.exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Derf PQ+FS Active", lambda: None, enabled=False),
        pystray.MenuItem("Exit", on_exit)
    )
    return pystray.Icon("Derf", img, "Derf Background Service", menu)

def main():
    print("[*] Starting High-Performance Zero-Latency Derf Background Service...")
    load_background_vault()

    # Start Clipboard Monitor Thread
    t_clip = threading.Thread(target=monitor_clipboard_loop, daemon=True)
    t_clip.start()

    # Register pynput Global Hotkeys
    hotkey_listener = None
    if keyboard:
        try:
            hotkey_listener = keyboard.GlobalHotKeys({
                '<alt>+<shift>+d': do_hotkey_encrypt,
                '<ctrl>+<shift>+e': do_hotkey_encrypt
            })
            hotkey_listener.start()
            print("[*] Registered pynput global hotkeys: Alt+Shift+D / Ctrl+Shift+E")
        except Exception as e:
            print(f"Hotkey listener status: {e}")

    icon = create_tray_icon()
    if icon:
        icon.run()
    else:
        print("[*] Derf Background Service running. Press Ctrl+C to stop.")
        stop_event = threading.Event()
        try:
            stop_event.wait()
        except (KeyboardInterrupt, SystemExit):
            print("[*] Stopping background service.")

if __name__ == '__main__':
    main()
