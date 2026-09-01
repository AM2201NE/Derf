_BG_CLIPBOARD = ""

def safe_clip_copy(text):
    global _BG_CLIPBOARD
    _BG_CLIPBOARD = text
    try: pyperclip.copy(text)
    except Exception: pass

def safe_clip_paste():
    global _BG_CLIPBOARD
    try:
        val = pyperclip.paste()
        if val: return val
    except Exception: pass
    return _BG_CLIPBOARD

"""
DERF BACKGROUND SERVICE (Desktop System Tray & Invisible Layer)
Uses pynput for non-admin global hotkey listeners & clipboard auto-decryption.
"""
import os, sys, re, time, threading
import pyperclip

# Import core crypto logic from Derf without starting Kivy GUI
from Derf import (
    _load_pq, contacts_load, vload, vsave, P, DATA_DIR, Session,
    id_fp, id_bundle, b64, ub64, clean_b64, feed, VAULT, derive_vault
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

# Global state for background service
ACTIVE_PEER = None
BUFFERS = {}

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

def do_hotkey_encrypt():
    global ACTIVE_PEER
    try:
        load_background_vault()

        # Simulate Ctrl+C to copy selected text
        if kb_controller:
            with kb_controller.pressed(Key.ctrl):
                kb_controller.press('c')
                kb_controller.release('c')
            time.sleep(0.2)

        selected_text = safe_clip_paste().strip()
        if not selected_text or selected_text.startswith("DERF:V1:"):
            return

        peer = ACTIVE_PEER or get_first_paired_peer()
        if not peer:
            if notification:
                notification.notify(title="Derf Background", message="No paired contacts found for encryption.")
            return

        cs = contacts_load()
        sess = Session.load(peer)

        idn = vload(P("lc_identity.json"))
        me_fp = id_fp(ub64(idn["pq_pk"]))
        peer_fp = id_fp(cs[peer])

        pkts = sess.encrypt(selected_text.encode('utf-8'), me_fp, peer_fp)
        sess.save(peer)

        cipher_text = "DERF:V1:\n" + "\n".join(b64(p) for p in pkts)
        safe_clip_copy(cipher_text)

        # Simulate Ctrl+V to paste encrypted text back
        if kb_controller:
            time.sleep(0.1)
            with kb_controller.pressed(Key.ctrl):
                kb_controller.press('v')
                kb_controller.release('v')

        if notification:
            notification.notify(
                title="Derf Encrypted",
                message=f"Encrypted message for {peer} and replaced text!"
            )
        print(f"[DERF BG] Successfully encrypted text for {peer}!")
    except Exception as e:
        print(f"[DERF BG Error] Hotkey encrypt: {e}")

def monitor_clipboard_loop():
    last_clip = ""
    pattern = re.compile(r"^DERF:V1:[A-Za-z0-9+/=\n\r\s]{50,}$")
    while True:
        try:
            time.sleep(0.5)
            load_background_vault()
            clip_text = safe_clip_paste().strip()
            if clip_text and clip_text != last_clip and pattern.match(clip_text):
                last_clip = clip_text
                raw = clip_text[8:].strip()
                lines = [l.strip() for l in raw.splitlines() if l.strip()]
                pkts = [ub64(clean_b64(l)) for l in lines]

                cs = contacts_load()
                idn = vload(P("lc_identity.json"))
                me_fp = id_fp(ub64(idn["pq_pk"]))

                paired = [n for n in cs if os.path.exists(P(f"lc_session_{n}.json"))]
                for peer in paired:
                    sess = Session.load(peer)
                    peer_fp = id_fp(cs[peer])
                    msgs = []
                    got = 0
                    for p in pkts:
                        try:
                            out = feed(sess, p, me_fp, peer_fp, BUFFERS)
                            if out: msgs.append(out.decode('utf-8')); got += 1
                        except Exception: pass
                    if got:
                        sess.save(peer)
                        dec_msg = "\n".join(msgs)
                        if notification:
                            notification.notify(
                                title=f"Derf Decrypted ({peer})",
                                message=dec_msg[:200]
                            )
                        print(f"[DERF BG DECRYPTED] {peer}: {dec_msg}")
                        break
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
    print("[*] Starting Derf Background Service...")
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
        # Keep main thread alive permanently
        print("[*] Derf Background Service running. Press Ctrl+C to stop.")
        stop_event = threading.Event()
        try:
            stop_event.wait()
        except (KeyboardInterrupt, SystemExit):
            print("[*] Stopping background service.")

if __name__ == '__main__':
    main()
