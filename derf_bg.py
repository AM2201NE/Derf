# Derf Background Service (Desktop)
# Runs silently in system tray (or as a daemon).
# Requires: keyboard, plyer, pyperclip (optional) – install via pip if needed.
import os, sys, time, threading, base64, binascii, hashlib, hmac, struct, json, glob
import traceback

# Safe import of crypto from derf (no Kivy GUI start)
# We assume derf.py is in the same directory or on PYTHONPATH.
# Determine the directory of this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DERF_PATH = os.path.join(SCRIPT_DIR, 'derf.py')
if not os.path.exists(DERF_PATH):
    # fallback: maybe one level up
    DERF_PATH = os.path.join(SCRIPT_DIR, '..', 'derf.py')
if not os.path.exists(DERF_PATH):
    print('[DERF BG] Cannot locate derf.py – aborting')
    sys.exit(1)

# Load only the needed symbols by executing the module but skipping Kivy GUI parts.
# We set a flag to skip heavy GUI imports if possible, but derf imports Kivy unconditionally at top.
# However Kivy does not start the App unless App().run() is called, which we never do.
# So a plain import is safe for our purpose.
try:
    # Temporarily suppress stdout/stderr to avoid noisy Kivy logs? Keep as-is.
    sys.path.insert(0, SCRIPT_DIR)
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("derf_core", DERF_PATH)
    _derf = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_derf)
    # Pull needed symbols
    PQ_KEM = _derf.PQ_KEM
    Session = _derf.Session
    lca_encrypt = _derf.lca_encrypt
    lca_decrypt = _derf.lca_decrypt
    P = _derf.P
    DATA_DIR = _derf.DATA_DIR
    id_bundle = _derf.id_bundle
    id_fp = _derf.id_fp
    contacts_load = _derf.contacts_load
    now8 = _derf.now8
    check_fresh = _derf.check_fresh
    pad = _derf.pad
    unpad = _derf.unpad
    b64 = _derf.b64
    ub64 = _derf.ub64
    clean_b64 = _derf.clean_b64
    keygen = _derf.keygen
    kdf_ck = _derf.kdf_ck
    tlv = _derf.tlv
    untlv = _derf.untlv
    hmac_sha256 = _derf.hmac_sha256
    hkdf = _derf.hkdf
    APP_AAD = _derf.APP_AAD
    CHUNK = _derf.CHUNK
    HJ = _derf.HJ
    PAYLOAD_MAX = _derf.PAYLOAD_MAX
    PACKET = _derf.PACKET
    VAULT = _derf.VAULT  # may be empty if vault not unlocked; functions will raise if used without vault
    # Some functions needed from Session
    # Safety code
    safety_code = _derf.safety_code
    # feed function? We'll reimplement using Session.try_decrypt
    # We need the feed function from derf
    feed = _derf.feed
    # Also need the identity (idn) from the main app? We can load it from vault if VAULT is set.
    # We'll attempt to load the identity when needed.
except Exception as e:
    print(f'[DERF BG] Failed to import crypto from derf: {e}')
    traceback.print_exc()
    sys.exit(1)

# Optional: clipboard and hotkey libs
try:
    import keyboard  # for global hotkey
except Exception:
    keyboard = None
    print('[DERF BG] keyboard module not found – hotkey disabled')

try:
    import pyperclip  # cross-platform clipboard
except Exception:
    pyperclip = None

try:
    from plyer import notification  # desktop notifications
except Exception:
    notification = None
    print('[DERF BG] plyer not found – notifications disabled')

# Fallback to Tkinter or raw clipboard if needed
def _clipboard_get():
    if pyperclip:
        try: return pyperclip.paste()
        except: pass
    # Try Tkinter
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        data = r.clipboard_get()
        r.destroy()
        return data
    except Exception:
        pass
    return ''

def _clipboard_set(text):
    if pyperclip:
        try: pyperclip.copy(text); return True
        except: pass
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception:
        pass
    return False

# Simulate Ctrl+V paste via keyboard library (if available)
def _simulate_ctrl_v():
    if keyboard:
        try:
            keyboard.send('ctrl+v')
            return True
        except Exception:
            pass
    # fallback: nothing
    return False

HOTKEY = 'alt+shift+d'

