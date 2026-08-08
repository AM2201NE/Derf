"""
Derf — deniable, post-quantum, per-letter-chained encrypted messenger.
PQ (ML-KEM-768) is MANDATORY: backend auto-detected = liboqs (native) or kyber-py (pure python).
Stack: uniform fixed-size packets w/ encrypted headers -> Double Ratchet w/ deniable
header MACs + MAC-key revelation -> deniable X3DH-style PQ handshake (X25519+ML-KEM-768)
-> LC-AEAD per-letter chained AEAD -> 7-min freshness.
"""
import os, sys, json, glob, hmac, hashlib, time, struct, base64, getpass, binascii
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat)
from cryptography.exceptions import InvalidTag

# ---------------- MANDATORY post-quantum backend (ML-KEM-768) ----------------
class _LiboqsBackend:
    name = "liboqs (native ML-KEM-768)"
    def __init__(self):
        import liboqs
        self._k = liboqs.KEM("ML-KEM-768")
    def generate_keypair(self): return self._k.generate_keypair()
    def encaps(self, pk): return self._k.encaps(pk)
    def decaps(self, ct, sk): return self._k.decaps(ct, sk)

class _KyberPyBackend:
    name = "kyber-py (pure-python ML-KEM-768)"
    def __init__(self):
        from kyber_py.ml_kem import ML_KEM768
        self._k = ML_KEM768
    def generate_keypair(self): return self._k.generate_keypair()
    def encaps(self, pk): return self._k.encaps(pk)
    def decaps(self, ct, sk): return self._k.decaps(ct, sk)

def _load_pq():
    for cls in (_LiboqsBackend, _KyberPyBackend):
        try: return cls()
        except Exception: continue
    print("FATAL: no post-quantum backend found. Derf requires ML-KEM-768.")
    print("Install one of:\n  pip install liboqs-python\n  pip install kyber-py")
    raise SystemExit(1)
PQ_KEM = _load_pq()

APP_AAD = b"derf-v1"; MAXSKIPPED = 1024; MAXN = 1 << 20
FRESH = 420.0; SKEW = 60.0; CHUNK = 128; HJ = 256
DROP = "lc_drop"; VAULT = b""
if "--fresh-sec" in sys.argv: FRESH = float(sys.argv[sys.argv.index("--fresh-sec")+1])

def hmac_sha256(k, d): return hmac.new(k, d, hashlib.sha256).digest()
def hkdf(ikm, salt, info, n=32):
    return HKDF(algorithm=hashes.SHA256(), length=n, salt=salt, info=info).derive(ikm)
def b64(b): return base64.b64encode(b).decode()
def ub64(s): return base64.b64decode(s)
def keygen(m): return tuple(hmac_sha256(hmac_sha256(m, l), b"okm") for l in
                            (b"lc-aead-nonce-v1", b"lc-aead-aead-v1", b"lc-aead-manifest-v1"))
def kdf_ck(ck): return hmac_sha256(ck, b"\x01"), hmac_sha256(ck, b"\x00")
def kdf3(rk, o):
    x = hkdf(o, rk, b"lc-ratchet3", 96); return x[:32], x[32:64], x[64:]
def x_new():
    p = x25519.X25519PrivateKey.generate()
    return (p.private_bytes(Encoding, PrivateFormat.Raw, NoEncryption()),
            p.public_key().public_bytes(Encoding, PublicFormat.Raw))
def x_pub_of(b):
    return x25519.X25519PrivateKey.from_private_bytes(b).public_key().public_bytes(Encoding, PublicFormat.Raw)
def dh(pr, pu): return x25519.X25519PrivateKey.from_private_bytes(pr).exchange(x25519.X25519PublicKey.from_public_bytes(pu))
def tlv(*it): return b"".join(struct.pack(">H", len(i)) + i for i in it)
def untlv(b, k):
    out, off = [], 0
    for _ in range(k):
        (l,), off = struct.unpack(">H", b[off:off+2]), off+2
        out.append(b[off:off+l]); off += l
    return out, off
