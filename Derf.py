"""
Derf PQ+FS — fully post-quantum AND forward-secret two-box messenger.
Handshake = ML-KEM-768 static (binding) + ML-KEM-768 ephemeral (forward secrecy).
Ratchet = symmetric HMAC-chain (PQ). Per-letter = LC-AEAD. NO RSA/ECC/X25519.
NO SERVER. Vault passkey (wrong=closes), change-passkey, single-instance, wipe.
"""
import os, sys, json, glob, hmac, hashlib, time, struct, base64, binascii, socket
import tkinter as tk
from tkinter import ttk, messagebox
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidTag

_LOCK=None
def _single():
    global _LOCK
    _LOCK=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:_LOCK.bind(("127.0.0.1",59731));return True
    except OSError:return False

# ================= PQ backend (ML-KEM-768) =================
EK,DK,CT,SS=1184,2400,1088,32
class _KyberPyBackend:
    name="kyber-py (ML-KEM-768)"
    def __init__(self):
        self._k=None
        for mn,cn in [("kyber_py.ml_kem","ML_KEM_768"),("kyber_py.ml_kem","ML_KEM768"),("kyber_py.kyber","Kyber768")]:
            try:
                c=getattr(__import__(mn,fromlist=[cn]),cn);a,b=c.keygen()
                if sorted((len(a),len(b)))!=sorted((EK,DK)):continue
                x,y=c.encaps(a if len(a)==EK else b)
                if sorted((len(x),len(y)))!=sorted((CT,SS)):continue
                self._k=c;break
            except Exception:continue
        if self._k is None:raise ImportError("no ML-KEM-768")
    def generate_keypair(self):
        a,b=self._k.keygen();return (a,b) if len(a)==EK else (b,a)
    def encaps(self,pk):
        x,y=self._k.encaps(pk);return (x,y) if len(x)==CT else (y,x)
    def decaps(self,ct,sk):
        try:return self._k.decaps(ct,sk)
        except Exception:return self._k.decaps(sk,ct)
class _OqsBackend:
    name="liboqs (ML-KEM-768)"
    def __init__(self):
        import oqs;m=next((x for x in ("ML-KEM-768","Kyber768") if x in oqs.get_enabled_KEM_mechanisms()),None)
        if not m:raise ImportError("no ML-KEM-768");self._m=m
    def generate_keypair(self):
        import oqs
        with oqs.KeyEncapsulation(self._m) as k:return k.generate_keypair()
    def encaps(self,pk):
        import oqs
        with oqs.KeyEncapsulation(self._m) as k:c,s=k.encaps(pk);return c,s
    def decaps(self,ct,sk):
        import oqs
        with oqs.KeyEncapsulation(self._m,sk) as k:return k.decaps(ct)
def _load_pq():
    for cls in (_OqsBackend,_KyberPyBackend):
        try:
            b=cls();pk,sk=b.generate_keypair();c,s1=b.encaps(pk);s2=b.decaps(c,sk)
            if s1==s2 and len(s1)==SS:return b
        except Exception:continue
    print("FATAL: pip install kyber-py");raise SystemExit(1)
PQ_KEM=_load_pq()

# ================= symmetric primitives =================
APP_AAD=b"derf-pqfs-v1";MAXSKIPPED=1024;MAXN=1<<20
FRESH=420.0;SKEW=60.0;CHUNK=128;HJ=256;VAULT=b""
def derive_vault(pw):
    return PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=b"derf-vault",iterations=600_000).derive(pw.encode())
def hmac_sha256(k,d):return hmac.new(k,d,hashlib.sha256).digest()
def hkdf(i,s,info,n=32):return HKDF(algorithm=hashes.SHA256(),length=n,salt=s,info=info).derive(i)
def b64(b):return base64.b64encode(b).decode()
def ub64(s):return base64.b64decode(s)
def keygen(m):return tuple(hmac_sha256(hmac_sha256(m,l),b"okm") for l in (b"a",b"b",b"c"))
def kdf_ck(ck):return hmac_sha256(ck,b"\x01"),hmac_sha256(ck,b"\x00")
def tlv(*it):return b"".join(struct.pack(">H",len(i))+i for i in it)
def untlv(b,k):
    o,off=[],0
    for _ in range(k):
        (l,),off=struct.unpack(">H",b[off:off+2]),off+2;o.append(b[off:off+l]);off+=l
    return o,off