def _load_identity_and_sessions():
    """Try to load identity and sessions using the current VAULT.
    Returns (idn, cs) or (None, None) if vault not unlocked or load fails."""
    try:
        # Check if VAULT is set (non-empty)
        if not hasattr(_derf, 'VAULT') or not _derf.VAULT:
            return None, None
        # Load identity
        identity_data = _derf.vload(_derf.P("lc_identity.json"))
        idn = _derf.norm_identity(identity_data)
        if not idn:
            return None, None
        cs = _derf.contacts_load()
        return idn, cs
    except Exception:
        return None, None

def _hotkey_worker():
    """When hotkey pressed: get selection (we approximate by clipboard copy of selection),
    encrypt, wrap, copy back, and simulate paste."""
    if not keyboard:
        return
    def on_activate():
        try:
            # 1. Copy current selection (Ctrl+C) – we assume user has selected text
            keyboard.send('ctrl+c')
            time.sleep(0.15)  # allow clipboard to update
            raw = _clipboard_get()
            if not raw or not raw.strip():
                return
            # 2. Load identity and sessions (requires vault unlocked)
            idn, cs = _load_identity_and_sessions()
            if not idn or not cs:
                return
            paired = [n for n in cs if os.path.exists(P(f"lc_session_{n}.json"))]
            if not paired:
                # No paired contacts; cannot encrypt
                return
            peer = paired[0]  # pick first
            sess = Session.load(peer)
            me_fp = id_fp(id_bundle(idn))
            peer_fp = id_fp(cs[peer])
            pkts = sess.encrypt(raw.encode('utf-8'), me_fp, peer_fp)
            sess.save(peer)
            out_b64 = '\n'.join(b64(p) for p in pkts)
            wrapped = 'DERF:V1:' + out_b64
            _clipboard_set(wrapped)
            time.sleep(0.05)
            _simulate_ctrl_v()
        except Exception as e:
            # Silent fail – do not pop up UI
            pass
    keyboard.add_hotkey(HOTKEY, on_activate)
    keyboard.wait()  # block

def _clipboard_monitor():
    """Background thread: check clipboard every 0.5s for DERF:V1: pattern,
    decrypt and show desktop notification."""
    import re
    pattern = re.compile(r'^DERF:V1:[A-Za-z0-9+/=\n\s]{50,}$')
    last = ''
    while True:
        try:
            text = _clipboard_get()
            if text and isinstance(text, str) and text != last:
                last = text
                if pattern.match(text):
                    stripped = text[len('DERF:V1:'):].strip()
                    if stripped:
                        # Try decrypt with any paired session
                        idn, cs = _load_identity_and_sessions()
                        if not idn or not cs:
                            # Vault not unlocked, skip
                            continue
                        paired = [n for n in cs if os.path.exists(P(f"lc_session_{n}.json"))]
                        for peer in paired:
                            try:
                                sess = Session.load(peer)
                                me_fp = id_fp(id_bundle(idn))
                                peer_fp = id_fp(cs[peer])
                                lines = [l.strip() for l in stripped.splitlines() if l.strip()]
                                buf = {}
                                msgs = []
                                for ln in lines:
                                    try:
                                        pkt = ub64(clean_b64(ln))
                                        out = feed(sess, pkt, me_fp, peer_fp, buf)
                                        if out:
                                            msgs.append(out.decode('utf-8', 'replace'))
                                    except Exception:
                                        pass
                                if msgs:
                                    sess.save(peer)
                                    plain = '\n'.join(msgs)
                                    # Show notification
                                    if notification:
                                        notification.notify(
                                            title='DERF Decrypted',
                                            message=plain[:200],
                                            app_name='Derf',
                                            timeout=10
                                        )
                                    else:
                                        # fallback: print to console
                                        print('[DERF BG] Decrypted:', plain[:100])
                                    break  # stop after first success
                            except Exception:
                                continue
        except Exception:
            pass
        time.sleep(0.5)

def main():
    print('[DERF BG] Starting background service...')
    threads = []
    if keyboard:
        t1 = threading.Thread(target=_hotkey_worker, daemon=True)
        t1.start()
        threads.append(t1)
        print('[DERF BG] Hotkey Alt+Shift+D registered (safe — D is near modifiers, zero conflicts)')
    t2 = threading.Thread(target=_clipboard_monitor, daemon=True)
    t2.start()
    threads.append(t2)
    print('[DERF BG] Clipboard monitor active')
    # Keep main alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('[DERF BG] Stopping')

if __name__ == '__main__':
    main()