def now8(): return struct.pack(">Q", int(time.time()*1e9))
def check_fresh(ts8):
    t = struct.unpack(">Q", ts8)[0]/1e9; n = time.time()
    if t > n+SKEW or n-t > FRESH: raise ValueError("stale")
def pad(pt):
    inner = struct.pack(">I", len(pt)) + pt
    return inner + os.urandom((-len(inner)) % 64)
def unpad(p):
    (l,) = struct.unpack(">I", p[:4])
    if 4+l > len(p): raise ValueError("pad")
    return p[4:4+l]
def clean_b64(raw):
    return "".join(l.strip() for l in raw.splitlines() if l.strip() and not l.strip().startswith("-----")).replace("-", "+").replace("_", "/")

# ---------------- LC-AEAD core (per-letter chained AEAD) ----------------
def lca_encrypt(master, message, aad):
    kn, ka, km = keygen(master); aead = ChaCha20Poly1305(ka); now = time.time()
    ts = [struct.pack(">Q", int((now+i*1e-6)*1e9)) for i in range(len(message))]
    prev, blobs = b"", []
    for i, (m, tc) in enumerate(zip(message, ts)):
        n_i = hmac_sha256(kn, tc+struct.pack(">Q", i)+prev+aad)[:12]
        blob = n_i + aead.encrypt(n_i, bytes([m]), aad); blobs.append(blob); prev = blob
    man = struct.pack(">H", len(aad))+aad+struct.pack(">Q", len(message))+b"".join(ts)
    out = bytearray(b"LCA1")+man+hmac_sha256(km, man+hashlib.sha256(b"".join(blobs)).digest())
    for b in blobs: out += struct.pack(">H", len(b))+b
    return bytes(out)
def lca_decrypt(master, pkg, expect_aad):
    if pkg[:4] != b"LCA1": raise ValueError("hdr")
    off = 4
    (al,), off = struct.unpack(">H", pkg[off:off+2]), off+2
    aad, off = pkg[off:off+al], off+al
    if not hmac.compare_digest(aad, expect_aad): raise ValueError("ctx")
    (n,), off = struct.unpack(">Q", pkg[off:off+8]), off+8
    ts = []
    for _ in range(n): ts.append(pkg[off:off+8]); off += 8
    mtag, off = pkg[off:off+32], off+32
    blobs = []
    for _ in range(n):
        (bl,) = struct.unpack(">H", pkg[off:off+2]); off += 2
        blobs.append(pkg[off:off+bl]); off += bl
    if off != len(pkg): raise ValueError("ext")
    kn, ka, km = keygen(master)
    man = struct.pack(">H", len(aad))+aad+struct.pack(">Q", n)+b"".join(ts)
    if not hmac.compare_digest(mtag, hmac_sha256(km, man+hashlib.sha256(b"".join(blobs)).digest())): raise ValueError("man")
    aead = ChaCha20Poly1305(ka); prev, out = b"", bytearray()
    for i, (blob, tc) in enumerate(zip(blobs, ts)):
        n_i = hmac_sha256(kn, tc+struct.pack(">Q", i)+prev+aad)[:12]
        if blob[:12] != n_i: raise ValueError("chain")
        out += aead.decrypt(n_i, blob[12:], aad); prev = blob
    return bytes(out), ts

def aad_len(): return len(APP_AAD)+32+HJ+64
def lca_size(n): return 4+2+aad_len()+8+8*n+32+n*31
PAYLOAD_MAX = lca_size(CHUNK); PACKET = 12+HJ+16+PAYLOAD_MAX

# ---------------- identities / contacts / vault ----------------
def make_identity():
    x, _ = x_new()
    pq_pk, pq_sk = PQ_KEM.generate_keypair()
    return {"x": x, "pq_sk": pq_sk, "pq_pk": pq_pk}
