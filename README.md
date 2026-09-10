# DERF — Post-Quantum Deniable Messenger 🔒

**Deniable, post-quantum, per-letter-chained encrypted messenger** featuring a modern, cross-platform **Kivy UI** for **Linux, macOS, Windows, and Android**.

Derf implements per-letter chained AEAD (LCA) + Signal-style Double Ratchet + deniable X3DH-style **ML-KEM-768** hybrid handshake + uniform fixed-size packets + dead-drop transport. Messages are confidential, authentic, replay/order-protected, and **unprovable to third parties**.

---

## ✨ Features

- **⚡ Post-Quantum KEM (ML-KEM-768 / Kyber768)**: NIST FIPS 203 quantum-resistant key encapsulation resisting Shor's algorithm.
- **🔄 Signal-Style Double Ratchet**: High-grade Forward Secrecy & Post-Compromise Security.
- **🛡️ LC-AEAD Chained Encryption**: Per-letter ChaCha20-Poly1305 AEAD structure protecting message order and payload integrity.
- **🎭 Unprovable Deniability**: Deniable X3DH handshake using symmetric HKDF MACs instead of digital signatures.
- **📦 Uniform Packet Sizing**: Every ciphertext packet is padded to an exact uniform size, preventing packet length side-channel metadata leaks.
- **🔐 Encrypted Vault at Rest**: All identity keys, sessions, and contacts stored encrypted using 600,000 PBKDF2-HMAC-SHA256 iterations.
- **📱 Cross-Platform Kivy UI**: Premium dark obsidian UI designed for Desktop (Linux/macOS/Windows) and Mobile (Android).
- **🧪 Automated Selftest Suite**: Comprehensive built-in test suite (`--selftest`).

---

## 🛠️ Requirements

- **Python 3.9+**
- **Dependencies**: Listed in `requirements.txt` (`cryptography`, `kyber-py`, `kivy`).

---

## 🚀 Installation & Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-username/derf.git
cd derf
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

*(Optional)* For faster native C post-quantum execution via `liboqs`:
- **macOS**: `brew install liboqs && pip install liboqs-python`
- **Ubuntu/Debian**: `sudo apt install cmake gcc libssl-dev && pip install liboqs-python`

---

## 💻 How to Run

### Run the Graphical App (GUI)

```bash
python Derf.py
```

### Run Automated Selftest Suite

```bash
python Derf.py --selftest
```

### Customize Freshness Window (Default: 420 seconds / 7 minutes)

```bash
python Derf.py --fresh-sec 900
```

---

## 📲 Building for Android (Buildozer)

Derf is fully compatible with Android via Kivy and Buildozer.

1. Install Buildozer:
   ```bash
   pip install buildozer
   ```
2. Initialize and build APK:
   ```bash
   buildozer init
   buildozer -v android debug
   ```
3. Install APK on connected Android device:
   ```bash
   buildozer android deploy run
   ```

---

## 📖 Quickstart Guide (Alice & Bob)

1. **Vault Setup**: Both Alice and Bob launch `python Derf.py`, enter a master passphrase to unlock or initialize their encrypted vault.
2. **Exchange Keys**: Go to **Contacts & Pairing** tab -> Copy your `LCAP1-...` Public Key and paste it to add each other as a contact.
3. **One-Time Pairing**:
   - **Alice (Initiator)**: Selects "I Start", clicks **Execute Pairing Step** -> Copies the generated Base64 Invite and sends it to Bob.
   - **Bob (Responder)**: Selects "They Started", pastes Alice's Invite into Step 1, clicks **Execute Pairing Step** -> Copies the generated Reply and sends it back to Alice.
   - **Alice**: Pastes Bob's Reply into Step 2, clicks **Execute Pairing Step**. Pairing is complete!
4. **Out-of-Band Safety Code**: Compare the displayed 12-digit Safety Code out-of-band to verify key authenticity.
5. **Encrypt & Decrypt Messages**:
   - **Send**: Type plaintext in the Messages tab -> Click **LOCK & ENCRYPT** -> Copy Base64 packets or save to `Desktop/Derf/lc_drop/`.
   - **Receive**: Paste Base64 packets into Decrypt box -> Click **UNLOCK & DECRYPT**.

---

## 📂 File Directory Structure

All application data is automatically stored in `Desktop/Derf/`:

| File | Description |
|---|---|
| `lc_identity.json` | Master identity keypair (vault-encrypted) |
| `lc_contacts.txt` | Saved contact names & public keys |
| `lc_session_<peer>.json` | Active Double Ratchet session state (vault-encrypted) |
| `lc_pending_<peer>.json` | Pending handshake state (vault-encrypted) |
| `lc_drop/` | Dead-drop uniform ciphertext packet folder |

---

## 🧪 Verification & Security Properties

Derf guarantees:
- **Replay Protection**: Packets cannot be re-fed or duplicated.
- **Stale Packet Rejection**: Messages older than 7 minutes (configurable) are rejected.
- **Order & Truncation Enforcement**: Modifying packet sequence fails decryption.
- **Constant Size**: All packets are padded to `PACKET` bytes.

Verify your installation anytime by running:
```bash
python Derf.py --selftest
```

---

## ⚠️ Disclaimer

Derf is an educational/research construction. For standard real-world commercial secrecy, use Signal.