def now8():return struct.pack(">Q",int(time.time()*1e9))
def check_fresh(t8):
    t=struct.unpack(">Q",t8)[0]/1e9;n=time.time()
    if t>n+SKEW or n-t>FRESH:raise ValueError("stale")
def pad(p):
    i=struct.pack(">I",len(p))+p;return i+os.urandom((-len(i))%64)
def unpad(p):
    (l,)=struct.unpack(">I",p[:4])
    if 4+l>len(p):raise ValueError("pad")
    return p[4:4+l]
def clean_b64(r):
    return "".join(l.strip() for l in r.splitlines() if l.strip() and not l.strip().startswith("-----")).replace("-","+").replace("_","/")
def parse_pubkey(t):
    s=clean_b64(t)
    for p in ("LCAP1+","LCAP1-"):
        if s.startswith(p):s=s[len(p):];break
    s+="="*(-len(s)%4);return base64.b64decode(s,validate=True)

def secure_shred(fp,passes=7):
    if not os.path.isfile(fp):return
    try:
        sz=os.path.getsize(fp)
        if sz==0:os.remove(fp);return
        with open(fp,"r+b") as f:
            for _ in range(passes):
                f.seek(0);f.write(os.urandom(sz));f.flush();os.fsync(f.fileno())
        os.remove(fp)
    except Exception:
        try:os.remove(fp)
        except Exception:pass
def nuke_all_files():
    for pat in ["lc_*.json","lc_*.txt","lc_*.bin"]:
        for f in glob.glob(pat):secure_shred(f)

def lca_encrypt(m,msg,aad):
    kn,ka,km=keygen(m);a=ChaCha20Poly1305(ka);now=time.time()
    ts=[struct.pack(">Q",int((now+i*1e-6)*1e9)) for i in range(len(msg))]
    pv,bl=b"",[]
    for i,(x,t) in enumerate(zip(msg,ts)):
        n=hmac_sha256(kn,t+struct.pack(">Q",i)+pv+aad)[:12]
        b=n+a.encrypt(n,bytes([x]),aad);bl.append(b);pv=b
    man=struct.pack(">H",len(aad))+aad+struct.pack(">Q",len(msg))+b"".join(ts)
    out=bytearray(b"LCA1")+man+hmac_sha256(km,man+hashlib.sha256(b"".join(bl)).digest())
    for b in bl:out+=struct.pack(">H",len(b))+b
    return bytes(out)
def lca_decrypt(m,pkg,ea):
    if pkg[:4]!=b"LCA1":raise ValueError("hdr")
    off=4;(al,),off=struct.unpack(">H",pkg[off:off+2]),off+2
    aad,off=pkg[off:off+al],off+al
    if not hmac.compare_digest(aad,ea):raise ValueError("ctx")
    (n,),off=struct.unpack(">Q",pkg[off:off+8]),off+8
    ts=[]
    for _ in range(n):ts.append(pkg[off:off+8]);off+=8
    mt,off=pkg[off:off+32],off+32
    bl=[]
    for _ in range(n):
        (l,),off=struct.unpack(">H",pkg[off:off+2]),off+2;bl.append(pkg[off:off+l]);off+=l
    if off!=len(pkg):raise ValueError("ext")
    kn,ka,km=keygen(m)
    man=struct.pack(">H",len(aad))+aad+struct.pack(">Q",n)+b"".join(ts)
    if not hmac.compare_digest(mt,hmac_sha256(km,man+hashlib.sha256(b"".join(bl)).digest())):raise ValueError("man")
    a=ChaCha20Poly1305(ka);pv,out=b"",bytearray()
    for i,(b,t) in enumerate(zip(bl,ts)):
        n=hmac_sha256(kn,t+struct.pack(">Q",i)+pv+aad)[:12]
        if b[:12]!=n:raise ValueError("chain")
        out+=a.decrypt(n,b[12:],aad);pv=b
    return bytes(out),ts
def aad_len():return len(APP_AAD)+32+HJ+64
def lca_size(n):return 4+2+aad_len()+8+8*n+32+n*31
PAYLOAD_MAX=lca_size(CHUNK);PACKET=12+HJ+16+PAYLOAD_MAX