def id_bundle(i): return tlv(x_pub_of(i["x"]), i["pq_pk"])
def id_fp(b): return hashlib.sha256(b).digest()
def pair_h(a, b): return hashlib.sha256(b"".join(sorted((a, b)))).digest()
def safety_code(a, b):
    h = hashlib.sha256(b"SAS"+b"".join(sorted((a, b)))).digest()[:6]
    return "-".join(str(int.from_bytes(h[i:i+2], "big") % 10000).zfill(4) for i in (0, 2, 4))
def contacts_load():
    d = {}
    if os.path.exists("lc_contacts.txt"):
        for line in open("lc_contacts.txt", encoding="utf-8"):
            n, _, b = line.strip().partition("\t")
            if n and b: d[n] = base64.urlsafe_b64decode(b+"="*(-len(b) % 4))
    return d
def contact_add(n, b):
    with open("lc_contacts.txt", "a", encoding="utf-8") as f:
        f.write(f"{n}\t{base64.urlsafe_b64encode(b).decode().rstrip('=')}\n")
def vsave(p, o):
    n = os.urandom(12); a = ChaCha20Poly1305(hmac_sha256(VAULT, b"vault"))
    open(p, "w").write(b64(n+a.encrypt(n, json.dumps(o).encode(), None)))
def vload(p):
    r = ub64(open(p).read().strip()); a = ChaCha20Poly1305(hmac_sha256(VAULT, b"vault"))
    return json.loads(a.decrypt(r[:12], r[12:], None))
def wipe_all():
    for f in glob.glob("lc_*"):
        try:
            with open(f, "r+b") as fh: fh.write(os.urandom(max(os.path.getsize(f), 1)))
            os.remove(f)
        except OSError: pass

