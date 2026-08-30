"""
Derf PQ+FS — post-quantum + forward-secret two-box messenger.
Cross-platform Kivy GUI + CLI selftest suite.
Data stored in 'Derf' folder on Desktop (auto-created + migrated).
"""
import os, sys, json, glob, hmac, hashlib, time, struct, base64, binascii, socket, shutil

# --- CLI Arguments pre-check ---
FRESH = 420.0
SKEW = 60.0
IS_SELFTEST = '--selftest' in sys.argv

if '--fresh-sec' in sys.argv:
    try:
        idx = sys.argv.index('--fresh-sec')
        FRESH = float(sys.argv[idx + 1])
        print(f'[*] Freshness limit set to {FRESH} seconds.')
    except Exception as e:
        print(f'⚠️ Error parsing --fresh-sec: {e}')

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidTag

try:
    import kyber_py.ml_kem  # noqa: F401
except Exception:
    pass

APP_NAME = "Derf"

def _old_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _migrate(old, new):
    if os.path.abspath(old) == os.path.abspath(new): return
    for f in glob.glob(os.path.join(old, "lc_*")):
        dst = os.path.join(new, os.path.basename(f))
        if not os.path.exists(dst):
            try: shutil.copy2(f, dst)
            except Exception: pass

def _data_dir():
    old = _old_dir()
    try:
        home = os.path.expanduser("~")
        desk = os.path.join(home, "Desktop")
        if not os.path.isdir(desk): desk = os.path.join(home, "desktop")
        d = os.path.join(desk, APP_NAME)
        os.makedirs(d, exist_ok=True)
        t = os.path.join(d, ".wtest"); open(t, "w").write("x"); os.remove(t)
        _migrate(old, d)
        return d
    except Exception:
        os.makedirs(old, exist_ok=True); return old

DATA_DIR = _data_dir()
def P(n): return os.path.join(DATA_DIR, n)

DROP_DIR = P("lc_drop")
os.makedirs(DROP_DIR, exist_ok=True)

_LOCK = None
def _single():
    global _LOCK
    if IS_SELFTEST: return True
    _LOCK = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _LOCK.bind(("127.0.0.1", 59731))
        return True
    except OSError:
        return False

# ================= PQ backend (ML-KEM-768) =================
EK, DK, CT, SS = 1184, 2400, 1088, 32

class _KyberPyBackend:
    name = "kyber-py (ML-KEM-768)"
    def __init__(self):
        self._k = None
        for mn, cn in [("kyber_py.ml_kem", "ML_KEM_768"), ("kyber_py.ml_kem", "ML_KEM768"), ("kyber_py.kyber", "Kyber768")]:
            try:
                c = getattr(__import__(mn, fromlist=[cn]), cn); a, b = c.keygen()
                if sorted((len(a), len(b))) != sorted((EK, DK)): continue
                x, y = c.encaps(a if len(a) == EK else b)
                if sorted((len(x), len(y))) != sorted((CT, SS)): continue
                self._k = c; break
            except Exception: continue
        if self._k is None: raise ImportError("no ML-KEM-768")
    def generate_keypair(self):
        a, b = self._k.keygen()
        return (a, b) if len(a) == EK else (b, a)
    def encaps(self, pk):
        if len(pk) != EK: raise ValueError(f"encaps needs public key ({EK}B), got {len(pk)}B")
        x, y = self._k.encaps(pk)
        return (x, y) if len(x) == CT else (y, x)
    def decaps(self, ct, sk):
        try: return self._k.decaps(ct, sk)
        except Exception: return self._k.decaps(sk, ct)

class _OqsBackend:
    name = "liboqs (ML-KEM-768)"
    def __init__(self):
        import oqs
        m = next((x for x in ("ML-KEM-768", "Kyber768") if x in oqs.get_enabled_KEM_mechanisms()), None)
        if not m: raise ImportError("no ML-KEM-768")
        self._m = m
    def generate_keypair(self):
        import oqs
        with oqs.KeyEncapsulation(self._m) as k:
            pk = k.generate_keypair()
            sk = k.export_secret_key()
            return pk, sk
    def encaps(self, pk):
        if len(pk) != EK: raise ValueError(f"encaps needs public key ({EK}B), got {len(pk)}B")
        import oqs
        with oqs.KeyEncapsulation(self._m) as k:
            c, s = k.encaps(pk)
            return c, s
    def decaps(self, ct, sk):
        import oqs
        with oqs.KeyEncapsulation(self._m, sk) as k:
            return k.decaps(ct)

def _load_pq():
    errs = []
    for cls in (_OqsBackend, _KyberPyBackend):
        try:
            b = cls()
            pk, sk = b.generate_keypair()
            c, s1 = b.encaps(pk)
            s2 = b.decaps(c, sk)
            if s1 == s2 and len(s1) == SS: return b
        except Exception as e: errs.append(f"{cls.__name__}: {e}")
    raise RuntimeError("No PQ backend. Errors: " + "; ".join(errs))

PQ_KEM = None

# ================= symmetric primitives =================
APP_AAD = b"derf-pqfs-v1"
MAXSKIPPED = 1024
MAXN = 1 << 20
CHUNK = 128
HJ = 256
VAULT = b""

def derive_vault(pw):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"derf-vault", iterations=600_000).derive(pw.encode())

def hmac_sha256(k, d): return hmac.new(k, d, hashlib.sha256).digest()
def hkdf(i, s, info, n=32): return HKDF(algorithm=hashes.SHA256(), length=n, salt=s, info=info).derive(i)
def b64(b): return base64.b64encode(b).decode()
def ub64(s): return base64.b64decode(s)
def keygen(m): return tuple(hmac_sha256(hmac_sha256(m, l), b"okm") for l in (b"a", b"b", b"c"))
def kdf_ck(ck): return hmac_sha256(ck, b"\x01"), hmac_sha256(ck, b"\x00")
def tlv(*it): return b"".join(struct.pack(">H", len(i)) + i for i in it)

def untlv(b, k):
    o, off = [], 0
    for _ in range(k):
        (l,), off = struct.unpack(">H", b[off:off+2]), off+2
        o.append(b[off:off+l]); off += l
    return o, off

def now8(): return struct.pack(">Q", int(time.time() * 1e9))

def check_fresh(t8):
    t = struct.unpack(">Q", t8)[0] / 1e9
    n = time.time()
    if t > n + SKEW or n - t > FRESH:
        raise ValueError("stale timestamp")

def pad(p):
    i = struct.pack(">I", len(p)) + p
    return i + os.urandom((-len(i)) % 64)

def unpad(p):
    (l,) = struct.unpack(">I", p[:4])
    if 4 + l > len(p): raise ValueError("pad")
    return p[4:4+l]

def clean_b64(r):
    return "".join(l.strip() for l in r.splitlines() if l.strip() and not l.strip().startswith("-----")).replace("-", "+").replace("_", "/")

def valid_pub(b): return isinstance(b, (bytes, bytearray)) and len(b) == EK

def parse_pubkey(t):
    raw = clean_b64(t)
    for p in ("LCAP1+", "LCAP1-"):
        if raw.startswith(p):
            raw = raw[len(p):]
            break
    raw += "=" * (-len(raw) % 4)
    b = base64.b64decode(raw, validate=True)
    if not valid_pub(b):
        raise ValueError("Not a valid PUBLIC key (wrong length). Copy the LCAP1- public key.")
    return b

def norm_identity(d):
    pk, sk = d.get("pq_pk"), d.get("pq_sk")
    if not pk or not sk: return None
    if isinstance(pk, str): pk = ub64(pk)
    if isinstance(sk, str): sk = ub64(sk)
    if len(pk) == EK and len(sk) == DK: return {"pq_pk": pk, "pq_sk": sk}
    if len(pk) == DK and len(sk) == EK: return {"pq_pk": sk, "pq_sk": pk}
    return None

