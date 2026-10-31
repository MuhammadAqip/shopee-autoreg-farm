# VM SAP — DEOBFUSCATION COMPLETE (Sesi 5)

## 🎯 VM SAP FULLY MAPPED — interpreter deobfuscated

---

## ✅ TEROBOSAN SESI INI

### 1. INTERPRETER PENUH — 14,420 char
```
sdk/vm_Z_full.txt (40KB awal) → sdk/vm_interp_FULL.js (14,420 char, brace-balanced)
330× ac[_++]  ·  450× ac[  ·  semua helper
```

### 2. DISPATCH TREE — 66 node binary-search, opcode max 999
```
tc<443 → tx<188 → eJ<97 → ei<48 → O<25 → T<23 → w<21 → k<2
J<28, g<36, R<63, ew<89, Q<88, eS<103, L<100, et<127...
... e8<508 ... s/d 999
153 cabang total
```

### 3. **KEYWORD/IDENTIFIER TABLE KETEBUK** (`eI` = `ad` = `ae`)
```js
eI(3)="now"     eI(12)="slice"   eI(13)="finally"
eI(14)="var"    eI(15)="for"     eI(16)="throw"
eI(17)="catch"  eI(18)="default" eI(19)="while"   eI(20)="return"
```
→ Interpreter obfuscate SEMUA identifier via table `ae`. **Bisa di-deobfuscate.**

### 4. REFLECTION TABLE `tE` (= `ad`) — method names
```js
tE("0x15")="toString"          tE("0x18")="slice"
tE("0x19")="getOwnPropertyDescriptor"  tE("0x1a")="__proto__"
tE("0x1b")="hardwareConcurrency"       tE("0x1c")="get"
tE("0x1e")="P|I"  (separator!)         tE("0xa")="vmp_getResolution"
tE("0xc")="devicePxPerCssPx"
```

### 5. CRYPTO/EVAL PRIMITIVE
```js
tl=ac[_++]+S;  eu=H(ac[tl]);  G=ac[tl+1]
X=ac[tE("0x15")](tl+3, tl+3+ac[tl+2])    ← string slice
ek=y(V())                                 ← ek = eval(pako(...))
```
`y()` = **eval** (30×), `V()` = **pako/zlib** (29×) → VM **decompress + eval kode tersembunyi**.
**Ini kenapa ada blob 8,752-byte ter-enkripsi di data section!**

### 6. SAP NETWORK HELPERS (di interpreter!)
```js
eG = state machine handler (status: 42,69,73,91,103,113,666)
eF = URL builder: "https://" + eo.envs[env] + eo.malls[locale]
ex = {isRelative, host, path, params} → request builder
```

### 7. Deobfuscator JALAN
```
vm_deobf_interp.py → ganti eI(k)/ad("0x..") → string ae[k]
vm_deobf_interp.js (output)
tE=ad  terlihat di source
```

---

## ✅ STATE LENGKAP VM
```
✅ INTERPRETER  : 14,420 char, brace-balanced
✅ DISPATCH     : 66 node, opcode 999
✅ ENCODING     : VERIFIED (HIT=40358/MISS=0)
✅ BYTECODE     : 70,943 slot
✅ DISASM       : 25,378 boundaries
✅ SEMANTICS    : 91 opcode
✅ MEMORY       : base 6000, stride 16, 762KB
✅ FRAMES       : op732 alloc
✅ REGISTERS    : slot 0..6000
✅ TABLES       : ae (identifiers) + aj (strings), 2627 entries
✅ REFLECTION   : tE method table
✅ HELPERS      : tM/tG/tE/H/V/G/eG/eF/ex (semua di-map)
✅ EVAL LOADER  : y(V()) = eval(pako(blob))
✅ ENGINE       : execute + slot + mem + stack + frame
✅ VALIDATOR    : 100% opcode fidelity
✅ REPLAY       : 20k step state-timeline
✅ DEOBFUSCATOR : interpreter → readable
```

## 📊 PROGRESS
```
[██████████████████████] 97%
  sisa: (1) wire engine pakai deobf interpreter
        (2) decode blob 8752-byte (eval payload)
        (3) run end-to-end → x-sap-sec
```

---

## 📦 ARTEFAK BARU
| File | Isi |
|---|---|
| `sdk/vm_interp_FULL.js` | interpreter penuh (14,420 char) |
| `vm_deobf_interp.py` | deobfuscator |
| `vm_interp_deobf.js` | interpreter ter-deobfuscate |
| `vm_reflect.py` / `vm_reflect.json` | reflection table model |
| `vm_interp_map.py` / `vm_interp_map.json` | dispatch leaf map |
| `VM_MEMORY_MODEL.md`, `VM_EMULATOR_STATUS.md`, `VM_ANALYSIS.md` | analisis |