# ---------------- ratchet session ----------------
class Session:
    def __init__(self, sid, rk, dp, du, dhrr=None, cks=None, ckr=None, hks=None, hkr=None,
                 ns=0, nr=0, pn=0, skipped=None, role="?", reveal=None, stepped=False, prev_rk=None):
        self.sid, self.rk, self.dp, self.du, self.dhrr = sid, rk, dp, du, dhrr
        self.cks, self.ckr, self.hks, self.hkr = cks, ckr, hks, hkr
        self.ns, self.nr, self.pn, self.stepped, self.prev_rk = ns, nr, pn, stepped, prev_rk
        self.skipped = skipped or {}; self.reveal = reveal or []
    def _skip(self, pn):
        if not self.ckr: return
        if not (self.nr <= pn <= self.nr+MAXSKIPPED): raise ValueError("pn")
        for i in range(self.nr, pn):
            if len(self.skipped) >= MAXSKIPPED: raise ValueError("ovf")
            mk, self.ckr = kdf_ck(self.ckr); self.skipped[(b64(self.dhrr), i)] = mk
    def _step(self, hdr):
        self._skip(hdr["pn"])
        if self.hks: self.reveal.append(b64(self.hks))
        if self.hkr: self.reveal.append(b64(self.hkr))
        self.dhrr = ub64(hdr["dh"])
        mid_rk, self.ckr, self.hkr = kdf3(self.rk, dh(self.dp, self.dhrr))
        self.prev_rk = mid_rk
        self.dp, self.du = x_new()
        self.rk, self.cks, self.hks = kdf3(self.rk, dh(self.dp, self.dhrr))
        self.pn, self.ns, self.nr, self.stepped = self.ns, 0, 0, True
    def encrypt(self, pt, me_fp, peer_fp):
        if not self.cks: raise ValueError("not ready")
        padded = pad(pt); tot = len(padded); mid = os.urandom(8).hex()
        mode = "step" if self.stepped else "cur"; self.stepped = False
        packets = []
        for ci in range(0, tot, CHUNK):
            ch = padded[ci:ci+CHUNK]
            mk, self.cks = kdf_ck(self.cks); n = self.ns; self.ns += 1
            rev = self.reveal[:2]; self.reveal = self.reveal[2:]
            hdr = {"dh": b64(self.du), "pn": self.pn, "n": n, "tot": tot, "ci": ci//CHUNK,
                   "mid": mid, "pl": 0, "rev": rev}
            hj = json.dumps(hdr, sort_keys=True).encode()
            hdr["pl"] = lca_size(len(ch))
            hj = json.dumps(hdr, sort_keys=True).encode()
            assert len(hj) <= HJ; hj += b" "*(HJ-len(hj))
            aad = APP_AAD+self.sid+hj+b"".join(sorted((me_fp, peer_fp)))
            lca1 = lca_encrypt(mk, ch, aad)
            payload = lca1 + os.urandom(PAYLOAD_MAX-len(lca1))
            nonce = os.urandom(12)
            ek = hmac_sha256(self.prev_rk, b"hstep") if mode == "step" else hmac_sha256(self.hks, b"hcur")
            mode = "cur"
            packets.append(nonce + ChaCha20Poly1305(ek).encrypt(nonce, hj, b"") + payload)
        return packets
    def try_decrypt(self, packet, me_fp, peer_fp):
        nonce, ct, payload = packet[:12], packet[12:12+HJ+16], packet[12+HJ+16:]
        cands = []
        if self.hkr: cands.append(("cur", hmac_sha256(self.hkr, b"hcur")))
        cands.append(("step", hmac_sha256(self.rk, b"hstep")))
        hj = mode = None
        for m, ek in cands:
            try:
                hj = ChaCha20Poly1305(ek).decrypt(nonce, ct, b""); mode = m; break
            except InvalidTag: continue
        if hj is None: raise ValueError("not-for-session")
        hdr = json.loads(hj.rstrip())
        if hdr["n"] > MAXN or hdr["pn"] > MAXN: raise ValueError("bounds")
        if mode == "step":
            if hdr["dh"] == (b64(self.dhrr) if self.dhrr else None): raise ValueError("step")
            self._step(hdr)
        elif hdr["dh"] != (b64(self.dhrr) if self.dhrr else None): raise ValueError("chain-id")
        key = (hdr["dh"], hdr["n"])
        if key in self.skipped: mk = self.skipped.pop(key)
        elif hdr["n"] < self.nr: raise ValueError("replay")
        else:
            while self.nr < hdr["n"]:
                if len(self.skipped) >= MAXSKIPPED: raise ValueError("ovf")
                mk_s, self.ckr = kdf_ck(self.ckr); self.skipped[(hdr["dh"], self.nr)] = mk_s; self.nr += 1
            mk, self.ckr = kdf_ck(self.ckr); self.nr = hdr["n"]+1
        aad = APP_AAD+self.sid+hj+b"".join(sorted((me_fp, peer_fp)))
        ch, ts = lca_decrypt(mk, payload[:hdr["pl"]], aad)
        check_fresh(ts[0])
        return hdr["tot"], hdr["ci"], hdr["mid"], ch
    def save(self, peer):
        vsave(f"lc_session_{peer}.json", {"sid": b64(self.sid), "rk": b64(self.rk), "dp": b64(self.dp),
            "du": b64(self.du), "rr": b64(self.dhrr) if self.dhrr else None,
            "cs": b64(self.cks) if self.cks else None, "cr": b64(self.ckr) if self.ckr else None,
            "hs": b64(self.hks) if self.hks else None, "hr": b64(self.hkr) if self.hkr else None,
            "ns": self.ns, "nr": self.nr, "pn": self.pn, "rev": self.reveal, "st": self.stepped,
            "pr": b64(self.prev_rk) if self.prev_rk else None, "role": self.role,
            "sk": {f"{d}|{n}": b64(m) for (d, n), m in self.skipped.items()}})
    @staticmethod
    def load(p):
        d = vload(f"lc_session_{p}.json")
        return Session(ub64(d["sid"]), ub64(d["rk"]), ub64(d["dp"]), ub64(d["du"]),
            ub64(d["rr"]) if d["rr"] else None, ub64(d["cs"]) if d["cs"] else None,
            ub64(d["cr"]) if d["cr"] else None, ub64(d["hs"]) if d["hs"] else None,
            ub64(d["hr"]) if d["hr"] else None, d["ns"], d["nr"], d["pn"],
            {(k.split("|")[0], int(k.split("|")[1])): ub64(v) for k, v in d["sk"].items()},
            d["role"], d["rev"], d["st"], ub64(d["pr"]) if d["pr"] else None)

