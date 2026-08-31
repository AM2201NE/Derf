"""
DERF BACKGROUND SERVICE (Desktop System Tray & Invisible Layer)
- Global Hotkey: Encrypts highlighted text and replaces in-place.
- Clipboard Monitor: Detects 'DERF:V1:' Base64 packets and shows decrypted notification.
"""
import os, sys, re, time, threading
import pyperclip

# Import core crypto logic from Derf without starting Kivy GUI
from Derf import (
    _load_pq, contacts_load, vload, vsave, P, DATA_DIR, Session,
    id_fp, id_bundle, b64, ub64, clean_b64, feed, run_selftest
)

try:
    from plyer import notification
except Exception:
    notification = None

try:
    import keyboard
except Exception:
    keyboard = None

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None

# Global state for background service
ACTIVE_PEER = None
BUFFERS = {}

def get_first_paired_peer():
    cs = contacts_load()
    paired = [n for n in cs if os.path.exists(P(f"lc_session_{n}.json"))]
    return paired[0] if paired else None

def do_hotkey_encrypt():
    global ACTIVE_PEER
    try:
        if keyboard:
            keyboard.send('ctrl+c')
            time.sleep(0.15)

        selected_text = pyperclip.paste().strip()
        if not selected_text or selected_text.startswith("DERF:V1:"):
            return

        peer = ACTIVE_PEER or get_first_paired_peer()
        if not peer:
            if notification:
                notification.notify(title="Derf Background", message="No paired contacts found for encryption.")
            return

        cs = contacts_load()
        sess = Session.load(peer)
        me_fp = id_fp(id_bundle(sess.idn if hasattr(sess, 'idn') else vload(P("lc_identity.json"))))
        peer_fp = id_fp(cs[peer])

        pkts = sess.encrypt(selected_text.encode('utf-8'), me_fp, peer_fp)
        sess.save(peer)

        cipher_text = "DERF:V1:\n" + "\n".join(b64(p) for p in pkts)
        pyperclip.copy(cipher_text)

        if keyboard:
            time.sleep(0.05)
            keyboard.send('ctrl+v')

        if notification:
            notification.notify(
                title="Derf Encrypted",
                message=f"Encrypted payload for {peer} and replaced selection!"
            )
    except Exception as e:
        print(f"Hotkey encrypt error: {e}")

def monitor_clipboard_loop():
    last_clip = ""
    pattern = re.compile(r"^DERF:V1:[A-Za-z0-9+/=\n\r\s]{50,}$")
    while True:
        try:
            time.sleep(0.5)
            clip_text = pyperclip.paste().strip()
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
                                title=f"Derf Message from {peer}",
                                message=dec_msg[:200]
                            )
                        print(f"[DERF BG DECRYPTED] {peer}: {dec_msg}")
                        break
        except Exception:
            pass

def create_tray_icon():
    if not pystray:
        print("pystray not installed; running in console mode.")
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

    # Start Clipboard Monitor Thread
    t_clip = threading.Thread(target=monitor_clipboard_loop, daemon=True)
    t_clip.start()

    # Register Hotkey
    if keyboard:
        try:
            keyboard.add_hotkey('alt+shift+d', do_hotkey_encrypt)
            keyboard.add_hotkey('ctrl+shift+e', do_hotkey_encrypt)
            print("[*] Registered hotkeys: Alt+Shift+D / Ctrl+Shift+E")
        except Exception as e:
            print(f"Hotkey registration warning: {e}")

    icon = create_tray_icon()
    if icon:
        icon.run()
    else:
        while True:
            time.sleep(1)

if __name__ == '__main__':
    main()