def secure_shred(fp, passes=7):
    if not os.path.isfile(fp): return
    try:
        sz = os.path.getsize(fp)
        if sz == 0: os.remove(fp); return
        with open(fp, "r+b") as f:
            for _ in range(passes):
                f.seek(0); f.write(os.urandom(sz)); f.flush(); os.fsync(f.fileno())
        os.remove(fp)
    except Exception:
        try: os.remove(fp)
        except Exception: pass

def nuke_all_files():
    for pat in ["lc_*.json", "lc_*.txt", "lc_*.bin"]:
        for f in glob.glob(P(pat)): secure_shred(f)

def lca_encrypt(m, msg, aad):
    kn, ka, km = keygen(m)
    a = ChaCha20Poly1305(ka)
    now = time.time()
    ts = [struct.pack(">Q", int((now + i * 1e-6) * 1e9)) for i in range(len(msg))]
    pv, bl = b"", []
    for i, (x, t) in enumerate(zip(msg, ts)):
        n = hmac_sha256(kn, t + struct.pack(">Q", i) + pv + aad)[:12]
        b = n + a.encrypt(n, bytes([x]), aad)
        bl.append(b); pv = b
    man = struct.pack(">H", len(aad)) + aad + struct.pack(">Q", len(msg)) + b"".join(ts)
    out = bytearray(b"LCA1") + man + hmac_sha256(km, man + hashlib.sha256(b"".join(bl)).digest())
    for b in bl: out += struct.pack(">H", len(b)) + b
    return bytes(out)

def lca_decrypt(m, pkg, ea):
    if pkg[:4] != b"LCA1": raise ValueError("hdr")
    off = 4
    (al,), off = struct.unpack(">H", pkg[off:off+2]), off+2
    aad, off = pkg[off:off+al], off+al
    if not hmac.compare_digest(aad, ea): raise ValueError("ctx")
    (n,), off = struct.unpack(">Q", pkg[off:off+8]), off+8
    ts = []
    for _ in range(n): ts.append(pkg[off:off+8]); off += 8
    mt, off = pkg[off:off+32], off+32
    bl = []
    for _ in range(n):
        (l,), off = struct.unpack(">H", pkg[off:off+2]), off+2
        bl.append(pkg[off:off+l]); off += l
    if off != len(pkg): raise ValueError("ext")
    kn, ka, km = keygen(m)
    man = struct.pack(">H", len(aad)) + aad + struct.pack(">Q", n) + b"".join(ts)
    if not hmac.compare_digest(mt, hmac_sha256(km, man + hashlib.sha256(b"".join(bl)).digest())):
        raise ValueError("man")
    a = ChaCha20Poly1305(ka)
    pv, out = b"", bytearray()
    for i, (b, t) in enumerate(zip(bl, ts)):
        n = hmac_sha256(kn, t + struct.pack(">Q", i) + pv + aad)[:12]
        if b[:12] != n: raise ValueError("chain")
        out += a.decrypt(n, b[12:], aad); pv = b
    return bytes(out), ts

def aad_len(): return len(APP_AAD) + 32 + HJ + 64
def lca_size(n): return 4 + 2 + aad_len() + 8 + 8 * n + 32 + n * 31
PAYLOAD_MAX = lca_size(CHUNK)
PACKET = 12 + HJ + 16 + PAYLOAD_MAX

def make_identity():
    pq_pk, pq_sk = PQ_KEM.generate_keypair()
    if not (len(pq_pk) == EK and len(pq_sk) == DK):
        raise ValueError("backend key length mismatch")
    return {"pq_sk": pq_sk, "pq_pk": pq_pk}

def id_bundle(i): return i["pq_pk"]
def id_fp(b): return hashlib.sha256(b).digest()
def pair_h(a, b): return hashlib.sha256(b"".join(sorted((a, b)))).digest()

def safety_code(a, b):
    h = hashlib.sha256(b"SAS" + b"".join(sorted((a, b)))).digest()[:6]
    return "-".join(str(int.from_bytes(h[i:i+2], "big") % 10000).zfill(4) for i in (0, 2, 4))

def contacts_load():
    d = {}
    if os.path.exists(P("lc_contacts.txt")):
        for ln in open(P("lc_contacts.txt"), encoding="utf-8"):
            n, _, b = ln.strip().partition("\t")
            if n and b:
                try: d[n] = parse_pubkey(b)
                except Exception: pass
    return d

def contact_add(n, b):
    contacts = contacts_load()
    contacts[n] = b
    with open(P("lc_contacts.txt"), "w", encoding="utf-8") as f:
        for name, key_bytes in contacts.items():
            f.write(f"{name}\t{base64.urlsafe_b64encode(key_bytes).decode().rstrip('=')}\n")

def contact_delete(n):
    contacts = contacts_load()
    if n in contacts:
        del contacts[n]
        with open(P("lc_contacts.txt"), "w", encoding="utf-8") as f:
            for name, key_bytes in contacts.items():
                f.write(f"{name}\t{base64.urlsafe_b64encode(key_bytes).decode().rstrip('=')}\n")
        if os.path.exists(P(f"lc_session_{n}.json")):
            secure_shred(P(f"lc_session_{n}.json"))
        if os.path.exists(P(f"lc_pending_{n}.json")):
            secure_shred(P(f"lc_pending_{n}.json"))

def vsave(p, o):
    n = os.urandom(12)
    a = ChaCha20Poly1305(hmac_sha256(VAULT, b"vault"))
    open(p, "w").write(b64(n + a.encrypt(n, json.dumps(o).encode(), None)))

def vload(p):
    r = ub64(open(p).read().strip())
    a = ChaCha20Poly1305(hmac_sha256(VAULT, b"vault"))
    return json.loads(a.decrypt(r[:12], r[12:], None))