# ---------------- deniable PQ handshake ----------------
def hs_req(idn, peer_bundle):
    me = id_bundle(idn); a_e, a_e_pub = x_new()
    ct_a, ss_a = PQ_KEM.encaps(untlv(peer_bundle, 2)[0][1])
    payload = tlv(b"LCREQ", me, a_e_pub, ct_a, now8(), os.urandom(16))
    k1 = hkdf(dh(a_e, untlv(peer_bundle, 2)[0][0])+dh(idn["x"], untlv(peer_bundle, 2)[0][0])+ss_a+pair_h(me, peer_bundle), b"m", b"k1")
    blob = payload+hmac_sha256(k1, payload)
    return blob, {"a_e": b64(a_e), "ss_a": b64(ss_a), "reqblob": b64(blob)}
def hs_rsp(idn, req_blob):
    payload, mac = req_blob[:-32], req_blob[-32:]
    _, bundleA, a_e_pub, ct_a, ts, _ = untlv(payload, 6); check_fresh(ts)
    xa_pub, a_pq = untlv(bundleA, 2)
    ss_a = PQ_KEM.decaps(ct_a, idn["pq_sk"])
    me = id_bundle(idn)
    k1 = hkdf(dh(idn["x"], a_e_pub)+dh(idn["x"], xa_pub)+ss_a+pair_h(bundleA, me), b"m", b"k1")
    if not hmac.compare_digest(mac, hmac_sha256(k1, payload)): raise ValueError("auth")
    b_e, b_e_pub = x_new(); rb, rb_pub = x_new()
    ct_b, ss_b = PQ_KEM.encaps(a_pq)
    rsp = tlv(b"LCRSP", hashlib.sha256(req_blob).digest(), b_e_pub, rb_pub, ct_b, now8(), os.urandom(16))
    k2 = hkdf(dh(b_e, xa_pub)+dh(idn["x"], xa_pub)+ss_b+pair_h(bundleA, me), b"m", b"k2")
    sid = hashlib.sha256(req_blob+rsp).digest()
    root = hkdf(dh(b_e, a_e_pub)+dh(idn["x"], a_e_pub)+dh(b_e, xa_pub)+dh(idn["x"], xa_pub)+ss_a+ss_b, sid, b"root")
    return rsp+hmac_sha256(k2, rsp), Session(sid, root, rb, rb_pub, role="resp", prev_rk=root)
def hs_complete(idn, pend, rsp_blob):
    payload, mac = rsp_blob[:-32], rsp_blob[-32:]
    _, reqh, b_e_pub, rb_pub, ct_b, ts, _ = untlv(payload, 7); check_fresh(ts)
    reqblob = ub64(pend["reqblob"])
    if reqh != hashlib.sha256(reqblob).digest(): raise ValueError("hs")
    me = id_bundle(idn)
    fr, _ = untlv(reqblob[:-32], 6); bundleA, a_e_pub = fr[1], fr[2]
    xa_pub, _ = untlv(bundleA, 2)
    ss_b = PQ_KEM.decaps(ct_b, idn["pq_sk"])
    k2 = hkdf(dh(ub64(pend["a_e"]), b_e_pub)+dh(idn["x"], xa_pub)+ss_b+pair_h(me, bundleA), b"m", b"k2")
    if not hmac.compare_digest(mac, hmac_sha256(k2, payload)): raise ValueError("auth")
    sid = hashlib.sha256(reqblob+payload).digest()
    root = hkdf(dh(ub64(pend["a_e"]), b_e_pub)+dh(ub64(pend["a_e"]), xa_pub)+dh(idn["x"], b_e_pub)+
                dh(idn["x"], xa_pub)+ub64(pend["ss_a"])+ss_b, sid, b"root")
    ra, _ = x_new()
    rk, cks, hks = kdf3(root, dh(ra, rb_pub))
    return Session(sid, rk, ra, x_pub_of(ra), dhrr=rb_pub, cks=cks, hks=hks,
                   role="init", stepped=True, prev_rk=root)

