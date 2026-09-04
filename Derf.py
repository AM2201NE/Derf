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

def _data_dir(profile_name="default"):
    old = _old_dir()
    try:
        home = os.path.expanduser("~")
        desk = os.path.join(home, "Desktop")
        if not os.path.isdir(desk): desk = os.path.join(home, "desktop")
        folder_name = APP_NAME if profile_name == "default" else f"{APP_NAME}_Profile_{profile_name}"
        d = os.path.join(desk, folder_name)
        os.makedirs(d, exist_ok=True)
        t = os.path.join(d, ".wtest"); open(t, "w").write("x"); os.remove(t)
        if profile_name == "default":
            _migrate(old, d)
        return d
    except Exception:
        os.makedirs(old, exist_ok=True); return old

DATA_DIR = _data_dir()
def P(n): return os.path.join(DATA_DIR, n)

def set_profile(profile_name):
    global DATA_DIR, DROP_DIR
    DATA_DIR = _data_dir(profile_name)
    DROP_DIR = P("lc_drop")
    os.makedirs(DROP_DIR, exist_ok=True)


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

_LOCK_FILE = None
def _single(profile_name="default"):
    global _LOCK_FILE
    if IS_SELFTEST: return True
    set_profile(profile_name)
    lock_path = P(".instance.lock")
    try:
        if sys.platform == "win32":
            import msvcrt
            _LOCK_FILE = open(lock_path, "a+b")
            try:
                msvcrt.locking(_LOCK_FILE.fileno(), msvcrt.LK_NCKBL, 1)
                return True
            except IOError:
                return False
        else:
            import fcntl
            _LOCK_FILE = open(lock_path, "a+b")
            try:
                fcntl.flock(_LOCK_FILE, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except IOError:
                return False
    except Exception:
        return True

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

try:
    PQ_KEM = _load_pq()
except Exception:
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
    if not r: return ""
    import html, re
    r = html.unescape(str(r))
    r = re.sub(r'<[^>]+>', '', r)
    for c in ['-', '_', ' ', '\n', '\r', '\t']:
        r = r.replace(c, '+' if c == '-' else ('/' if c == '_' else ''))
    m = re.search(r'([A-Za-z0-9+/=]{40,})', r)
    if m:
        r = m.group(1)
    missing = len(r) % 4
    if missing:
        r += '=' * (4 - missing)
    return r
def valid_pub(b): return isinstance(b, (bytes, bytearray)) and len(b) == EK

def parse_pubkey(t):
    if not t: raise ValueError("Key is empty")
    t = str(t).strip()
    for p in ("LCAP1+", "LCAP1-", "LCAP1"):
        if t.startswith(p):
            t = t[len(p):]
            break
    raw = clean_b64(t)
    b = ub64(raw)
    if not valid_pub(b):
        raise ValueError(f"Not a valid PUBLIC key (got {len(b)} bytes, expected {EK}). Copy the LCAP1- public key.")
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
_CLIPBOARD_TEXT = ""

def safe_copy(text):
    global _CLIPBOARD_TEXT
    _CLIPBOARD_TEXT = text
    try: pyperclip.copy(text)
    except Exception: pass

def safe_paste():
    global _CLIPBOARD_TEXT
    try:
        val = pyperclip.paste()
        if val: return val
    except Exception: pass
    return _CLIPBOARD_TEXT

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

            safe_copy(cipher_text)
            time.sleep(0.03)
            trigger_paste_native()
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


def main():
    profile_name = "default"
    for arg in sys.argv[1:]:
        if arg.startswith("--profile="):
            profile_name = arg.split("=", 1)[1]

    if not _single(profile_name):
        print(f"⚠️ Another instance of Derf (Profile: {profile_name}) is already running.")
        sys.exit(1)

    global PQ_KEM
    try:
        PQ_KEM = _load_pq()
    except Exception as e:
        print(f"FATAL: Post-Quantum backend failed to initialize: {e}")
        sys.exit(1)

    import derf_qt_ui
    derf_qt_ui.launch_pyqt_app(profile_name)

if __name__ == "__main__":
    main()