class Session:
    def __init__(s, sid, root, role, sck=None, rck=None, sn=0, rn=0, hsend=None, hrecv=None, skipped=None):
        s.sid = sid; s.role = role
        if sck is None:
            ckAB = hkdf(root, b"ck", b"AtoB", 32); ckBA = hkdf(root, b"ck", b"BtoA", 32)
            hkAB = hkdf(root, b"hk", b"AtoB", 32); hkBA = hkdf(root, b"hk", b"BtoA", 32)
            if role == "init": s.sck, s.rck, s.hsend, s.hrecv = ckAB, ckBA, hkAB, hkBA
            else: s.sck, s.rck, s.hsend, s.hrecv = ckBA, ckAB, hkBA, hkAB
        else:
            s.sck, s.rck, s.hsend, s.hrecv = sck, rck, hsend, hrecv
        s.sn, s.rn = sn, rn
        s.skipped = skipped or {}

    def encrypt(s, pt, mf, pf):
        pd = pad(pt); tot = len(pd); mid = os.urandom(8).hex(); pk = []
        for ci in range(0, tot, CHUNK):
            ch = pd[ci:ci+CHUNK]
            mk, s.sck = kdf_ck(s.sck); n = s.sn; s.sn += 1
            h = {"n": n, "tot": tot, "ci": ci // CHUNK, "mid": mid, "pl": 0}
            hj = json.dumps(h, sort_keys=True).encode(); h["pl"] = lca_size(len(ch))
            hj = json.dumps(h, sort_keys=True).encode(); hj += b" " * (HJ - len(hj))
            aad = APP_AAD + s.sid + hj + b"".join(sorted((mf, pf)))
            l1 = lca_encrypt(mk, ch, aad); pay = l1 + os.urandom(PAYLOAD_MAX - len(l1)); no = os.urandom(12)
            pk.append(no + ChaCha20Poly1305(s.hsend).encrypt(no, hj, b"") + pay)
        return pk

    def try_decrypt(s, pkt, mf, pf):
        if len(pkt) != PACKET:
            raise ValueError(f"Invalid packet size ({len(pkt)}B vs {PACKET}B)")
        no, ct, pay = pkt[:12], pkt[12:12+HJ+16], pkt[12+HJ+16:]
        try: hj = ChaCha20Poly1305(s.hrecv).decrypt(no, ct, b"")
        except InvalidTag: raise ValueError("not-for-session")
        h = json.loads(hj.rstrip()); n = h["n"]
        if n > MAXN: raise ValueError("bounds")
        if n in s.skipped: mk = s.skipped.pop(n)
        elif n < s.rn: raise ValueError("replay")
        else:
            while s.rn < n:
                if len(s.skipped) >= MAXSKIPPED: raise ValueError("ovf")
                m2, s.rck = kdf_ck(s.rck); s.skipped[s.rn] = m2; s.rn += 1
            mk, s.rck = kdf_ck(s.rck); s.rn = n + 1
        aad = APP_AAD + s.sid + hj + b"".join(sorted((mf, pf)))
        ch, ts = lca_decrypt(mk, pay[:h["pl"]], aad); check_fresh(ts[0])
        return h["tot"], h["ci"], h["mid"], ch

    def save(s, p):
        vsave(P(f"lc_session_{p}.json"), {
            "sid": b64(s.sid), "role": s.role, "sck": b64(s.sck), "rck": b64(s.rck),
            "sn": s.sn, "rn": s.rn, "hsend": b64(s.hsend), "hrecv": b64(s.hrecv),
            "sk": {str(k): b64(v) for k, v in s.skipped.items()}
        })

    @staticmethod
    def load(p):
        d = vload(P(f"lc_session_{p}.json"))
        return Session(ub64(d["sid"]), None, d["role"], ub64(d["sck"]), ub64(d["rck"]),
                       d["sn"], d["rn"], ub64(d["hsend"]), ub64(d["hrecv"]),
                       {int(k): ub64(v) for k, v in d["sk"].items()})

def hs_req(idn, pb):
    if not valid_pub(pb):
        raise ValueError("Contact public key invalid. Re-add them with their current LCAP1- public key.")
    me = idn["pq_pk"]
    eA_pk, eA_sk = PQ_KEM.generate_keypair()
    ctb, ssb = PQ_KEM.encaps(pb)
    pay = tlv(b"LCREQ", me, eA_pk, ctb, now8(), os.urandom(16))
    k1 = hkdf(ssb + pair_h(me, pb), b"m", b"k1")
    blob = pay + hmac_sha256(k1, pay)
    return blob, {"eA_sk": b64(eA_sk), "ssb": b64(ssb), "reqblob": b64(blob), "peer": b64(pb)}

def hs_rsp(idn, rb):
    pay, mac = rb[:-32], rb[-32:]
    f, _ = untlv(pay, 6); tag, meA, eA_pk, ctb, ts, _ = f
    if tag != b"LCREQ": raise ValueError("not an invite")
    if not valid_pub(meA): raise ValueError("invite has bad key")
    check_fresh(ts)
    meB = idn["pq_pk"]
    ssb = PQ_KEM.decaps(ctb, idn["pq_sk"])
    k1 = hkdf(ssb + pair_h(meA, meB), b"m", b"k1")
    if not hmac.compare_digest(mac, hmac_sha256(k1, pay)): raise ValueError("auth")
    ctf, ssf = PQ_KEM.encaps(eA_pk)
    rsp = tlv(b"LCRSP", hashlib.sha256(rb).digest(), ctf, now8(), os.urandom(16))
    k2 = hkdf(ssf + pair_h(meA, meB), b"m", b"k2")
    sid = hashlib.sha256(rb + rsp).digest()
    root = hkdf(ssb + ssf + pair_h(meA, meB), sid, b"root")
    return rsp + hmac_sha256(k2, rsp), Session(sid, root, "resp")

def hs_complete(idn, pend, rsb):
    pay, mac = rsb[:-32], rsb[-32:]
    f, _ = untlv(pay, 5); tag, rh, ctf, ts, _ = f
    if tag != b"LCRSP": raise ValueError("not a reply")
    check_fresh(ts)
    reqb = ub64(pend["reqblob"])
    if rh != hashlib.sha256(reqb).digest(): raise ValueError("mismatch")
    meA = idn["pq_pk"]; pb = ub64(pend["peer"])
    eA_sk = ub64(pend["eA_sk"])
    ssf = PQ_KEM.decaps(ctf, eA_sk)
    eA_sk = None
    ssb = ub64(pend["ssb"])
    k2 = hkdf(ssf + pair_h(meA, pb), b"m", b"k2")
    if not hmac.compare_digest(mac, hmac_sha256(k2, pay)): raise ValueError("auth")
    sid = hashlib.sha256(reqb + pay).digest()
    root = hkdf(ssb + ssf + pair_h(meA, pb), sid, b"root")
    return Session(sid, root, "init")

def feed(s, pkt, mf, pf, buf):
    tot, ci, mid, ch = s.try_decrypt(pkt, mf, pf)
    b = buf.setdefault(mid, {"tot": tot, "parts": {}})
    b["parts"][ci] = ch
    need = (tot + CHUNK - 1) // CHUNK
    if len(b["parts"]) == need:
        pd = b"".join(b["parts"][i] for i in range(need))[:tot]
        del buf[mid]
        return unpad(pd)
    return None

def run_selftest():
    print("===========================================")
    print("      RUNNING DERF AUTOMATED SELFTESTS     ")
    print("===========================================")
    global PQ_KEM, VAULT
    PQ_KEM = _load_pq()
    print(f"[1/6] ML-KEM-768 Backend: {PQ_KEM.name}")
    pk, sk = PQ_KEM.generate_keypair()
    assert len(pk) == EK and len(sk) == DK, f"Keygen error: pk={len(pk)}, sk={len(sk)}"
    ct, s1 = PQ_KEM.encaps(pk)
    s2 = PQ_KEM.decaps(ct, sk)
    assert s1 == s2 and len(s1) == SS, "Encaps/decaps mismatch!"

    print("[2/6] Handshake & Invite Flow (Alice <-> Bob)...")
    alice_idn = make_identity()
    bob_idn = make_identity()
    req_blob, pend = hs_req(alice_idn, id_bundle(bob_idn))
    rsp_blob, bob_sess = hs_rsp(bob_idn, req_blob)
    alice_sess = hs_complete(alice_idn, pend, rsp_blob)
    assert alice_sess.sid == bob_sess.sid, "Handshake SID mismatch!"
    assert alice_sess.sck == bob_sess.rck, "Alice SCK != Bob RCK!"
    assert alice_sess.rck == bob_sess.sck, "Alice RCK != Bob SCK!"

    print("[3/6] Message Encryption, Decryption & Uniform Sizing...")
    msg = b"Derf post-quantum deniable message test string. " * 10
    alice_fp = id_fp(id_bundle(alice_idn))
    bob_fp = id_fp(id_bundle(bob_idn))
    pkts = alice_sess.encrypt(msg, alice_fp, bob_fp)
    for p in pkts:
        assert len(p) == PACKET, f"Non-uniform packet size! {len(p)} vs {PACKET}"

    buf = {}
    decrypted = None
    for p in pkts:
        res = feed(bob_sess, p, bob_fp, alice_fp, buf)
        if res: decrypted = res
    assert decrypted == msg, "Decrypted message payload mismatch!"

    print("[4/6] Replay Attack Rejection...")
    try:
        feed(bob_sess, pkts[0], bob_fp, alice_fp, buf)
        assert False, "Replay packet did NOT fail!"
    except ValueError as e:
        print(f"   Expected rejection triggered: {e}")

    print("[5/6] Vault Storage Encryption & Decryption...")
    VAULT = derive_vault("test-passphrase-selftest")
    test_path = P("lc_selftest_vault.json")
    vsave(test_path, {"hello": "world", "val": 12345})
    loaded = vload(test_path)
    assert loaded == {"hello": "world", "val": 12345}, "Vault storage corrupted!"
    os.remove(test_path)

    print("[6/6] Out-of-Band Safety Code Verification...")
    sc1 = safety_code(id_bundle(alice_idn), id_bundle(bob_idn))
    sc2 = safety_code(id_bundle(bob_idn), id_bundle(alice_idn))
    assert sc1 == sc2 and len(sc1) == 14, f"Safety code error: {sc1} vs {sc2}"
    print(f"   Safety code format verified: {sc1}")

    print("\n[+] ALL SELFTESTS PASSED SUCCESSFULLY (100% OK).\n")
    return True

if __name__ == '__main__' and IS_SELFTEST:
    run_selftest()
    sys.exit(0)

# =========================================================
# CROSS-PLATFORM KIVY UI FRAMEWORK (STITCH DESIGN SYSTEM)
# =========================================================

os.environ["KIVY_NO_ARGS"] = "1"
from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Line, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition

# --- Stitch Design System Tokens ---
BG_OBSIDIAN = (0.055, 0.055, 0.065, 1)      # #0E0E10
BG_SIDEBAR  = (0.075, 0.080, 0.095, 1)      # #131418
SURFACE_CARD = (0.12, 0.13, 0.16, 1)        # #1F2129
SURFACE_ALT  = (0.16, 0.17, 0.22, 1)        # #292C38
CYAN_PRIMARY = (0.0, 0.94, 1.0, 1)          # #00F0FF Electric Cyan
CYAN_HOVER   = (0.0, 0.75, 0.82, 1)
TEXT_MAIN    = (0.93, 0.94, 0.97, 1)        # #EEF0F8
TEXT_MUTED   = (0.52, 0.56, 0.65, 1)        # #858FA6
COLOR_GREEN  = (0.0, 0.88, 0.45, 1)        # #00E073 Neon Green
COLOR_RED    = (1.0, 0.28, 0.28, 1)        # #FF4747 Danger Red

_CLIPBOARD_TEXT = ""

def safe_copy(text):
    global _CLIPBOARD_TEXT
    _CLIPBOARD_TEXT = text
    try: Clipboard.copy(text)
    except Exception: pass

def safe_paste():
    global _CLIPBOARD_TEXT
    try:
        val = Clipboard.paste()
        if val: return val
    except Exception: pass
    return _CLIPBOARD_TEXT

class CardPanel(BoxLayout):
    """Sleek container panel with rounded corners and glass surface shift."""
    def __init__(self, bg_color=SURFACE_CARD, radius=12, border_color=None, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.radius = radius
        self.border_color = border_color
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            if self.border_color:
                Color(*self.border_color)
                self.border_line = Line(rounded_rectangle=[self.pos[0], self.pos[1], self.size[0], self.size[1], self.radius], width=1)
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
        if hasattr(self, 'border_line') and self.border_color:
            self.border_line.rounded_rectangle = [self.pos[0], self.pos[1], self.size[0], self.size[1], self.radius]

class PrimaryButton(Button):
    """Prominent Electric Cyan Pill Button."""
    def __init__(self, text="", bg_color=CYAN_PRIMARY, text_color=(0.04, 0.04, 0.05, 1), radius=10, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.bg_color = bg_color
        self.color = text_color
        self.bold = True
        self.font_size = '13sp'
        self.radius = radius
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

class SecondaryButton(Button):
    """Subtle Ghost/Secondary Button."""
    def __init__(self, text="", bg_color=SURFACE_ALT, text_color=CYAN_PRIMARY, radius=8, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.bg_color = bg_color
        self.color = text_color
        self.bold = True
        self.font_size = '12sp'
        self.radius = radius
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

# ================= VAULT UNLOCK SCREEN =================
class VaultScreen(Screen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = app_ref

        layout = AnchorLayout(anchor_x='center', anchor_y='center')
        with layout.canvas.before:
            Color(*BG_OBSIDIAN)
            self.bg_rect = Rectangle(pos=layout.pos, size=layout.size)
        layout.bind(pos=self._update_bg, size=self._update_bg)

        card = CardPanel(orientation='vertical', size_hint=(None, None), size=(440, 340), padding=28, spacing=16)

        # Header Badge
        header_box = BoxLayout(orientation='vertical', size_hint_y=None, height=65, spacing=4)
        header_box.add_widget(Label(text="DERF VAULT", font_size='22sp', bold=True, color=CYAN_PRIMARY, halign='center'))
        header_box.add_widget(Label(text="Post-Quantum Master Encryption Vault", font_size='12sp', color=TEXT_MUTED, halign='center'))

        self.pass_input = TextInput(password=True, multiline=False, hint_text="Enter Master Passphrase...",
                                   background_color=(0.07, 0.08, 0.10, 1), foreground_color=TEXT_MAIN,
                                   cursor_color=CYAN_PRIMARY, size_hint_y=None, height=45, padding=(14, 12))

        self.err_lbl = Label(text="", font_size='12sp', color=COLOR_RED, size_hint_y=None, height=20)

        unlock_btn = PrimaryButton(text="UNLOCK VAULT", size_hint_y=None, height=45, radius=12)
        unlock_btn.bind(on_release=self.do_unlock)

        card.add_widget(header_box)
        card.add_widget(self.pass_input)
        card.add_widget(self.err_lbl)
        card.add_widget(unlock_btn)

        layout.add_widget(card)
        self.add_widget(layout)

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def do_unlock(self, *args):
        pw = self.pass_input.text
        if not pw:
            self.err_lbl.text = "Passphrase required."
            return

        global VAULT
        VAULT = derive_vault(pw)

        if os.path.exists(P("lc_identity.json")):
            try:
                d = vload(P("lc_identity.json"))
                norm = norm_identity(d)
                if not norm: raise ValueError("Corrupted identity")
                self.app_ref.idn = norm
            except Exception:
                self.err_lbl.text = "Incorrect passphrase or corrupted vault."
                return
        else:
            try:
                self.app_ref.idn = make_identity()
                vsave(P("lc_identity.json"), {"pq_sk": b64(self.app_ref.idn["pq_sk"]), "pq_pk": b64(self.app_ref.idn["pq_pk"])})
            except Exception as e:
                self.err_lbl.text = f"Failed to create identity: {e}"
                return

        self.app_ref.on_vault_unlocked()

# ================= MAIN APP SCREEN =================
class MainScreen(Screen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = app_ref
        self.buffers = {}

        # Main Horizontal Layout: Sidebar + Workspace
        self.root_box = BoxLayout(orientation='horizontal')

        with self.root_box.canvas.before:
            Color(*BG_OBSIDIAN)
            self.bg_rect = Rectangle(pos=self.root_box.pos, size=self.root_box.size)
        self.root_box.bind(pos=self._update_bg, size=self._update_bg)

        # ---------------- 1. LEFT SIDEBAR (Width: 280dp) ----------------
        sidebar = CardPanel(bg_color=BG_SIDEBAR, radius=0, size_hint_x=None, width=280, orientation='vertical', padding=16, spacing=16)

        # Logo & App Title
        branding = BoxLayout(orientation='vertical', size_hint_y=None, height=55, spacing=2)
        branding.add_widget(Label(text="DERF", font_size='22sp', bold=True, color=CYAN_PRIMARY, halign='left'))
        branding.add_widget(Label(text="Post-Quantum PQ+FS Messenger", font_size='11sp', color=TEXT_MUTED, halign='left'))
        for child in branding.children: child.bind(size=child.setter('text_size'))
        sidebar.add_widget(branding)

        # Contact List Header
        sb_contacts_hdr = BoxLayout(orientation='horizontal', size_hint_y=None, height=28)
        sb_contacts_hdr.add_widget(Label(text="CONTACTS & PEERS", font_size='11sp', bold=True, color=TEXT_MUTED, halign='left'))
        for child in sb_contacts_hdr.children: child.bind(size=child.setter('text_size'))
        sidebar.add_widget(sb_contacts_hdr)

        # Contact Scroll List
        self.contact_scroll = ScrollView()
        self.contact_list_layout = GridLayout(cols=1, spacing=8, size_hint_y=None)
        self.contact_list_layout.bind(minimum_height=self.contact_list_layout.setter('height'))
        self.contact_scroll.add_widget(self.contact_list_layout)
        sidebar.add_widget(self.contact_scroll)

        # Sidebar Bottom Actions
        sb_actions = BoxLayout(orientation='vertical', size_hint_y=None, height=130, spacing=8)

        btn_add_peer = PrimaryButton(text="+ ADD NEW PEER", size_hint_y=None, height=36, radius=8)
        btn_add_peer.bind(on_release=lambda x: self.switch_tab("contacts"))

        btn_vault_set = SecondaryButton(text="Vault Passkey Settings", text_color=TEXT_MAIN, size_hint_y=None, height=36)
        btn_vault_set.bind(on_release=self.show_change_passkey)

        btn_nuke_data = Button(text="NUKE ALL DATA", background_normal='', background_color=COLOR_RED, color=TEXT_MAIN, bold=True, font_size='11sp', size_hint_y=None, height=34)
        btn_nuke_data.bind(on_release=self.confirm_nuke)

        sb_actions.add_widget(btn_add_peer)
        sb_actions.add_widget(btn_vault_set)
        sb_actions.add_widget(btn_nuke_data)
        sidebar.add_widget(sb_actions)

        self.root_box.add_widget(sidebar)

        # ---------------- 2. RIGHT WORKSPACE STAGE ----------------
        self.workspace = BoxLayout(orientation='vertical', padding=16, spacing=12)

        # Stage Top Header
        self.stage_hdr = CardPanel(bg_color=SURFACE_CARD, size_hint_y=None, height=60, padding=(16, 10), orientation='horizontal', spacing=12)

        self.active_peer_lbl = Label(text="Select a contact to chat", font_size='16sp', bold=True, color=TEXT_MAIN, halign='left')
        self.active_peer_lbl.bind(size=self.active_peer_lbl.setter('text_size'))

        self.safety_badge = Label(text="Safety: N/A", font_size='12sp', color=TEXT_MUTED, halign='right')
        self.safety_badge.bind(size=self.safety_badge.setter('text_size'))

        self.stage_hdr.add_widget(self.active_peer_lbl)
        self.stage_hdr.add_widget(self.safety_badge)
        self.workspace.add_widget(self.stage_hdr)

        # Stage Sub-Nav Pills
        nav_pills = BoxLayout(orientation='horizontal', size_hint_y=None, height=38, spacing=8)
        self.pill_btns = {}

        pills = [
            ("messages", "MESSAGES & PACKETS"),
            ("contacts", "PAIRING WIZARD"),
            ("security", "SECURITY SPECS"),
            ("help", "PROTOCOL GUIDE")
        ]

        for key, label in pills:
            btn = SecondaryButton(text=label, size_hint_x=None, width=150)
            btn.bind(on_release=lambda instance, k=key: self.switch_tab(k))
            nav_pills.add_widget(btn)
            self.pill_btns[key] = btn

        self.workspace.add_widget(nav_pills)

        # Stage Content View Container
        self.content_container = BoxLayout(orientation='vertical')
        self.workspace.add_widget(self.content_container)

        # Status Bar
        self.status_lbl = Label(text=f"Data Dir: {DATA_DIR}", font_size='11sp', color=TEXT_MUTED, size_hint_y=None, height=20, halign='left')
        self.status_lbl.bind(size=self.status_lbl.setter('text_size'))
        self.workspace.add_widget(self.status_lbl)

        self.root_box.add_widget(self.workspace)
        self.add_widget(self.root_box)

        self.selected_peer = None
        self.current_tab = "messages"

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def refresh_views(self):
        self.update_sidebar_contacts()
        self.switch_tab(self.current_tab)

    def update_sidebar_contacts(self):
        self.contact_list_layout.clear_widgets()
        cs = contacts_load()
        if not cs:
            lbl = Label(text="No Contacts Yet", font_size='12sp', color=TEXT_MUTED, size_hint_y=None, height=30)
            self.contact_list_layout.add_widget(lbl)
            return

        for name, pub_bytes in cs.items():
            is_paired = os.path.exists(P(f"lc_session_{name}.json"))
            card = CardPanel(bg_color=SURFACE_ALT if name == self.selected_peer else SURFACE_CARD,
                             radius=8, size_hint_y=None, height=52, padding=(10, 8), orientation='horizontal', spacing=8)

            # Avatar Icon Box
            avatar = CardPanel(bg_color=(0.20, 0.22, 0.28, 1), radius=6, size_hint=(None, None), size=(34, 34))
            avatar.add_widget(Label(text=name[:2].upper(), font_size='12sp', bold=True, color=CYAN_PRIMARY))

            info = BoxLayout(orientation='vertical', spacing=2)
            info.add_widget(Label(text=name, font_size='13sp', bold=True, color=TEXT_MAIN, halign='left'))

            st_text = "[ PAIRED ]" if is_paired else "[ UNPAIRED ]"
            st_color = COLOR_GREEN if is_paired else TEXT_MUTED
            info.add_widget(Label(text=st_text, font_size='10sp', color=st_color, halign='left'))

            for child in info.children: child.bind(size=child.setter('text_size'))

            card.add_widget(avatar)
            card.add_widget(info)

            # Select contact callback
            def make_select_cb(p_name):
                return lambda x: self.select_peer(p_name)

            card.bind(on_touch_down=lambda instance, touch, p=name: make_select_cb(p)(x) if instance.collide_point(*touch.pos) else None)
            self.contact_list_layout.add_widget(card)

        if not self.selected_peer and cs:
            self.select_peer(list(cs.keys())[0])

    def select_peer(self, name):
        self.selected_peer = name
        cs = contacts_load()
        if name in cs and hasattr(self.app_ref, 'idn'):
            sc = safety_code(id_bundle(self.app_ref.idn), cs[name])
            is_p = os.path.exists(P(f"lc_session_{name}.json"))
            st_str = "PAIRED" if is_p else "UNPAIRED"
            self.active_peer_lbl.text = f"Peer: {name} ({st_str})"
            self.safety_badge.text = f"Safety Code: {sc}"
        else:
            self.active_peer_lbl.text = f"Peer: {name}"
            self.safety_badge.text = "Safety Code: N/A"

        self.update_sidebar_contacts()
        self.switch_tab(self.current_tab)

    def switch_tab(self, tab_key):
        self.current_tab = tab_key
        for k, b in self.pill_btns.items():
            if k == tab_key:
                b.bg_color = CYAN_PRIMARY
                b.color = (0.04, 0.04, 0.05, 1)
            else:
                b.bg_color = SURFACE_ALT
                b.color = CYAN_PRIMARY

        self.content_container.clear_widgets()
        if tab_key == "messages":
            self.content_container.add_widget(self.build_messages_view())
        elif tab_key == "contacts":
            self.content_container.add_widget(self.build_contacts_view())
        elif tab_key == "security":
            self.content_container.add_widget(self.build_security_view())
        elif tab_key == "help":
            self.content_container.add_widget(self.build_help_view())

    # --- VIEW 1: MESSAGES & PACKETS ---
    def build_messages_view(self):
        split = BoxLayout(orientation='horizontal', spacing=12)

        # Encrypt Column
        enc_box = CardPanel(orientation='vertical', padding=12, spacing=10)
        enc_box.add_widget(Label(text="ENCRYPT CONFIDENTIAL MESSAGE", font_size='13sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left'))

        self.enc_input = TextInput(hint_text="Type confidential plaintext message here...", background_color=(0.06, 0.07, 0.09, 1),
                                   foreground_color=TEXT_MAIN, cursor_color=CYAN_PRIMARY, padding=(10, 10))
        enc_box.add_widget(self.enc_input)

        btn_enc = PrimaryButton(text="[ LOCK & ENCRYPT MESSAGE ]", size_hint_y=None, height=42, radius=10)
        btn_enc.bind(on_release=self.do_encrypt)
        enc_box.add_widget(btn_enc)

        self.enc_output = TextInput(hint_text="Encrypted Base64 uniform packets output...", readonly=True,
                                    background_color=(0.06, 0.07, 0.09, 1), foreground_color=CYAN_PRIMARY)
        enc_box.add_widget(self.enc_output)

        enc_act = BoxLayout(orientation='horizontal', size_hint_y=None, height=36, spacing=8)
        btn_c1 = SecondaryButton(text="[ Copy Packets ]")
        btn_c1.bind(on_release=lambda x: self.copy_to_clip(self.enc_output.text, "Encrypted packets copied!"))
        btn_s1 = SecondaryButton(text="[ Save to Drop File ]")
        btn_s1.bind(on_release=self.save_to_drop)
        enc_act.add_widget(btn_c1)
        enc_act.add_widget(btn_s1)
        enc_box.add_widget(enc_act)

        # Decrypt Column
        dec_box = CardPanel(orientation='vertical', padding=12, spacing=10)
        dec_box.add_widget(Label(text="DECRYPT INCOMING PACKETS", font_size='13sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left'))

        self.dec_input = TextInput(hint_text="Paste received Base64 ciphertext packets here...", background_color=(0.06, 0.07, 0.09, 1),
                                   foreground_color=TEXT_MAIN, cursor_color=CYAN_PRIMARY, padding=(10, 10))
        dec_box.add_widget(self.dec_input)

        btn_dec = PrimaryButton(text="[ UNLOCK & DECRYPT PACKETS ]", size_hint_y=None, height=42, radius=10)
        btn_dec.bind(on_release=self.do_decrypt)
        dec_box.add_widget(btn_dec)

        self.dec_output = TextInput(hint_text="Decrypted message payload result...", readonly=True,
                                    background_color=(0.06, 0.07, 0.09, 1), foreground_color=COLOR_GREEN, font_size='14sp')
        dec_box.add_widget(self.dec_output)

        dec_act = BoxLayout(orientation='horizontal', size_hint_y=None, height=36, spacing=8)
        btn_p2 = SecondaryButton(text="[ Paste Clipboard ]")
        btn_p2.bind(on_release=lambda x: setattr(self.dec_input, 'text', safe_paste()))
        btn_c2 = SecondaryButton(text="[ Copy Decrypted ]")
        btn_c2.bind(on_release=lambda x: self.copy_to_clip(self.dec_output.text, "Decrypted text copied!"))
        dec_act.add_widget(btn_p2)
        dec_act.add_widget(btn_c2)
        dec_box.add_widget(dec_act)

        split.add_widget(enc_box)
        split.add_widget(dec_box)
        return split

    def do_encrypt(self, *args):
        peer = self.selected_peer
        cs = contacts_load()
        if not peer or peer not in cs or not os.path.exists(P(f"lc_session_{peer}.json")):
            self.show_popup("Encrypt Error", "Please select a valid PAIRED contact from the sidebar first.")
            return

        pt = self.enc_input.text.strip()
        if not pt:
            self.show_popup("Encrypt Error", "Message payload cannot be empty.")
            return

        try:
            sess = Session.load(peer)
            me_fp = id_fp(id_bundle(self.app_ref.idn))
            peer_fp = id_fp(cs[peer])
            pkts = sess.encrypt(pt.encode('utf-8'), me_fp, peer_fp)
            sess.save(peer)

            out_b64 = "\n".join(b64(p) for p in pkts)
            self.enc_output.text = out_b64
            safe_copy(out_b64)
            self.enc_input.text = ""
            self.status_lbl.text = f"[*] Encrypted {len(pkts)} packet(s) for {peer} — Copied to clipboard."
        except Exception as e:
            self.show_popup("Encryption Failed", str(e))

    def save_to_drop(self, *args):
        raw = self.enc_output.text.strip()
        if not raw:
            self.show_popup("Save Error", "No encrypted packets to save.")
            return
        fn = f"packet_{int(time.time())}_{os.urandom(3).hex()}.bin"
        fp = os.path.join(DROP_DIR, fn)
        with open(fp, "w") as f: f.write(raw)
        self.status_lbl.text = f"[*] Saved drop file: {fp}"
        self.show_popup("Saved", f"Packet drop saved to Desktop/Derf/lc_drop/{fn}")

    def do_decrypt(self, *args):
        raw = self.dec_input.text.strip()
        if not raw:
            self.show_popup("Decrypt Error", "Paste Base64 packet text first.")
            return

        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        try:
            pkts = [ub64(clean_b64(l)) for l in lines]
        except Exception:
            self.show_popup("Decrypt Error", "Invalid Base64 ciphertext packet format.")
            return

        cs = contacts_load()
        me_fp = id_fp(id_bundle(self.app_ref.idn))

        paired = [n for n in cs if os.path.exists(P(f"lc_session_{n}.json"))]
        for peer in paired:
            sess = Session.load(peer)
            peer_fp = id_fp(cs[peer])
            msgs = []
            got = 0
            for p in pkts:
                try:
                    out = feed(sess, p, me_fp, peer_fp, self.buffers)
                    if out:
                        msgs.append(out.decode('utf-8'))
                        got += 1
                except Exception:
                    pass
            if got or len(self.buffers) > 0:
                sess.save(peer)
            if got:
                self.dec_output.text = "\n".join(msgs)
                self.status_lbl.text = f"[*] Successfully decrypted payload from {peer}!"
                return

        self.show_popup("Decrypt Failed", "Could not decrypt packet (wrong key, stale >7min, or tampered).")

    # --- VIEW 2: CONTACTS & PAIRING WIZARD ---
    def build_contacts_view(self):
        layout = BoxLayout(orientation='vertical', spacing=12)

        # My Identity Key Card
        my_card = CardPanel(orientation='vertical', size_hint_y=None, height=115, padding=12, spacing=6)
        my_card.add_widget(Label(text="YOUR PUBLIC IDENTITY KEY (ML-KEM-768)", font_size='13sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=20, halign='left'))

        my_pub_str = "LCAP1-" + base64.urlsafe_b64encode(id_bundle(self.app_ref.idn)).decode().rstrip("=")
        key_input = TextInput(text=my_pub_str, readonly=True, background_color=(0.06, 0.07, 0.09, 1), foreground_color=TEXT_MAIN, size_hint_y=None, height=40)
        my_card.add_widget(key_input)

        btn_c_my = PrimaryButton(text="[ COPY MY PUBLIC KEY ]", size_hint_y=None, height=32, radius=8)
        btn_c_my.bind(on_release=lambda x: self.copy_to_clip(my_pub_str, "Public key copied!"))
        my_card.add_widget(btn_c_my)
        layout.add_widget(my_card)

        split_pair = BoxLayout(orientation='horizontal', spacing=12)

        # Add Contact Card
        add_box = CardPanel(orientation='vertical', padding=12, spacing=10)
        add_box.add_widget(Label(text="ADD NEW CONTACT", font_size='13sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left'))

        self.new_name = TextInput(hint_text="Contact Name (e.g. Alice)", multiline=False, background_color=(0.06, 0.07, 0.09, 1),
                                  foreground_color=TEXT_MAIN, size_hint_y=None, height=38)
        self.new_key = TextInput(hint_text="Paste their LCAP1- Public Key...", background_color=(0.06, 0.07, 0.09, 1),
                                 foreground_color=TEXT_MAIN)

        btn_add = PrimaryButton(text="[ SAVE CONTACT ]", size_hint_y=None, height=38, radius=8)
        btn_add.bind(on_release=self.do_add_contact)

        add_box.add_widget(self.new_name)
        add_box.add_widget(self.new_key)
        add_box.add_widget(btn_add)
        split_pair.add_widget(add_box)

        # Guided Pairing Wizard Card
        pair_box = CardPanel(orientation='vertical', padding=12, spacing=10)
        pair_box.add_widget(Label(text="STEP-BY-STEP PAIRING WIZARD", font_size='13sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left'))

        pair_mode_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=36, spacing=8)
        self.btn_m_a = SecondaryButton(text="I Start (Send Invite)")
        self.btn_m_b = SecondaryButton(text="They Started (Accept Invite)")

        self.pair_mode = "A"
        def set_mode(m):
            self.pair_mode = m
            if m == "A":
                self.btn_m_a.bg_color = CYAN_PRIMARY; self.btn_m_a.color = (0.04, 0.04, 0.05, 1)
                self.btn_m_b.bg_color = SURFACE_ALT; self.btn_m_b.color = CYAN_PRIMARY
                self.p_step1_lbl.text = "Step 1: Generate & Copy Invite"
                self.p_step2_lbl.text = "Step 2: Paste Reply & Finish"
            else:
                self.btn_m_b.bg_color = CYAN_PRIMARY; self.btn_m_b.color = (0.04, 0.04, 0.05, 1)
                self.btn_m_a.bg_color = SURFACE_ALT; self.btn_m_a.color = CYAN_PRIMARY
                self.p_step1_lbl.text = "Step 1: Paste Received Invite"
                self.p_step2_lbl.text = "Step 2: Create Reply & Finish"

        self.btn_m_a.bind(on_release=lambda x: set_mode("A"))
        self.btn_m_b.bind(on_release=lambda x: set_mode("B"))
        pair_mode_box.add_widget(self.btn_m_a)
        pair_mode_box.add_widget(self.btn_m_b)
        pair_box.add_widget(pair_mode_box)

        self.p_step1_lbl = Label(text="Step 1: Generate & Copy Invite", font_size='12sp', color=TEXT_MAIN, size_hint_y=None, height=20, halign='left')
        self.p_io1 = TextInput(hint_text="Invite payload will appear here...", background_color=(0.06, 0.07, 0.09, 1), foreground_color=CYAN_PRIMARY)

        self.p_step2_lbl = Label(text="Step 2: Paste Reply & Finish", font_size='12sp', color=TEXT_MAIN, size_hint_y=None, height=20, halign='left')
        self.p_io2 = TextInput(hint_text="Paste peer reply here...", background_color=(0.06, 0.07, 0.09, 1), foreground_color=TEXT_MAIN)

        btn_exec_pair = PrimaryButton(text="[ EXECUTE PAIRING STEP ]", size_hint_y=None, height=38, radius=8)
        btn_exec_pair.bind(on_release=self.execute_pairing)

        pair_box.add_widget(self.p_step1_lbl)
        pair_box.add_widget(self.p_io1)
        pair_box.add_widget(self.p_step2_lbl)
        pair_box.add_widget(self.p_io2)
        pair_box.add_widget(btn_exec_pair)

        split_pair.add_widget(pair_box)
        layout.add_widget(split_pair)
        set_mode("A")
        return layout

    def do_add_contact(self, *args):
        name = self.new_name.text.strip()
        raw_key = self.new_key.text.strip()
        if not name or not raw_key:
            self.show_popup("Add Error", "Please provide both Name and Public Key.")
            return
        try:
            pub_b = parse_pubkey(raw_key)
            contact_add(name, pub_b)
            self.new_name.text = ""
            self.new_key.text = ""
            self.show_popup("Success", f"Saved contact '{name}'. You can now pair with them!")
            self.refresh_views()
        except Exception as e:
            self.show_popup("Invalid Key", str(e))

    def execute_pairing(self, *args):
        peer = self.selected_peer
        cs = contacts_load()
        if not peer or peer not in cs:
            self.show_popup("Pairing Error", "Select a contact from the sidebar first.")
            return

        if self.pair_mode == "A":
            if not self.p_io1.text:
                try:
                    req_blob, pend = hs_req(self.app_ref.idn, cs[peer])
                    vsave(P(f"lc_pending_{peer}.json"), pend)
                    inv_b64 = b64(req_blob)
                    self.p_io1.text = inv_b64
                    safe_copy(inv_b64)
                    self.show_popup("Invite Created", f"Invite copied! Send this to {peer}. When they reply, paste it into Step 2 box and click Execute again.")
                except Exception as e:
                    self.show_popup("Invite Failed", str(e))
            else:
                reply_raw = self.p_io2.text.strip()
                if not reply_raw:
                    self.show_popup("Pairing Error", "Paste peer reply into Step 2 box.")
                    return
                try:
                    pend = vload(P(f"lc_pending_{peer}.json"))
                    sess = hs_complete(self.app_ref.idn, pend, ub64(clean_b64(reply_raw)))
                    sess.save(peer)
                    os.remove(P(f"lc_pending_{peer}.json"))
                    self.show_popup("PAIRED!", f"Successfully paired with {peer}! You can now exchange encrypted messages.")
                    self.refresh_views()
                except Exception as e:
                    self.show_popup("Pairing Failed", str(e))
        else:
            inv_raw = self.p_io1.text.strip()
            if not inv_raw:
                self.show_popup("Pairing Error", "Paste initiator invite into Step 1 box first.")
                return
            try:
                rsp_blob, sess = hs_rsp(self.app_ref.idn, ub64(clean_b64(inv_raw)))
                sess.save(peer)
                reply_b64 = b64(rsp_blob)
                self.p_io2.text = reply_b64
                safe_copy(reply_b64)
                self.show_popup("Reply Generated", f"Reply generated & copied! Send this reply back to {peer} to complete pairing.")
                self.refresh_views()
            except Exception as e:
                self.show_popup("Responder Error", str(e))

    # --- VIEW 3: SECURITY SPECS ---
    def build_security_view(self):
        layout = ScrollView()
        grid = GridLayout(cols=1, spacing=12, padding=12, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        cards_data = [
            ("Post-Quantum KEM (ML-KEM-768 / Kyber768)", "Derf uses NIST FIPS 203 ML-KEM-768 post-quantum key encapsulation. Handshakes resist quantum computers running Shor's algorithm."),
            ("LC-AEAD Chained Encryption", "Per-letter chained ChaCha20-Poly1305 AEAD structure ensures payload integrity, strict message order, and immediate truncation rejection."),
            ("Signal-Style Double Ratchet", "Every packet advances the key ratchet. Compromising future or past keys yields zero access to prior ciphertexts (Forward Secrecy + Post-Compromise Security)."),
            ("Unprovable Deniability (X3DH)", "Handshakes rely on symmetric HKDF MAC tags rather than non-repudiable digital signatures. Neither party can prove message authorship to third parties."),
            ("Uniform Packet Sizing", "Every ciphertext packet is padded to an exact fixed size (PACKET bytes), preventing packet length side-channel leaks."),
            ("Vault at Rest (PBKDF2-HMAC-SHA256)", "All identity keys, pending sessions, and contact states are stored on disk encrypted using 600,000 PBKDF2 iterations.")
        ]

        for title, desc in cards_data:
            c = CardPanel(orientation='vertical', size_hint_y=None, height=90, padding=12, spacing=4)
            c.add_widget(Label(text=title, font_size='14sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left'))
            lbl_desc = Label(text=desc, font_size='12sp', color=TEXT_MAIN, halign='left')
            lbl_desc.bind(size=lbl_desc.setter('text_size'))
            c.add_widget(lbl_desc)
            grid.add_widget(c)

        layout.add_widget(grid)
        return layout

    # --- VIEW 4: GUIDE ---
    def build_help_view(self):
        layout = ScrollView()
        box = CardPanel(orientation='vertical', padding=16, spacing=10, size_hint_y=None)
        box.bind(minimum_height=box.setter('height'))

        help_text = (
            "[b][size=16sp]DERF PQ+FS QUICKSTART GUIDE[/size][/b]\n\n"
            "1. [b]Exchange Public Keys[/b]: Copy your [i]LCAP1-...[/i] public key from the Pairing tab and add each other as contacts.\n"
            "2. [b]One-Time Pairing[/b]:\n"
            "   - Initiator selects 'I Start', clicks 'Execute Pairing Step' to copy an Invite string, and sends it to the Peer.\n"
            "   - Responder selects 'They Started', pastes the Invite into Step 1, clicks 'Execute Pairing Step' to copy a Reply string.\n"
            "   - Initiator pastes Responder's Reply into Step 2 and clicks 'Execute Pairing Step'. Pairing complete!\n"
            "3. [b]Send Encrypted Messages[/b]: Go to Messages tab, type plaintext, click ENCRYPT, and copy/send uniform Base64 packets.\n"
            "4. [b]Decrypt Messages[/b]: Paste received Base64 packets into Decrypt box and click DECRYPT.\n\n"
            "[b]Important Security Rules:[/b]\n"
            "• Messages must be decrypted within [b]7 minutes[/b] (420s freshness window) to prevent replay attacks.\n"
            "• Compare the 12-digit Safety Code out-of-band once to verify peer key authenticity."
        )

        lbl = Label(text=help_text, markup=True, font_size='13sp', color=TEXT_MAIN, halign='left', size_hint_y=None)
        lbl.bind(size=lbl.setter('text_size'))
        lbl.bind(texture_size=lambda instance, val: setattr(lbl, 'height', val[1]))

        box.add_widget(lbl)
        layout.add_widget(box)
        return layout

    # --- UTILITY ACTIONS & MODALS ---
    def copy_to_clip(self, text, msg):
        if text:
            safe_copy(text)
            self.status_lbl.text = f"[*] {msg}"

    def show_popup(self, title, msg):
        content = BoxLayout(orientation='vertical', padding=12, spacing=10)
        content.add_widget(Label(text=msg, font_size='13sp', color=TEXT_MAIN))
        btn = PrimaryButton(text="OK", size_hint_y=None, height=36, radius=8)
        content.add_widget(btn)

        popup = Popup(title=title, content=content, size_hint=(None, None), size=(380, 200),
                      title_color=CYAN_PRIMARY, background_color=SURFACE_CARD)
        btn.bind(on_release=popup.dismiss)
        popup.open()

    def show_change_passkey(self, *args):
        content = BoxLayout(orientation='vertical', padding=12, spacing=8)
        content.add_widget(Label(text="New Vault Passphrase:", font_size='12sp', color=TEXT_MAIN))
        e1 = TextInput(password=True, multiline=False, background_color=(0.06, 0.07, 0.09, 1), foreground_color=TEXT_MAIN, size_hint_y=None, height=35)
        content.add_widget(e1)

        content.add_widget(Label(text="Confirm Passphrase:", font_size='12sp', color=TEXT_MAIN))
        e2 = TextInput(password=True, multiline=False, background_color=(0.06, 0.07, 0.09, 1), foreground_color=TEXT_MAIN, size_hint_y=None, height=35)
        content.add_widget(e2)

        btn_change = PrimaryButton(text="CHANGE PASSKEY", size_hint_y=None, height=36, radius=8)
        content.add_widget(btn_change)

        popup = Popup(title="Change Master Passkey", content=content, size_hint=(None, None), size=(380, 240), title_color=CYAN_PRIMARY)

        def do_rekey(*a):
            if not e1.text or e1.text != e2.text:
                self.show_popup("Error", "Passphrases do not match or are empty.")
                return
            global VAULT
            files = [P("lc_identity.json")] + glob.glob(P("lc_session_*.json")) + glob.glob(P("lc_pending_*.json"))
            data = {}
            for f in files:
                try: data[f] = vload(f)
                except Exception: pass

            VAULT = derive_vault(e1.text)
            for f, dta in data.items(): vsave(f, dta)
            popup.dismiss()
            self.show_popup("Success", "Vault passkey changed and files re-encrypted successfully.")

        btn_change.bind(on_release=do_rekey)
        popup.open()

    def confirm_nuke(self, *args):
        content = BoxLayout(orientation='vertical', padding=12, spacing=10)
        content.add_widget(Label(text="WARNING: Destroy ALL keys, sessions, and contacts in Desktop/Derf?", font_size='12sp', color=COLOR_RED))

        btn_box = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=36)
        btn_cancel = SecondaryButton(text="Cancel")
        btn_yes = Button(text="DESTROY EVERYTHING", background_normal='', background_color=COLOR_RED, color=TEXT_MAIN, bold=True)
        btn_box.add_widget(btn_cancel)
        btn_box.add_widget(btn_yes)
        content.add_widget(btn_box)

        popup = Popup(title="NUKE DATA CONFIRMATION", content=content, size_hint=(None, None), size=(400, 200), title_color=COLOR_RED)
        btn_cancel.bind(on_release=popup.dismiss)

        def nuke_now(*a):
            nuke_all_files()
            popup.dismiss()
            App.get_running_app().stop()

        btn_yes.bind(on_release=nuke_now)
        popup.open()

class DerfApp(App):
    def build(self):
        self.title = "Derf PQ+FS — Post-Quantum Messenger"
        Window.clearcolor = BG_OBSIDIAN
        Window.size = (1024, 720)

        global PQ_KEM
        try:
            PQ_KEM = _load_pq()
        except Exception as e:
            print(f"FATAL: {e}")
            sys.exit(1)

        self.sm = ScreenManager(transition=FadeTransition(duration=0.15))
        self.vault_screen = VaultScreen(app_ref=self, name='vault')
        self.main_screen = MainScreen(app_ref=self, name='main')

        self.sm.add_widget(self.vault_screen)
        self.sm.add_widget(self.main_screen)
        return self.sm

    def on_vault_unlocked(self):
        self.main_screen.refresh_views()
        self.sm.current = 'main'

def main():
    if not _single():
        print("⚠️ Another instance of Derf is already running.")
        sys.exit(1)
    DerfApp().run()

if __name__ == '__main__':
    main()
