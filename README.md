# Derf

**Deniable, post-quantum, per-letter-chained encrypted messenger** — single-file Python
console app. LC-AEAD per-letter chained AEAD + Signal-style Double Ratchet + deniable
X3DH-style **ML-KEM-768** handshake + uniform fixed-size packets + dead-drop transport.
Messages are confidential, authentic, replay/order-protected and **unprovable to third
parties**.

> ⚠️ Derf is an educational/research construction, **not audited**. For real-world secrecy,
> use Signal.

---

## Requirements

| Requirement | Notes |
|---|---|
| Python | **3.9+** |
| `cryptography` | **required** — ChaCha20-Poly1305, X25519, HKDF, PBKDF2 |
| PQ backend | **required** — `kyber-py` (pure Python, easiest on Windows) **or** `liboqs-python` (native, faster). Derf **refuses to start** without one. |

---

## Installation

### Linux / macOS

```bash
python -m pip install --upgrade pip
pip install cryptography kyber-py          # pure-python PQ: done
# OR faster native PQ instead of kyber-py:
#   macOS:  brew install liboqs && pip install liboqs-python
#   Ubuntu: sudo apt install cmake gcc libssl-dev git
#           git clone --depth 1 https://github.com/openquantumsafe/liboqs.git
#           cd liboqs && mkdir build && cd build && cmake -DBUILD_SHARED_LIBS=ON .. \
#             && make -j"$(nproc)" && sudo make install && sudo ldconfig
#           pip install liboqs-python
```

### Windows

**Method A — pure Python (recommended, no compiling):**

```powershell
winget install Python.Python.3.12
pip install cryptography kyber-py
```

**Method B — native liboqs (faster):**

```powershell
winget install Kitware.CMake
winget install Microsoft.VisualStudio.2022.BuildTools   # select "Desktop development with C++"
git clone --depth 1 https://github.com/openquantumsafe/liboqs.git
cd liboqs
mkdir build; cd build
cmake -G "Visual Studio 17 2022" -DBUILD_SHARED_LIBS=ON ..
cmake --build . --config Release
cmake --install . --config Release --prefix C:\liboqs
setx PATH "C:\liboqs\bin;%PATH%"
pip install liboqs-python
```

**Verify:**

```bash
python -c "import kyber_py" 2>nul || python -c "import liboqs"
```

---

## Run

```bash
python derf.py --selftest     # automated proof (round trip, replay/injection, uniformity)
python derf.py                # the app (asks vault passphrase)
python derf.py --fresh-sec 900  # change the 7-minute limit
```

---

## Quickstart (Alice & Bob)

1. Both: `[1]` create identity → exchange the printed `LCAP1-…` public keys; `[3]` add each
   other; compare the **safety code** out-of-band.
2. Alice `[4]` → sends REQ. Bob `[5]` pastes REQ → sends RSP. Alice `[6]` pastes RSP → live.
3. `[7]` send / `[8]` receive in both directions (print, file, or dead-drop `lc_drop/`).
4. Messages must be opened within **7 minutes**.

| Key | Action |
|---|---|
| 1 / 2 | create / load identity |
| 3 | contacts + safety codes |
| 4 / 5 / 6 | START / ANSWER / FINISH session |
| 7 / 8 | SEND / RECEIVE (print·file·drop) |
| 9 | WIPE all state |
| 0 | exit |

---

## Files

`lc_identity.json`, `lc_session_<peer>.json`, `lc_pending_<peer>.json` (vault-encrypted,
secret) · `lc_contacts.txt` (public keys) · `lc_drop/*.bin` (uniform ciphertext packets).

## Security properties

ML-KEM-768‖X25519 hybrid confidentiality · deniable MAC authentication (no signatures) ·
forward secrecy + post-compromise security · replay/reorder/truncation rejection ·
unprovability (revealed MAC keys) · encrypted headers + constant-size packets ·
encrypted state at rest · uniform `❌ rejected` errors.

**Cannot hide:** that uniform packets appeared on a channel when (use Tor/mixnets for
anonymity), endpoint compromise, supply-chain attacks; handshake blobs are not uniform.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `FATAL: no post-quantum backend` | `pip install kyber-py` (or liboqs, see above) |
| `❌ rejected` | wrong vault passphrase / >7 min old / replay / not your packet / tampered |
| `not ready` | responder must receive the peer's first message before sending |

## Disclaimer

No formal verification, no audit. "Perfect encryption" does not exist. Use at your own risk.
