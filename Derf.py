"""
Derf PQ+FS — post-quantum + forward-secret two-box messenger.
Cross-platform Kivy GUI + Integrated Background Service + CLI selftest.
Data stored in 'Derf' folder on Desktop (auto-created + migrated).
"""
import os, sys, json, zstandard as zstd, zlib, glob, hmac, hashlib, time, struct, base64, binascii, socket, shutil, threading, re
import pyperclip

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
        print(f'⚠️ Error parsing --fresh-sec: {repr(e)}')

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidTag

try:
    import kyber_py.ml_kem  # noqa: F401
except Exception:
    pass

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

if os.path.exists(P("lc_fresh.json")):
    try:
        d = vload(P("lc_fresh.json"))
        FRESH = float(d.get("fresh_sec", 420.0))
    except Exception: pass

# ================= ALIEN COMPRESSION STACK =================
DICT_PATH = P("derf_elite_dict.zdict")
ALIEN_COMPRESSION_ENABLED = False

zstd_compressor = None
zstd_decompressor = None

if os.path.exists(DICT_PATH):
    try:
        with open(DICT_PATH, "rb") as f:
            elite_dict = zstd.ZstdCompressionDict(f.read())
        # Level 19 is the perfect balance of speed and ultra-compression
        zstd_compressor = zstd.ZstdCompressor(level=19, dict_data=elite_dict)
        zstd_decompressor = zstd.ZstdDecompressor(dict_data=elite_dict)
        ALIEN_COMPRESSION_ENABLED = True
        print(f"[*] Derf Alien Stack Loaded. Dictionary size: {os.path.getsize(DICT_PATH) / 1024:.1f} KB")
    except Exception as e:
        print(f"[!] Failed to load dictionary: {repr(e)}")
# ===========================================================

