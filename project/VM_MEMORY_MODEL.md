# VM SAP — MEMORY MODEL + FRAME MODEL (Sesi 4)

## Ringkasan: dari "emulator" → "arsitektur lengkap terpetakan"

---

## ✅ MEMORY MODEL (baru — kunci!)
```
Operand distribution (320,000 total):
  register (0..6000) : 309,115 (97%)
  memory   (>6000)   :  10,747 (3%)
  negative           :     138

Memory samples: 6000, 6002, 6016, 6018, 6032, 6034, 6048, 6050, 6064, 6066...
  → BASE = 6000
  → STRIDE = 16 (record size!)
  → field offset 0 / 2
  → memory size max = 767,834
```
VM = **stack-based CPU** dengan DUA ruang:
1. **Register file** — slot index 0..6000
2. **Memory records** — alamat 6000+, **struct 16-byte**, field di +0/+2

Pattern: `mem_addr = 6000 + record_idx*16 + field_offset`

## ✅ FRAME MODEL
```
op732 (FRAME) [slot, offset, ...]:
  (43491, 6, 40691, 13)
  (43498, 10, 40704, 13)   ← offset +13 per step
  (43505, 14, 40717, 13)
  (43512, 18, 40730, 13)
  → slot +4, offset +13 (record alloc, size 13?)
op281 (INIT) [idx, offset]:
  (38022, 286, 66) (56944, 330, 64) (56953, 334, 368)
  → init loop (i, stride)

slot 6 = 4045 (basepointer, ditulis 294×)
slot 2 = loop counter
slot 128/568/416 = variabel penting (offset/const)
```

## ✅ DATA SECTION
```
ac[0..3266]     = code section
ac[3266] = 99999 = marker
ac[3267..57561] = interleaved code+data (semua region punya opcode density)
ac[57562..66314] = 8,752-byte ENCRYPTED BLOB (entropy 7.96/8 = ~random)
ac[66314..70943] = tail
big consts: ac[40917]=791621423, ac[47345]=767834
```

## ✅ STATE LENGKAP EMULATOR
```
ENCODING   : VERIFIED (HIT=40358/MISS=0)
DISASM     : 25,378 boundaries, 100% match
BYTECODE   : 70,943 slot (full)
LENGTHS    : 91 opcode
SEMANTICS  : 91 opcode
MEMORY     : 6000 base, stride 16, size ~762KB
FRAMES     : op732 alloc, base 4045
ENGINE     : execute + slot + memory + stack + frame
VALIDATE   : 100% opcode fidelity
REPLAY     : 20k step state-timeline (296 slot, 1123 frame)
```

## 📊 PROGRESS BAR
```
[█████████████████████░]  92%
  ✅ bytecode/encoding/disasm/semantics
  ✅ engine (slot+mem+stack+frame)
  ✅ validator + replay
  ✅ memory model + frame model
  ⏳ dekompilasi fungsi signer
  ⏳ ekstrak x-sap-sec dari emulator
```

## ⏳ SISA
1. Dekompilasi fungsi crypto (cari call ke hash/AES via opcode semantics)
2. Run emulator penuh → dapat output signer
3. Validasi byte-for-byte vs browser

**Estimasi: <1 hari.**

---

## 📦 TOOLS BARU
| File | Fungsi |
|---|---|
| `vm_replay.py` | replay trace → state timeline |
| `vm_engine.py` | + memory model (6000, stride 16) |