def make_identity():
    pq_pk,pq_sk=PQ_KEM.generate_keypair();return {"pq_sk":pq_sk,"pq_pk":pq_pk}
def id_bundle(i):return i["pq_pk"]
def id_fp(b):return hashlib.sha256(b).digest()
def pair_h(a,b):return hashlib.sha256(b"".join(sorted((a,b)))).digest()
def safety_code(a,b):
    h=hashlib.sha256(b"SAS"+b"".join(sorted((a,b)))).digest()[:6]
    return "-".join(str(int.from_bytes(h[i:i+2],"big")%10000).zfill(4) for i in (0,2,4))
def contacts_load():
    d={}
    if os.path.exists("lc_contacts.txt"):
        for ln in open("lc_contacts.txt",encoding="utf-8"):
            n,_,b=ln.strip().partition("\t")
            if n and b:d[n]=base64.urlsafe_b64decode(b+"="*(-len(b)%4))
    return d
def contact_add(n,b):
    with open("lc_contacts.txt","a",encoding="utf-8") as f:
        f.write(f"{n}\t{base64.urlsafe_b64encode(b).decode().rstrip('=')}\n")
def vsave(p,o):
    n=os.urandom(12);a=ChaCha20Poly1305(hmac_sha256(VAULT,b"vault"))
    open(p,"w").write(b64(n+a.encrypt(n,json.dumps(o).encode(),None)))
def vload(p):
    r=ub64(open(p).read().strip());a=ChaCha20Poly1305(hmac_sha256(VAULT,b"vault"))
    return json.loads(a.decrypt(r[:12],r[12:],None))