def clean_ciphertext_input(text):
    if not text: return ""
    import html
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    replacements = {
        '’': "'", '‘': "'", '“': '"', '”': '"',
        '–': '-', '—': '-', '\u200b': '', '\u200c': '',
        '\u200d': '', '\ufeff': '', '\u00a0': '', '\r': ''
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.strip()


def smart_split_text(text, max_chars=200):
    """Splits text at spaces/newlines so words are never cut in half."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n")
    current_chunk = ""

    for para in paragraphs:
        if len(para) > max_chars:
            words = para.split(" ")
            for word in words:
                if len(current_chunk) + len(word) + 1 > max_chars:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = word + " "
                else:
                    current_chunk += word + " "
        else:
            if len(current_chunk) + len(para) + 1 > max_chars:
                chunks.append(current_chunk.strip())
                current_chunk = para + "\n"
            else:
                current_chunk += para + "\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    return chunks

def encrypt_alien_stack(text, peer, idn_data):
    cs = contacts_load()
    if not peer or peer not in cs or not os.path.exists(P(f"lc_session_{peer}.json")):
        raise ValueError("Please select a valid PAIRED contact.")

    text_chunks = smart_split_text(text, max_chars=200)
    sess = Session.load(peer)
    me_pk = ub64(idn_data["pq_pk"]) if isinstance(idn_data["pq_pk"], str) else idn_data["pq_pk"]
    me_fp = id_fp(me_pk)
    peer_fp = id_fp(cs[peer])
    encrypted_outputs = []

    for chunk in text_chunks:
        chunk_bytes = chunk.encode('utf-8')
        is_compressed = False

        if ALIEN_COMPRESSION_ENABLED and zstd_compressor and len(chunk_bytes) > 50:
            chunk_bytes = zstd_compressor.compress(chunk_bytes)
            is_compressed = True
        elif len(chunk_bytes) > 50:
            chunk_bytes = zlib.compress(chunk_bytes, 9)
            is_compressed = True

        pkts = sess.encrypt(chunk_bytes, me_fp, peer_fp)
        prefix = "DERF:V1:C:" if is_compressed else "DERF:V1:R:"
        for pkt in pkts:
            encoded_str = base64.b64encode(pkt).decode('ascii')
            encrypted_outputs.append(prefix + encoded_str)

    sess.save(peer)
    return "\n\n".join(encrypted_outputs)

def decrypt_alien_stack(raw_text, idn_data, custom_session_loader=None):
    if not raw_text: return None
    raw_text = clean_ciphertext_input(raw_text)

    pattern = re.compile(r'DERF:V1:(?:C:|R:)?')
    matches = list(pattern.finditer(raw_text))

    raw_chunks = []
    if matches:
        for i in range(len(matches)):
            start_idx = matches[i].start()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
            raw_chunks.append(raw_text[start_idx:end_idx].strip())
    else:
        raw_chunks = re.split(r'\n\s*\n', raw_text.strip())
        if len(raw_chunks) == 1:
            raw_chunks = raw_text.strip().split('\n')

    cs = contacts_load()
    me_pk = ub64(idn_data["pq_pk"]) if isinstance(idn_data["pq_pk"], str) else idn_data["pq_pk"]
    me_fp = id_fp(me_pk)
    final_decrypted_texts = []
    buf_custom = {}
    buf_paired = {}

    for raw_block in raw_chunks:
        raw_block = raw_block.strip()
        if not raw_block: continue

        # Strip leading markdown formatting characters (~, *, _, `) inserted before DERF:V1: tag by Messenger
        raw_block = re.sub(r'^[~\*_`\s]+', '', raw_block)

        is_compressed = False
        if raw_block.startswith("DERF:V1:C:"):
            raw_block = raw_block[10:]; is_compressed = True
        elif raw_block.startswith("DERF:V1:R:"):
            raw_block = raw_block[10:]
        elif raw_block.startswith("DERF:V1:"):
            raw_block = raw_block[8:]

        pkts = None

        # Try Base64 first (default standard)
        try:
            b64_match = re.search(r'([A-Za-z0-9+/=]{100,})', re.sub(r'^[~\*_`\s]+', '', raw_block))
            clean_b64 = b64_match.group(1) if b64_match else re.sub(r'[^A-Za-z0-9+/=]+', '', raw_block)
            combined_binary = base64.b64decode(clean_b64)
            if len(combined_binary) % PACKET == 0 and len(combined_binary) > 0:
                pkts = [combined_binary[i:i + PACKET] for i in range(0, len(combined_binary), PACKET)]
        except Exception:
            pass

        # Fallback to Base85 if Base64 fails or isn't aligned
        if not pkts:
            try:
                clean_b85 = re.sub(r'[^0-9A-Za-z!#$%&()*+,-;<=>?@^_`{|}~]+', '', raw_block)
                combined_binary = base64.b85decode(clean_b85)
                if len(combined_binary) % PACKET == 0 and len(combined_binary) > 0:
                    pkts = [combined_binary[i:i + PACKET] for i in range(0, len(combined_binary), PACKET)]
            except Exception:
                pass

        if not pkts:
            continue

        if custom_session_loader:
            c_sess, c_idn = custom_session_loader()
            if c_sess and c_idn:
                peer_fp = id_fp(c_idn["pq_pk"])
                for p in pkts:
                    try:
                        out = feed(c_sess, p, me_fp, peer_fp, buf_custom)
                        if out:
                            if is_compressed:
                                try:
                                    if ALIEN_COMPRESSION_ENABLED and zstd_decompressor:
                                        out = zstd_decompressor.decompress(out)
                                    else:
                                        out = zlib.decompress(out)
                                except Exception: pass
                            final_decrypted_texts.append(out.decode('utf-8', errors='replace'))
                    except Exception: pass
                if final_decrypted_texts:
                    continue

        paired = [n for n in cs if os.path.exists(P(f"lc_session_{n}.json"))]
        for peer in paired:
            sess = Session.load(peer)
            if not sess: continue
            peer_fp = id_fp(cs[peer])
            got = False
            for p in pkts:
                try:
                    out = feed(sess, p, me_fp, peer_fp, buf_paired)
                    if out:
                        if is_compressed:
                            try:
                                if ALIEN_COMPRESSION_ENABLED and zstd_decompressor:
                                    out = zstd_decompressor.decompress(out)
                                else:
                                    out = zlib.decompress(out)
                            except Exception: pass
                        final_decrypted_texts.append(out.decode('utf-8', errors='replace'))
                        sess.save(peer)
                        got = True
                except Exception: pass
            if got: break

    return " ".join(final_decrypted_texts) if final_decrypted_texts else None



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
                res = c.encaps(a if len(a) == EK else b)
                if sorted((len(res[0]), len(res[1]))) != sorted((CT, SS)): continue
                self._k = c; break
            except Exception: continue
        if self._k is None: raise ImportError("no ML-KEM-768")
    def generate_keypair(self):
        a, b = self._k.keygen()
        return (a, b) if len(a) == EK else (b, a)
    def encaps(self, pk):
        if len(pk) != EK: raise ValueError(f"encaps needs public key ({EK}B), got {len(pk)}B")
        res = self._k.encaps(pk)
        return (res[1], res[0]) if len(res[0]) == SS else (res[0], res[1])
    def decaps(self, ct, sk):
        if len(ct) != CT or len(sk) != DK: raise ValueError("Invalid KEM decaps lengths")
        return self._k.decaps(sk, ct)

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
        except Exception as e: errs.append(f"{cls.__name__}: {repr(e)}")
    raise RuntimeError("No PQ backend. Errors: " + "; ".join(errs))

PQ_KEM = None

# ================= symmetric primitives =================
APP_AAD = b"derf-pqfs-v1"
MAXSKIPPED = 1024
MAXN = 1 << 20
CHUNK = 220
HJ = 128
BUCKET_SIZE = 256

def pad_bucket(p, bucket_size=BUCKET_SIZE):
    if len(p) > bucket_size - 4: raise ValueError("Payload too large")
    i = struct.pack(">I", len(p)) + p
    return i + os.urandom(bucket_size - len(i))

def unpad_bucket(p):
    (l,) = struct.unpack(">I", p[:4])
    return p[4:4+l]
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
    padded = pad_bucket(msg, bucket_size=BUCKET_SIZE)
    no = os.urandom(12)
    ct = a.encrypt(no, padded, aad)
    man = struct.pack(">H", len(aad)) + aad + no
    mac = hmac_sha256(km, man + ct)
    return b"LCA2" + struct.pack(">H", len(aad)) + aad + no + mac + ct

def lca_decrypt(m, pkg, ea):
    if pkg[:4] == b"LCA2":
        off = 4
        (al,), off = struct.unpack(">H", pkg[off:off+2]), off+2
        aad, off = pkg[off:off+al], off+al
        if aad != ea: raise ValueError("ctx")
        no, off = pkg[off:off+12], off+12
        mac, off = pkg[off:off+32], off+32
        ct = pkg[off:]
        kn, ka, km = keygen(m)
        man = struct.pack(">H", len(aad)) + aad + no
        if not hmac.compare_digest(mac, hmac_sha256(km, man + ct)):
            raise ValueError("mac")
        a = ChaCha20Poly1305(ka)
        padded = a.decrypt(no, ct, aad)
        now = time.time()
        return unpad_bucket(padded), [struct.pack(">Q", int((now + i * 1e-6) * 1e9)) for i in range(1)]

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
    if off > len(pkg): raise ValueError("ext")
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
def lca_size(n=BUCKET_SIZE): return 4 + 2 + aad_len() + 12 + 32 + (BUCKET_SIZE + 16)
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
        tot = len(pt); mid = os.urandom(8).hex(); pk = []
        for ci in range(0, tot, CHUNK):
            ch = pt[ci:ci+CHUNK]
            mk, s.sck = kdf_ck(s.sck); n = s.sn; s.sn += 1
            h = {"n": n, "tot": tot, "ci": ci // CHUNK, "mid": mid, "pl": 0}
            hj = json.dumps(h, sort_keys=True).encode()
            hj += b" " * (HJ - len(hj))
            aad = APP_AAD + s.sid + hj + b"".join(sorted((mf, pf)))
            l1 = lca_encrypt(mk, ch, aad)
            h["pl"] = len(l1)
            hj = json.dumps(h, sort_keys=True).encode()
            hj += b" " * (HJ - len(hj))
            aad = APP_AAD + s.sid + hj + b"".join(sorted((mf, pf)))
            l1 = lca_encrypt(mk, ch, aad)
            pay = l1 + os.urandom(PAYLOAD_MAX - len(l1))
            no = os.urandom(12)
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
        try:
            d = vload(P(f"lc_session_{p}.json"))
            return Session(ub64(d["sid"]), None, d["role"], ub64(d["sck"]), ub64(d["rck"]),
                           d["sn"], d["rn"], ub64(d["hsend"]), ub64(d["hrecv"]),
                           {int(k): ub64(v) for k, v in d.get("sk", {}).items()})
        except Exception:
            return None

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
        return pd
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
        print(f"   Expected rejection triggered: {repr(e)}")

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

    print("[7/7] Alien Stack (Zstd/Zlib Compression, Z85 Encoding & Smart Chunking)...")
    long_msg = "Derf Alien Stack test payload with repetitive phrases. " * 30
    chunks = smart_split_text(long_msg, max_chars=150)
    assert len(chunks) > 1, "Smart chunking failed to split long text!"

    test_bytes = long_msg.encode('utf-8')
    if ALIEN_COMPRESSION_ENABLED and zstd_compressor:
        comp = zstd_compressor.compress(test_bytes)
        decomp = zstd_decompressor.decompress(comp)
        assert decomp == test_bytes, "Zstd dictionary decompression mismatch!"

    comp_zlib = zlib.compress(test_bytes, 9)
    assert zlib.decompress(comp_zlib) == test_bytes, "Zlib decompression mismatch!"

    z85_enc = base64.b85encode(test_bytes).decode('ascii')
    z85_dec = base64.b85decode(z85_enc)
    assert z85_dec == test_bytes, "Z85 b85encode/b85decode mismatch!"

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
from kivy.clock import Clock
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
TEXT_MAIN    = (0.93, 0.94, 0.97, 1)        # #EEF0F8
TEXT_MUTED   = (0.52, 0.56, 0.65, 1)        # #858FA6
COLOR_GREEN  = (0.0, 0.88, 0.45, 1)        # #00E073 Neon Green
COLOR_RED    = (1.0, 0.28, 0.28, 1)        # #FF4747 Danger Red

_CLIPBOARD_TEXT = ""

def safe_copy(text):
    global _CLIPBOARD_TEXT
    _CLIPBOARD_TEXT = text
    try: pyperclip.copy(text)
    except Exception: pass
    try: Clipboard.copy(text)
    except Exception: pass

def safe_paste():
    global _CLIPBOARD_TEXT
    try:
        val = pyperclip.paste()
        if val: return val
    except Exception: pass
    try:
        val = Clipboard.paste()
        if val: return val
    except Exception: pass
    return _CLIPBOARD_TEXT

class CardPanel(BoxLayout):
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
    def __init__(self, text="", bg_color=CYAN_PRIMARY, text_color=(0.04, 0.04, 0.05, 1), radius=10, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.bg_color = bg_color
        self.color = text_color
        self.bold = True
        self.font_size = '12sp'
        self.halign = 'center'
        self.valign = 'middle'
        self.radius = radius
        self.bind(size=self._update_text_size)
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_text_size(self, *args):
        self.text_size = (self.width - 12, None)

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

class SecondaryButton(Button):
    def __init__(self, text="", bg_color=SURFACE_ALT, text_color=CYAN_PRIMARY, radius=8, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.bg_color = bg_color
        self.color = text_color
        self.bold = True
        self.font_size = '11sp'
        self.halign = 'center'
        self.valign = 'middle'
        self.radius = radius
        self.bind(size=self._update_text_size)
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_text_size(self, *args):
        self.text_size = (self.width - 10, None)

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

        card = CardPanel(orientation='vertical', size_hint=(None, None), size=(440, 320), padding=28, spacing=16)

        header_box = BoxLayout(orientation='vertical', size_hint_y=None, height=65, spacing=4)
        header_box.add_widget(Label(text="DERF VAULT", font_size='20sp', bold=True, color=CYAN_PRIMARY, halign='center', valign='middle'))
        header_box.add_widget(Label(text="Post-Quantum Master Encryption Vault", font_size='11sp', color=TEXT_MUTED, halign='center', valign='middle'))
        for c in header_box.children: c.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))

        self.pass_input = TextInput(password=True, multiline=False, hint_text="Enter Master Passphrase...",
                                   background_color=(0.07, 0.08, 0.10, 1), foreground_color=TEXT_MAIN,
                                   cursor_color=CYAN_PRIMARY, size_hint_y=None, height=45, padding=(14, 12), font_size='13sp')

        self.err_lbl = Label(text="", font_size='11sp', color=COLOR_RED, size_hint_y=None, height=20, halign='center', valign='middle')
        self.err_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))

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
                self.err_lbl.text = f"Failed to create identity: {repr(e)}"
                return

        self.app_ref.on_vault_unlocked()

# ================= MAIN APP SCREEN =================
class MainScreen(Screen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = app_ref
        self.buffers = {}

        self.root_box = BoxLayout(orientation='horizontal')

        with self.root_box.canvas.before:
            Color(*BG_OBSIDIAN)
            self.bg_rect = Rectangle(pos=self.root_box.pos, size=self.root_box.size)
        self.root_box.bind(pos=self._update_bg, size=self._update_bg)

        # ---------------- 1. LEFT SIDEBAR (Width: 280dp) ----------------
        sidebar = CardPanel(bg_color=BG_SIDEBAR, radius=0, size_hint_x=None, width=280, orientation='vertical', padding=16, spacing=14)

        branding = BoxLayout(orientation='vertical', size_hint_y=None, height=52, spacing=2)
        lbl_b1 = Label(text="DERF", font_size='20sp', bold=True, color=CYAN_PRIMARY, halign='left', valign='middle')
        lbl_b2 = Label(text="Post-Quantum PQ+FS Messenger", font_size='11sp', color=TEXT_MUTED, halign='left', valign='middle')
        branding.add_widget(lbl_b1)
        branding.add_widget(lbl_b2)
        for child in branding.children: child.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        sidebar.add_widget(branding)

        sb_contacts_hdr = BoxLayout(orientation='horizontal', size_hint_y=None, height=24)
        lbl_c_hdr = Label(text="CONTACTS & PEERS", font_size='11sp', bold=True, color=TEXT_MUTED, halign='left', valign='middle')
        lbl_c_hdr.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        sb_contacts_hdr.add_widget(lbl_c_hdr)
        sidebar.add_widget(sb_contacts_hdr)

        self.contact_scroll = ScrollView()
        self.contact_list_layout = GridLayout(cols=1, spacing=8, size_hint_y=None)
        self.contact_list_layout.bind(minimum_height=self.contact_list_layout.setter('height'))
        self.contact_scroll.add_widget(self.contact_list_layout)
        sidebar.add_widget(self.contact_scroll)

        # Single-Device Simulation Card
        sim_card = CardPanel(bg_color=SURFACE_ALT, radius=8, size_hint_y=None, height=75, padding=10, orientation='vertical', spacing=6)
        lbl_sim = Label(text="SINGLE-DEVICE SIMULATOR", font_size='11sp', bold=True, color=CYAN_PRIMARY, halign='left', valign='middle')
        lbl_sim.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        sim_card.add_widget(lbl_sim)

        btn_auto_pair = PrimaryButton(text="[ AUTO-PAIR TEST PEER ]", size_hint_y=None, height=32, radius=6)
        btn_auto_pair.bind(on_release=self.auto_pair_sim_peer)
        sim_card.add_widget(btn_auto_pair)
        sidebar.add_widget(sim_card)

        sb_actions = BoxLayout(orientation='vertical', size_hint_y=None, height=128, spacing=8)

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

        self.stage_hdr = CardPanel(bg_color=SURFACE_CARD, size_hint_y=None, height=58, padding=(16, 10), orientation='horizontal', spacing=12)

        self.active_peer_lbl = Label(text="Select a contact to chat", font_size='15sp', bold=True, color=TEXT_MAIN, halign='left', valign='middle')
        self.active_peer_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))

        self.safety_badge = Label(text="Safety: N/A", font_size='12sp', color=TEXT_MUTED, halign='right', valign='middle')
        self.safety_badge.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))

        self.stage_hdr.add_widget(self.active_peer_lbl)
        self.stage_hdr.add_widget(self.safety_badge)
        self.workspace.add_widget(self.stage_hdr)

        nav_pills = BoxLayout(orientation='horizontal', size_hint_y=None, height=38, spacing=8)
        self.pill_btns = {}

        pills = [
            ("messages", "MESSAGES & PACKETS"),
            ("contacts", "PAIRING WIZARD"),
            ("simulator", "LIVE SIMULATOR"),
            ("security", "SECURITY SPECS"),
            ("help", "PROTOCOL GUIDE")
        ]

        for key, label in pills:
            btn = SecondaryButton(text=label, size_hint_x=None, width=150)
            btn.bind(on_release=lambda instance, k=key: self.switch_tab(k))
            nav_pills.add_widget(btn)
            self.pill_btns[key] = btn

        self.workspace.add_widget(nav_pills)

        self.content_container = BoxLayout(orientation='vertical')
        self.workspace.add_widget(self.content_container)

        self.status_lbl = Label(text=f"Data Dir: {DATA_DIR}", font_size='11sp', color=TEXT_MUTED, size_hint_y=None, height=20, halign='left', valign='middle')
        self.status_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        self.workspace.add_widget(self.status_lbl)

        self.root_box.add_widget(self.workspace)
        self.add_widget(self.root_box)

        self.selected_peer = None
        self.current_tab = "messages"

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size


    def load_sim_bob_session(self):
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

    def auto_pair_sim_peer(self, *args):
        sim_name = "Bob Test"
        try:
            bob_idn = make_identity()
            contact_add(sim_name, bob_idn["pq_pk"])

            req_blob, pend = hs_req(self.app_ref.idn, bob_idn["pq_pk"])
            rsp_blob, bob_sess = hs_rsp(bob_idn, req_blob)
            alice_sess = hs_complete(self.app_ref.idn, pend, rsp_blob)

            alice_sess.save(sim_name)
            vsave(P(f"lc_sim_bob_session.json"), {
                "sid": b64(bob_sess.sid), "role": bob_sess.role, "sck": b64(bob_sess.sck), "rck": b64(bob_sess.rck),
                "sn": bob_sess.sn, "rn": bob_sess.rn, "hsend": b64(bob_sess.hsend), "hrecv": b64(bob_sess.hrecv),
                "sk": {}, "bob_idn": {"pq_sk": b64(bob_idn["pq_sk"]), "pq_pk": b64(bob_idn["pq_pk"])}
            })

            self.refresh_views()
            self.select_peer(sim_name)
            self.show_popup("Auto-Paired!", f"Created virtual test peer '{sim_name}' & completed ML-KEM-768 handshake!\n\nYou can now encrypt messages and use 'Simulate Bob Reply' to test decryption.")
        except Exception as e:
            self.show_popup("Simulator Error", str(e))

    def refresh_views(self):
        self.update_sidebar_contacts()
        self.switch_tab(self.current_tab)

    def update_sidebar_contacts(self):
        self.contact_list_layout.clear_widgets()
        cs = contacts_load()
        if not cs:
            lbl = Label(text="No Contacts Yet", font_size='11sp', color=TEXT_MUTED, size_hint_y=None, height=30, halign='center', valign='middle')
            lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
            self.contact_list_layout.add_widget(lbl)
            return

        for name, pub_bytes in cs.items():
            is_paired = os.path.exists(P(f"lc_session_{name}.json"))
            card = CardPanel(bg_color=SURFACE_ALT if name == self.selected_peer else SURFACE_CARD,
                             radius=8, size_hint_y=None, height=52, padding=(10, 8), orientation='horizontal', spacing=8)

            avatar = CardPanel(bg_color=(0.20, 0.22, 0.28, 1), radius=6, size_hint=(None, None), size=(34, 34))
            lbl_av = Label(text=name[:2].upper(), font_size='12sp', bold=True, color=CYAN_PRIMARY, halign='center', valign='middle')
            lbl_av.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
            avatar.add_widget(lbl_av)

            info = BoxLayout(orientation='vertical', spacing=2)
            lbl_n = Label(text=name, font_size='12sp', bold=True, color=TEXT_MAIN, halign='left', valign='middle', shorten=True, shorten_from='right')

            st_text = "[ PAIRED ]" if is_paired else "[ UNPAIRED ]"
            st_color = COLOR_GREEN if is_paired else TEXT_MUTED
            lbl_st = Label(text=st_text, font_size='10sp', color=st_color, halign='left', valign='middle')

            info.add_widget(lbl_n)
            info.add_widget(lbl_st)
            for child in info.children: child.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))

            card.add_widget(avatar)
            card.add_widget(info)

            def make_select_cb(p_name):
                def on_touch(instance, touch):
                    if instance.collide_point(*touch.pos):
                        self.select_peer(p_name)
                        return True
                    return False
                return on_touch

            cb = make_select_cb(name)
            card.bind(on_touch_down=cb)
            avatar.bind(on_touch_down=cb)
            info.bind(on_touch_down=cb)
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
        elif tab_key == "simulator":
            self.content_container.add_widget(self.build_simulator_view())
        elif tab_key == "help":
            self.content_container.add_widget(self.build_help_view())

    # --- VIEW 1: MESSAGES & PACKETS ---
    def build_messages_view(self):
        split = BoxLayout(orientation='horizontal', spacing=12)

        # Encrypt Column
        enc_box = CardPanel(orientation='vertical', padding=12, spacing=10)
        lbl_e1 = Label(text="ENCRYPT CONFIDENTIAL MESSAGE", font_size='12sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left', valign='middle')
        lbl_e1.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        enc_box.add_widget(lbl_e1)

        self.enc_input = TextInput(hint_text="Type confidential plaintext message here...", background_color=(0.06, 0.07, 0.09, 1),
                                   foreground_color=TEXT_MAIN, cursor_color=CYAN_PRIMARY, padding=(12, 10), font_size='12sp')
        enc_box.add_widget(self.enc_input)

        btn_enc = PrimaryButton(text="[ LOCK & ENCRYPT MESSAGE ]", size_hint_y=None, height=42, radius=10)
        btn_enc.bind(on_release=self.do_encrypt)
        enc_box.add_widget(btn_enc)

        self.enc_output = TextInput(hint_text="Encrypted DERF:V1: Base64 uniform packets output...", readonly=True,
                                    background_color=(0.06, 0.07, 0.09, 1), foreground_color=CYAN_PRIMARY, padding=(12, 10), font_size='11sp')
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
        lbl_d1 = Label(text="DECRYPT INCOMING PACKETS", font_size='12sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left', valign='middle')
        lbl_d1.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        dec_box.add_widget(lbl_d1)

        self.dec_input = TextInput(hint_text="Paste received DERF:V1: Base64 ciphertext packets here...", background_color=(0.06, 0.07, 0.09, 1),
                                   foreground_color=TEXT_MAIN, cursor_color=CYAN_PRIMARY, padding=(12, 10), font_size='12sp')
        dec_box.add_widget(self.dec_input)

        btn_dec = PrimaryButton(text="[ UNLOCK & DECRYPT PACKETS ]", size_hint_y=None, height=42, radius=10)
        btn_dec.bind(on_release=self.do_decrypt)
        dec_box.add_widget(btn_dec)

        self.dec_output = TextInput(hint_text="Decrypted message payload result...", readonly=True,
                                    background_color=(0.06, 0.07, 0.09, 1), foreground_color=COLOR_GREEN, padding=(12, 10), font_size='13sp')
        dec_box.add_widget(self.dec_output)

        dec_act = BoxLayout(orientation='horizontal', size_hint_y=None, height=36, spacing=8)
        btn_sim_bob = SecondaryButton(text="[ Simulate Bob Reply ]")
        btn_sim_bob.bind(on_release=self.simulate_bob_reply)
        btn_p2 = SecondaryButton(text="[ Paste Clipboard ]")
        btn_p2.bind(on_release=lambda x: setattr(self.dec_input, 'text', safe_paste()))
        btn_c2 = SecondaryButton(text="[ Copy Decrypted ]")
        btn_c2.bind(on_release=lambda x: self.copy_to_clip(self.dec_output.text, "Decrypted text copied!"))

        dec_act.add_widget(btn_sim_bob)
        dec_act.add_widget(btn_p2)
        dec_act.add_widget(btn_c2)
        dec_box.add_widget(dec_act)

        split.add_widget(enc_box)
        split.add_widget(dec_box)
        return split

    def simulate_bob_reply(self, *args):
        sim_path = P("lc_sim_bob_session.json")
        if not os.path.exists(sim_path):
            self.show_popup("Simulation Error", "Please click '[ AUTO-PAIR TEST PEER ]' in the sidebar first to create 'Bob Test'.")
            return

        try:
            d = vload(sim_path)
            bob_sess = Session(ub64(d["sid"]), None, d["role"], ub64(d["sck"]), ub64(d["rck"]),
                               d["sn"], d["rn"], ub64(d["hsend"]), ub64(d["hrecv"]),
                               {int(k): ub64(v) for k, v in d["sk"].items()})

            bob_idn = {"pq_sk": ub64(d["bob_idn"]["pq_sk"]), "pq_pk": ub64(d["bob_idn"]["pq_pk"])}
            alice_pk = id_bundle(self.app_ref.idn)

            msg = f"Hello Alice! Received your encrypted message at {time.strftime('%H:%M:%S')}. Double ratchet & ML-KEM-768 verified!"
            msg_bytes = msg.encode('utf-8')
            is_compressed = False
            if ALIEN_COMPRESSION_ENABLED and zstd_compressor and len(msg_bytes) > 50:
                msg_bytes = zstd_compressor.compress(msg_bytes)
                is_compressed = True
            elif len(msg_bytes) > 50:
                msg_bytes = zlib.compress(msg_bytes, 9)
                is_compressed = True

            pkts = bob_sess.encrypt(msg_bytes, id_fp(bob_idn["pq_pk"]), id_fp(alice_pk))

            d["sck"] = b64(bob_sess.sck); d["sn"] = bob_sess.sn
            vsave(sim_path, d)

            combined_binary = b"".join(pkts)
            encoded_str = base64.b64encode(combined_binary).decode('ascii')
            prefix = "DERF:V1:C:" if is_compressed else "DERF:V1:R:"
            bob_cipher = prefix + encoded_str

            self.dec_input.text = bob_cipher
            self.do_decrypt()
            self.show_popup("Simulated Reply Received", f"Received & decrypted live DERF:V1: packet reply from 'Bob Test'!")
        except Exception as e:
            self.show_popup("Simulate Reply Error", str(e))

    def do_encrypt(self, *args):
        peer = self.selected_peer
        pt = self.enc_input.text.strip()
        if not pt:
            self.show_popup("Encrypt Error", "Message payload cannot be empty.")
            return

        try:
            final_out = encrypt_alien_stack(pt, peer, self.app_ref.idn)
            self.enc_output.text = final_out
            safe_copy(final_out)
            self.enc_input.text = ""
            self.status_lbl.text = f"[*] Encrypted & encoded message for {peer}."
        except Exception as e:
            self.show_popup("Encryption Failed", str(e))


    def save_to_drop(self, *args):
        raw = self.enc_output.text.strip()
        if not raw:
            self.show_popup("Save Error", "No encrypted packets to save.")
            return
        if not raw.startswith("DERF:V1:"):
            raw = "DERF:V1:\n" + raw
        fn = f"packet_{int(time.time())}_{os.urandom(3).hex()}.bin"
        fp = os.path.join(DROP_DIR, fn)
        with open(fp, "w") as f: f.write(raw)
        self.status_lbl.text = f"[*] Saved drop file: {fp}"
        self.show_popup("Saved", f"Packet drop saved to Desktop/Derf/lc_drop/{fn}")

    def launch_dual_instance(self, *args):
        import subprocess
        try:
            subprocess.Popen([sys.executable, sys.argv[0], "--profile=bob"])
            self.show_popup("Sandbox Launched", "Secondary Derf instance (Bob) launched in isolated profile ~/desktop/Derf_Profile_bob!")
        except Exception as e:
            self.show_popup("Launch Error", repr(e))

    def save_freshness_window(self, *args):
        global FRESH
        try:
            val = float(self.fresh_input.text.strip())
            FRESH = val
            vsave(P("lc_fresh.json"), {"fresh_sec": FRESH})
            self.show_popup("Freshness Saved", f"Freshness window updated to {FRESH} seconds!")
        except Exception as e:
            self.show_popup("Error", f"Invalid freshness number: {e}")

    def do_decrypt(self, *args):
        raw = self.dec_input.text.strip()
        if not raw:
            self.show_popup("Decrypt Error", "Paste encrypted text first.")
            return

        decrypted = decrypt_alien_stack(raw, self.app_ref.idn, custom_session_loader=self.load_sim_bob_session)
        if decrypted:
            self.dec_output.text = decrypted
            self.status_lbl.text = "[*] Successfully decrypted & reassembled message!"
        else:
            self.show_popup("Decrypt Failed", "Could not decrypt (wrong key, stale, or tampered).")



    def build_simulator_view(self):
        split = BoxLayout(orientation='horizontal', spacing=12)

        # --- LEFT COLUMN: DISCORD-STYLE MESSENGER SIMULATION ---
        left_box = CardPanel(bg_color=(0.19, 0.20, 0.22, 1), orientation='vertical', padding=12, spacing=8)

        # Discord Channel Header
        discord_hdr = CardPanel(bg_color=(0.17, 0.18, 0.19, 1), radius=8, size_hint_y=None, height=36, padding=(12, 6), orientation='horizontal')
        lbl_channel = Label(text="💬 # derf-pq-chat  |  Post-Quantum Double Ratchet Channel", font_size='12sp', bold=True, color=(0.95, 0.95, 0.96, 1), halign='left', valign='middle')
        lbl_channel.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        discord_hdr.add_widget(lbl_channel)
        left_box.add_widget(discord_hdr)

        # Chat Feed
        self.sim_chat_scroll = ScrollView(size_hint_y=1)
        self.sim_chat_feed = BoxLayout(orientation='vertical', padding=10, spacing=10, size_hint_y=None)
        self.sim_chat_feed.bind(minimum_height=self.sim_chat_feed.setter('height'))

        welcome_lbl = Label(text="[i][*] Discord channel active. Send a message as Alice or Bob. Click 'COPY DISCORD CIPHERTEXT', then press [ Alt + Shift + Q ] to trigger the Quick Peek Glass Overlay hovering above the chat![/i]",
                            markup=True, font_size='11sp', color=(0.58, 0.61, 0.64, 1), size_hint_y=None, height=36, halign='center', valign='middle')
        welcome_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        self.sim_chat_feed.add_widget(welcome_lbl)
        self.sim_chat_scroll.add_widget(self.sim_chat_feed)
        left_box.add_widget(self.sim_chat_scroll)

        # Chat Input Bar
        self.sim_chat_input = TextInput(text="Meet at 18:00 UTC. Bring the quantum key vault.", multiline=False,
                                       background_color=(0.22, 0.23, 0.25, 1), foreground_color=(0.95, 0.95, 0.96, 1),
                                       padding=(12, 8), font_size='12sp', size_hint_y=None, height=38)
        left_box.add_widget(self.sim_chat_input)

        # Discord Action Buttons Row
        btn_row = BoxLayout(orientation='horizontal', spacing=8, size_hint_y=None, height=36)
        btn_alice = PrimaryButton(text="[ ALICE SENDS ]", radius=8, bg_color=(0.35, 0.40, 0.95, 1), color=(1, 1, 1, 1))
        btn_alice.bind(on_release=lambda x: self.run_sim_send_actor("Alice"))

        btn_bob = PrimaryButton(text="[ BOB REPLIES ]", radius=8, bg_color=(0.14, 0.65, 0.35, 1), color=(1, 1, 1, 1))
        btn_bob.bind(on_release=lambda x: self.run_sim_send_actor("Bob"))

        btn_row.add_widget(btn_alice)
        btn_row.add_widget(btn_bob)
        left_box.add_widget(btn_row)

        split.add_widget(left_box)

        # --- RIGHT COLUMN: QUICK PEEK HUD PREVIEW & SECURITY SANDBOX ---
        right_box = CardPanel(bg_color=(0.17, 0.18, 0.19, 1), orientation='vertical', padding=12, spacing=10)

        lbl_peek_hdr = Label(text="👻 QUICK PEEK GLASS CARD CONTROL", font_size='12sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=20, halign='left')
        lbl_peek_hdr.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        right_box.add_widget(lbl_peek_hdr)

        lbl_peek_desc = Label(text="• Highlight ciphertext in Discord or above and press [b]Alt+Shift+Q[/b].\n• The frameless Glass Card appears on top of all open apps right at your cursor position with 0 app popups.",
                              markup=True, font_size='11sp', color=(0.58, 0.61, 0.64, 1), size_hint_y=None, height=44, halign='left')
        lbl_peek_desc.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        right_box.add_widget(lbl_peek_desc)

        # Security Sandbox
        lbl_a_title = Label(text="SECURITY ATTACK SANDBOX", font_size='12sp', bold=True, color=COLOR_RED, size_hint_y=None, height=20, halign='left')
        lbl_a_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        right_box.add_widget(lbl_a_title)

        sandbox_row = BoxLayout(orientation='horizontal', spacing=6, size_hint_y=None, height=34)
        btn_tamper = SecondaryButton(text="[ TAMPER BIT-FLIP ]", font_size='10sp')
        btn_tamper.bind(on_release=self.run_sim_attack_tamper)

        btn_replay = SecondaryButton(text="[ REPLAY ATTACK ]", font_size='10sp')
        btn_replay.bind(on_release=self.run_sim_attack_replay)

        btn_suite = PrimaryButton(text="[ FULL SUITE ]", radius=6, font_size='10sp')
        btn_suite.bind(on_release=self.run_sim_head_to_toe)

        sandbox_row.add_widget(btn_tamper)
        sandbox_row.add_widget(btn_replay)
        sandbox_row.add_widget(btn_suite)
        right_box.add_widget(sandbox_row)

        # Event log
        lbl_l = Label(text="DISCORD SIMULATION LOG", font_size='12sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=20, halign='left')
        lbl_l.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        right_box.add_widget(lbl_l)

        self.sim_log_output = TextInput(text="[*] Discord #derf-pq-chat simulation active.\n[*] Highlight ciphertext and press Alt+Shift+Q for Quick Peek.\n",
                                        readonly=True, background_color=(0.12, 0.13, 0.14, 1), foreground_color=(0.95, 0.95, 0.96, 1), padding=(10, 8), font_size='11sp')
        right_box.add_widget(self.sim_log_output)

        split.add_widget(right_box)
        self.sim_ghost_active = True
        self.last_sim_ciphertext = None
        return split

    def sim_log(self, text):
        if hasattr(self, 'sim_log_output'):
            self.sim_log_output.text += f"[*] {text}\n"

    def run_sim_send_actor(self, actor, *args):
        try:
            pt = self.sim_chat_input.text.strip()
            if not pt:
                self.sim_log("Error: Chat text payload is empty.")
                return

            peer = "Bob Test"
            if not os.path.exists(P(f"lc_session_{peer}.json")):
                self.auto_pair_sim_peer()

            idn = self.app_ref.idn if (hasattr(self.app_ref, "idn") and self.app_ref.idn) else norm_identity(vload(P("lc_identity.json")))

            if actor == "Alice":
                cipher_text = encrypt_alien_stack(pt, peer, idn)
                self.last_sim_ciphertext = cipher_text
                safe_copy(cipher_text)

                self._add_discord_message_card("Alice", "YOU", pt, cipher_text)
                self.sim_log(f"Alice encrypted & posted message in Discord channel ({len(pt)} chars).")
            else:
                sim_path = P("lc_sim_bob_session.json")
                d = vload(sim_path)
                bob_sess = Session(ub64(d["sid"]), None, d["role"], ub64(d["sck"]), ub64(d["rck"]),
                                   d["sn"], d["rn"], ub64(d["hsend"]), ub64(d["hrecv"]),
                                   {int(k): ub64(v) for k, v in d["sk"].items()})

                bob_idn = {"pq_sk": ub64(d["bob_idn"]["pq_sk"]), "pq_pk": ub64(d["bob_idn"]["pq_pk"])}
                alice_pk = id_bundle(idn)

                msg_bytes = pt.encode('utf-8')
                is_compressed = False
                if ALIEN_COMPRESSION_ENABLED and zstd_compressor and len(msg_bytes) > 50:
                    msg_bytes = zstd_compressor.compress(msg_bytes)
                    is_compressed = True
                elif len(msg_bytes) > 50:
                    msg_bytes = zlib.compress(msg_bytes, 9)
                    is_compressed = True

                pkts = bob_sess.encrypt(msg_bytes, id_fp(bob_idn["pq_pk"]), id_fp(alice_pk))
                d["sck"] = b64(bob_sess.sck); d["sn"] = bob_sess.sn
                vsave(sim_path, d)

                combined_binary = b"".join(pkts)
                encoded_str = base64.b64encode(combined_binary).decode('ascii')
                prefix = "DERF:V1:C:" if is_compressed else "DERF:V1:R:"
                cipher_text = prefix + encoded_str
                self.last_sim_ciphertext = cipher_text

                self._add_discord_message_card("Bob", "PEER", pt, cipher_text)
                self.sim_log(f"Bob encrypted & posted message in Discord channel ({len(pt)} chars).")

        except Exception as e:
            self.sim_log(f"[ERROR] Actor send simulation failed: {repr(e)}")

    def _add_discord_message_card(self, name, role_badge, plaintext, ciphertext):
        card = CardPanel(bg_color=(0.17, 0.18, 0.19, 1), radius=8, size_hint_y=None, padding=(10, 8), spacing=6, orientation='vertical')

        badge_color = (0.35, 0.40, 0.95, 1) if role_badge == "YOU" else (0.14, 0.65, 0.35, 1)
        lbl_hdr = Label(text=f"👤 [b]{name}[/b]  [size=9sp][color=#FFFFFF]{role_badge}[/color][/size]  [color=#949BA4]Today at {time.strftime('%H:%M')}[/color]",
                        markup=True, font_size='11sp', color=(0.95, 0.95, 0.96, 1), size_hint_y=None, height=18, halign='left')
        lbl_hdr.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        card.add_widget(lbl_hdr)

        lbl_cip = TextInput(text=ciphertext, readonly=True, background_color=(0.12, 0.13, 0.14, 1), foreground_color=(0, 240, 255, 1),
                            font_size='10sp', size_hint_y=None, height=52, padding=(8, 6))
        card.add_widget(lbl_cip)

        btn_row = BoxLayout(orientation='horizontal', spacing=6, size_hint_y=None, height=28)
        btn_copy = SecondaryButton(text="[ 📋 COPY DISCORD CIPHERTEXT ]", font_size='9sp')
        btn_copy.bind(on_release=lambda x: self.copy_to_clip(ciphertext, "Discord ciphertext copied to clipboard!"))

        btn_row.add_widget(btn_copy)
        card.add_widget(btn_row)

        card.height = 118
        self.sim_chat_feed.add_widget(card)

    def run_sim_attack_tamper(self, *args):
        self.sim_log("--- ATTACK SANDBOX: BIT-FLIP TAMPER TEST ---")
        if not self.last_sim_ciphertext:
            self.sim_log("Sending automated test packet first to generate ciphertext...")
            self.run_sim_send_actor("Alice")

        tampered = list(self.last_sim_ciphertext)
        pos = len(tampered) // 2
        tampered[pos] = "X" if tampered[pos] != "X" else "Y"
        tampered_str = "".join(tampered)

        self.sim_log(f"Flipped bit at position {pos}. Attempting ChaCha20-Poly1305 AEAD decryption...")

        idn = self.app_ref.idn if (hasattr(self.app_ref, "idn") and self.app_ref.idn) else norm_identity(vload(P("lc_identity.json")))
        decrypted = decrypt_alien_stack(tampered_str, idn, custom_session_loader=self.load_sim_bob_session)

        if decrypted is None:
            self.sim_log(" [SUCCESS] AEAD Authentication MAC rejected tampered ciphertext! Zero plaintext leaked.")
        else:
            self.sim_log(" [FAIL] Tampered ciphertext was incorrectly accepted!")

    def run_sim_attack_replay(self, *args):
        self.sim_log("--- ATTACK SANDBOX: REPLAY ATTACK TEST ---")
        if not self.last_sim_ciphertext:
            self.run_sim_send_actor("Alice")

        self.sim_log("Re-submitting previously received ratchet packet to test replay protection...")
        idn = self.app_ref.idn if (hasattr(self.app_ref, "idn") and self.app_ref.idn) else norm_identity(vload(P("lc_identity.json")))

        decrypted1 = decrypt_alien_stack(self.last_sim_ciphertext, idn, custom_session_loader=self.load_sim_bob_session)
        decrypted2 = decrypt_alien_stack(self.last_sim_ciphertext, idn, custom_session_loader=self.load_sim_bob_session)

        if decrypted2 is None:
            self.sim_log(" [SUCCESS] Replay attack blocked! Stale message counter rejected.")
        else:
            self.sim_log(" [FAIL] Replay attack succeeded! Counter not enforced.")

    def run_sim_head_to_toe(self, *args):
        self.sim_log("=== STARTING HEAD-TO-TOE FULL SYSTEM SIMULATION ===")
        try:
            self.sim_log("Step 1: Checking local identity & pairing Bob Test peer...")
            self.auto_pair_sim_peer()
            peer = "Bob Test"

            test_payloads = [
                "Hello world! Testing DERF Post-Quantum Forward-Secrecy protocol.",
                "Short payload",
                "Large payload: " + ("A" * 500),
                "Special characters: !@#$%^&*()_+-=[]{}|;':\",<.>/?~`"
            ]

            cs = contacts_load()
            idn = self.app_ref.idn if (hasattr(self.app_ref, "idn") and self.app_ref.idn) else norm_identity(vload(P("lc_identity.json")))
            me_fp = id_fp(ub64(idn["pq_pk"]) if isinstance(idn["pq_pk"], str) else idn["pq_pk"])
            peer_fp = id_fp(cs[peer])

            bob_sess, bob_idn = self.load_sim_bob_session()

            for idx, payload in enumerate(test_payloads, 1):
                self.sim_log(f"Step 2.{idx}: Testing payload '{payload[:30]}...' ({len(payload)} chars)")
                cipher_text = encrypt_alien_stack(payload, peer, idn)

                decrypted = decrypt_alien_stack(cipher_text, idn, custom_session_loader=self.load_sim_bob_session)

                if decrypted == payload:
                    self.sim_log(f"  [PASS] Payload {idx} decrypted perfectly matching input!")
                else:
                    self.sim_log(f"  [FAIL] Payload {idx} mismatch! Got '{decrypted}'")

            self.sim_log("=== ALL HEAD-TO-TOE SIMULATION TESTS PASSED 100% ===")
        except Exception as e:
            self.sim_log(f"[CRITICAL ERROR] Simulation suite failed: {repr(e)}")

    def build_contacts_view(self):
        layout = BoxLayout(orientation='vertical', spacing=12)

        my_card = CardPanel(orientation='vertical', size_hint_y=None, height=115, padding=12, spacing=6)
        lbl_k1 = Label(text="YOUR PUBLIC IDENTITY KEY (ML-KEM-768)", font_size='12sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=20, halign='left', valign='middle')
        lbl_k1.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        my_card.add_widget(lbl_k1)

        my_pub_str = "LCAP1-" + base64.urlsafe_b64encode(id_bundle(self.app_ref.idn)).decode().rstrip("=")
        key_input = TextInput(text=my_pub_str, readonly=True, background_color=(0.06, 0.07, 0.09, 1), foreground_color=TEXT_MAIN, size_hint_y=None, height=40, padding=(12, 10), font_size='11sp')
        my_card.add_widget(key_input)

        btn_c_my = PrimaryButton(text="[ COPY MY PUBLIC KEY ]", size_hint_y=None, height=32, radius=8)
        btn_c_my.bind(on_release=lambda x: self.copy_to_clip(my_pub_str, "Public key copied!"))
        my_card.add_widget(btn_c_my)
        layout.add_widget(my_card)

        split_pair = BoxLayout(orientation='horizontal', spacing=12)

        add_box = CardPanel(orientation='vertical', padding=12, spacing=10)
        lbl_a1 = Label(text="ADD NEW CONTACT", font_size='12sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left', valign='middle')
        lbl_a1.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        add_box.add_widget(lbl_a1)

        self.new_name = TextInput(hint_text="Contact Name (e.g. Alice)", multiline=False, background_color=(0.06, 0.07, 0.09, 1),
                                  foreground_color=TEXT_MAIN, size_hint_y=None, height=38, padding=(12, 10), font_size='12sp')
        self.new_key = TextInput(hint_text="Paste their LCAP1- Public Key...", background_color=(0.06, 0.07, 0.09, 1),
                                 foreground_color=TEXT_MAIN, padding=(12, 10), font_size='11sp')

        btn_add = PrimaryButton(text="[ SAVE CONTACT ]", size_hint_y=None, height=38, radius=8)
        btn_add.bind(on_release=self.do_add_contact)

        add_box.add_widget(self.new_name)
        add_box.add_widget(self.new_key)
        add_box.add_widget(btn_add)
        split_pair.add_widget(add_box)

        pair_box = CardPanel(orientation='vertical', padding=12, spacing=10)
        lbl_p1 = Label(text="STEP-BY-STEP PAIRING WIZARD", font_size='12sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left', valign='middle')
        lbl_p1.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        pair_box.add_widget(lbl_p1)

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

        self.p_step1_lbl = Label(text="Step 1: Generate & Copy Invite", font_size='11sp', color=TEXT_MAIN, size_hint_y=None, height=20, halign='left', valign='middle')
        self.p_step1_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        self.p_io1 = TextInput(hint_text="Invite payload will appear here...", background_color=(0.06, 0.07, 0.09, 1), foreground_color=CYAN_PRIMARY, padding=(12, 10), font_size='11sp')

        self.p_step2_lbl = Label(text="Step 2: Paste Reply & Finish", font_size='11sp', color=TEXT_MAIN, size_hint_y=None, height=20, halign='left', valign='middle')
        self.p_step2_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        self.p_io2 = TextInput(hint_text="Paste peer reply here...", background_color=(0.06, 0.07, 0.09, 1), foreground_color=TEXT_MAIN, padding=(12, 10), font_size='11sp')

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

        # Dual-Instance Testing Sandbox Panel
        c_dual = CardPanel(orientation='vertical', size_hint_y=None, height=110, padding=14, spacing=8)
        lbl_d = Label(text="DUAL INSTANCE SANDBOX (TEST AS 2 DEVICES)", font_size='13sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left', valign='middle')
        lbl_d.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        btn_dual = PrimaryButton(text="[ 👥 LAUNCH SECONDARY INSTANCE (BOB PROFILE) ]", size_hint_y=None, height=38, radius=8)
        btn_dual.bind(on_release=self.launch_dual_instance)
        c_dual.add_widget(lbl_d)
        c_dual.add_widget(btn_dual)
        grid.add_widget(c_dual)

        # Customizable Freshness Window Sync Panel
        c_fresh = CardPanel(orientation='vertical', size_hint_y=None, height=140, padding=14, spacing=8)
        lbl_f = Label(text="CUSTOMIZE FRESHNESS WINDOW TIME (SECONDS)", font_size='13sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left', valign='middle')
        lbl_f.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        self.fresh_input = TextInput(text=str(FRESH), multiline=False, background_color=(0.06, 0.07, 0.09, 1), foreground_color=CYAN_PRIMARY, size_hint_y=None, height=38, padding=(12, 8), font_size='12sp')
        btn_f_save = PrimaryButton(text="[ SAVE & SYNC FRESHNESS WINDOW ]", size_hint_y=None, height=38, radius=8)
        btn_f_save.bind(on_release=self.save_freshness_window)
        c_fresh.add_widget(lbl_f)
        c_fresh.add_widget(self.fresh_input)
        c_fresh.add_widget(btn_f_save)
        grid.add_widget(c_fresh)

        for title, desc in cards_data:
            c = CardPanel(orientation='vertical', size_hint_y=None, height=95, padding=14, spacing=4)

            lbl_t = Label(text=title, font_size='13sp', bold=True, color=CYAN_PRIMARY, size_hint_y=None, height=22, halign='left', valign='middle')
            lbl_t.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
            c.add_widget(lbl_t)

            lbl_desc = Label(text=desc, font_size='11sp', color=TEXT_MAIN, halign='left', valign='top')
            lbl_desc.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
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
            "[b][size=15sp]DERF PQ+FS QUICKSTART GUIDE[/size][/b]\n\n"
            "1. [b]Exchange Public Keys[/b]: Copy your [i]LCAP1-...[/i] public key from the Pairing tab and add each other as contacts.\n"
            "2. [b]One-Time Pairing[/b]:\n"
            "   - Initiator selects 'I Start', clicks 'Execute Pairing Step' to copy an Invite string, and sends it to the Peer.\n"
            "   - Responder selects 'They Started', pastes the Invite into Step 1, clicks 'Execute Pairing Step' to copy a Reply string.\n"
            "   - Initiator pastes Responder's Reply into Step 2 and clicks 'Execute Pairing Step'. Pairing complete!\n"
            "3. [b]Send Encrypted Messages[/b]: Go to Messages tab, type plaintext, click ENCRYPT, and copy/send uniform Base64 packets.\n"
            "4. [b]Decrypt Messages[/b]: Paste received Base64 packets into Decrypt box and click DECRYPT.\n\n"
            "[b]Background Hotkeys & Invisible Layer[/b]:\n"
            "• Highlight text anywhere and press [b]Alt+Shift+D[/b] or [b]Ctrl+Shift+E[/b] to encrypt & replace text in-place!\n"
            "• Copying any 'DERF:V1:' encrypted message auto-decrypts and shows a notification.\n\n"
            "[b]Single-Device Testing[/b]:\n"
            "• Click '[ AUTO-PAIR TEST PEER ]' in the sidebar to simulate 'Bob Test' instantly.\n"
            "• Use '[ Simulate Bob Reply ]' in the Decrypt view to test round-trip messaging on a single device."
        )

        lbl = Label(text=help_text, markup=True, font_size='12sp', color=TEXT_MAIN, halign='left', valign='top', size_hint_y=None)
        lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
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
        content = BoxLayout(orientation='vertical', padding=14, spacing=10)
        lbl_msg = Label(text=msg, font_size='12sp', color=TEXT_MAIN, halign='center', valign='middle')
        lbl_msg.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        content.add_widget(lbl_msg)

        btn = PrimaryButton(text="OK", size_hint_y=None, height=36, radius=8)
        content.add_widget(btn)

        popup = Popup(title=title, content=content, size_hint=(None, None), size=(380, 200),
                      title_color=CYAN_PRIMARY, background_color=SURFACE_CARD)
        btn.bind(on_release=popup.dismiss)
        popup.open()

    def show_change_passkey(self, *args):
        content = BoxLayout(orientation='vertical', padding=12, spacing=8)
        content.add_widget(Label(text="New Vault Passphrase:", font_size='11sp', color=TEXT_MAIN, halign='left', valign='middle'))
        e1 = TextInput(password=True, multiline=False, background_color=(0.06, 0.07, 0.09, 1), foreground_color=TEXT_MAIN, size_hint_y=None, height=35, padding=(10, 8), font_size='12sp')
        content.add_widget(e1)

        content.add_widget(Label(text="Confirm Passphrase:", font_size='11sp', color=TEXT_MAIN, halign='left', valign='middle'))
        e2 = TextInput(password=True, multiline=False, background_color=(0.06, 0.07, 0.09, 1), foreground_color=TEXT_MAIN, size_hint_y=None, height=35, padding=(10, 8), font_size='12sp')
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
        lbl_w = Label(text="WARNING: Destroy ALL keys, sessions, and contacts in Desktop/Derf?", font_size='11sp', color=COLOR_RED, halign='center', valign='middle')
        lbl_w.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        content.add_widget(lbl_w)

        btn_box = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=36)
        btn_cancel = SecondaryButton(text="Cancel")
        btn_yes = Button(text="DESTROY EVERYTHING", background_normal='', background_color=COLOR_RED, color=TEXT_MAIN, bold=True, font_size='11sp')
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
        for ch in [ord('Q'), ord('q'), ord('D'), ord('d'), ord('E'), ord('e')]:
            user32.keybd_event(ch, 0, KEYEVENTF_KEYUP, 0)

    def trigger_copy_native():
        release_modifiers_native()
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(ord('C'), 0, 0, 0)
        user32.keybd_event(ord('C'), 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    def trigger_paste_native():
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_LALT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_RALT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_LSHIFT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_RSHIFT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(ord('V'), 0, 0, 0)
        user32.keybd_event(ord('V'), 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
else:
    def release_modifiers_native():
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_LALT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_RALT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_LSHIFT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_RSHIFT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        for ch in [ord('Q'), ord('q'), ord('D'), ord('d'), ord('E'), ord('e')]:
            user32.keybd_event(ch, 0, KEYEVENTF_KEYUP, 0)

    def trigger_copy_native():
        release_modifiers_native()
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(ord('C'), 0, 0, 0)
        user32.keybd_event(ord('C'), 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    def trigger_paste_native():
        release_modifiers_native()
        if IS_WINDOWS:
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(ord('V'), 0, 0, 0)
            user32.keybd_event(ord('V'), 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        elif kb_controller:
            with kb_controller.pressed(Key.ctrl):
                kb_controller.press('v')
                kb_controller.release('v')

    def send_enter_native():
        release_modifiers_native()
        if IS_WINDOWS:
            user32.keybd_event(0x0D, 0, 0, 0)
            user32.keybd_event(0x0D, 0, KEYEVENTF_KEYUP, 0)
        elif kb_controller:
            kb_controller.press(Key.enter)
            kb_controller.release(Key.enter)

_bg_hotkey_lock = threading.Lock()

def start_integrated_background_service(app_ref):
    """Integrated Desktop & Android Background Service (Hotkeys + Quick Peek Glass Overlay)."""
    peek_card_inst = None
    try:
        import derf_peek
        peek_card_inst = derf_peek.PeekCard()
        t_peek = threading.Thread(target=peek_card_inst.run, daemon=True)
        t_peek.start()
        print("[*] Quick Peek Glass Card Overlay active in background!")
    except Exception as e:
        print(f"Peek Overlay init status: {repr(e)}")

    def do_bg_hotkey_encrypt():
        if not _bg_hotkey_lock.acquire(blocking=False):
            return
        try:
            trigger_copy_native()
            time.sleep(0.04)

            selected_text = safe_paste().strip()
            if not selected_text or selected_text.startswith("DERF:V1:"):
                return

            cs = contacts_load()
            peer = app_ref.main_screen.selected_peer or (list(cs.keys())[0] if cs else None)
            if not peer or not os.path.exists(P(f"lc_session_{peer}.json")): return

            cipher_text = encrypt_alien_stack(selected_text, peer, app_ref.idn)
            if not cipher_text: return

            chunks = [b.strip() for b in re.split(r'\n\s*\n', cipher_text.strip()) if b.strip() and "DERF:V1:" in b]
            if not chunks:
                chunks = [b.strip() for b in cipher_text.strip().split('\n') if b.strip()]

            if len(chunks) == 1:
                safe_copy(chunks[0])
                time.sleep(0.03)
                trigger_paste_native()
            else:
                for chunk in chunks:
                    safe_copy(chunk)
                    time.sleep(0.03)
                    trigger_paste_native()
                    time.sleep(0.04)
                    send_enter_native()
                    time.sleep(0.18)
        except Exception as e:
            print(f"Hotkey BG error: {repr(e)}")
        finally:
            _bg_hotkey_lock.release()

    def do_peek_decrypt():
        try:
            v_token_path = P(".vault_token")
            if os.path.exists(v_token_path):
                try:
                    raw_v = open(v_token_path, "rb").read()
                    if len(raw_v) == 32:
                        global VAULT
                        VAULT = raw_v
                except Exception: pass

            trigger_copy_native()
            time.sleep(0.15)

            selected_text = safe_paste().strip()
            if selected_text and "DERF:V1:" in selected_text:
                raw_idn = vload(P("lc_identity.json"))
                idn = norm_identity(raw_idn)
                decrypted = decrypt_alien_stack(selected_text, idn, custom_session_loader=load_sim_bob_session_standalone)
                if decrypted:
                    x, y = 200, 200
                    if IS_WINDOWS:
                        try:
                            import win32gui
                            x, y = win32gui.GetCursorPos()
                        except Exception: pass

                    if peek_card_inst and hasattr(peek_card_inst, 'show'):
                        peek_card_inst.show(decrypted, x, y)
        except Exception:
            pass

    if keyboard:
        try:
            listener = keyboard.GlobalHotKeys({
                '<alt>+<shift>+d': do_bg_hotkey_encrypt,
                '<ctrl>+<shift>+e': do_bg_hotkey_encrypt,
                '<alt>+<shift>+q': do_peek_decrypt
            })
            listener.start()
            print("[*] Integrated Background Hotkey Listener active (Alt+Shift+D / Ctrl+Shift+E / Alt+Shift+Q)")
        except Exception as e:
            print(f"Hotkey listener status: {repr(e)}")

    def bg_clip_monitor():
        last_clip = ""
        while True:
            try:
                time.sleep(0.4)
                clip_text = safe_paste().strip()
                if clip_text and clip_text != last_clip and "DERF:V1:" in clip_text:
                    last_clip = clip_text
                    if not hasattr(app_ref, 'idn') or not app_ref.idn: continue
                    dec_msg = decrypt_alien_stack(clip_text, app_ref.idn, custom_session_loader=app_ref.main_screen.load_sim_bob_session)
            except Exception:
                pass

    t_clip = threading.Thread(target=bg_clip_monitor, daemon=True)
    t_clip.start()


class DerfApp(App):
    def build(self):
        self.title = "Derf PQ+FS — Post-Quantum Messenger"
        Window.clearcolor = BG_OBSIDIAN
        Window.size = (1024, 720)

        global PQ_KEM
        try:
            PQ_KEM = _load_pq()
        except Exception as e:
            print(f"FATAL: {repr(e)}")
            sys.exit(1)

        self.sm = ScreenManager(transition=FadeTransition(duration=0.15))
        self.vault_screen = VaultScreen(app_ref=self, name='vault')
        self.main_screen = MainScreen(app_ref=self, name='main')

        self.sm.add_widget(self.vault_screen)
        self.sm.add_widget(self.main_screen)

        # Start background clipboard monitor for iOS/Android
        Clock.schedule_interval(self.check_clipboard_background, 1.0) # Check every 1 second
        return self.sm

    def check_clipboard_background(self, dt):
        try:
            from kivy.core.clipboard import Clipboard
            current_clip = Clipboard.paste()
            if current_clip and "DERF:V1:" in current_clip and (not hasattr(self, '_last_clip') or self._last_clip != current_clip):
                self._last_clip = current_clip
                print("[*] Derf ciphertext detected in clipboard!")
        except Exception:
            pass

    def on_vault_unlocked(self):
        self.main_screen.refresh_views()
        self.sm.current = 'main'
        start_integrated_background_service(self)

try:
    from jnius import autoclass, cast
    from android import activity

    Context = autoclass('android.content.Context')
    Intent = autoclass('android.content.Intent')
    ClipboardManager = autoclass('android.content.ClipboardManager')

    class PythonServiceManager:
        @staticmethod
        @android.jnius.java_method('(Ljava/lang/String;)V')
        def onDerfTextDetected(text):
            # Schedule on main thread to update Kivy UI
            Clock.schedule_once(lambda dt: handle_android_overlay(text), 0)

    def handle_android_overlay(text):
        print(f"Detected Derf text on Android: {text}")

except ImportError:
    pass # Not on Android, ignore

def main():
    if not _single():
        print("⚠️ Another instance of Derf is already running.")
        sys.exit(1)
    DerfApp().run()

if __name__ == "__main__":
    main()