def feed(sess, packet, me_fp, peer_fp, buff):
    tot, ci, mid, ch = sess.try_decrypt(packet, me_fp, peer_fp)
    b = buff.setdefault(mid, {"tot": tot, "parts": {}})
    b["parts"][ci] = ch
    need = (tot+CHUNK-1)//CHUNK
    if len(b["parts"]) == need:
        padded = b"".join(b["parts"][i] for i in range(need))[:tot]
        del buff[mid]
        return unpad(padded)
    return None

def selftest():
    global VAULT; VAULT = hashlib.sha256(b"t").digest()
    A, B = make_identity(), make_identity()
    ba, bb = id_bundle(A), id_bundle(B); fa, fb = id_fp(ba), id_fp(bb)
    req, pend = hs_req(A, bb)
    rsp, sB = hs_rsp(B, req)
    sA = hs_complete(A, pend, rsp)
    buf, out = {}, None
    for p in sA.encrypt(b"hello untraceable world "*5, fa, fb):
        assert len(p) == PACKET and bb not in p and ba not in p
        out = feed(sB, p, fb, fa, buf)
    assert out and out.startswith(b"hello")
    pk = sA.encrypt(b"two", fa, fb); assert feed(sB, pk[0], fb, fa, buf) == b"two"
    r = sB.encrypt(b"reply", fb, fa); assert feed(sA, r[0], fa, fb, {}) == b"reply"
    for bad in (lambda: feed(sB, pk[0], fb, fa, {}),
                lambda: feed(sB, pk[0][:-1]+bytes([pk[0][-1]^1]), fb, fa, {}),
                lambda: feed(sB, os.urandom(PACKET), fb, fa, {})):
        try: bad(); raise SystemExit("FAIL")
        except (ValueError, InvalidTag): pass
    print(f"selftest OK | PQ: {PQ_KEM.name} | packet={PACKET}B uniform | deniable | fresh={int(FRESH)}s")

# ---------------- UI ----------------
def read_multiline(p):
    print(p); lines = []
    while True:
        l = input()
        if l == "": break
        lines.append(l)
    return "\n".join(lines)