class Session:
    def __init__(s,sid,root,role,sck=None,rck=None,sn=0,rn=0,hsend=None,hrecv=None,skipped=None):
        s.sid=sid;s.role=role
        if sck is None:
            ckAB=hkdf(root,b"ck",b"AtoB",32);ckBA=hkdf(root,b"ck",b"BtoA",32)
            hkAB=hkdf(root,b"hk",b"AtoB",32);hkBA=hkdf(root,b"hk",b"BtoA",32)
            if role=="init":s.sck,s.rck,s.hsend,s.hrecv=ckAB,ckBA,hkAB,hkBA
            else:s.sck,s.rck,s.hsend,s.hrecv=ckBA,ckAB,hkBA,hkAB
        else:
            s.sck,s.rck,s.hsend,s.hrecv=sck,rck,hsend,hrecv
        s.sn,s.rn=sn,rn
        s.skipped=skipped or {}
    def encrypt(s,pt,mf,pf):
        pd=pad(pt);tot=len(pd);mid=os.urandom(8).hex();pk=[]
        for ci in range(0,tot,CHUNK):
            ch=pd[ci:ci+CHUNK]
            mk,s.sck=kdf_ck(s.sck);n=s.sn;s.sn+=1
            h={"n":n,"tot":tot,"ci":ci//CHUNK,"mid":mid,"pl":0}
            hj=json.dumps(h,sort_keys=True).encode();h["pl"]=lca_size(len(ch))
            hj=json.dumps(h,sort_keys=True).encode();hj+=b" "*(HJ-len(hj))
            aad=APP_AAD+s.sid+hj+b"".join(sorted((mf,pf)))
            l1=lca_encrypt(mk,ch,aad);pay=l1+os.urandom(PAYLOAD_MAX-len(l1));no=os.urandom(12)
            pk.append(no+ChaCha20Poly1305(s.hsend).encrypt(no,hj,b"")+pay)
        return pk
    def try_decrypt(s,pkt,mf,pf):
        no,ct,pay=pkt[:12],pkt[12:12+HJ+16],pkt[12+HJ+16:]
        try:hj=ChaCha20Poly1305(s.hrecv).decrypt(no,ct,b"")
        except InvalidTag:raise ValueError("not-for-session")
        h=json.loads(hj.rstrip());n=h["n"]
        if n>MAXN:raise ValueError("bounds")
        if n in s.skipped:mk=s.skipped.pop(n)
        elif n<s.rn:raise ValueError("replay")
        else:
            while s.rn<n:
                if len(s.skipped)>=MAXSKIPPED:raise ValueError("ovf")
                m2,s.rck=kdf_ck(s.rck);s.skipped[s.rn]=m2;s.rn+=1
            mk,s.rck=kdf_ck(s.rck);s.rn=n+1
        aad=APP_AAD+s.sid+hj+b"".join(sorted((mf,pf)))
        ch,ts=lca_decrypt(mk,pay[:h["pl"]],aad);check_fresh(ts[0])
        return h["tot"],h["ci"],h["mid"],ch
    def save(s,p):
        vsave(f"lc_session_{p}.json",{"sid":b64(s.sid),"role":s.role,"sck":b64(s.sck),"rck":b64(s.rck),
            "sn":s.sn,"rn":s.rn,"hsend":b64(s.hsend),"hrecv":b64(s.hrecv),
            "sk":{str(k):b64(v) for k,v in s.skipped.items()}})
    @staticmethod
    def load(p):
        d=vload(f"lc_session_{p}.json")
        return Session(ub64(d["sid"]),None,d["role"],ub64(d["sck"]),ub64(d["rck"]),
            d["sn"],d["rn"],ub64(d["hsend"]),ub64(d["hrecv"]),
            {int(k):ub64(v) for k,v in d["sk"].items()})

# ===== PQ + Forward-Secrecy handshake (static bind + ephemeral FS) =====
def hs_req(idn,pb):
    me=idn["pq_pk"]
    eA_sk,eA_pk=PQ_KEM.generate_keypair()          # ephemeral, erased after use
    ctb,ssb=PQ_KEM.encaps(pb)                       # bind to B static
    pay=tlv(b"LCREQ",me,eA_pk,ctb,now8(),os.urandom(16))
    k1=hkdf(ssb+pair_h(me,pb),b"m",b"k1")
    blob=pay+hmac_sha256(k1,pay)
    return blob,{"eA_sk":b64(eA_sk),"ssb":b64(ssb),"reqblob":b64(blob),"peer":b64(pb)}
def hs_rsp(idn,rb):
    pay,mac=rb[:-32],rb[-32:]
    f,_=untlv(pay,6);tag,meA,eA_pk,ctb,ts,_=f
    if tag!=b"LCREQ":raise ValueError("not an invite")
    check_fresh(ts)
    meB=idn["pq_pk"]
    ssb=PQ_KEM.decaps(ctb,idn["pq_sk"])
    k1=hkdf(ssb+pair_h(meA,meB),b"m",b"k1")
    if not hmac.compare_digest(mac,hmac_sha256(k1,pay)):raise ValueError("auth")
    ctf,ssf=PQ_KEM.encaps(eA_pk)                    # FS term (only eA_sk recovers it)
    rsp=tlv(b"LCRSP",hashlib.sha256(rb).digest(),ctf,now8(),os.urandom(16))
    k2=hkdf(ssf+pair_h(meA,meB),b"m",b"k2")
    sid=hashlib.sha256(rb+rsp).digest()
    root=hkdf(ssb+ssf+pair_h(meA,meB),sid,b"root")
    return rsp+hmac_sha256(k2,rsp),Session(sid,root,"resp")
def hs_complete(idn,pend,rsb):
    pay,mac=rsb[:-32],rsb[-32:]
    f,_=untlv(pay,5);tag,rh,ctf,ts,_=f
    if tag!=b"LCRSP":raise ValueError("not a reply")
    check_fresh(ts)
    reqb=ub64(pend["reqblob"])
    if rh!=hashlib.sha256(reqb).digest():raise ValueError("mismatch")
    meA=idn["pq_pk"];pb=ub64(pend["peer"])
    eA_sk=ub64(pend["eA_sk"])
    ssf=PQ_KEM.decaps(ctf,eA_sk)
    eA_sk=None                                       # erase ephemeral -> forward secrecy
    ssb=ub64(pend["ssb"])
    k2=hkdf(ssf+pair_h(meA,pb),b"m",b"k2")
    if not hmac.compare_digest(mac,hmac_sha256(k2,pay)):raise ValueError("auth")
    sid=hashlib.sha256(reqb+pay).digest()
    root=hkdf(ssb+ssf+pair_h(meA,pb),sid,b"root")
    return Session(sid,root,"init")
def feed(s,pkt,mf,pf,buf):
    tot,ci,mid,ch=s.try_decrypt(pkt,mf,pf)
    b=buf.setdefault(mid,{"tot":tot,"parts":{}});b["parts"][ci]=ch
    need=(tot+CHUNK-1)//CHUNK
    if len(b["parts"])==need:
        pd=b"".join(b["parts"][i] for i in range(need))[:tot];del buf[mid];return unpad(pd)
    return None

HELP="""DERF PQ+FS — post-quantum AND forward-secret two-box tool

All asymmetric crypto is ML-KEM-768 (NIST L3). The handshake adds an
EPHEMERAL ML-KEM keypair so old sessions stay secret even if your long-term
key is stolen later (forward secrecy). Ratchet + MACs use SHA-256/HMAC/
ChaCha20 (quantum-safe). No RSA/ECC/X25519 anywhere.

SECURITY
 - Wrong vault passkey => app closes.
 - One instance at a time. Change passkey re-encrypts everything.
 - NUKE shreds all keys/contacts/sessions (7-pass).

ENCRYPT: pick person, type, ENCRYPT -> copied. DECRYPT: paste -> DECRYPT.
PAIRING (once): exchange keys; invite -> reply -> finish. Compare safety code.
RULES: open within 7 min.
"""

class App:
    def __init__(self,root):
        self.root=root;root.title(f"Derf PQ+FS — {PQ_KEM.name}");root.geometry("960x780")
        try:ttk.Style().theme_use("clam")
        except Exception:pass
        self.buffers={}
        self.vault_prompt()
        if not self.check_vault():
            messagebox.showerror("Wrong Passkey","Incorrect vault passphrase. Closing to protect your data.")
            root.destroy();sys.exit(1)
        self.ensure_identity();self.build();self.status("Ready.")
    def vault_prompt(self):
        global VAULT
        self._pw=""
        d=tk.Toplevel(self.root);d.title("Unlock Derf");d.geometry("380x130");d.resizable(False,False)
        d.transient(self.root);d.grab_set()
        ttk.Label(d,text="Vault passphrase:").pack(pady=6)
        e=ttk.Entry(d,show="*");e.pack(fill="x",padx=20);e.focus()
        def go():
            self._pw=e.get();d.destroy()
        ttk.Button(d,text="Unlock",command=go).pack(pady=6);e.bind("<Return>",lambda ev:go())
        self.root.wait_window(d)
        if not self._pw:self.root.destroy();sys.exit(0)
        VAULT=derive_vault(self._pw)
    def check_vault(self):
        if not os.path.exists("lc_identity.json"):return True
        try:vload("lc_identity.json");return True
        except Exception:return False
    def ensure_identity(self):
        if os.path.exists("lc_identity.json"):
            try:
                d=vload("lc_identity.json");self.idn={"pq_sk":ub64(d["pq_sk"]),"pq_pk":ub64(d["pq_pk"])};return
            except Exception as e:
                messagebox.showerror("Fatal",f"Identity corrupted: {e}");self.root.destroy();sys.exit(1)
        self.idn=make_identity()
        vsave("lc_identity.json",{"pq_sk":b64(self.idn["pq_sk"]),"pq_pk":b64(self.idn["pq_pk"])})
    def my_pub(self):return "LCAP1-"+base64.urlsafe_b64encode(id_bundle(self.idn)).decode().rstrip("=")
    def clip_set(self,s):self.root.clipboard_clear();self.root.clipboard_append(s)
    def clip_get(self):
        try:return self.root.clipboard_get()
        except Exception:return ""
    def status(self,m):self.statvar.set(m)
    def change_passkey(self):
        d=tk.Toplevel(self.root);d.title("Change passkey");d.geometry("400x190");d.transient(self.root);d.grab_set()
        ttk.Label(d,text="New passphrase:").pack(pady=2)
        e1=ttk.Entry(d,show="*");e1.pack(fill="x",padx=20)
        ttk.Label(d,text="Confirm:").pack(pady=2)
        e2=ttk.Entry(d,show="*");e2.pack(fill="x",padx=20)
        def go():
            a,b=e1.get(),e2.get()
            if not a:return messagebox.showerror("Change","Empty.")
            if a!=b:return messagebox.showerror("Change","Don't match.")
            self._rekey(a);d.destroy()
        ttk.Button(d,text="Change",command=go).pack(pady=8)
        self.root.wait_window(d)
    def _rekey(self,newpw):
        global VAULT
        files=["lc_identity.json"]+glob.glob("lc_session_*.json")+glob.glob("lc_pending_*.json")
        data={}
        for f in files:
            try:data[f]=vload(f)
            except Exception:pass
        VAULT=derive_vault(newpw)
        for f,dta in data.items():vsave(f,dta)
        self.status("Passkey changed.")
        messagebox.showinfo("Changed","Passkey changed.")
    def build(self):
        nb=ttk.Notebook(self.root);nb.pack(fill="both",expand=True,padx=8,pady=8)
        self.build_main(nb);self.build_people(nb);self.build_help(nb)
    def build_main(self,nb):
        f=ttk.Frame(nb);nb.add(f,text="  🔒 Encrypt /  Decrypt  ")
        ef=ttk.LabelFrame(f,text=" ENCRYPT — normal → encrypted ");ef.pack(fill="x",padx=10,pady=8)
        r=ttk.Frame(ef);r.pack(fill="x",padx=8,pady=4)
        ttk.Label(r,text="To:").pack(side="left")
        self.enc_to=ttk.Combobox(r,width=24);self.enc_to.pack(side="left",padx=4)
        ttk.Button(r,text="refresh",command=self.refresh_people).pack(side="left")
        self.enc_in=tk.Text(ef,height=5,font=("",12),wrap="word");self.enc_in.pack(fill="x",padx=8,pady=4)
        b1=ttk.Frame(ef);b1.pack(pady=4)
        ttk.Button(b1,text="🔒  ENCRYPT  →  copy",command=self.do_encrypt).pack(side="left",padx=4)
        self.enc_out=tk.Text(ef,height=4,font=("Consolas",10),wrap="word");self.enc_out.pack(fill="x",padx=8,pady=4)
        ttk.Button(ef,text="Copy encrypted again",command=lambda:(self.clip_set(self.enc_out.get("1.0",tk.END).strip()),self.status("Copied."))).pack(pady=2)
        df=ttk.LabelFrame(f,text=" DECRYPT — encrypted → normal ");df.pack(fill="both",expand=True,padx=10,pady=8)
        self.dec_in=tk.Text(df,height=5,font=("Consolas",10),wrap="word");self.dec_in.pack(fill="x",padx=8,pady=4)
        b2=ttk.Frame(df);b2.pack(pady=4)
        ttk.Button(b2,text="📋 paste",command=lambda:(self.dec_in.delete("1.0",tk.END),self.dec_in.insert(tk.END,self.clip_get()))).pack(side="left",padx=4)
        ttk.Button(b2,text="🔓  DECRYPT",command=lambda:self.do_decrypt(self.dec_in.get("1.0",tk.END))).pack(side="left",padx=4)
        self.dec_out=tk.Text(df,height=6,font=("",12),wrap="word");self.dec_out.pack(fill="both",expand=True,padx=8,pady=4)
        ttk.Button(df,text="Copy decrypted",command=lambda:(self.clip_set(self.dec_out.get("1.0",tk.END).strip()),self.status("Copied."))).pack(pady=2)
        sb=ttk.Frame(self.root);sb.pack(fill="x",padx=8,pady=4)
        self.statvar=tk.StringVar();ttk.Label(sb,textvariable=self.statvar,foreground="#555").pack(side="left")
        self.refresh_people()
    def paired(self):return [n for n in contacts_load() if os.path.exists(f"lc_session_{n}.json")]
    def refresh_people(self):self.enc_to["values"]=self.paired()
    def do_encrypt(self):
        n=self.enc_to.get()
        if not n or n not in self.paired():return messagebox.showerror("Encrypt","Pick a paired person.")
        text=self.enc_in.get("1.0",tk.END).strip()
        if not text:return messagebox.showerror("Encrypt","Type a message.")
        try:
            s=Session.load(n);cs=contacts_load()
            pk=s.encrypt(text.encode(),id_fp(id_bundle(self.idn)),id_fp(cs[n]));s.save(n)
            out="\n".join(b64(p) for p in pk)
            self.enc_out.delete("1.0",tk.END);self.enc_out.insert(tk.END,out)
            self.clip_set(out);self.enc_in.delete("1.0",tk.END)
            self.status(f"Encrypted {len(pk)} packet(s) — copied.")
        except Exception as e:messagebox.showerror("Encrypt",f"{e}")
    def do_decrypt(self,raw):
        lines=[l for l in raw.splitlines() if l.strip()]
        if not lines:return messagebox.showerror("Decrypt","Paste encrypted text first.")
        try:pkts=[ub64(clean_b64(l)) for l in lines]
        except Exception:return messagebox.showerror("Decrypt","Not valid encrypted text.")
        cs=contacts_load();me=id_fp(id_bundle(self.idn))
        for n in self.paired():
            s=Session.load(n);got=0;msgs=[]
            for p in pkts:
                try:
                    out=feed(s,p,me,id_fp(cs[n]),self.buffers)
                    if out:msgs.append(out.decode());got+=1
                except Exception:pass
            if got:
                s.save(n)
                self.dec_out.delete("1.0",tk.END);self.dec_out.insert(tk.END,"\n".join(msgs))
                self.status(f"Decrypted from {n}.");return
        messagebox.showerror("Decrypt","Nothing decrypted.")
    def build_people(self,nb):
        f=ttk.Frame(nb);nb.add(f,text="  👥 People (one-time setup)  ")
        me=ttk.LabelFrame(f,text=" 1. YOUR identity (ML-KEM-768) ");me.pack(fill="x",padx=10,pady=6)
        self.my_t=tk.Text(me,height=3,wrap="word");self.my_t.pack(fill="x",padx=8,pady=4)
        self.my_t.insert(tk.END,self.my_pub())
        bf=ttk.Frame(me);bf.pack(pady=3)
        ttk.Button(bf,text="Copy my public key",command=lambda:(self.clip_set(self.my_pub()),self.status("Your key copied."))).pack(side="left",padx=4)
        ttk.Button(bf,text="🔑 Change passkey",command=self.change_passkey).pack(side="left",padx=4)
        add=ttk.LabelFrame(f,text=" 2. ADD a person ");add.pack(fill="x",padx=10,pady=6)
        a=ttk.Frame(add);a.pack(fill="x",padx=8,pady=4)
        ttk.Label(a,text="Name:").pack(side="left")
        self.p_name=ttk.Entry(a,width=16);self.p_name.pack(side="left",padx=4)
        ttk.Button(a,text="paste their key",command=lambda:(self.p_key.delete("1.0",tk.END),self.p_key.insert(tk.END,self.clip_get()))).pack(side="left",padx=4)
        self.p_key=tk.Text(add,height=3,wrap="word");self.p_key.pack(fill="x",padx=8,pady=4)
        ttk.Button(add,text="Add person →",command=self.add_person).pack(pady=3)
        self.pair_frame=ttk.LabelFrame(f,text=" 3. PAIR (one-time) ");self.pair_frame.pack(fill="both",expand=True,padx=10,pady=6)
        ttk.Label(self.pair_frame,text="Add a person above to start pairing.",foreground="#777").pack(pady=10)
        self.list_f=ttk.LabelFrame(f,text=" Your people ");self.list_f.pack(fill="x",padx=10,pady=6)
        self.people_list=tk.Text(self.list_f,height=4);self.people_list.pack(fill="x",padx=8,pady=4)
        tk.Button(f,text="🚨 NUKE ALL DATA",command=self.nuke_everything,bg="darkred",fg="white",font=("",11,"bold")).pack(pady=20)
        self.refresh_list()
    def nuke_everything(self):
        if not messagebox.askyesno("NUKE","Destroy ALL keys/contacts/sessions? Cannot be undone."):return
        if not messagebox.askyesno("CONFIRM","Final warning. Proceed?"):return
        nuke_all_files();self.clip_set("");self.idn=None;self.buffers={}
        messagebox.showinfo("Nuked","All data destroyed. Closing.");self.root.destroy()
    def refresh_list(self):
        self.people_list.delete("1.0",tk.END)
        for n,b in contacts_load().items():
            st="paired" if os.path.exists(f"lc_session_{n}.json") else "not paired"
            self.people_list.insert(tk.END,f"{n:14s} [{st}]  safety={safety_code(id_bundle(self.idn),b)}\n")
    def add_person(self):
        n=self.p_name.get().strip();raw=self.p_key.get("1.0",tk.END).strip()
        if not n or not raw:return messagebox.showerror("Add","Name + key required.")
        try:b=parse_pubkey(raw)
        except Exception:return messagebox.showerror("Add","Bad key.")
        contact_add(n,b);self.refresh_list();self.refresh_people();self.build_pairing(n,b)
    def build_pairing(self,name,bundle):
        for w in self.pair_frame.winfo_children():w.destroy()
        b=self.pair_frame
        ttk.Label(b,text=f"Pair with {name} — ONCE.",font=("",11,"bold")).pack(pady=4)
        self.var=tk.IntVar(value=0)
        ttk.Radiobutton(b,text="I start (send invite)",variable=self.var,value=0).pack()
        ttk.Radiobutton(b,text="They started (paste invite)",variable=self.var,value=1).pack()
        ttk.Button(b,text="Begin →",command=lambda:self.start_pair(name,bundle)).pack(pady=6)
    def start_pair(self,name,bundle):
        for w in self.pair_frame.winfo_children():w.destroy()
        b=self.pair_frame
        if self.var.get()==0:
            req,pend=hs_req(self.idn,bundle);vsave(f"lc_pending_{name}.json",pend)
            self.inv=b64(req)
            ttk.Label(b,text="A) SEND this invite:",font=("",11,"bold")).pack()
            t=tk.Text(b,height=4,wrap="word");t.pack(fill="x",padx=8);t.insert(tk.END,self.inv)
            ttk.Button(b,text="Copy invite",command=lambda:(self.clip_set(self.inv),self.status("Invite copied."))).pack(pady=2)
            ttk.Label(b,text="B) Paste their REPLY and Finish:").pack()
            self.re=tk.Text(b,height=4,wrap="word");self.re.pack(fill="x",padx=8)
            bb=ttk.Frame(b);bb.pack(pady=4)
            ttk.Button(bb,text="paste reply",command=lambda:(self.re.delete("1.0",tk.END),self.re.insert(tk.END,self.clip_get()))).pack(side="left",padx=4)
            ttk.Button(bb,text="Finish ✓",command=lambda:self.finish_a(name)).pack(side="left",padx=4)
        else:
            ttk.Label(b,text="A) PASTE their invite:",font=("",11,"bold")).pack()
            self.inv=tk.Text(b,height=4,wrap="word");self.inv.pack(fill="x",padx=8)
            ttk.Button(b,text="paste invite",command=lambda:(self.inv.delete("1.0",tk.END),self.inv.insert(tk.END,self.clip_get()))).pack(pady=2)
            ttk.Button(b,text="B) Create reply →",command=lambda:self.make_reply(name)).pack(pady=2)
            self.rep=tk.Text(b,height=4,wrap="word");self.rep.pack(fill="x",padx=8)
            ttk.Button(b,text="Copy reply & finish ✓",command=self.finish_b).pack(pady=4)
    def finish_a(self,name):
        try:
            hs_complete(self.idn,vload(f"lc_pending_{name}.json"),ub64(clean_b64(self.re.get("1.0",tk.END)))).save(name)
            os.remove(f"lc_pending_{name}.json")
        except Exception as e:return messagebox.showerror("Pair",f"{e}")
        self.done_pair()
    def make_reply(self,name):
        try:
            rsp,sess=hs_rsp(self.idn,ub64(clean_b64(self.inv.get("1.0",tk.END))))
            sess.save(name);self.reply=b64(rsp)
            self.rep.delete("1.0",tk.END);self.rep.insert(tk.END,self.reply)
        except Exception as e:messagebox.showerror("Pair",f"{e}")
    def finish_b(self):
        if not getattr(self,"reply",None):return messagebox.showerror("Pair","Create the reply first.")
        self.clip_set(self.reply);self.done_pair()
    def done_pair(self):
        self.refresh_list();self.refresh_people();self.status("Paired!")
        messagebox.showinfo("Paired","Done! Use the Encrypt/Decrypt tab.")
    def build_help(self,nb):
        f=ttk.Frame(nb);nb.add(f,text="  ❓ Help  ")
        t=tk.Text(f,wrap="word");t.pack(fill="both",expand=True,padx=10,pady=10)
        t.insert(tk.END,HELP);t.config(state="disabled")

def main():
    if not _single():
        r=tk.Tk();r.withdraw()
        messagebox.showerror("Derf","Another instance is already running. Only one at a time.")
        r.destroy();return
    root=tk.Tk();App(root);root.mainloop()
if __name__=="__main__":
    main()