def main():
    global VAULT
    if "--selftest" in sys.argv: selftest(); return
    print(f"Derf | PQ backend: {PQ_KEM.name}")
    VAULT = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"derf-vault", iterations=600_000)\
        .derive(getpass.getpass("Vault passphrase: ").encode())
    idn = None
    while True:
        print(f"\n===== Derf ===== [id:{'yes' if idn else 'no'}] [fresh:{int(FRESH)}s]")
        print(" [1] create id  [2] load id  [3] contacts/safety  [4] START session  [5] ANSWER req")
        print(" [6] FINISH session  [7] SEND  [8] RECEIVE  [9] WIPE all  [0] exit")
        c = input("> ").strip()
        try:
            if c == "0": break
            elif c == "9": wipe_all(); idn = None; print("wiped.")
            elif c == "1":
                idn = make_identity(); vsave("lc_identity.json",
                    {"x": b64(idn["x"]), "pq_sk": b64(idn["pq_sk"]), "pq_pk": b64(idn["pq_pk"])})
                print("Your public key (share anywhere):\n LCAP1-"+base64.urlsafe_b64encode(id_bundle(idn)).decode().rstrip("="))
            elif c == "2":
                d = vload("lc_identity.json")
                idn = {"x": ub64(d["x"]), "pq_sk": ub64(d["pq_sk"]), "pq_pk": ub64(d["pq_pk"])}
                print("loaded.")
            elif c == "3":
                cs = contacts_load()
                for n, b in cs.items():
                    print(f"  {n}  fp={id_fp(b).hex()[:12]}" + (f"  safety={safety_code(id_bundle(idn), b)}" if idn else ""))
                if input("add contact? y/N: ").strip() == "y":
                    nm = input("name: ").strip()
                    s = clean_b64(read_multiline("paste LCAP1- key, EMPTY line ends:")).removeprefix("LCAP1-")
                    contact_add(nm, base64.b64decode(s+"="*(-len(s) % 4)))
            elif c in "45678" and not idn: print("load identity first."); continue
            elif c == "4":
                cs = contacts_load(); nm = input(f"peer {list(cs)}: ").strip()
                req, pend = hs_req(idn, cs[nm]); vsave(f"lc_pending_{nm}.json", pend)
                print("\nREQ (send to peer):\n"+b64(req))
            elif c == "5":
                rsp, sess = hs_rsp(idn, ub64(clean_b64(read_multiline("paste REQ, EMPTY line ends:"))))
                nm = input("peer name: ").strip(); sess.save(nm)
                print("\nRSP (send back):\n"+b64(rsp))
            elif c == "6":
                nm = input("peer: ").strip()
                hs_complete(idn, vload(f"lc_pending_{nm}.json"), ub64(clean_b64(read_multiline("paste RSP, EMPTY line ends:")))).save(nm)
                os.remove(f"lc_pending_{nm}.json"); print("session live.")
            elif c == "7":
                nm = input("peer: ").strip(); sess = Session.load(nm)
                pkts = sess.encrypt(read_multiline("message, EMPTY line ends:").encode(),
                                    id_fp(id_bundle(idn)), id_fp(contacts_load()[nm]))
                sess.save(nm)
                m = input("output (p)rint/(f)ile/(d)rop: ").strip()
                os.makedirs(DROP, exist_ok=True)
                for i, p in enumerate(pkts):
                    if m == "f": open(f"{nm}_out_{i}.bin", "wb").write(p)
                    elif m == "d": open(f"{DROP}/{os.urandom(8).hex()}.bin", "wb").write(p)
                    else: print(b64(p))
                print(f"({len(pkts)} uniform {PACKET}-B packets)")
            elif c == "8":
                me = id_fp(id_bundle(idn))
                sessions = {n: Session.load(n) for n in
                            [os.path.basename(f)[11:-5] for f in glob.glob("lc_session_*.json")]}
                m = input("input (p)aste/(f)ile/(d)rop: ").strip()
                pkts = []
                if m == "p":
                    pkts = [ub64(clean_b64(l)) for l in read_multiline("paste packets (one per line), EMPTY line ends:").splitlines() if l.strip()]
                elif m == "f":
                    raw = open(input("path: ").strip(), "rb").read()
                    pkts = [raw[i:i+PACKET] for i in range(0, len(raw), PACKET)]
                else:
                    for f in glob.glob(f"{DROP}/*.bin"):
                        pkts.append(open(f, "rb").read()); os.remove(f)
                buff, done, unmatched = {}, 0, 0
                for p in pkts:
                    hit = False
                    for n, s in sessions.items():
                        try:
                            out = feed(s, p, me, id_fp(contacts_load()[n]), buff)
                            hit = True; done += 1
                            if out: print(f"\n✅ [{n}] {out.decode()}")
                            break
                        except (ValueError, InvalidTag): continue
                    if not hit: unmatched += 1
                for n, s in sessions.items(): s.save(n)
                print(f"({done} processed, {unmatched} not-for-any-session)")
        except (ValueError, InvalidTag, binascii.Error, KeyError, OSError):
            print("❌ rejected")
        except KeyboardInterrupt: print("\n(interrupted)")
    print("Bye.")
if __name__ == "__main__":
    main()
